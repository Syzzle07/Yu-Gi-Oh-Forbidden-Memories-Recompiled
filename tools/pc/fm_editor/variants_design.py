"""What the Frames designer (ui_frames.FramesPage) asks of the tab that holds it, for the Variants tab.

The Variants tab holds the UI tab's Frames designer itself, pinned to one variant's own
frame style and to the variant as its sample card (FramesPage.lock): drag or resize the
picture's window, the name, the stars, the element and the ATK and DEF values, choose the
frame picture, the labels' pictures and a digit strip of your own, hide or tint a part, and
see the card as the game lays it out. The styles of the mod's other cards, and the layout's
rules for all cards, are not shown and never touched.
"""
from __future__ import annotations

from . import ui_tab


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
