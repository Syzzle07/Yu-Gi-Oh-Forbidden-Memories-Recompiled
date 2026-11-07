"""The card's own small pictures off the disc, for the Cards tab's form: the
attribute balls (Light ... Wind, then Magic and Trap) and the level star of
the big card (func_80028B08: the card view package's sheet, here the
Library's in WA_MRG.MRG), and the sword and shield the duel's info bar puts
before ATK and DEF (its 8x8 letters ♂ and ♀, func_80035E20).

Each sheet is 4 bits a texel, 128 bytes a row; a palette entry is 15-bit
color, 0 transparent."""
from __future__ import annotations

import base64
import tkinter as tk

from . import pngio

CARD_SHEET, CARD_PALETTES = 0xEFE800, 0xF06800     # the Library's sheet (VRAM 960, 256) and palettes (256, 240)
BALL_PALETTE, STAR_PALETTE, LABEL_PALETTE = 0x1E00, 0x1180, 0x11E0
SMALL_FONT, SMALL_PALETTE = 0xB50000, 0xB60520     # the boot package's 8x8 letters and their white


def _picture(wa: bytes, base: int, u: int, v: int, width: int, height: int, palette: int):
    if len(wa) < max(base + (v + height) * 128, palette + 32):
        return None
    rgba = bytearray()
    for y in range(height):
        for x in range(width):
            tu = u + x
            index = wa[base + (v + y) * 128 + tu // 2] >> 4 * (tu & 1) & 15
            word = wa[palette + 2 * index] | wa[palette + 2 * index + 1] << 8
            rgba += bytes(((word & 31) << 3, (word >> 5 & 31) << 3, (word >> 10 & 31) << 3,
                           0 if index == 0 or word == 0 else 255))
    return pngio.Image(width, height, bytes(rgba)) if any(rgba[3::4]) else None


FRAME_COLUMNS, FRAME_COLUMN = CARD_SHEET - 3 * 0x8000, 0x8000    # the frame sheet's two 128-texel columns
FRAME_SIZE = (140, 197)                                           # a card: 140 wide, 196 rows (and one clear)


def _texels(wa: bytes, page: int, palette: int, sx: int, sy: int, w: int, h: int, flip: bool = False):
    """The rows of a w x h piece of a frame sheet page (8 bits a texel, 128 a row) as RGBA texels, top to bottom
    (bottom to top with `flip`)."""
    rows = []
    for y in range(h):
        row = bytearray()
        for x in range(w):
            index = wa[page + (sy + y) * 128 + sx + x]
            row += _rgba(wa[palette + 2 * index] | wa[palette + 2 * index + 1] << 8, index)
        rows.append(bytes(row))
    return rows[::-1] if flip else rows


def _cut_card(wa: bytes, frame: int, pieces):
    """A 140 x 197 card out of the frame sheet's pieces: (page, sx, sy, w, h, dx, dy[, flip]) each. Its last row
    stays clear: the card is 196 rows."""
    palette = CARD_PALETTES + (8 + frame) * 0x200
    right, foot = FRAME_COLUMNS + FRAME_COLUMN, FRAME_COLUMNS + 2 * FRAME_COLUMN
    pages = (FRAME_COLUMNS, right, foot)
    if not 0 <= frame < 6 or len(wa) < max(foot + 64 * 128, right + 256 * 128, palette + 0x200):
        return None
    width, height = FRAME_SIZE
    rgba = bytearray(width * height * 4)
    for piece in pieces:
        page, sx, sy, w, h, dx, dy = piece[:7]
        for y, row in enumerate(_texels(wa, pages[page], palette, sx, sy, w, h, len(piece) > 7 and piece[7])):
            at = ((dy + y) * width + dx) * 4
            rgba[at:at + 4 * w] = row
    return pngio.Image(width, height, bytes(rgba)) if any(rgba[3::4]) else None


def card_frame(wa: bytes, frame: int = 0, monster: bool = True):
    """The game's own frame of a card as it draws it, 140 x 197 (its last row is clear: the card is 196 rows):
    `frame` is a gamedata.FRAME_NAMES index (monster, magic, trap, ritual, purple, orange), `monster` says whether
    it has a monster's plaque for ATK and DEF (every other card has a larger panel there). The picture's window is
    black in it. Cut from the frame sheet of WA_MRG.MRG, where the card is the left page's top 128 x 192 texels in
    its own palette row (8 + frame), its right edge two 12-texel strips of the second page, its bottom border the
    top border turned over. (The same pieces as the 0.1.3 editor's, which found where they are.)"""
    pieces = [(0, 0, 0, 128, 192, 0, 0),                    # the body
              (1, 4, 0, 12, 128, 128, 0),                   # the right edge, top
              (1, 36, 0, 12, 68, 128, 128),                 # and bottom, down to the card's last row
              (0, 0, 0, 128, 4, 0, 192, True)]              # the bottom border: the top one, turned over
    if not monster:
        pieces.insert(1, (0, 0, 208, 128, 48, 0, 144))      # the larger panel in the plaque's place
    return _cut_card(wa, frame, pieces)


def _rgba(word: int, index: int) -> bytes:
    """One texel: a 15-bit color (5 bits a channel, widened), clear for index 0 or a zero word."""
    if not index or not word:
        return bytes(4)
    return bytes(((word & 31) << 3 | (word & 31) >> 2, (word >> 5 & 31) << 3 | (word >> 5 & 31) >> 2,
                  (word >> 10 & 31) << 3 | (word >> 10 & 31) >> 2, 255))


def card_back(wa: bytes, frame: int = 0):
    """The game's own back of a card, 140 x 197 as card_frame, in the palette of FRAME_NAMES index `frame`. The
    frame sheet's second and third pages hold it: the lower half of the second is the back's top half and its right
    edge, the top of the third its bottom half; the bottom border is the top one turned over."""
    return _cut_card(wa, frame, [(1, 0, 128, 128, 128, 0, 0),         # the top half
                                 (2, 0, 0, 128, 64, 0, 128),          # the bottom half
                                 (1, 16, 0, 12, 128, 128, 0),         # the right edge, top
                                 (1, 48, 0, 12, 68, 128, 128),        # and bottom
                                 (1, 0, 128, 128, 4, 0, 192, True)])  # the bottom border


LIBRARY_ICON = (17713152, 17733120)                      # the Library grid's icon sheet (4 bits a texel) and palettes
LIBRARY_ICON_ROW = {0: 3, 1: 6, 2: 8, 3: 10}             # monster, magic, trap, ritual (FRAME_NAMES order)


def library_icon(wa: bytes, frame: int = 0):
    """The Library grid's plain card icon (12 x 14), tinted as the game tints the kind of `frame` (a FRAME_NAMES index;
    the purple and orange monsters' is the monster's). What func_80029EC4 draws for a card with no icon picture."""
    row = LIBRARY_ICON_ROW.get(frame, 3)
    return _picture(wa, LIBRARY_ICON[0], 96, 112, 12, 14, LIBRARY_ICON[1] + row * 0x20)


def attribute(wa: bytes, n: int):
    """Attribute n's ball (0 Light ... 5 Wind, 6 Magic, 7 Trap), 16 x 16."""
    return _picture(wa, CARD_SHEET, 16 * n, 128, 16, 16, CARD_PALETTES + BALL_PALETTE + 0x20 * n) \
        if 0 <= n < 8 else None


def level_star(wa: bytes):
    return _picture(wa, CARD_SHEET, 0, 144, 9, 9, CARD_PALETTES + STAR_PALETTE)


def kind_label(wa: bytes, kind: str):
    """The retail caption from the card-view sheet, 56 x 16.

    Ritual cards share the normal-magic caption in the retail sheet.  The
    editor still offers a separate ritual replacement image because the
    card-layout API intentionally lets a style distinguish it.
    """
    row = {"magic": 158, "trap": 174, "ritual": 158, "equip": 190}.get(kind)
    return _picture(wa, CARD_SHEET, 0, row, 56, 16, CARD_PALETTES + LABEL_PALETTE) if row is not None else None


def sword(wa: bytes):
    return _picture(wa, SMALL_FONT, 208, 88, 8, 8, SMALL_PALETTE)


def shield(wa: bytes):
    return _picture(wa, SMALL_FONT, 216, 88, 8, 8, SMALL_PALETTE)


def photos(app, widget, zoom: int = 1) -> dict:
    """The pictures as Tk images, kept by the window (its Tk's): "attribute"
    (by number), "level", "attack", "defense"; empty without game files."""
    files = getattr(app, "files", None)
    if files is None or getattr(files, "wa", None) is None:
        return {}
    cache = app.__dict__.setdefault("_card_icons", {})
    key = (getattr(files, "source", id(files)), zoom)
    if key not in cache:
        master = widget.winfo_toplevel()

        def photo(image):
            if image is None:
                return None
            image = pngio.scale_nearest(image, zoom)
            return tk.PhotoImage(master=master, data=base64.b64encode(pngio.encode(image)), format="png")
        cache[key] = {"attribute": {n: photo(attribute(files.wa, n)) for n in range(8)},
                      "level": photo(level_star(files.wa)), "attack": photo(sword(files.wa)),
                      "defense": photo(shield(files.wa))}
    return cache[key]
