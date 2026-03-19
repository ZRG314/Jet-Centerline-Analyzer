"""Reusable custom Tkinter widgets shared by the GUI."""

import tkinter as tk


class RangeSlider(tk.Canvas):
    def __init__(self, parent, min_val, max_val, width=300, height=60, command=None):
        super().__init__(parent, width=width, height=height, bg="white", highlightthickness=0)
        self.min_val = min_val
        self.max_val = max_val
        self.command = command
        self.width = width
        self.height = height

        self.pad = 15
        self.line_y = height // 2

        self.start_val = min_val
        self.end_val = max_val
        self.active_handle = None
        self.enabled = True

        self.bind("<Button-1>", self.click)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)

        self.draw()

    def value_to_pos(self, value):
        if self.max_val == self.min_val:
            return self.pad
        ratio = (value - self.min_val) / (self.max_val - self.min_val)
        return self.pad + ratio * (self.width - 2 * self.pad)

    def pos_to_value(self, pos):
        ratio = (pos - self.pad) / (self.width - 2 * self.pad)
        value = self.min_val + ratio * (self.max_val - self.min_val)
        return int(round(min(max(value, self.min_val), self.max_val)))

    def draw(self):
        self.delete("all")
        self.create_line(self.pad, self.line_y, self.width - self.pad, self.line_y, width=4, fill="gray")

        x1 = self.value_to_pos(self.start_val)
        x2 = self.value_to_pos(self.end_val)

        self.create_line(x1, self.line_y, x2, self.line_y, width=6, fill="blue")

        self.create_oval(x1 - 8, self.line_y - 8, x1 + 8, self.line_y + 8, fill="red")
        self.create_oval(x2 - 8, self.line_y - 8, x2 + 8, self.line_y + 8, fill="red")

    def click(self, event):
        if not self.enabled:
            return
        x1 = self.value_to_pos(self.start_val)
        x2 = self.value_to_pos(self.end_val)
        if abs(event.x - x1) < 10:
            self.active_handle = "start"
        elif abs(event.x - x2) < 10:
            self.active_handle = "end"

    def drag(self, event):
        if not self.enabled or not self.active_handle:
            return
        value = self.pos_to_value(event.x)
        if self.active_handle == "start":
            self.start_val = min(value, self.end_val)
        else:
            self.end_val = max(value, self.start_val)
        self.draw()
        if self.command:
            self.command(self.start_val, self.end_val, self.active_handle)

    def release(self, event):
        self.active_handle = None

    def set_range(self, min_val, max_val):
        self.min_val = min_val
        self.max_val = max_val
        self.start_val = min_val
        self.end_val = max_val
        self.draw()

    def set_values(self, start_val, end_val):
        self.start_val = int(min(max(start_val, self.min_val), self.max_val))
        self.end_val = int(min(max(end_val, self.min_val), self.max_val))
        if self.end_val < self.start_val:
            self.end_val = self.start_val
        self.draw()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)


class HoverTooltip:
    def __init__(self, widget, text, delay_ms=150):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.after_id = None
        self.hide_after_id = None
        self.tip_window = None

        self.widget.bind("<Enter>", self.on_enter, add="+")
        self.widget.bind("<Leave>", self.on_leave, add="+")
        self.widget.bind("<Motion>", self.on_motion, add="+")
        self.widget.bind("<ButtonPress-1>", self.on_leave, add="+")

    def on_enter(self, _event=None):
        self.cancel_hide()
        self.schedule()

    def on_leave(self, _event=None):
        self.unschedule()
        self.schedule_hide()

    def on_motion(self, event):
        if self.tip_window:
            self.move_tip(event.x_root, event.y_root)

    def schedule(self):
        if self.tip_window is not None:
            return
        self.unschedule()
        self.after_id = self.widget.after(self.delay_ms, self.show_tip)

    def unschedule(self):
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def schedule_hide(self, delay_ms=120):
        self.cancel_hide()
        self.hide_after_id = self.widget.after(delay_ms, self.hide_tip)

    def cancel_hide(self):
        if self.hide_after_id is not None:
            self.widget.after_cancel(self.hide_after_id)
            self.hide_after_id = None

    def show_tip(self):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_pointerx() + 14
        y = self.widget.winfo_pointery() + 14

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        try:
            self.tip_window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass

        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify="left",
            wraplength=320,
            bg="#fffde7",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6,
        )
        label.pack()
        self.move_tip(x, y)

    def move_tip(self, x_root, y_root):
        if self.tip_window:
            self.tip_window.wm_geometry(f"+{x_root}+{y_root}")

    def hide_tip(self):
        self.cancel_hide()
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None
