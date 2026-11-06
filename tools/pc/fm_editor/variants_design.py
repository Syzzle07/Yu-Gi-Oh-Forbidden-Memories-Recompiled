"""The window that designs one variant's card (the Variants tab's "Design the card...").

It is the UI tab's Frames designer (ui_frames.FramesPage) pinned to the variant's
own frame style and to the variant as its sample card: drag or resize the
picture's window, the name, the stars, the element and the ATK and DEF values,
choose the frame picture, the labels' pictures and a digit strip of your own, hide
a part, and see the card as the game lays it out. The styles of the mod's other
cards, and the layout's rules for all cards, are not shown and never touched.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import ui_frames, ui_tab
from .widgets import px


class DesignHost:
    """What the Frames page asks of the UI tab that normally holds it."""

    comparing = False

    def __init__(self, app):
        self.app = app

    @property
    def project(self):
        return self.app.project

    def changed(self, key: str):
        """After an edit of project.other[key]: empty objects out, the window told."""
        ui_tab.prune(self.project, key)
        self.app.changed()

    def mark_reverts(self):
        pass

    def draw_compared(self, page, draw):
        draw()

    def revert_page(self, page):
        pass


class DesignWindow(tk.Toplevel):
    def __init__(self, master, app, cid: int, style_name: str, on_close=None):
        super().__init__(master)
        project = app.project
        self.title(f"Design the card: {project.card_label(cid)}")
        self.transient(master.winfo_toplevel())
        self.on_close = on_close
        self.host = DesignHost(app)
        self.page = ui_frames.FramesPage(self, self.host, locked={"style": style_name, "card": cid})
        self.page.pack(fill="both", expand=True, padx=px(self, 8), pady=px(self, 8))
        ttk.Button(self, text="Close", command=self.close).pack(side="right", padx=px(self, 8), pady=(0, px(self, 8)))
        self.geometry(f"{px(self, 1060)}x{px(self, 700)}")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda e: self.close())
        self.page.fill()

    def close(self):
        callback, self.on_close = self.on_close, None
        self.destroy()
        if callback:
            callback()
