#!/usr/bin/env python3
"""Make the FM Editor's frame presets (tools/pc/fm_editor/frame_presets_data.py).

The Variants tab offers a few ready frames for a card's alternate versions: a
rainbow foil, a gold foil and a silver foil. They are the anime frame of the
Forbidden Memories HD pack (tools/pc/hd_recipes/anime_frame_monster.png)
recolored, with a strip in the top of the picture window for the card's name
(the name is drawn after the picture, so it needs a place the picture does not
cover). Each is kept at 256x512, which is more than the game's own 177x254 frame
texture, as a PNG written into a Python module: a packaged editor carries
Python modules, not loose files.

This needs Pillow and numpy; the editor itself needs neither, and is not changed
by running it again:

    python tools/pc/make_frame_presets.py
"""
import base64
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "hd_recipes" / "anime_frame_monster.png"
TARGET = HERE / "fm_editor" / "frame_presets_data.py"
WIDTH, HEIGHT = 256, 512

# The anime frame is 1024x2048 for a 140x197 card: 7.31 px a unit across and 10.4 down. Its picture
# window runs from x 22 and y 31 to x 1002 and y 1476, the bare band below it from y 1520 to 1687.
# The top 167 rows of the window (16 units) become band, for the name.
WINDOW_LEFT, WINDOW_TOP, WINDOW_RIGHT = 22, 31, 1002
BAND_TOP, STRIP = 1520, 167


def base_frame() -> Image.Image:
    frame = Image.open(SOURCE).convert("RGBA")
    strip = frame.crop((WINDOW_LEFT, BAND_TOP, WINDOW_RIGHT, BAND_TOP + STRIP))
    frame.paste(strip, (WINDOW_LEFT, WINDOW_TOP))
    return frame


def finish(frame, hue, saturation, value, sparkle) -> Image.Image:
    height, width = np.array(frame.getchannel("A")).shape
    alpha = frame.getchannel("A")
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    diagonal = (xx / width) + (yy / height) * 0.55
    glint = np.clip(1.0 - np.abs(((diagonal * 9.0) % 1.0) - 0.5) * 7.0, 0, 1) ** 2 * sparkle
    value = np.clip(value + glint * 0.35, 0, 1)
    saturation = np.clip(saturation - glint * 0.45, 0, 1)
    pixels = np.stack([(hue % 1.0) * 255, saturation * 255, value * 255], axis=-1).astype(np.uint8)
    rgb = Image.frombytes("HSV", (width, height), pixels.tobytes()).convert("RGB")
    out = Image.merge("RGBA", (*rgb.split(), alpha))
    return out.resize((WIDTH, HEIGHT), Image.LANCZOS)


def presets() -> dict:
    frame = base_frame()
    height, width = frame.size[1], frame.size[0]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    luminance = np.array(frame.convert("RGB").convert("HSV"), dtype=np.float32)[..., 2] / 255.0
    band = 0.5 + 0.5 * np.sin(((xx / width) * 2.0 + (yy / height) * 3.0) * np.pi * 2)
    return {
        # the hue sweeps across the whole card: the grey border and the gold band both take it
        "rainbow": finish(frame, (xx / width) * 0.9 + (yy / height) * 0.6, np.full_like(luminance, 0.62),
                          np.clip(0.35 + luminance * 0.75, 0, 1), 1.0),
        # a bright metallic gold, light and dark bands running across
        "gold": finish(frame, np.full_like(luminance, 0.125) + band * 0.012,
                       np.clip(0.85 - luminance * 0.2, 0, 1), np.clip(0.45 + luminance * 0.55 + band * 0.18, 0, 1), 0.8),
        # a pale cool silver, with fainter glints
        "silver": finish(frame, np.full_like(luminance, 0.60), np.clip(0.16 - luminance * 0.08, 0, 1),
                         np.clip(0.50 + luminance * 0.50 + band * 0.12, 0, 1), 0.6),
    }


def main() -> int:
    lines = ['"""The FM Editor\'s frame presets, as PNGs in base64 (made by tools/pc/make_frame_presets.py: do not edit)."""',
             "", "PNG = {"]
    for name, image in presets().items():
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        text = base64.b64encode(buffer.getvalue()).decode("ascii")
        lines.append(f'    "{name}": (')
        lines += [f'        "{text[i:i + 96]}"' for i in range(0, len(text), 96)]
        lines.append("    ),")
        print(f"{name}: {len(buffer.getvalue())} bytes")
    lines.append("}")
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
