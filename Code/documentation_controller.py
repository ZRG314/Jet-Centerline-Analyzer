"""Controller for opening, viewing, and saving in-app documentation text."""

import os
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk


class DocumentationController:
    def __init__(self, app):
        self.app = app

    def open_documentation_page(self):
        app = self.app
        if app.doc_window and app.doc_window.winfo_exists():
            app.doc_window.lift()
            app.doc_window.focus_force()
            return

        app.doc_window = ctk.CTkToplevel(app.root)
        app.doc_window.title("Application Documentation")
        app.doc_window.geometry("1200x900")
        app.doc_window.configure(fg_color="#eef3f9")
        try:
            app.doc_window.state("zoomed")
        except tk.TclError:
            app.doc_window.attributes("-fullscreen", True)

        app.doc_window.protocol("WM_DELETE_WINDOW", app.close_documentation_page)
        app.doc_window.bind("<Escape>", lambda _event: app.close_documentation_page())

        top_bar = ctk.CTkFrame(app.doc_window, fg_color="#ffffff", corner_radius=14, border_width=1, border_color="#d5deea")
        top_bar.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(top_bar, text=f"Viewing: {os.path.basename(app.doc_path)}", text_color="#5f7086").pack(side="left", padx=12, pady=10)
        ctk.CTkButton(
            top_bar,
            text="Close",
            command=app.close_documentation_page,
            fg_color="#edf2f8",
            hover_color="#e2eaf4",
            text_color="#10233d",
            corner_radius=10,
        ).pack(side="right", padx=12, pady=10)

        editor_frame = ctk.CTkFrame(app.doc_window, fg_color="#ffffff", corner_radius=14, border_width=1, border_color="#d5deea")
        editor_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        scroll = ctk.CTkScrollbar(editor_frame)
        scroll.pack(side="right", fill="y")

        app.doc_text_widget = tk.Text(
            editor_frame,
            wrap="word",
            undo=True,
            yscrollcommand=scroll.set,
            bg="#f8fbff",
            fg="#10233d",
            relief="flat",
            borderwidth=0,
            padx=16,
            pady=16,
        )
        app.doc_text_widget.pack(fill="both", expand=True)
        scroll.configure(command=app.doc_text_widget.yview)

        text = self.load_documentation_text()
        app.doc_text_widget.delete("1.0", tk.END)
        app.doc_text_widget.insert("1.0", text)
        app.doc_text_widget.configure(state="disabled")

    def load_documentation_text(self):
        app = self.app
        if os.path.isfile(app.doc_path):
            try:
                with open(app.doc_path, "r", encoding="utf-8") as handle:
                    return handle.read()
            except OSError:
                pass
        return (
            "# Jet Centerline Analyzer Documentation\n\n"
            "## Purpose\n"
            "Describe what this app does.\n\n"
            "## Basic Workflow\n"
            "1. Select a video.\n"
            "2. Optionally set crop.\n"
            "3. Choose frame range and parameters.\n"
            "4. Run analysis.\n\n"
            "## Parameter Notes\n"
            "- Threshold Offset:\n"
            "- Pixels per Column:\n"
            "- Standard Deviations:\n\n"
            "## Output Files\n"
            "Describe output videos and where they are saved.\n"
        )

    def save_documentation_text(self):
        app = self.app
        if not app.doc_text_widget:
            return
        text = app.doc_text_widget.get("1.0", tk.END).rstrip() + "\n"
        try:
            with open(app.doc_path, "w", encoding="utf-8") as handle:
                handle.write(text)
            messagebox.showinfo("Documentation", f"Saved to:\n{app.doc_path}")
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save documentation:\n{exc}")

    def close_documentation_page(self):
        app = self.app
        if app.doc_window and app.doc_window.winfo_exists():
            app.doc_window.destroy()
        app.doc_window = None
        app.doc_text_widget = None
