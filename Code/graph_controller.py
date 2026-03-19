"""Controller for graph computations, rendering, and graph export actions."""

import csv
import os
import tkinter as tk
from datetime import datetime
from statistics import NormalDist
from tkinter import filedialog, messagebox, simpledialog, ttk

import cv2
import numpy as np

from graph_math import compute_best_fit as compute_best_fit_profile
from graph_math import format_graph_value as format_graph_value_text
from plotting import resolve_axis_limits as resolve_plot_axis_limits


class GraphController:
    def __init__(self, app):
        self.app = app

    def graph_view_mode(self):
        return str(self.app.graph_view_mode_var.get()).strip()

    def resolve_graph_title(self, default_title):
        title_var = getattr(self.app, "graph_title_var", None)
        if title_var is None:
            return default_title
        custom = str(title_var.get()).strip()
        return custom if custom else default_title

    def edit_graph_title(self):
        title_var = getattr(self.app, "graph_title_var", None)
        if title_var is None:
            return
        current = str(title_var.get())
        new_value = simpledialog.askstring(
            "Edit Graph Title",
            "Enter graph title text (blank uses auto title).",
            initialvalue=current,
            parent=self.app.root,
        )
        if new_value is None:
            return
        title_var.set(str(new_value).strip())
        self.redraw_graph()

    def current_axis_label_text(self, axis_name):
        axis_name = str(axis_name).strip().upper()
        app = self.app
        mode = self.graph_view_mode()

        if mode == "Profile":
            if axis_name == "X":
                return app.graph_x_axis_label.get().strip() or self.profile_default_x_axis_label()
            return app.graph_y_axis_label.get().strip() or self.profile_default_y_axis_label()

        distribution_data = self.build_distribution_data()
        if distribution_data is None:
            return f"{axis_name} Axis"

        if mode == "Histogram":
            x_axis_text = distribution_data["default_x_label"]
            y_axis_text = distribution_data["default_y_label"]
        else:
            x_axis_text = "Theoretical Normal Quantile"
            y_axis_text = "Observed Quantile"

        return x_axis_text if axis_name == "X" else y_axis_text

    def _edit_axis_text(self, var, title, prompt):
        current_value = str(var.get())
        new_value = simpledialog.askstring(title, prompt, initialvalue=current_value, parent=self.app.root)
        if new_value is None:
            return
        var.set(str(new_value).strip())
        self.redraw_graph()

    def _split_axis_label_and_unit(self, label_text, fallback_label):
        text = str(label_text or "").strip()
        if text.endswith(")") and "(" in text:
            prefix, suffix = text.rsplit("(", 1)
            base = prefix.strip()
            unit = suffix[:-1].strip().lower()
            if base:
                if unit in ("mm", "pix", "px"):
                    unit = "pix" if unit in ("pix", "px") else "mm"
                    return base, unit
        return (text or fallback_label), "mm"

    def _axis_unit_from_var(self, var, fallback="mm"):
        text = str(var.get() if var is not None else "").strip()
        _base, unit = self._split_axis_label_and_unit(text, "")
        if unit in ("mm", "pix"):
            return unit
        return fallback

    def _clean_axis_bound_text(self, text, label):
        cleaned = str(text).strip()
        if not cleaned:
            return ""
        try:
            float(cleaned)
        except ValueError:
            messagebox.showerror("Invalid axis bound", f"{label} must be numeric or blank.")
            return None
        return cleaned

    def _resolve_auto_axis_limits(self, x_values, y_values, y_pad=1.0):
        return resolve_plot_axis_limits(
            x_values,
            y_values,
            x_user_min=None,
            x_user_max=None,
            y_user_min=None,
            y_user_max=None,
            y_pad=y_pad,
        )

    def current_graph_suggested_bounds(self):
        mode = self.graph_view_mode()

        if mode == "Profile":
            plot_data = self.build_plot_data()
            if plot_data is None:
                return None
            valid = plot_data["valid"]
            x_values = plot_data["x_all_values"][valid]
            y_values = np.concatenate((plot_data["upper_values"][valid], plot_data["lower_values"][valid]))
            return self._resolve_auto_axis_limits(x_values, y_values, y_pad=1.0)

        distribution_data = self.build_distribution_data()
        if distribution_data is None:
            return None

        if mode == "Histogram":
            if distribution_data.get("all_columns"):
                x_column_display = distribution_data["x_column_display"]
                edges = distribution_data["histogram_edges"]
                if x_column_display.size == 1:
                    column_span = 1.0
                    x_edges = np.array(
                        [
                            x_column_display[0] - 0.5 * column_span,
                            x_column_display[0] + 0.5 * column_span,
                        ],
                        dtype=np.float64,
                    )
                else:
                    midpoints = 0.5 * (x_column_display[:-1] + x_column_display[1:])
                    first_edge = x_column_display[0] - (midpoints[0] - x_column_display[0])
                    last_edge = x_column_display[-1] + (x_column_display[-1] - midpoints[-1])
                    x_edges = np.concatenate(([first_edge], midpoints, [last_edge]))
                return float(x_edges[0]), float(x_edges[-1]), float(edges[0]), float(edges[-1])

            edges = distribution_data["histogram_edges"]
            counts = distribution_data["histogram_counts"]
            limits = self._resolve_auto_axis_limits(edges, np.append(counts, 0), y_pad=1.0)
            if limits is None:
                return None
            x_min, x_max, _y_min, y_max = limits
            return x_min, x_max, 0.0, y_max

        theoretical = distribution_data["theoretical_quantiles"]
        observed = distribution_data["sorted_values"]
        combined = np.concatenate((theoretical, observed))
        return self._resolve_auto_axis_limits(combined, combined, y_pad=1.0)

    def x_axis_unit(self):
        fallback = "pix" if (self.app.graph_unit_label or "px").strip().lower() == "px" else "mm"
        return self._axis_unit_from_var(getattr(self.app, "graph_x_axis_label", None), fallback=fallback)

    def y_axis_unit(self):
        fallback = "pix" if (self.app.graph_unit_label or "px").strip().lower() == "px" else "mm"
        return self._axis_unit_from_var(getattr(self.app, "graph_y_axis_label", None), fallback=fallback)

    def _edit_axis_title_with_units(self, var, axis_name):
        axis_name = str(axis_name).strip().upper()
        current_value = str(var.get())
        visible_label = self.current_axis_label_text(axis_name)
        current_base, current_unit = self._split_axis_label_and_unit(current_value or visible_label, f"{axis_name} Axis")
        min_var = self.app.graph_x_min_var if axis_name == "X" else self.app.graph_y_min_var
        max_var = self.app.graph_x_max_var if axis_name == "X" else self.app.graph_y_max_var
        bound_min_var = tk.StringVar(value=str(min_var.get()).strip())
        bound_max_var = tk.StringVar(value=str(max_var.get()).strip())

        popup = tk.Toplevel(self.app.root)
        popup.title(f"Edit {axis_name} Axis Title")
        popup.resizable(False, False)
        popup.transient(self.app.root)
        popup.grab_set()

        title_var = tk.StringVar(value=current_base)
        unit_var = tk.StringVar(value=current_unit)

        frame = tk.Frame(popup, padx=12, pady=10)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        tk.Label(frame, text="Title").grid(row=0, column=0, sticky="w")
        title_entry = tk.Entry(frame, textvariable=title_var, width=34)
        title_entry.grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 8))

        tk.Label(frame, text="Units").grid(row=2, column=0, sticky="w")
        unit_combo = ttk.Combobox(
            frame,
            textvariable=unit_var,
            values=["mm", "pix"],
            state="readonly",
            width=10,
        )
        unit_combo.grid(row=2, column=1, sticky="w", padx=(8, 0))

        tk.Label(frame, text=f"{axis_name} Axis Bounds").grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        tk.Label(frame, text="Min").grid(row=4, column=0, sticky="w", pady=(2, 0))
        min_entry = tk.Entry(frame, textvariable=bound_min_var, width=14)
        min_entry.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(2, 0))
        tk.Label(frame, text="Max").grid(row=5, column=0, sticky="w", pady=(6, 0))
        max_entry = tk.Entry(frame, textvariable=bound_max_var, width=14)
        max_entry.grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

        suggested_bounds_var = tk.StringVar(value="Suggested min: n/a\nSuggested max: n/a")
        suggested_bounds_label = tk.Label(
            frame,
            textvariable=suggested_bounds_var,
            justify="left",
            fg="gray35",
        )
        suggested_bounds_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))

        use_suggested_button = tk.Button(frame, text="Use Suggested Bounds")
        use_suggested_button.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))

        button_row = tk.Frame(frame)
        button_row.grid(row=8, column=0, columnspan=2, sticky="e", pady=(12, 0))

        def refresh_suggested_bounds(*_args):
            selected_unit = unit_var.get().strip().lower()
            if selected_unit not in ("mm", "pix"):
                selected_unit = current_unit if current_unit in ("mm", "pix") else "mm"

            original_value = str(var.get())
            try:
                var.set(f"{current_base} ({selected_unit})")
                suggested_bounds = self.current_graph_suggested_bounds()
            finally:
                var.set(original_value)

            suggested_min = None
            suggested_max = None
            if suggested_bounds is not None:
                if axis_name == "X":
                    suggested_min, suggested_max = suggested_bounds[0], suggested_bounds[1]
                else:
                    suggested_min, suggested_max = suggested_bounds[2], suggested_bounds[3]

            suggested_min_text = self.format_graph_value(suggested_min) if suggested_min is not None else "n/a"
            suggested_max_text = self.format_graph_value(suggested_max) if suggested_max is not None else "n/a"
            suggested_bounds_var.set(f"Suggested min: {suggested_min_text}\nSuggested max: {suggested_max_text}")

            if suggested_min is not None and suggested_max is not None:
                use_suggested_button.config(
                    state="normal",
                    command=lambda min_text=suggested_min_text, max_text=suggested_max_text: (
                        bound_min_var.set(min_text),
                        bound_max_var.set(max_text),
                    ),
                )
            else:
                use_suggested_button.config(state="disabled", command=lambda: None)

        def on_save():
            cleaned_min = self._clean_axis_bound_text(bound_min_var.get(), f"{axis_name} axis minimum")
            if cleaned_min is None:
                return
            cleaned_max = self._clean_axis_bound_text(bound_max_var.get(), f"{axis_name} axis maximum")
            if cleaned_max is None:
                return
            if cleaned_min and cleaned_max and float(cleaned_max) <= float(cleaned_min):
                messagebox.showerror(
                    "Invalid axis bounds",
                    f"{axis_name} axis maximum must be greater than the minimum.",
                )
                return
            label_text = title_var.get().strip() or current_base
            selected_unit = unit_var.get().strip().lower()
            if selected_unit not in ("mm", "pix"):
                selected_unit = "mm"
            var.set(f"{label_text} ({selected_unit})")
            min_var.set(cleaned_min)
            max_var.set(cleaned_max)
            popup.destroy()
            self.redraw_graph()

        tk.Button(button_row, text="Cancel", command=popup.destroy).pack(side="right")
        tk.Button(button_row, text="Save", command=on_save).pack(side="right", padx=(0, 6))

        popup.update_idletasks()
        width = popup.winfo_reqwidth()
        height = popup.winfo_reqheight()
        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        popup.geometry(f"{width}x{height}+{x}+{y}")

        popup.bind("<Return>", lambda _event: on_save())
        popup.bind("<Escape>", lambda _event: popup.destroy())
        unit_var.trace_add("write", refresh_suggested_bounds)
        refresh_suggested_bounds()
        title_entry.focus_set()
        popup.wait_window()

    def _edit_axis_limit(self, var, title):
        current_value = str(var.get())
        new_value = simpledialog.askstring(
            title,
            "Enter a number, or leave blank for auto bounds.",
            initialvalue=current_value,
            parent=self.app.root,
        )
        if new_value is None:
            return
        cleaned = str(new_value).strip()
        if cleaned:
            try:
                float(cleaned)
            except ValueError:
                messagebox.showerror("Invalid axis bound", "Axis bounds must be numeric or blank.")
                return
        var.set(cleaned)
        self.redraw_graph()

    def _bind_graph_edit_action(self, tag, callback):
        canvas = self.app.graph_canvas
        canvas.tag_bind(tag, "<Button-1>", lambda _event: callback())
        canvas.tag_bind(tag, "<Enter>", lambda _event: canvas.config(cursor="hand2"))
        canvas.tag_bind(tag, "<Leave>", lambda _event: canvas.config(cursor=""))

    def _clear_graph_edit_action(self, tag):
        canvas = self.app.graph_canvas
        for sequence in ("<Button-1>", "<Enter>", "<Leave>"):
            try:
                canvas.tag_unbind(tag, sequence)
            except tk.TclError:
                pass

    def _draw_editable_axis_controls(self, left, top, plot_w, plot_h):
        app = self.app
        canvas = app.graph_canvas
        axis_text_color = "black"

        x_label_text = self.current_axis_label_text("X")
        y_label_text = self.current_axis_label_text("Y")

        canvas.create_text(
            canvas.winfo_width() // 2,
            canvas.winfo_height() - 22,
            text=x_label_text,
            fill=axis_text_color,
            font=("TkDefaultFont", 10),
            tags=("graph_edit_x_label",),
        )
        canvas.create_text(
            28,
            canvas.winfo_height() // 2,
            text=y_label_text,
            fill=axis_text_color,
            angle=90,
            font=("TkDefaultFont", 10),
            tags=("graph_edit_y_label",),
        )

        self._bind_graph_edit_action(
            "graph_edit_x_label",
            lambda: self._edit_axis_title_with_units(app.graph_x_axis_label, "X"),
        )
        self._bind_graph_edit_action(
            "graph_edit_y_label",
            lambda: self._edit_axis_title_with_units(app.graph_y_axis_label, "Y"),
        )
        self._clear_graph_edit_action("graph_edit_x_min_tick")
        self._clear_graph_edit_action("graph_edit_x_max_tick")
        self._clear_graph_edit_action("graph_edit_y_min_tick")
        self._clear_graph_edit_action("graph_edit_y_max_tick")

    def histogram_scope(self):
        scope_var = getattr(self.app, "graph_histogram_scope_var", None)
        return str(scope_var.get()).strip() if scope_var is not None else "All Columns"

    def is_single_column_mode(self):
        mode = self.graph_view_mode()
        if mode == "Histogram" and self.histogram_scope() == "Selected Column":
            return True
        return False

    def profile_value_mode(self):
        return "Pixel Values" if self.y_axis_unit() == "pix" else "Actual Values"

    def profile_x_value_mode(self):
        return "Pixel Values" if self.x_axis_unit() == "pix" else "Actual Values"

    def column_input_mode(self):
        return "Pixel Values" if self.x_axis_unit() == "pix" else "Actual Values"

    def using_profile_pixel_values(self):
        return self.profile_value_mode() == "Pixel Values"

    def using_profile_x_pixel_values(self):
        return self.profile_x_value_mode() == "Pixel Values"

    def profile_x_value(self, x_px):
        if self.using_profile_x_pixel_values():
            return float(x_px)
        return float(self.x_position_to_graph_units(x_px))

    def profile_y_value(self, y_px):
        if self.using_profile_pixel_values():
            return float(self.y_position_to_graph_pixels(y_px))
        return float(self.y_position_to_graph_units(y_px))

    def profile_y_delta_value(self, dy_px):
        if self.using_profile_pixel_values():
            return float(dy_px)
        return float(self.y_delta_to_graph_units(dy_px))

    def profile_axis_unit_label(self):
        return "pix" if self.using_profile_pixel_values() else "mm"

    def profile_x_axis_unit_label(self):
        return "pix" if self.using_profile_x_pixel_values() else "mm"

    def profile_default_x_axis_label(self):
        return f"Horizontal Position ({self.profile_x_axis_unit_label()})"

    def profile_default_y_axis_label(self):
        return f"Vertical Position ({self.profile_axis_unit_label()})"

    def column_index_to_value(self, column_index):
        x_px = float(self.profile_index_to_x_px(column_index))
        if self.column_input_mode() == "Actual Values":
            return float(self.x_position_to_graph_units(x_px))
        return x_px

    def column_value_to_index(self, value, column_count):
        if column_count <= 0:
            return 0
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.0
        x_px = numeric
        if self.column_input_mode() == "Actual Values":
            scale = float(self.app.graph_unit_scale) if float(self.app.graph_unit_scale) != 0 else 1.0
            x_px = numeric / scale
        index = int(round(x_px / self.pixels_per_column()))
        return max(0, min(int(column_count - 1), index))

    def column_input_suffix(self):
        return "pix" if self.column_input_mode() == "Pixel Values" else "mm"

    def format_column_input_bounds(self, column_count):
        if column_count <= 0:
            return "Input range: run analysis to populate bounds."
        low = self.column_index_to_value(0)
        high = self.column_index_to_value(column_count - 1)
        suffix = self.column_input_suffix()
        return f"Input range: {self.format_graph_value(low)} to {self.format_graph_value(high)} {suffix}"

    def refresh_distribution_column_controls(self):
        app = self.app
        mode = self.graph_view_mode()
        if mode == "Q-Q Plot" and getattr(app, "graph_histogram_scope_var", None) is not None:
            if str(app.graph_histogram_scope_var.get()).strip() != "All Columns (Combined)":
                app.graph_histogram_scope_var.set("All Columns (Combined)")

        profile_mode = mode == "Profile"
        qq_mode = mode == "Q-Q Plot"

        def set_entry_enabled(widget, enabled):
            if widget is not None:
                widget.config(state=("normal" if enabled else "disabled"))

        def set_combo_enabled(widget, enabled):
            if widget is not None:
                widget.config(state=("readonly" if enabled else "disabled"))

        def set_label_enabled(widget, enabled, disabled_fg="gray55"):
            if widget is not None:
                widget.config(fg=("black" if enabled else disabled_fg))

        def set_header_enabled(header_row, enabled):
            if header_row is None:
                return
            for child in header_row.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(fg=("black" if enabled else "gray55"))

        distribution_controls_enabled = not profile_mode
        histogram_scope_enabled = not (profile_mode or qq_mode)

        set_combo_enabled(getattr(app, "graph_distribution_kind_combo", None), distribution_controls_enabled)
        set_header_enabled(getattr(app, "graph_distribution_kind_header_row", None), distribution_controls_enabled)

        set_combo_enabled(getattr(app, "graph_histogram_scope_combo", None), histogram_scope_enabled)
        set_header_enabled(getattr(app, "graph_histogram_scope_header_row", None), histogram_scope_enabled)

        bins_enabled = not (profile_mode or qq_mode)
        set_entry_enabled(getattr(app, "graph_distribution_bins_entry", None), bins_enabled)
        set_label_enabled(getattr(app, "graph_distribution_bins_label", None), bins_enabled)

        if hasattr(app, "graph_distribution_column_label"):
            app.graph_distribution_column_label.config(text=f"Selected Column ({self.column_input_suffix()})")

        single_column_mode = self.is_single_column_mode()
        column_enabled = distribution_controls_enabled and single_column_mode
        if hasattr(app, "graph_distribution_column_entry"):
            app.graph_distribution_column_entry.config(state="normal" if column_enabled else "disabled")
        set_label_enabled(getattr(app, "graph_distribution_column_label", None), column_enabled)
        if hasattr(app, "graph_distribution_column_bounds_label"):
            app.graph_distribution_column_bounds_label.config(fg=("gray35" if column_enabled else "gray55"))

        bounds_text = "Input range: run analysis to populate bounds."
        if column_enabled:
            samples = getattr(app, "final_centerline_samples", None)
            if samples is not None:
                arr = np.asarray(samples, dtype=np.float64)
                if arr.ndim == 2 and arr.shape[1] > 0:
                    bounds_text = self.format_column_input_bounds(arr.shape[1])
        elif profile_mode:
            bounds_text = "Selected Column is available only for Histogram and Q-Q views."
        elif qq_mode:
            bounds_text = "Q-Q Plot always uses all columns combined."
        else:
            bounds_text = "Selected Column is active only for Single Column Histogram."
        if hasattr(app, "graph_distribution_column_bounds_var"):
            app.graph_distribution_column_bounds_var.set(bounds_text)

    def parse_graph_stdevs(self):
        app = self.app
        try:
            value = float(str(app.graph_stdevs_var.get()).strip())
            return max(0.0, value)
        except (TypeError, ValueError):
            return 0.0

    def parse_graph_fit_degree(self):
        app = self.app
        try:
            value = int(str(app.graph_fit_degree_var.get()).strip())
            return max(1, min(6, value))
        except (TypeError, ValueError):
            return 2

    def pixels_per_column(self):
        app = self.app
        value = app.safe_int(app.pixel_entry.get())
        if value is None or value <= 0:
            return 1.0
        return float(value)

    def profile_index_to_x_px(self, x_index):
        return float(x_index) * self.pixels_per_column()

    def to_graph_units(self, px_value):
        app = self.app
        return px_value * app.graph_unit_scale

    def x_position_to_graph_units(self, x_px):
        return self.to_graph_units(x_px)

    def get_profile_height_px(self):
        app = self.app
        if app.last_analysis_frame is not None:
            return int(app.last_analysis_frame.shape[0])
        height = int(app.crop_bottom - app.crop_top)
        if height > 0:
            return height
        return None

    def nozzle_origin_y_in_profile_px(self):
        app = self.app
        if app.nozzle_origin_img is None:
            return None
        nozzle_y = float(app.nozzle_origin_img[1])
        if app.crop_bottom > app.crop_top:
            return nozzle_y - float(app.crop_top)
        return nozzle_y

    def y_position_to_graph_units(self, y_px):
        app = self.app
        frame_height = self.get_profile_height_px()
        if frame_height is None or frame_height <= 1:
            return self.to_graph_units(y_px)
        
        nozzle_y = self.nozzle_origin_y_in_profile_px()
        if nozzle_y is not None:
            # With nozzle origin: measure absolute distance from nozzle
            return self.to_graph_units(abs(y_px - nozzle_y))
        
        # Without nozzle origin: flip y-axis so top of image = top of graph
        return self.to_graph_units((frame_height - 1) - y_px)

    def y_delta_to_graph_units(self, dy_px):
        return self.to_graph_units(dy_px)

    def y_position_to_graph_pixels(self, y_px):
        frame_height = self.get_profile_height_px()
        if frame_height is None or frame_height <= 1:
            return float(y_px)

        nozzle_y = self.nozzle_origin_y_in_profile_px()
        if nozzle_y is not None:
            return float(abs(y_px - nozzle_y))

        return float((frame_height - 1) - y_px)

    def parse_optional_float_var(self, var):
        text = str(var.get()).strip()
        if not text:
            return None
        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    def resolve_axis_limits(self, x_values, y_values, y_pad=1.0):
        app = self.app
        x_user_min = self.parse_optional_float_var(app.graph_x_min_var)
        x_user_max = self.parse_optional_float_var(app.graph_x_max_var)
        y_user_min = self.parse_optional_float_var(app.graph_y_min_var)
        y_user_max = self.parse_optional_float_var(app.graph_y_max_var)
        return resolve_plot_axis_limits(
            x_values,
            y_values,
            x_user_min=x_user_min,
            x_user_max=x_user_max,
            y_user_min=y_user_min,
            y_user_max=y_user_max,
            y_pad=y_pad,
        )

    def format_graph_value(self, value):
        return format_graph_value_text(value)

    def compute_best_fit(self, mean, valid):
        return compute_best_fit_profile(mean, valid, self.parse_graph_fit_degree())

    def parse_distribution_bins(self):
        app = self.app
        try:
            value = int(str(app.graph_distribution_bins_var.get()).strip())
            return max(3, min(200, value))
        except (TypeError, ValueError):
            return 20

    def parse_distribution_column_px(self):
        app = self.app
        try:
            return float(str(app.graph_distribution_column_px_var.get()).strip())
        except (TypeError, ValueError):
            return 0.0

    def distribution_kind_defaults(self):
        app = self.app
        kind = str(app.graph_distribution_kind_var.get()).strip()
        unit_label = self.profile_axis_unit_label()
        if kind == "Positions":
            default_value_label = app.graph_y_axis_label.get().strip() or f"Vertical Position ({unit_label})"
        elif kind == "Z-Scores":
            # Z-scores are unitless; keep the axis label explicit and stable.
            default_value_label = "Z-Score"
            unit_label = "z"
        else:
            default_value_label = app.graph_y_axis_label.get().strip() or f"Residual ({unit_label})"
        return kind, unit_label, default_value_label

    def transform_distribution_values(self, raw_px, kind):
        raw_px = np.asarray(raw_px, dtype=np.float64)
        raw_px = raw_px[np.isfinite(raw_px)]
        if raw_px.size < 3:
            return None

        raw_mean_px = float(np.mean(raw_px))
        raw_std_px = float(np.std(raw_px))

        if kind == "Positions":
            values = np.array([float(self.profile_y_value(value)) for value in raw_px], dtype=np.float64)
        elif kind == "Z-Scores":
            if raw_std_px <= 0:
                values = np.zeros(raw_px.shape[0], dtype=np.float64)
            else:
                values = (raw_px - raw_mean_px) / raw_std_px
        else:
            residual_px = raw_px - raw_mean_px
            values = np.array([float(self.profile_y_delta_value(value)) for value in residual_px], dtype=np.float64)

        values = values[np.isfinite(values)]
        if values.size < 3:
            return None
        return values

    def build_histogram_across_columns_data(self, samples):
        app = self.app
        kind, unit_label, default_value_label = self.distribution_kind_defaults()
        bins = self.parse_distribution_bins()

        column_count = samples.shape[1]
        x_column_px = np.array([self.profile_index_to_x_px(idx) for idx in range(column_count)], dtype=np.float64)
        x_column_units = np.array([self.x_position_to_graph_units(value) for value in x_column_px], dtype=np.float64)
        x_column_display = np.array([self.column_index_to_value(idx) for idx in range(column_count)], dtype=np.float64)
        x_suffix = self.column_input_suffix()

        transformed_columns = []
        valid_mask = np.zeros(column_count, dtype=bool)
        collected_values = []
        for idx in range(column_count):
            transformed = self.transform_distribution_values(samples[:, idx], kind)
            transformed_columns.append(transformed)
            if transformed is not None:
                valid_mask[idx] = True
                collected_values.append(transformed)

        if not collected_values:
            return None

        all_values = np.concatenate(collected_values)
        min_value = float(np.min(all_values))
        max_value = float(np.max(all_values))
        if max_value <= min_value:
            min_value -= 0.5
            max_value += 0.5

        histogram_matrix = np.zeros((column_count, bins), dtype=np.int32)
        histogram_edges = None
        per_column_mean = np.full(column_count, np.nan, dtype=np.float64)
        per_column_std = np.full(column_count, np.nan, dtype=np.float64)

        for idx, values in enumerate(transformed_columns):
            if values is None:
                continue
            counts, edges = np.histogram(values, bins=bins, range=(min_value, max_value))
            histogram_matrix[idx, :] = counts
            histogram_edges = edges
            per_column_mean[idx] = float(np.mean(values))
            per_column_std[idx] = float(np.std(values))

        if histogram_edges is None:
            return None

        valid_column_indices = np.where(valid_mask)[0]
        median_std = float(np.nanmedian(per_column_std[valid_mask])) if np.any(valid_mask) else 0.0

        return {
            "mode": "Histogram",
            "kind": kind,
            "all_columns": True,
            "unit_label": unit_label,
            "column_input_mode": self.column_input_mode(),
            "column_input_suffix": x_suffix,
            "default_x_label": app.graph_x_axis_label.get().strip() or f"Horizontal Position ({x_suffix})",
            "default_y_label": default_value_label,
            "histogram_matrix": histogram_matrix,
            "histogram_edges": histogram_edges,
            "x_column_px": x_column_px,
            "x_column_units": x_column_units,
            "x_column_display": x_column_display,
            "valid_column_mask": valid_mask,
            "valid_column_indices": valid_column_indices,
            "sample_count": int(all_values.size),
            "column_count": int(column_count),
            "valid_column_count": int(valid_column_indices.size),
            "median_std": median_std,
            "per_column_mean": per_column_mean,
            "per_column_std": per_column_std,
        }

    def build_histogram_combined_columns_data(self, samples):
        app = self.app
        kind, unit_label, default_value_label = self.distribution_kind_defaults()
        bins = self.parse_distribution_bins()

        column_count = samples.shape[1]
        pooled_values = []
        valid_columns = 0
        for idx in range(column_count):
            transformed = self.transform_distribution_values(samples[:, idx], kind)
            if transformed is None:
                continue
            valid_columns += 1
            pooled_values.append(transformed)

        if not pooled_values:
            return None

        values = np.concatenate(pooled_values)
        values = values[np.isfinite(values)]
        if values.size < 3:
            return None

        value_mean = float(np.mean(values))
        value_std = float(np.std(values))
        centered = values - value_mean
        variance = float(np.mean(centered ** 2))
        if variance > 0:
            skewness = float(np.mean(centered ** 3) / (variance ** 1.5))
            excess_kurtosis = float(np.mean(centered ** 4) / (variance ** 2) - 3.0)
        else:
            skewness = 0.0
            excess_kurtosis = 0.0

        percentiles = np.percentile(values, [10, 50, 90])
        sorted_values = np.sort(values)
        probabilities = (np.arange(1, sorted_values.size + 1, dtype=np.float64) - 0.5) / sorted_values.size
        if value_std > 0:
            normal_dist = NormalDist(mu=value_mean, sigma=value_std)
            theoretical_quantiles = np.array([normal_dist.inv_cdf(float(prob)) for prob in probabilities], dtype=np.float64)
        else:
            theoretical_quantiles = np.full(sorted_values.shape, value_mean, dtype=np.float64)

        min_value = float(np.min(values))
        max_value = float(np.max(values))
        if max_value <= min_value:
            min_value -= 0.5
            max_value += 0.5
        histogram_counts, histogram_edges = np.histogram(values, bins=bins, range=(min_value, max_value))

        return {
            "mode": "Histogram",
            "kind": kind,
            "combined_columns": True,
            "unit_label": unit_label,
            "default_x_label": default_value_label,
            "default_y_label": "Sample Count",
            "values": values,
            "mean": value_mean,
            "std": value_std,
            "skewness": skewness,
            "excess_kurtosis": excess_kurtosis,
            "percentiles": percentiles,
            "sorted_values": sorted_values,
            "theoretical_quantiles": theoretical_quantiles,
            "histogram_counts": histogram_counts,
            "histogram_edges": histogram_edges,
            "sample_count": int(values.size),
            "column_count": int(column_count),
            "valid_column_count": int(valid_columns),
        }

    def selected_distribution_index(self, samples):
        if samples.ndim != 2 or samples.shape[1] <= 0:
            return None

        sample_width = samples.shape[1]
        requested_index = self.column_value_to_index(self.parse_distribution_column_px(), sample_width)

        def sync_entry_to_index(index_to_show):
            try:
                active_widget = self.app.root.focus_get()
                if active_widget is not self.app.graph_distribution_column_entry:
                    self.app.graph_distribution_column_px_var.set(self.format_graph_value(self.column_index_to_value(index_to_show)))
            except Exception:
                pass

        valid_counts = np.sum(np.isfinite(samples), axis=0)
        if valid_counts[requested_index] >= 3:
            sync_entry_to_index(requested_index)
            return requested_index

        candidate_indices = np.where(valid_counts >= 3)[0]
        if candidate_indices.size == 0:
            return None

        nearest = int(candidate_indices[np.argmin(np.abs(candidate_indices - requested_index))])
        sync_entry_to_index(nearest)
        return nearest

    def build_distribution_data(self):
        app = self.app
        if app.final_centerline_samples is None:
            return None

        samples = np.asarray(app.final_centerline_samples, dtype=np.float64)
        if samples.ndim != 2 or samples.shape[0] == 0 or samples.shape[1] == 0:
            return None

        mode = str(app.graph_view_mode_var.get()).strip()
        if mode == "Histogram":
            histogram_scope_var = getattr(app, "graph_histogram_scope_var", None)
            histogram_scope = str(histogram_scope_var.get()).strip() if histogram_scope_var is not None else "All Columns"
            if histogram_scope == "All Columns":
                return self.build_histogram_across_columns_data(samples)
            if histogram_scope == "All Columns (Combined)":
                return self.build_histogram_combined_columns_data(samples)
        elif mode == "Q-Q Plot":
            combined_data = self.build_histogram_combined_columns_data(samples)
            if combined_data is None:
                return None
            combined_data["mode"] = "Q-Q Plot"
            return combined_data

        selected_index = self.selected_distribution_index(samples)
        if selected_index is None:
            return None
        raw_px = samples[:, selected_index]

        values = self.transform_distribution_values(raw_px, str(app.graph_distribution_kind_var.get()).strip())
        if values is None:
            return None

        selected_x_px = float(self.profile_index_to_x_px(selected_index))
        selected_x_units = float(self.x_position_to_graph_units(selected_x_px))
        selected_x_display = float(self.column_index_to_value(selected_index))
        kind, unit_label, default_value_label = self.distribution_kind_defaults()

        value_mean = float(np.mean(values))
        value_std = float(np.std(values))
        centered = values - value_mean
        variance = float(np.mean(centered ** 2))
        if variance > 0:
            skewness = float(np.mean(centered ** 3) / (variance ** 1.5))
            excess_kurtosis = float(np.mean(centered ** 4) / (variance ** 2) - 3.0)
        else:
            skewness = 0.0
            excess_kurtosis = 0.0

        percentiles = np.percentile(values, [10, 50, 90])
        sorted_values = np.sort(values)
        probabilities = (np.arange(1, sorted_values.size + 1, dtype=np.float64) - 0.5) / sorted_values.size
        if value_std > 0:
            normal_dist = NormalDist(mu=value_mean, sigma=value_std)
            theoretical_quantiles = np.array([normal_dist.inv_cdf(float(prob)) for prob in probabilities], dtype=np.float64)
        else:
            theoretical_quantiles = np.full(sorted_values.shape, value_mean, dtype=np.float64)

        bins = self.parse_distribution_bins()
        min_value = float(np.min(values))
        max_value = float(np.max(values))
        if max_value <= min_value:
            min_value -= 0.5
            max_value += 0.5
        histogram_counts, histogram_edges = np.histogram(values, bins=bins, range=(min_value, max_value))

        return {
            "mode": str(app.graph_view_mode_var.get()).strip(),
            "kind": kind,
            "values": values,
            "selected_index": selected_index,
            "selected_x_px": selected_x_px,
            "selected_x_units": selected_x_units,
            "selected_x_display": selected_x_display,
            "column_input_mode": self.column_input_mode(),
            "column_input_suffix": self.column_input_suffix(),
            "unit_label": unit_label,
            "default_x_label": default_value_label,
            "default_y_label": "Sample Count",
            "mean": value_mean,
            "std": value_std,
            "skewness": skewness,
            "excess_kurtosis": excess_kurtosis,
            "percentiles": percentiles,
            "sorted_values": sorted_values,
            "theoretical_quantiles": theoretical_quantiles,
            "histogram_counts": histogram_counts,
            "histogram_edges": histogram_edges,
        }

    def build_distribution_summary(self, distribution_data):
        if distribution_data.get("all_columns"):
            return (
                f"All columns histogram | valid columns={distribution_data['valid_column_count']}/{distribution_data['column_count']} "
                f"| total samples={distribution_data['sample_count']}\n"
                f"median column std={distribution_data['median_std']:.4g} ({distribution_data['kind']})"
            )

        if distribution_data.get("combined_columns"):
            mean_value = distribution_data["mean"]
            std_value = distribution_data["std"]
            skewness = distribution_data["skewness"]
            excess_kurtosis = distribution_data["excess_kurtosis"]
            p10, p50, p90 = distribution_data["percentiles"]
            return (
                f"Combined all-columns histogram | valid columns={distribution_data['valid_column_count']}/{distribution_data['column_count']} "
                f"| n={distribution_data['sample_count']}\n"
                f"mean={mean_value:.4g} | std={std_value:.4g} | skew={skewness:.4g} | excess kurtosis={excess_kurtosis:.4g}\n"
                f"p10={p10:.4g} | median={p50:.4g} | p90={p90:.4g}"
            )

        selected_x_px = distribution_data["selected_x_px"]
        selected_x_display = distribution_data.get("selected_x_display", selected_x_px)
        selected_suffix = distribution_data.get("column_input_suffix", "px")
        selected_index = distribution_data["selected_index"]
        mean_value = distribution_data["mean"]
        std_value = distribution_data["std"]
        skewness = distribution_data["skewness"]
        excess_kurtosis = distribution_data["excess_kurtosis"]
        p10, p50, p90 = distribution_data["percentiles"]
        return (
            f"Column {selected_x_display:.3g} {selected_suffix} (sample {selected_index}, pixel x={selected_x_px:.3g}px) | "
            f"n={distribution_data['values'].size} | mean={mean_value:.4g} | std={std_value:.4g}\n"
            f"skew={skewness:.4g} | excess kurtosis={excess_kurtosis:.4g}\n"
            f"p10={p10:.4g} | median={p50:.4g} | p90={p90:.4g}"
        )

    def redraw_graph(self):
        self.refresh_distribution_column_controls()
        mode = str(self.app.graph_view_mode_var.get()).strip()
        if mode == "Profile":
            self.redraw_profile_graph()
        else:
            self.redraw_distribution_graph(mode)

    def redraw_profile_graph(self):
        app = self.app
        app.graph_canvas.delete("all")
        app.graph_canvas.config(cursor="")
        w = app.graph_canvas.winfo_width()
        h = app.graph_canvas.winfo_height()
        if w < 50 or h < 50:
            return

        if app.final_mean_profile is None or app.final_std_profile is None:
            app.set_graph_fit_equation_text("Best fit: n/a")
            app.graph_canvas.create_text(
                w // 2,
                h // 2,
                text="Run analysis to generate mean/std graph.",
                fill="gray35",
                font=("TkDefaultFont", 12),
            )
            return

        mean = np.asarray(app.final_mean_profile, dtype=np.float64)
        std = np.asarray(app.final_std_profile, dtype=np.float64)
        if mean.size == 0:
            app.set_graph_fit_equation_text("Best fit: n/a")
            return

        stdevs = self.parse_graph_stdevs()
        safe_std = np.where(np.isfinite(std), std, 0.0)
        upper = mean + stdevs * safe_std
        lower = mean - stdevs * safe_std
        valid = np.isfinite(mean)

        if not np.any(valid):
            app.set_graph_fit_equation_text("Best fit: n/a")
            app.graph_canvas.create_text(
                w // 2,
                h // 2,
                text="No valid centerline data to plot.",
                fill="gray35",
                font=("TkDefaultFont", 12),
            )
            return

        valid_idx = np.where(valid)[0]
        x_all_values = np.array(
            [self.profile_x_value(self.profile_index_to_x_px(i)) for i in range(mean.size)],
            dtype=np.float64,
        )
        mean_values = np.full(mean.shape, np.nan, dtype=np.float64)
        upper_values = np.full(mean.shape, np.nan, dtype=np.float64)
        lower_values = np.full(mean.shape, np.nan, dtype=np.float64)
        for idx in valid_idx:
            mean_values[idx] = float(self.profile_y_value(mean[idx]))
            upper_values[idx] = float(self.profile_y_value(upper[idx]))
            lower_values[idx] = float(self.profile_y_value(lower[idx]))

        y_range_values = np.concatenate((upper_values[valid], lower_values[valid]))
        limits = self.resolve_axis_limits(x_all_values[valid], y_range_values, y_pad=1.0)
        if limits is None:
            app.set_graph_fit_equation_text("Best fit: n/a")
            return
        x_min, x_max, y_min, y_max = limits

        left = 110
        right = 20
        top = 28
        bottom = 62
        plot_w = max(1, w - left - right)
        plot_h = max(1, h - top - bottom)

        def x_to_px(x_value):
            if x_max <= x_min:
                return left + (plot_w / 2.0)
            return left + ((x_value - x_min) / (x_max - x_min)) * plot_w

        def y_to_px(y_value):
            return top + ((y_max - y_value) / (y_max - y_min)) * plot_h

        app.graph_canvas.create_rectangle(left, top, left + plot_w, top + plot_h, fill="white", outline="")
        app.graph_canvas.create_line(left, top + plot_h, left + plot_w, top + plot_h, fill="black")
        app.graph_canvas.create_line(left, top, left, top + plot_h, fill="black")

        y_ticks = 5
        for i in range(y_ticks + 1):
            frac = i / y_ticks
            y_val = y_min + (y_max - y_min) * frac
            y_px = y_to_px(y_val)
            app.graph_canvas.create_line(left - 5, y_px, left, y_px, fill="black")
            y_tags = ()
            if i == 0:
                y_tags = ("graph_edit_y_min_tick",)
            elif i == y_ticks:
                y_tags = ("graph_edit_y_max_tick",)
            app.graph_canvas.create_text(
                left - 8,
                y_px,
                text=self.format_graph_value(y_val),
                anchor="e",
                fill="black",
                font=("TkDefaultFont", 9),
                tags=y_tags,
            )

        x_ticks = 6
        for i in range(x_ticks):
            frac = i / max(1, (x_ticks - 1))
            x_val = x_min + frac * (x_max - x_min)
            x_px = x_to_px(x_val)
            app.graph_canvas.create_line(x_px, top + plot_h, x_px, top + plot_h + 5, fill="black")
            x_tags = ()
            if i == 0:
                x_tags = ("graph_edit_x_min_tick",)
            elif i == (x_ticks - 1):
                x_tags = ("graph_edit_x_max_tick",)
            app.graph_canvas.create_text(
                x_px,
                top + plot_h + 16,
                text=self.format_graph_value(x_val),
                fill="black",
                font=("TkDefaultFont", 9),
                tags=x_tags,
            )

        band_points = []
        for idx in valid_idx:
            band_points.extend((x_to_px(x_all_values[idx]), y_to_px(upper_values[idx])))
        for idx in valid_idx[::-1]:
            band_points.extend((x_to_px(x_all_values[idx]), y_to_px(lower_values[idx])))
        if len(band_points) >= 6:
            app.graph_canvas.create_polygon(band_points, fill="#cfe8ff", outline="")

        mean_points = []
        for idx in valid_idx:
            mean_points.extend((x_to_px(x_all_values[idx]), y_to_px(mean_values[idx])))
        if len(mean_points) >= 4:
            app.graph_canvas.create_line(mean_points, fill="#005fbd", width=2)

        if app.show_best_fit_var.get():
            fit = self.compute_best_fit(mean, valid)
            if fit is not None:
                fit_points = []
                for idx in valid_idx:
                    fit_y_value = float(self.profile_y_value(fit["y_fit"][idx]))
                    fit_points.extend((x_to_px(x_all_values[idx]), y_to_px(fit_y_value)))
                if len(fit_points) >= 4:
                    app.graph_canvas.create_line(fit_points, fill="#d62728", width=2, dash=(6, 4))
                app.set_graph_fit_equation_text(fit["equation"])
            else:
                app.set_graph_fit_equation_text("Best fit: n/a")
        else:
            app.set_graph_fit_equation_text("Best fit: hidden")

        app.graph_canvas.create_text(
            w // 2,
            10,
            text=self.resolve_graph_title(f"Final Mean Centerline with +/- {stdevs:g}sigma Band ({self.profile_axis_unit_label()})"),
            fill="black",
            anchor="n",
            font=("TkDefaultFont", 11, "bold"),
            tags=("graph_edit_title",),
        )
        self._bind_graph_edit_action("graph_edit_title", self.edit_graph_title)
        self._draw_editable_axis_controls(left, top, plot_w, plot_h)

    def redraw_distribution_graph(self, mode):
        app = self.app
        app.graph_canvas.delete("all")
        app.graph_canvas.config(cursor="")
        w = app.graph_canvas.winfo_width()
        h = app.graph_canvas.winfo_height()
        if w < 50 or h < 50:
            return

        distribution_data = self.build_distribution_data()
        if distribution_data is None:
            app.set_graph_fit_equation_text("Distribution data: n/a")
            app.graph_canvas.create_text(
                w // 2,
                h // 2,
                text="Run video analysis first to collect per-frame samples for histogram and Q-Q views.",
                fill="gray35",
                font=("TkDefaultFont", 12),
                width=max(200, w - 80),
            )
            return

        app.set_graph_fit_equation_text(self.build_distribution_summary(distribution_data))

        left = 110
        right = 20
        top = 28
        bottom = 62
        plot_w = max(1, w - left - right)
        plot_h = max(1, h - top - bottom)

        if mode == "Histogram":
            if distribution_data.get("all_columns"):
                edges = distribution_data["histogram_edges"]
                counts_matrix = distribution_data["histogram_matrix"]
                x_column_display = distribution_data["x_column_display"]
                max_count = int(np.max(counts_matrix)) if counts_matrix.size > 0 else 0
                if max_count <= 0:
                    return

                if x_column_display.size == 1:
                    column_span = 1.0
                    x_edges = np.array([x_column_display[0] - 0.5 * column_span, x_column_display[0] + 0.5 * column_span], dtype=np.float64)
                else:
                    midpoints = 0.5 * (x_column_display[:-1] + x_column_display[1:])
                    first_edge = x_column_display[0] - (midpoints[0] - x_column_display[0])
                    last_edge = x_column_display[-1] + (x_column_display[-1] - midpoints[-1])
                    x_edges = np.concatenate(([first_edge], midpoints, [last_edge]))

                x_min = float(x_edges[0])
                x_max = float(x_edges[-1])
                y_min = float(edges[0])
                y_max = float(edges[-1])

                def x_to_px(x_value):
                    return left + ((x_value - x_min) / (x_max - x_min)) * plot_w if x_max > x_min else left + (plot_w / 2.0)

                def y_to_px(y_value):
                    return top + ((y_max - y_value) / max(y_max - y_min, 1.0)) * plot_h

                def heat_color(norm_value):
                    norm = max(0.0, min(1.0, float(norm_value)))
                    red = int(round(248 - 184 * norm))
                    green = int(round(251 - 196 * norm))
                    blue = int(round(255 - 21 * norm))
                    return f"#{red:02x}{green:02x}{blue:02x}"

                app.graph_canvas.create_rectangle(left, top, left + plot_w, top + plot_h, fill="white", outline="")
                app.graph_canvas.create_line(left, top + plot_h, left + plot_w, top + plot_h, fill="black")
                app.graph_canvas.create_line(left, top, left, top + plot_h, fill="black")

                for col_idx in range(counts_matrix.shape[0]):
                    x0 = x_to_px(float(x_edges[col_idx]))
                    x1 = x_to_px(float(x_edges[col_idx + 1]))
                    for bin_idx in range(counts_matrix.shape[1]):
                        count = int(counts_matrix[col_idx, bin_idx])
                        if count <= 0:
                            continue
                        y0 = y_to_px(float(edges[bin_idx + 1]))
                        y1 = y_to_px(float(edges[bin_idx]))
                        app.graph_canvas.create_rectangle(
                            x0,
                            y0,
                            x1,
                            y1,
                            fill=heat_color(count / max_count),
                            outline="",
                        )

                y_ticks = 5
                for i in range(y_ticks + 1):
                    frac = i / y_ticks
                    y_val = y_min + (y_max - y_min) * frac
                    y_px = y_to_px(y_val)
                    app.graph_canvas.create_line(left - 5, y_px, left, y_px, fill="black")
                    y_tags = ()
                    if i == 0:
                        y_tags = ("graph_edit_y_min_tick",)
                    elif i == y_ticks:
                        y_tags = ("graph_edit_y_max_tick",)
                    app.graph_canvas.create_text(left - 8, y_px, text=self.format_graph_value(y_val), anchor="e", fill="black", font=("TkDefaultFont", 9), tags=y_tags)

                x_ticks = 6
                for i in range(x_ticks):
                    frac = i / max(1, (x_ticks - 1))
                    x_val = x_min + frac * (x_max - x_min)
                    x_px = x_to_px(x_val)
                    app.graph_canvas.create_line(x_px, top + plot_h, x_px, top + plot_h + 5, fill="black")
                    x_tags = ()
                    if i == 0:
                        x_tags = ("graph_edit_x_min_tick",)
                    elif i == (x_ticks - 1):
                        x_tags = ("graph_edit_x_max_tick",)
                    app.graph_canvas.create_text(x_px, top + plot_h + 16, text=self.format_graph_value(x_val), fill="black", font=("TkDefaultFont", 9), tags=x_tags)

                title = (
                    f"Histogram Heatmap of {distribution_data['kind']} Across Columns "
                    f"({distribution_data['sample_count']} samples)"
                )
                x_axis_text = distribution_data["default_x_label"]
                y_axis_text = distribution_data["default_y_label"]
                app.graph_canvas.create_text(left + 8, top + 12, text="Darker color = higher count", anchor="w", fill="gray30", font=("TkDefaultFont", 9))
            else:
                edges = distribution_data["histogram_edges"]
                counts = distribution_data["histogram_counts"]
                limits = self.resolve_axis_limits(edges, np.append(counts, 0), y_pad=1.0)
                if limits is None:
                    return
                x_min, x_max, _y_min, y_max = limits
                y_min = 0.0

                def x_to_px(x_value):
                    return left + ((x_value - x_min) / (x_max - x_min)) * plot_w if x_max > x_min else left + (plot_w / 2.0)

                def y_to_px(y_value):
                    return top + ((y_max - y_value) / max(y_max - y_min, 1.0)) * plot_h

                app.graph_canvas.create_rectangle(left, top, left + plot_w, top + plot_h, fill="white", outline="")
                app.graph_canvas.create_line(left, top + plot_h, left + plot_w, top + plot_h, fill="black")
                app.graph_canvas.create_line(left, top, left, top + plot_h, fill="black")

                for idx, count in enumerate(counts):
                    x0 = x_to_px(edges[idx])
                    x1 = x_to_px(edges[idx + 1])
                    y1 = y_to_px(float(count))
                    app.graph_canvas.create_rectangle(x0, y1, x1, top + plot_h, fill="#cfe8ff", outline="#4a7ebb")

                y_ticks = 5
                for i in range(y_ticks + 1):
                    frac = i / y_ticks
                    y_val = y_min + (y_max - y_min) * frac
                    y_px = y_to_px(y_val)
                    app.graph_canvas.create_line(left - 5, y_px, left, y_px, fill="black")
                    y_tags = ()
                    if i == 0:
                        y_tags = ("graph_edit_y_min_tick",)
                    elif i == y_ticks:
                        y_tags = ("graph_edit_y_max_tick",)
                    app.graph_canvas.create_text(left - 8, y_px, text=self.format_graph_value(y_val), anchor="e", fill="black", font=("TkDefaultFont", 9), tags=y_tags)

                x_ticks = 6
                for i in range(x_ticks):
                    frac = i / max(1, (x_ticks - 1))
                    x_val = x_min + frac * (x_max - x_min)
                    x_px = x_to_px(x_val)
                    app.graph_canvas.create_line(x_px, top + plot_h, x_px, top + plot_h + 5, fill="black")
                    x_tags = ()
                    if i == 0:
                        x_tags = ("graph_edit_x_min_tick",)
                    elif i == (x_ticks - 1):
                        x_tags = ("graph_edit_x_max_tick",)
                    app.graph_canvas.create_text(x_px, top + plot_h + 16, text=self.format_graph_value(x_val), fill="black", font=("TkDefaultFont", 9), tags=x_tags)

                std_value = distribution_data["std"]
                if std_value > 0:
                    x_curve = np.linspace(x_min, x_max, 200)
                    bin_width = edges[1] - edges[0] if len(edges) > 1 else 1.0
                    normal_curve = np.array([
                        distribution_data["values"].size * bin_width * NormalDist(mu=distribution_data["mean"], sigma=std_value).pdf(float(x_val))
                        for x_val in x_curve
                    ], dtype=np.float64)
                    curve_points = []
                    for x_val, y_val in zip(x_curve, normal_curve):
                        curve_points.extend((x_to_px(float(x_val)), y_to_px(float(y_val))))
                    if len(curve_points) >= 4:
                        app.graph_canvas.create_line(curve_points, fill="#d62728", width=2, smooth=True)

                if distribution_data.get("combined_columns"):
                    title = (
                        f"Histogram of {distribution_data['kind']} Across All Columns "
                        f"({distribution_data['values'].size} samples)"
                    )
                else:
                    title = (
                        f"Histogram of {distribution_data['kind']} at x={distribution_data['selected_x_display']:.3g} "
                        f"{distribution_data.get('column_input_suffix', 'px')} "
                        f"({distribution_data['values'].size} samples)"
                    )
                x_axis_text = distribution_data["default_x_label"]
                y_axis_text = distribution_data["default_y_label"]
        else:
            theoretical = distribution_data["theoretical_quantiles"]
            observed = distribution_data["sorted_values"]
            combined = np.concatenate((theoretical, observed))
            limits = self.resolve_axis_limits(combined, combined, y_pad=1.0)
            if limits is None:
                return
            x_min, x_max, y_min, y_max = limits

            def x_to_px(x_value):
                return left + ((x_value - x_min) / (x_max - x_min)) * plot_w if x_max > x_min else left + (plot_w / 2.0)

            def y_to_px(y_value):
                return top + ((y_max - y_value) / max(y_max - y_min, 1.0)) * plot_h

            app.graph_canvas.create_rectangle(left, top, left + plot_w, top + plot_h, fill="white", outline="")
            app.graph_canvas.create_line(left, top + plot_h, left + plot_w, top + plot_h, fill="black")
            app.graph_canvas.create_line(left, top, left, top + plot_h, fill="black")

            diag_start_x = max(x_min, y_min)
            diag_end_x = min(x_max, y_max)
            if diag_end_x > diag_start_x:
                app.graph_canvas.create_line(
                    x_to_px(diag_start_x),
                    y_to_px(diag_start_x),
                    x_to_px(diag_end_x),
                    y_to_px(diag_end_x),
                    fill="#999999",
                    dash=(4, 3),
                )

            for x_val, y_val in zip(theoretical, observed):
                x_px = x_to_px(float(x_val))
                y_px = y_to_px(float(y_val))
                app.graph_canvas.create_oval(x_px - 2, y_px - 2, x_px + 2, y_px + 2, fill="#005fbd", outline="")

            y_ticks = 5
            for i in range(y_ticks + 1):
                frac = i / y_ticks
                y_val = y_min + (y_max - y_min) * frac
                y_px = y_to_px(y_val)
                app.graph_canvas.create_line(left - 5, y_px, left, y_px, fill="black")
                y_tags = ()
                if i == 0:
                    y_tags = ("graph_edit_y_min_tick",)
                elif i == y_ticks:
                    y_tags = ("graph_edit_y_max_tick",)
                app.graph_canvas.create_text(left - 8, y_px, text=self.format_graph_value(y_val), anchor="e", fill="black", font=("TkDefaultFont", 9), tags=y_tags)

            x_ticks = 6
            for i in range(x_ticks):
                frac = i / max(1, (x_ticks - 1))
                x_val = x_min + frac * (x_max - x_min)
                x_px = x_to_px(x_val)
                app.graph_canvas.create_line(x_px, top + plot_h, x_px, top + plot_h + 5, fill="black")
                x_tags = ()
                if i == 0:
                    x_tags = ("graph_edit_x_min_tick",)
                elif i == (x_ticks - 1):
                    x_tags = ("graph_edit_x_max_tick",)
                app.graph_canvas.create_text(x_px, top + plot_h + 16, text=self.format_graph_value(x_val), fill="black", font=("TkDefaultFont", 9), tags=x_tags)

            if distribution_data.get("combined_columns"):
                title = f"Normal Q-Q Plot of {distribution_data['kind']} Across All Columns"
            else:
                title = (
                    f"Normal Q-Q Plot of {distribution_data['kind']} at x={distribution_data['selected_x_display']:.3g} "
                    f"{distribution_data.get('column_input_suffix', 'px')}"
                )
            x_axis_text = app.graph_x_axis_label.get().strip() or "Theoretical Normal Quantile"
            y_axis_text = app.graph_y_axis_label.get().strip() or "Observed Quantile"

        app.graph_canvas.create_text(
            w // 2,
            10,
            text=self.resolve_graph_title(title),
            fill="black",
            anchor="n",
            font=("TkDefaultFont", 11, "bold"),
            tags=("graph_edit_title",),
        )
        self._bind_graph_edit_action("graph_edit_title", self.edit_graph_title)
        # Keep vars synced with the currently active graph labels so canvas editing always targets visible labels.
        if not app.graph_x_axis_label.get().strip():
            app.graph_x_axis_label.set(x_axis_text)
        if not app.graph_y_axis_label.get().strip():
            app.graph_y_axis_label.set(y_axis_text)
        self._draw_editable_axis_controls(left, top, plot_w, plot_h)

    def build_plot_data(self):
        app = self.app
        if app.final_mean_profile is None or app.final_std_profile is None:
            return None
        mean = np.asarray(app.final_mean_profile, dtype=np.float64)
        std = np.asarray(app.final_std_profile, dtype=np.float64)
        if mean.size == 0:
            return None
        stdevs = self.parse_graph_stdevs()
        safe_std = np.where(np.isfinite(std), std, 0.0)
        upper = mean + stdevs * safe_std
        lower = mean - stdevs * safe_std
        valid = np.isfinite(mean)
        if not np.any(valid):
            return None
        x_all_values = np.array(
            [self.profile_x_value(self.profile_index_to_x_px(i)) for i in range(mean.size)],
            dtype=np.float64,
        )
        mean_values = np.full(mean.shape, np.nan, dtype=np.float64)
        upper_values = np.full(mean.shape, np.nan, dtype=np.float64)
        lower_values = np.full(mean.shape, np.nan, dtype=np.float64)
        valid_idx = np.where(valid)[0]
        for idx in valid_idx:
            mean_values[idx] = float(self.profile_y_value(mean[idx]))
            upper_values[idx] = float(self.profile_y_value(upper[idx]))
            lower_values[idx] = float(self.profile_y_value(lower[idx]))
        return {
            "mean": mean,
            "upper": upper,
            "lower": lower,
            "valid": valid,
            "stdevs": stdevs,
            "x_all_values": x_all_values,
            "mean_values": mean_values,
            "upper_values": upper_values,
            "lower_values": lower_values,
        }

    def build_graph_export_rows(self):
        app = self.app
        plot_data = self.build_plot_data()
        if plot_data is None:
            return None

        mean = plot_data["mean"]
        upper = plot_data["upper"]
        lower = plot_data["lower"]
        valid = plot_data["valid"]
        stdevs = plot_data["stdevs"]
        std = np.asarray(app.final_std_profile, dtype=np.float64)
        fit = self.compute_best_fit(mean, valid)

        unit_label = (app.graph_unit_label or "px").strip()
        unit_suffix = unit_label.lower()

        pixel_header = [
            "column_px",
            "mean_y_graph_px",
            "lower_band_y_graph_px",
            "upper_band_y_graph_px",
            "fit_y_graph_px",
        ]
        unit_header = [
            f"column_{unit_suffix}",
            f"mean_y_{unit_suffix}",
            f"lower_band_y_{unit_suffix}",
            f"upper_band_y_{unit_suffix}",
            f"fit_y_{unit_suffix}",
        ]

        rows = []
        for idx in range(mean.size):
            is_valid = bool(valid[idx])
            # Skip rows with no data
            if not is_valid:
                continue
            
            x_px = self.profile_index_to_x_px(idx)
            mean_raw_px = float(mean[idx])
            mean_px = self.y_position_to_graph_pixels(mean_raw_px)
            std_px = float(std[idx]) if np.isfinite(std[idx]) else 0.0
            lower_raw_px = float(lower[idx])
            upper_raw_px = float(upper[idx])
            lower_px = self.y_position_to_graph_pixels(lower_raw_px)
            upper_px = self.y_position_to_graph_pixels(upper_raw_px)
            mean_unit = float(self.y_position_to_graph_units(mean_raw_px))
            std_unit = float(self.y_delta_to_graph_units(std_px))
            lower_unit = float(self.y_position_to_graph_units(lower_raw_px))
            upper_unit = float(self.y_position_to_graph_units(upper_raw_px))
            if fit is not None:
                fit_raw_px = float(fit["y_fit"][idx])
                fit_px = self.y_position_to_graph_pixels(fit_raw_px)
                fit_unit = float(self.y_position_to_graph_units(fit_raw_px))
            else:
                fit_px = ""
                fit_unit = ""

            rows.append(
                {
                    "pixel": [
                        x_px,
                        mean_px,
                        lower_px,
                        upper_px,
                        fit_px,
                    ],
                    "unit": [
                        float(self.x_position_to_graph_units(x_px)),
                        mean_unit,
                        lower_unit,
                        upper_unit,
                        fit_unit,
                    ],
                }
            )

        metadata = [
            ["export_type", "graph_profile"],
            ["unit_label", unit_label],
            ["pixel_y_reference", "graph_oriented"],
            ["unit_scale", f"{app.graph_unit_scale:.12g}"],
            ["stdev_multiplier", f"{stdevs:g}"],
            ["fit_degree", str(fit["degree"]) if fit is not None else ""],
            ["fit_equation", fit["equation"] if fit is not None else "n/a"],
            ["nozzle_origin_y_px", f"{app.nozzle_origin_img[1]:.6g}" if app.nozzle_origin_img is not None else ""],
            ["source_video", app.video_path.get().strip()],
            ["generated_at", datetime.now().isoformat(timespec="seconds")],
        ]

        return {
            "metadata": metadata,
            "pixel_header": pixel_header,
            "unit_header": unit_header,
            "rows": rows,
        }

    def _build_combined_distribution_export(self, samples):
        """Always export combined-columns distribution with all three transform columns."""
        samples = np.asarray(samples, dtype=np.float64)
        if samples.ndim != 2 or samples.shape[0] == 0 or samples.shape[1] == 0:
            return None

        col_count = samples.shape[1]
        positions_list = []
        residuals_list = []
        zscores_list = []
        valid_columns = 0

        for col_idx in range(col_count):
            raw_px = samples[:, col_idx]
            raw_px = raw_px[np.isfinite(raw_px)]
            if raw_px.size < 3:
                continue

            raw_mean = float(np.mean(raw_px))
            raw_std = float(np.std(raw_px))

            pos_vals = np.array(
                [float(self.profile_y_value(v)) for v in raw_px], dtype=np.float64
            )
            residual_px = raw_px - raw_mean
            res_vals = np.array(
                [float(self.profile_y_delta_value(v)) for v in residual_px], dtype=np.float64
            )
            if raw_std > 0:
                z_vals = (raw_px - raw_mean) / raw_std
            else:
                z_vals = np.zeros_like(raw_px)

            # Use a common finite mask so all three arrays are aligned row-for-row
            finite_mask = np.isfinite(pos_vals) & np.isfinite(res_vals) & np.isfinite(z_vals)
            if np.sum(finite_mask) < 3:
                continue

            positions_list.append(pos_vals[finite_mask])
            residuals_list.append(res_vals[finite_mask])
            zscores_list.append(z_vals[finite_mask])
            valid_columns += 1

        if not positions_list:
            return None

        all_positions = np.concatenate(positions_list)
        all_residuals = np.concatenate(residuals_list)
        all_zscores = np.concatenate(zscores_list)
        n = all_zscores.size

        z_mean = float(np.mean(all_zscores))
        z_std = float(np.std(all_zscores))
        sorted_z = np.sort(all_zscores)
        probabilities = (np.arange(1, n + 1, dtype=np.float64) - 0.5) / n
        if z_std > 0:
            normal_dist = NormalDist(mu=z_mean, sigma=z_std)
            theoretical = np.array(
                [normal_dist.inv_cdf(float(p)) for p in probabilities], dtype=np.float64
            )
        else:
            theoretical = np.full(n, z_mean, dtype=np.float64)

        # Sort all columns by z-score order so the Q-Q theoretical column aligns
        sort_order = np.argsort(all_zscores)
        all_positions = all_positions[sort_order]
        all_residuals = all_residuals[sort_order]
        all_zscores = all_zscores[sort_order]

        rows = [
            [
                idx,
                float(all_positions[idx]),
                float(all_residuals[idx]),
                float(all_zscores[idx]),
                float(theoretical[idx]),
            ]
            for idx in range(n)
        ]

        z_centered = all_zscores - z_mean
        z_var = float(np.mean(z_centered ** 2))
        skewness = float(np.mean(z_centered ** 3) / (z_var ** 1.5)) if z_var > 0 else 0.0
        excess_kurtosis = float(np.mean(z_centered ** 4) / (z_var ** 2) - 3.0) if z_var > 0 else 0.0

        unit_label = (getattr(self.app, "graph_unit_label", None) or "px").strip()
        metadata = [
            ["export_type", "graph_distribution"],
            ["combined_columns", "true"],
            ["column_count", str(col_count)],
            ["valid_column_count", str(valid_columns)],
            ["sample_count", str(n)],
            ["z_score_mean", f"{z_mean:.12g}"],
            ["z_score_std", f"{z_std:.12g}"],
            ["z_score_skewness", f"{skewness:.12g}"],
            ["z_score_excess_kurtosis", f"{excess_kurtosis:.12g}"],
            ["position_unit", unit_label],
            ["residual_unit", unit_label],
            ["generated_at", datetime.now().isoformat(timespec="seconds")],
        ]

        return {
            "metadata": metadata,
            "header": [
                "sample_index",
                f"position_{unit_label}",
                f"residual_{unit_label}",
                "z_score",
                "theoretical_normal_quantile",
            ],
            "rows": rows,
        }

    def build_distribution_export_rows(self):
        distribution_data = self.build_distribution_data()
        if distribution_data is None:
            return None

        if distribution_data.get("all_columns"):
            rows = []
            histogram_matrix = distribution_data["histogram_matrix"]
            histogram_edges = distribution_data["histogram_edges"]
            x_column_px = distribution_data["x_column_px"]
            x_column_units = distribution_data["x_column_units"]
            for col_idx in range(histogram_matrix.shape[0]):
                for bin_idx in range(histogram_matrix.shape[1]):
                    rows.append([
                        col_idx,
                        float(x_column_px[col_idx]),
                        float(x_column_units[col_idx]),
                        float(histogram_edges[bin_idx]),
                        float(histogram_edges[bin_idx + 1]),
                        int(histogram_matrix[col_idx, bin_idx]),
                    ])

            metadata = [
                ["export_type", "graph_distribution_heatmap"],
                ["graph_view_mode", distribution_data["mode"]],
                ["distribution_kind", distribution_data["kind"]],
                ["column_input_mode", distribution_data.get("column_input_mode", "Pixel Values")],
                ["column_count", str(distribution_data["column_count"])],
                ["valid_column_count", str(distribution_data["valid_column_count"])],
                ["total_sample_count", str(distribution_data["sample_count"])],
                ["generated_at", datetime.now().isoformat(timespec="seconds")],
            ]

            return {
                "metadata": metadata,
                "header": ["column_index", "column_px", "column_unit", "bin_start", "bin_end", "count"],
                "rows": rows,
            }

        extra_tables = []
        if distribution_data.get("mode") == "Histogram":
            histogram_rows = []
            histogram_counts = distribution_data.get("histogram_counts")
            histogram_edges = distribution_data.get("histogram_edges")
            if histogram_counts is not None and histogram_edges is not None:
                for bin_index, count in enumerate(histogram_counts):
                    histogram_rows.append([
                        int(bin_index),
                        float(histogram_edges[bin_index]),
                        float(histogram_edges[bin_index + 1]),
                        int(count),
                    ])
            if histogram_rows:
                extra_tables.append(
                    {
                        "title": "Histogram Bin Counts",
                        "header": ["bin_index", "bin_start", "bin_end", "count"],
                        "rows": histogram_rows,
                    }
                )

        rows = []
        values = distribution_data["values"]
        sorted_values = distribution_data["sorted_values"]
        theoretical = distribution_data["theoretical_quantiles"]
        row_count = max(values.size, sorted_values.size)
        for idx in range(row_count):
            rows.append([
                idx,
                float(values[idx]) if idx < values.size else "",
                float(theoretical[idx]) if idx < theoretical.size else "",
            ])

        metadata = [
            ["export_type", "graph_distribution"],
            ["graph_view_mode", distribution_data["mode"]],
            ["distribution_kind", distribution_data["kind"]],
            ["sample_count", str(values.size)],
            ["mean", f"{distribution_data['mean']:.12g}"],
            ["std", f"{distribution_data['std']:.12g}"],
            ["skewness", f"{distribution_data['skewness']:.12g}"],
            ["excess_kurtosis", f"{distribution_data['excess_kurtosis']:.12g}"],
            ["generated_at", datetime.now().isoformat(timespec="seconds")],
        ]

        if distribution_data.get("combined_columns"):
            metadata.insert(3, ["combined_columns", "true"])
            metadata.insert(4, ["column_count", str(distribution_data["column_count"])])
            metadata.insert(5, ["valid_column_count", str(distribution_data["valid_column_count"])])
        else:
            metadata.insert(3, ["selected_column_px", f"{distribution_data['selected_x_px']:.12g}"])
            metadata.insert(4, ["selected_column_unit", f"{distribution_data['selected_x_units']:.12g}"])
            metadata.insert(5, ["selected_column_display", f"{distribution_data.get('selected_x_display', distribution_data['selected_x_px']):.12g}"])
            metadata.insert(6, ["column_input_mode", distribution_data.get("column_input_mode", "Pixel Values")])

        export_payload = {
            "metadata": metadata,
            "header": ["sample_index", "value", "theoretical_normal_quantile"],
            "rows": rows,
        }
        if extra_tables:
            export_payload["extra_tables"] = extra_tables
        return export_payload

    def _draw_centered_text_cv(self, image, text, center_x, baseline_y, font_scale=0.55, thickness=1, color=(0, 0, 0)):
        label = str(text)
        (text_w, _text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        text_x = int(round(center_x - (text_w / 2.0)))
        cv2.putText(image, label, (max(0, text_x), int(baseline_y)), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)

    def _draw_vertical_text_cv(self, image, text, x_left, center_y, font_scale=0.55, thickness=1, color=(0, 0, 0)):
        label = str(text)
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        temp_h = max(1, text_h + baseline + 8)
        temp_w = max(1, text_w + 8)
        temp = np.full((temp_h, temp_w, 3), 255, dtype=np.uint8)
        cv2.putText(temp, label, (2, text_h + 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)
        rotated = cv2.rotate(temp, cv2.ROTATE_90_COUNTERCLOCKWISE)

        y_start = int(round(center_y - (rotated.shape[0] / 2.0)))
        x_start = int(x_left)
        y_end = y_start + rotated.shape[0]
        x_end = x_start + rotated.shape[1]

        clip_y0 = max(0, y_start)
        clip_x0 = max(0, x_start)
        clip_y1 = min(image.shape[0], y_end)
        clip_x1 = min(image.shape[1], x_end)
        if clip_y1 <= clip_y0 or clip_x1 <= clip_x0:
            return

        src_y0 = clip_y0 - y_start
        src_x0 = clip_x0 - x_start
        src_y1 = src_y0 + (clip_y1 - clip_y0)
        src_x1 = src_x0 + (clip_x1 - clip_x0)
        src = rotated[src_y0:src_y1, src_x0:src_x1]
        dst = image[clip_y0:clip_y1, clip_x0:clip_x1]
        mask = np.any(src < 250, axis=2)
        dst[mask] = src[mask]

    def _draw_right_aligned_text_cv(self, image, text, right_x, baseline_y, font_scale=0.45, thickness=1, color=(0, 0, 0)):
        label = str(text)
        (text_w, _text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        text_x = int(round(right_x - text_w))
        cv2.putText(image, label, (max(0, text_x), int(baseline_y)), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)

    def render_graph_image(self, width=1600, height=1000):
        if str(self.app.graph_view_mode_var.get()).strip() != "Profile":
            return self.render_distribution_graph_image(width=width, height=height)

        app = self.app
        plot_data = self.build_plot_data()
        if plot_data is None:
            return None
        mean = plot_data["mean"]
        upper = plot_data["upper"]
        lower = plot_data["lower"]
        valid = plot_data["valid"]
        stdevs = plot_data["stdevs"]
        x_all_values = plot_data["x_all_values"]
        mean_values = plot_data["mean_values"]
        upper_values = plot_data["upper_values"]
        lower_values = plot_data["lower_values"]
        valid_idx = np.where(valid)[0]

        image = np.full((height, width, 3), 255, dtype=np.uint8)
        left, right, top, bottom = 140, 30, 50, 110
        plot_w = max(1, width - left - right)
        plot_h = max(1, height - top - bottom)

        y_range_values = np.concatenate((upper_values[valid], lower_values[valid]))
        limits = self.resolve_axis_limits(x_all_values[valid], y_range_values, y_pad=1.0)
        if limits is None:
            return None
        x_min, x_max, y_min, y_max = limits

        def x_to_px(x_value):
            if x_max <= x_min:
                return int(left + (plot_w / 2.0))
            return int(round(left + ((x_value - x_min) / (x_max - x_min)) * plot_w))

        def y_to_px(y_value):
            return int(round(top + ((y_max - y_value) / (y_max - y_min)) * plot_h))

        cv2.line(image, (left, top + plot_h), (left + plot_w, top + plot_h), (0, 0, 0), 1)
        cv2.line(image, (left, top), (left, top + plot_h), (0, 0, 0), 1)

        y_ticks = 5
        for i in range(y_ticks + 1):
            frac = i / y_ticks
            y_val = y_min + (y_max - y_min) * frac
            y_px = y_to_px(y_val)
            cv2.line(image, (left - 6, y_px), (left, y_px), (0, 0, 0), 1)
            label = self.format_graph_value(y_val)
            self._draw_right_aligned_text_cv(image, label, left - 10, y_px + 4)

        x_ticks = 6
        for i in range(x_ticks):
            frac = i / max(1, (x_ticks - 1))
            x_val = x_min + frac * (x_max - x_min)
            x_px = x_to_px(x_val)
            cv2.line(image, (x_px, top + plot_h), (x_px, top + plot_h + 6), (0, 0, 0), 1)
            cv2.putText(
                image,
                self.format_graph_value(x_val),
                (x_px - 12, top + plot_h + 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

        upper_pts = np.array([(x_to_px(x_all_values[idx]), y_to_px(upper_values[idx])) for idx in valid_idx], dtype=np.int32)
        lower_pts = np.array([(x_to_px(x_all_values[idx]), y_to_px(lower_values[idx])) for idx in valid_idx[::-1]], dtype=np.int32)
        band_poly = np.vstack((upper_pts, lower_pts))
        if band_poly.shape[0] >= 3:
            cv2.fillPoly(image, [band_poly], (255, 232, 207))

        mean_pts = np.array([(x_to_px(x_all_values[idx]), y_to_px(mean_values[idx])) for idx in valid_idx], dtype=np.int32)
        if mean_pts.shape[0] >= 2:
            cv2.polylines(image, [mean_pts], False, (189, 95, 0), 2)

        if app.show_best_fit_var.get():
            fit = self.compute_best_fit(mean, valid)
            if fit is not None:
                fit_pts = np.array(
                    [
                        (x_to_px(x_all_values[idx]), y_to_px(float(self.profile_y_value(fit["y_fit"][idx]))))
                        for idx in valid_idx
                    ],
                    dtype=np.int32,
                )
                if fit_pts.shape[0] >= 2:
                    cv2.polylines(image, [fit_pts], False, (40, 40, 220), 2)
                cv2.putText(
                    image,
                    fit["equation"],
                    (left, top + 44),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (40, 40, 40),
                    1,
                    cv2.LINE_AA,
                )

        title = self.resolve_graph_title(f"Final Mean Centerline with +/- {stdevs:g}sigma Band ({self.profile_axis_unit_label()})")
        self._draw_centered_text_cv(image, title, width // 2, 30, font_scale=0.62, thickness=1)
        x_axis_text = app.graph_x_axis_label.get().strip() or self.profile_default_x_axis_label()
        y_axis_text = app.graph_y_axis_label.get().strip() or self.profile_default_y_axis_label()
        self._draw_centered_text_cv(image, x_axis_text, width // 2, height - 28, font_scale=0.55, thickness=1)
        self._draw_vertical_text_cv(image, y_axis_text, 8, top + (plot_h // 2), font_scale=0.55, thickness=1)
        return image

    def render_distribution_graph_image(self, width=1600, height=1000):
        app = self.app
        mode = str(app.graph_view_mode_var.get()).strip()
        distribution_data = self.build_distribution_data()
        if distribution_data is None:
            return None

        image = np.full((height, width, 3), 255, dtype=np.uint8)
        left, right, top, bottom = 140, 30, 50, 110
        plot_w = max(1, width - left - right)
        plot_h = max(1, height - top - bottom)

        if mode == "Histogram":
            if distribution_data.get("all_columns"):
                edges = distribution_data["histogram_edges"]
                counts_matrix = distribution_data["histogram_matrix"]
                x_column_display = distribution_data["x_column_display"]
                max_count = int(np.max(counts_matrix)) if counts_matrix.size > 0 else 0
                if max_count <= 0:
                    return None

                if x_column_display.size == 1:
                    x_edges = np.array([x_column_display[0] - 0.5, x_column_display[0] + 0.5], dtype=np.float64)
                else:
                    midpoints = 0.5 * (x_column_display[:-1] + x_column_display[1:])
                    first_edge = x_column_display[0] - (midpoints[0] - x_column_display[0])
                    last_edge = x_column_display[-1] + (x_column_display[-1] - midpoints[-1])
                    x_edges = np.concatenate(([first_edge], midpoints, [last_edge]))

                x_min = float(x_edges[0])
                x_max = float(x_edges[-1])
                y_min = float(edges[0])
                y_max = float(edges[-1])

                def x_to_px(x_value):
                    if x_max <= x_min:
                        return int(left + (plot_w / 2.0))
                    return int(round(left + ((x_value - x_min) / (x_max - x_min)) * plot_w))

                def y_to_px(y_value):
                    return int(round(top + ((y_max - y_value) / max(y_max - y_min, 1.0)) * plot_h))

                cv2.line(image, (left, top + plot_h), (left + plot_w, top + plot_h), (0, 0, 0), 1)
                cv2.line(image, (left, top), (left, top + plot_h), (0, 0, 0), 1)

                for col_idx in range(counts_matrix.shape[0]):
                    x0 = x_to_px(float(x_edges[col_idx]))
                    x1 = x_to_px(float(x_edges[col_idx + 1]))
                    for bin_idx in range(counts_matrix.shape[1]):
                        count = int(counts_matrix[col_idx, bin_idx])
                        if count <= 0:
                            continue
                        y0 = y_to_px(float(edges[bin_idx + 1]))
                        y1 = y_to_px(float(edges[bin_idx]))
                        norm = max(0.0, min(1.0, count / max_count))
                        color = (
                            int(round(255 - 21 * norm)),
                            int(round(251 - 196 * norm)),
                            int(round(248 - 184 * norm)),
                        )
                        cv2.rectangle(image, (x0, y0), (x1, y1), color, -1)

                y_ticks = 5
                for i in range(y_ticks + 1):
                    frac = i / y_ticks
                    y_val = y_min + (y_max - y_min) * frac
                    y_px = y_to_px(y_val)
                    cv2.line(image, (left - 6, y_px), (left, y_px), (0, 0, 0), 1)
                    self._draw_right_aligned_text_cv(image, self.format_graph_value(y_val), left - 10, y_px + 4)

                x_ticks = 6
                for i in range(x_ticks):
                    frac = i / max(1, (x_ticks - 1))
                    x_val = x_min + frac * (x_max - x_min)
                    x_px = x_to_px(x_val)
                    cv2.line(image, (x_px, top + plot_h), (x_px, top + plot_h + 6), (0, 0, 0), 1)
                    cv2.putText(image, self.format_graph_value(x_val), (x_px - 12, top + plot_h + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

                title = (
                    f"Histogram Heatmap of {distribution_data['kind']} Across Columns "
                    f"({distribution_data['sample_count']} samples)"
                )
                x_axis_text = distribution_data["default_x_label"]
                y_axis_text = distribution_data["default_y_label"]
            else:
                edges = distribution_data["histogram_edges"]
                counts = distribution_data["histogram_counts"]
                limits = self.resolve_axis_limits(edges, np.append(counts, 0), y_pad=1.0)
                if limits is None:
                    return None
                x_min, x_max, _y_min, y_max = limits
                y_min = 0.0

                def x_to_px(x_value):
                    if x_max <= x_min:
                        return int(left + (plot_w / 2.0))
                    return int(round(left + ((x_value - x_min) / (x_max - x_min)) * plot_w))

                def y_to_px(y_value):
                    return int(round(top + ((y_max - y_value) / max(y_max - y_min, 1.0)) * plot_h))

                cv2.line(image, (left, top + plot_h), (left + plot_w, top + plot_h), (0, 0, 0), 1)
                cv2.line(image, (left, top), (left, top + plot_h), (0, 0, 0), 1)

                for idx, count in enumerate(counts):
                    x0 = x_to_px(edges[idx])
                    x1 = x_to_px(edges[idx + 1])
                    y1 = y_to_px(float(count))
                    cv2.rectangle(image, (x0, y1), (x1, top + plot_h), (189, 126, 74), 1)
                    cv2.rectangle(image, (x0, y1), (x1, top + plot_h), (255, 232, 207), -1)
                    cv2.rectangle(image, (x0, y1), (x1, top + plot_h), (189, 126, 74), 1)

                y_ticks = 5
                for i in range(y_ticks + 1):
                    frac = i / y_ticks
                    y_val = y_min + (y_max - y_min) * frac
                    y_px = y_to_px(y_val)
                    cv2.line(image, (left - 6, y_px), (left, y_px), (0, 0, 0), 1)
                    self._draw_right_aligned_text_cv(image, self.format_graph_value(y_val), left - 10, y_px + 4)

                x_ticks = 6
                for i in range(x_ticks):
                    frac = i / max(1, (x_ticks - 1))
                    x_val = x_min + frac * (x_max - x_min)
                    x_px = x_to_px(x_val)
                    cv2.line(image, (x_px, top + plot_h), (x_px, top + plot_h + 6), (0, 0, 0), 1)
                    cv2.putText(image, self.format_graph_value(x_val), (x_px - 12, top + plot_h + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

                std_value = distribution_data["std"]
                if std_value > 0:
                    x_curve = np.linspace(x_min, x_max, 200)
                    bin_width = edges[1] - edges[0] if len(edges) > 1 else 1.0
                    y_curve = np.array([
                        distribution_data["values"].size * bin_width * NormalDist(mu=distribution_data["mean"], sigma=std_value).pdf(float(x_val))
                        for x_val in x_curve
                    ], dtype=np.float64)
                    points = np.array([(x_to_px(x_val), y_to_px(y_val)) for x_val, y_val in zip(x_curve, y_curve)], dtype=np.int32)
                    if points.shape[0] >= 2:
                        cv2.polylines(image, [points], False, (40, 40, 220), 2)

                if distribution_data.get("combined_columns"):
                    title = (
                        f"Histogram of {distribution_data['kind']} Across All Columns "
                        f"({distribution_data['values'].size} samples)"
                    )
                else:
                    title = (
                        f"Histogram of {distribution_data['kind']} at x={distribution_data['selected_x_display']:.3g} "
                        f"{distribution_data.get('column_input_suffix', 'px')} "
                        f"({distribution_data['values'].size} samples)"
                    )
                x_axis_text = distribution_data["default_x_label"]
                y_axis_text = distribution_data["default_y_label"]
        else:
            theoretical = distribution_data["theoretical_quantiles"]
            observed = distribution_data["sorted_values"]
            combined = np.concatenate((theoretical, observed))
            limits = self.resolve_axis_limits(combined, combined, y_pad=1.0)
            if limits is None:
                return None
            x_min, x_max, y_min, y_max = limits

            def x_to_px(x_value):
                if x_max <= x_min:
                    return int(left + (plot_w / 2.0))
                return int(round(left + ((x_value - x_min) / (x_max - x_min)) * plot_w))

            def y_to_px(y_value):
                return int(round(top + ((y_max - y_value) / max(y_max - y_min, 1.0)) * plot_h))

            cv2.line(image, (left, top + plot_h), (left + plot_w, top + plot_h), (0, 0, 0), 1)
            cv2.line(image, (left, top), (left, top + plot_h), (0, 0, 0), 1)

            diag_start_x = max(x_min, y_min)
            diag_end_x = min(x_max, y_max)
            if diag_end_x > diag_start_x:
                cv2.line(image, (x_to_px(diag_start_x), y_to_px(diag_start_x)), (x_to_px(diag_end_x), y_to_px(diag_end_x)), (140, 140, 140), 1)

            points = np.array([(x_to_px(x_val), y_to_px(y_val)) for x_val, y_val in zip(theoretical, observed)], dtype=np.int32)
            for x_px, y_px in points:
                cv2.circle(image, (int(x_px), int(y_px)), 3, (189, 95, 0), -1)

            y_ticks = 5
            for i in range(y_ticks + 1):
                frac = i / y_ticks
                y_val = y_min + (y_max - y_min) * frac
                y_px = y_to_px(y_val)
                cv2.line(image, (left - 6, y_px), (left, y_px), (0, 0, 0), 1)
                self._draw_right_aligned_text_cv(image, self.format_graph_value(y_val), left - 10, y_px + 4)

            x_ticks = 6
            for i in range(x_ticks):
                frac = i / max(1, (x_ticks - 1))
                x_val = x_min + frac * (x_max - x_min)
                x_px = x_to_px(x_val)
                cv2.line(image, (x_px, top + plot_h), (x_px, top + plot_h + 6), (0, 0, 0), 1)
                cv2.putText(image, self.format_graph_value(x_val), (x_px - 12, top + plot_h + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

            if distribution_data.get("combined_columns"):
                title = f"Normal Q-Q Plot of {distribution_data['kind']} Across All Columns"
            else:
                title = (
                    f"Normal Q-Q Plot of {distribution_data['kind']} at x={distribution_data['selected_x_display']:.3g} "
                    f"{distribution_data.get('column_input_suffix', 'px')}"
                )
            x_axis_text = app.graph_x_axis_label.get().strip() or "Theoretical Normal Quantile"
            y_axis_text = app.graph_y_axis_label.get().strip() or "Observed Quantile"

        self._draw_centered_text_cv(image, self.resolve_graph_title(title), width // 2, 30, font_scale=0.62, thickness=1)
        self._draw_centered_text_cv(image, x_axis_text, width // 2, height - 28, font_scale=0.55, thickness=1)
        self._draw_vertical_text_cv(image, y_axis_text, 8, top + (plot_h // 2), font_scale=0.55, thickness=1)
        return image

    def save_graph_image(self):
        app = self.app
        image = self.render_graph_image()
        if image is None:
            messagebox.showinfo("No graph data", "Run analysis first to generate graph data.")
            return

        default_dir = app.output_dir.get().strip() or os.path.dirname(__file__)
        default_file = f"{app.output_name_entry.get().strip() or 'analysis_output'}_graph.png"
        file_path = filedialog.asksaveasfilename(
            title="Save graph image",
            initialdir=default_dir,
            initialfile=default_file,
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("JPEG image", "*.jpg *.jpeg"),
                ("Bitmap image", "*.bmp"),
                ("TIFF image", "*.tif *.tiff"),
            ],
        )
        if not file_path:
            return
        if cv2.imwrite(file_path, image):
            messagebox.showinfo("Graph saved", f"Saved graph image to:\n{file_path}")
        else:
            messagebox.showerror("Save failed", f"Could not save graph image:\n{file_path}")

    def save_graph_data_csv(self):
        app = self.app
        export_data = self.build_graph_export_rows()
        if export_data is None:
            messagebox.showinfo("No graph data", "Run analysis first to generate graph data.")
            return

        default_dir = app.output_dir.get().strip() or os.path.dirname(__file__)
        default_file = f"{app.output_name_entry.get().strip() or 'analysis_output'}_graph_data.csv"
        file_path = filedialog.asksaveasfilename(
            title="Save graph data (CSV)",
            initialdir=default_dir,
            initialfile=default_file,
            defaultextension=".csv",
            filetypes=[("CSV file", "*.csv")],
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                metadata = export_data.get("metadata", [])
                data_rows = export_data.get("rows", [])

                if "pixel_header" in export_data and "unit_header" in export_data:
                    pixel_header = export_data["pixel_header"]
                    unit_header = export_data["unit_header"]
                    _raw = getattr(app, "final_centerline_samples", None)
                    histogram_export = (
                        self._build_combined_distribution_export(_raw)
                        if _raw is not None
                        else None
                    )
                    histogram_header = []
                    histogram_rows = []
                    histogram_metadata = []
                    if histogram_export is not None:
                        histogram_header = list(histogram_export.get("header", []))
                        histogram_rows = list(histogram_export.get("rows", []))
                        histogram_metadata = list(histogram_export.get("metadata", []))

                    if histogram_metadata:
                        metadata = list(metadata) + [
                            [f"histogram_{str(key)}", str(value)] for key, value in histogram_metadata
                        ]

                    unit_label_text = (app.graph_unit_label or "Actual Units").strip()
                    position_title = ["Position Data (Pixels)"] + [""] * (len(pixel_header) - 1)
                    unit_title = [f"Position Data ({unit_label_text})"] + [""] * (len(unit_header) - 1)
                    histogram_title = ["Histogram Data"] + [""] * (len(histogram_header) - 1) if histogram_header else []

                    title_row = ["Metadata", "Value", "", *position_title, "", *unit_title]
                    if histogram_header:
                        title_row.extend(["", *histogram_title])
                    writer.writerow(title_row)

                    header_row = ["metadata_key", "metadata_value", "", *pixel_header, "", *unit_header]
                    if histogram_header:
                        header_row.extend(["", *histogram_header])
                    writer.writerow(header_row)

                    row_count = max(len(data_rows), len(metadata), len(histogram_rows))
                    for row_idx in range(row_count):
                        if row_idx < len(metadata):
                            metadata_key, metadata_value = metadata[row_idx]
                        else:
                            metadata_key, metadata_value = "", ""

                        if row_idx < len(data_rows):
                            pixel_part = data_rows[row_idx].get("pixel", [""] * len(pixel_header))
                            unit_part = data_rows[row_idx].get("unit", [""] * len(unit_header))
                        else:
                            pixel_part = [""] * len(pixel_header)
                            unit_part = [""] * len(unit_header)

                        row = [metadata_key, metadata_value, "", *pixel_part, "", *unit_part]
                        if histogram_header:
                            histogram_part = histogram_rows[row_idx] if row_idx < len(histogram_rows) else [""] * len(histogram_header)
                            row.extend(["", *histogram_part])
                        writer.writerow(row)
                else:
                    combined_header = ["metadata_key", "metadata_value", *export_data["header"]]
                    writer.writerow(combined_header)

                    row_count = max(len(data_rows), len(metadata))
                    for row_index in range(row_count):
                        data_part = data_rows[row_index] if row_index < len(data_rows) else [""] * len(export_data["header"])
                        if row_index < len(metadata):
                            metadata_key, metadata_value = metadata[row_index]
                        else:
                            metadata_key, metadata_value = "", ""
                        writer.writerow([metadata_key, metadata_value, *data_part])

                    # Preserve the existing CSV table format and append optional
                    # supplemental sections for view-specific data (for example, histogram bins).
                    extra_tables = export_data.get("extra_tables", [])
                    for table in extra_tables:
                        table_header = table.get("header", [])
                        table_rows = table.get("rows", [])
                        if not table_header:
                            continue
                        writer.writerow([])
                        table_title = str(table.get("title", "Additional Data")).strip()
                        writer.writerow([table_title])
                        writer.writerow(table_header)
                        for table_row in table_rows:
                            writer.writerow(table_row)
            messagebox.showinfo("Graph data saved", f"Saved graph CSV to:\n{file_path}")
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save graph CSV:\n{exc}")
