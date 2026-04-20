"""Main Tkinter application entry point and UI coordinator.

Owns shared app state and delegates focused behavior to controller modules.
"""

import os
import sys
import json
import time
import copy
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser
import threading

os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")

try:
    import cv2  # type: ignore
except ModuleNotFoundError as exc:
    if getattr(exc, "name", None) != "cv2":
        raise
    raise ModuleNotFoundError(
        "OpenCV (cv2) is required to run JetAnalyzer from source.\n"
        "\n"
        "Install dependencies:\n"
        "  - From the project root: `python -m pip install -r requirements.txt`\n"
        "  - From the Code folder:  `python -m pip install -r ..\\requirements.txt`\n"
        "\n"
        "Or run `run_gui.ps1` (from the project root), or `..\\run_gui.ps1` (from Code/).\n"
        f"\nPython executable: {sys.executable}"
    ) from exc

try:
    cv2.setLogLevel(0)
except Exception:
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
    except Exception:
        pass

try:
    import numpy as np  # type: ignore
except ModuleNotFoundError as exc:
    if getattr(exc, "name", None) != "numpy":
        raise
    raise ModuleNotFoundError(
        "numpy is required to run JetAnalyzer from source.\n"
        "\n"
        "Install dependencies:\n"
        "  - From the project root: `python -m pip install -r requirements.txt`\n"
        "  - From the Code folder:  `python -m pip install -r ..\\requirements.txt`\n"
        "\n"
        "Or run `run_gui.ps1` (from the project root), or `..\\run_gui.ps1` (from Code/).\n"
        f"\nPython executable: {sys.executable}"
    ) from exc
try:
    import customtkinter as ctk
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "customtkinter is required for the modernized UI. "
        "Install dependencies with `python -m pip install -r ..\\requirements.txt` "
        "when running from the Code folder, or `python -m pip install customtkinter`."
    ) from exc

# Prefer smooth cross-monitor dragging over per-monitor UI rescaling.
ctk.deactivate_automatic_dpi_awareness()

from analysis_engine import JetAnalysisConfig, process_video
from camera_capture import create_camera_capture, list_available_cameras
from display_controller import DisplayController
from documentation_controller import DocumentationController
from graph_controller import GraphController
from gui_widgets import HoverTooltip, RangeSlider
from project_state_controller import ProjectStateController
from range_controller import RangeController
from status_controller import StatusController
from live_engine import LiveEngine


DEFAULTS = {
    "threshold_offset": 15,
    "multi_threshold_offsets": [7, 20, 30, 40, 50],
    "multi_threshold_weights": [1, 1, 1, 1, 1, 1],
    "multi_threshold_colors": ["#000000", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd", "#1f77b4"],
    "frame_stride": 1,
    "pixels_per_col": 3,
    "stdevs": 2,
    "output_name": "analysis_output",
    "threshold_output_name": "threshold_output",
    "output_dir": "",
    "save_analysis_output": True,
    "save_threshold_output": False,
    "analysis_output_format": "AVI (.avi)",
    "threshold_output_format": "AVI (.avi)",
    "analysis_output_path": "",
    "threshold_output_path": "",
    "preview_mode": "analysis",
    "show_preview_std_region": True,
    "show_preview_frame_dots": True,
    "show_preview_mean_line": True,
    "apply_preview_overlay_to_output": False,
    "use_multi_threshold": False,
    "live_frame_limit": "",
    "num_thresholds": 1,
    "graph_stdevs": "2",
    "graph_fit_degree": "2",
    "show_best_fit": True,
    "graph_view_mode": "Profile",
    "graph_value_type": "Actual (mm)",
    "graph_title": "",
    "graph_profile_value_mode": "Actual Values",
    "graph_column_value_mode": "Pixel Values",
    "graph_distribution_kind": "Residuals",
    "graph_histogram_scope": "All Columns",
    "graph_distribution_column_px": "0",
    "graph_distribution_bins": "20",
    "graph_x_axis_label": "Horizontal Position (px)",
    "graph_y_axis_label": "Vertical Position (px)",
    "graph_x_min": "",
    "graph_x_max": "",
    "graph_y_min": "",
    "graph_y_max": "",
    "calibration_units": "mm",
}
INPUT_VIDEO_FILETYPES = [
    ("Video Files", "*.mp4 *.avi *.mov *.mkv *.wmv *.m4v *.mpg *.mpeg"),
    ("MP4", "*.mp4 *.m4v"),
    ("AVI", "*.avi"),
    ("QuickTime", "*.mov"),
    ("Matroska", "*.mkv"),
    ("Windows Media", "*.wmv"),
    ("MPEG", "*.mpg *.mpeg"),
    ("All Files", "*.*"),
]
OUTPUT_FORMATS = {
    "AVI (.avi)": ".avi",
    "MP4 (.mp4)": ".mp4",
    "MOV (.mov)": ".mov",
    "MKV (.mkv)": ".mkv",
    "WMV (.wmv)": ".wmv",
    "MPEG (.mpeg)": ".mpeg",
}
DEFAULT_DOC_FILENAME = "app_documentation.md"
APP_SETTINGS_FILENAME = "app_settings.json"
STARTUP_PROJECT_FILENAMES = [
    # When packaged: projects/ folder sits next to the exe
    os.path.join("projects", "sample_project.json"),
    os.path.join("projects", "test_project.json"),
    # When running from source: projects/ is one level above Code/
    os.path.join("..", "projects", "sample_project.json"),
    os.path.join("..", "projects", "test_project.json"),
    "sample_project.json",
    "test_project.json",
]


def _get_app_dir():
    """Return the writable app directory (next to the .exe when frozen, else Code/ dir)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_resource_dir():
    """Return the read-only resource directory (unpacked _internal/ when frozen, else Code/ dir)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_app_settings_path():
    return os.path.join(_get_app_dir(), APP_SETTINGS_FILENAME)


def _to_portable_app_path(path_value):
    path_text = str(path_value or "").strip()
    if not path_text:
        return ""

    normalized = os.path.normpath(path_text)
    if not os.path.isabs(normalized):
        return normalized

    try:
        return os.path.normpath(os.path.relpath(normalized, _get_app_dir()))
    except ValueError:
        return normalized


def _resolve_app_path(path_value):
    path_text = str(path_value or "").strip()
    if not path_text:
        return ""

    normalized = os.path.normpath(path_text)
    if os.path.isabs(normalized):
        return normalized
    return os.path.normpath(os.path.join(_get_app_dir(), normalized))


def normalize_app_defaults(saved_defaults):
    merged = copy.deepcopy(DEFAULTS)
    if not isinstance(saved_defaults, dict):
        return merged

    merged.update({k: v for k, v in saved_defaults.items() if k in merged})

    merged["multi_threshold_offsets"] = list(saved_defaults.get("multi_threshold_offsets", merged["multi_threshold_offsets"]))[:5]
    while len(merged["multi_threshold_offsets"]) < 5:
        merged["multi_threshold_offsets"].append(DEFAULTS["multi_threshold_offsets"][len(merged["multi_threshold_offsets"])])

    merged["multi_threshold_weights"] = list(saved_defaults.get("multi_threshold_weights", merged["multi_threshold_weights"]))[:6]
    while len(merged["multi_threshold_weights"]) < 6:
        merged["multi_threshold_weights"].append(DEFAULTS["multi_threshold_weights"][len(merged["multi_threshold_weights"])])

    merged["multi_threshold_colors"] = list(saved_defaults.get("multi_threshold_colors", merged["multi_threshold_colors"]))[:6]
    while len(merged["multi_threshold_colors"]) < 6:
        merged["multi_threshold_colors"].append(DEFAULTS["multi_threshold_colors"][len(merged["multi_threshold_colors"])])

    if merged.get("analysis_output_format") not in OUTPUT_FORMATS:
        merged["analysis_output_format"] = DEFAULTS["analysis_output_format"]
    if merged.get("threshold_output_format") not in OUTPUT_FORMATS:
        merged["threshold_output_format"] = DEFAULTS["threshold_output_format"]

    try:
        merged["threshold_offset"] = int(merged["threshold_offset"])
    except (TypeError, ValueError):
        merged["threshold_offset"] = DEFAULTS["threshold_offset"]

    try:
        merged["frame_stride"] = int(merged["frame_stride"])
    except (TypeError, ValueError):
        merged["frame_stride"] = DEFAULTS["frame_stride"]
    if merged["frame_stride"] < 1:
        merged["frame_stride"] = DEFAULTS["frame_stride"]

    try:
        merged["pixels_per_col"] = int(merged["pixels_per_col"])
    except (TypeError, ValueError):
        merged["pixels_per_col"] = DEFAULTS["pixels_per_col"]

    try:
        merged["stdevs"] = int(merged["stdevs"])
    except (TypeError, ValueError):
        merged["stdevs"] = DEFAULTS["stdevs"]

    try:
        merged["num_thresholds"] = max(1, min(5, int(merged["num_thresholds"])))
    except (TypeError, ValueError):
        merged["num_thresholds"] = DEFAULTS["num_thresholds"]

    merged["save_analysis_output"] = bool(merged.get("save_analysis_output", DEFAULTS["save_analysis_output"]))
    merged["save_threshold_output"] = bool(merged.get("save_threshold_output", DEFAULTS["save_threshold_output"]))
    merged["show_best_fit"] = bool(merged.get("show_best_fit", DEFAULTS["show_best_fit"]))
    merged["show_preview_std_region"] = bool(merged.get("show_preview_std_region", DEFAULTS["show_preview_std_region"]))
    merged["show_preview_frame_dots"] = bool(merged.get("show_preview_frame_dots", DEFAULTS["show_preview_frame_dots"]))
    merged["show_preview_mean_line"] = bool(merged.get("show_preview_mean_line", DEFAULTS["show_preview_mean_line"]))
    merged["apply_preview_overlay_to_output"] = bool(merged.get("apply_preview_overlay_to_output", DEFAULTS["apply_preview_overlay_to_output"]))
    merged["use_multi_threshold"] = bool(merged.get("use_multi_threshold", DEFAULTS["use_multi_threshold"]))

    merged["preview_mode"] = merged.get("preview_mode") if merged.get("preview_mode") in ("analysis", "threshold") else DEFAULTS["preview_mode"]
    merged["calibration_units"] = merged.get("calibration_units") if merged.get("calibration_units") in ("mm", "cm", "in") else DEFAULTS["calibration_units"]

    merged["graph_view_mode"] = merged.get("graph_view_mode") if merged.get("graph_view_mode") in ("Profile", "Histogram", "Q-Q Plot") else DEFAULTS["graph_view_mode"]
    if merged.get("graph_value_type") in ("Actual (mm)", "Pixel"):
        pass
    else:
        legacy_profile = str(saved_defaults.get("graph_profile_value_mode", "")).strip()
        legacy_column = str(saved_defaults.get("graph_column_value_mode", "")).strip()
        if legacy_profile == "Pixel Values" or legacy_column == "Pixel Values":
            merged["graph_value_type"] = "Pixel"
        else:
            merged["graph_value_type"] = DEFAULTS["graph_value_type"]
    merged["graph_profile_value_mode"] = merged.get("graph_profile_value_mode") if merged.get("graph_profile_value_mode") in ("Actual Values", "Pixel Values") else DEFAULTS["graph_profile_value_mode"]
    merged["graph_column_value_mode"] = merged.get("graph_column_value_mode") if merged.get("graph_column_value_mode") in ("Pixel Values", "Actual Values") else DEFAULTS["graph_column_value_mode"]
    merged["graph_distribution_kind"] = merged.get("graph_distribution_kind") if merged.get("graph_distribution_kind") in ("Residuals", "Positions", "Z-Scores") else DEFAULTS["graph_distribution_kind"]
    merged["graph_histogram_scope"] = merged.get("graph_histogram_scope") if merged.get("graph_histogram_scope") in ("All Columns", "All Columns (Combined)", "Selected Column") else DEFAULTS["graph_histogram_scope"]

    for key in (
        "output_name", "threshold_output_name", "output_dir", "analysis_output_path", "threshold_output_path",
        "live_frame_limit", "graph_stdevs", "graph_fit_degree", "graph_view_mode", "graph_value_type", "graph_title", "graph_profile_value_mode", "graph_column_value_mode", "graph_distribution_kind", "graph_histogram_scope",
        "graph_distribution_column_px", "graph_distribution_bins", "graph_x_axis_label",
        "graph_y_axis_label", "graph_x_min", "graph_x_max", "graph_y_min", "graph_y_max",
    ):
        merged[key] = str(merged.get(key, DEFAULTS.get(key, ""))).strip()

    return merged


def load_app_defaults():
    settings_path = get_app_settings_path()
    if not os.path.isfile(settings_path):
        return copy.deepcopy(DEFAULTS)
    try:
        with open(settings_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        normalized = normalize_app_defaults(data)
        for key in ("output_dir", "analysis_output_path", "threshold_output_path"):
            normalized[key] = _resolve_app_path(normalized.get(key, ""))
        return normalized
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return copy.deepcopy(DEFAULTS)


def save_app_defaults(defaults_dict):
    settings_path = get_app_settings_path()
    normalized = normalize_app_defaults(defaults_dict)
    portable = copy.deepcopy(normalized)
    for key in ("output_dir", "analysis_output_path", "threshold_output_path"):
        portable[key] = _to_portable_app_path(portable.get(key, ""))
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(portable, handle, indent=2)

# ======================================================
# Main GUI
# ======================================================

class JetAnalysisGUI:

    CORNER_SIZE = 10
    APP_BG = "#eef3f9"
    PANEL_BG = "#f7f9fc"
    CARD_BG = "#ffffff"
    BORDER_COLOR = "#d5deea"
    TEXT_COLOR = "#10233d"
    MUTED_TEXT_COLOR = "#5f7086"
    ACCENT_COLOR = "#1f6feb"
    ACCENT_HOVER = "#1858bb"
    ACCENT_SOFT = "#dce9ff"
    SUCCESS_SOFT = "#e6f6ed"
    SUCCESS_TEXT = "#17643d"
    WARNING_SOFT = "#fff4d6"
    WARNING_TEXT = "#8a5a00"
    ERROR_SOFT = "#fde8ea"
    ERROR_TEXT = "#a11d2f"
    ENTRY_BG = "#f9fbff"
    ENTRY_BORDER = "#c8d5e6"
    ENTRY_ERROR_BG = "#fff1f2"
    ENTRY_ERROR_BORDER = "#d63950"
    FIELD_HELP = {
        "Threshold Offset": "Adjusts how strict thresholding is compared to the frame average. Higher values usually detect fewer pixels.",
        "Output File Name": "Base name used to auto-fill saved output file names and graph exports.",
        "Analysis Output": "Choose whether to save the analysis-overlay video, which format to use, and exactly where to store it.",
        "Threshold Output": "Choose whether to save the threshold video, which format to use, and exactly where to store it.",
        "Export Package": "Creates a timestamped folder with the current graph image, graph CSV, project JSON, any saved output videos that exist, and a quick summary text file.",
        "Preview Mode": "Choose what to display during processing: analysis overlay or threshold/binary output.",
        "Frame Range Selection": "Choose the start and end frame to process. Drag red handles; start and end previews update as you move.",
        "Crop Controls": "Adjust the crop region directly on the preview, then press Save Crop to apply it for processing.",
        "Analyze Every N Frames": "Sample the selected frame range by analyzing every Nth frame. Use 1 for high detail and larger values for faster preview runs.",
        "Minimum detected pixels per column": "Minimum number of detected pixels required in a column before that column is counted in the result.",
        "Standard Deviations": "Controls confidence band width around the detected centerline. Higher values create a wider band.",
        "Graph Standard Deviations": "Controls the plotted band width around the final mean centerline profile.",
        "Graph View": "Switch between the profile graph, a histogram heatmap across all columns, and a normal Q-Q plot.",
        "Profile Value Mode": "Choose whether the profile graph axes show calibrated values or graph-oriented pixel values.",
        "Column Input Mode": "Choose whether Selected Column input is interpreted as pixel position or calibrated horizontal position.",
        "Distribution Values": "Choose whether the distribution uses raw position, centered residuals, or z-scores.",
        "Histogram Scope": "For Histogram view, choose all-columns heatmap, a pooled all-columns histogram, or a single selected column histogram with a normal-curve overlay.",
        "Distribution Column": "Sampled column index used for single-column histogram and Q-Q views (0-based).",
        "Distribution Bins": "Number of bins used for the histogram view.",
        "Graph X Axis Label": "Custom label shown on the graph X axis.",
        "Graph Y Axis Label": "Custom label shown on the graph Y axis.",
        "Graph X Axis Bounds": "Optional X axis min/max in graph units. Leave blank for automatic bounds.",
        "Graph Y Axis Bounds": "Optional Y axis min/max in graph units. Leave blank for automatic bounds.",
        "Graph Fit Degree": "Polynomial degree used for best-fit equation (1=linear, 2=quadratic, etc.).",
        "Calibration Distance": "Real-world length that matches the line drawn on the preview.",
        "Calibration Units": "Measurement units used for calibration.",
        "Nozzle Origin": "Set a point where the jet exits the nozzle; calibrated graph values are measured from this point.",
    }

    def __init__(self, root):
        self.root = root
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.root.title("Jet Centerline Analyzer")
        self.root.geometry("1360x900")
        try:
            self.root.minsize(1280, 900)
        except Exception:
            pass
        self.configure_theme()

        self.app_defaults = load_app_defaults()
        self.settings_path = get_app_settings_path()

        self.video_path = tk.StringVar()
        self.video_source_var = tk.StringVar(value="Video File")
        self.saved_video_session = None
        self.camera_index_var = tk.StringVar(value="0")
        self.available_cameras = {}
        self.output_dir = tk.StringVar(value=self.app_defaults["output_dir"])
        self.save_analysis_output_var = tk.BooleanVar(value=self.app_defaults["save_analysis_output"])
        self.save_threshold_output_var = tk.BooleanVar(value=self.app_defaults["save_threshold_output"])
        self.analysis_output_format_var = tk.StringVar(value=self.app_defaults["analysis_output_format"])
        self.threshold_output_format_var = tk.StringVar(value=self.app_defaults["threshold_output_format"])
        self.threshold_output_name_var = tk.StringVar(value=self.app_defaults["threshold_output_name"])
        self.analysis_output_path_var = tk.StringVar(value=self.app_defaults["analysis_output_path"])
        self.threshold_output_path_var = tk.StringVar(value=self.app_defaults["threshold_output_path"])
        self.preview_mode = tk.StringVar(value=self.app_defaults["preview_mode"])
        self.show_preview_std_region_var = tk.BooleanVar(value=self.app_defaults["show_preview_std_region"])
        self.show_preview_frame_dots_var = tk.BooleanVar(value=self.app_defaults["show_preview_frame_dots"])
        self.show_preview_mean_line_var = tk.BooleanVar(value=self.app_defaults["show_preview_mean_line"])
        self.apply_preview_overlay_to_output_var = tk.BooleanVar(value=self.app_defaults["apply_preview_overlay_to_output"])
        self.threshold_offset_var = tk.IntVar(value=self.app_defaults["threshold_offset"])
        self.live_frame_limit = tk.StringVar(value=self.app_defaults["live_frame_limit"])

        self.use_multi_threshold_var = tk.BooleanVar(value=self.app_defaults["use_multi_threshold"])
        self.num_thresholds_var = tk.IntVar(value=self.app_defaults["num_thresholds"])
        self.multi_threshold_offsets = [
            tk.IntVar(value=self.app_defaults["multi_threshold_offsets"][0]),
            tk.IntVar(value=self.app_defaults["multi_threshold_offsets"][1]),
            tk.IntVar(value=self.app_defaults["multi_threshold_offsets"][2]),
            tk.IntVar(value=self.app_defaults["multi_threshold_offsets"][3]),
            tk.IntVar(value=self.app_defaults["multi_threshold_offsets"][4]),
        ]
        self.multi_threshold_weights = [
            tk.DoubleVar(value=self.app_defaults["multi_threshold_weights"][0]),
            tk.DoubleVar(value=self.app_defaults["multi_threshold_weights"][1]),
            tk.DoubleVar(value=self.app_defaults["multi_threshold_weights"][2]),
            tk.DoubleVar(value=self.app_defaults["multi_threshold_weights"][3]),
            tk.DoubleVar(value=self.app_defaults["multi_threshold_weights"][4]),
            tk.DoubleVar(value=self.app_defaults["multi_threshold_weights"][5]),
        ]
        self.multi_threshold_colors = list(self.app_defaults["multi_threshold_colors"])

        self.start_frame_var = tk.IntVar(value=0)
        self.end_frame_var = tk.IntVar(value=0)
        self.start_frame_text = tk.StringVar(value="0")
        self.end_frame_text = tk.StringVar(value="0")
        self.total_frames = 0
        self.total_frames_to_process = 0

        self.is_running = False
        self.live_preview_active = False  # Track if live preview is running (not analysis)
        self.stop_event = None
        self.current_analysis_config = None  # Store config reference for live threshold updates
        self.frame_counter = 0
        self.start_time = None
        self.analysis_error = None
        self.analysis_was_stopped = False

        self.preview_width = 900
        self.preview_height = 600
        self.left_panel_default_width = 470
        self.current_scale = 1
        self.x_offset = 0
        self.y_offset = 0
        self.display_w = 0
        self.display_h = 0
        self._resize_after_id = None
        self._pending_preview_size = None
        self._cached_display_frame_id = None
        self._cached_display_pil = None
        self.canvas_image_item = None
        self._resize_render_hold_until = 0.0
        self._deferred_display_frame = None
        self._resize_freeze_active = False

        self.crop_mode = False
        self.drag_start = None
        self.resize_corner = None
        self.crop_rect = None
        self.original_crop_frame = None

        self.crop_left = 0
        self.crop_top = 0
        self.crop_right = 0
        self.crop_bottom = 0

        self.last_analysis_frame = None
        self.last_raw_analysis_frame = None
        self.last_threshold_frame = None
        self.last_centerline_array = None
        self.last_running_avg = None
        self.last_running_std = None
        self.last_display_frame = None
        self.last_raw_frame = None  # Raw uncropped frame from live camera
        self.current_preview_frame_index = 0
        self.final_mean_profile = None
        self.final_std_profile = None
        self.final_centerline_samples = None
        self.imported_profile_data = None
        self.imported_distribution_data = None
        self.imported_table_path = ""
        self.imported_table_rows = None
        self.graph_stdevs_var = tk.StringVar(value=self.app_defaults["graph_stdevs"])
        self.graph_unit_label = "px"
        self.graph_unit_scale = 1.0
        self.graph_view_mode_var = tk.StringVar(value=self.app_defaults["graph_view_mode"])
        self.graph_value_type_var = tk.StringVar(value=self.app_defaults["graph_value_type"])
        self.graph_title_var = tk.StringVar(value=self.app_defaults["graph_title"])
        self.graph_profile_value_mode_var = tk.StringVar(value=self.app_defaults["graph_profile_value_mode"])
        self.graph_column_value_mode_var = tk.StringVar(value=self.app_defaults["graph_column_value_mode"])
        self.graph_distribution_kind_var = tk.StringVar(value=self.app_defaults["graph_distribution_kind"])
        self.graph_histogram_scope_var = tk.StringVar(value=self.app_defaults["graph_histogram_scope"])
        self.graph_distribution_column_px_var = tk.StringVar(value=self.app_defaults["graph_distribution_column_px"])
        self.graph_distribution_column_bounds_var = tk.StringVar(value="Input range: run analysis to populate bounds.")
        self.graph_distribution_bins_var = tk.StringVar(value=self.app_defaults["graph_distribution_bins"])
        self.graph_x_axis_label = tk.StringVar(value=self.app_defaults["graph_x_axis_label"])
        self.graph_y_axis_label = tk.StringVar(value=self.app_defaults["graph_y_axis_label"])
        self.graph_x_min_var = tk.StringVar(value=self.app_defaults["graph_x_min"])
        self.graph_x_max_var = tk.StringVar(value=self.app_defaults["graph_x_max"])
        self.graph_y_min_var = tk.StringVar(value=self.app_defaults["graph_y_min"])
        self.graph_y_max_var = tk.StringVar(value=self.app_defaults["graph_y_max"])
        self.graph_fit_degree_var = tk.StringVar(value=self.app_defaults["graph_fit_degree"])
        self.show_best_fit_var = tk.BooleanVar(value=self.app_defaults["show_best_fit"])
        self.graph_fit_equation_var = tk.StringVar(value="Best fit: n/a")
        self.calibration_distance_var = tk.StringVar(value="")
        self.calibration_units_var = tk.StringVar(value=self.app_defaults["calibration_units"])
        self.calibration_status_var = tk.StringVar(value="Calibration: not set")
        self.calibration_mode = False
        self.calibration_line_img = None
        self.calibration_drag_point = None
        self.calibration_zoom = 1.0
        self.calibration_pan_x = 0.0
        self.calibration_pan_y = 0.0
        self.calibration_pan_active = False
        self.calibration_pan_start = None
        self.nozzle_origin_img = None
        self.nozzle_pick_mode = False
        self.nozzle_status_var = tk.StringVar(value="Nozzle origin: not set")
        self.validation_message = tk.StringVar(value="")
        self.crop_size_text = tk.StringVar(value="Crop: full frame")
        self._range_sync_lock = False
        self.doc_window = None
        self.doc_text_widget = None
        self.doc_path = os.path.join(_get_resource_dir(), DEFAULT_DOC_FILENAME)
        _icon_path = os.path.join(_get_resource_dir(), "icon.ico")
        if os.path.isfile(_icon_path):
            try:
                self.root.iconbitmap(_icon_path)
            except Exception:
                pass
        self.project_path = ""
        self._tooltips = []
        self.status_var = tk.StringVar(value="Needs Input")
        self.settings_status_var = tk.StringVar(value="Startup defaults ready.")
        self.display_controller = DisplayController(self)
        self.documentation_controller = DocumentationController(self)
        self.graph_controller = GraphController(self)
        self.project_state_controller = ProjectStateController(self, STARTUP_PROJECT_FILENAMES)
        self.range_controller = RangeController(self)
        self.status_controller = StatusController(self)
        self.live_engine = None

        self.build_layout()
        self.detect_available_cameras()
        self.reset_defaults()
        self.bind_validation_hooks()
        self.bind_keyboard_shortcuts()
        self.set_range_controls_enabled(True)
        self.refresh_run_state()
        base_dir = os.path.dirname(__file__)
        default_video_candidates = [
            os.path.join(base_dir, "..", "Example Videos", "example_input.mp4"),
            os.path.join(base_dir, "Example Videos", "example_input.mp4"),
            os.path.join(os.getcwd(), "Example Videos", "example_input.mp4"),
            os.path.join(base_dir, "..", "Input Videos", "example_input.mp4"),
            os.path.join(base_dir, "Input Videos", "example_input.mp4"),
            os.path.join(os.getcwd(), "Input Videos", "example_input.mp4"),
            os.path.join(os.getcwd(), "example_input.mp4"),
        ]
        for default_video in default_video_candidates:
            default_video = os.path.normpath(default_video)
            if os.path.isfile(default_video):
                self.load_video(default_video)
                break
        self.try_auto_load_startup_project()

    def configure_theme(self):
        self.root.configure(fg_color=self.APP_BG)
        self.ttk_style = ttk.Style(self.root)
        try:
            self.ttk_style.theme_use("clam")
        except tk.TclError:
            pass
        self.ttk_style.configure("Modern.TNotebook", background=self.PANEL_BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        self.ttk_style.configure(
            "Modern.TNotebook.Tab",
            background=self.CARD_BG,
            foreground=self.MUTED_TEXT_COLOR,
            borderwidth=0,
            padding=(5, 4),
            font=("Segoe UI Semibold", 8),
        )
        self.ttk_style.map(
            "Modern.TNotebook.Tab",
            background=[("selected", self.ACCENT_SOFT)],
            foreground=[("selected", self.TEXT_COLOR)],
        )
        self.ttk_style.configure(
            "Modern.TCombobox",
            fieldbackground=self.CARD_BG,
            background=self.CARD_BG,
            foreground=self.TEXT_COLOR,
            arrowcolor=self.MUTED_TEXT_COLOR,
            bordercolor=self.ENTRY_BORDER,
            lightcolor=self.CARD_BG,
            darkcolor=self.CARD_BG,
            padding=6,
        )
        self.ttk_style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", self.CARD_BG)],
            selectbackground=[("readonly", self.ACCENT_SOFT)],
            selectforeground=[("readonly", self.TEXT_COLOR)],
        )
        self.ttk_style.configure(
            "Modern.TMenubutton",
            background=self.CARD_BG,
            foreground=self.TEXT_COLOR,
            arrowcolor=self.MUTED_TEXT_COLOR,
            bordercolor=self.ENTRY_BORDER,
            lightcolor=self.CARD_BG,
            darkcolor=self.CARD_BG,
            padding=6,
        )
        self.ttk_style.map(
            "Modern.TMenubutton",
            background=[("active", self.CARD_BG), ("disabled", self.CARD_BG)],
            foreground=[("disabled", "gray55")],
            arrowcolor=[("disabled", "gray65")],
        )
        self.ttk_style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor="#dfe7f1",
            bordercolor="#dfe7f1",
            background=self.ACCENT_COLOR,
            lightcolor=self.ACCENT_COLOR,
            darkcolor=self.ACCENT_COLOR,
        )

    def create_card(self, parent, padx=0, pady=0):
        card = ctk.CTkFrame(
            parent,
            fg_color=self.CARD_BG,
            corner_radius=16,
            border_width=1,
            border_color=self.BORDER_COLOR,
        )
        card.pack(fill="x", padx=padx, pady=pady)
        return card

    def create_section_card(self, parent, title, padx=0, pady=0, compact=False):
        card = self.create_card(parent, padx=padx, pady=pady)
        header = ctk.CTkLabel(
            card,
            text=title,
            font=("Segoe UI Semibold", 12 if compact else 13),
            text_color=self.TEXT_COLOR,
        )
        header.pack(anchor="w", padx=10 if compact else 12, pady=(7, 4) if compact else (10, 6))
        return card

    def create_button(self, parent, text, command, width=None, tone="secondary", compact=False):
        colors = {
            "primary": (self.ACCENT_COLOR, self.ACCENT_HOVER, "#ffffff"),
            "secondary": ("#edf2f8", "#e2eaf4", self.TEXT_COLOR),
            "danger": ("#fbe3e6", "#f6d3d9", self.ERROR_TEXT),
        }
        fg_color, hover_color, text_color = colors[tone]
        kwargs = {
            "text": text,
            "command": command,
            "height": 26 if compact else 30,
            "corner_radius": 8 if compact else 9,
            "fg_color": fg_color,
            "hover_color": hover_color,
            "text_color": text_color,
            "font": ("Segoe UI Semibold", 10 if compact else 10),
        }
        if width is not None:
            kwargs["width"] = width
        return ctk.CTkButton(
            parent,
            **kwargs,
        )

    def create_entry(self, parent, textvariable=None, width=None, compact=False):
        entry = ctk.CTkEntry(
            parent,
            textvariable=textvariable,
            height=28 if compact else 34,
            corner_radius=8 if compact else 10,
            fg_color=self.ENTRY_BG,
            border_color=self.ENTRY_BORDER,
            text_color=self.TEXT_COLOR,
            font=("Segoe UI", 11 if compact else 12),
        )
        if width is not None:
            entry.configure(width=width)
        return entry

    def set_entry_validation_state(self, entry, is_error):
        if isinstance(entry, ctk.CTkEntry):
            entry.configure(
                fg_color=self.ENTRY_ERROR_BG if is_error else self.ENTRY_BG,
                border_color=self.ENTRY_ERROR_BORDER if is_error else self.ENTRY_BORDER,
            )
        else:
            entry.configure(bg="misty rose" if is_error else "white")

    # ======================================================
    # Layout
    # ======================================================

    def build_layout(self):

        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.pack(fill="both", expand=True)

        self.left_panel = ctk.CTkFrame(
            main,
            fg_color=self.PANEL_BG,
            corner_radius=18,
            border_width=1,
            border_color=self.BORDER_COLOR,
        )
        self.left_panel.configure(width=self.left_panel_default_width)
        self.left_panel.pack_propagate(False)
        self.left_panel.pack(side="left", fill="y", padx=8, pady=8)

        # ================= CONTROL BAR (TOP) =================
        control_bar = ctk.CTkFrame(self.left_panel, fg_color=self.CARD_BG, corner_radius=14, border_width=1, border_color=self.BORDER_COLOR)
        control_bar.pack(fill="x", padx=0, pady=(0, 6))

        run_stop_row = ctk.CTkFrame(control_bar, fg_color="transparent")
        run_stop_row.pack(side="left", padx=4, pady=4)

        self.run_button = self.create_button(
            run_stop_row, text="Run Analysis", command=self.start_thread, width=104, tone="primary")
        self.run_button.pack(side="left", padx=(0, 4))

        self.stop_button = self.create_button(
            run_stop_row, text="Stop",
            command=self.stop_analysis,
            width=84,
            tone="danger",
        )
        self.stop_button.configure(state="disabled")
        self.stop_button.pack(side="left")
        
        self.status_badge = ctk.CTkLabel(
            run_stop_row,
            textvariable=self.status_var,
            fg_color="#edf2f8",
            text_color=self.TEXT_COLOR,
            corner_radius=999,
            padx=8,
            pady=4,
            font=("Segoe UI Semibold", 10),
        )
        self.status_badge.pack(side="left", padx=(6, 4))

        self.progress = ttk.Progressbar(
            run_stop_row, length=95, mode="determinate", style="Modern.Horizontal.TProgressbar")
        self.progress.pack(side="left")

        # Progress and stats on the right
        stats_row = ctk.CTkFrame(control_bar, fg_color="transparent")
        stats_row.pack(side="right", padx=4, pady=4)

        self.time_label = ctk.CTkLabel(
            stats_row,
            text="0.00s | 0/0",
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            text_color=self.MUTED_TEXT_COLOR,
        )
        self.time_label.pack(side="left")

        self.preview_frame = tk.Frame(main, bg="black")
        self.preview_frame.pack(side="right", expand=True, fill="both")

        self.canvas = tk.Canvas(self.preview_frame, bg="black")
        self.canvas.pack(expand=True, fill="both")
        self.preview_frame.bind("<Configure>", self.on_resize)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<ButtonPress-3>", self.on_right_mouse_down)
        self.canvas.bind("<B3-Motion>", self.on_right_mouse_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_mouse_up)
        self.canvas.bind("<MouseWheel>", self.on_calibration_mouse_wheel)

        self.notebook = ttk.Notebook(self.left_panel, style="Modern.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        basic_tab = tk.Frame(self.notebook, bg=self.PANEL_BG)
        self.threshold_tab = tk.Frame(self.notebook, bg=self.PANEL_BG)
        advanced_tab = tk.Frame(self.notebook, bg=self.PANEL_BG)
        self.crop_tab = tk.Frame(self.notebook, bg=self.PANEL_BG)
        self.calibration_tab = tk.Frame(self.notebook, bg=self.PANEL_BG)
        self.graph_tab = tk.Frame(self.notebook, bg="white")
        self.settings_tab = tk.Frame(self.notebook, bg=self.PANEL_BG)

        self.notebook.add(basic_tab, text="Basic")
        self.notebook.add(self.threshold_tab, text="Threshold")
        self.notebook.add(advanced_tab, text="Advanced")
        self.notebook.add(self.crop_tab, text="Crop")
        self.notebook.add(self.calibration_tab, text="Calibration")
        self.notebook.add(self.graph_tab, text="Graphs")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.bind("<<NotebookTabChanged>>", self.on_notebook_tab_changed)

        # ================= BASIC TAB =================

        source_frame = self.create_card(basic_tab, padx=6, pady=(8, 6))

        self.video_source_label = ctk.CTkLabel(source_frame, text="Video Source:", text_color=self.TEXT_COLOR)
        self.video_source_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.video_source_menu = ttk.Combobox(
            source_frame,
            textvariable=self.video_source_var,
            values=["Video File", "Live Camera"],
            state="readonly",
            style="Modern.TCombobox",
        )
        self.video_source_menu.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.video_source_menu.bind("<<ComboboxSelected>>", self.on_video_source_change)

        # Camera selection (only shown for live camera)
        self.camera_label = ctk.CTkLabel(source_frame, text="Camera:", text_color=self.TEXT_COLOR)
        self.camera_combo = ttk.Combobox(
            source_frame,
            textvariable=self.camera_index_var,
            values=[],
            state="readonly",
            width=20,
            style="Modern.TCombobox",
        )
        self.camera_combo.bind("<<ComboboxSelected>>", self.on_camera_selected)
        # Initially hide camera controls
        self.camera_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.camera_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.camera_label.grid_remove()
        self.camera_combo.grid_remove()

        self.select_video_button = self.create_button(
            basic_tab, text="Select Video", command=self.select_video, tone="primary")
        self.select_video_button.pack(pady=5)

        self.video_label = ctk.CTkLabel(
            basic_tab, text="No video selected", wraplength=250, text_color=self.MUTED_TEXT_COLOR)
        self.video_label.pack()

        analysis_output_frame = self.create_section_card(basic_tab, "Analysis Output", padx=6, pady=(0, 4), compact=True)
        self.attach_tooltip(analysis_output_frame, "Analysis Output")
        self.analysis_output_check = ctk.CTkCheckBox(
            analysis_output_frame,
            text="Save analysis video",
            variable=self.save_analysis_output_var,
            command=self.on_output_toggle_changed,
            text_color=self.TEXT_COLOR,
            checkbox_width=16,
            checkbox_height=16,
            font=("Segoe UI", 11),
        )
        self.analysis_output_check.pack(anchor="w", padx=10, pady=(2, 1))
        ctk.CTkLabel(analysis_output_frame, text="File name:", text_color=self.TEXT_COLOR, font=("Segoe UI", 11)).pack(anchor="w", padx=10)
        self.output_name_entry = self.create_entry(analysis_output_frame, compact=True)
        self.output_name_entry.insert(0, self.app_defaults.get("output_name", DEFAULTS["output_name"]))
        self.output_name_entry.pack(fill="x", padx=10, pady=(0, 3))
        self.attach_tooltip(self.output_name_entry, "Output File Name")
        analysis_format_row = ctk.CTkFrame(analysis_output_frame, fg_color="transparent")
        analysis_format_row.pack(fill="x", padx=10, pady=(0, 3))
        ctk.CTkLabel(analysis_format_row, text="Format:", text_color=self.TEXT_COLOR, font=("Segoe UI", 11)).pack(side="left")
        self.analysis_output_format_combo = ttk.Combobox(
            analysis_format_row,
            textvariable=self.analysis_output_format_var,
            values=list(OUTPUT_FORMATS.keys()),
            state="readonly",
            width=11,
            style="Modern.TCombobox",
        )
        self.analysis_output_format_combo.pack(side="left", padx=(6, 0))
        self.analysis_output_format_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_output_format_changed("analysis"))
        analysis_path_row = ctk.CTkFrame(analysis_output_frame, fg_color="transparent")
        analysis_path_row.pack(fill="x", padx=10, pady=(0, 5))
        self.analysis_output_entry = self.create_entry(analysis_path_row, textvariable=self.analysis_output_path_var, compact=True)
        self.analysis_output_entry.pack(side="left", fill="x", expand=True)
        self.analysis_output_browse_button = self.create_button(
            analysis_path_row,
            text="Browse",
            command=lambda: self.select_output_file("analysis"),
            compact=True,
        )
        self.analysis_output_browse_button.pack(side="left", padx=(6, 0))

        threshold_output_frame = self.create_section_card(basic_tab, "Threshold Output", padx=6, pady=(0, 4), compact=True)
        self.attach_tooltip(threshold_output_frame, "Threshold Output")
        self.threshold_output_check = ctk.CTkCheckBox(
            threshold_output_frame,
            text="Save threshold video",
            variable=self.save_threshold_output_var,
            command=self.on_output_toggle_changed,
            text_color=self.TEXT_COLOR,
            checkbox_width=16,
            checkbox_height=16,
            font=("Segoe UI", 11),
        )
        self.threshold_output_check.pack(anchor="w", padx=10, pady=(2, 1))
        ctk.CTkLabel(threshold_output_frame, text="File name:", text_color=self.TEXT_COLOR, font=("Segoe UI", 11)).pack(anchor="w", padx=10)
        self.threshold_output_name_entry = self.create_entry(
            threshold_output_frame,
            textvariable=self.threshold_output_name_var,
            compact=True,
        )
        self.threshold_output_name_entry.pack(fill="x", padx=10, pady=(0, 3))
        threshold_format_row = ctk.CTkFrame(threshold_output_frame, fg_color="transparent")
        threshold_format_row.pack(fill="x", padx=10, pady=(0, 3))
        ctk.CTkLabel(threshold_format_row, text="Format:", text_color=self.TEXT_COLOR, font=("Segoe UI", 11)).pack(side="left")
        self.threshold_output_format_combo = ttk.Combobox(
            threshold_format_row,
            textvariable=self.threshold_output_format_var,
            values=list(OUTPUT_FORMATS.keys()),
            state="readonly",
            width=11,
            style="Modern.TCombobox",
        )
        self.threshold_output_format_combo.pack(side="left", padx=(6, 0))
        self.threshold_output_format_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_output_format_changed("threshold"))
        threshold_path_row = ctk.CTkFrame(threshold_output_frame, fg_color="transparent")
        threshold_path_row.pack(fill="x", padx=10, pady=(0, 5))
        self.threshold_output_entry = self.create_entry(threshold_path_row, textvariable=self.threshold_output_path_var, compact=True)
        self.threshold_output_entry.pack(side="left", fill="x", expand=True)
        self.threshold_output_browse_button = self.create_button(
            threshold_path_row,
            text="Browse",
            command=lambda: self.select_output_file("threshold"),
            compact=True,
        )
        self.threshold_output_browse_button.pack(side="left", padx=(6, 0))



        # Live video frame limit control (shown only for live camera mode)
        self.live_limit_row = ctk.CTkFrame(basic_tab, fg_color="transparent")
        self.live_limit_header = ctk.CTkLabel(self.live_limit_row, text="Frames to run:", text_color=self.TEXT_COLOR)
        self.live_limit_entry = self.create_entry(self.live_limit_row, textvariable=self.live_frame_limit, width=90)
        self.live_limit_header.pack(side="left")
        self.live_limit_entry.pack(side="left", padx=(6, 0))
        # Initially hidden - will be shown when Live Camera is selected
        self.validation_label = ctk.CTkLabel(
            basic_tab,
            textvariable=self.validation_message,
            text_color=self.ERROR_TEXT,
            wraplength=260,
            justify="left"
        )
        self.validation_label.pack(pady=(6, 2), anchor="w")

        project_actions_grid = ctk.CTkFrame(basic_tab, fg_color="transparent")
        project_actions_grid.pack(pady=(2, 4))
        self.create_button(
            project_actions_grid,
            text="Save Project",
            command=self.save_project,
            width=170,
        ).grid(row=0, column=0, padx=6, pady=4)
        self.create_button(
            project_actions_grid,
            text="Load Project",
            command=self.load_project,
            width=170,
        ).grid(row=0, column=1, padx=6, pady=4)
        self.export_package_button = self.create_button(
            project_actions_grid,
            text="Export Package",
            command=self.export_package,
            width=170,
        )
        self.export_package_button.grid(row=1, column=1, padx=6, pady=4)
        self.attach_tooltip(self.export_package_button, "Export Package")
        self.create_button(
            project_actions_grid,
            text="Open Documentation Page",
            command=self.open_documentation_page,
            width=170,
        ).grid(row=1, column=0, padx=6, pady=4)
        self.create_button(
            basic_tab,
            text="Reset Basic Tab",
            command=self.reset_basic_tab,
            width=170,
        ).pack(pady=(2, 6))

        # ================= ADVANCED TAB =================

        self.labeled_header(advanced_tab, "Frame Range Selection", pady=(10, 5))
        self.use_full_range_button = self.create_button(
            advanced_tab,
            text="Use full video",
            command=self.use_full_video
        )
        self.use_full_range_button.pack(anchor="w", padx=8)

        self.range_slider = RangeSlider(advanced_tab, 0, 0,
                                        command=self.on_range_change)
        self.range_slider.pack(pady=10)

        self.range_label = ctk.CTkLabel(advanced_tab, text="Start: 0   End: 0", text_color=self.TEXT_COLOR)
        self.range_label.pack()
        range_entry_row = ctk.CTkFrame(advanced_tab, fg_color="transparent")
        range_entry_row.pack(pady=(4, 0))
        ctk.CTkLabel(range_entry_row, text="Start", text_color=self.TEXT_COLOR).grid(row=0, column=0, padx=(0, 4))
        self.start_entry = self.create_entry(range_entry_row, width=72, textvariable=self.start_frame_text)
        self.start_entry.grid(row=0, column=1, padx=(0, 8))
        ctk.CTkLabel(range_entry_row, text="End", text_color=self.TEXT_COLOR).grid(row=0, column=2, padx=(0, 4))
        self.end_entry = self.create_entry(range_entry_row, width=72, textvariable=self.end_frame_text)
        self.end_entry.grid(row=0, column=3)

        jump_row = ctk.CTkFrame(advanced_tab, fg_color="transparent")
        jump_row.pack(pady=(6, 0))
        self.jump_start_button = self.create_button(
            jump_row, text="Jump to Start", command=self.jump_to_start_frame)
        self.jump_start_button.grid(row=0, column=0, padx=(0, 8))
        self.jump_end_button = self.create_button(
            jump_row, text="Jump to End", command=self.jump_to_end_frame)
        self.jump_end_button.grid(row=0, column=1)

        analyze_every_row = ctk.CTkFrame(advanced_tab, fg_color="transparent")
        analyze_every_row.pack(pady=(10, 0), anchor="w", padx=8)
        analyze_every_label = ctk.CTkLabel(analyze_every_row, text="Analyze every", text_color=self.TEXT_COLOR)
        analyze_every_label.pack(side="left")
        self.analyze_every_entry = self.create_entry(analyze_every_row, width=72)
        self.analyze_every_entry.insert(0, self.app_defaults.get("frame_stride", DEFAULTS["frame_stride"]))
        self.analyze_every_entry.pack(side="left", padx=(6, 6))
        ctk.CTkLabel(analyze_every_row, text="frames", text_color=self.TEXT_COLOR).pack(side="left")
        self.attach_tooltip(analyze_every_label, "Analyze Every N Frames")
        self.attach_tooltip(self.analyze_every_entry, "Analyze Every N Frames")

        self.pixel_entry = self.labeled_entry(
            advanced_tab, "Minimum detected pixels per column", "pixels_per_col")

        self.create_button(advanced_tab, text="Reset Advanced Tab", command=self.reset_advanced_tab).pack(pady=10)

        # ================= THRESHOLD TAB =================

        self.labeled_header(self.threshold_tab, "Preview Mode", pady=(10, 5))
        ctk.CTkRadioButton(
            self.threshold_tab,
            text="Threshold Preview",
            variable=self.preview_mode,
            value="threshold",
            command=self.on_preview_mode_changed,
            text_color=self.TEXT_COLOR,
        ).pack(anchor="w", padx=8)

        ctk.CTkRadioButton(
            self.threshold_tab,
            text="Analysis Preview",
            variable=self.preview_mode,
            value="analysis",
            command=self.on_preview_mode_changed,
            text_color=self.TEXT_COLOR,
        ).pack(anchor="w", padx=8)

        self.apply_preview_overlay_to_output_checkbox = ctk.CTkCheckBox(
            self.threshold_tab,
            text="Apply the following settings to saved output video:",
            variable=self.apply_preview_overlay_to_output_var,
            command=self.on_analysis_overlay_toggle,
            text_color=self.TEXT_COLOR,
        )
        self.apply_preview_overlay_to_output_checkbox.pack(anchor="w", padx=26, pady=(2, 0))

        self.show_preview_frame_dots_checkbox = ctk.CTkCheckBox(
            self.threshold_tab,
            text="Show per-frame average",
            variable=self.show_preview_frame_dots_var,
            command=self.on_analysis_overlay_toggle,
            text_color=self.TEXT_COLOR,
        )
        self.show_preview_frame_dots_checkbox.pack(anchor="w", padx=44, pady=(2, 0))

        self.show_preview_mean_line_checkbox = ctk.CTkCheckBox(
            self.threshold_tab,
            text="Show average over time",
            variable=self.show_preview_mean_line_var,
            command=self.on_analysis_overlay_toggle,
            text_color=self.TEXT_COLOR,
        )
        self.show_preview_mean_line_checkbox.pack(anchor="w", padx=44, pady=(2, 0))

        std_region_row = ctk.CTkFrame(self.threshold_tab, fg_color="transparent")
        std_region_row.pack(anchor="w", padx=44, pady=(2, 0))

        self.show_preview_std_region_checkbox = ctk.CTkCheckBox(
            std_region_row,
            text="Show standard deviation region",
            variable=self.show_preview_std_region_var,
            command=self.on_analysis_overlay_toggle,
            text_color=self.TEXT_COLOR,
        )
        self.show_preview_std_region_checkbox.pack(side="left")
        self.attach_tooltip(self.show_preview_std_region_checkbox, "Standard Deviations")

        self.stdev_entry = self.create_entry(std_region_row, width=56)
        self.stdev_entry.insert(0, self.app_defaults.get("stdevs", DEFAULTS["stdevs"]))
        self.stdev_entry.pack(side="left", padx=(8, 0))
        self.attach_tooltip(self.stdev_entry, "Standard Deviations")

        # Create dummy labels for backward compatibility (no longer displayed)
        self.actual_threshold_label = ctk.CTkLabel(self.threshold_tab, text="")
        self.threshold_value_label = ctk.CTkLabel(self.threshold_tab, text="")
        self.threshold_scale = None

        self.labeled_header(self.threshold_tab, "Threshold Mode", pady=(15, 5))
        
        self.use_multi_threshold_checkbox = ctk.CTkCheckBox(
            self.threshold_tab,
            text="Use Multi-Threshold",
            variable=self.use_multi_threshold_var,
            command=self.on_threshold_mode_toggle,
            text_color=self.TEXT_COLOR,
        )
        self.use_multi_threshold_checkbox.pack(anchor="w", padx=8)

        num_thresholds_frame = ctk.CTkFrame(self.threshold_tab, fg_color="transparent")
        num_thresholds_frame.pack(anchor="w", padx=8, pady=(10, 0))
        ctk.CTkLabel(num_thresholds_frame, text="Number of Thresholds:", text_color=self.TEXT_COLOR).pack(side="left")
        self.num_thresholds_combo = ttk.Combobox(
            num_thresholds_frame,
            textvariable=self.num_thresholds_var,
            values=["1", "2", "3", "4", "5"],
            state="readonly",
            width=5,
            style="Modern.TCombobox",
        )
        self.num_thresholds_combo.pack(side="left", padx=(6, 0))
        self.num_thresholds_combo.bind("<<ComboboxSelected>>", self.on_num_thresholds_changed)

        self.multi_threshold_frame = ctk.CTkFrame(
            self.threshold_tab,
            fg_color=self.CARD_BG,
            corner_radius=16,
            border_width=1,
            border_color=self.BORDER_COLOR,
        )
        self.multi_threshold_frame.pack(fill="both", expand=True, padx=8, pady=(10, 0))

        self.multi_threshold_rows = []
        self.multi_threshold_value_labels = []
        self.multi_threshold_sliders = []

        sliders_row = ctk.CTkFrame(self.multi_threshold_frame, fg_color="transparent")
        sliders_row.pack(fill="x", pady=(4, 0))
        for idx in range(5):
            sliders_row.columnconfigure(idx, weight=1)

        for idx in range(5):
            col_frame = ctk.CTkFrame(sliders_row, fg_color="transparent")
            col_frame.grid(row=0, column=idx, sticky="n", padx=4)

            label_color = self.multi_threshold_colors[idx + 1]
            ctk.CTkLabel(
                col_frame,
                text=f"T{idx + 1}",
                text_color=label_color,
                font=("Segoe UI Semibold", 12),
            ).grid(row=0, column=0)

            scale = tk.Scale(
                col_frame,
                from_=100,
                to=-50,
                orient="vertical",
                variable=self.multi_threshold_offsets[idx],
                command=lambda value, i=idx: self.on_multi_threshold_changed(i, value),
                length=120,
                width=14,
                sliderlength=16,
                showvalue=False
            )
            scale.grid(row=1, column=0)

            value_label = ctk.CTkLabel(col_frame, text=str(self.multi_threshold_offsets[idx].get()), font=("Segoe UI", 11), text_color=self.TEXT_COLOR)
            value_label.grid(row=2, column=0)

            # Arrow buttons row
            arrow_row = ctk.CTkFrame(col_frame, fg_color="transparent")
            arrow_row.grid(row=3, column=0)
            self.create_button(
                arrow_row, text="\u25B2", width=36,
                command=lambda i=idx: self._nudge_threshold(i, 1)
            ).pack(side="left", padx=1)
            self.create_button(
                arrow_row, text="\u25BC", width=36,
                command=lambda i=idx: self._nudge_threshold(i, -1)
            ).pack(side="left", padx=1)

            self.multi_threshold_rows.append(col_frame)
            self.multi_threshold_value_labels.append(value_label)
            self.multi_threshold_sliders.append(scale)
        
        weights_header = ctk.CTkLabel(self.multi_threshold_frame, text="Region Weights (0-10)", font=("Segoe UI Semibold", 12), text_color=self.TEXT_COLOR)
        weights_header.pack(pady=(10, 6))
        
        weights_row = ctk.CTkFrame(self.multi_threshold_frame, fg_color="transparent")
        weights_row.pack(fill="x", pady=(0, 6))
        
        self.multi_region_rows = []
        self.multi_region_weight_entries = []
        self.multi_region_color_buttons = []
        
        for idx in range(6):
            region_frame = ctk.CTkFrame(weights_row, fg_color="transparent")
            region_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
            self.multi_region_rows.append(region_frame)
            
            color = self.multi_threshold_colors[idx]
            
            # Color-coded label
            label = tk.Label(
                region_frame,
                text=f"R{idx + 1}",
                bg=color,
                fg="white",
                font=("TkDefaultFont", 9, "bold"),
                width=3,
                pady=2,
                cursor="hand2"
            )
            label.pack()
            label.bind("<Button-1>", lambda _e, i=idx: self.pick_multi_threshold_color(i))
            
            # Weight entry
            entry = self.create_entry(region_frame, textvariable=self.multi_threshold_weights[idx], width=56)
            entry.pack()
            entry.bind("<Return>", lambda _e, i=idx: self.on_multi_threshold_weights_changed(i))
            entry.bind("<FocusOut>", lambda _e, i=idx: self.on_multi_threshold_weights_changed(i))
            
            self.multi_region_weight_entries.append(entry)
            self.multi_region_color_buttons.append(label)

        self.create_button(
            self.threshold_tab,
            text="Reset Threshold Tab",
            command=self.reset_threshold_tab
        ).pack(anchor="w", padx=8, pady=(10, 8))

        # ================= CROP TAB =================

        self.labeled_header(self.crop_tab, "Crop Controls", pady=(10, 5))

        self.save_crop_button = self.create_button(
            self.crop_tab,
            text="Save Crop",
            command=self.save_crop,
        )
        self.save_crop_button.configure(state="disabled")
        self.save_crop_button.pack(pady=5)
        self.reset_crop_button = self.create_button(
            self.crop_tab,
            text="Reset Crop Tab",
            command=self.reset_crop_tab
        )
        self.reset_crop_button.pack(pady=5)

        self.crop_size_label = ctk.CTkLabel(
            self.crop_tab, textvariable=self.crop_size_text, text_color=self.MUTED_TEXT_COLOR)
        self.crop_size_label.pack(pady=(2, 0))

        # ================= CALIBRATION TAB =================
        self.labeled_header(self.calibration_tab, "Calibration Distance", pady=(10, 5))
        self.calibration_distance_entry = self.create_entry(
            self.calibration_tab, textvariable=self.calibration_distance_var, width=110
        )
        self.calibration_distance_entry.pack(anchor="w", padx=8)
        self.attach_tooltip(self.calibration_distance_entry, "Calibration Distance")

        self.labeled_header(self.calibration_tab, "Calibration Units", pady=(10, 5))
        self.calibration_units_combo = ttk.Combobox(
            self.calibration_tab,
            textvariable=self.calibration_units_var,
            values=["mm", "cm", "in"],
            width=8,
            state="readonly",
            style="Modern.TCombobox",
        )
        self.calibration_units_combo.pack(anchor="w", padx=8)
        self.attach_tooltip(self.calibration_units_combo, "Calibration Units")

        # Top row: Set Calibration Line and Set Nozzle Origin
        top_button_row = ctk.CTkFrame(self.calibration_tab, fg_color="transparent")
        top_button_row.pack(anchor="w", padx=8, pady=(10, 0))
        self.calibration_set_line_button = self.create_button(
            top_button_row,
            text="Set Calibration Line",
            command=self.start_calibration_line_mode
        )
        self.calibration_set_line_button.pack(side="left", padx=(0, 6))
        self.calibration_set_nozzle_button = self.create_button(
            top_button_row,
            text="Set Nozzle Origin",
            command=self.start_nozzle_pick_mode
        )
        self.calibration_set_nozzle_button.pack(side="left")
        self.attach_tooltip(self.calibration_set_nozzle_button, "Nozzle Origin")
        
        # Bottom row: Apply Calibration and Clear Calibration
        bottom_button_row = ctk.CTkFrame(self.calibration_tab, fg_color="transparent")
        bottom_button_row.pack(anchor="w", padx=8, pady=(6, 0))
        self.calibration_apply_button = self.create_button(
            bottom_button_row,
            text="Apply Calibration",
            command=self.apply_calibration
        )
        self.calibration_apply_button.pack(side="left", padx=(0, 6))
        self.calibration_clear_button = self.create_button(
            bottom_button_row,
            text="Clear Calibration",
            command=self.clear_calibration
        )
        self.calibration_clear_button.pack(side="left")
        ctk.CTkLabel(
            self.calibration_tab,
            text="Draw or drag the two endpoints on the preview.\nThen enter the real distance and units.",
            text_color=self.MUTED_TEXT_COLOR,
            justify="left"
        ).pack(anchor="w", padx=8, pady=(10, 0))
        self.calibration_status_label = ctk.CTkLabel(
            self.calibration_tab,
            textvariable=self.calibration_status_var,
            text_color=self.TEXT_COLOR,
            justify="left",
            wraplength=260
        )
        self.calibration_status_label.pack(anchor="w", padx=8, pady=(8, 0))
        self.nozzle_status_label = ctk.CTkLabel(
            self.calibration_tab,
            textvariable=self.nozzle_status_var,
            text_color=self.TEXT_COLOR,
            justify="left",
            wraplength=260
        )
        self.nozzle_status_label.pack(anchor="w", padx=8, pady=(4, 0))

        self.labeled_header(self.calibration_tab, "Calibration Zoom", pady=(10, 5))
        zoom_row = ctk.CTkFrame(self.calibration_tab, fg_color="transparent")
        zoom_row.pack(anchor="w", padx=8)
        self.calibration_zoom_out_button = self.create_button(
            zoom_row,
            text="-",
            width=36,
            command=lambda: self.set_calibration_zoom(self.calibration_zoom / 1.25)
        )
        self.calibration_zoom_out_button.pack(side="left")
        self.calibration_zoom_in_button = self.create_button(
            zoom_row,
            text="+",
            width=36,
            command=lambda: self.set_calibration_zoom(self.calibration_zoom * 1.25)
        )
        self.calibration_zoom_in_button.pack(side="left", padx=(6, 0))
        self.calibration_zoom_reset_button = self.create_button(
            zoom_row,
            text="Reset",
            command=lambda: self.set_calibration_zoom(1.0)
        )
        self.calibration_zoom_reset_button.pack(side="left", padx=(8, 0))

        self.create_button(
            self.calibration_tab,
            text="Reset Calibration Tab",
            command=self.reset_calibration_tab
        ).pack(anchor="w", padx=8, pady=(12, 0))

        # ================= GRAPH TAB =================
        graph_controls = tk.Frame(self.graph_tab, bg="white")
        graph_controls.pack(fill="x", padx=10, pady=10)
        graph_controls.columnconfigure(0, weight=0)
        graph_controls.columnconfigure(1, weight=0)
        graph_controls.columnconfigure(2, weight=0)
        graph_controls.columnconfigure(3, weight=0)

        graph_controls_left = tk.Frame(graph_controls, bg="white")
        graph_controls_left.grid(row=0, column=0, sticky="nw", padx=(0, 20))

        graph_controls_right = tk.Frame(graph_controls, bg="white")
        graph_controls_right.grid(row=0, column=1, sticky="nw", padx=(0, 20))

        graph_controls_far_right = tk.Frame(graph_controls, bg="white")
        graph_controls_far_right.grid(row=0, column=2, sticky="nw", padx=(0, 20))

        graph_controls_outer_right = tk.Frame(graph_controls, bg="white")
        graph_controls_outer_right.grid(row=0, column=3, sticky="nw")

        self.create_button(
            graph_controls_left,
            text="Save Graph Image",
            command=self.save_graph_image
        ).pack(anchor="w", pady=(8, 0))
        self.create_button(
            graph_controls_left,
            text="Save Graph Data (CSV)",
            command=self.save_graph_data_csv
        ).pack(anchor="w", pady=(6, 0))
        self.create_button(
            graph_controls_left,
            text="Import Graph File",
            command=self.import_graph_csv
        ).pack(anchor="w", pady=(6, 0))
        self.create_button(
            graph_controls_left,
            text="Map Imported Columns",
            command=self.import_graph_csv_with_mapping
        ).pack(anchor="w", pady=(6, 0))
        self.create_button(
            graph_controls_left,
            text="Clear Imported File",
            command=self.clear_imported_graph_data
        ).pack(anchor="w", pady=(6, 0))

        self.graph_units_label = tk.Label(
            graph_controls_left,
            text="Units: px (uncalibrated)",
            fg="gray30",
            bg="white"
        )
        self.graph_units_label.pack(anchor="w", pady=(6, 0))

        self.graph_view_header_row = self.labeled_header(graph_controls_far_right, "Graph View", pady=(0, 0))
        self.graph_view_combo = ttk.Combobox(
            graph_controls_far_right,
            textvariable=self.graph_view_mode_var,
            values=["Profile", "Histogram", "Q-Q Plot"],
            state="readonly",
            width=18,
            style="Modern.TCombobox",
        )
        self.graph_view_combo.pack(anchor="w")
        self.graph_view_combo.bind("<<ComboboxSelected>>", lambda _event: self.redraw_graph())
        self.attach_tooltip(self.graph_view_combo, "Graph View")

        self.graph_distribution_kind_header_row = self.labeled_header(graph_controls_far_right, "Distribution Values", pady=(8, 0))
        self.graph_distribution_kind_combo = ttk.Menubutton(
            graph_controls_far_right,
            textvariable=self.graph_distribution_kind_var,
            width=18,
            style="Modern.TMenubutton",
        )
        self.graph_distribution_kind_combo.pack(anchor="w")
        self.graph_distribution_kind_menu = tk.Menu(self.graph_distribution_kind_combo, tearoff=0)
        self.graph_distribution_kind_combo.configure(menu=self.graph_distribution_kind_menu)
        self.configure_distribution_kind_menu()
        self.attach_tooltip(self.graph_distribution_kind_combo, "Distribution Values")

        self.graph_histogram_scope_header_row = self.labeled_header(graph_controls_far_right, "Histogram Scope", pady=(8, 0))
        self.graph_histogram_scope_combo = ttk.Menubutton(
            graph_controls_far_right,
            textvariable=self.graph_histogram_scope_var,
            width=18,
            style="Modern.TMenubutton",
        )
        self.graph_histogram_scope_combo.pack(anchor="w")
        self.graph_histogram_scope_menu = tk.Menu(self.graph_histogram_scope_combo, tearoff=0)
        self.graph_histogram_scope_combo.configure(menu=self.graph_histogram_scope_menu)
        self.configure_histogram_scope_menu()
        self.attach_tooltip(self.graph_histogram_scope_combo, "Histogram Scope")

        distribution_label_width = 20

        distribution_column_row = tk.Frame(graph_controls_outer_right, bg="white")
        distribution_column_row.pack(anchor="w", pady=(8, 0))
        self.graph_distribution_column_label = tk.Label(
            distribution_column_row,
            text="Selected Column (px)",
            bg="white",
            width=distribution_label_width,
            anchor="w",
        )
        self.graph_distribution_column_label.grid(row=0, column=0, sticky="w")
        self.graph_distribution_column_entry = self.create_entry(
            distribution_column_row,
            textvariable=self.graph_distribution_column_px_var,
            width=80
        )
        self.graph_distribution_column_entry.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.attach_tooltip(self.graph_distribution_column_entry, "Distribution Column")
        self.create_button(
            distribution_column_row,
            text="Reset Graph Tab",
            command=self.reset_graph_tab
        ).grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.graph_distribution_column_bounds_label = tk.Label(
            graph_controls_outer_right,
            textvariable=self.graph_distribution_column_bounds_var,
            bg="white",
            fg="gray35",
            justify="left",
            wraplength=230,
        )
        self.graph_distribution_column_bounds_label.pack(anchor="w", pady=(2, 0))

        distribution_bins_row = tk.Frame(graph_controls_outer_right, bg="white")
        distribution_bins_row.pack(anchor="w", pady=(6, 0))
        self.graph_distribution_bins_label = tk.Label(
            distribution_bins_row,
            text="Histogram Bins",
            bg="white",
            width=distribution_label_width,
            anchor="w",
        )
        self.graph_distribution_bins_label.grid(row=0, column=0, sticky="w")
        self.graph_distribution_bins_entry = self.create_entry(
            distribution_bins_row,
            textvariable=self.graph_distribution_bins_var,
            width=80
        )
        self.graph_distribution_bins_entry.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.attach_tooltip(self.graph_distribution_bins_entry, "Distribution Bins")

        tk.Label(
            graph_controls_right,
            text="Click the graph title or axis labels to edit titles, units, and axis bounds.",
            bg="white",
            fg="gray30",
            justify="left",
            wraplength=320,
        ).pack(anchor="w", pady=(0, 6))

        self.labeled_header(graph_controls_right, "Graph Standard Deviations", pady=(0, 0))
        self.graph_stdev_entry = self.create_entry(graph_controls_right, textvariable=self.graph_stdevs_var, width=80)
        self.graph_stdev_entry.pack(anchor="w")
        self.attach_tooltip(self.graph_stdev_entry, "Graph Standard Deviations")

        self.labeled_header(graph_controls_right, "Graph Fit Degree", pady=(8, 0))
        self.graph_fit_degree_entry = self.create_entry(graph_controls_right, textvariable=self.graph_fit_degree_var, width=80)
        self.graph_fit_degree_entry.pack(anchor="w")
        self.attach_tooltip(self.graph_fit_degree_entry, "Graph Fit Degree")

        self.show_best_fit_checkbox = ctk.CTkCheckBox(
            graph_controls_right,
            text="Show Best-Fit Line",
            variable=self.show_best_fit_var,
            command=self.redraw_graph,
            text_color=self.TEXT_COLOR,
        )
        self.show_best_fit_checkbox.pack(anchor="w", pady=(6, 0))

        self.graph_fit_equation_text = tk.Text(
            graph_controls_right,
            width=42,
            height=3,
            wrap="word",
            fg="gray20",
            bg="white",
            relief="flat",
            highlightthickness=0,
            borderwidth=0
        )
        self.graph_fit_equation_text.pack(anchor="w", pady=(6, 0))
        self.graph_fit_equation_text.configure(state="disabled")
        self.set_graph_fit_equation_text(self.graph_fit_equation_var.get())

        self.graph_canvas = tk.Canvas(self.graph_tab, bg="white", highlightthickness=1, highlightbackground="#dddddd")
        self.graph_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.graph_canvas.bind("<Configure>", lambda _event: self.redraw_graph())

        # ================= SETTINGS TAB =================
        self.labeled_header(self.settings_tab, "Startup Defaults", pady=(10, 5))
        ctk.CTkLabel(
            self.settings_tab,
            text=(
                "Set up the app the way you want across all tabs, then save those values as startup defaults.\n"
                "They will be loaded automatically next time the app opens."
            ),
            justify="left",
            wraplength=290,
            text_color=self.MUTED_TEXT_COLOR
        ).pack(anchor="w", padx=8)
        ctk.CTkLabel(
            self.settings_tab,
            textvariable=self.settings_status_var,
            justify="left",
            wraplength=290,
            text_color=self.TEXT_COLOR
        ).pack(anchor="w", padx=8, pady=(8, 10))
        self.create_button(
            self.settings_tab,
            text="Save Current Values as Startup Defaults",
            command=self.save_current_as_startup_defaults
        ).pack(anchor="w", padx=8, pady=(0, 6))
        self.create_button(
            self.settings_tab,
            text="Apply Startup Defaults Now",
            command=self.apply_startup_defaults_now
        ).pack(anchor="w", padx=8, pady=(0, 6))
        self.create_button(
            self.settings_tab,
            text="Reset Factory Defaults",
            command=self.reset_saved_startup_defaults
        ).pack(anchor="w", padx=8, pady=(0, 6))
        ctk.CTkLabel(
            self.settings_tab,
            text=f"Settings file: {APP_SETTINGS_FILENAME}",
            justify="left",
            wraplength=290,
            text_color=self.MUTED_TEXT_COLOR
        ).pack(anchor="w", padx=8, pady=(10, 0))

    # ======================================================
    # Range Slider Callback
    # ======================================================

    def on_range_change(self, start, end, active_handle):
        self.range_controller.on_range_change(start, end, active_handle)

    def on_video_source_change(self, event=None):
        source = self.video_source_var.get()
        if source == "Live Camera":
            self.saved_video_session = self.capture_video_file_session_state()
            self.select_video_button.pack_forget()
            self.video_label.configure(text="Live from webcam (press Run to start analysis)")
            self.video_path.set("")  # Clear video path
            self.total_frames = 0
            self.reset_runtime_state()
            # Reset crop to full frame when switching to live camera
            self.crop_left = 0
            self.crop_top = 0
            self.crop_right = 1280
            self.crop_bottom = 720
            self.update_crop_size_label()
            self.set_range_controls_enabled(False)  # Disable range controls for live video
            self.validation_message.set("")
            # Show camera selection controls
            self.camera_label.grid()
            self.camera_combo.grid()
            # Show live frame limit control
            self.live_limit_row.pack(pady=(6, 0), anchor="w", before=self.validation_label)
            
            # Start live preview (without analysis)
            self.start_live_preview()
            self.refresh_run_state()
        else:  # Video File
            self.select_video_button.pack(pady=5)
            self.video_label.configure(text="No video selected")
            self.set_range_controls_enabled(False)  # Will be enabled on video load
            # Hide camera selection controls
            self.camera_label.grid_remove()
            self.camera_combo.grid_remove()
            # Hide live frame limit control
            self.live_limit_row.pack_forget()
            # Stop any live preview
            self.stop_live_preview()
            if not self.restore_video_file_session_state():
                self.video_label.configure(text="No video selected")
                self.set_range_controls_enabled(False)  # Will be enabled on video load
            self.refresh_run_state()

    def capture_video_file_session_state(self):
        """Capture the current video-file session so it can be restored after live mode."""
        video_path = self.video_path.get().strip()
        if not video_path:
            return None

        return {
            "video_path": video_path,
            "video_label": self.video_label.cget("text"),
            "output_dir": self.output_dir.get(),
            "analysis_output_path": self.analysis_output_path_var.get(),
            "threshold_output_path": self.threshold_output_path_var.get(),
            "total_frames": int(self.total_frames),
            "current_preview_frame_index": int(self.current_preview_frame_index),
            "start_frame": int(self.start_frame_var.get()),
            "end_frame": int(self.end_frame_var.get()),
            "start_frame_text": self.start_frame_text.get(),
            "end_frame_text": self.end_frame_text.get(),
            "crop_left": int(self.crop_left),
            "crop_top": int(self.crop_top),
            "crop_right": int(self.crop_right),
            "crop_bottom": int(self.crop_bottom),
            "calibration_line_img": copy.deepcopy(self.calibration_line_img),
            "nozzle_origin_img": copy.deepcopy(self.nozzle_origin_img),
            "graph_unit_scale": float(self.graph_unit_scale),
            "graph_unit_label": self.graph_unit_label,
            "calibration_status": self.calibration_status_var.get(),
            "nozzle_status": self.nozzle_status_var.get(),
            "calibration_distance": self.calibration_distance_var.get(),
            "calibration_units": self.calibration_units_var.get(),
        }

    def restore_video_file_session_state(self):
        """Restore the previous video-file session after leaving live camera mode."""
        session = self.saved_video_session
        if not session:
            return False

        video_path = str(session.get("video_path", "")).strip()
        if not video_path:
            return False

        self.load_video(video_path)
        self.video_label.configure(text=session.get("video_label") or os.path.basename(video_path))
        self.output_dir.set(session.get("output_dir", self.output_dir.get()))
        self.analysis_output_path_var.set(session.get("analysis_output_path", self.analysis_output_path_var.get()))
        self.threshold_output_path_var.set(session.get("threshold_output_path", self.threshold_output_path_var.get()))

        max_frame_index = max(0, self.total_frames - 1)
        start_frame = max(0, min(int(session.get("start_frame", 0)), max_frame_index))
        end_frame = max(start_frame, min(int(session.get("end_frame", max_frame_index)), max_frame_index))
        self.range_slider.set_range(start_frame, end_frame)
        self.apply_range(start_frame, end_frame)
        self.start_frame_text.set(session.get("start_frame_text", str(start_frame)))
        self.end_frame_text.set(session.get("end_frame_text", str(end_frame)))

        preview_frame_index = max(0, min(int(session.get("current_preview_frame_index", start_frame)), max_frame_index))
        self.preview_frame_at(preview_frame_index)

        if self.original_crop_frame is not None:
            frame_height, frame_width = self.original_crop_frame.shape[:2]
            saved_left = int(session.get("crop_left", 0))
            saved_top = int(session.get("crop_top", 0))
            saved_right = int(session.get("crop_right", frame_width))
            saved_bottom = int(session.get("crop_bottom", frame_height))
            if 0 <= saved_left < saved_right <= frame_width and 0 <= saved_top < saved_bottom <= frame_height:
                self.crop_left = saved_left
                self.crop_top = saved_top
                self.crop_right = saved_right
                self.crop_bottom = saved_bottom
                self.update_crop_size_label()
                self.preview_frame_at(preview_frame_index)

        self.calibration_line_img = copy.deepcopy(session.get("calibration_line_img"))
        self.nozzle_origin_img = copy.deepcopy(session.get("nozzle_origin_img"))
        self.graph_unit_scale = float(session.get("graph_unit_scale", 1.0))
        self.graph_unit_label = session.get("graph_unit_label", "px")
        self.calibration_status_var.set(session.get("calibration_status", "Calibration: not set"))
        self.nozzle_status_var.set(session.get("nozzle_status", "Nozzle origin: not set"))
        self.calibration_distance_var.set(session.get("calibration_distance", ""))
        self.calibration_units_var.set(session.get("calibration_units", self.calibration_units_var.get()))
        if self.graph_unit_label == "px":
            self.graph_units_label.configure(text="Units: px (uncalibrated)")
        else:
            self.graph_units_label.configure(
                text=f"Units: {self.graph_unit_label} ({self.graph_unit_scale:.6g} {self.graph_unit_label}/px)"
            )

        if self.last_display_frame is not None:
            self.display_frame(self.last_display_frame)

        return True

    def detect_available_cameras(self):
        """Detect available cameras on the system."""
        self.available_cameras = {}
        camera_names = []

        for camera in list_available_cameras():
            display_name = camera["display_name"]
            self.available_cameras[display_name] = camera
            camera_names.append(display_name)

        # Update combobox with available cameras
        if camera_names:
            self.camera_combo['values'] = camera_names
            self.camera_index_var.set(camera_names[0])
        else:
            self.camera_combo['values'] = ["No cameras found"]
            self.camera_index_var.set("No cameras found")

    def get_camera_source_from_name(self, device_name):
        """Map the selected display name to the camera descriptor."""
        return self.available_cameras.get(
            device_name,
            {"backend": "opencv", "index": 0, "display_name": device_name or "Camera 0"},
        )

    def on_camera_selected(self, event=None):
        """Handle camera selection change - restart preview with new camera."""
        selected_text = self.camera_index_var.get()
        source = self.video_source_var.get()
        
        # Only restart preview if we're in Live Camera mode
        if source == "Live Camera":
            # If preview is running, stop and restart with new camera
            if self.live_preview_active and self.live_engine:
                self.live_engine.stop()
                self.live_engine = None
                self.live_preview_active = False  # Reset flag so new preview can start
            
            # Start preview with new camera
            self.start_live_preview()

    def on_range_entry_commit(self, _event=None):
        self.range_controller.on_range_entry_commit(_event)

    def apply_range(self, start, end, preview_handle=None):
        self.range_controller.apply_range(start, end, preview_handle)
    
    def use_full_video(self):
        self.range_controller.use_full_video()

    def on_notebook_tab_changed(self, _event=None):
        selected = self.notebook.select()
        showing_graph = selected == str(self.graph_tab)
        calibration_tab_selected = selected == str(self.calibration_tab)
        crop_tab_selected = selected == str(self.crop_tab)
        source = self.video_source_var.get()

        if source == "Live Camera" and self.live_engine and self.live_engine.analysis_config and not self.is_running:
            self.live_engine.analysis_config['preview_mode'] = self.preview_mode.get()

        if showing_graph:
            self.left_panel.pack_propagate(True)
            if self.preview_frame.winfo_manager():
                self.preview_frame.pack_forget()
            self.left_panel.pack_configure(fill="both", expand=True)
            self.redraw_graph()
        else:
            self.left_panel.pack_propagate(False)
            self.left_panel.configure(width=self.left_panel_default_width)
            self.left_panel.pack_configure(fill="y", expand=False)
            if not self.preview_frame.winfo_manager():
                self.preview_frame.pack(side="right", expand=True, fill="both")

        if crop_tab_selected:
            has_video_file = self.video_path.get()
            
            # Can edit crop settings for video files or when in live camera mode
            if not self.is_running:
                if source == "Live Camera" and self.live_preview_active:
                    # Always refresh Crop with a raw camera frame rather than a threshold preview.
                    self.enable_live_crop_mode()
                elif has_video_file:
                    self.enable_crop_mode()
        else:
            self.drag_start = None
            self.resize_corner = None
            self.canvas.delete("crop_box")
            self.save_crop_button.configure(state="disabled")

        if not calibration_tab_selected:
            self.calibration_mode = False
            self.calibration_drag_point = None
            self.calibration_pan_active = False
            self.calibration_pan_start = None
            self.nozzle_pick_mode = False
            self.canvas.delete("cal_line")
            self.canvas.delete("nozzle_origin")
        else:
            has_video_file = self.video_path.get()
            
            if has_video_file and not self.is_running:
                # Always show analysis frame in calibration tab to see centerline
                if self.original_crop_frame is not None:
                    self.apply_threshold_settings_to_configs()
                    self.display_frame(self.prepare_preview_frame(self.original_crop_frame.copy()))
                elif self.total_frames > 0:
                    self.preview_frame_at(self.start_frame_var.get())
                else:
                    self.preview_frame_at(0)
            elif source == "Live Camera" and self.last_display_frame is not None:
                # For live camera, show the last captured frame for calibration
                self.display_frame(self.last_display_frame)

        if not showing_graph:
            if self.is_running:
                if self.last_display_frame is not None:
                    self.display_frame(self.last_display_frame)
            elif self.video_path.get() and self.total_frames > 0 and not (crop_tab_selected or calibration_tab_selected):
                # Before running, show the user's selected preview mode on every tab.
                if self.use_multi_threshold_var.get() and self.original_crop_frame is not None:
                    self.apply_threshold_settings_to_configs()
                elif self.original_crop_frame is not None:
                    self.display_frame(self.prepare_preview_frame(self.original_crop_frame.copy()))
                else:
                    self.preview_frame_at(self.current_preview_frame_index)
            elif self.last_display_frame is not None:
                self.display_frame(self.last_display_frame)

    def parse_graph_stdevs(self):
        return self.graph_controller.parse_graph_stdevs()
    
    def parse_graph_fit_degree(self):
        return self.graph_controller.parse_graph_fit_degree()

    def pixels_per_column(self):
        return self.graph_controller.pixels_per_column()

    def profile_index_to_x_px(self, x_index):
        return self.graph_controller.profile_index_to_x_px(x_index)

    def to_graph_units(self, px_value):
        return self.graph_controller.to_graph_units(px_value)

    def x_position_to_graph_units(self, x_px):
        return self.graph_controller.x_position_to_graph_units(x_px)

    def get_profile_height_px(self):
        return self.graph_controller.get_profile_height_px()

    def nozzle_origin_y_in_profile_px(self):
        return self.graph_controller.nozzle_origin_y_in_profile_px()

    def y_position_to_graph_units(self, y_px):
        return self.graph_controller.y_position_to_graph_units(y_px)

    def y_delta_to_graph_units(self, dy_px):
        return self.graph_controller.y_delta_to_graph_units(dy_px)

    def parse_optional_float_var(self, var):
        return self.graph_controller.parse_optional_float_var(var)

    def resolve_axis_limits(self, x_values, y_values, y_pad=1.0):
        return self.graph_controller.resolve_axis_limits(x_values, y_values, y_pad=y_pad)

    def format_graph_value(self, value):
        return self.graph_controller.format_graph_value(value)

    def compute_best_fit(self, mean, valid):
        return self.graph_controller.compute_best_fit(mean, valid)

    def redraw_graph(self):
        self.graph_controller.redraw_graph()

    def build_plot_data(self):
        return self.graph_controller.build_plot_data()

    def build_graph_export_rows(self):
        return self.graph_controller.build_graph_export_rows()

    def render_graph_image(self, width=1600, height=1000):
        return self.graph_controller.render_graph_image(width=width, height=height)

    def save_graph_image(self):
        self.graph_controller.save_graph_image()

    def save_graph_data_csv(self):
        self.graph_controller.save_graph_data_csv()

    def import_graph_csv(self):
        self.graph_controller.import_graph_csv()

    def import_graph_csv_with_mapping(self):
        self.graph_controller.import_graph_csv(force_mapping=True)

    def clear_imported_graph_data(self):
        self.graph_controller.clear_imported_graph_data()

    def configure_distribution_kind_menu(self, disabled_options=None):
        options = ["Residuals", "Positions", "Z-Scores"]
        disabled = set(disabled_options or [])
        menu = getattr(self, "graph_distribution_kind_menu", None)
        if menu is None:
            return

        menu.delete(0, "end")
        for option in options:
            menu.add_radiobutton(
                label=option,
                value=option,
                variable=self.graph_distribution_kind_var,
                command=self.redraw_graph,
                state=("disabled" if option in disabled else "normal"),
            )

    def configure_histogram_scope_menu(self, disabled_options=None):
        options = ["All Columns", "All Columns (Combined)", "Selected Column"]
        disabled = set(disabled_options or [])
        menu = getattr(self, "graph_histogram_scope_menu", None)
        if menu is None:
            return

        menu.delete(0, "end")
        for option in options:
            menu.add_radiobutton(
                label=option,
                value=option,
                variable=self.graph_histogram_scope_var,
                command=self.redraw_graph,
                state=("disabled" if option in disabled else "normal"),
            )

    def set_range_controls_enabled(self, enabled):
        self.range_controller.set_range_controls_enabled(enabled)

    def jump_to_start_frame(self):
        self.range_controller.jump_to_start_frame()

    def jump_to_end_frame(self):
        self.range_controller.jump_to_end_frame()

    # ======================================================
    # Display
    # ======================================================

    def on_resize(self, event):
        self.display_controller.on_resize(event)

    def display_frame(self, frame):
        self.display_controller.display_frame(frame)

    # ======================================================
    # Video Selection
    # ======================================================

    def select_video(self):
        if self.is_running:
            return
        file = filedialog.askopenfilename(filetypes=INPUT_VIDEO_FILETYPES)
        if file:
            self.load_video(file)

    def load_video(self, file):
        self.video_path.set(file)
        self.video_label.configure(text=os.path.basename(file))
        self.output_dir.set(os.path.dirname(file))
        self.update_output_path_defaults(force=False)
        self.reset_runtime_state()
        self.clear_calibration()
        self.analysis_error = None
        self.analysis_was_stopped = False

        cap = cv2.VideoCapture(file)
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ret, frame = cap.read()
        cap.release()

        if ret:
            self.display_frame(frame)
            self.current_preview_frame_index = 0
            h, w = frame.shape[:2]
            self.crop_left = 0
            self.crop_top = 0
            self.crop_right = w
            self.crop_bottom = h
            self.original_crop_frame = frame.copy()
            self.update_crop_size_label()
        else:
            self.crop_left = 0
            self.crop_top = 0
            self.crop_right = 0
            self.crop_bottom = 0
            self.crop_size_text.set("Crop: full frame")

        if self.total_frames > 0:
            self.range_slider.set_range(0, self.total_frames - 1)
            self.apply_range(0, self.total_frames - 1)
        else:
            self.range_slider.set_range(0, 0)
            self.apply_range(0, 0)
        self.set_range_controls_enabled(self.total_frames > 0)
        self.refresh_run_state()

    def get_output_extension(self, format_label):
        return OUTPUT_FORMATS.get(format_label, ".avi")

    def get_output_format_label(self, path, fallback="AVI (.avi)"):
        ext = os.path.splitext(str(path or ""))[1].lower()
        for label, candidate_ext in OUTPUT_FORMATS.items():
            if ext == candidate_ext:
                return label
        return fallback

    def get_default_output_dir(self):
        if self.output_dir.get().strip():
            return self.output_dir.get().strip()
        current_video = self.video_path.get().strip()
        if current_video:
            return os.path.dirname(current_video)
        return os.path.dirname(__file__)

    def get_output_file_name(self, output_kind):
        if output_kind == "analysis":
            return self.output_name_entry.get().strip() or self.app_defaults["output_name"]
        return self.threshold_output_name_var.get().strip() or self.app_defaults["threshold_output_name"]

    def build_default_output_path(self, output_kind):
        base_name = self.get_output_file_name(output_kind)
        format_var = self.analysis_output_format_var if output_kind == "analysis" else self.threshold_output_format_var
        ext = self.get_output_extension(format_var.get())
        return os.path.join(self.get_default_output_dir(), f"{base_name}{ext}")

    def ensure_output_path_extension(self, path, format_label):
        path = str(path or "").strip()
        if not path:
            return ""
        root, _ext = os.path.splitext(path)
        return root + self.get_output_extension(format_label)

    def compose_output_path(self, output_kind, base_path=""):
        format_var = self.analysis_output_format_var if output_kind == "analysis" else self.threshold_output_format_var
        ext = self.get_output_extension(format_var.get())
        base_path = str(base_path or "").strip()
        directory = os.path.dirname(base_path) if base_path else self.get_default_output_dir()
        if not directory:
            directory = self.get_default_output_dir()
        file_name = self.get_output_file_name(output_kind)
        return os.path.join(directory, f"{file_name}{ext}")

    def update_output_path_defaults(self, force=False):
        if force or not self.analysis_output_path_var.get().strip():
            self.analysis_output_path_var.set(self.build_default_output_path("analysis"))
        else:
            self.analysis_output_path_var.set(self.compose_output_path("analysis", self.analysis_output_path_var.get()))
        if force or not self.threshold_output_path_var.get().strip():
            self.threshold_output_path_var.set(self.build_default_output_path("threshold"))
        else:
            self.threshold_output_path_var.set(self.compose_output_path("threshold", self.threshold_output_path_var.get()))

    def on_output_toggle_changed(self):
        self.refresh_output_controls_state()
        self.refresh_run_state()

    def on_output_format_changed(self, output_kind):
        if output_kind == "analysis":
            self.analysis_output_path_var.set(self.compose_output_path("analysis", self.analysis_output_path_var.get()))
        else:
            self.threshold_output_path_var.set(self.compose_output_path("threshold", self.threshold_output_path_var.get()))
        self.output_dir.set(self.get_default_output_dir())
        self.refresh_run_state()

    def select_output_file(self, output_kind):
        if self.is_running:
            return
        is_analysis = output_kind == "analysis"
        path_var = self.analysis_output_path_var if is_analysis else self.threshold_output_path_var
        format_var = self.analysis_output_format_var if is_analysis else self.threshold_output_format_var
        current_path = path_var.get().strip()
        default_path = current_path or self.build_default_output_path(output_kind)
        selected_file = filedialog.asksaveasfilename(
            title=f"Save {output_kind.title()} Video As",
            defaultextension=self.get_output_extension(format_var.get()),
            filetypes=[(label, f"*{ext}") for label, ext in OUTPUT_FORMATS.items()],
            initialdir=os.path.dirname(default_path) or self.get_default_output_dir(),
            initialfile=os.path.basename(default_path),
        )
        if not selected_file:
            return
        path_var.set(selected_file)
        format_var.set(self.get_output_format_label(selected_file, fallback=format_var.get()))
        file_name = os.path.splitext(os.path.basename(selected_file))[0]
        if is_analysis:
            self._set_entry_text(self.output_name_entry, file_name)
        else:
            self.threshold_output_name_var.set(file_name)
        normalized_path = self.compose_output_path(output_kind, path_var.get())
        path_var.set(normalized_path)
        selected_dir = os.path.dirname(normalized_path)
        if selected_dir:
            self.output_dir.set(selected_dir)
        self.refresh_output_controls_state()
        self.refresh_run_state()

    def refresh_output_controls_state(self):
        analysis_enabled = self.save_analysis_output_var.get() and not self.is_running
        threshold_enabled = self.save_threshold_output_var.get() and not self.is_running
        self.output_name_entry.configure(state="normal" if analysis_enabled else "disabled")
        self.analysis_output_entry.configure(state="normal" if analysis_enabled else "disabled")
        self.analysis_output_browse_button.configure(state="normal" if analysis_enabled else "disabled")
        self.analysis_output_format_combo.configure(state="readonly" if analysis_enabled else "disabled")
        self.threshold_output_name_entry.configure(state="normal" if threshold_enabled else "disabled")
        self.threshold_output_entry.configure(state="normal" if threshold_enabled else "disabled")
        self.threshold_output_browse_button.configure(state="normal" if threshold_enabled else "disabled")
        self.threshold_output_format_combo.configure(state="readonly" if threshold_enabled else "disabled")

    def preview_frame_at(self, frame_index):
        self.display_controller.preview_frame_at(frame_index)

    def canvas_to_image_point(self, canvas_x, canvas_y):
        return self.display_controller.canvas_to_image_point(canvas_x, canvas_y)

    def image_to_canvas_point(self, img_x, img_y):
        return self.display_controller.image_to_canvas_point(img_x, img_y)

    def draw_calibration_line(self):
        self.canvas.delete("cal_line")
        if self.calibration_line_img is None:
            return
        x1, y1, x2, y2 = self.calibration_line_img
        cx1, cy1 = self.image_to_canvas_point(x1, y1)
        cx2, cy2 = self.image_to_canvas_point(x2, y2)
        self.canvas.create_line(cx1, cy1, cx2, cy2, fill="#ffeb3b", width=2, tags="cal_line")
        r = 6
        self.canvas.create_oval(cx1 - r, cy1 - r, cx1 + r, cy1 + r, fill="#ff9800", outline="", tags="cal_line")
        self.canvas.create_oval(cx2 - r, cy2 - r, cx2 + r, cy2 + r, fill="#ff9800", outline="", tags="cal_line")
        if self.calibration_mode:
            self.canvas.create_text(
                12, 12, anchor="nw",
                text="Calibration mode: drag endpoints",
                fill="#ffeb3b",
                font=("TkDefaultFont", 10, "bold"),
                tags="cal_line"
            )

    def draw_nozzle_origin(self):
        self.canvas.delete("nozzle_origin")
        if self.nozzle_origin_img is None:
            return
        nx, ny = self.nozzle_origin_img
        cx, cy = self.image_to_canvas_point(nx, ny)
        r = 6
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill="#00bcd4", outline="white", width=1, tags="nozzle_origin"
        )
        self.canvas.create_line(cx - 10, cy, cx + 10, cy, fill="#00bcd4", width=2, tags="nozzle_origin")
        self.canvas.create_line(cx, cy - 10, cx, cy + 10, fill="#00bcd4", width=2, tags="nozzle_origin")
        self.canvas.create_text(
            cx + 12, cy - 10,
            text="Nozzle origin",
            fill="#00bcd4",
            anchor="w",
            font=("TkDefaultFont", 9, "bold"),
            tags="nozzle_origin"
        )

    def nearest_calibration_endpoint(self, canvas_x, canvas_y, threshold=12):
        if self.calibration_line_img is None:
            return None
        x1, y1, x2, y2 = self.calibration_line_img
        cx1, cy1 = self.image_to_canvas_point(x1, y1)
        cx2, cy2 = self.image_to_canvas_point(x2, y2)
        d1 = ((canvas_x - cx1) ** 2 + (canvas_y - cy1) ** 2) ** 0.5
        d2 = ((canvas_x - cx2) ** 2 + (canvas_y - cy2) ** 2) ** 0.5
        if d1 <= threshold and d1 <= d2:
            return 0
        if d2 <= threshold:
            return 1
        return None

    def set_calibration_zoom(self, zoom_value):
        zoom_value = max(1.0, min(8.0, float(zoom_value)))
        self.calibration_zoom = zoom_value
        if self.notebook.select() == str(self.calibration_tab) and self.last_display_frame is not None:
            self.display_frame(self.last_display_frame)

    def on_calibration_mouse_wheel(self, event):
        if self.notebook.select() != str(self.calibration_tab):
            return
        if event.delta > 0:
            self.set_calibration_zoom(self.calibration_zoom * 1.1)
        elif event.delta < 0:
            self.set_calibration_zoom(self.calibration_zoom / 1.1)

    def start_calibration_line_mode(self):
        source = self.video_source_var.get()
        has_video = bool(self.video_path.get())
        has_live_frame = (source == "Live Camera" and self.last_display_frame is not None)
        if not has_video and not has_live_frame:
            messagebox.showinfo("Calibration", "Select a video or start live preview first.")
            return
        self.nozzle_pick_mode = False
        self.crop_mode = False
        self.canvas.delete("crop_box")
        self.save_crop_button.configure(state="disabled")
        self.calibration_mode = True
        if self.calibration_line_img is None:
            scale = self.current_scale if self.current_scale > 0 else 1.0
            center_x = max(0.0, (self.display_w / scale) / 2.0)
            center_y = max(0.0, (self.display_h / scale) / 2.0)
            self.calibration_line_img = [center_x - 40, center_y, center_x + 40, center_y]
        self.calibration_status_var.set("Calibration: draw or drag line endpoints on preview.")
        if self.last_display_frame is not None:
            self.display_frame(self.last_display_frame)
        self.draw_calibration_line()

    def start_nozzle_pick_mode(self):
        source = self.video_source_var.get()
        has_video = bool(self.video_path.get())
        has_live_frame = (source == "Live Camera" and self.last_display_frame is not None)
        if not has_video and not has_live_frame:
            messagebox.showinfo("Nozzle origin", "Select a video or start live preview first.")
            return
        self.crop_mode = False
        self.canvas.delete("crop_box")
        self.save_crop_button.configure(state="disabled")
        self.calibration_mode = False
        self.calibration_drag_point = None
        self.nozzle_pick_mode = True
        self.nozzle_status_var.set("Nozzle origin: click the nozzle exit point on preview.")
        if self.last_display_frame is not None:
            self.display_frame(self.last_display_frame)

    def calibration_pixel_length(self):
        if self.calibration_line_img is None:
            return None
        x1, y1, x2, y2 = self.calibration_line_img
        return float(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)

    def apply_calibration(self):
        pixel_distance = self.calibration_pixel_length()
        if pixel_distance is None or pixel_distance < 1e-6:
            messagebox.showerror("Calibration", "Draw a calibration line first.")
            return
        try:
            real_distance = float(str(self.calibration_distance_var.get()).strip())
        except ValueError:
            messagebox.showerror("Calibration", "Calibration distance must be a number.")
            return
        if real_distance <= 0:
            messagebox.showerror("Calibration", "Calibration distance must be greater than 0.")
            return

        units = self.calibration_units_var.get().strip() or "mm"
        old_default_x = f"Horizontal Position ({self.graph_unit_label})"
        old_default_y = f"Vertical Position ({self.graph_unit_label})"
        self.graph_unit_scale = real_distance / pixel_distance
        self.graph_unit_label = units
        x_label_text = self.graph_x_axis_label.get().strip()
        if x_label_text == old_default_x or x_label_text in ("Column Index (pixels)", "Column Index (px)"):
            self.graph_x_axis_label.set(f"Horizontal Position ({units})")
        if self.graph_y_axis_label.get().strip() == old_default_y:
            self.graph_y_axis_label.set(f"Vertical Position ({units})")
        self.graph_units_label.configure(
            text=f"Units: {units} | Scale: {self.graph_unit_scale:.6g} {units}/px"
        )
        self.calibration_status_var.set(
            f"Calibration set: {real_distance:g} {units} over {pixel_distance:.2f} px "
            f"({self.graph_unit_scale:.6g} {units}/px)"
        )
        self.calibration_mode = False
        self.calibration_drag_point = None
        self.redraw_graph()

    def clear_calibration(self):
        self.graph_unit_scale = 1.0
        old_default_x = f"Horizontal Position ({self.graph_unit_label})"
        old_default_y = f"Vertical Position ({self.graph_unit_label})"
        self.graph_unit_label = "px"
        if self.graph_x_axis_label.get().strip() == old_default_x:
            self.graph_x_axis_label.set("Horizontal Position (px)")
        if self.graph_y_axis_label.get().strip() == old_default_y:
            self.graph_y_axis_label.set("Vertical Position (px)")
        self.graph_units_label.configure(text="Units: px (uncalibrated)")
        self.calibration_status_var.set("Calibration: not set")
        self.calibration_mode = False
        self.calibration_drag_point = None
        self.calibration_line_img = None
        self.nozzle_pick_mode = False
        self.nozzle_origin_img = None
        self.nozzle_status_var.set("Nozzle origin: not set")
        self.canvas.delete("cal_line")
        self.canvas.delete("nozzle_origin")
        self.redraw_graph()

    # ======================================================
    # Cropping
    # ======================================================

    def should_show_full_preview_frame(self):
        return self.display_controller.should_show_full_preview_frame()

    def prepare_preview_frame(self, frame):
        return self.display_controller.prepare_preview_frame(frame)

    def has_saved_crop_for_shape(self, width, height):
        return (
            0 <= self.crop_left < self.crop_right <= width
            and 0 <= self.crop_top < self.crop_bottom <= height
        )

    def apply_saved_crop_to_frame(self, frame):
        if frame is None:
            return frame
        h, w = frame.shape[:2]
        if not self.has_saved_crop_for_shape(w, h):
            return frame
        cropped = frame[self.crop_top:self.crop_bottom, self.crop_left:self.crop_right]
        if cropped.size == 0:
            return frame
        return cropped

    def enable_crop_mode(self, reset_box=False):
        if self.is_running:
            return
        if not self.video_path.get():
            return

        cap = cv2.VideoCapture(self.video_path.get())
        frame_index = self.current_preview_frame_index
        if self.total_frames > 0:
            frame_index = max(0, min(int(frame_index), self.total_frames - 1))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return

        self._setup_crop_mode(frame, reset_box=reset_box)

    def enable_live_crop_mode(self, reset_box=False):
        """Enable crop mode for live camera using the current preview frame."""
        if self.is_running or not self.live_preview_active:
            return
        
        frame = None
        # Crop editing should always use the raw camera frame, not a threshold preview.
        if self.last_raw_frame is not None:
            frame = self.last_raw_frame.copy()
        elif self.original_crop_frame is not None:
            frame = self.original_crop_frame.copy()
        elif self.last_display_frame is not None:
            frame = self.last_display_frame.copy()
        
        if frame is None:
            return
        
        self._setup_crop_mode(frame, reset_box=reset_box)

    def _setup_crop_mode(self, frame, reset_box=False):
        """Common setup for crop mode (used by both video files and live camera)."""
        self.original_crop_frame = frame.copy()
        self.calibration_mode = False
        self.calibration_drag_point = None
        self.crop_mode = True
        self.save_crop_button.configure(state="normal")
        self.display_frame(frame)

        h, w = frame.shape[:2]
        has_saved_crop = (
            0 <= self.crop_left < self.crop_right <= w
            and 0 <= self.crop_top < self.crop_bottom <= h
        )

        if reset_box:
            h, w = frame.shape[:2]
            self.crop_rect = [
                self.x_offset,
                self.y_offset,
                self.x_offset + int(round(w * self.current_scale)),
                self.y_offset + int(round(h * self.current_scale))
            ]
        elif has_saved_crop:
            self.crop_rect = [
                self.x_offset + int(round(self.crop_left * self.current_scale)),
                self.y_offset + int(round(self.crop_top * self.current_scale)),
                self.x_offset + int(round(self.crop_right * self.current_scale)),
                self.y_offset + int(round(self.crop_bottom * self.current_scale))
            ]
        else:
            pad = min(80, max(10, min(self.display_w, self.display_h) // 8))
            self.crop_rect = [
                self.x_offset + pad,
                self.y_offset + pad,
                self.x_offset + self.display_w - pad,
                self.y_offset + self.display_h - pad
            ]
        self.crop_rect = self.clamp_crop_rect(self.crop_rect)
        self.update_crop_size_label(preview_rect=self.crop_rect)
        self.draw_crop_box()

    def reset_crop(self):
        if self.is_running:
            return
        
        source = self.video_source_var.get()
        
        # For video files, reload the current frame from video file
        if source == "Video File" and self.video_path.get():
            cap = cv2.VideoCapture(self.video_path.get())
            frame_index = self.current_preview_frame_index
            if self.total_frames > 0:
                frame_index = max(0, min(int(frame_index), self.total_frames - 1))
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return
            self.original_crop_frame = frame.copy()
        # For live camera, get the raw uncropped frame
        elif source == "Live Camera":
            # Try to use stored raw frame first, fall back to capturing directly
            if self.last_raw_frame is not None:
                self.original_crop_frame = self.last_raw_frame.copy()
            else:
                # Fallback: capture directly from camera
                camera_source = self.get_camera_source_from_name(self.camera_index_var.get())
                cap = create_camera_capture(camera_source)
                ret, frame = False, None
                try:
                    if cap.open():
                        ret, frame = cap.read()
                finally:
                    cap.release()
                if not ret:
                    return
                self.original_crop_frame = frame.copy()

        h, w = self.original_crop_frame.shape[:2]
        self.crop_left = 0
        self.crop_top = 0
        self.crop_right = w
        self.crop_bottom = h
        self.update_crop_size_label()
        self.refresh_run_state()

        if self.notebook.select() == str(self.crop_tab):
            if source == "Live Camera":
                self.enable_live_crop_mode(reset_box=True)
            else:
                self.enable_crop_mode(reset_box=True)

    def draw_crop_box(self):
        self.canvas.delete("crop_box")
        x1, y1, x2, y2 = self.crop_rect

        self.canvas.create_rectangle(x1, y1, x2, y2,
                                     outline="red",
                                     width=2,
                                     tags="crop_box")

        for (cx, cy) in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
            self.canvas.create_rectangle(
                cx - self.CORNER_SIZE,
                cy - self.CORNER_SIZE,
                cx + self.CORNER_SIZE,
                cy + self.CORNER_SIZE,
                fill="red",
                tags="crop_box"
            )

    def detect_corner(self, x, y):
        x1, y1, x2, y2 = self.crop_rect
        corners = {
            "tl": (x1, y1),
            "tr": (x2, y1),
            "bl": (x1, y2),
            "br": (x2, y2)
        }
        for name, (cx, cy) in corners.items():
            if abs(x - cx) < self.CORNER_SIZE and abs(y - cy) < self.CORNER_SIZE:
                return name
        return None

    def on_mouse_down(self, event):
        crop_tab_selected = self.notebook.select() == str(self.crop_tab)
        calibration_tab_selected = self.notebook.select() == str(self.calibration_tab)

        if self.nozzle_pick_mode and self.notebook.select() == str(self.calibration_tab):
            img_pt = self.canvas_to_image_point(event.x, event.y)
            if img_pt is None:
                return
            x_img, y_img = img_pt
            self.nozzle_origin_img = [x_img, y_img]
            self.nozzle_pick_mode = False
            self.nozzle_status_var.set(f"Nozzle origin set: x={x_img:.1f}px, y={y_img:.1f}px")
            if self.last_display_frame is not None:
                self.display_frame(self.last_display_frame)
            self.redraw_graph()
            return

        if self.calibration_mode:
            img_pt = self.canvas_to_image_point(event.x, event.y)
            if img_pt is None:
                return
            endpoint = self.nearest_calibration_endpoint(event.x, event.y)
            if endpoint is not None:
                self.calibration_drag_point = endpoint
                return
            x_img, y_img = img_pt
            self.calibration_line_img = [x_img, y_img, x_img, y_img]
            self.calibration_drag_point = 1
            self.draw_calibration_line()
            return

        if (not self.crop_mode) or (not crop_tab_selected):
            return
        corner = self.detect_corner(event.x, event.y)
        if corner:
            self.resize_corner = corner
        else:
            x1, y1, x2, y2 = self.crop_rect
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.drag_start = (event.x, event.y)

    def on_mouse_drag(self, event):
        crop_tab_selected = self.notebook.select() == str(self.crop_tab)

        if self.calibration_mode:
            if self.calibration_drag_point is None or self.calibration_line_img is None:
                return
            img_pt = self.canvas_to_image_point(event.x, event.y)
            if img_pt is None:
                return
            x_img, y_img = img_pt
            if self.calibration_drag_point == 0:
                self.calibration_line_img[0] = x_img
                self.calibration_line_img[1] = y_img
            else:
                self.calibration_line_img[2] = x_img
                self.calibration_line_img[3] = y_img
            self.draw_calibration_line()
            return

        if (not self.crop_mode) or (not crop_tab_selected):
            return

        x1, y1, x2, y2 = self.crop_rect

        if self.resize_corner:
            if "l" in self.resize_corner:
                x1 = event.x
            if "r" in self.resize_corner:
                x2 = event.x
            if "t" in self.resize_corner:
                y1 = event.y
            if "b" in self.resize_corner:
                y2 = event.y
        elif self.drag_start:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            x1 += dx
            x2 += dx
            y1 += dy
            y2 += dy
            self.drag_start = (event.x, event.y)

        self.crop_rect = self.clamp_crop_rect([x1, y1, x2, y2])
        self.update_crop_size_label(preview_rect=self.crop_rect)
        self.draw_crop_box()

    def on_mouse_up(self, event):
        self.calibration_drag_point = None
        self.drag_start = None
        self.resize_corner = None

    def on_right_mouse_down(self, event):
        """Handle right-click for panning in calibration tab."""
        if self.notebook.select() == str(self.calibration_tab):
            self.calibration_pan_active = True
            self.calibration_pan_start = (event.x, event.y)

    def on_right_mouse_drag(self, event):
        """Handle right-click drag for panning in calibration tab."""
        if self.calibration_pan_active and self.notebook.select() == str(self.calibration_tab):
            if self.calibration_pan_start is None:
                return
            dx = event.x - self.calibration_pan_start[0]
            dy = event.y - self.calibration_pan_start[1]
            self.calibration_pan_x += dx
            self.calibration_pan_y += dy
            self.calibration_pan_start = (event.x, event.y)
            if self.last_display_frame is not None:
                self.display_frame(self.last_display_frame)

    def on_right_mouse_up(self, event):
        """Handle right-click release for panning."""
        self.calibration_pan_active = False
        self.calibration_pan_start = None

    def save_crop(self):
        if not self.crop_mode:
            return

        if self.original_crop_frame is None:
            return

        x1, y1, x2, y2 = self.clamp_crop_rect(self.crop_rect)
        h, w = self.original_crop_frame.shape[:2]

        left = int(max(0, min((x1 - self.x_offset) / self.current_scale, w - 1)))
        right = int(max(1, min((x2 - self.x_offset) / self.current_scale, w)))
        top = int(max(0, min((y1 - self.y_offset) / self.current_scale, h - 1)))
        bottom = int(max(1, min((y2 - self.y_offset) / self.current_scale, h)))

        if right <= left:
            right = min(w, left + 1)
        if bottom <= top:
            bottom = min(h, top + 1)

        self.crop_left = left
        self.crop_right = right
        self.crop_top = top
        self.crop_bottom = bottom

        self.crop_mode = False
        self.save_crop_button.configure(state="disabled")
        self.canvas.delete("crop_box")
        self.update_crop_size_label()
        self.refresh_run_state()

        cropped = self.original_crop_frame[
            self.crop_top:self.crop_bottom,
            self.crop_left:self.crop_right
        ]
        if cropped.size > 0:
            self.display_frame(cropped)
        
        # If in live camera mode, restart preview with new crop settings
        source = self.video_source_var.get()
        if source == "Live Camera" and self.live_preview_active and not self.is_running:
            self.stop_live_preview()
            self.start_live_preview()

    def clamp_crop_rect(self, rect):
        if self.display_w <= 0 or self.display_h <= 0:
            return rect
        x1, y1, x2, y2 = rect
        left_bound = self.x_offset
        top_bound = self.y_offset
        right_bound = self.x_offset + self.display_w
        bottom_bound = self.y_offset + self.display_h
        min_size = 8

        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))

        x1 = max(left_bound, min(x1, right_bound))
        x2 = max(left_bound, min(x2, right_bound))
        y1 = max(top_bound, min(y1, bottom_bound))
        y2 = max(top_bound, min(y2, bottom_bound))

        if x2 - x1 < min_size:
            if x1 + min_size <= right_bound:
                x2 = x1 + min_size
            else:
                x1 = max(left_bound, right_bound - min_size)
                x2 = right_bound

        if y2 - y1 < min_size:
            if y1 + min_size <= bottom_bound:
                y2 = y1 + min_size
            else:
                y1 = max(top_bound, bottom_bound - min_size)
                y2 = bottom_bound

        return [int(x1), int(y1), int(x2), int(y2)]

    # ======================================================
    # Processing
    # ======================================================

    def start_live_preview(self):
        """Start live camera preview without analysis."""
        if self.live_preview_active:
            return
        
        source = self.video_source_var.get()
        if source != "Live Camera":
            return
        
        # Show immediate feedback
        self.set_status("Connecting to camera...", "normal")
        self.root.update_idletasks()  # Force UI update
        
        self.live_preview_active = True
        
        # Get selected camera descriptor from device name
        selected_camera = self.camera_index_var.get()
        camera_source = self.get_camera_source_from_name(selected_camera)
        
        # Build preview config with current crop settings
        crop_left = self.crop_left if self.crop_left < self.crop_right else 0
        crop_right = self.crop_right if self.crop_right > self.crop_left else 1280
        crop_top = self.crop_top if self.crop_top < self.crop_bottom else 0
        crop_bottom = self.crop_bottom if self.crop_bottom > self.crop_top else 720
        
        preview_config = {
            'crop_left': crop_left,
            'crop_right': crop_right,
            'crop_top': crop_top,
            'crop_bottom': crop_bottom,
            'threshold_offset': self.threshold_offset_var.get(),
            'pixels_per_col': 1,
            'stdevs': 0,
            'preview_mode': self.preview_mode.get(),
            'show_preview_std_region': self.show_preview_std_region_var.get(),
            'show_preview_frame_dots': self.show_preview_frame_dots_var.get(),
            'show_preview_mean_line': self.show_preview_mean_line_var.get(),
            'apply_preview_overlay_to_output': self.apply_preview_overlay_to_output_var.get(),
        }
        
        # Start preview without analysis (analysis_config has preview_mode)
        self.live_engine = LiveEngine(gui=self, camera_source=camera_source, analysis_config=preview_config)
        self.live_engine.start(analyze=False)
        # Status will be updated to "Live preview: Camera ready" once first frame is received
        # Don't call refresh_run_state() here as it would override the "Connecting..." message

    def stop_live_preview(self):
        """Stop live camera preview."""
        if self.live_engine:
            self.live_engine.stop()
            self.live_engine = None
        self.live_preview_active = False

    def start_thread(self):
        if self.is_running:
            return

        source = self.video_source_var.get()

        if source == "Video File":
            is_valid, errors = self.validate_inputs(for_run=True)
            if not is_valid:
                self.validation_message.set("\n".join(errors))
                return

            self.imported_profile_data = None
            self.imported_distribution_data = None
            self.imported_table_path = ""
            self.imported_table_rows = None
            config = self.build_config()
            self.is_running = True
            self.stop_event = threading.Event()
            self.current_analysis_config = config  # Store reference for live threshold updates
            self.analysis_error = None
            self.analysis_was_stopped = False

            self.set_processing_controls(True)
            self.total_frames_to_process = config.num_frames

            self.progress["maximum"] = self.total_frames_to_process
            self.progress["value"] = 0

            self.frame_counter = 0
            self.start_time = time.time()

            thread = threading.Thread(target=self.run_analysis,
                                      args=(config,), daemon=True)
            thread.start()
        elif source == "Live Camera":
            # Stop any existing preview/analysis without waiting
            if self.live_engine:
                self.live_engine.stop()
                self.live_engine = None
            
            self.imported_profile_data = None
            self.imported_distribution_data = None
            self.imported_table_path = ""
            self.imported_table_rows = None
            self.live_preview_active = False
            self.analysis_error = None
            self.analysis_was_stopped = False
            self.set_processing_controls(True)
            self.reset_runtime_state()
            self.set_status("Starting live analysis...", "normal")
            
            # Get selected camera descriptor from device name
            selected_camera = self.camera_index_var.get()
            camera_source = self.get_camera_source_from_name(selected_camera)
            
            # Build analysis config for live engine
            # Use default crop values if not set by user
            crop_left = self.crop_left if self.crop_left < self.crop_right else 0
            crop_right = self.crop_right if self.crop_right > self.crop_left else 1280
            crop_top = self.crop_top if self.crop_top < self.crop_bottom else 0
            crop_bottom = self.crop_bottom if self.crop_bottom > self.crop_top else 720
            
            # Parse frame limit (empty = unlimited)
            max_frames = None
            limit_text = self.live_frame_limit.get().strip()
            if limit_text:
                try:
                    max_frames = int(limit_text)
                    if max_frames <= 0:
                        max_frames = None
                except ValueError:
                    max_frames = None
            
            live_analysis_config = {
                'crop_left': crop_left,
                'crop_right': crop_right,
                'crop_top': crop_top,
                'crop_bottom': crop_bottom,
                'threshold_offset': self.threshold_offset_var.get(),
                'frame_stride': max(1, self.safe_int(self.analyze_every_entry.get()) or 1),
                'pixels_per_col': max(1, self.safe_int(self.pixel_entry.get()) or 3),
                'stdevs': max(0, self.safe_int(self.stdev_entry.get()) or 2),
                'avg_line_thickness': 2,
                'show_confidence': True,
                'confidence_mode': self.preview_mode.get() if self.preview_mode.get() == 'analysis' else 'band',
                'preview_mode': self.preview_mode.get(),
                'show_preview_std_region': self.show_preview_std_region_var.get(),
                'show_preview_frame_dots': self.show_preview_frame_dots_var.get(),
                'show_preview_mean_line': self.show_preview_mean_line_var.get(),
                'apply_preview_overlay_to_output': self.apply_preview_overlay_to_output_var.get(),
                'max_frames': max_frames,
                'use_multi_threshold': self.use_multi_threshold_var.get(),
                'multi_threshold_offsets': self.get_multi_threshold_offsets(),
                'multi_threshold_weights': self.get_multi_threshold_weights(),
                'multi_threshold_colors': self.get_multi_threshold_colors(),
            }
            
            # Set up progress bar for frame limit
            if max_frames:
                self.total_frames_to_process = max_frames
                self.progress["maximum"] = max_frames
                self.progress["value"] = 0
            else:
                self.progress["maximum"] = 100
                self.progress["value"] = 0
            
            analysis_output_path = None
            threshold_output_path = None
            if self.save_analysis_output_var.get():
                analysis_output_path = self.ensure_output_path_extension(
                    self.analysis_output_path_var.get(),
                    self.analysis_output_format_var.get(),
                )
            if self.save_threshold_output_var.get():
                threshold_output_path = self.ensure_output_path_extension(
                    self.threshold_output_path_var.get(),
                    self.threshold_output_format_var.get(),
                )
            
            # Initialize and start the live engine with analysis enabled
            self.is_running = True
            self.stop_event = threading.Event()
            self.live_engine = LiveEngine(
                gui=self, 
                camera_source=camera_source, 
                analysis_config=live_analysis_config,
                analysis_output_path=analysis_output_path,
                threshold_output_path=threshold_output_path,
            )
            self.live_engine.start(analyze=True)
            self.refresh_run_state()

    def on_live_analysis_complete(self):
        """Called by LiveEngine when analysis completes naturally (e.g., frame limit reached)."""
        if self.live_engine and self.live_engine.running_stats:
            self.final_mean_profile, self.final_std_profile = self.live_engine.running_stats.get_mean_std()
        self.final_centerline_samples = None
        self.live_engine = None
        self.analysis_was_stopped = False  # Completed normally, not stopped
        self.reset_state()

    def stop_analysis(self):
        # Clear validation errors to allow recovery
        self.validation_message.set("")
        
        source = self.video_source_var.get()
        if source == "Live Camera":
            if self.live_engine:
                # Signal stop and grab profiles immediately (thread will finish in background)
                self.live_engine.stop()
                # Get whatever profiles we have so far without waiting
                if self.live_engine.running_stats:
                    self.final_mean_profile, self.final_std_profile = self.live_engine.running_stats.get_mean_std()
                else:
                    self.final_mean_profile = None
                    self.final_std_profile = None
                self.final_centerline_samples = None
                # Don't wait for thread - let it finish in background
                self.live_engine = None
            self.analysis_was_stopped = True
            self.reset_state()
        else: # Video File
            if self.stop_event:
                self.stop_event.set()
                self.set_status("Stopping", "warning")
            else:
                # Not running but user clicked stop - just refresh state
                self.refresh_run_state()

    def run_analysis(self, config):
        try:
            final_mean, final_std, _threshold_history, centerline_samples = process_video(
                config,
                preview_callback=self.update_preview,
                stop_event=self.stop_event
            )
            self.final_mean_profile = final_mean
            self.final_std_profile = final_std
            self.final_centerline_samples = centerline_samples
            self.root.after(0, self.redraw_graph)
            if self.stop_event and self.stop_event.is_set():
                self.analysis_was_stopped = True
        except Exception as exc:
            self.analysis_error = exc
        finally:
            self.root.after(0, self.reset_state)

    def reset_state(self):
        self.is_running = False
        self.set_processing_controls(False)
        
        source = self.video_source_var.get()
        
        if source == "Live Camera":
            # For live camera, redraw graph with captured data
            has_valid_profile = self.final_mean_profile is not None and np.any(np.isfinite(self.final_mean_profile))
            if has_valid_profile:
                self.redraw_graph()
            
            if self.analysis_error is not None:
                self.set_status("Error", "error")
                messagebox.showerror(
                    "Live analysis failed",
                    f"{self.analysis_error}"
                )
            elif self.analysis_was_stopped:
                self.set_status("Stopped", "warning")
            else:
                self.set_status("Ready", "ready")
            
            # Restart preview for continuous camera view
            self.start_live_preview()
            
            self.analysis_error = None
            self.analysis_was_stopped = False
        else:
            # Video file mode
            if self.analysis_error is not None:
                self.set_status("Error", "error")
                messagebox.showerror(
                    "Processing failed",
                    f"{self.analysis_error}\n\nCheck output directory permissions and output file paths."
                )
            elif self.analysis_was_stopped:
                self.set_status("Stopped", "warning")
                messagebox.showinfo(
                    "Processing stopped",
                    f"Stopped at frame {self.frame_counter} of {self.total_frames_to_process}."
                )
            else:
                self.set_status("Ready", "ready")
            self.analysis_error = None
            self.analysis_was_stopped = False
        
        self.refresh_run_state()

    def update_preview(self, processed_count, frame, binary_frame, threshold_value,
                       raw_frame=None, centerline_array=None, running_avg=None, running_std=None):
        self.display_controller.update_preview(
            processed_count,
            frame,
            binary_frame,
            threshold_value,
            raw_frame,
            centerline_array,
            running_avg,
            running_std,
        )

    def on_threshold_changed(self, value):
        """Handle threshold slider changes with real-time preview update."""
        threshold_val = int(value)
        
        # Update the displayed value first
        self.threshold_value_label.configure(text=value)
        
        # Check if this would cause clamping and prevent it (only if we have a frame)
        min_allowed = self.get_minimum_threshold_offset()
        if min_allowed is not None and threshold_val < min_allowed:
            # Don't allow values that would cause clamping
            # Use after to avoid triggering this callback recursively
            self.root.after(0, lambda: self.threshold_offset_var.set(min_allowed))
            return
        
        # Update actual threshold display
        self.update_actual_threshold_display()
        
        # Update live engine config if running
        source = self.video_source_var.get()
        if source == "Live Camera" and self.live_engine and self.live_engine.analysis_config:
            self.live_engine.analysis_config['threshold_offset'] = threshold_val
        
        # Update video file analysis config if running
        if self.is_running and self.current_analysis_config:
            self.current_analysis_config.threshold_offset = threshold_val
        
        # Update post-analysis preview
        self.update_post_analysis_preview()

    def get_minimum_threshold_offset(self):
        """Calculate the minimum allowed threshold offset to avoid clamping."""
        try:
            # Get current frame to calculate Otsu threshold
            frame = None
            
            if self.last_raw_frame is not None:
                frame = self.last_raw_frame
            elif self.last_analysis_frame is not None and len(self.last_analysis_frame.shape) == 3 and self.last_analysis_frame.shape[2] == 3:
                frame = self.last_analysis_frame
            elif self.last_display_frame is not None and len(self.last_display_frame.shape) == 3 and self.last_display_frame.shape[2] == 3:
                frame = self.last_display_frame
            elif self.video_path.get() and self.video_source_var.get() == "Video File":
                try:
                    cap = cv2.VideoCapture(self.video_path.get())
                    frame_index = self.current_preview_frame_index
                    if self.total_frames > 0:
                        frame_index = max(0, min(int(frame_index), self.total_frames - 1))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                    ret, frame = cap.read()
                    cap.release()
                    if not ret:
                        frame = None
                except:
                    frame = None
            
            if frame is None:
                return None
            
            # Calculate Otsu threshold
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            otsu_thresh, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Minimum offset allowed is (1 - otsu_thresh) so that otsu + offset >= 1
            return 1 - int(otsu_thresh)
        except:
            return None

    def on_threshold_mode_toggle(self):
        """Handle toggling between single and multi-threshold modes."""
        use_multi = self.use_multi_threshold_var.get()
        
        # Update visibility of threshold controls in Threshold tab
        self.update_multi_threshold_visibility()
        
        # Apply threshold settings to configs with updated multi-threshold state
        self.apply_threshold_settings_to_configs()

    def update_multi_threshold_visibility(self):
        """Show/hide multi-threshold controls based on mode."""
        use_multi = self.use_multi_threshold_var.get()
        
        # Show/hide threshold column frames
        num_thresholds = max(1, min(5, int(self.num_thresholds_var.get())))
        for idx, col_frame in enumerate(self.multi_threshold_rows):
            if use_multi and idx < num_thresholds:
                col_frame.grid()
            else:
                col_frame.grid_remove()

        # Show/hide region color/weight controls (regions = thresholds + 1)
        region_count = num_thresholds + 1
        for idx, region_frame in enumerate(self.multi_region_rows):
            if use_multi and idx < region_count:
                region_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
            else:
                region_frame.pack_forget()

    def update_actual_threshold_display(self):
        """Calculate and display the actual threshold value (Otsu + offset)."""
        try:
            # Get current frame to calculate Otsu threshold
            frame = None
            
            # First try raw frame (for live camera)
            if self.last_raw_frame is not None:
                frame = self.last_raw_frame
            # For video files, check if we have analysis frame and it's a color frame
            elif self.last_analysis_frame is not None and len(self.last_analysis_frame.shape) == 3 and self.last_analysis_frame.shape[2] == 3:
                frame = self.last_analysis_frame
            # If display frame is a color frame (not binary), use it
            elif self.last_display_frame is not None and len(self.last_display_frame.shape) == 3 and self.last_display_frame.shape[2] == 3:
                frame = self.last_display_frame
            # Last resort: try to read current frame from video file
            elif self.video_path.get() and self.video_source_var.get() == "Video File":
                try:
                    cap = cv2.VideoCapture(self.video_path.get())
                    frame_index = self.current_preview_frame_index
                    if self.total_frames > 0:
                        frame_index = max(0, min(int(frame_index), self.total_frames - 1))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                    ret, frame = cap.read()
                    cap.release()
                    if not ret:
                        frame = None
                except:
                    frame = None
            
            if frame is None:
                self.actual_threshold_label.configure(text="Actual Threshold: N/A (no frame)")
                return
            
            # Calculate Otsu threshold
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            otsu_thresh, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Get offset and calculate final threshold
            offset = self.threshold_offset_var.get()
            adjusted_thresh = otsu_thresh + offset
            final_thresh = max(1, adjusted_thresh)
            
            # Update label
            self.actual_threshold_label.configure(
                text=f"Actual Threshold: {int(final_thresh)} (Otsu: {int(otsu_thresh)} + Offset: {int(offset)})"
            )
        except Exception as e:
            self.actual_threshold_label.configure(text=f"Actual Threshold: Error ({str(e)[:20]})")

    def on_num_thresholds_changed(self, event=None):
        """Handle change in number of thresholds."""
        self.update_multi_threshold_visibility()
        self.apply_threshold_settings_to_configs()

    def _nudge_threshold(self, index, delta):
        """Increment/decrement a threshold offset by delta and trigger update."""
        var = self.multi_threshold_offsets[index]
        new_val = max(-50, min(100, var.get() + delta))
        var.set(new_val)
        self.on_multi_threshold_changed(index, new_val)

    def on_multi_threshold_changed(self, index, value):
        """Handle multi-threshold slider changes."""
        threshold_val = int(value)
        
        # Update value label
        if 0 <= index < len(self.multi_threshold_value_labels):
            self.multi_threshold_value_labels[index].configure(text=str(threshold_val))
        
        # Apply settings
        self.apply_threshold_settings_to_configs()

    def on_multi_threshold_weights_changed(self, index):
        """Handle multi-threshold weight entry changes."""
        self.apply_threshold_settings_to_configs()

    def pick_multi_threshold_color(self, index):
        """Open color picker for a threshold region."""
        current_color = self.multi_threshold_colors[index]
        color = colorchooser.askcolor(color=current_color, title=f"Pick color for region {index + 1}")
        if color[1]:
            hex_color = color[1]
            self.multi_threshold_colors[index] = hex_color
            # Update the label color
            if index < len(self.multi_region_color_buttons):
                self.multi_region_color_buttons[index].configure(bg=hex_color)
            self.apply_threshold_settings_to_configs()

    def get_multi_threshold_offsets(self):
        """Get current multi-threshold offsets."""
        count = max(1, min(5, int(self.num_thresholds_var.get())))
        return [self.multi_threshold_offsets[idx].get() for idx in range(count)]

    def get_multi_threshold_weights(self):
        """Get current multi-threshold weights."""
        count = max(1, min(5, int(self.num_thresholds_var.get())))
        region_count = count + 1
        return [self.multi_threshold_weights[idx].get() for idx in range(region_count)]

    def get_multi_threshold_colors(self):
        """Get current multi-threshold colors."""
        count = max(1, min(5, int(self.num_thresholds_var.get())))
        region_count = count + 1
        return [self.multi_threshold_colors[idx] for idx in range(region_count)]

    def apply_threshold_settings_to_configs(self):
        """Apply threshold settings to live and analysis configs."""
        use_multi = self.use_multi_threshold_var.get()
        offsets = self.get_multi_threshold_offsets()
        weights = self.get_multi_threshold_weights()
        colors = self.get_multi_threshold_colors()

        if self.live_engine and self.live_engine.analysis_config is not None:
            config = self.live_engine.analysis_config
            config['threshold_offset'] = self.threshold_offset_var.get()
            config['use_multi_threshold'] = use_multi
            config['multi_threshold_offsets'] = offsets
            config['multi_threshold_weights'] = weights
            config['multi_threshold_colors'] = colors
            config['preview_mode'] = self.preview_mode.get()
            config['show_preview_std_region'] = self.show_preview_std_region_var.get()
            config['show_preview_frame_dots'] = self.show_preview_frame_dots_var.get()
            config['show_preview_mean_line'] = self.show_preview_mean_line_var.get()

        if self.is_running and self.current_analysis_config:
            self.current_analysis_config.threshold_offset = self.threshold_offset_var.get()
            self.current_analysis_config.use_multi_threshold = use_multi
            self.current_analysis_config.multi_threshold_offsets = offsets
            self.current_analysis_config.multi_threshold_weights = weights
            self.current_analysis_config.multi_threshold_colors = colors
        
        # Always regenerate threshold preview when thresholds change
        # Only display static preview if live preview is NOT active
        # If live preview is active, the live engine will handle display based on config updates
        if self.original_crop_frame is not None and not self.live_preview_active:
            config = {
                'use_multi_threshold': use_multi,
                'multi_threshold_offsets': offsets,
                'multi_threshold_weights': weights,
                'multi_threshold_colors': colors,
                'threshold_offset': self.threshold_offset_var.get(),
            }
            frame_to_preview = self.apply_saved_crop_to_frame(self.original_crop_frame.copy())
            if frame_to_preview is not None:
                from analysis_engine import compute_multi_thresholds, build_threshold_color_preview_filtered, threshold_frame
                gray = cv2.cvtColor(frame_to_preview, cv2.COLOR_BGR2GRAY) if frame_to_preview.ndim == 3 else frame_to_preview
                if use_multi and offsets:
                    thresholds, _ = compute_multi_thresholds(gray, offsets)
                    region_count = len(thresholds) + 1
                    preview_colors = colors[:region_count] if len(colors) >= region_count else colors + ["#000000"] * (region_count - len(colors))
                    threshold_frame_img = build_threshold_color_preview_filtered(gray, thresholds, preview_colors)
                else:
                    threshold_offset = config['threshold_offset']
                    binary, _ = threshold_frame(frame_to_preview, threshold_offset)
                    threshold_frame_img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
                self.last_threshold_frame = threshold_frame_img
                self.update_post_analysis_preview()

    def on_preview_mode_changed(self):
        """Handle preview mode changes for both live and static previews."""
        source = self.video_source_var.get()
        if source == "Live Camera" and self.live_engine and self.live_engine.analysis_config:
            # Update the live engine's preview mode
            self.live_engine.analysis_config['preview_mode'] = self.preview_mode.get()
        else:
            # Update static preview (video file or recorded frame)
            self.update_post_analysis_preview()

    def on_analysis_overlay_toggle(self):
        """Update analysis overlay settings for preview/output."""
        source = self.video_source_var.get()
        if source == "Live Camera" and self.live_engine and self.live_engine.analysis_config:
            self.live_engine.analysis_config['show_preview_std_region'] = self.show_preview_std_region_var.get()
            self.live_engine.analysis_config['show_preview_frame_dots'] = self.show_preview_frame_dots_var.get()
            self.live_engine.analysis_config['show_preview_mean_line'] = self.show_preview_mean_line_var.get()
            self.live_engine.analysis_config['apply_preview_overlay_to_output'] = self.apply_preview_overlay_to_output_var.get()
        if self.is_running and self.current_analysis_config:
            self.current_analysis_config.show_preview_std_region = self.show_preview_std_region_var.get()
            self.current_analysis_config.show_preview_frame_dots = self.show_preview_frame_dots_var.get()
            self.current_analysis_config.show_preview_mean_line = self.show_preview_mean_line_var.get()
            self.current_analysis_config.apply_preview_overlay_to_output = self.apply_preview_overlay_to_output_var.get()
        self.update_post_analysis_preview()

    def update_post_analysis_preview(self):
        self.display_controller.update_post_analysis_preview()

    # ======================================================
    # Utilities
    # ======================================================

    def labeled_header(self, parent, label, pady=(10, 0)):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w", fill="x", pady=pady)
        header_label = ctk.CTkLabel(
            row,
            text=label,
            text_color=self.TEXT_COLOR,
            font=("Segoe UI Semibold", 13),
        )
        header_label.pack(side="left")
        help_text = self.FIELD_HELP.get(label)
        if help_text:
            self.attach_tooltip(header_label, label)
        return row

    def set_graph_fit_equation_text(self, text):
        value = str(text)
        self.graph_fit_equation_var.set(value)
        if not hasattr(self, "graph_fit_equation_text"):
            return
        self.graph_fit_equation_text.configure(state="normal")
        self.graph_fit_equation_text.delete("1.0", "end")
        self.graph_fit_equation_text.insert("1.0", value)
        self.graph_fit_equation_text.configure(state="disabled")

    def labeled_entry(self, parent, label, key):
        self.labeled_header(parent, label, pady=(10, 0))
        entry = self.create_entry(parent)
        entry.insert(0, self.app_defaults.get(key, DEFAULTS.get(key, "")))
        entry.pack()
        self.attach_tooltip(entry, label)
        return entry

    def collect_startup_defaults_from_ui(self):
        value_type = self.graph_value_type_var.get().strip()
        legacy_mode = "Pixel Values" if value_type == "Pixel" else "Actual Values"
        return normalize_app_defaults({
            "threshold_offset": self.threshold_offset_var.get(),
            "use_multi_threshold": self.use_multi_threshold_var.get(),
            "multi_threshold_offsets": [var.get() for var in self.multi_threshold_offsets],
            "multi_threshold_weights": [var.get() for var in self.multi_threshold_weights],
            "multi_threshold_colors": list(self.multi_threshold_colors),
            "frame_stride": self.safe_int(self.analyze_every_entry.get()) or self.app_defaults["frame_stride"],
            "pixels_per_col": self.safe_int(self.pixel_entry.get()) or self.app_defaults["pixels_per_col"],
            "stdevs": self.safe_int(self.stdev_entry.get()) or self.app_defaults["stdevs"],
            "output_name": self.output_name_entry.get().strip() or self.app_defaults["output_name"],
            "threshold_output_name": self.threshold_output_name_var.get().strip() or self.app_defaults["threshold_output_name"],
            "output_dir": self.output_dir.get().strip(),
            "save_analysis_output": self.save_analysis_output_var.get(),
            "save_threshold_output": self.save_threshold_output_var.get(),
            "analysis_output_format": self.analysis_output_format_var.get(),
            "threshold_output_format": self.threshold_output_format_var.get(),
            "analysis_output_path": self.analysis_output_path_var.get().strip(),
            "threshold_output_path": self.threshold_output_path_var.get().strip(),
            "preview_mode": self.preview_mode.get(),
            "show_preview_std_region": self.show_preview_std_region_var.get(),
            "show_preview_frame_dots": self.show_preview_frame_dots_var.get(),
            "show_preview_mean_line": self.show_preview_mean_line_var.get(),
            "apply_preview_overlay_to_output": self.apply_preview_overlay_to_output_var.get(),
            "live_frame_limit": self.live_frame_limit.get().strip(),
            "num_thresholds": self.num_thresholds_var.get(),
            "graph_stdevs": self.graph_stdevs_var.get().strip(),
            "graph_fit_degree": self.graph_fit_degree_var.get().strip(),
            "show_best_fit": self.show_best_fit_var.get(),
            "graph_view_mode": self.graph_view_mode_var.get().strip(),
            "graph_value_type": value_type,
            "graph_title": self.graph_title_var.get().strip(),
            "graph_profile_value_mode": legacy_mode,
            "graph_column_value_mode": legacy_mode,
            "graph_distribution_kind": self.graph_distribution_kind_var.get().strip(),
            "graph_histogram_scope": self.graph_histogram_scope_var.get().strip(),
            "graph_distribution_column_px": self.graph_distribution_column_px_var.get().strip(),
            "graph_distribution_bins": self.graph_distribution_bins_var.get().strip(),
            "graph_x_axis_label": self.graph_x_axis_label.get().strip(),
            "graph_y_axis_label": self.graph_y_axis_label.get().strip(),
            "graph_x_min": self.graph_x_min_var.get().strip(),
            "graph_x_max": self.graph_x_max_var.get().strip(),
            "graph_y_min": self.graph_y_min_var.get().strip(),
            "graph_y_max": self.graph_y_max_var.get().strip(),
            "calibration_units": self.calibration_units_var.get().strip(),
        })

    def save_current_as_startup_defaults(self):
        self.app_defaults = self.collect_startup_defaults_from_ui()
        try:
            save_app_defaults(self.app_defaults)
            self.settings_status_var.set("Saved current values as startup defaults.")
        except OSError as exc:
            self.settings_status_var.set(f"Could not save startup defaults: {exc}")

    def apply_startup_defaults_now(self):
        self.app_defaults = load_app_defaults()
        self.apply_saved_defaults_to_ui()
        self.settings_status_var.set("Applied saved startup defaults to all tabs.")

    def reset_saved_startup_defaults(self):
        # Confirm with user before resetting to factory defaults
        result = messagebox.askyesno(
            "Confirm Reset",
            "Are you sure you want to reset all settings to factory defaults?\nThis will discard all your custom settings."
        )
        if not result:
            return
        
        self.app_defaults = copy.deepcopy(DEFAULTS)
        try:
            save_app_defaults(self.app_defaults)
        except OSError as exc:
            self.settings_status_var.set(f"Could not reset startup defaults: {exc}")
            return
        self.reset_defaults()
        self.settings_status_var.set("Restored built-in factory defaults.")

    def apply_saved_defaults_to_ui(self):
        self._set_entry_text(self.output_name_entry, self.app_defaults["output_name"])
        self.threshold_output_name_var.set(self.app_defaults["threshold_output_name"])
        self.output_dir.set(self.app_defaults["output_dir"])
        self.live_frame_limit.set(self.app_defaults["live_frame_limit"])
        self.save_analysis_output_var.set(self.app_defaults["save_analysis_output"])
        self.save_threshold_output_var.set(self.app_defaults["save_threshold_output"])
        self.analysis_output_format_var.set(self.app_defaults["analysis_output_format"])
        self.threshold_output_format_var.set(self.app_defaults["threshold_output_format"])
        self.analysis_output_path_var.set(self.app_defaults["analysis_output_path"])
        self.threshold_output_path_var.set(self.app_defaults["threshold_output_path"])
        self.refresh_output_controls_state()

        self.preview_mode.set(self.app_defaults["preview_mode"])
        self.show_preview_std_region_var.set(self.app_defaults["show_preview_std_region"])
        self.show_preview_frame_dots_var.set(self.app_defaults["show_preview_frame_dots"])
        self.show_preview_mean_line_var.set(self.app_defaults["show_preview_mean_line"])
        self.apply_preview_overlay_to_output_var.set(self.app_defaults["apply_preview_overlay_to_output"])
        self.threshold_offset_var.set(self.app_defaults["threshold_offset"])
        self.threshold_value_label.configure(text=str(self.app_defaults["threshold_offset"]))
        self.use_multi_threshold_var.set(self.app_defaults["use_multi_threshold"])
        self.num_thresholds_var.set(self.app_defaults["num_thresholds"])
        for idx, offset_val in enumerate(self.app_defaults["multi_threshold_offsets"]):
            self.multi_threshold_offsets[idx].set(offset_val)
            if 0 <= idx < len(self.multi_threshold_value_labels):
                self.multi_threshold_value_labels[idx].configure(text=str(offset_val))
        for idx, weight_val in enumerate(self.app_defaults["multi_threshold_weights"]):
            self.multi_threshold_weights[idx].set(weight_val)
        self.multi_threshold_colors = list(self.app_defaults["multi_threshold_colors"])
        for idx, color in enumerate(self.multi_threshold_colors):
            if idx < len(self.multi_region_color_buttons):
                self.multi_region_color_buttons[idx].configure(bg=color)
        self.update_multi_threshold_visibility()
        self.update_actual_threshold_display()
        self.apply_threshold_settings_to_configs()

        self._set_entry_text(self.analyze_every_entry, self.app_defaults["frame_stride"])
        self._set_entry_text(self.pixel_entry, self.app_defaults["pixels_per_col"])
        self._set_entry_text(self.stdev_entry, self.app_defaults["stdevs"])

        self.calibration_units_var.set(self.app_defaults["calibration_units"])

        self.graph_stdevs_var.set(self.app_defaults["graph_stdevs"])
        self.graph_fit_degree_var.set(self.app_defaults["graph_fit_degree"])
        self.show_best_fit_var.set(self.app_defaults["show_best_fit"])
        self.graph_view_mode_var.set(self.app_defaults["graph_view_mode"])
        self.graph_value_type_var.set(self.app_defaults["graph_value_type"])
        self.graph_title_var.set(self.app_defaults["graph_title"])
        self.graph_profile_value_mode_var.set("Pixel Values" if self.graph_value_type_var.get().strip() == "Pixel" else "Actual Values")
        self.graph_column_value_mode_var.set("Pixel Values" if self.graph_value_type_var.get().strip() == "Pixel" else "Actual Values")
        self.graph_distribution_kind_var.set(self.app_defaults["graph_distribution_kind"])
        self.graph_histogram_scope_var.set(self.app_defaults["graph_histogram_scope"])
        self.graph_distribution_column_px_var.set(self.app_defaults["graph_distribution_column_px"])
        self.graph_distribution_bins_var.set(self.app_defaults["graph_distribution_bins"])
        self.graph_x_axis_label.set(self.app_defaults["graph_x_axis_label"])
        self.graph_y_axis_label.set(self.app_defaults["graph_y_axis_label"])
        self.graph_x_min_var.set(self.app_defaults["graph_x_min"])
        self.graph_x_max_var.set(self.app_defaults["graph_x_max"])
        self.graph_y_min_var.set(self.app_defaults["graph_y_min"])
        self.graph_y_max_var.set(self.app_defaults["graph_y_max"])
        self.set_graph_fit_equation_text("Best fit: n/a")
        self.redraw_graph()
        self.refresh_run_state()

    def reset_basic_tab(self):
        self._set_entry_text(self.output_name_entry, self.app_defaults["output_name"])
        self.threshold_output_name_var.set(self.app_defaults["threshold_output_name"])
        self.output_dir.set(self.app_defaults["output_dir"])
        self.live_frame_limit.set(self.app_defaults["live_frame_limit"])
        self.save_analysis_output_var.set(self.app_defaults["save_analysis_output"])
        self.save_threshold_output_var.set(self.app_defaults["save_threshold_output"])
        self.analysis_output_format_var.set(self.app_defaults["analysis_output_format"])
        self.threshold_output_format_var.set(self.app_defaults["threshold_output_format"])
        self.analysis_output_path_var.set(self.app_defaults["analysis_output_path"])
        self.threshold_output_path_var.set(self.app_defaults["threshold_output_path"])
        self.update_output_path_defaults(force=False)
        self.refresh_output_controls_state()
        self.refresh_run_state()

    def reset_threshold_tab(self):
        self.preview_mode.set(self.app_defaults["preview_mode"])
        self.show_preview_std_region_var.set(self.app_defaults["show_preview_std_region"])
        self.show_preview_frame_dots_var.set(self.app_defaults["show_preview_frame_dots"])
        self.show_preview_mean_line_var.set(self.app_defaults["show_preview_mean_line"])
        self.apply_preview_overlay_to_output_var.set(self.app_defaults["apply_preview_overlay_to_output"])
        self.threshold_offset_var.set(self.app_defaults["threshold_offset"])
        self.threshold_value_label.configure(text=str(self.app_defaults["threshold_offset"]))
        self.use_multi_threshold_var.set(self.app_defaults["use_multi_threshold"])
        self.num_thresholds_var.set(self.app_defaults["num_thresholds"])
        for idx, offset_val in enumerate(self.app_defaults["multi_threshold_offsets"]):
            self.multi_threshold_offsets[idx].set(offset_val)
            # Manually update value labels since .set() doesn't trigger Scale command callback
            if 0 <= idx < len(self.multi_threshold_value_labels):
                self.multi_threshold_value_labels[idx].configure(text=str(offset_val))
        for idx, weight_val in enumerate(self.app_defaults["multi_threshold_weights"]):
            self.multi_threshold_weights[idx].set(weight_val)
        self.multi_threshold_colors = list(self.app_defaults["multi_threshold_colors"])
        for idx, color in enumerate(self.multi_threshold_colors):
            if idx < len(self.multi_region_color_buttons):
                self.multi_region_color_buttons[idx].configure(bg=color)
        self.update_multi_threshold_visibility()
        self.update_actual_threshold_display()
        self.apply_threshold_settings_to_configs()
        self.refresh_run_state()

    def reset_advanced_tab(self):
        self._set_entry_text(self.analyze_every_entry, self.app_defaults["frame_stride"])
        self._set_entry_text(self.pixel_entry, self.app_defaults["pixels_per_col"])
        self._set_entry_text(self.stdev_entry, self.app_defaults["stdevs"])
        if self.total_frames > 0:
            self.apply_range(0, self.total_frames - 1)
        self.refresh_run_state()

    def reset_crop_tab(self):
        self.reset_crop()

    def reset_calibration_tab(self):
        self.calibration_distance_var.set("")
        self.calibration_units_var.set(self.app_defaults["calibration_units"])
        self.set_calibration_zoom(1.0)
        self.clear_calibration()
        self.refresh_run_state()

    def reset_graph_tab(self):
        self.imported_profile_data = None
        self.imported_distribution_data = None
        self.imported_table_path = ""
        self.imported_table_rows = None
        self.graph_stdevs_var.set(self.app_defaults["graph_stdevs"])
        self.graph_fit_degree_var.set(self.app_defaults["graph_fit_degree"])
        self.show_best_fit_var.set(self.app_defaults["show_best_fit"])
        self.graph_view_mode_var.set(self.app_defaults["graph_view_mode"])
        self.graph_value_type_var.set(self.app_defaults["graph_value_type"])
        self.graph_title_var.set(self.app_defaults["graph_title"])
        self.graph_profile_value_mode_var.set("Pixel Values" if self.graph_value_type_var.get().strip() == "Pixel" else "Actual Values")
        self.graph_column_value_mode_var.set("Pixel Values" if self.graph_value_type_var.get().strip() == "Pixel" else "Actual Values")
        self.graph_distribution_kind_var.set(self.app_defaults["graph_distribution_kind"])
        self.graph_histogram_scope_var.set(self.app_defaults["graph_histogram_scope"])
        self.graph_distribution_column_px_var.set(self.app_defaults["graph_distribution_column_px"])
        self.graph_distribution_bins_var.set(self.app_defaults["graph_distribution_bins"])
        self.graph_x_axis_label.set(self.app_defaults["graph_x_axis_label"])
        self.graph_y_axis_label.set(self.app_defaults["graph_y_axis_label"])
        self.graph_x_min_var.set(self.app_defaults["graph_x_min"])
        self.graph_x_max_var.set(self.app_defaults["graph_x_max"])
        self.graph_y_min_var.set(self.app_defaults["graph_y_min"])
        self.graph_y_max_var.set(self.app_defaults["graph_y_max"])
        if self.graph_unit_label == "px":
            self.graph_units_label.configure(text="Units: px (uncalibrated)")
        else:
            self.graph_units_label.configure(
                text=f"Units: {self.graph_unit_label} | Scale: {self.graph_unit_scale:.6g} {self.graph_unit_label}/px"
            )
        self.set_graph_fit_equation_text("Best fit: n/a")
        self.redraw_graph()
        self.refresh_run_state()

    def attach_tooltip(self, widget, label_key):
        return

    def bind_validation_hooks(self):
        for entry in (
            self.output_name_entry,
            self.threshold_output_name_entry,
            self.analysis_output_entry,
            self.threshold_output_entry,
            self.analyze_every_entry,
            self.pixel_entry,
            self.stdev_entry,
            self.graph_stdev_entry,
            self.graph_fit_degree_entry,
            self.graph_distribution_bins_entry,
            self.calibration_distance_entry,
            self.start_entry,
            self.end_entry,
        ):
            entry.bind("<KeyRelease>", self.on_user_input_changed)
            entry.bind("<FocusOut>", self.on_user_input_changed)
        self.start_entry.bind("<Return>", self.on_range_entry_commit)
        self.end_entry.bind("<Return>", self.on_range_entry_commit)
        self.graph_distribution_column_entry.bind("<Return>", lambda _event: self.redraw_graph())
        self.graph_distribution_column_entry.bind("<FocusOut>", lambda _event: self.redraw_graph())
        self.output_dir.trace_add("write", lambda *_: self.refresh_run_state())
        self.threshold_output_name_var.trace_add("write", lambda *_: self.update_output_path_defaults(force=False))
        self.analysis_output_path_var.trace_add("write", lambda *_: self.refresh_run_state())
        self.threshold_output_path_var.trace_add("write", lambda *_: self.refresh_run_state())
        self.save_analysis_output_var.trace_add("write", lambda *_: self.refresh_output_controls_state())
        self.save_threshold_output_var.trace_add("write", lambda *_: self.refresh_output_controls_state())
        self.calibration_units_var.trace_add("write", lambda *_: self.redraw_graph())

    def bind_keyboard_shortcuts(self):
        self.root.bind_all("<Control-Tab>", self.on_cycle_tabs_shortcut)
        self.root.bind_all("<Control-r>", self.on_run_shortcut)
        self.root.bind_all("<Control-R>", self.on_run_shortcut)
        self.root.bind_all("<Control-s>", self.on_stop_shortcut)
        self.root.bind_all("<Control-S>", self.on_stop_shortcut)

    def on_cycle_tabs_shortcut(self, _event=None):
        tabs = list(self.notebook.tabs())
        if not tabs:
            return "break"
        current_tab = self.notebook.select()
        if current_tab not in tabs:
            self.notebook.select(tabs[0])
            return "break"
        next_index = (tabs.index(current_tab) + 1) % len(tabs)
        self.notebook.select(tabs[next_index])
        return "break"

    def on_run_shortcut(self, _event=None):
        self.start_thread()
        return "break"

    def on_stop_shortcut(self, _event=None):
        self.stop_analysis()
        return "break"

    def on_user_input_changed(self, _event=None):
        self.update_output_path_defaults(force=False)
        self.on_range_entry_commit()
        self.refresh_run_state()
        self.redraw_graph()

    def safe_int(self, value):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    def validate_inputs(self, for_run=False):
        errors = []
        source = self.video_source_var.get()
        entries = [
            self.output_name_entry,
            self.threshold_output_name_entry,
            self.analysis_output_entry,
            self.threshold_output_entry,
            self.analyze_every_entry,
            self.pixel_entry,
            self.stdev_entry,
            self.start_entry,
            self.end_entry,
        ]
        for entry in entries:
            self.set_entry_validation_state(entry, False)

        # Video validation depends on source
        if source == "Video File" and not self.video_path.get():
            errors.append("Select a video file.")

        frame_stride = self.safe_int(self.analyze_every_entry.get())
        if frame_stride is None or frame_stride <= 0:
            errors.append("Analyze every N frames must be an integer greater than 0.")
            self.set_entry_validation_state(self.analyze_every_entry, True)

        pixels_per_col = self.safe_int(self.pixel_entry.get())
        if pixels_per_col is None or pixels_per_col <= 0:
            errors.append("Pixels per Column must be an integer greater than 0.")
            self.set_entry_validation_state(self.pixel_entry, True)

        stdevs = self.safe_int(self.stdev_entry.get())
        if stdevs is None or stdevs < 0:
            errors.append("Standard Deviations must be an integer >= 0.")
            self.set_entry_validation_state(self.stdev_entry, True)

        output_targets = []
        if self.save_analysis_output_var.get():
            output_targets.append(("Analysis", self.analysis_output_path_var.get().strip(), self.analysis_output_entry, self.analysis_output_format_var.get()))
        if self.save_threshold_output_var.get():
            output_targets.append(("Threshold", self.threshold_output_path_var.get().strip(), self.threshold_output_entry, self.threshold_output_format_var.get()))

        if self.save_analysis_output_var.get() and not self.output_name_entry.get().strip():
            errors.append("Analysis file name is required when saving analysis output.")
            self.set_entry_validation_state(self.output_name_entry, True)
        if self.save_threshold_output_var.get() and not self.threshold_output_name_var.get().strip():
            errors.append("Threshold file name is required when saving threshold output.")
            self.set_entry_validation_state(self.threshold_output_name_entry, True)

        for label, path, entry, format_label in output_targets:
            if not path:
                errors.append(f"{label} output path is required when saving is enabled.")
                self.set_entry_validation_state(entry, True)
                continue
            normalized_path = self.ensure_output_path_extension(path, format_label)
            if normalized_path != path:
                if label == "Analysis":
                    self.analysis_output_path_var.set(normalized_path)
                else:
                    self.threshold_output_path_var.set(normalized_path)
            ext = os.path.splitext(normalized_path)[1].lower()
            if ext not in OUTPUT_FORMATS.values():
                errors.append(f"{label} output format is not supported: {ext or '(no extension)'}.")
                self.set_entry_validation_state(entry, True)

        if len(output_targets) == 2:
            analysis_path = self.analysis_output_path_var.get().strip()
            threshold_path = self.threshold_output_path_var.get().strip()
            if analysis_path and threshold_path and os.path.normcase(os.path.abspath(analysis_path)) == os.path.normcase(os.path.abspath(threshold_path)):
                errors.append("Analysis and threshold outputs must use different file paths.")
                self.set_entry_validation_state(self.analysis_output_entry, True)
                self.set_entry_validation_state(self.threshold_output_entry, True)

        # Frame range validation only for video files
        if source == "Video File" and self.total_frames > 0:
            start = self.safe_int(self.start_frame_text.get())
            end = self.safe_int(self.end_frame_text.get())
            if start is None:
                errors.append("Start frame must be an integer.")
                self.set_entry_validation_state(self.start_entry, True)
            if end is None:
                errors.append("End frame must be an integer.")
                self.set_entry_validation_state(self.end_entry, True)
            if start is not None and end is not None:
                if start < 0 or end < 0 or start >= self.total_frames or end >= self.total_frames:
                    errors.append(f"Frame range must be between 0 and {self.total_frames - 1}.")
                    self.set_entry_validation_state(self.start_entry, True)
                    self.set_entry_validation_state(self.end_entry, True)
                elif start > end:
                    errors.append("Start frame cannot be greater than end frame.")
                    self.set_entry_validation_state(self.start_entry, True)
                    self.set_entry_validation_state(self.end_entry, True)

        # Crop validation only for video files
        if source == "Video File" and (self.crop_right <= self.crop_left or self.crop_bottom <= self.crop_top):
            errors.append("Crop area is invalid. Adjust crop in the Crop tab and press Save Crop.")

        if for_run:
            for label, path, entry, _format_label in output_targets:
                if not path:
                    continue
                output_dir = os.path.dirname(path) or "."
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    write_probe = os.path.join(output_dir, ".write_test.tmp")
                    with open(write_probe, "w", encoding="utf-8") as tmp:
                        tmp.write("ok")
                    os.remove(write_probe)
                except Exception as exc:
                    errors.append(f"Cannot write {label.lower()} output to {output_dir}: {exc}")
                    self.set_entry_validation_state(entry, True)

        self.validation_message.set("\n".join(errors))
        return len(errors) == 0, errors

    def refresh_run_state(self):
        if self.is_running:
            self.run_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.set_status("Running", "running")
            return
        
        # Live preview active but not analyzing - Run button should be enabled
        if self.live_preview_active:
            self.run_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.set_status("Preview ready", "ready")
            return
        
        is_valid, _ = self.validate_inputs(for_run=False)
        self.run_button.configure(state="normal" if is_valid else "disabled")
        # Enable stop button if there are validation errors to allow clearing them
        has_validation_errors = len(self.validation_message.get()) > 0
        self.stop_button.configure(state="normal" if has_validation_errors else "disabled")
        if self.analysis_error is not None:
            self.set_status("Error", "error")
        elif self.analysis_was_stopped:
            self.set_status("Stopped", "warning")
        elif is_valid:
            self.set_status("Ready", "ready")
        else:
            self.set_status("Needs Input", "idle")

    def reset_runtime_state(self):
        self.last_analysis_frame = None
        self.last_raw_analysis_frame = None
        self.last_threshold_frame = None
        self.last_centerline_array = None
        self.last_running_avg = None
        self.last_running_std = None
        self.last_raw_frame = None
        self.final_mean_profile = None
        self.final_std_profile = None
        self.final_centerline_samples = None
        self.imported_profile_data = None
        self.imported_distribution_data = None
        self.imported_table_path = ""
        self.imported_table_rows = None
        self.set_graph_fit_equation_text("Best fit: n/a")
        self.progress["maximum"] = 1
        self.progress["value"] = 0
        self.frame_counter = 0
        self.validation_message.set("")
        self.time_label.configure(text="0.00s | 0/0")
        self.redraw_graph()

    def update_crop_size_label(self, preview_rect=None):
        if preview_rect is not None and self.current_scale > 0:
            x1, y1, x2, y2 = self.clamp_crop_rect(preview_rect)
            width = max(1, int((x2 - x1) / self.current_scale))
            height = max(1, int((y2 - y1) / self.current_scale))
            self.crop_size_text.set(f"Crop: {width} x {height} px (preview)")
            return
        width = max(0, self.crop_right - self.crop_left)
        height = max(0, self.crop_bottom - self.crop_top)
        if width > 0 and height > 0:
            self.crop_size_text.set(f"Crop: {width} x {height} px")
        else:
            self.crop_size_text.set("Crop: full frame")

    def set_processing_controls(self, running):
        self.status_controller.set_processing_controls(running)

    def set_status(self, text, tone):
        self.status_controller.set_status(text, tone)

    def select_output_dir(self):
        self.status_controller.select_output_dir()

    def open_documentation_page(self):
        self.documentation_controller.open_documentation_page()

    def load_documentation_text(self):
        return self.documentation_controller.load_documentation_text()

    def save_documentation_text(self):
        self.documentation_controller.save_documentation_text()

    def close_documentation_page(self):
        self.documentation_controller.close_documentation_page()

    def build_config(self):
        analysis_path = None
        threshold_path = None
        if self.save_analysis_output_var.get():
            analysis_path = self.ensure_output_path_extension(
                self.analysis_output_path_var.get(),
                self.analysis_output_format_var.get(),
            )
        if self.save_threshold_output_var.get():
            threshold_path = self.ensure_output_path_extension(
                self.threshold_output_path_var.get(),
                self.threshold_output_format_var.get(),
            )

        start = self.start_frame_var.get()
        end = self.end_frame_var.get()
        frame_stride = max(1, self.safe_int(self.analyze_every_entry.get()) or 1)
        num_frames = max(1, ((end - start) // frame_stride) + 1)

        return JetAnalysisConfig(
            crop_left=self.crop_left,
            crop_right=self.crop_right,
            crop_top=self.crop_top,
            crop_bottom=self.crop_bottom,
            num_frames=num_frames,
            threshold_offset=self.threshold_offset_var.get(),
            frame_stride=frame_stride,
            pixels_per_col=int(self.pixel_entry.get()),
            avg_line_thickness=2,
            stdevs=int(self.stdev_entry.get()),
            show_confidence=True,
            confidence_mode="band",
            show_progress=False,
            input_video_path=self.video_path.get(),
            output_analysis_path=analysis_path,
            output_thresh_path=threshold_path,
            use_multi_threshold=self.use_multi_threshold_var.get(),
            multi_threshold_offsets=self.get_multi_threshold_offsets(),
            multi_threshold_weights=self.get_multi_threshold_weights(),
            multi_threshold_colors=self.get_multi_threshold_colors(),
            show_preview_std_region=self.show_preview_std_region_var.get(),
            show_preview_frame_dots=self.show_preview_frame_dots_var.get(),
            show_preview_mean_line=self.show_preview_mean_line_var.get(),
            apply_preview_overlay_to_output=self.apply_preview_overlay_to_output_var.get(),
            start_frame=start,
            end_frame=end
        )

    def collect_project_state(self):
        return self.project_state_controller.collect_project_state()

    def save_project(self):
        self.project_state_controller.save_project()

    def save_project_to_path(self, file_path, update_current_project_path=True):
        return self.project_state_controller.save_project_to_path(
            file_path,
            update_current_project_path=update_current_project_path,
        )

    def _set_entry_text(self, entry, value):
        entry.delete(0, tk.END)
        entry.insert(0, str(value))

    def apply_project_state(self, state):
        self.project_state_controller.apply_project_state(state)

    def load_project(self):
        self.project_state_controller.load_project()

    def build_export_package_summary(self, package_dir, included_files):
        source_mode = self.video_source_var.get().strip() or "Video File"
        if source_mode == "Live Camera":
            source_detail = self.camera_index_var.get().strip() or "Live Camera"
        else:
            source_detail = self.video_path.get().strip() or "No video selected"

        crop_width = max(0, int(self.crop_right) - int(self.crop_left))
        crop_height = max(0, int(self.crop_bottom) - int(self.crop_top))
        lines = [
            "Jet Analyzer Export Package",
            f"Created: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Package directory: {package_dir}",
            "",
            "Source",
            f"Mode: {source_mode}",
            f"Input: {source_detail}",
            "",
            "Run settings",
            f"Frame range: {self.start_frame_var.get()} to {self.end_frame_var.get()}",
            f"Analyze every: {self.analyze_every_entry.get().strip()} frame(s)",
            f"Crop: left={self.crop_left}, top={self.crop_top}, right={self.crop_right}, bottom={self.crop_bottom} ({crop_width} x {crop_height} px)",
            f"Preview mode: {self.preview_mode.get().strip()}",
            f"Threshold offset: {self.threshold_offset_var.get()}",
            f"Pixels per column: {self.pixel_entry.get().strip()}",
            f"Standard deviations: {self.stdev_entry.get().strip()}",
            f"Graph view: {self.graph_view_mode_var.get().strip()}",
            f"Graph units: {self.graph_unit_label}",
            f"Calibration: {self.calibration_status_var.get().strip()}",
            f"Nozzle origin: {self.nozzle_status_var.get().strip()}",
            "",
            "Included files",
        ]

        for label, path in included_files:
            lines.append(f"{label}: {os.path.basename(path)}")

        return "\n".join(lines) + "\n"

    def get_export_package_video_sources(self):
        video_sources = []
        output_configs = [
            (
                "Analysis video",
                self.save_analysis_output_var.get(),
                self.analysis_output_path_var.get(),
                self.analysis_output_format_var.get(),
            ),
            (
                "Threshold video",
                self.save_threshold_output_var.get(),
                self.threshold_output_path_var.get(),
                self.threshold_output_format_var.get(),
            ),
        ]
        for label, is_enabled, raw_path, format_label in output_configs:
            if not is_enabled:
                continue
            source_path = self.ensure_output_path_extension(raw_path, format_label)
            if source_path and os.path.isfile(source_path):
                video_sources.append((label, source_path))
        return video_sources

    def export_package(self):
        if self.is_running:
            return

        if self.render_graph_image() is None or self.build_graph_export_rows() is None:
            messagebox.showinfo("No analysis results", "Run analysis first to export a results package.")
            return

        output_dir = self.get_default_output_dir()
        base_name = self.output_name_entry.get().strip() or self.app_defaults["output_name"]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        package_dir = os.path.join(output_dir, f"{base_name}_export_package_{timestamp}")
        suffix = 2
        while os.path.exists(package_dir):
            package_dir = os.path.join(output_dir, f"{base_name}_export_package_{timestamp}_{suffix}")
            suffix += 1

        graph_image_path = os.path.join(package_dir, f"{base_name}_graph.png")
        graph_csv_path = os.path.join(package_dir, f"{base_name}_graph_data.csv")
        project_json_path = os.path.join(package_dir, f"{base_name}_project.json")
        summary_path = os.path.join(package_dir, f"{base_name}_summary.txt")
        included_files = [
            ("Graph image", graph_image_path),
            ("Graph data", graph_csv_path),
            ("Project settings", project_json_path),
            ("Summary", summary_path),
        ]

        try:
            os.makedirs(package_dir, exist_ok=False)
            self.graph_controller.save_graph_image_to_path(graph_image_path)
            self.graph_controller.save_graph_data_csv_to_path(graph_csv_path)
            self.save_project_to_path(project_json_path, update_current_project_path=False)
            for label, source_path in self.get_export_package_video_sources():
                destination_path = os.path.join(package_dir, os.path.basename(source_path))
                root, ext = os.path.splitext(destination_path)
                suffix = 2
                while os.path.exists(destination_path):
                    destination_path = f"{root}_{suffix}{ext}"
                    suffix += 1
                shutil.copy2(source_path, destination_path)
                included_files.append((label, destination_path))
            summary_text = self.build_export_package_summary(package_dir, included_files)
            with open(summary_path, "w", encoding="utf-8") as handle:
                handle.write(summary_text)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Export failed", f"Could not create export package:\n{exc}")
            return

        messagebox.showinfo(
            "Export package saved",
            f"Saved export package to:\n{package_dir}",
        )

    def try_auto_load_startup_project(self):
        self.project_state_controller.try_auto_load_startup_project()

    def reset_defaults(self):
        self.reset_basic_tab()
        self.reset_threshold_tab()
        self.reset_advanced_tab()
        self.reset_graph_tab()
        self.reset_calibration_tab()

        self.project_path = ""
        self.crop_mode = False
        self.drag_start = None
        self.resize_corner = None
        self.crop_rect = None
        self.canvas.delete("crop_box")
        self.save_crop_button.configure(state="disabled")

        if self.total_frames > 0:
            self.apply_range(0, self.total_frames - 1)
            self.current_preview_frame_index = 0
            if self.original_crop_frame is not None:
                h, w = self.original_crop_frame.shape[:2]
                self.crop_left = 0
                self.crop_top = 0
                self.crop_right = w
                self.crop_bottom = h
                self.update_crop_size_label()
            self.preview_frame_at(0)
        else:
            self.crop_left = 0
            self.crop_top = 0
            self.crop_right = 0
            self.crop_bottom = 0
            self.crop_size_text.set("Crop: full frame")

        self.redraw_graph()
        self.refresh_run_state()

    def reset_advanced_only(self):
        self.reset_advanced_tab()

if __name__ == "__main__":
    root = ctk.CTk()
    app = JetAnalysisGUI(root)
    root.mainloop()




