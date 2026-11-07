"""Variants: a card's alternate versions (notes/more-cards.md, "Variants").

A variant is a copy of a retail card with a "variant_permille" (its chance, in
thousandths, of being won in the card's place), its own picture and, when it
has one, a frame of its own: a "frame_style" naming an entry of the mod's
card_layout "frame_styles". This module is the engine of the Variants tab,
with no Tk: it makes, changes and removes them in a Project, writing what the
game reads (the card's entry, its picture, the frame style and its picture) so the
modder never has to. A mod of frame styles alone needs no switch: the game draws such
a style for the cards that name it.

A frame is chosen as one of:
    None                      no frame of its own: the game's
    ("preset", name)          one of frame_presets.PRESETS
    ("style", name)           a style the mod already has
    ("png", bytes, stem)      a picture the modder drew, on the presets' places
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import art, frame_presets, pngio, text_presets
from .gamedata import CARD_COUNT
from .model import KEY_RE, replaced

EXODIA = (17, 18, 19, 20, 21)
PERMILLE_MIN, PERMILLE_MAX = 1, 1000
LABEL_MAX = 24
KEY_MAX = 80
FRAME_DIR = "frames"
PRESET_PREFIX = "foil-"
CUSTOM_PREFIX = "custom-"
DESIGN_PREFIX = "v-"       # a variant's own design: v-<its key>
STYLE_NAME_MAX = 31        # the game's longest frame style name
FINISHES = ("glossy", "royal")   # a card's "finish": the foil its view shows over it (notes/more-cards.md)


@dataclass
class Variant:
    cid: int
    key: str
    base: int
    permille: int
    label: str
    frame_style: str
    art: str
    finish: str = ""


def is_variant(project, cid: int) -> bool:
    added = project.added.get(cid)
    return added is not None and "variant_permille" in added.extra


def read(project, cid: int) -> Variant:
    added = project.added[cid]
    extra = added.extra
    permille = extra.get("variant_permille")
    return Variant(cid, added.key, added.base,
                   permille if isinstance(permille, int) and not isinstance(permille, bool) else 0,
                   extra.get("variant_label") if isinstance(extra.get("variant_label"), str) else "",
                   extra.get("frame_style") if isinstance(extra.get("frame_style"), str) else "",
                   extra.get("art") if isinstance(extra.get("art"), str) else "",
                   extra.get("finish") if extra.get("finish") in FINISHES else "")


def variants(project) -> list:
    """The mod's variants, by their base card and then as they were made."""
    found = [read(project, cid) for cid in sorted(project.added) if is_variant(project, cid)]
    return sorted(found, key=lambda v: (v.base, v.cid))


def family(project, base: int) -> list:
    return [v for v in variants(project) if v.base == base]


# --- chance ----------------------------------------------------------------------------

def percent_text(permille: int) -> str:
    """50 as "5%", 25 as "2.5%"."""
    return f"{permille / 10:g}%"


def parse_percent(text: str):
    """The chance in thousandths the text names ("5", "2.5%", "0,5"), None for none or out of range."""
    text = text.strip().rstrip("%").strip().replace(",", ".")
    try:
        value = round(float(text) * 10)
    except ValueError:
        return None
    return value if PERMILLE_MIN <= value <= PERMILLE_MAX else None


# --- keys ---------------------------------------------------------------------------------

def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "card"


def suggest_key(project, base: int) -> str:
    """A key for a new variant of `base`: its name and "-alt-N", unused."""
    taken = {added.key for added in project.added.values()}
    stem = slug(project.cards[base].name)[:KEY_MAX - 12].strip("-") or "card"
    n = 1
    while f"{stem}-alt-{n}" in taken:
        n += 1
    return f"{stem}-alt-{n}"


# --- checks --------------------------------------------------------------------------------

def check_base(base: int):
    if not isinstance(base, int) or not 1 <= base <= CARD_COUNT:
        raise ValueError("a variant is a version of a card of the disc (1 to 722)")
    if base in EXODIA:
        raise ValueError("a piece of Exodia has no variants: a copy of it would not complete Exodia")


def check_chance(permille):
    if not isinstance(permille, int) or isinstance(permille, bool) or not PERMILLE_MIN <= permille <= PERMILLE_MAX:
        raise ValueError("the chance is 0.1% to 100%")


def check_finish(finish: str):
    if finish and finish not in FINISHES:
        raise ValueError("the finish is " + " or ".join(FINISHES))


def check_label(label: str):
    if len(label.encode("utf-8")) > LABEL_MAX:
        raise ValueError(f"the label is {LABEL_MAX} letters at most")


# --- the mod's layout --------------------------------------------------------------------

def _object(project, *path) -> dict:
    at = project.other
    for key in path:
        if not isinstance(at.get(key), dict):
            at[key] = {}
        at = at[key]
    return at


def styles(project) -> dict:
    value = project.other.get("card_layout")
    value = value.get("frame_styles") if isinstance(value, dict) else None
    return value if isinstance(value, dict) else {}


def _images_of(entry) -> list:
    '''The picture files a frame style names (its frame, back and parts).'''
    if isinstance(entry, dict):
        out = [entry["image"]] if isinstance(entry.get("image"), str) else []
        for value in entry.values():
            out += _images_of(value)
        return out
    return []


def _held(project, name: str):
    """A file of the mod, from what the editor holds or the mod's folder."""
    if not isinstance(name, str) or not name:        # a style drawn from parts alone has no picture file
        return None
    if name in project.files:
        return project.files[name]
    if project.source_dir:
        path = Path(project.source_dir) / name
        if path.is_file():
            try:
                return path.read_bytes()
            except OSError:
                return None
    return None


def _free_file(project, stem: str, data: bytes) -> str:
    """frames/<stem>.png, or the next free name when that holds another picture."""
    name, n = f"{FRAME_DIR}/{stem}.png", 2
    while _held(project, name) not in (None, data):
        name = f"{FRAME_DIR}/{stem}-{n}.png"
        n += 1
    return name


def frame_choices(project) -> list:
    """(text, choice) for each frame the tab offers: none, the presets, the mod's own styles."""
    out = [("The game's frame", None)]
    out += [(frame_presets.label(name), ("preset", name)) for name in frame_presets.PRESETS]
    made = {PRESET_PREFIX + name for name in frame_presets.PRESETS}
    for name in styles(project):
        if name not in made:             # a preset's own style is the preset
            out.append((f"This mod's \"{name}\"", ("style", name)))
    return out


def _use_preset(project, name: str) -> str:
    style_name = PRESET_PREFIX + name
    entries = _object(project, "card_layout", "frame_styles")
    if style_name not in entries:
        data = frame_presets.png(name)
        file = _free_file(project, style_name, data)
        project.files[file] = data
        entries[style_name] = frame_presets.style(file, frame_presets.PRESETS[name][1])
    return style_name


HAND_COLORS = ("gold", "green", "pink", "blue", "purple", "orange")      # gamedata.FRAME_NAMES' order


def hand_color_of(project, cid: int) -> str:
    """The colour of the card's own frame (what its type, or its own frame setting, gives it) as a "hand_color" names it:
    the duel's hand and field draw the card in that colour, so a frame of the modder's own keeps it."""
    card = project.cards.get(cid)
    index = card.shown_frame() if card is not None else 0
    return HAND_COLORS[index] if 0 <= index < len(HAND_COLORS) else HAND_COLORS[0]


def _use_png(project, data: bytes, stem: str, hand_color: str = None) -> str:
    try:
        image = pngio.decode(data)
    except (pngio.PngError, ValueError) as problem:
        raise ValueError(f"that is not a PNG the editor can read: {problem}")
    if image.width > 1024 or image.height > 2048:
        raise ValueError("a frame is 1024x2048 at most")
    stem_name = CUSTOM_PREFIX + slug(stem)[:40]
    entries = _object(project, "card_layout", "frame_styles")
    file = _free_file(project, stem_name, data)
    project.files[file] = data
    style_name, n = stem_name, 2
    while style_name in entries and entries[style_name].get("image") != file:   # another picture's style
        style_name = f"{stem_name}-{n}"
        n += 1
    entries.setdefault(style_name, frame_presets.style(file, hand_color or frame_presets.CUSTOM_HAND_COLOR))
    return style_name


def set_frame(project, cid: int, choice):
    """Give the variant the frame `choice` (see the top); None takes its own frame away."""
    extra = project.added[cid].extra
    if choice is None:
        extra.pop("frame_style", None)
        return
    kind = choice[0]
    if kind == "preset":
        if choice[1] not in frame_presets.PRESETS:
            raise ValueError(f"no frame preset named {choice[1]!r}")
        name = _use_preset(project, choice[1])
    elif kind == "style":
        if choice[1] not in styles(project):
            raise ValueError(f"the mod has no frame style named {choice[1]!r}")
        name = choice[1]
    elif kind == "png":
        name = _use_png(project, choice[1], choice[2], hand_color_of(project, cid))
    else:
        raise ValueError(f"unknown frame choice {kind!r}")
    extra["frame_style"] = name


# --- a variant's own design ------------------------------------------------------------

def design_name(key: str) -> str:
    '''The frame style that is one variant's alone.'''
    return (DESIGN_PREFIX + slug(key))[:STYLE_NAME_MAX].rstrip("-")


def has_own_design(project, cid: int) -> bool:
    added = project.added[cid]
    name = design_name(added.key)
    return added.extra.get("frame_style") == name and name in styles(project)


def own_design(project, cid: int) -> str:
    '''The name of the variant's own frame style, made the first time as a copy of the one it has
    (a preset's, a style of the mod's, or none: the game's own layout), and given to the variant. It is
    what the designer window edits: no other card's style, and no rule of the layout, is touched.'''
    added = project.added[cid]
    name = design_name(added.key)
    entries = _object(project, "card_layout", "frame_styles")
    if name not in entries:
        current = added.extra.get("frame_style")
        source = entries.get(current) if isinstance(current, str) else None
        entries[name] = copy.deepcopy(source) if isinstance(source, dict) else {"hand_color": hand_color_of(project, cid)}
    added.extra["frame_style"] = name
    return name


def remove_own_design(project, cid: int):
    '''Take the variant's own design away: it has no frame of its own again.'''
    added = project.added[cid]
    name = design_name(added.key)
    if added.extra.get("frame_style") == name:
        del added.extra["frame_style"]
    entries = styles(project)
    if name in entries and not any(a.extra.get("frame_style") == name for a in project.added.values()):
        for value in _images_of(entries[name]):
            replaced(project, value)
        del entries[name]


def window_of_style(project, name) -> dict:
    '''The picture's window of a frame style: its "art" part where it has one, else the presets'.'''
    entry = styles(project).get(name) if isinstance(name, str) else None
    part = entry.get("art") if isinstance(entry, dict) else None
    window = dict(frame_presets.WINDOW)
    if isinstance(part, dict):
        for key in window:
            if isinstance(part.get(key), int) and not isinstance(part.get(key), bool):
                window[key] = part[key]
    return window


RETAIL_WINDOW = {"x": 19, "y": 50, "width": 102, "height": 96}      # where the game puts a card's picture


def _entry_of(project, choice):
    return styles(project).get(choice[1]) if choice is not None and choice[0] == "style" else None


def window_applies(project, choice) -> bool:
    """Whether the frame `choice` places the picture itself (a preset, a PNG, a style with an image or a full
    bleed); the game's own frame keeps the picture where the game puts it."""
    if choice is None:
        return False
    if choice[0] != "style":
        return True
    entry = _entry_of(project, choice)
    return isinstance(entry, dict) and (bool(entry.get("image")) or entry.get("full_bleed") is True)


def shows_game_frame(project, choice) -> bool:
    """Whether the game draws its own frame for `choice`: no frame of the card's own, or a style with no image that
    keeps it (no full_bleed, or full_bleed and game_frame)."""
    if choice is None:
        return True
    if choice[0] != "style":
        return False
    entry = _entry_of(project, choice)
    if not isinstance(entry, dict):
        return True
    return not entry.get("image") and (entry.get("full_bleed") is not True or entry.get("game_frame") is True)


def window_of_choice(project, choice) -> dict:
    if window_applies(project, choice):
        return window_of_style(project, choice[1]) if choice[0] == "style" else dict(frame_presets.WINDOW)
    return dict(RETAIL_WINDOW)


def frame_of(project, cid: int):
    """The choice that gives the variant its frame now, as set_frame takes it."""
    name = project.added[cid].extra.get("frame_style")
    if not isinstance(name, str) or not name:
        return None
    for preset in frame_presets.PRESETS:
        if name == PRESET_PREFIX + preset:
            return ("preset", preset)
    return ("style", name)


def frame_picture(project, cid: int):
    """The pngio.Image of the variant's frame, or None (no frame of its own, or a picture not found)."""
    name = project.added[cid].extra.get("frame_style")
    entry = styles(project).get(name) if isinstance(name, str) else None
    file = entry.get("image") if isinstance(entry, dict) else None
    data = _held(project, file) if isinstance(file, str) else None
    if data is None:
        return None
    try:
        return pngio.decode(data)
    except (pngio.PngError, ValueError):
        return None


# --- making, changing and removing -----------------------------------------------------

def add_variant(project, base: int, image=None, frame=None, permille: int = 50, label: str = "",
                key: str = None, full_art: bool = False, finish: str = ""):
    """A new variant of retail card `base`: (its id, notes on its picture). `image` is a pngio.Image."""
    check_base(base)
    check_chance(permille)
    check_label(label)
    check_finish(finish)
    if key is not None and (len(key) > KEY_MAX or not KEY_RE.match(key) or
                            any(a.key == key for a in project.added.values())):
        raise ValueError("the key is letters, digits, - and _ (80 at most), and no other card of the mod has it")
    cid = project.add_card(base, key or suggest_key(project, base))
    extra = project.added[cid].extra
    extra["variant_permille"] = permille
    if label:
        extra["variant_label"] = label
    if finish:
        extra["finish"] = finish
    notes = []
    try:
        set_frame(project, cid, frame)
        if image is not None:
            notes = set_art(project, cid, image, full_art)
    except ValueError:
        project.remove_card(cid)
        raise
    return cid, notes


def set_chance(project, cid: int, permille: int):
    check_chance(permille)
    project.added[cid].extra["variant_permille"] = permille


def set_finish(project, cid: int, finish: str):
    """The foil the card's view shows over it: "glossy", "royal", or "" for none."""
    check_finish(finish)
    extra = project.added[cid].extra
    if finish:
        extra["finish"] = finish
    else:
        extra.pop("finish", None)


def set_label(project, cid: int, label: str):
    check_label(label)
    extra = project.added[cid].extra
    if label:
        extra["variant_label"] = label
    else:
        extra.pop("variant_label", None)


def full_art_window(aspect: float) -> dict:
    """The picture's window for a full art card: the picture (of width / height `aspect`) laid over the
    whole card as far as it covers it, centred, what is past the card's edge cut off by the game."""
    card_w, card_h = frame_presets.CARD_W, frame_presets.CARD_H
    if aspect >= card_w / card_h:
        height, width = card_h, round(card_h * aspect)
    else:
        width, height = card_w, round(card_w / aspect)
    return {"x": (card_w - width) // 2, "y": (card_h - height) // 2, "width": width, "height": height}


def make_full_art(project, cid: int, aspect: float):
    """The variant's card, a full art one: its own design, the picture's window over the whole card. A card
    with no frame picture of its own gets the parts it needs over a picture (the name, and white numbers: the
    game's own numbers cannot be seen on a dark picture); one with a frame keeps its frame, under the picture."""
    name = own_design(project, cid)
    entry = styles(project)[name]
    entry["art"] = full_art_window(aspect)
    entry["parts_over_art"] = True          # the name, stars, element and ATK/DEF show over a picture past its window
    # The duel hand's small card: the whole picture over the whole 52 x 60 card, as the big one (the game draws the
    # small picture into this box, and the game's own hand card shows through where it is clear).
    entry.setdefault("hand", {}).setdefault("art", {"x": 0, "y": 0, "width": 52, "height": 60})
    if not entry.get("image"):
        # The game's own frame stays under the picture (game_frame): with the name, the ATK and DFD words and the numbers
        # left out, they are the game's own, where it puts them (card_layout.c).
        entry["full_bleed"] = True
        entry["game_frame"] = True


def has_game_frame(project, name) -> bool:
    entry = styles(project).get(name) if isinstance(name, str) else None
    return isinstance(entry, dict) and entry.get("game_frame") is True and not entry.get("image")


def set_art(project, cid: int, image, whole: bool = False) -> list:
    """The variant's picture. `whole` keeps all of it, as a full art card's: the card gets its own design with
    the picture laid over the whole card (make_full_art)."""
    notes = art.set_image(project, cid, "art", image, whole)
    extra = project.added[cid].extra
    if whole and not image.opaque():
        extra["art_transparent"] = True          # the game keeps the picture's clear parts clear (cards.c)
    else:
        extra.pop("art_transparent", None)
    if whole:
        # The small picture (the hand's, the field's) is the middle of the picture as it is: the game would make it
        # from the squeezed one, and stretch it.
        art.set_image(project, cid, "thumbnail", image, whole=True)
        make_full_art(project, cid, image.width / image.height)
        notes.append("the card has a design of its own now: its picture covers the card")
    return notes


def remove_variant(project, cid: int):
    if not is_variant(project, cid):
        raise ValueError("not a variant")
    project.remove_card(cid)


def unused_styles(project) -> list:
    """The frame styles no card of the mod names (a preset taken from the last variant that used it)."""
    used = {a.extra.get("frame_style") for a in project.added.values()}
    used |= {e.get("frame_style") for e in project.card_extra.values() if isinstance(e, dict)}
    return [name for name in styles(project) if name not in used]


# --- the picture of the card -----------------------------------------------------------

def over(base: pngio.Image, top: pngio.Image, left: int = 0, top_edge: int = 0) -> pngio.Image:
    """`top` laid over `base` at (left, top_edge), by its alpha: a new Image the size of `base`."""
    out = bytearray(base.rgba)
    for y in range(top.height):
        by = y + top_edge
        if not 0 <= by < base.height:
            continue
        for x in range(top.width):
            bx = x + left
            if not 0 <= bx < base.width:
                continue
            at, to = (y * top.width + x) * 4, (by * base.width + bx) * 4
            a = top.rgba[at + 3]
            if a == 0:
                continue
            if a == 255:
                out[to:to + 3] = top.rgba[at:at + 3]
            else:
                for c in range(3):
                    out[to + c] = (top.rgba[at + c] * a + out[to + c] * (255 - a)) // 255
            out[to + 3] = 255
    return pngio.Image(base.width, base.height, bytes(out))


# --- layered artwork: a background and a foreground laid into one picture ----------------------------------

LAYERS_DIR = "art/layers"
LAYER_NAMES = ("background", "foreground")


def layer_height(image, width: int) -> int:
    return max(1, round(width * image.height / image.width))


def default_layer(name: str, image) -> dict:
    """Where a layer goes at first, in card units (the card is 140 x 196): the background in the game's picture
    window, the foreground across the card's width and down to its bottom edge."""
    if name == "background":
        return {"x": RETAIL_WINDOW["x"], "y": RETAIL_WINDOW["y"], "width": RETAIL_WINDOW["width"]}
    return {"x": 0, "y": frame_presets.CARD_H - layer_height(image, frame_presets.CARD_W),
            "width": frame_presets.CARD_W}


HAND_SIZE = (52, 60)         # the duel hand's small card, in units


def compose_layers(layers, scale: int = 4, units=None) -> pngio.Image:
    """The card-sized picture (140 x 196 units, or `units`, `scale` pixels a unit) made of `layers`, bottom first:
    each (image, x, y, width) in card units, its height from its own shape, laid by its alpha over what is under
    it. What no layer covers stays clear, and what runs past the card's edge is cut off."""
    units = units or (frame_presets.CARD_W, frame_presets.CARD_H)
    width, height = units[0] * scale, units[1] * scale
    out = bytearray(width * height * 4)
    for image, x, y, layer_width in layers:
        w = max(1, round(layer_width * scale))
        h = max(1, round(w * image.height / image.width))
        picture = image if (w, h) == image.size else pngio.resample(image, w, h)
        left, top = round(x * scale), round(y * scale)
        source = picture.rgba
        for row in range(max(0, -top), min(h, height - top)):
            at = ((top + row) * width + max(left, 0)) * 4
            first = max(0, -left)
            sat = (row * w + first) * 4
            for _ in range(first, min(w, width - left)):
                a = source[sat + 3]
                if a == 255:
                    out[at:at + 4] = source[sat:sat + 4]
                elif a:
                    ba = out[at + 3]
                    if ba == 0:
                        out[at:at + 4] = source[sat:sat + 4]
                    else:
                        total = a + ba * (255 - a) // 255
                        for c in range(3):
                            out[at + c] = (source[sat + c] * a + out[at + c] * ba * (255 - a) // 255) // total
                        out[at + 3] = total
                at += 4
                sat += 4
    return pngio.Image(width, height, bytes(out))


def default_hand_layer(place: dict) -> dict:
    """Where a layer goes on the hand's small card (52 x 60 units) when it is at `place` on the card: the same place
    in proportion, its shape kept."""
    scale_x = HAND_SIZE[0] / frame_presets.CARD_W
    return {"x": round(place["x"] * scale_x, 1), "y": round(place["y"] * HAND_SIZE[1] / frame_presets.CARD_H, 1),
            "width": max(1, round(place["width"] * scale_x, 1))}


def _layer_file(key: str, name: str) -> str:
    return f"{LAYERS_DIR}/{key}-{name}.png"


def _place(value):
    numbers = {k: value[k] for k in ("x", "y", "width") if isinstance(value, dict) and isinstance(value.get(k), (int, float))}
    return numbers if len(numbers) == 3 else None


def read_layers(project, cid: int) -> dict:
    """The layers a variant's picture was made of: {name: (image, place on the card, place on the hand's small
    card)}, each place {"x", "y", "width"} (the hand's None when it was not given); {} when it was not made of layers."""
    key = project.added[cid].key
    data = _held(project, f"{LAYERS_DIR}/{key}.json")
    if data is None:
        return {}
    try:
        spec = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    found = {}
    for name in LAYER_NAMES:
        place = spec.get(name) if isinstance(spec, dict) else None
        picture = _held(project, _layer_file(key, name))
        if not isinstance(place, dict) or picture is None:
            continue
        numbers = _place(place)
        try:
            image = pngio.decode(picture)
        except (pngio.PngError, ValueError):
            continue
        if numbers:
            found[name] = (image, numbers, _place(place.get("hand")))
    return found


def set_layers(project, cid: int, layers: dict) -> list:
    """The variant's picture made of `layers` ({name: (image, place[, hand place])}, places {"x", "y", "width"} in
    units: on the card, and on the hand's small card, in proportion when not given; a background and/or a
    foreground): they are kept in the mod (art/layers/) to be changed again, composed into the card's picture and
    into the small one the hand shows, and the card made a full art one (set_art). Notes on the picture."""
    chosen = []
    for name in LAYER_NAMES:
        if layers.get(name):
            image, place, *hand = layers[name]
            chosen.append((name, image, place, (hand[0] if hand and hand[0] else None) or default_hand_layer(place)))
    if not chosen:
        raise ValueError("choose a picture for at least one layer")
    for name, image, place, hand in chosen:
        if place["width"] < 1 or hand["width"] < 1:
            raise ValueError(f"the {name}'s width is at least 1 unit")
    key = project.added[cid].key
    composed = compose_layers([(image, p["x"], p["y"], p["width"]) for _, image, p, _ in chosen])
    notes = set_art(project, cid, composed, whole=True)
    small = compose_layers([(image, h["x"], h["y"], h["width"]) for _, image, _, h in chosen], units=HAND_SIZE)
    art.set_image(project, cid, "thumbnail", small, whole=True)          # the picture the hand's card shows
    if not small.opaque():
        project.added[cid].extra["art_transparent"] = True
    spec = {}
    for name, image, place, hand in chosen:
        project.files[_layer_file(key, name)] = pngio.encode(image)
        spec[name] = {"x": place["x"], "y": place["y"], "width": place["width"],
                      "hand": {"x": hand["x"], "y": hand["y"], "width": hand["width"]}}
    project.files[f"{LAYERS_DIR}/{key}.json"] = json.dumps(spec, indent=1).encode("utf-8")
    for name in LAYER_NAMES:                                  # a layer taken away is not kept
        if name not in spec:
            project.files.pop(_layer_file(key, name), None)
    return notes


def hand_picture(art_image, frame_image, width: int = 104) -> pngio.Image:
    """The duel hand's small card (52 x 60 units, `width` pixels across): the game's own card behind, the picture
    laid over the whole of it, as the game draws the small picture. Either may be None."""
    height = round(width * HAND_SIZE[1] / HAND_SIZE[0])
    canvas = pngio.Image(width, height, bytes((0x20, 0x20, 0x28, 255)) * (width * height))
    if frame_image is not None:
        canvas = over(canvas, pngio.scale_to(frame_image, width, height))
    if art_image is not None:
        canvas = over(canvas, pngio.scale_to(art_image, width, height))
    return canvas


def card_picture(art_image, frame_image, width: int = 140, window: dict = None) -> pngio.Image:
    """The card as its frame lays out its picture (the places in frame_presets.WINDOW): the
    picture cut to the window and the frame over it, `width` pixels across. Either may be None."""
    scale = width / frame_presets.FRAME_W
    height = round(frame_presets.FRAME_H * scale)
    canvas = pngio.Image(width, height, bytes((0x20, 0x20, 0x28, 255)) * (width * height))
    window = window or frame_presets.WINDOW     # the frame's units: the picture's x, y, width and height
    # As the game draws it: the frame behind, the picture stretched over its window (a window past the
    # card's edge is cut at the edge: a full art card's), and the rest of the card over both.
    if frame_image is not None:
        canvas = over(canvas, pngio.scale_to(frame_image, width, height))
    if art_image is not None:
        left, top = window["x"] * scale, window["y"] * scale
        w, h = window["width"] * scale, window["height"] * scale
        x0, y0, x1, y1 = max(0, round(left)), max(0, round(top)), min(width, round(left + w)), min(height, round(top + h))
        if x1 > x0 and y1 > y0 and w > 0 and h > 0:
            sx, sy = art_image.width / w, art_image.height / h
            box = ((x0 - left) * sx, (y0 - top) * sy, (x1 - x0) * sx, (y1 - y0) * sy)
            canvas = over(canvas, pngio.resample(art_image, x1 - x0, y1 - y0, box), x0, y0)
    return canvas
