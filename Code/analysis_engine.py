"""Core video-processing pipeline for jet centerline analysis.

Defines processing configuration and frame-by-frame analysis functions.
"""

import os
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional


OUTPUT_CODEC_CANDIDATES = {
    ".avi": ["MJPG", "XVID", "DIVX"],
    ".mp4": ["mp4v", "avc1", "H264"],
    ".m4v": ["mp4v", "avc1", "H264"],
    ".mov": ["mp4v", "MJPG", "avc1"],
    ".mkv": ["XVID", "MJPG", "mp4v"],
    ".wmv": ["WMV2", "WMV1", "XVID"],
    ".mpg": ["PIM1", "XVID", "MJPG"],
    ".mpeg": ["PIM1", "XVID", "MJPG"],
}


# ==========================================
# -------- CONFIG OBJECT -------------------
# ==========================================

@dataclass
class JetAnalysisConfig:
    crop_left: int
    crop_right: int
    crop_top: int
    crop_bottom: int

    num_frames: int
    threshold_offset: int
    pixels_per_col: int
    avg_line_thickness: int
    stdevs: int
    show_confidence: bool
    confidence_mode: str
    show_progress: bool

    input_video_path: str
    output_analysis_path: Optional[str]
    output_thresh_path: Optional[str] = None

    # Multi-threshold support
    use_multi_threshold: bool = False
    multi_threshold_offsets: Optional[list] = None
    multi_threshold_weights: Optional[list] = None
    multi_threshold_colors: Optional[list] = None

    # Frame range support
    start_frame: int = 0
    end_frame: int = None


# ==========================================
# -------- FRAME PROCESSING ----------------
# ==========================================


def threshold_frame(frame, threshold_offset):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    otsu_thresh, _ = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    adjusted_thresh = otsu_thresh + threshold_offset
    # Ensure final threshold is at least 1 (never 0 or negative)
    adjusted_thresh = max(1, adjusted_thresh)
    _, binary = cv2.threshold(gray, adjusted_thresh, 255, cv2.THRESH_BINARY)

    return binary, int(adjusted_thresh)


def compute_multi_thresholds(gray, offsets):
    """
    Compute multiple threshold values from Otsu threshold and offsets.
    
    Args:
        gray: Grayscale image
        offsets: List of threshold offsets [offset1, offset2, ...]
    
    Returns:
        (thresholds, otsu_thresh) - sorted threshold values and the Otsu baseline
    """
    otsu_thresh, _ = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    
    # Calculate actual thresholds
    thresholds = []
    for offset in offsets:
        adjusted = otsu_thresh + offset
        adjusted = max(1, adjusted)
        thresholds.append(int(adjusted))
    
    # Sort thresholds for digitize
    thresholds = sorted(thresholds)
    
    return thresholds, int(otsu_thresh)


def hex_to_bgr(hex_color):
    """Convert hex color string to BGR tuple for OpenCV."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (b, g, r)  # BGR for OpenCV


def build_threshold_color_preview_filtered(gray, thresholds, colors):
    """
    Build colored threshold preview with regions indicated by different colors.
    
    Args:
        gray: Grayscale image
        thresholds: Sorted list of threshold values
        colors: List of hex color strings for each region
    
    Returns:
        BGR image with regions colored
    """
    if not thresholds:
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    
    # Use np.digitize to assign each pixel to a region
    # digitize returns bin indices: 0 for pixels < thresholds[0], 1 for pixels < thresholds[1], etc.
    regions = np.digitize(gray, thresholds, right=False)
    
    # Convert hex colors to BGR tuples
    color_table = np.array([hex_to_bgr(color) for color in colors], dtype=np.uint8)
    
    # Clip color_table to match the number of regions
    if np.max(regions) >= len(color_table):
        # Extend color_table if needed
        color_table = np.vstack([color_table, np.tile(color_table[-1], (np.max(regions) - len(color_table) + 1, 1))])
    else:
        color_table = color_table[:np.max(regions) + 1]
    
    # Apply colors to create the preview
    colorized = color_table[regions]
    return colorized


def build_threshold_output_frame(frame, binary, use_multi_threshold=False,
                                 multi_threshold_offsets=None,
                                 multi_threshold_colors=None):
    """Build threshold output frame as either binary BGR or multi-threshold color preview."""
    if use_multi_threshold:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        offsets = multi_threshold_offsets or [15, 25, 35, 45, 55]
        colors = multi_threshold_colors or ["#000000", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd", "#1f77b4"]
        thresholds, _ = compute_multi_thresholds(gray, offsets)
        region_count = len(thresholds) + 1
        preview_colors = colors[:region_count] if len(colors) >= region_count else colors + ["#000000"] * (region_count - len(colors))
        return build_threshold_color_preview_filtered(gray, thresholds, preview_colors)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def create_video_writer(path, fps, frame_size):
    if not path:
        return None

    output_dir = os.path.dirname(path) or "."
    os.makedirs(output_dir, exist_ok=True)

    ext = os.path.splitext(path)[1].lower()
    codec_candidates = OUTPUT_CODEC_CANDIDATES.get(ext, OUTPUT_CODEC_CANDIDATES[".avi"])
    last_error = None

    for codec in codec_candidates:
        writer = cv2.VideoWriter(
            path,
            cv2.VideoWriter_fourcc(*codec),
            fps,
            frame_size
        )
        if writer.isOpened():
            return writer
        writer.release()
        last_error = codec

    raise IOError(
        f"Could not open output video file for writing: {path}. Tried codecs: {', '.join(codec_candidates)}"
    )


def extract_centerline(binary, pixels_per_col):
    height, width = binary.shape
    centerline = []

    for x in range(width):
        ys = np.where(binary[:, x] > 0)[0]
        if len(ys) > pixels_per_col:
            centerline.append(int(np.mean(ys)))
        else:
            centerline.append(np.nan)

    return centerline


# ==========================================
# -------- RUNNING STATS -------------------
# ==========================================

class RunningStats:
    """
    Incremental per-column mean and std (population variance, ddof=0).
    """

    def __init__(self, width):
        self.mean = np.zeros(width, dtype=np.float64)
        self.M2 = np.zeros(width, dtype=np.float64)
        self.count = np.zeros(width, dtype=np.int32)

    def update(self, centerline_array):
        valid = ~np.isnan(centerline_array)

        delta = np.zeros_like(centerline_array)
        delta[valid] = centerline_array[valid] - self.mean[valid]

        self.count[valid] += 1
        self.mean[valid] += delta[valid] / self.count[valid]

        delta2 = np.zeros_like(centerline_array)
        delta2[valid] = centerline_array[valid] - self.mean[valid]

        self.M2[valid] += delta[valid] * delta2[valid]

    def get_mean_std(self):
        width = len(self.mean)
        running_avg = np.full(width, np.nan)
        running_std = np.full(width, np.nan)

        valid_mean = self.count > 0
        valid_std = self.count > 1

        running_avg[valid_mean] = self.mean[valid_mean]
        running_std[valid_std] = np.sqrt(
            self.M2[valid_std] / self.count[valid_std]
        )

        return running_avg, running_std


# ==========================================
# -------- DRAW FUNCTIONS ------------------
# ==========================================


def draw_instantaneous_centerline(frame, centerline):
    for x, y in enumerate(centerline):
        if not np.isnan(y):
            cv2.circle(frame, (x, int(y)), 1, (0, 0, 255), -1)
    return frame


def draw_confidence_region(frame, running_avg, running_std,
                           stdevs, confidence_mode):

    height = frame.shape[0]

    upper = running_avg + stdevs * running_std
    lower = running_avg - stdevs * running_std

    valid_mask = (~np.isnan(running_avg)) & (~np.isnan(running_std))
    valid_indices = np.where(valid_mask)[0]

    if len(valid_indices) < 10:
        return frame

    upper_pts = []
    lower_pts = []

    for x_idx in valid_indices:
        uy = int(np.clip(upper[x_idx], 0, height - 1))
        ly = int(np.clip(lower[x_idx], 0, height - 1))
        upper_pts.append((x_idx, uy))
        lower_pts.append((x_idx, ly))

    if confidence_mode == "band":
        band_overlay = frame.copy()
        polygon = np.array(upper_pts + lower_pts[::-1], dtype=np.int32)
        cv2.fillPoly(band_overlay, [polygon], (0, 255, 0))
        frame = cv2.addWeighted(band_overlay, 0.25, frame, 0.75, 0)

    elif confidence_mode == "lines":
        cv2.polylines(frame,
                      [np.array(upper_pts)],
                      False, (0, 255, 0), 1)
        cv2.polylines(frame,
                      [np.array(lower_pts)],
                      False, (0, 255, 0), 1)

    return frame


def draw_mean_centerline(frame, running_avg, thickness):
    mean_pts = []
    for x, y in enumerate(running_avg):
        if not np.isnan(y):
            mean_pts.append((x, int(y)))

    if len(mean_pts) > 1:
        cv2.polylines(
            frame,
            [np.array(mean_pts)],
            False,
            (200, 150, 0),
            thickness
        )
    return frame


# ==========================================
# -------- MAIN PIPELINE -------------------
# ==========================================


def process_video(config: JetAnalysisConfig,
                  preview_callback=None,
                  stop_event=None):

    cap = cv2.VideoCapture(config.input_video_path)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    start = max(0, config.start_frame)
    end = config.end_frame if config.end_frame is not None else total_frames - 1
    end = min(end, total_frames - 1)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start)

    ret, frame = cap.read()
    if not ret:
        raise Exception("Could not read video.")

    cropped_width = config.crop_right - config.crop_left
    cropped_height = config.crop_bottom - config.crop_top
    if cropped_width <= 0 or cropped_height <= 0:
        raise ValueError(
            f"Invalid crop bounds produced {cropped_width}x{cropped_height} output."
        )

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 30.0

    out_analysis = None
    out_threshold = None
    try:
        if config.output_analysis_path:
            out_analysis = create_video_writer(
                config.output_analysis_path,
                fps,
                (cropped_width, cropped_height)
            )
        if config.output_thresh_path:
            out_threshold = create_video_writer(
                config.output_thresh_path,
                fps,
                (cropped_width, cropped_height)
            )
    except Exception:
        cap.release()
        if out_analysis:
            out_analysis.release()
        if out_threshold:
            out_threshold.release()
        raise

    stats = RunningStats(cropped_width)
    threshold_history = []
    centerline_samples = []

    frame_index = start
    processed = 0

    while frame_index <= end and processed < config.num_frames:

        if stop_event and stop_event.is_set():
            break

        ret, frame = cap.read()
        if not ret:
            break

        frame_index += 1
        processed += 1

        frame = frame[
            config.crop_top:config.crop_bottom,
            config.crop_left:config.crop_right
        ]

        binary, adjusted_thresh = threshold_frame(frame, config.threshold_offset)
        threshold_history.append(adjusted_thresh)

        centerline = extract_centerline(binary, config.pixels_per_col)
        centerline_array = np.array(centerline, dtype=np.float64)
        centerline_samples.append(centerline_array.copy())

        stats.update(centerline_array)
        running_avg, running_std = stats.get_mean_std()

        # Save raw frame before drawing overlays (for threshold preview)
        raw_frame = frame.copy()

        frame = draw_instantaneous_centerline(frame, centerline_array)

        if config.show_confidence:
            frame = draw_confidence_region(
                frame,
                running_avg,
                running_std,
                config.stdevs,
                config.confidence_mode
            )

        frame = draw_mean_centerline(
            frame,
            running_avg,
            config.avg_line_thickness
        )

        binary_bgr = build_threshold_output_frame(
            raw_frame,
            binary,
            use_multi_threshold=config.use_multi_threshold,
            multi_threshold_offsets=config.multi_threshold_offsets,
            multi_threshold_colors=config.multi_threshold_colors,
        )

        if out_analysis:
            out_analysis.write(frame)
        if out_threshold:
            out_threshold.write(binary_bgr)

        if preview_callback:
            preview_callback(processed, frame, binary_bgr, adjusted_thresh, raw_frame)

    cap.release()
    if out_analysis:
        out_analysis.release()
    if out_threshold:
        out_threshold.release()

    final_mean, final_std = stats.get_mean_std()
    sample_matrix = np.vstack(centerline_samples) if centerline_samples else None

    return final_mean, final_std, threshold_history, sample_matrix


# ==========================================
# -------- CLI ENTRY -----------------------
# ==========================================

if __name__ == "__main__":

    config = JetAnalysisConfig(
        crop_left=0,
        crop_right=900,
        crop_top=0,
        crop_bottom=600,
        num_frames=300,
        threshold_offset=15,
        pixels_per_col=3,
        avg_line_thickness=2,
        stdevs=2,
        show_confidence=True,
        confidence_mode="band",
        show_progress=False,
        input_video_path="slo_mo.mp4",
        output_analysis_path="slow_results/slow_analysis.avi"
    )

    mean, std, thresh_hist, _sample_matrix = process_video(config)

    print("Processing complete.")
