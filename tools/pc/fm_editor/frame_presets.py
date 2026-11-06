"""Ready frames for a card's alternate versions (variants.py, the Variants tab).

A preset is a full-card frame picture (frame_presets_data.py, made by
tools/pc/make_frame_presets.py from the Forbidden Memories HD pack's anime
frame) and the places the game puts a card's elements on it: the picture in the
window, the name in a strip above it, the stars, the element and ATK and DEF in
the band below. Those places are one table for every preset and for a frame
the modder draws, which should keep the same shape: 140x197 units, a picture
window of x 3, y 19, 134x123, a name strip over it from y 3 to 19, and a band
from y 146 (notes/modding.md, "Frame styles"). The pictures are kept at
256x512, over the 177x254 texture the game draws a frame at.
"""
from __future__ import annotations

import base64

from . import frame_presets_data

# key: (label, the color of the card's frame in the duel hand, "hand_color")
PRESETS = {
    "rainbow": ("Rainbow foil", "purple"),
    "gold": ("Gold foil", "orange"),
    "silver": ("Silver foil", "blue"),
}
CUSTOM_HAND_COLOR = "purple"

FRAME_W, FRAME_H = 140, 197
# The window the card's picture fills, in the frame's units.
WINDOW = {"x": 3, "y": 19, "width": 134, "height": 123}

# A style's own parts: a frame made for these places. The name is drawn dark over the strip.
PARTS = {
    "title": {"x": 12, "y": 4, "color": {"r": 40, "g": 30, "b": 20}},
    "art": dict(WINDOW),
    "attribute": {"x": 114, "y": 149},
    "atk": {"x": 38, "y": 179},
    "def": {"x": 102, "y": 179},
    "stars": {"x": 99, "y": 153},
    # a magic, trap, ritual or equip card has no stats: its picture and the card kind's icon
    "spell": {"art": dict(WINDOW), "icon": {"x": 62, "y": 163}},
}


def label(preset: str) -> str:
    return PRESETS[preset][0]


def png(preset: str) -> bytes:
    """The preset's frame picture."""
    return base64.b64decode("".join(frame_presets_data.PNG[preset]))


def style(image: str, hand_color: str = CUSTOM_HAND_COLOR) -> dict:
    """A "frame_styles" entry: the picture (a path in the mod) on the places above."""
    entry = {"image": image, "width": FRAME_W, "height": FRAME_H, "hand_color": hand_color}
    for key, value in PARTS.items():
        entry[key] = {k: dict(v) if isinstance(v, dict) else v for k, v in value.items()}
    return entry
