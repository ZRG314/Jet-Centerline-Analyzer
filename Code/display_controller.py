"""Controller for preview rendering, frame display transforms, and live preview updates."""

import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk


class DisplayController:
    def __init__(self, app):
        self.app = app

    def on_resize(self, event):
        app = self.app
        new_size = (max(1, int(event.width)), max(1, int(event.height)))
        if app._pending_preview_size == new_size:
            return
        app._pending_preview_size = new_size
        app._resize_render_hold_until = time.time() + 0.45
        app._resize_freeze_active = True
        if app._resize_after_id is not None:
            app.root.after_cancel(app._resize_after_id)
        app._resize_after_id = app.root.after(260, self._flush_resize)

    def _flush_resize(self):
        app = self.app
        app._resize_after_id = None
        if not app._pending_preview_size:
            return
        app.preview_width, app.preview_height = app._pending_preview_size
        app._pending_preview_size = None
        app._resize_freeze_active = False
        frame_to_render = app._deferred_display_frame if app._deferred_display_frame is not None else app.last_display_frame
        app._deferred_display_frame = None
        if frame_to_render is not None:
            self._render_frame(frame_to_render, remember_frame=False, update_threshold=False)
        else:
            app.update_post_analysis_preview()

    def display_frame(self, frame):
        app = self.app
        if app._resize_freeze_active or time.time() < app._resize_render_hold_until:
            app._deferred_display_frame = frame.copy()
            app.last_display_frame = app._deferred_display_frame
            return
        self._render_frame(frame, remember_frame=True, update_threshold=True)

    def _render_frame(self, frame, remember_frame, update_threshold):
        app = self.app
        frame_id = id(frame)
        if app._cached_display_frame_id == frame_id and app._cached_display_pil is not None:
            img = app._cached_display_pil
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            app._cached_display_frame_id = frame_id
            app._cached_display_pil = img
        if remember_frame:
            app.last_display_frame = frame.copy()
            app._cached_display_frame_id = id(app.last_display_frame)
            app._cached_display_pil = img

        orig_w, orig_h = img.size
        scale = min(app.preview_width / orig_w, app.preview_height / orig_h)
        if app.notebook.select() == str(app.calibration_tab):
            scale *= app.calibration_zoom

        app.current_scale = scale
        display_w = int(orig_w * scale)
        display_h = int(orig_h * scale)
        app.display_w = display_w
        app.display_h = display_h

        resized = img.resize((display_w, display_h), Image.Resampling.BILINEAR)
        canvas_img = Image.new("RGB", (app.preview_width, app.preview_height), (0, 0, 0))

        base_x = (app.preview_width - display_w) // 2
        base_y = (app.preview_height - display_h) // 2
        if app.notebook.select() == str(app.calibration_tab):
            max_pan_x = max(0.0, (display_w - app.preview_width) / 2.0)
            max_pan_y = max(0.0, (display_h - app.preview_height) / 2.0)
            app.calibration_pan_x = max(-max_pan_x, min(app.calibration_pan_x, max_pan_x))
            app.calibration_pan_y = max(-max_pan_y, min(app.calibration_pan_y, max_pan_y))
            app.x_offset = int(round(base_x + app.calibration_pan_x))
            app.y_offset = int(round(base_y + app.calibration_pan_y))
        else:
            app.calibration_pan_x = 0.0
            app.calibration_pan_y = 0.0
            app.x_offset = base_x
            app.y_offset = base_y

        canvas_img.paste(resized, (app.x_offset, app.y_offset))

        photo = ImageTk.PhotoImage(canvas_img)
        if app.canvas_image_item is None:
            app.canvas_image_item = app.canvas.create_image(0, 0, anchor="nw", image=photo)
        else:
            try:
                app.canvas.itemconfigure(app.canvas_image_item, image=photo)
            except tk.TclError:
                app.canvas_image_item = app.canvas.create_image(0, 0, anchor="nw", image=photo)
        app.canvas.image = photo

        if app.crop_mode and app.crop_rect and app.notebook.select() == str(app.crop_tab):
            app.draw_crop_box()
            app.update_crop_size_label(preview_rect=app.crop_rect)
        else:
            app.canvas.delete("crop_box")
        if app.notebook.select() == str(app.calibration_tab):
            if app.calibration_line_img is not None and not app.crop_mode:
                app.draw_calibration_line()
            if app.nozzle_origin_img is not None:
                app.draw_nozzle_origin()
        else:
            app.canvas.delete("cal_line")
            app.canvas.delete("nozzle_origin")
        
        if update_threshold:
            app.update_actual_threshold_display()

    def preview_frame_at(self, frame_index):
        app = self.app
        if not app.video_path.get():
            return
        if app.total_frames > 0:
            frame_index = max(0, min(int(frame_index), app.total_frames - 1))
        cap = cv2.VideoCapture(app.video_path.get())
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = cap.read()
        cap.release()
        if ret:
            app.current_preview_frame_index = frame_index
            app.original_crop_frame = frame.copy()
            frame_to_show = app.prepare_preview_frame(frame)
            app.display_frame(frame_to_show)

    def canvas_to_image_point(self, canvas_x, canvas_y):
        app = self.app
        if app.current_scale <= 0 or app.display_w <= 0 or app.display_h <= 0:
            return None
        img_x = (canvas_x - app.x_offset) / app.current_scale
        img_y = (canvas_y - app.y_offset) / app.current_scale
        img_x = max(0.0, min(img_x, (app.display_w / app.current_scale) - 1))
        img_y = max(0.0, min(img_y, (app.display_h / app.current_scale) - 1))
        return float(img_x), float(img_y)

    def image_to_canvas_point(self, img_x, img_y):
        app = self.app
        x = app.x_offset + (img_x * app.current_scale)
        y = app.y_offset + (img_y * app.current_scale)
        return x, y

    def should_show_full_preview_frame(self):
        app = self.app
        selected = app.notebook.select()
        return selected == str(app.calibration_tab) or (selected == str(app.crop_tab) and app.crop_mode)

    def prepare_preview_frame(self, frame):
        app = self.app
        if frame is None:
            return frame
        if self.should_show_full_preview_frame():
            return frame
        return app.apply_saved_crop_to_frame(frame)

    def update_preview(self, processed_count, frame, binary_frame, threshold_value, raw_frame=None):
        app = self.app
        app.frame_counter = processed_count
        app.root.after(0, lambda: app.progress.configure(value=app.frame_counter))

        elapsed = time.time() - app.start_time

        app.root.after(
            0,
            lambda: app.time_label.configure(
                text=f"{elapsed:.2f}s | {app.frame_counter}/{app.total_frames_to_process}"
            ),
        )

        app.last_analysis_frame = frame.copy()
        app.last_threshold_frame = binary_frame.copy()
        if raw_frame is not None:
            app.last_raw_analysis_frame = raw_frame.copy()

        app.root.after(0, app.update_post_analysis_preview)

    def update_post_analysis_preview(self):
        app = self.app
        if app.last_analysis_frame is None:
            return
        if app.preview_mode.get() == "analysis":
            if app.show_analysis_overlay_var.get():
                app.display_frame(app.last_analysis_frame)
            elif app.last_raw_analysis_frame is not None:
                app.display_frame(app.last_raw_analysis_frame)
            else:
                app.display_frame(app.last_analysis_frame)
        elif app.preview_mode.get() == "threshold":
            # Regenerate multi-threshold colored preview if enabled
            if app.use_multi_threshold_var.get():
                import cv2
                from analysis_engine import compute_multi_thresholds, build_threshold_color_preview_filtered
                offsets = app.get_multi_threshold_offsets()
                colors = app.get_multi_threshold_colors()
                # Always use last_raw_analysis_frame (no overlays) for clean threshold preview
                source_frame = getattr(app, 'last_raw_analysis_frame', None)
                if source_frame is None:
                    source_frame = app.last_analysis_frame
                if source_frame is not None:
                    frame_to_preview = source_frame.copy()
                    gray = cv2.cvtColor(frame_to_preview, cv2.COLOR_BGR2GRAY) if frame_to_preview.ndim == 3 else frame_to_preview
                    thresholds, _ = compute_multi_thresholds(gray, offsets)
                    region_count = len(thresholds) + 1
                    preview_colors = colors[:region_count] if len(colors) >= region_count else colors + ["#000000"] * (region_count - len(colors))
                    threshold_frame_img = build_threshold_color_preview_filtered(gray, thresholds, preview_colors)
                    app.last_threshold_frame = threshold_frame_img
                    app.display_frame(threshold_frame_img)
                    return
            # Fall back to standard binary threshold frame
            if app.last_threshold_frame is not None:
                app.display_frame(app.last_threshold_frame)
