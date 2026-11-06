"""The Variants tab: a card's alternate versions (variants.py, notes/more-cards.md
"Variants"): another picture and, if the modder likes, a frame of its own, won in
the card's place by a chance. Pick the card, the picture, the frame and the
chance, and the tab writes everything the game reads (the card's entry, the
picture, the frame style and its picture, the "Special frames" switch).

The list is the mod's variants by their card; beside it, the card as the
game lays it out (the picture in its frame's window, the frame over it) and what
can be changed of the chosen one."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from . import art, file_dialogs, frame_presets, pngio, variants
from .tabs import Tab
from .widgets import CardField, FormDialog, WrapLabel, px, scrolled_tree

PREVIEW_W = 210          # the preview card's width at 96 dpi: 1.5x the 140 units of a card
OWN_PNG = "A PNG of my own..."
NO_CHOICE = "(not one of these)"


def photo(master, image: pngio.Image):
    return tk.PhotoImage(master=master, data=pngio.ppm(image), format="PPM")


class FrameChooser:
    """A combobox of the frames the tab offers, and a PNG of the modder's own. `choice` is what
    variants.set_frame takes: None, ("preset", name), ("style", name) or ("png", bytes, stem)."""

    def __init__(self, master, project_getter, on_change):
        self.project_getter = project_getter
        self.on_change = on_change
        self.options = []
        self.own = None                    # ("png", bytes, stem) once a file is chosen
        self.var = tk.StringVar()
        self.box = ttk.Combobox(master, textvariable=self.var, state="readonly", width=30)
        self.box.bind("<<ComboboxSelected>>", lambda e: self.selected())
        self.reload()

    def reload(self, current=None):
        """The choices, with `current` (a choice) shown."""
        project = self.project_getter()
        self.options = variants.frame_choices(project) if project is not None else [("The game's frame", None)]
        names = [text for text, _ in self.options]
        if self.own is not None:
            names.append(f"{self.own[2]} (my PNG)")
        names.append(OWN_PNG)
        self.box.configure(values=names)
        self.show(current)

    def show(self, choice):
        for text, option in self.options:
            if option == choice:
                self.var.set(text)
                return
        if choice is not None and choice[0] == "png" and self.own is not None:
            self.var.set(f"{self.own[2]} (my PNG)")
        else:
            self.var.set(self.options[0][0])

    def selected(self):
        text = self.var.get()
        if text == OWN_PNG:
            path = file_dialogs.askopenfilename(parent=self.box, title="A frame (a PNG)",
                                                filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
            if path:
                try:
                    data = Path(path).read_bytes()
                    pngio.decode(data)
                except (OSError, pngio.PngError, ValueError) as problem:
                    messagebox.showerror("FM Editor", f"Could not use {path}: {problem}", parent=self.box)
                    path = None
                else:
                    self.own = ("png", data, Path(path).stem)
            self.reload(self.own)
            if path is None:
                self.reload(self.choice())
        self.on_change()

    def choice(self):
        text = self.var.get()
        if self.own is not None and text == f"{self.own[2]} (my PNG)":
            return self.own
        for name, option in self.options:
            if name == text:
                return option
        return None

    def frame_image(self):
        """The picture of the chosen frame, for a preview: a pngio.Image or None."""
        choice = self.choice()
        if choice is None:
            return None
        try:
            if choice[0] == "preset":
                return pngio.decode(frame_presets.png(choice[1]))
            if choice[0] == "png":
                return pngio.decode(choice[1])
            entry = variants.styles(self.project_getter()).get(choice[1])
            data = variants._held(self.project_getter(), entry.get("image")) if isinstance(entry, dict) else None
            return pngio.decode(data) if data else None
        except (pngio.PngError, ValueError):
            return None


class VariantsTab(Tab):
    def __init__(self, notebook, app):
        super().__init__(notebook, app, "Variants")
        self.current = None
        self.photo = None
        WrapLabel(self, style="Hint.TLabel", text=(
            "A variant is another version of a card, as in the trading card game: its own picture and, if you like, "
            "a frame of its own. When a duel would give the card, a variant is given instead by the chance you set "
            "(5% is one drop in twenty). A deck holds three of a card and its variants together, and the Library "
            "shows them as one entry. Needs game version 25 of the mod API (the editor writes min_api itself).")
        ).pack(fill="x")
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=(6, 0))
        left = ttk.LabelFrame(body, text="Variants", padding=6)
        left.pack(side="left", fill="y")
        frame, self.tree = scrolled_tree(left, [("card", "Card"), ("name", "Variant"), ("chance", "Chance"),
                                                ("frame", "Frame")], [170, 130, 60, 110], 14)
        frame.pack(fill="y", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.pick())
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(buttons, text="New variant...", command=self.new).pack(side="left")
        self.remove_button = ttk.Button(buttons, text="Remove", command=self.remove)
        self.remove_button.pack(side="left", padx=4)

        right = ttk.LabelFrame(body, text="The chosen variant", padding=8)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.preview = ttk.Label(right)
        self.preview.grid(row=0, column=0, rowspan=6, sticky="n", padx=(0, 12))
        self.title = ttk.Label(right, text="Choose a variant, or make one.")
        self.title.grid(row=0, column=1, columnspan=2, sticky="w")
        self.label = tk.StringVar()
        self.chance = tk.StringVar()
        ttk.Label(right, text="Label").grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Entry(right, textvariable=self.label, width=26).grid(row=1, column=2, sticky="w", padx=4, pady=(6, 0))
        ttk.Label(right, text="Chance (%)").grid(row=2, column=1, sticky="w", pady=(4, 0))
        ttk.Entry(right, textvariable=self.chance, width=8).grid(row=2, column=2, sticky="w", padx=4, pady=(4, 0))
        ttk.Label(right, text="Frame").grid(row=3, column=1, sticky="w", pady=(4, 0))
        self.frames = FrameChooser(right, lambda: self.project, self.preview_changed)
        self.frames.box.grid(row=3, column=2, sticky="w", padx=4, pady=(4, 0))
        self.picture_button = ttk.Button(right, text="Choose a picture...", command=self.choose_picture)
        self.picture_button.grid(row=4, column=1, columnspan=2, sticky="w", pady=(6, 0))
        self.apply_button = ttk.Button(right, text="Apply", command=self.apply)
        self.apply_button.grid(row=5, column=1, sticky="w", pady=(8, 0))
        self.status = ttk.Label(right, style="Hint.TLabel", wraplength=px(self, 360), justify="left")
        self.status.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.show(None)

    # --- the list -------------------------------------------------------------------------

    @property
    def wa(self):
        files = self.app.files
        return files.wa if files is not None else None

    def refresh(self):
        if self.project is None:
            return
        self.frames.reload(variants.frame_of(self.project, self.current) if self.current in self.project.added else None)
        self.fill()
        if self.current is not None and not self.tree.exists(str(self.current)):
            self.current = None
        if self.current is None:
            first = self.tree.get_children()
            self.current = int(first[0]) if first else None
        if self.current is not None:
            self.tree.selection_set(str(self.current))
        self.show(self.current)

    def fill(self):
        self.tree.delete(*self.tree.get_children())
        project = self.project
        for v in variants.variants(project):
            self.tree.insert("", "end", iid=str(v.cid),
                             values=(project.card_label(v.base), v.label or v.key, variants.percent_text(v.permille),
                                     v.frame_style or "the game's"))

    def pick(self):
        selected = self.tree.selection()
        self.show(int(selected[0]) if selected else None)

    # --- the chosen variant -----------------------------------------------------------------

    def show(self, cid):
        project = self.project
        self.current = cid if cid is not None and project is not None and variants.is_variant(project, cid) else None
        on = self.current is not None
        for widget in (self.remove_button, self.picture_button, self.apply_button):
            widget.state(["!disabled"] if on else ["disabled"])
        self.status.configure(text="")
        if not on:
            self.title.configure(text="Choose a variant, or make one.")
            self.label.set("")
            self.chance.set("")
            self.frames.reload(None)
            self.preview.configure(image="")
            self.photo = None
            return
        v = variants.read(project, self.current)
        self.title.configure(text=f"{project.card_label(v.base)}   ({v.key})")
        self.label.set(v.label)
        self.chance.set(variants.percent_text(v.permille).rstrip("%"))
        self.frames.reload(variants.frame_of(project, self.current))
        self.draw()

    def picture_of(self, cid):
        """The picture the card shows now: the mod's own, else its base's from the disc."""
        if self.wa is None or cid is None:
            return None
        try:
            return art.shown_image(self.project, self.wa, cid, "art")[0]
        except (OSError, pngio.PngError, ValueError):
            return None

    def draw(self):
        if self.current is None or self.project is None:
            return
        card = variants.card_picture(self.picture_of(self.current), self.frames.frame_image(), px(self, PREVIEW_W))
        self.photo = photo(self, card)
        self.preview.configure(image=self.photo)

    def preview_changed(self):
        self.draw()

    def apply(self) -> bool:
        """The form's label, chance and frame to the chosen variant (the Apply button, and a tab change)."""
        cid, project = self.current, self.project
        if cid is None or project is None:
            return True
        before = variants.read(project, cid)
        chance = variants.parse_percent(self.chance.get())
        if chance is None:
            self.status.configure(text="The chance is 0.1% to 100%.")
            return False
        label = self.label.get().strip()
        frame = self.frames.choice()
        try:
            if label != before.label:
                variants.set_label(project, cid, label)
            if chance != before.permille:
                variants.set_chance(project, cid, chance)
            if frame != variants.frame_of(project, cid):
                variants.set_frame(project, cid, frame)
        except ValueError as problem:
            self.status.configure(text=str(problem))
            return False
        if variants.read(project, cid) != before or frame != variants.frame_of(project, cid):
            self.app.changed()
        self.fill()
        self.tree.selection_set(str(cid))
        self.frames.reload(variants.frame_of(project, cid))
        self.status.configure(text="")
        self.draw()
        self.applied()
        return True

    def commit(self):
        return self.apply() if self.current is not None else True

    def choose_picture(self):
        cid = self.current
        if cid is None:
            return
        path = file_dialogs.askopenfilename(parent=self, title=f"A picture for {self.project.card_label(cid)}",
                                            filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
        if path:
            self.use_picture(path)

    def use_picture(self, path) -> bool:
        """`path` as the chosen variant's picture (the button, and tests)."""
        try:
            notes = variants.set_art(self.project, self.current, pngio.read(path))
        except (OSError, pngio.PngError, ValueError) as problem:
            messagebox.showerror("FM Editor", f"Could not use {path}: {problem}", parent=self)
            return False
        self.app.changed()
        self.draw()
        self.status.configure(text=f"{Path(path).name} is the picture" + (": " + "; ".join(notes) if notes else "."))
        return True

    # --- making and removing -------------------------------------------------------------

    def make(self, base, image, frame, permille, label) -> int:
        """A variant, in the project and the list (the dialog's OK, and tests); its card id."""
        cid, notes = variants.add_variant(self.project, base, image, frame, permille, label)
        self.app.changed()
        self.fill()
        self.current = cid
        self.tree.selection_set(str(cid))
        self.tree.see(str(cid))
        self.frames.reload(variants.frame_of(self.project, cid))
        self.show(cid)
        if notes:
            self.status.configure(text="The picture: " + "; ".join(notes) + ".")
        return cid

    def new(self):
        if self.project is None or not self.apply():
            return
        state = {"image": None, "name": ""}

        def build(dialog, body):
            def only(card):
                return card <= 722 and card not in variants.EXODIA

            ttk.Label(body, text="Card").grid(row=0, column=0, sticky="w")
            dialog.card = CardField(body, lambda: self.project, width=30, only=only)
            dialog.card.grid(row=0, column=1, sticky="we", padx=4)
            if self.current and variants.is_variant(self.project, self.current):
                dialog.card.set(variants.read(self.project, self.current).base)
            ttk.Label(body, text="Picture").grid(row=1, column=0, sticky="w", pady=(4, 0))
            line = ttk.Frame(body)
            line.grid(row=1, column=1, sticky="w", padx=4, pady=(4, 0))
            dialog.picture = ttk.Label(line, text="the card's own")
            ttk.Button(line, text="Choose a PNG...", command=lambda: choose(dialog)).pack(side="left")
            dialog.picture.pack(side="left", padx=6)
            ttk.Label(body, text="Frame").grid(row=2, column=0, sticky="w", pady=(4, 0))
            dialog.frames = FrameChooser(body, lambda: self.project, lambda: draw(dialog))
            dialog.frames.box.grid(row=2, column=1, sticky="w", padx=4, pady=(4, 0))
            ttk.Label(body, text="Chance (%)").grid(row=3, column=0, sticky="w", pady=(4, 0))
            dialog.chance = tk.StringVar(value="5")
            ttk.Entry(body, textvariable=dialog.chance, width=8).grid(row=3, column=1, sticky="w", padx=4, pady=(4, 0))
            ttk.Label(body, text="Label").grid(row=4, column=0, sticky="w", pady=(4, 0))
            dialog.label = tk.StringVar()
            ttk.Entry(body, textvariable=dialog.label, width=26).grid(row=4, column=1, sticky="w", padx=4, pady=(4, 0))
            dialog.preview = ttk.Label(body)
            dialog.preview.grid(row=0, column=2, rowspan=6, padx=(14, 0))
            dialog.photo = None
            dialog.card.var.trace_add("write", lambda *_: draw(dialog))
            draw(dialog)

        def choose(dialog):
            path = file_dialogs.askopenfilename(parent=dialog, title="A picture for the variant",
                                                filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
            if not path:
                return
            try:
                state["image"] = pngio.read(path)
            except (OSError, pngio.PngError, ValueError) as problem:
                messagebox.showerror("FM Editor", f"Could not use {path}: {problem}", parent=dialog)
                return
            dialog.picture.configure(text=Path(path).name)
            draw(dialog)

        def draw(dialog):
            base = dialog.card.get()
            image = state["image"]
            if image is None and base and self.wa is not None:
                try:
                    image = art.disc_image(self.wa, base, "art")
                except (OSError, ValueError, KeyError):
                    image = None
            card = variants.card_picture(image, dialog.frames.frame_image(), px(self, PREVIEW_W))
            dialog.photo = photo(dialog, card)
            dialog.preview.configure(image=dialog.photo)

        def ok(dialog):
            base = dialog.card.get()
            if not base:
                return "Choose the card this is a version of."
            chance = variants.parse_percent(dialog.chance.get())
            if chance is None:
                return "The chance is 0.1% to 100%."
            try:
                self.make(base, state["image"], dialog.frames.choice(), chance, dialog.label.get().strip())
            except ValueError as problem:
                return str(problem)
            return None

        FormDialog(self, "New variant", build, ok)

    def remove(self):
        cid = self.current
        if cid is None:
            return
        if not messagebox.askyesno("Remove variant", f"Remove {self.project.card_label(cid)} and every rule that "
                                   "names it? The frame it used stays in the mod.", parent=self):
            return
        variants.remove_variant(self.project, cid)
        self.app.changed()
        self.current = None
        self.fill()
        self.show(None)
