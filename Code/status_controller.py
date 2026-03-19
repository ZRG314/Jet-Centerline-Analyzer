"""Controller for run-state UI toggles, status badge styling, and output folder selection."""

from tkinter import filedialog


class StatusController:
    def __init__(self, app):
        self.app = app

    def set_processing_controls(self, running):
        app = self.app
        app.run_button.config(state="disabled" if running else "normal")
        app.stop_button.config(state="normal" if running else "disabled")
        if running:
            app.calibration_mode = False
            app.calibration_drag_point = None
            app.nozzle_pick_mode = False
            app.set_status("Running", "running")
        disabled_state = "disabled" if running else "normal"
        app.video_source_menu.config(state="disabled" if running else "readonly")
        app.select_video_button.config(state=disabled_state)
        app.output_name_entry.config(state=disabled_state)
        app.threshold_output_name_entry.config(state=disabled_state)
        app.analysis_output_check.config(state=disabled_state)
        app.threshold_output_check.config(state=disabled_state)
        if running:
            app.analysis_output_entry.config(state="disabled")
            app.analysis_output_browse_button.config(state="disabled")
            app.analysis_output_format_combo.config(state="disabled")
            app.threshold_output_entry.config(state="disabled")
            app.threshold_output_browse_button.config(state="disabled")
            app.threshold_output_format_combo.config(state="disabled")
        else:
            app.refresh_output_controls_state()
        app.calibration_set_line_button.config(state=disabled_state)
        app.calibration_set_nozzle_button.config(state=disabled_state)
        app.calibration_apply_button.config(state=disabled_state)
        app.calibration_clear_button.config(state=disabled_state)
        app.calibration_units_combo.config(state="disabled" if running else "readonly")
        app.save_crop_button.config(state="disabled")
        app.reset_crop_button.config(state=disabled_state)
        app.use_full_range_button.config(state=disabled_state)
        if running:
            app.set_range_controls_enabled(False)
        else:
            app.set_range_controls_enabled(app.total_frames > 0)

    def set_status(self, text, tone):
        app = self.app
        tones = {
            "ready": ("#e8f5e9", "#1b5e20"),
            "running": ("#e3f2fd", "#0d47a1"),
            "warning": ("#fff8e1", "#8a6d00"),
            "error": ("#ffebee", "#b71c1c"),
            "idle": ("#eceff1", "#37474f"),
        }
        bg, fg = tones.get(tone, tones["idle"])
        app.status_var.set(text)
        app.status_badge.config(bg=bg, fg=fg)

    def select_output_dir(self):
        app = self.app
        if app.is_running:
            return
        folder = filedialog.askdirectory()
        if folder:
            app.output_dir.set(folder)
            app.refresh_run_state()
