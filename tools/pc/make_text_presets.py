#!/usr/bin/env python3
"""Make the FM Editor's own card numbers, labels and level stars (tools/pc/fm_editor/text_presets_data.py).

The game draws a card's ATK and DEF numbers by subtraction, so they can only darken what is behind them and take no
color of their own. A style that draws its numbers and its "ATK"/"DFD" words from pictures does: the style's
"color" multiplies the picture, so a picture of white ink takes any color. The Variants tab's card designer uses these
white pictures when a modder colors the numbers or the words.

The level stars are shapes (a star, a diamond, a heart, a plain disc) in the same white ink: the style's "stars"
"color" colors them. Written with Pillow's own font (Aileron, public domain), as PNGs inside a Python module (a packaged editor carries
Python modules, not loose files). The editor needs no Pillow for it, and is not changed by running this again:

    python tools/pc/make_text_presets.py
"""
import base64
import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TARGET = Path(__file__).resolve().parent / "fm_editor" / "text_presets_data.py"

# The digit strip the game reads (src/pc/cards/card_layout_art.h): 5 x 4 cells of 40 x 48 texels, digit d in column
# d % 5 and row d / 5, the same ten greyed two rows further down (the stat the attack screen dims), saved at 256 x 256.
COLS, ROWS, CELL_W, CELL_H = 5, 4, 40, 48
OUT_SIZE = (256, 256)
GLYPH_H = 36          # the digits' height in texels (a card unit is four)
STROKE = 2            # a little body for the thin font
SUPER = 8
DIM = 150             # the greyed digits' ink, of 255
LABEL_SIZE = (128, 64)   # a label's picture: 16 x 8 card units at 8 texels a unit


def png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def font_sized(height_texels: int, text: str, stroke: int) -> ImageFont.FreeTypeFont:
    '''The font at the size where `text` is `height_texels` tall.'''
    probe = ImageFont.load_default(200)
    left, top, right, bottom = probe.getbbox(text, stroke_width=0)
    return ImageFont.load_default(round(200 * height_texels / (bottom - top)))


def digits() -> bytes:
    font = font_sized(GLYPH_H * SUPER, "0", 0)
    sheet = Image.new("RGBA", (COLS * CELL_W, ROWS * CELL_H), (0, 0, 0, 0))
    for d in range(10):
        mask = Image.new("L", (CELL_W * SUPER, CELL_H * SUPER), 0)
        draw = ImageDraw.Draw(mask)
        left, top, right, bottom = font.getbbox(str(d), stroke_width=STROKE * SUPER)
        x = (CELL_W * SUPER - (right - left)) // 2 - left
        y = (CELL_H * SUPER - (bottom - top)) // 2 - top
        draw.text((x, y), str(d), font=font, fill=255, stroke_width=STROKE * SUPER, stroke_fill=255)
        alpha = mask.resize((CELL_W, CELL_H), Image.BOX)
        for dim in (0, 1):
            ink = DIM if dim else 255
            cell = Image.merge("RGBA", (Image.new("L", alpha.size, ink),) * 3 + (alpha,))
            sheet.paste(cell, (d % COLS * CELL_W, (d // COLS + 2 * dim) * CELL_H))
    return png(sheet.resize(OUT_SIZE, Image.LANCZOS))


def label(text: str) -> bytes:
    width, height = LABEL_SIZE
    scale = 4
    font = font_sized(round(height * 0.62) * scale, text, 0)
    mask = Image.new("L", (width * scale, height * scale), 0)
    stroke = scale
    left, top, right, bottom = font.getbbox(text, stroke_width=stroke)
    x = (width * scale - (right - left)) // 2 - left
    y = (height * scale - (bottom - top)) // 2 - top
    ImageDraw.Draw(mask).text((x, y), text, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
    alpha = mask.resize((width, height), Image.LANCZOS)
    return png(Image.merge("RGBA", (Image.new("L", alpha.size, 255),) * 3 + (alpha,)))


STAR_SIZE = 64        # a level star's picture: 9 x 9 card units, in texels a little over 7 a unit
SHAPES = ("star", "diamond", "heart", "disc")


def shape_polygon(name: str, s: int) -> list:
    """The outline of a shape in a square of side `s`, as one or more (kind, points) items."""
    c = s / 2
    if name == "star":
        points = []
        for i in range(10):
            radius = s * (0.49 if i % 2 == 0 else 0.21)
            angle = -math.pi / 2 + i * math.pi / 5
            points.append((c + radius * math.cos(angle), c + radius * math.sin(angle) + s * 0.03))
        return [("poly", points)]
    if name == "diamond":
        return [("poly", [(c, s * 0.02), (s * 0.98, c), (c, s * 0.98), (s * 0.02, c)])]
    if name == "heart":
        r = s * 0.26
        return [("circle", (s * 0.28, s * 0.32, r)), ("circle", (s * 0.72, s * 0.32, r)),
                ("poly", [(s * 0.03, s * 0.42), (s * 0.97, s * 0.42), (c, s * 0.97)])]
    return [("circle", (c, c, s * 0.47))]


def star(name: str) -> bytes:
    scale = 8
    s = STAR_SIZE * scale
    mask = Image.new("L", (s, s), 0)
    draw = ImageDraw.Draw(mask)
    for kind, data in shape_polygon(name, s):
        if kind == "poly":
            draw.polygon(data, fill=255)
        else:
            x, y, r = data
            draw.ellipse((x - r, y - r, x + r, y + r), fill=255)
    alpha = mask.resize((STAR_SIZE, STAR_SIZE), Image.LANCZOS)
    return png(Image.merge("RGBA", (Image.new("L", alpha.size, 255),) * 3 + (alpha,)))


def wrapped(name: str, data: bytes) -> str:
    text = base64.b64encode(data).decode("ascii")
    lines = [text[i:i + 100] for i in range(0, len(text), 100)]
    body = "\n".join(f'    "{line}"' for line in lines)
    return f"{name} = (\n{body}\n)\n"


def main():
    parts = ['"""The card numbers, words and stars of the Variants designer (made by tools/pc/make_text_presets.py)."""\n\n',
             wrapped("DIGITS", digits()), "\n", wrapped("ATK", label("ATK")), "\n", wrapped("DFD", label("DFD"))]
    for name in SHAPES:
        parts += ["\n", wrapped("STAR_" + name.upper(), star(name))]
    TARGET.write_text("".join(parts), encoding="utf-8", newline="\n")
    print("wrote", TARGET, TARGET.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
