"""The variants engine (variants.py): variants made in a project, what is written for the game, what is read
back, and the checks. On synthetic data:

    python -m unittest discover -s tools/pc/fm_editor/tests -t tools/pc
"""
import json
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk
from pathlib import Path
from unittest import mock

from fm_editor import art, card_icons, compat, frame_presets, manifest, pngio, text_presets, ui_frames, validate, variants
from fm_editor.model import Project, replaced
from fm_editor.pngio import Image
from fm_editor.tests.test_data import fixture
from fm_editor.tests.test_gui import GuiCase


def picture(width, height, color):
    return Image(width, height, bytes(color) * (width * height))


def errors(project):
    return [i for i in validate.validate(project) if i.level == "error"]


class VariantsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.game = fixture().game()
        self.project = Project(self.game)

    def tearDown(self):
        self.tmp.cleanup()

    def test_alt_art(self):
        cid, notes = variants.add_variant(self.project, 1, picture(204, 192, (200, 30, 30, 255)), None, 50, "Alt art")
        added = self.project.added[cid]
        self.assertEqual((added.base, added.extra["variant_permille"], added.extra["variant_label"]), (1, 50, "Alt art"))
        self.assertTrue(added.extra["art"].startswith("art/"))
        self.assertNotIn("frame_style", added.extra)
        self.assertEqual(notes, [])
        # The base card's own name, which is why no "name" is written.
        self.assertEqual(self.project.cards[cid].name, self.project.cards[1].name)
        # No frame of its own: no layout and no switch added.
        self.assertNotIn("card_layout", self.project.other)
        self.assertEqual(self.project.info.settings, [])
        self.assertTrue(variants.is_variant(self.project, cid))
        self.assertFalse(variants.is_variant(self.project, 1))
        found = variants.variants(self.project)
        self.assertEqual([(v.cid, v.base, v.permille, v.label) for v in found], [(cid, 1, 50, "Alt art")])
        self.assertEqual(variants.family(self.project, 1), found)
        self.assertEqual(variants.family(self.project, 2), [])

    def test_a_preset_frame(self):
        cid, _ = variants.add_variant(self.project, 1, None, ("preset", "rainbow"), 50, "Rainbow foil")
        extra = self.project.added[cid].extra
        self.assertEqual(extra["frame_style"], "foil-rainbow")
        entry = self.project.other["card_layout"]["frame_styles"]["foil-rainbow"]
        self.assertEqual((entry["image"], entry["hand_color"], entry["width"], entry["height"]),
                         ("frames/foil-rainbow.png", "purple", 140, 197))
        # The places the game puts the card's parts on the frame.
        self.assertEqual(entry["art"], {"x": 3, "y": 19, "width": 134, "height": 123})
        self.assertEqual(entry["title"]["y"], 4)
        self.assertEqual(entry["spell"]["art"], entry["art"])
        image = pngio.decode(self.project.files["frames/foil-rainbow.png"])
        self.assertEqual(image.size, (256, 512))
        # The mod needs no switch: a mod of styles alone has them on (card_layout.c).
        self.assertEqual(self.project.info.settings, [])
        # A second variant with the same preset shares the style and the picture.
        other, _ = variants.add_variant(self.project, 35, None, ("preset", "rainbow"), 100, "")
        self.assertEqual(self.project.added[other].extra["frame_style"], "foil-rainbow")
        self.assertEqual(list(self.project.other["card_layout"]["frame_styles"]), ["foil-rainbow"])
        self.assertEqual([k for k in self.project.files if k.startswith("frames/")], ["frames/foil-rainbow.png"])
        self.assertNotIn("variant_label", self.project.added[other].extra)
        # Each preset is a picture the editor carries.
        for name in frame_presets.PRESETS:
            self.assertEqual(pngio.decode(frame_presets.png(name)).size, (256, 512))
        self.assertEqual(variants.unused_styles(self.project), [])
        # The style of a preset is shown as the preset, and not offered twice.
        self.assertEqual(variants.frame_of(self.project, cid), ("preset", "rainbow"))
        self.assertEqual([c for _, c in variants.frame_choices(self.project) if c and c[0] == "style"], [])
        variants.set_frame(self.project, cid, None)
        variants.set_frame(self.project, other, None)
        self.assertEqual(variants.unused_styles(self.project), ["foil-rainbow"])

    def test_a_frame_of_the_modders_own(self):
        data = pngio.encode(picture(140, 197, (10, 90, 200, 255)))
        cid, _ = variants.add_variant(self.project, 2, None, ("png", data, "My Frame!"), 25, "Mine")
        name = self.project.added[cid].extra["frame_style"]
        self.assertEqual(name, "custom-my-frame")
        self.assertEqual(self.project.other["card_layout"]["frame_styles"][name]["image"], "frames/custom-my-frame.png")
        self.assertEqual(self.project.files["frames/custom-my-frame.png"], data)
        # The same picture again is the same style; another picture under that name gets its own.
        again, _ = variants.add_variant(self.project, 3, None, ("png", data, "My Frame!"), 25, "")
        self.assertEqual(self.project.added[again].extra["frame_style"], name)
        other = pngio.encode(picture(140, 197, (200, 90, 10, 255)))
        third, _ = variants.add_variant(self.project, 4, None, ("png", other, "My Frame!"), 25, "")
        self.assertEqual(self.project.added[third].extra["frame_style"], "custom-my-frame-2")
        self.assertNotEqual(self.project.files["frames/custom-my-frame.png"],
                            self.project.files["frames/custom-my-frame-2.png"])
        # A style the mod has can be named.
        variants.set_frame(self.project, again, ("style", "custom-my-frame-2"))
        self.assertEqual(self.project.added[again].extra["frame_style"], "custom-my-frame-2")
        self.assertIn(("This mod's \"custom-my-frame\"", ("style", "custom-my-frame")), variants.frame_choices(self.project))

    def test_what_is_refused(self):
        project = self.project
        cards = len(project.added)
        for base in (17, 21, 0, 723, "1"):
            with self.assertRaises(ValueError, msg=base):
                variants.add_variant(project, base, None, None, 50, "")
        for chance in (0, 1001, -5, 2.5, True):
            with self.assertRaises(ValueError, msg=chance):
                variants.add_variant(project, 1, None, None, chance, "")
        with self.assertRaises(ValueError):
            variants.add_variant(project, 1, None, None, 50, "x" * 25)
        with self.assertRaises(ValueError):
            variants.add_variant(project, 1, None, None, 50, "", key="no spaces")
        with self.assertRaises(ValueError):
            variants.add_variant(project, 1, None, ("png", b"not a png", "bad"), 50, "")
        with self.assertRaises(ValueError):
            variants.add_variant(project, 1, None, ("preset", "nothing"), 50, "")
        with self.assertRaises(ValueError):
            variants.add_variant(project, 1, None, ("style", "nothing"), 50, "")
        self.assertEqual(len(project.added), cards)           # none left behind
        variants.add_variant(project, 1, None, None, 50, "", key="mine")
        with self.assertRaises(ValueError):
            variants.add_variant(project, 1, None, None, 50, "", key="mine")   # a key is one card's
        with self.assertRaises(ValueError):
            variants.remove_variant(project, 1)

    def test_chance_and_keys(self):
        self.assertEqual([variants.percent_text(p) for p in (1, 25, 50, 1000)], ["0.1%", "2.5%", "5%", "100%"])
        for text, want in (("5", 50), ("2.5%", 25), ("0,5", 5), (" 100 % ", 1000), ("0.1", 1)):
            self.assertEqual(variants.parse_percent(text), want, text)
        for text in ("", "x", "0", "0.04", "100.1", "-1"):
            self.assertIsNone(variants.parse_percent(text), text)
        first = variants.suggest_key(self.project, 1)
        self.assertEqual(first, "blue-eyes-white-dragon-alt-1" if self.project.cards[1].name == "Blue-eyes White Dragon"
                         else first)
        cid, _ = variants.add_variant(self.project, 1, None, None, 50, "", key=first)
        self.assertNotEqual(variants.suggest_key(self.project, 1), first)
        self.assertTrue(variants.suggest_key(self.project, 1).endswith("-alt-2"))
        self.assertRegex(variants.suggest_key(self.project, 1), r"^[a-z0-9-]+$")

    def test_a_finish(self):
        cid, _ = variants.add_variant(self.project, 1, None, None, 50, "Shiny", finish="royal")
        self.assertEqual(self.project.added[cid].extra["finish"], "royal")
        self.assertEqual(variants.read(self.project, cid).finish, "royal")
        variants.set_finish(self.project, cid, "glossy")
        self.assertEqual(self.project.added[cid].extra["finish"], "glossy")
        variants.set_finish(self.project, cid, "")
        self.assertNotIn("finish", self.project.added[cid].extra)
        self.assertEqual(variants.read(self.project, cid).finish, "")
        for bad in ("shiny", "Royal"):
            with self.assertRaises(ValueError):
                variants.set_finish(self.project, cid, bad)
            with self.assertRaises(ValueError):
                variants.add_variant(self.project, 1, None, None, 50, "", finish=bad)
        self.assertEqual(len(variants.variants(self.project)), 1)    # the refused one left nothing behind
        # What the editor writes is what the game reads, and a mistaken one is flagged.
        variants.set_finish(self.project, cid, "royal")
        self.assertEqual(errors(self.project), [])
        self.project.added[cid].extra["finish"] = "sparkly"
        self.assertTrue([i for i in validate.validate(self.project) if "finish" in i.message])
        self.assertEqual(variants.read(self.project, cid).finish, "")    # not shown as a choice

    def test_changing_and_removing(self):
        cid, _ = variants.add_variant(self.project, 1, None, None, 50, "One")
        variants.set_chance(self.project, cid, 300)
        variants.set_label(self.project, cid, "Two")
        self.assertEqual(variants.read(self.project, cid).permille, 300)
        self.assertEqual(variants.read(self.project, cid).label, "Two")
        variants.set_label(self.project, cid, "")
        self.assertNotIn("variant_label", self.project.added[cid].extra)
        with self.assertRaises(ValueError):
            variants.set_chance(self.project, cid, 0)
        with self.assertRaises(ValueError):
            variants.set_label(self.project, cid, "y" * 30)
        variants.set_art(self.project, cid, picture(102, 96, (1, 2, 3, 255)))
        self.assertIn("art", self.project.added[cid].extra)
        variants.remove_variant(self.project, cid)
        self.assertNotIn(cid, self.project.added)
        self.assertEqual(variants.variants(self.project), [])

    def test_saved_and_read_back(self):
        art_image = picture(204, 192, (20, 120, 220, 255))
        cid, _ = variants.add_variant(self.project, 1, art_image, ("preset", "gold"), 50, "Gold foil", key="bewd-gold")
        variants.add_variant(self.project, 35, art_image, None, 100, "Alt art", key="dm-alt")
        self.assertEqual(errors(self.project), [])
        folder = self.root / "mod"
        manifest.save_mod(self.project, folder)
        written = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
        gold = next(e for e in written["cards"] if e.get("id") == "bewd-gold")
        self.assertEqual({k: v for k, v in gold.items() if k not in ("art",)},
                         {"copy": 1, "id": "bewd-gold", "variant_permille": 50, "variant_label": "Gold foil",
                          "frame_style": "foil-gold"})
        self.assertEqual(gold["art"], "art/bewd-gold.png")
        alt = next(e for e in written["cards"] if e.get("id") == "dm-alt")
        self.assertNotIn("frame_style", alt)
        self.assertIn("foil-gold", written["card_layout"]["frame_styles"])
        self.assertNotIn("settings", written)
        self.assertEqual(written["min_api"], compat.HOST_API)
        for file in ("art/bewd-gold.png", "art/dm-alt.png", "frames/foil-gold.png"):
            self.assertTrue((folder / file).is_file(), file)
        # Read back, it is the same.
        again, _ = manifest.open_mod(self.game, folder)
        found = variants.variants(again)
        self.assertEqual([(v.key, v.base, v.permille, v.label, v.frame_style) for v in found],
                         [("bewd-gold", 1, 50, "Gold foil", "foil-gold"), ("dm-alt", 35, 100, "Alt art", "")])
        self.assertEqual(errors(again), [])
        self.assertEqual(variants.frame_picture(again, found[0].cid).size, (256, 512))
        self.assertIsNone(variants.frame_picture(again, found[1].cid))

    def test_a_replaced_picture_is_not_left_in_the_folder(self):
        art_image = picture(204, 192, (20, 120, 220, 255))
        cid, _ = variants.add_variant(self.project, 1, art_image, None, 50, "Mine", key="mine")
        name = variants.own_design(self.project, cid)
        entry = variants.styles(self.project)[name]
        first, second = "frames/one.png", "frames/two.png"
        self.project.files[first] = frame_presets.png("gold")
        entry["image"] = first
        folder = self.root / "mod"
        manifest.save_mod(self.project, folder)
        self.assertTrue((folder / first).is_file())
        # The frame is replaced by another picture: the first is not named any more.
        self.project.files[second] = frame_presets.png("silver")
        entry["image"] = second
        replaced(self.project, first)
        replaced(self.project, "art/not-ours.png")           # only frames/ and ui/ are swept
        manifest.save_mod(self.project, folder)
        self.assertFalse((folder / first).exists())
        self.assertTrue((folder / second).is_file())
        self.assertNotIn(first, self.project.files)
        # A picture still named by another style is kept.
        other = variants.styles(self.project).setdefault("other", {"image": second})
        entry["image"] = "frames/three.png"
        self.project.files["frames/three.png"] = frame_presets.png("rainbow")
        replaced(self.project, second)
        manifest.save_mod(self.project, folder)
        self.assertTrue((folder / second).is_file())
        # The variant's design taken away: its pictures go with it.
        variants.remove_own_design(self.project, cid)
        manifest.save_mod(self.project, folder)
        self.assertFalse((folder / "frames/three.png").exists())

    def test_a_jpeg_picture(self):
        try:
            from PIL import Image as Picture
        except ImportError:
            self.skipTest("Pillow is not installed")
        path = self.root / "art.jpg"
        Picture.new("RGB", (60, 40), (200, 30, 30)).save(path, "JPEG")
        image = pngio.read(path)
        self.assertEqual(image.size, (60, 40))
        red, green, blue, alpha = image.rgba[:4]
        self.assertTrue(red > 150 and green < 80 and blue < 80 and alpha == 255)
        # A PNG is read as it always was, and a file of no picture kind is refused.
        pngio.write(self.root / "a.png", picture(2, 2, (1, 2, 3, 255)))
        self.assertEqual(pngio.read(self.root / "a.png").size, (2, 2))
        (self.root / "bad.jpg").write_bytes(b"not a picture")
        with self.assertRaises(pngio.PngError):
            pngio.read(self.root / "bad.jpg")
        # Without Pillow the message says what to do.
        with mock.patch.dict("sys.modules", {"PIL": None}):
            with self.assertRaises(pngio.PngError) as caught:
                pngio.read(path)
        self.assertIn("Pillow", str(caught.exception))

    def test_the_games_own_back_and_library_icon(self):
        columns, palettes = card_icons.FRAME_COLUMNS, card_icons.CARD_PALETTES
        right, foot = columns + card_icons.FRAME_COLUMN, columns + 2 * card_icons.FRAME_COLUMN
        wa = bytearray(palettes + 14 * 0x200)
        wa[right + 128 * 128] = 1                      # the right page's row 128, texel 0: the card's top left
        wa[foot + 63 * 128 + 127] = 1                  # the foot page's row 63, texel 127: card x 127, row 191
        wa[right + 16] = 1                             # the right edge's top: card x 128, row 0
        wa[right + 63 * 128 + 59] = 1                  # its bottom: card x 139, row 128 + 63
        wa[right + 5 * 128 + 5] = 1                    # in no part of the back
        word = 31 | 8 << 5 | 16 << 10
        wa[palettes + 9 * 0x200 + 2], wa[palettes + 9 * 0x200 + 3] = word & 255, word >> 8     # the magic frame's row
        back = card_icons.card_back(bytes(wa), 1)
        self.assertEqual((back.width, back.height), (140, 197))
        pixel = lambda x, y: tuple(back.rgba[(y * 140 + x) * 4:(y * 140 + x) * 4 + 4])
        for at in ((0, 0), (127, 191), (128, 0), (139, 191), (0, 195)):     # the last turned over from the top's
            self.assertEqual(pixel(*at), (255, 66, 132, 255), at)
        self.assertEqual(pixel(5, 5)[3], 0)
        self.assertEqual(pixel(0, 192)[3], 0)
        self.assertIsNone(card_icons.card_back(b"short", 0))
        self.assertIsNone(card_icons.card_back(bytes(wa), 6))
        # The Library's icon: 12 x 14 at (96, 112) of its sheet, 4 bits a texel, in the row of its kind.
        sheet, clut = card_icons.LIBRARY_ICON
        icons = bytearray(clut + 12 * 0x20)
        icons[sheet + 112 * 128 + 96 // 2] = 1 | 1 << 4                 # texels 96 and 97 of row 112
        icons[clut + 6 * 0x20 + 2], icons[clut + 6 * 0x20 + 3] = word & 255, word >> 8        # magic: row 6
        icon = card_icons.library_icon(bytes(icons), 1)
        self.assertEqual((icon.width, icon.height), (12, 14))
        self.assertEqual(tuple(icon.rgba[0:4])[3], 255)
        self.assertIsNone(card_icons.library_icon(bytes(icons), 0))     # the monster's row has no color for it
        self.assertIsNone(card_icons.library_icon(b"short", 0))

    def test_the_games_own_frame(self):
        # The frame sheet: a pixel of index 1 at the top left of column 0, one at the right edge of the card (column 1),
        # and the palette of the monster frame (row 8) giving index 1 a color.
        base, palettes = card_icons.CARD_SHEET - 3 * 0x8000, card_icons.CARD_PALETTES
        wa = bytearray(palettes + 14 * 0x200)
        wa[base] = 1
        wa[base + 0x8000 + 4] = 1                                     # the right edge's first texel: card x 128, row 0
        wa[base + 0x8000 + 67 * 128 + 47] = 1                         # the lower edge's last: card x 139, row 128 + 67
        wa[base + 191 * 128] = 1                                      # the body's last row
        wa[base + 192 * 128 + 5] = 1                                  # past the card's body: the left page's, not in it
        wa[base + 208 * 128 + 2] = 1                                  # a non-monster's panel, from the left page's row 208
        word = 31 | 8 << 5 | 16 << 10                                 # 5 bits a channel
        wa[palettes + 8 * 0x200 + 2], wa[palettes + 8 * 0x200 + 3] = word & 255, word >> 8
        frame = card_icons.card_frame(bytes(wa), 0)
        self.assertEqual((frame.width, frame.height), (140, 197))
        pixel = lambda x, y: tuple(frame.rgba[(y * 140 + x) * 4:(y * 140 + x) * 4 + 4])
        self.assertEqual(pixel(0, 0), (255, 66, 132, 255))
        self.assertEqual(pixel(128, 0)[3], 255)
        self.assertEqual(pixel(139, 195)[3], 255)                     # the edge reaches the card's last row
        self.assertEqual(pixel(0, 191)[3], 255)
        self.assertEqual(pixel(5, 192)[3], 0)                         # the page's row 192 is not the card's
        self.assertEqual(pixel(0, 195)[3], 255)                       # the bottom border is the top one turned over
        self.assertEqual(pixel(0, 196)[3], 0)                         # the card is 196 rows of the 197
        self.assertEqual(pixel(5, 5)[3], 0)                           # index 0 is clear
        self.assertEqual(pixel(2, 144)[3], 0)                         # a monster's plaque has no panel's row
        panel = card_icons.card_frame(bytes(wa), 0, False)
        self.assertEqual(panel.rgba[(144 * 140 + 2) * 4 + 3], 255)    # a card that is not one has it
        self.assertIsNone(card_icons.card_frame(b"short", 0))
        self.assertIsNone(card_icons.card_frame(bytes(wa), 6))
        # With no picture of its own the game's frame is drawn, and its picture goes where the game puts it.
        project = self.project
        self.assertFalse(variants.window_applies(project, None))
        self.assertTrue(variants.shows_game_frame(project, None))
        self.assertTrue(variants.window_applies(project, ("preset", "gold")))
        self.assertFalse(variants.shows_game_frame(project, ("preset", "gold")))
        self.assertEqual(variants.window_of_choice(project, None), variants.RETAIL_WINDOW)
        self.assertEqual(variants.window_of_choice(project, ("preset", "gold")), frame_presets.WINDOW)
        styles = variants._object(project, "card_layout", "frame_styles")
        styles["bare"] = {"hand_color": "gold", "art": {"x": 1, "y": 2, "width": 3, "height": 4}}
        styles["full"] = {"hand_color": "gold", "full_bleed": True, "art": {"x": 1, "y": 2, "width": 30, "height": 40}}
        styles["framed"] = {"hand_color": "gold", "image": "frames/x.png", "art": {"x": 5, "y": 6, "width": 7, "height": 8}}
        self.assertFalse(variants.window_applies(project, ("style", "bare")))
        self.assertTrue(variants.shows_game_frame(project, ("style", "bare")))
        self.assertEqual(variants.window_of_choice(project, ("style", "bare")), variants.RETAIL_WINDOW)   # its art part is ignored
        self.assertTrue(variants.window_applies(project, ("style", "full")))
        self.assertFalse(variants.shows_game_frame(project, ("style", "full")))       # full bleed: no frame at all
        styles["kept"] = {"hand_color": "gold", "full_bleed": True, "game_frame": True,
                          "art": {"x": 1, "y": 2, "width": 50, "height": 60}}
        self.assertTrue(variants.shows_game_frame(project, ("style", "kept")))        # unless it keeps the game's
        self.assertTrue(variants.window_applies(project, ("style", "kept")))
        self.assertEqual(variants.window_of_choice(project, ("style", "kept"))["width"], 50)
        self.assertFalse(variants.shows_game_frame(project, ("style", "framed")))
        self.assertEqual(variants.window_of_choice(project, ("style", "full"))["width"], 30)
        self.assertEqual(variants.window_of_choice(project, ("style", "framed"))["width"], 7)

    def test_the_frame_colour_of_the_hand_follows_the_card(self):
        frame_png = pngio.encode(picture(8, 16, (200, 180, 40, 255)))
        by_type = {}
        for cid, card in self.project.cards.items():
            if cid <= 722 and cid not in variants.EXODIA:
                by_type.setdefault(card.shown_frame(), cid)
        wanted = {0: "gold", 1: "green", 2: "pink", 3: "blue"}
        self.assertTrue(set(wanted) <= set(by_type), by_type)          # the fixture has a card of each colour
        for index, name in wanted.items():
            cid, _ = variants.add_variant(self.project, by_type[index], None, ("png", frame_png, f"mine-{index}"), 50, "",
                                          key=f"colour-{index}")
            style = variants.styles(self.project)[self.project.added[cid].extra["frame_style"]]
            self.assertEqual(style["hand_color"], name)                  # a monster's frame is gold, a spell's green...
            self.assertEqual(variants.hand_color_of(self.project, cid), name)
        # A card with a frame colour of its own keeps it; the presets' own colours are theirs.
        card = self.project.cards[by_type[0]]
        self.project.cards[by_type[0]] = card.copy(frame=5)
        self.assertEqual(variants.hand_color_of(self.project, by_type[0]), "orange")
        self.project.cards[by_type[0]] = card
        rainbow, _ = variants.add_variant(self.project, by_type[1], None, ("preset", "rainbow"), 50, "", key="rain")
        self.assertEqual(variants.styles(self.project)["foil-rainbow"]["hand_color"], "purple")
        # A design with no frame of its own starts in the card's colour too.
        spell, _ = variants.add_variant(self.project, by_type[1], None, None, 50, "", key="spell-design")
        name = variants.own_design(self.project, spell)
        self.assertEqual(variants.styles(self.project)[name]["hand_color"], "green")

    def test_a_full_art_card(self):
        # A tall picture, kept whole: squeezed into the art's shape, the card's window stretches it back.
        tall = picture(200, 300, (30, 120, 200, 255))
        cid, notes = variants.add_variant(self.project, 35, tall, None, 50, "Full art", key="dm-full", full_art=True)
        stored = art.state(self.project).images[(cid, "art")].image
        self.assertEqual(stored.width * 96, stored.height * 102)                    # the art's shape: not cut
        self.assertTrue(any("all of it is kept" in n for n in notes))
        window = variants.full_art_window(200 / 300)
        self.assertEqual(window, {"x": 0, "y": -7, "width": 140, "height": 210})   # covers the card, centred
        self.assertEqual(variants.full_art_window(2.0), {"x": -126, "y": 0, "width": 392, "height": 196})
        self.assertEqual(variants.full_art_window(140 / 196), {"x": 0, "y": 0, "width": 140, "height": 196})
        name = variants.design_name("dm-full")
        entry = variants.styles(self.project)[name]
        self.assertEqual(entry["art"], window)
        # No frame picture: the parts a card over a picture needs, and white numbers (the game's own cannot be
        # seen on a dark picture).
        self.assertIs(entry["full_bleed"], True)
        self.assertIs(entry["parts_over_art"], True)      # the name, stars and numbers show over the picture
        self.assertIs(entry["game_frame"], True)          # on the game's own frame
        self.assertEqual(entry["hand"]["art"], {"x": 0, "y": 0, "width": 52, "height": 60})   # the hand's card too
        for key in ("title", "digits", "atk_label", "dfd_label"):
            self.assertNotIn(key, entry)                  # the name, words and numbers are the game's own then
        self.assertEqual(self.project.added[cid].extra["frame_style"], name)
        # The small picture (the hand's) is all of the picture too, in the small picture's shape.
        thumb = art.state(self.project).images[(cid, "thumbnail")].image
        self.assertEqual(thumb.width * 32, thumb.height * 40)          # the small picture's shape
        self.assertEqual(errors(self.project), [])
        # A picture that is not kept whole is cut, as ever, and takes no design.
        other, _ = variants.add_variant(self.project, 1, tall, None, 50, "Cut", key="bewd-cut")
        cut = art.state(self.project).images[(other, "art")].image
        self.assertEqual(cut.width, 200)                                                  # the middle, cut to the art's shape
        self.assertTrue(abs(cut.width / cut.height - 102 / 96) < 0.02 and cut.height < 200)
        self.assertNotIn("frame_style", self.project.added[other].extra)
        # With a frame, the frame stays (under the picture): only the window changes.
        framed, _ = variants.add_variant(self.project, 1, tall, ("preset", "gold"), 50, "Framed", key="bewd-framed",
                                         full_art=True)
        style = variants.styles(self.project)[variants.design_name("bewd-framed")]
        self.assertTrue(style["image"].startswith("frames/foil-gold"))
        self.assertNotIn("full_bleed", style)
        self.assertNotIn("game_frame", style)             # it has a frame of its own
        self.assertIs(style["parts_over_art"], True)
        self.assertEqual(style["art"], window)
        self.assertEqual(variants.styles(self.project)["foil-gold"]["art"]["width"], 134)   # the preset is as it was

    def test_a_full_art_picture_keeps_its_transparent_parts(self):
        # A figure on a transparent background: kept see-through, so the frame behind shows around it.
        rgba = bytearray()
        for y in range(120):
            for x in range(80):
                inside = 20 <= x < 60 and 20 <= y < 100
                rgba += bytes((200, 30, 30, 255)) if inside else bytes((0, 0, 0, 0))
        figure = Image(80, 120, bytes(rgba))
        cid, notes = variants.add_variant(self.project, 35, figure, ("preset", "gold"), 50, "Cut-out", key="dm-cutout",
                                          full_art=True)
        stored = art.state(self.project).images[(cid, "art")].image
        self.assertFalse(stored.opaque())
        self.assertEqual(stored.rgba[3], 0)                                        # a corner: see-through
        middle = ((stored.height // 2) * stored.width + stored.width // 2) * 4
        self.assertEqual(stored.rgba[middle + 3], 255)                              # the figure: solid
        self.assertTrue(any("see-through" in n for n in notes))
        thumb = art.state(self.project).images[(cid, "thumbnail")].image
        self.assertFalse(thumb.opaque())                                            # the hand's small picture keeps it clear too
        self.assertEqual(thumb.rgba[3], 0)
        self.assertIs(self.project.added[cid].extra["art_transparent"], True)         # the game keeps it clear
        # The preview lays it over the frame, which shows where it is clear.
        frame = picture(140, 197, (20, 200, 20, 255))
        card = variants.card_picture(stored, frame, 140, variants.full_art_window(80 / 120))
        self.assertEqual(tuple(card.rgba[0:3]), (20, 200, 20))
        centre = ((98 * 140) + 70) * 4
        self.assertEqual(tuple(card.rgba[centre:centre + 3]), (200, 30, 30))
        # A picture that is not kept whole is still drawn over black, as it always was.
        other, _ = variants.add_variant(self.project, 1, figure, None, 50, "Flat", key="bewd-flat")
        self.assertTrue(art.state(self.project).images[(other, "art")].image.opaque())
        self.assertNotIn("art_transparent", self.project.added[other].extra)
        # An opaque full art picture needs no flag; a new picture takes the flag away.
        opaque, _ = variants.add_variant(self.project, 1, picture(80, 120, (1, 2, 3, 255)), None, 50, "Solid",
                                         key="bewd-solid", full_art=True)
        self.assertNotIn("art_transparent", self.project.added[opaque].extra)
        variants.set_art(self.project, cid, figure, whole=False)
        self.assertNotIn("art_transparent", self.project.added[cid].extra)

    def test_layered_artwork(self):
        red = picture(10, 10, (200, 20, 20, 255))                          # the background: a solid square
        figure_rgba = bytearray()
        for y in range(20):
            for x in range(10):
                figure_rgba += bytes((20, 20, 200, 255)) if 3 <= x < 7 and 2 <= y < 18 else bytes((0, 0, 0, 0))
        figure = Image(10, 20, bytes(figure_rgba))                          # the foreground: a figure on a clear ground
        self.assertEqual(variants.default_layer("background", red), {"x": 19, "y": 50, "width": 102})
        self.assertEqual(variants.default_layer("foreground", figure), {"x": 0, "y": 196 - 280, "width": 140})
        layers = [(red, 20, 50, 100), (figure, 40, 20, 40)]
        composed = variants.compose_layers(layers, scale=2)
        self.assertEqual((composed.width, composed.height), (280, 392))
        pixel = lambda x, y: tuple(composed.rgba[(y * 280 + x) * 4:(y * 280 + x) * 4 + 4])
        self.assertEqual(pixel(2, 2), (0, 0, 0, 0))                          # no layer there: clear
        self.assertEqual(pixel(2 * 30, 2 * 60), (200, 20, 20, 255))          # the background alone
        self.assertEqual(pixel(2 * 60, 2 * 60), (20, 20, 200, 255))          # the figure over it
        self.assertEqual(pixel(2 * 43, 2 * 40), (0, 0, 0, 0))                # its clear ground, above the background
        self.assertEqual(pixel(2 * 43, 2 * 70), (200, 20, 20, 255))          # its clear ground shows the background
        # What runs past the card is cut off, and a layer wholly outside draws nothing.
        edge = variants.compose_layers([(red, -50, -50, 100), (red, 500, 0, 10)], scale=1)
        self.assertEqual(tuple(edge.rgba[0:4]), (200, 20, 20, 255))
        self.assertEqual(tuple(edge.rgba[(60 * 140 + 10) * 4:(60 * 140 + 10) * 4 + 4]), (0, 0, 0, 0))
        # A half clear pixel over a clear one stays half clear; over a solid one it blends.
        half = Image(1, 1, bytes((100, 100, 100, 128)))
        blend = variants.compose_layers([(red, 0, 0, 140), (half, 0, 0, 1)], scale=1)
        self.assertTrue(abs(blend.rgba[0] - 150) <= 2 and blend.rgba[3] == 255)
        alone = variants.compose_layers([(half, 0, 0, 1)], scale=1)
        self.assertEqual(alone.rgba[3], 128)
        # Made into the variant's picture: a full art one, its layers kept in the mod for another time.
        cid, _ = variants.add_variant(self.project, 35, None, None, 50, "Layered", key="dm-layers")
        notes = variants.set_layers(self.project, cid, {"background": (red, {"x": 19, "y": 50, "width": 102}),
                                                       "foreground": (figure, {"x": 40, "y": 20, "width": 40})})
        stored = art.state(self.project).images[(cid, "art")].image
        self.assertFalse(stored.opaque())
        self.assertIs(self.project.added[cid].extra["art_transparent"], True)
        self.assertTrue(variants.has_game_frame(self.project, variants.design_name("dm-layers")))
        self.assertEqual(variants.styles(self.project)[variants.design_name("dm-layers")]["art"],
                         {"x": 0, "y": 0, "width": 140, "height": 196})
        again = variants.read_layers(self.project, cid)
        self.assertEqual(sorted(again), ["background", "foreground"])
        self.assertEqual(again["foreground"][1], {"x": 40, "y": 20, "width": 40})
        self.assertEqual(again["background"][0].size, (10, 10))
        # The hand's small card has its own places: in proportion when not given (the card's 140 x 196 on its 52 x 60).
        self.assertEqual(again["foreground"][2], variants.default_hand_layer({"x": 40, "y": 20, "width": 40}))
        self.assertEqual(variants.default_hand_layer({"x": 70, "y": 98, "width": 140}), {"x": 26.0, "y": 30.0, "width": 52.0})
        small = art.state(self.project).images[(cid, "thumbnail")].image
        self.assertEqual(small.width * 32, small.height * 40)                       # the small picture's shape
        self.assertFalse(small.opaque())
        # Given, they are the picture of the hand: a layer put elsewhere there than on the card.
        variants.set_layers(self.project, cid, {"background": (red, {"x": 0, "y": 0, "width": 140}, {"x": 0, "y": 0, "width": 26})})
        kept = variants.read_layers(self.project, cid)["background"]
        self.assertEqual(kept[2], {"x": 0, "y": 0, "width": 26})
        hand = variants.compose_layers([(red, 0, 0, 26)], scale=1, units=variants.HAND_SIZE)
        self.assertEqual((hand.width, hand.height), (52, 60))
        self.assertEqual(hand.rgba[3], 255)
        self.assertEqual(hand.rgba[(0 * 52 + 40) * 4 + 3], 0)                        # past its layer: clear
        small_card = variants.hand_picture(hand, None, 52)
        self.assertEqual((small_card.width, small_card.height), (52, 60))
        # One layer alone, and the other taken away from what is kept; none is refused.
        variants.set_layers(self.project, cid, {"background": (red, {"x": 0, "y": 0, "width": 140})})
        self.assertEqual(sorted(variants.read_layers(self.project, cid)), ["background"])
        with self.assertRaises(ValueError):
            variants.set_layers(self.project, cid, {})
        with self.assertRaises(ValueError):
            variants.set_layers(self.project, cid, {"background": (red, {"x": 0, "y": 0, "width": 0})})
        folder = self.root / "layers"
        manifest.save_mod(self.project, folder)
        self.assertTrue((folder / "art/layers/dm-layers.json").is_file())
        self.assertEqual(errors(self.project), [])

    def test_the_card_picture_is_cut_at_the_card(self):
        red = picture(40, 30, (200, 20, 20, 255))
        blue = picture(30, 30, (20, 20, 200, 255))
        frame = picture(140, 197, (20, 200, 20, 255))
        # The picture past every edge of the card covers it, over a frame behind it.
        card = variants.card_picture(red, frame, 140, {"x": -20, "y": -30, "width": 180, "height": 260})
        self.assertEqual((card.width, card.height), (140, 197))
        for x, y in ((0, 0), (139, 0), (0, 196), (139, 196), (70, 100)):
            self.assertEqual(tuple(card.rgba[(y * 140 + x) * 4:(y * 140 + x) * 4 + 3]), (200, 20, 20))
        # A window inside the card leaves the frame around it.
        card = variants.card_picture(red, frame, 140, {"x": 10, "y": 10, "width": 50, "height": 50})
        self.assertEqual(tuple(card.rgba[(5 * 140 + 5) * 4:(5 * 140 + 5) * 4 + 3]), (20, 200, 20))
        self.assertEqual(tuple(card.rgba[(30 * 140 + 30) * 4:(30 * 140 + 30) * 4 + 3]), (200, 20, 20))
        # A window wholly outside draws nothing, and nothing fails.
        card = variants.card_picture(blue, None, 140, {"x": 500, "y": 0, "width": 30, "height": 30})
        self.assertEqual(tuple(card.rgba[0:3]), (0x20, 0x20, 0x28))

    def test_checks(self):
        project = self.project
        cid, _ = variants.add_variant(project, 1, None, ("preset", "silver"), 50, "Silver", key="v")
        self.assertEqual(errors(project), [])
        extra = project.added[cid].extra
        extra["variant_permille"] = 0
        self.assertTrue(any("thousandths" in i.message for i in errors(project)))
        extra["variant_permille"] = 50
        project.added[cid].base = 17
        self.assertTrue(any("Exodia" in i.message for i in errors(project)))
        project.added[cid].base = 1
        extra["frame_style"] = "nothing"
        problems = [i for i in validate.validate(project) if i.where == project.card_label(cid)]
        self.assertTrue(any(i.level == "warning" and "card layout" in i.message for i in problems))
        extra["frame_style"] = "foil-silver"
        extra["variant_label"] = "z" * 40
        self.assertTrue(any("variant_label" in i.message for i in validate.validate(project)))
        del extra["variant_permille"]
        self.assertTrue(any("needs" in i.message for i in validate.validate(project)))
        # On a replace the keys belong to nothing.
        project.card_extra[5] = {"variant_permille": 50}
        self.assertTrue(any("replace" in i.message for i in validate.validate(project)))

    def test_a_variants_own_design(self):
        project = self.project
        a, _ = variants.add_variant(project, 1, None, ("preset", "gold"), 50, "A", key="a")
        b, _ = variants.add_variant(project, 35, None, ("preset", "gold"), 50, "B", key="b")
        name = variants.own_design(project, a)
        self.assertEqual(name, "v-a")
        self.assertTrue(variants.has_own_design(project, a))
        self.assertFalse(variants.has_own_design(project, b))
        entries = project.other["card_layout"]["frame_styles"]
        self.assertEqual(entries["v-a"], entries["foil-gold"])           # made as a copy of what it had
        self.assertIsNot(entries["v-a"], entries["foil-gold"])
        entries["v-a"]["art"]["width"] = 100                              # its own: the preset is not changed
        self.assertEqual(entries["foil-gold"]["art"]["width"], 134)
        self.assertEqual(project.added[b].extra["frame_style"], "foil-gold")
        self.assertEqual(variants.own_design(project, a), "v-a")          # again: the same, not a second copy
        self.assertEqual(sorted(entries), ["foil-gold", "v-a"])
        # No rule of the layout, and no default for all cards, is made.
        self.assertEqual(sorted(project.other["card_layout"]), ["frame_styles"])
        # Where its picture goes, as the style says.
        self.assertEqual(variants.window_of_style(project, "v-a")["width"], 100)
        self.assertEqual(variants.window_of_style(project, "foil-gold"), frame_presets.WINDOW)
        self.assertEqual(variants.window_of_style(project, "nothing"), frame_presets.WINDOW)
        self.assertEqual(variants.window_of_choice(project, ("style", "v-a"))["width"], 100)
        self.assertEqual(variants.window_of_choice(project, ("preset", "gold")), frame_presets.WINDOW)
        # With no frame of its own it starts as the game's layout.
        c, _ = variants.add_variant(project, 2, None, None, 50, "", key="c")
        variants.own_design(project, c)
        self.assertEqual(entries["v-c"], {"hand_color": "gold"})
        self.assertEqual(variants.frame_of(project, c), ("style", "v-c"))
        # Taking it away leaves no frame, and the style that was its alone.
        variants.remove_own_design(project, a)
        self.assertNotIn("v-a", entries)
        self.assertNotIn("frame_style", project.added[a].extra)
        self.assertFalse(variants.has_own_design(project, a))
        # A long key still names a style the game accepts (31 letters at most).
        long_key = "k" * 70
        d, _ = variants.add_variant(project, 3, None, None, 50, "", key=long_key)
        self.assertLessEqual(len(variants.own_design(project, d)), 31)
        # Saved and read back, the design is what the mod holds.
        folder = self.root / "design"
        manifest.save_mod(project, folder)
        again, _ = manifest.open_mod(self.game, folder)
        self.assertIn("v-c", variants.styles(again))
        self.assertEqual(errors(again), [])

    def test_the_picture_of_a_card(self):
        art_image = picture(204, 192, (200, 30, 30, 255))
        frame = picture(256, 512, (0, 0, 0, 0))
        # a frame that is opaque only in a bar across the top
        rows = bytearray(frame.rgba)
        for y in range(0, 20):
            for x in range(256):
                rows[(y * 256 + x) * 4:(y * 256 + x) * 4 + 4] = bytes((10, 200, 10, 255))
        frame = Image(256, 512, bytes(rows))
        card = variants.card_picture(art_image, frame, 140)
        self.assertEqual(card.size, (140, 197))
        px = lambda x, y: tuple(card.rgba[(y * 140 + x) * 4:(y * 140 + x) * 4 + 4])
        self.assertEqual(px(70, 4), (10, 200, 10, 255))      # the frame's bar
        self.assertEqual(px(70, 80), (200, 30, 30, 255))     # the picture in its window
        self.assertEqual(px(1, 100)[:3], (0x20, 0x20, 0x28))  # outside the window: the canvas
        self.assertEqual(variants.card_picture(None, None, 70).size, (70, 98))
        halves = variants.over(picture(2, 1, (0, 0, 0, 255)), Image(2, 1, bytes((255, 255, 255, 128, 9, 9, 9, 0))))
        self.assertEqual(halves.rgba[0], 128)
        self.assertEqual(tuple(halves.rgba[4:7]), (0, 0, 0))   # a hole leaves what was under it


class VariantsTabTest(GuiCase):
    # The Variants tab, driven as a person would, on the fixture's game files.


    def test_making_changing_and_removing(self):
        tab, project = self.app.variants, self.app.project
        self.assertIn(tab, self.app.tabs)
        self.assertEqual(tab.tree.get_children(), ())
        self.assertTrue(tab.commit())            # nothing chosen: nothing to refuse
        self.app.dirty = False
        cid = tab.make(1, picture(204, 192, (200, 30, 30, 255)), ("preset", "rainbow"), 50, "Rainbow foil")
        self.app.update()
        self.assertTrue(self.app.dirty)
        self.assertEqual(tab.tree.get_children(), (str(cid),))
        self.assertEqual(tab.tree.item(str(cid), "values")[1:], ("Rainbow foil", "5%", "foil-rainbow"))
        # Shown: the form holds it, and the card is drawn in its frame.
        self.assertEqual((tab.label.get(), tab.chance.get(), tab.frames.var.get()), ("Rainbow foil", "5", "Rainbow foil"))
        self.assertIsNotNone(tab.photo)
        self.assertTrue(tab.apply_button.instate(["!disabled"]))
        # No foil at first; the Finish box sets one, and None takes it away.
        self.assertEqual(tab.finish.get(), "None")
        tab.finish.set("Royal")
        self.assertTrue(tab.apply())
        self.assertEqual(project.added[cid].extra["finish"], "royal")
        tab.pick()
        self.assertEqual(tab.finish.get(), "Royal")
        tab.finish.set("None")
        self.assertTrue(tab.apply())
        self.assertNotIn("finish", project.added[cid].extra)
        # A new chance, label and frame.
        tab.chance.set("2.5")
        tab.label.set("Foil")
        tab.frames.var.set("Gold foil")
        tab.frames.selected()
        self.assertTrue(tab.apply())
        extra = project.added[cid].extra
        self.assertEqual((extra["variant_permille"], extra["variant_label"], extra["frame_style"]),
                         (25, "Foil", "foil-gold"))
        self.assertEqual(tab.tree.item(str(cid), "values")[1:], ("Foil", "2.5%", "foil-gold"))
        # A chance out of range is not taken, and the tab says so.
        tab.chance.set("0")
        self.assertFalse(tab.apply())
        self.assertFalse(tab.commit())
        self.assertIn("0.1%", tab.status.cget("text"))
        self.assertEqual(project.added[cid].extra["variant_permille"], 25)
        tab.chance.set("25")
        # No frame of its own again.
        tab.frames.var.set("The game's frame")
        tab.frames.selected()
        self.assertTrue(tab.apply())
        self.assertNotIn("frame_style", project.added[cid].extra)
        # A picture from a file.
        path = Path(self.tmp.name) / "alt.png"
        pngio.write(path, picture(204, 192, (10, 20, 230, 255)))
        self.assertTrue(tab.use_picture(path))
        self.assertTrue(project.added[cid].extra["art"].startswith("art/"))
        # A second variant of the same card, then one taken away.
        second = tab.make(1, None, None, 100, "")
        self.assertEqual(len(tab.tree.get_children()), 2)
        with mock.patch("fm_editor.variants_tab.messagebox.askyesno", return_value=True):
            tab.remove()
        self.assertNotIn(second, project.added)
        self.assertEqual(tab.tree.get_children(), (str(cid),))
        # Refused: the card is not one of the disc's, or a piece of Exodia.
        with self.assertRaises(ValueError):
            tab.make(17, None, None, 50, "")
        with self.assertRaises(ValueError):
            tab.make(cid, None, None, 50, "")
        self.assertEqual(len(project.added), 1)

    def test_designing_a_card(self):
        tab, project = self.app.variants, self.app.project
        cid = tab.make(1, picture(204, 192, (200, 30, 30, 255)), ("preset", "silver"), 50, "Mine")
        name = variants.design_name(project.added[cid].key)
        other = tab.make(35, None, ("preset", "silver"), 50, "Other")
        tab.show(cid)
        # No design of its own yet: the card, and a button to design it. The designer is not made until needed.
        self.assertEqual((tab.plain.winfo_manager(), tab.design_box.winfo_manager()), ("grid", ""))
        self.assertIsNone(tab.designer)
        page = tab.design()
        self.app.update()
        # The designer is in the tab itself: no window of its own.
        self.assertIsNotNone(page)
        self.assertIs(page, tab.designer)
        self.assertEqual((tab.plain.winfo_manager(), tab.design_box.winfo_manager()), ("", "grid"))
        self.assertEqual(tab.designed_for, (cid, name))
        self.assertEqual([w for w in tab.winfo_children() if w.winfo_class() == "Toplevel"], [])
        self.assertEqual(project.added[cid].extra["frame_style"], name)
        entries = project.other["card_layout"]["frame_styles"]
        self.assertIn(name, entries)
        self.assertEqual((page.style_name.get(), page.card.get()), (name, cid))
        before = {k: v for k, v in entries["foil-silver"].items()}
        # A part moved and resized through the fields, as a person types them.
        page.select("art")
        for field, value in (("x", "10"), ("y", "24"), ("width", "120"), ("height", "110")):
            page.vars[field].set(value)
            page.typed(field)
        self.assertEqual(entries[name]["art"], {"x": 10, "y": 24, "width": 120, "height": 110})
        page.select("stars")
        page.hidden.set(True)
        page.set_hidden()
        self.assertIs(entries[name]["stars"]["hide"], True)
        page.select("atk")
        page.vars["x"].set("60")
        page.typed("x")
        self.assertEqual(entries[name]["digits"]["atk"]["x"], 60)
        # A tint: black stars, and the neutral tint is no tint.
        page.select("stars")
        page.set_tint(0x000000)
        self.assertEqual(entries[name]["stars"]["color"], {"r": 0, "g": 0, "b": 0})
        self.assertEqual(ui_frames.tint_value(entries[name]["stars"]["color"]), 0)
        page.set_tint(0x808080)
        self.assertNotIn("color", entries[name]["stars"])
        page.set_tint(0xC08040)
        self.assertEqual(entries[name]["stars"]["color"], {"r": 0xC0, "g": 0x80, "b": 0x40})
        self.assertEqual(ui_frames.tint_value({"r": 300, "g": "x", "b": -4}), 0xFF8000)
        self.assertEqual(ui_frames.tint_value(None), 0x808080)
        # The preview draws a tint as the game does: a channel times value/128.
        one = pngio.Image(1, 1, bytes((200, 100, 50, 255)))
        self.assertIs(ui_frames.tinted(one, 0x808080), one)
        self.assertEqual(tuple(ui_frames.tinted(one, 0x000000).rgba), (0, 0, 0, 255))
        self.assertEqual(tuple(ui_frames.tinted(one, 0x408000).rgba), (100, 100, 0, 255))
        self.assertEqual(tuple(ui_frames.tinted(one, 0xFF8080).rgba), (255, 100, 50, 255))
        self.assertEqual((ui_frames.tint_color(0x808080), ui_frames.tint_color(0x000000)), ("#ffffff", "#000000"))
        self.assertIsNone(ui_frames.tinted(None, 0))
        page.select("art")                       # the picture takes none: no tint to set
        page.set_tint(0x000000)
        self.assertNotIn("color", entries[name]["art"])
        # Only this card's own style changed: no one else's, and nothing for all cards.
        self.assertEqual(entries["foil-silver"], before)
        self.assertEqual(project.added[other].extra["frame_style"], "foil-silver")
        layout = project.other["card_layout"]
        for key in ("default_style", "frame_for", "default_styles"):
            self.assertNotIn(key, layout)
        self.assertEqual(variants.window_of_style(project, name)["width"], 120)
        # Another variant without a design: the card shown plain; back to this one: the same designer.
        tab.show(other)
        self.assertEqual((tab.plain.winfo_manager(), tab.design_box.winfo_manager()), ("grid", ""))
        tab.show(cid)
        self.assertEqual((tab.plain.winfo_manager(), tab.design_box.winfo_manager()), ("", "grid"))
        self.assertIs(tab.designer, page)
        self.assertEqual((page.style_name.get(), page.card.get(), page.locked["card"]), (name, cid, cid))
        self.assertEqual(tab.frames.var.get(), f"This mod's \"{name}\"")
        # A second variant designed: the one designer, now on that card and its own style.
        second = variants.design_name(project.added[other].key)
        tab.show(other)
        self.assertIs(tab.design(), page)
        self.assertEqual((page.style_name.get(), page.card.get()), (second, other))
        self.assertIn(second, entries)
        self.assertEqual(entries[name]["art"], {"x": 10, "y": 24, "width": 120, "height": 110})   # the first kept
        # Choosing another frame for the card takes the designer away; the design stays for later.
        tab.frames.var.set("Gold foil")
        tab.frames.selected()
        self.assertTrue(tab.apply())
        self.assertEqual((tab.plain.winfo_manager(), tab.design_box.winfo_manager()), ("grid", ""))
        self.assertIn(second, entries)
        tab.show(cid)
        # A name plate of its own.
        plate = Path(self.tmp.name) / "plate.png"
        pngio.write(plate, picture(192, 28, (255, 255, 255, 255)))
        self.assertTrue(tab.use_plate(plate))
        self.assertTrue(project.added[cid].extra["title"].startswith("art/"))
        # The design taken away.
        with mock.patch("fm_editor.variants_tab.messagebox.askyesno", return_value=True):
            tab.remove_design()
        self.assertNotIn(name, project.other["card_layout"]["frame_styles"])
        self.assertNotIn("frame_style", project.added[cid].extra)
        self.assertEqual((tab.plain.winfo_manager(), tab.design_box.winfo_manager()), ("grid", ""))

    def test_the_info_tab_keeps_a_setting_another_tab_added(self):
        project = self.app.project
        self.app.info.refresh()                        # the Info tab shows the mod without the setting
        self.assertEqual(project.info.settings, [])
        project.info.settings.append({"key": "extra", "label": "Extra", "type": "bool", "default": 1})
        # Saving applies the Info tab: its stale box must not take the setting away.
        self.assertTrue(self.app.info.commit())
        self.assertEqual([s["key"] for s in project.info.settings], ["extra"])
        folder = Path(self.tmp.name) / "saved"
        manifest.save_mod(project, folder)
        written = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
        self.assertEqual([s["key"] for s in written["settings"]], ["extra"])
        # Typed in the box, it still applies.
        self.app.info.refresh()
        self.app.info.settings.delete("1.0", "end")
        self.assertTrue(self.app.info.commit())
        self.assertEqual(project.info.settings, [])

    def test_coloring_the_numbers_and_words(self):
        tab, project = self.app.variants, self.app.project
        cid = tab.make(1, picture(204, 192, (200, 30, 30, 255)), None, 50, "Mine")
        name = variants.design_name(project.added[cid].key)
        tab.show(cid)
        page = tab.design()
        entries = project.other["card_layout"]["frame_styles"]
        # The game draws its own numbers by subtraction: they take no color. Coloring one puts in the editor's
        # white digit strip, which a color multiplies; coloring the other uses the same strip.
        self.assertNotIn("image", entries[name].get("digits", {}))
        page.select("atk")
        page.set_tint(0x000000)
        image = entries[name]["digits"]["image"]
        self.assertEqual(image, f"frames/{name}-digits.png")
        self.assertEqual(pngio.decode(project.files[image]).size, (256, 256))
        self.assertEqual(entries[name]["digits"]["atk"]["color"], {"r": 0, "g": 0, "b": 0})
        page.select("def")
        page.set_tint(0x204060)
        self.assertEqual(entries[name]["digits"]["image"], image)
        self.assertEqual(entries[name]["digits"]["def"]["color"], {"r": 0x20, "g": 0x40, "b": 0x60})
        # A word: its own white picture, put where the preview shows it.
        page.select("atk_label")
        self.assertNotIn("atk_label", entries[name])
        page.set_tint(0x000000)
        label = entries[name]["atk_label"]
        self.assertEqual(label["image"], f"frames/{name}-atk_label.png")
        self.assertEqual(pngio.decode(project.files[label["image"]]).size, (128, 64))
        self.assertEqual([label[k] for k in ("x", "y", "width", "height")], [12, 171, 16, 8])
        self.assertEqual(label["color"], {"r": 0, "g": 0, "b": 0})
        self.assertNotIn("dfd_label", entries[name])           # the other word is left as it was
        page.select("dfd_label")
        page.set_tint(0x808080)                                # no tint is no picture put in
        self.assertNotIn("dfd_label", entries[name])
        self.assertEqual(ui_frames.tint_color(0x000000), "#000000")
        # The preview draws a colored picture colored.
        self.assertEqual(len(ui_frames.TEXT_ASSETS), 4)
        # The game reads what was written: no error from the checks.
        self.assertEqual(errors(project), [])

    def test_the_shape_of_the_stars(self):
        tab, project = self.app.variants, self.app.project
        cid = tab.make(1, picture(204, 192, (200, 30, 30, 255)), None, 50, "Mine")
        name = variants.design_name(project.added[cid].key)
        tab.show(cid)
        page = tab.design()
        entries = project.other["card_layout"]["frame_styles"]
        page.select("stars")
        self.assertEqual(page.shape.get(), "The game's")
        self.assertEqual(page.shapes.winfo_manager(), "grid")
        self.assertNotIn("image", entries[name].get("stars", {}))
        # A shape of the editor's: its white picture in frames/, which the tint colors.
        page.shape.set("Heart")
        page.shape_chosen()
        stars = entries[name]["stars"]
        self.assertEqual(stars["image"], f"frames/{name}-stars.png")
        self.assertEqual(project.files[stars["image"]], text_presets.star("heart"))
        self.assertEqual(page.shape.get(), "Heart")
        page.set_tint(0x4060FF)
        self.assertEqual(entries[name]["stars"]["color"], {"r": 0x40, "g": 0x60, "b": 0xFF})
        self.assertEqual(entries[name]["stars"]["image"], stars["image"])        # the tint keeps the shape
        page.shape.set("Star")
        page.shape_chosen()
        self.assertEqual(project.files[entries[name]["stars"]["image"]], text_presets.star("star"))
        # A picture of one's own is told apart from the shapes.
        project.files["frames/own.png"] = picture(16, 16, (255, 255, 255, 255))
        entries[name]["stars"]["image"] = "frames/own.png"
        page.fill_form()
        self.assertEqual(page.shape.get(), "My own picture")
        # Back to the game's own star: no picture, the tint stays.
        page.shape.set("The game's")
        page.shape_chosen()
        self.assertNotIn("image", entries[name]["stars"])
        self.assertIn("color", entries[name]["stars"])
        self.assertEqual(len(text_presets.SHAPES), 4)
        for shape, _ in text_presets.SHAPES:
            self.assertEqual(pngio.decode(text_presets.star(shape)).size, (64, 64))
        # Other parts have no shape to choose.
        page.select("art")
        self.assertEqual(page.shapes.winfo_manager(), "")
        self.assertEqual(errors(project), [])

    def test_full_art_in_the_tab(self):
        tab, project = self.app.variants, self.app.project
        cid = tab.make(35, None, None, 50, "Mine")
        tab.show(cid)
        self.assertEqual(project.info.settings, [])
        path = Path(self.tmp.name) / "tall.png"
        pngio.write(path, picture(200, 300, (30, 120, 200, 255)))
        self.assertFalse(tab.whole.get())
        self.assertTrue(tab.use_picture(path, whole=True))
        name = variants.design_name(project.added[cid].key)
        # The tab shows the designer, on a card whose picture covers it.
        self.assertEqual((tab.plain.winfo_manager(), tab.design_box.winfo_manager()), ("", "grid"))
        self.assertEqual(variants.styles(project)[name]["art"], variants.full_art_window(200 / 300))
        page = tab.designer
        # The picture's window may be made bigger than the card in the designer: the game cuts it at the edge.
        page.select("art")
        for field, value in (("x", "-20"), ("y", "-40"), ("width", "400"), ("height", "580")):
            page.vars[field].set(value)
            page.typed(field)
        self.assertEqual(variants.styles(project)[name]["art"], {"x": -20, "y": -40, "width": 400, "height": 580})
        page.vars["width"].set("900")
        page.typed("width")
        self.assertEqual(variants.styles(project)["" + name]["art"]["width"], 420)         # bounded
        # The tab's box, and the New variant way.
        other = tab.make(1, picture(200, 300, (200, 30, 30, 255)), None, 50, "Full", full_art=True)
        self.assertTrue(variants.has_own_design(project, other))
        self.assertEqual(errors(project), [])

    def test_back_to_the_games_on_the_games_frame(self):
        tab, project = self.app.variants, self.app.project
        cid = tab.make(35, picture(200, 300, (30, 120, 200, 255)), None, 50, "Full", full_art=True)
        name = variants.design_name(project.added[cid].key)
        tab.show(cid)
        page = tab.designer or tab.design()
        entry = variants.styles(project)[name]
        self.assertTrue(variants.has_game_frame(project, name))
        # The editor's defaults for the parts the style leaves out are the game's own, on its frame.
        for key, want in ui_frames.GAME_FRAME_DEFAULTS.items():
            self.assertEqual(page.defaults(key), want)
        self.assertEqual(page.rect("atk")[:2], (109, 163))
        self.assertEqual(page.rect("dfd_label"), (72, 171, 24, 12))
        # Moved, then back: the part is left out again, which the game draws as its own.
        page.select("title")
        page.vars["x"].set("40"); page.typed("x")
        self.assertEqual(entry["title"]["x"], 40)
        page.vars["x"].set("12"); page.typed("x")                        # the game's place: nothing to write for it
        self.assertNotIn("x", entry.get("title", {}))
        page.set_tint(0x000000)
        self.assertIn("title", entry)
        page.reset()
        self.assertNotIn("title", entry)
        # Coloring a number puts in the editor's strip, at the game's size, and at the game's place.
        page.select("atk")
        page.set_tint(0x000000)
        digits = entry["digits"]
        self.assertEqual((digits["width"], digits["height"], digits["step"]), (6, 13, 6))
        self.assertNotIn("x", digits["atk"])
        page.select("atk_label")
        page.set_tint(0x000000)
        self.assertEqual([entry["atk_label"][k] for k in ("x", "y", "width", "height")], [72, 157, 24, 12])
        self.assertEqual(errors(project), [])
        # A design that does not keep the game's frame has the editor's own defaults, and nothing changes there.
        plain = tab.make(1, None, None, 50, "Plain")
        tab.show(plain)
        plain_page = tab.design()
        self.assertFalse(variants.has_game_frame(project, variants.design_name(project.added[plain].key)))
        self.assertEqual(plain_page.defaults("atk"), ui_frames.SPECS["atk"][3])

    def test_layers_in_the_tab_and_the_hand_frame(self):
        tab, project = self.app.variants, self.app.project
        cid = tab.make(35, None, None, 50, "Layered")
        tab.show(cid)
        self.assertEqual(str(tab.layers_button.cget("state")), "normal")
        # The layers dialog's work: what the tab does after the picture is made.
        red = picture(10, 10, (200, 20, 20, 255))
        notes = variants.set_layers(project, cid, {"background": (red, {"x": 19, "y": 50, "width": 102})})
        tab.after_picture(notes, "the layers")
        name = variants.design_name(project.added[cid].key)
        self.assertEqual((tab.plain.winfo_manager(), tab.design_box.winfo_manager()), ("", "grid"))
        self.assertIn("layers", tab.status.cget("text"))
        # The hand's card in the designer: the game's own, in the card's colour, when the design has none of its own.
        page = tab.designer
        self.assertEqual(ui_frames.hand_frame(b"", 0), None)
        self.assertIsNone(ui_frames.hand_frame(None, 0))
        self.assertIsNone(ui_frames.hand_frame(b"x" * 10, 9))
        page.pick("hand")
        page.draw()                       # nothing on the disc of the fixture: the plain picture, and no failure
        for key in ("field", "field_back", "library", "hand"):
            page.pick(key)
            page.draw()
        page.face.set(False)
        page.draw()                       # the back: the game's, or the plain picture without the disc
        self.assertIsNone(ui_frames.field_frame(None, 0))
        self.assertIsNone(ui_frames.field_frame(b"x" * 10, 9, False, True))

    def test_the_layers_dialog_and_the_hands_own_picture(self):
        from fm_editor import variants_tab
        tab, project = self.app.variants, self.app.project
        cid = tab.make(35, None, None, 50, "Layered")
        tab.show(cid)
        folder = Path(self.tmp.name)
        pngio.write(folder / "back.png", picture(20, 20, (20, 60, 160, 255)))
        figure = bytearray()
        for y in range(40):
            for x in range(20):
                figure += bytes((220, 40, 40, 255)) if 6 <= x < 14 and 4 <= y < 36 else bytes((0, 0, 0, 0))
        pngio.write(folder / "figure.png", Image(20, 40, bytes(figure)))
        made = {}

        def fake_dialog(master, title, build, ok):
            window = tk.Toplevel(master)
            body = ttk.Frame(window)
            body.pack()
            build(window, body)
            made.update(window=window, ok=ok)

        def buttons(widget):
            for child in widget.winfo_children():
                yield child
                yield from buttons(child)

        paths = iter((str(folder / "back.png"), str(folder / "figure.png")))
        with mock.patch.object(variants_tab, "FormDialog", fake_dialog), \
                mock.patch("fm_editor.variants_tab.file_dialogs.askopenfilename", side_effect=lambda **o: next(paths)):
            tab.layers()
            window = made["window"]
            chooses = [b for b in buttons(window) if isinstance(b, ttk.Button) and b.cget("text") == "Choose..."]
            self.assertEqual(len(chooses), 2)
            for button in chooses:
                button.invoke()
            self.app.update()
            # Both sets of places were filled: the card's, and the hand's in proportion.
            sets = window.sets
            card_boxes = [b for b in buttons(sets["card"]) if isinstance(b, ttk.Spinbox)]
            hand_boxes = [b for b in buttons(sets["hand"]) if isinstance(b, ttk.Spinbox)]
            self.assertEqual(len(card_boxes), 6)
            self.assertEqual(card_boxes[0].get(), "19")                      # the background's x: the game's window
            self.assertEqual(card_boxes[2].get(), "102")
            self.assertEqual(hand_boxes[2].get(), "37.9")                    # 102 on the hand's 52 / 140
            self.assertEqual(sets["card"].winfo_manager(), "grid")
            self.assertEqual(sets["hand"].winfo_manager(), "")
            # The foreground put somewhere else on the hand's card than on the card.
            radios = [b for b in buttons(window) if isinstance(b, ttk.Radiobutton)]
            radios[1].invoke()
            self.assertEqual((sets["card"].winfo_manager(), sets["hand"].winfo_manager()), ("", "grid"))
            hand_boxes[3].delete(0, "end"); hand_boxes[3].insert(0, "-5")      # the foreground's x
            self.assertIsNone(made["ok"](window))
            window.destroy()
        layers = variants.read_layers(project, cid)
        self.assertEqual(sorted(layers), ["background", "foreground"])
        self.assertEqual(layers["foreground"][2]["x"], -5.0)
        self.assertEqual(layers["background"][2]["width"], 37.9)
        self.assertEqual(layers["background"][1]["width"], 102)
        self.assertIn((cid, "thumbnail"), art.state(project).images)
        self.assertIs(project.added[cid].extra["art_transparent"], True)
        # The hand's Artwork has a picture of its own (the card's small one) to choose in the designer.
        page = tab.designer
        small = folder / "small.png"
        pngio.write(small, picture(40, 32, (1, 200, 1, 255)))
        before = art.state(project).images[(cid, "thumbnail")].image
        page.pick("hand_art")
        self.assertEqual(str(page.choose.cget("state")), "normal")                 # the hand's Artwork can take a picture
        with mock.patch("fm_editor.file_dialogs.askopenfilename", return_value=str(small)):
            page.choose_image()
        after = art.state(project).images[(cid, "thumbnail")].image
        self.assertNotEqual(after.rgba[:4], before.rgba[:4])
        self.assertEqual(after.rgba[:3], bytes((1, 200, 1)))
        self.assertEqual(project.added[cid].extra["art_transparent"], True)         # kept: the card's own picture needs it
        art_before = art.state(project).images[(cid, "art")].image
        page.remove_image()
        self.assertNotIn((cid, "thumbnail"), art.state(project).images)             # made from the card's picture again
        self.assertEqual(art.state(project).images[(cid, "art")].image.rgba[:8], art_before.rgba[:8])
        self.assertEqual(errors(project), [])

    def test_a_variants_design_is_not_listed_in_the_ui_tab(self):
        tab, project = self.app.variants, self.app.project
        cid = tab.make(1, picture(204, 192, (200, 30, 30, 255)), ("preset", "gold"), 50, "Mine")
        name = variants.design_name(project.added[cid].key)
        tab.show(cid)
        self.assertIsNotNone(tab.design())
        self.assertIn(name, variants.styles(project))
        page = self.app.ui.pages["frames"]
        page.fill()
        listed = list(page.style_list.get(0, "end"))
        self.assertNotIn(name, listed)                    # designed in the Variants tab only
        self.assertIn("foil-gold", listed)                # a preset's style is the modder's to edit there
        # The mod's own styles of other names are listed as ever.
        variants.styles(project)["mine"] = {"hand_color": "gold"}
        page.fill()
        self.assertIn("mine", page.style_list.get(0, "end"))

    def test_a_design_without_a_frame_picture(self):
        tab, project = self.app.variants, self.app.project
        project.source_dir = Path(self.tmp.name)          # a mod that is on disk, as one opened or saved is
        cid = tab.make(1, picture(204, 192, (200, 30, 30, 255)), None, 50, "Plain")
        other = tab.make(35, None, None, 50, "Other")
        name = variants.design_name(project.added[cid].key)
        tab.show(cid)
        self.assertIsNotNone(tab.design())
        self.assertNotIn("image", project.other["card_layout"]["frame_styles"][name])
        # Away and back, and the preview of a style that is only parts: no frame picture, and no error.
        tab.show(other)
        tab.show(cid)
        self.app.update()
        self.assertIsNone(tab.frames.frame_image())
        self.assertIsNone(variants._held(project, None))

    def test_a_mod_read_back_shows_its_variants(self):
        tab, project = self.app.variants, self.app.project
        cid = tab.make(35, picture(204, 192, (50, 200, 50, 255)), ("preset", "silver"), 100, "Silver")
        folder = Path(self.tmp.name) / "variants-mod"
        manifest.save_mod(project, folder)
        opened, _ = manifest.open_mod(project.retail, folder)
        self.app.project = opened
        tab.current = None
        tab.refresh()
        self.assertEqual(len(tab.tree.get_children()), 1)
        shown = tab.tree.item(tab.tree.get_children()[0], "values")
        self.assertEqual(shown[1:], ("Silver", "10%", "foil-silver"))
        self.assertEqual(tab.frames.var.get(), "Silver foil")
        self.assertIsNotNone(tab.photo)


if __name__ == "__main__":
    unittest.main()
