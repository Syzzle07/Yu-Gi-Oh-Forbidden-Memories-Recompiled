"""The variants engine (variants.py): variants made in a project, what is written for the game, what is read
back, and the checks. On synthetic data:

    python -m unittest discover -s tools/pc/fm_editor/tests -t tools/pc
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fm_editor import compat, frame_presets, manifest, pngio, validate, variants
from fm_editor.model import Project
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
        # Its switch is in the mod's settings, on from the start.
        switch = [s for s in self.project.info.settings if s["key"] == "full_bleed"]
        self.assertEqual(len(switch), 1)
        self.assertEqual((switch[0]["type"], switch[0]["default"]), ("bool", 1))
        # A second variant with the same preset shares the style, the picture and the switch.
        other, _ = variants.add_variant(self.project, 35, None, ("preset", "rainbow"), 100, "")
        self.assertEqual(self.project.added[other].extra["frame_style"], "foil-rainbow")
        self.assertEqual(list(self.project.other["card_layout"]["frame_styles"]), ["foil-rainbow"])
        self.assertEqual([k for k in self.project.files if k.startswith("frames/")], ["frames/foil-rainbow.png"])
        self.assertEqual(len([s for s in self.project.info.settings if s["key"] == "full_bleed"]), 1)
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
        self.assertEqual([s["key"] for s in written["settings"]], ["full_bleed"])
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
