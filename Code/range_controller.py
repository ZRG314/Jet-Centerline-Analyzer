"""Controller for frame-range slider synchronization and range navigation."""

class RangeController:
    def __init__(self, app):
        self.app = app

    def on_range_change(self, start, end, active_handle):
        app = self.app
        if app.total_frames <= 0:
            return
        app._range_sync_lock = True
        app.start_frame_var.set(start)
        app.end_frame_var.set(end)
        app.start_frame_text.set(str(start))
        app.end_frame_text.set(str(end))
        app._range_sync_lock = False
        app.range_label.config(text=f"Start: {start}   End: {end}")

        if active_handle == "start":
            app.preview_frame_at(start)
        elif active_handle == "end":
            app.preview_frame_at(end)
        app.refresh_run_state()

    def on_range_entry_commit(self, _event=None):
        app = self.app
        if app._range_sync_lock or app.total_frames <= 0:
            return
        start = app.safe_int(app.start_frame_text.get())
        end = app.safe_int(app.end_frame_text.get())
        if start is None or end is None:
            app.refresh_run_state()
            return
        app.apply_range(start, end)

    def apply_range(self, start, end, preview_handle=None):
        app = self.app
        if app.total_frames <= 0:
            return
        start = max(0, min(int(start), app.total_frames - 1))
        end = max(0, min(int(end), app.total_frames - 1))
        if start > end:
            start, end = end, start

        app._range_sync_lock = True
        app.start_frame_var.set(start)
        app.end_frame_var.set(end)
        app.start_frame_text.set(str(start))
        app.end_frame_text.set(str(end))
        app._range_sync_lock = False

        app.range_slider.set_values(start, end)
        app.range_label.config(text=f"Start: {start}   End: {end}")
        if preview_handle == "start":
            app.preview_frame_at(start)
        elif preview_handle == "end":
            app.preview_frame_at(end)
        app.refresh_run_state()

    def use_full_video(self):
        app = self.app
        if app.total_frames <= 0:
            return
        app.apply_range(0, app.total_frames - 1)
        app.refresh_run_state()

    def set_range_controls_enabled(self, enabled):
        app = self.app
        app.range_slider.set_enabled(enabled)
        state = "normal" if enabled else "disabled"
        for widget in (app.start_entry, app.end_entry, app.jump_start_button, app.jump_end_button):
            widget.config(state=state)

    def jump_to_start_frame(self):
        app = self.app
        if app.total_frames <= 0:
            return
        app.preview_frame_at(app.start_frame_var.get())

    def jump_to_end_frame(self):
        app = self.app
        if app.total_frames <= 0:
            return
        app.preview_frame_at(app.end_frame_var.get())
