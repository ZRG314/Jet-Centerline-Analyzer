"""Controller for project JSON save/load and startup auto-load behavior."""

import json
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox


class ProjectStateController:
    def __init__(self, app, startup_project_filenames):
        self.app = app
        self.startup_project_filenames = startup_project_filenames

    def _set_entry_text(self, entry, value):
        entry.delete(0, tk.END)
        entry.insert(0, str(value))

    def _to_portable_path(self, path_value, project_file_path):
        path_text = str(path_value or "").strip()
        if not path_text:
            return ""
        if not project_file_path:
            return os.path.normpath(path_text)

        base_dir = os.path.dirname(os.path.abspath(project_file_path))
        normalized = os.path.normpath(path_text)
        if not os.path.isabs(normalized):
            return normalized

        try:
            relative = os.path.relpath(normalized, base_dir)
            return os.path.normpath(relative)
        except ValueError:
            return normalized

    def _resolve_project_path(self, path_value, project_file_path):
        path_text = str(path_value or "").strip()
        if not path_text:
            return ""

        normalized = os.path.normpath(path_text)
        if os.path.isabs(normalized) or not project_file_path:
            return normalized

        base_dir = os.path.dirname(os.path.abspath(project_file_path))
        return os.path.normpath(os.path.join(base_dir, normalized))

    def collect_project_state(self, project_file_path=None):
        app = self.app
        return {
            "project_version": 1,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "video_path": self._to_portable_path(app.video_path.get().strip(), project_file_path),
            "output_dir": self._to_portable_path(app.output_dir.get().strip(), project_file_path),
            "output_name": app.output_name_entry.get().strip(),
            "threshold_output_name": app.threshold_output_name_var.get().strip(),
            "save_analysis_output": bool(app.save_analysis_output_var.get()),
            "analysis_output_format": app.analysis_output_format_var.get().strip(),
            "analysis_output_path": self._to_portable_path(app.analysis_output_path_var.get().strip(), project_file_path),
            "save_threshold_output": bool(app.save_threshold_output_var.get()),
            "threshold_output_format": app.threshold_output_format_var.get().strip(),
            "threshold_output_path": self._to_portable_path(app.threshold_output_path_var.get().strip(), project_file_path),
            "threshold_offset": str(app.threshold_offset_var.get()).strip(),
            "pixels_per_col": app.pixel_entry.get().strip(),
            "stdevs": app.stdev_entry.get().strip(),
            "preview_mode": app.preview_mode.get().strip(),
            "start_frame": int(app.start_frame_var.get()),
            "end_frame": int(app.end_frame_var.get()),
            "current_preview_frame_index": int(app.current_preview_frame_index),
            "crop_left": int(app.crop_left),
            "crop_top": int(app.crop_top),
            "crop_right": int(app.crop_right),
            "crop_bottom": int(app.crop_bottom),
            "graph_stdevs": str(app.graph_stdevs_var.get()).strip(),
            "graph_fit_degree": str(app.graph_fit_degree_var.get()).strip(),
            "show_best_fit": bool(app.show_best_fit_var.get()),
            "graph_x_axis_label": app.graph_x_axis_label.get().strip(),
            "graph_y_axis_label": app.graph_y_axis_label.get().strip(),
            "graph_x_min": str(app.graph_x_min_var.get()).strip(),
            "graph_x_max": str(app.graph_x_max_var.get()).strip(),
            "graph_y_min": str(app.graph_y_min_var.get()).strip(),
            "graph_y_max": str(app.graph_y_max_var.get()).strip(),
            "graph_unit_label": str(app.graph_unit_label).strip(),
            "graph_unit_scale": float(app.graph_unit_scale),
            "calibration_distance": str(app.calibration_distance_var.get()).strip(),
            "calibration_units": str(app.calibration_units_var.get()).strip(),
            "calibration_line_img": list(app.calibration_line_img) if app.calibration_line_img is not None else None,
            "nozzle_origin_img": list(app.nozzle_origin_img) if app.nozzle_origin_img is not None else None,
        }

    def save_project(self):
        app = self.app
        if app.is_running:
            return
        default_name = f"{app.output_name_entry.get().strip() or 'analysis_output'}_project.json"
        initial_dir = app.output_dir.get().strip() or os.path.dirname(__file__)
        file_path = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".json",
            filetypes=[("Project JSON", "*.json")],
            initialfile=default_name,
            initialdir=initial_dir,
        )
        if not file_path:
            return
        state = self.collect_project_state(file_path)
        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2)
            app.project_path = file_path
            messagebox.showinfo("Project saved", f"Saved project to:\n{file_path}")
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save project:\n{exc}")

    def apply_project_state(self, state, project_file_path=None):
        app = self.app
        if not isinstance(state, dict):
            raise ValueError("Invalid project file format.")

        video_path = self._resolve_project_path(state.get("video_path", ""), project_file_path)
        if video_path and os.path.isfile(video_path):
            app.load_video(video_path)
        elif video_path:
            messagebox.showwarning(
                "Video not found",
                f"Saved video path does not exist:\n{video_path}\n\nOther settings will still be loaded.",
            )
            app.video_path.set(video_path)
            app.video_label.config(text=os.path.basename(video_path) or "No video selected")

        app.output_dir.set(self._resolve_project_path(state.get("output_dir", app.output_dir.get()), project_file_path))
        self._set_entry_text(app.output_name_entry, state.get("output_name", app.output_name_entry.get()))
        app.threshold_output_name_var.set(str(state.get("threshold_output_name", app.threshold_output_name_var.get())).strip())
        app.save_analysis_output_var.set(bool(state.get("save_analysis_output", app.save_analysis_output_var.get())))
        analysis_format = str(state.get("analysis_output_format", app.analysis_output_format_var.get())).strip()
        if analysis_format in app.analysis_output_format_combo.cget("values"):
            app.analysis_output_format_var.set(analysis_format)
        app.analysis_output_path_var.set(self._resolve_project_path(state.get("analysis_output_path", app.analysis_output_path_var.get()), project_file_path))
        app.save_threshold_output_var.set(bool(state.get("save_threshold_output", app.save_threshold_output_var.get())))
        threshold_format = str(state.get("threshold_output_format", app.threshold_output_format_var.get())).strip()
        if threshold_format in app.threshold_output_format_combo.cget("values"):
            app.threshold_output_format_var.set(threshold_format)
        app.threshold_output_path_var.set(self._resolve_project_path(state.get("threshold_output_path", app.threshold_output_path_var.get()), project_file_path))
        app.update_output_path_defaults(force=False)
        try:
            threshold_val = int(state.get("threshold_offset", app.threshold_offset_var.get()))
            app.threshold_offset_var.set(threshold_val)
        except (ValueError, TypeError):
            pass
        self._set_entry_text(app.pixel_entry, state.get("pixels_per_col", app.pixel_entry.get()))
        self._set_entry_text(app.stdev_entry, state.get("stdevs", app.stdev_entry.get()))

        preview_mode = str(state.get("preview_mode", app.preview_mode.get())).strip()
        if preview_mode in ("analysis", "threshold"):
            app.preview_mode.set(preview_mode)

        app.graph_stdevs_var.set(str(state.get("graph_stdevs", app.graph_stdevs_var.get())).strip())
        app.graph_fit_degree_var.set(str(state.get("graph_fit_degree", app.graph_fit_degree_var.get())).strip())
        app.show_best_fit_var.set(bool(state.get("show_best_fit", app.show_best_fit_var.get())))
        app.graph_x_axis_label.set(str(state.get("graph_x_axis_label", app.graph_x_axis_label.get())))
        app.graph_y_axis_label.set(str(state.get("graph_y_axis_label", app.graph_y_axis_label.get())))
        app.graph_x_min_var.set(str(state.get("graph_x_min", app.graph_x_min_var.get())).strip())
        app.graph_x_max_var.set(str(state.get("graph_x_max", app.graph_x_max_var.get())).strip())
        app.graph_y_min_var.set(str(state.get("graph_y_min", app.graph_y_min_var.get())).strip())
        app.graph_y_max_var.set(str(state.get("graph_y_max", app.graph_y_max_var.get())).strip())

        app.calibration_distance_var.set(str(state.get("calibration_distance", app.calibration_distance_var.get())))
        cal_units = str(state.get("calibration_units", app.calibration_units_var.get())).strip()
        if cal_units in ("mm", "cm", "in"):
            app.calibration_units_var.set(cal_units)

        unit_label = str(state.get("graph_unit_label", "px")).strip() or "px"
        try:
            unit_scale = float(state.get("graph_unit_scale", 1.0))
        except (TypeError, ValueError):
            unit_scale = 1.0
        if unit_scale <= 0:
            unit_scale = 1.0
        app.graph_unit_label = unit_label
        app.graph_unit_scale = unit_scale
        if unit_label == "px":
            app.graph_units_label.config(text="Units: px (uncalibrated)")
            app.calibration_status_var.set("Calibration: not set")
        else:
            app.graph_units_label.config(text=f"Units: {unit_label} | Scale: {app.graph_unit_scale:.6g} {unit_label}/px")
            app.calibration_status_var.set(f"Calibration loaded: {app.graph_unit_scale:.6g} {unit_label}/px")

        cal_line = state.get("calibration_line_img")
        if isinstance(cal_line, list) and len(cal_line) == 4:
            app.calibration_line_img = [float(cal_line[0]), float(cal_line[1]), float(cal_line[2]), float(cal_line[3])]
        else:
            app.calibration_line_img = None
        nozzle = state.get("nozzle_origin_img")
        if isinstance(nozzle, list) and len(nozzle) == 2:
            app.nozzle_origin_img = [float(nozzle[0]), float(nozzle[1])]
            app.nozzle_status_var.set(
                f"Nozzle origin set: x={app.nozzle_origin_img[0]:.1f}px, y={app.nozzle_origin_img[1]:.1f}px"
            )
        else:
            app.nozzle_origin_img = None
            app.nozzle_status_var.set("Nozzle origin: not set")

        app.crop_mode = False
        app.canvas.delete("crop_box")
        app.save_crop_button.config(state="disabled")
        if app.total_frames > 0 and app.original_crop_frame is not None:
            h, w = app.original_crop_frame.shape[:2]
            left = int(state.get("crop_left", app.crop_left))
            top = int(state.get("crop_top", app.crop_top))
            right = int(state.get("crop_right", app.crop_right))
            bottom = int(state.get("crop_bottom", app.crop_bottom))
            left = max(0, min(left, w - 1))
            top = max(0, min(top, h - 1))
            right = max(left + 1, min(right, w))
            bottom = max(top + 1, min(bottom, h))
            app.crop_left = left
            app.crop_top = top
            app.crop_right = right
            app.crop_bottom = bottom
            app.update_crop_size_label()

        if app.total_frames > 0:
            start = app.safe_int(state.get("start_frame", app.start_frame_var.get()))
            end = app.safe_int(state.get("end_frame", app.end_frame_var.get()))
            if start is None:
                start = app.start_frame_var.get()
            if end is None:
                end = app.end_frame_var.get()
            app.apply_range(start, end)
            frame_idx = app.safe_int(state.get("current_preview_frame_index", start))
            if frame_idx is None:
                frame_idx = start
            frame_idx = max(0, min(frame_idx, app.total_frames - 1))
            app.current_preview_frame_index = frame_idx
            app.preview_frame_at(frame_idx)

        app.calibration_mode = False
        app.calibration_drag_point = None
        app.nozzle_pick_mode = False
        app.refresh_output_controls_state()
        app.redraw_graph()
        app.refresh_run_state()

    def load_project(self):
        app = self.app
        if app.is_running:
            return
        initial_dir = app.output_dir.get().strip() or os.path.dirname(__file__)
        file_path = filedialog.askopenfilename(
            title="Load Project",
            defaultextension=".json",
            filetypes=[("Project JSON", "*.json"), ("All Files", "*.*")],
            initialdir=initial_dir,
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                state = json.load(handle)
            self.apply_project_state(state, project_file_path=file_path)
            app.project_path = file_path
            messagebox.showinfo("Project loaded", f"Loaded project from:\n{file_path}")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror("Load failed", f"Could not load project:\n{exc}")

    def try_auto_load_startup_project(self):
        import sys
        app = self.app
        if app.is_running:
            return
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(__file__)
        for filename in self.startup_project_filenames:
            file_path = os.path.normpath(os.path.join(base_dir, filename))
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    state = json.load(handle)
                self.apply_project_state(state, project_file_path=file_path)
                app.project_path = file_path
                return
            except (OSError, json.JSONDecodeError, ValueError):
                return
