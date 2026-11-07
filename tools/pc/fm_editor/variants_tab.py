"""The Variants tab: a card's alternate versions (variants.py, notes/more-cards.md
"Variants"): another picture and, if the modder likes, a frame of its own, won in
the card's place by a chance. Pick the card, the picture, the frame and the
chance, and the tab writes everything the game reads (the card's entry, the
picture, the frame style and its picture).

The list is the mod's variants by their card; beside it, the card as the
game lays it out (the picture in its frame's window, the frame over it) and what
can be changed of the chosen one."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from . import art, card_icons, file_dialogs, frame_presets, pngio, ui_frames, variants
from .tabs import Tab
from .variants_design import DesignHost
from .widgets import CardField, FormDialog, WrapLabel, px, scrolled_tree

PREVIEW_W = 210          # the preview card's width at 96 dpi: 1.5x the 140 units of a card
PLAIN_W = 280            # the card in the tab while it has no design of its own: 2x
FINISH_NAMES = ("None", "Glossy", "Royal")   # the Finish box, in the order of variants.FINISHES after "none"


def finish_name(finish: str) -> str:
    return finish.capitalize() if finish in variants.FINISHES else FINISH_NAMES[0]


def finish_key(name: str) -> str:
    return name.lower() if name.lower() in variants.FINISHES else ""
OWN_PNG = "A PNG of my own..."
NO_CHOICE = "(not one of these)"


def photo(master, image: pngio.Image):
    return tk.PhotoImage(master=master, data=pngio.ppm(image), format="PPM")


class FrameChooser:
    """A combobox of the frames the tab offers, and a PNG of the modder's own. `choice` is what
    variants.set_frame takes: None, ("preset", name), ("style", name) or ("png", bytes, stem)."""

    def __init__(self, master, project_getter, on_change, width=30):
        self.project_getter = project_getter
        self.on_change = on_change
        self.options = []
        self.own = None                    # ("png", bytes, stem) once a file is chosen
        self.var = tk.StringVar()
        self.box = ttk.Combobox(master, textvariable=self.var, state="readonly", width=width)
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
            "shows them as one entry. Needs mod API 25 (the editor writes min_api itself).")
        ).pack(fill="x")
        self.designer = None            # the Frames designer, made when a card first has a design of its own
        self.designed_for = None        # (card id, style name) the designer shows now
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=(6, 0))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="ns")
        listing = ttk.LabelFrame(left, text="Variants", padding=6)
        listing.pack(fill="x")
        frame, self.tree = scrolled_tree(listing, [("card", "Card"), ("name", "Variant"), ("chance", "Chance"),
                                                   ("frame", "Frame")], [125, 85, 50, 95], 9)
        frame.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.pick())
        buttons = ttk.Frame(listing)
        buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(buttons, text="New variant...", command=self.new).pack(side="left")
        self.remove_button = ttk.Button(buttons, text="Remove", command=self.remove)
        self.remove_button.pack(side="left", padx=4)

        form = ttk.LabelFrame(left, text="The chosen variant", padding=8)
        form.pack(fill="x", pady=(8, 0))
        self.title = ttk.Label(form, text="Choose a variant, or make one.")
        self.title.grid(row=0, column=0, columnspan=2, sticky="w")
        self.label = tk.StringVar()
        self.chance = tk.StringVar()
        ttk.Label(form, text="Label").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(form, textvariable=self.label, width=22).grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))
        ttk.Label(form, text="Chance (%)").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(form, textvariable=self.chance, width=8).grid(row=2, column=1, sticky="w", padx=4, pady=(4, 0))
        ttk.Label(form, text="Frame").grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.frames = FrameChooser(form, lambda: self.project, self.preview_changed, width=24)
        self.frames.box.grid(row=3, column=1, sticky="w", padx=4, pady=(4, 0))
        ttk.Label(form, text="Finish").grid(row=4, column=0, sticky="w", pady=(4, 0))
        self.finish = tk.StringVar(value=FINISH_NAMES[0])
        self.finish_box = ttk.Combobox(form, textvariable=self.finish, values=FINISH_NAMES, state="readonly", width=21)
        self.finish_box.grid(row=4, column=1, sticky="w", padx=4, pady=(4, 0))
        pictures = ttk.Frame(form)
        pictures.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.picture_button = ttk.Button(pictures, text="Choose a picture...", command=self.choose_picture)
        self.picture_button.pack(side="left")
        self.whole = tk.BooleanVar(value=False)
        self.whole_check = ttk.Checkbutton(pictures, text="Full art", variable=self.whole)
        self.whole_check.pack(side="left", padx=(6, 0))
        self.layers_button = ttk.Button(pictures, text="Layers...", command=self.layers)
        self.layers_button.pack(side="left", padx=(4, 0))
        self.plate_button = ttk.Button(pictures, text="Name plate...", command=self.choose_plate)
        self.plate_button.pack(side="left", padx=(4, 0))
        self.apply_button = ttk.Button(form, text="Apply", command=self.apply)
        self.apply_button.grid(row=6, column=0, sticky="w", pady=(10, 0))
        self.status = ttk.Label(form, style="Hint.TLabel", wraplength=px(self, 300), justify="left")
        self.status.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # The rest of the tab is the card as it is, or, once it has a design of its own, the Frames designer.
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.plain = ttk.LabelFrame(right, text="The card", padding=8)
        self.plain.grid(row=0, column=0, sticky="nsew")
        self.preview = ttk.Label(self.plain)
        self.preview.pack(anchor="n")
        WrapLabel(self.plain, style="Hint.TLabel", text=(
            "This card has the game's frame or a preset. Design it to place every part yourself: the frame picture, "
            "the picture's window, the name, the stars, the element, ATK and DEF and their pictures, in a card of its own.")
        ).pack(fill="x", pady=(10, 0))
        self.design_button = ttk.Button(self.plain, text="Design the card", command=self.design)
        self.design_button.pack(anchor="w", pady=(6, 0))
        self.design_box = ttk.LabelFrame(right, text="This card's own design", padding=6)
        self.design_box.grid(row=0, column=0, sticky="nsew")
        self.design_box.grid_remove()
        bar = ttk.Frame(self.design_box)
        bar.pack(fill="x")
        self.undesign_button = ttk.Button(bar, text="Remove the design", command=self.remove_design)
        self.undesign_button.pack(side="left")
        ttk.Label(bar, text="Drag the parts on the card, or use the fields.", style="Hint.TLabel").pack(side="left", padx=8)
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
        for widget in (self.remove_button, self.picture_button, self.plate_button, self.design_button,
                       self.apply_button, self.whole_check, self.layers_button):
            widget.state(["!disabled"] if on else ["disabled"])
        self.status.configure(text="")
        if not on:
            self.title.configure(text="Choose a variant, or make one.")
            self.label.set("")
            self.chance.set("")
            self.finish.set(FINISH_NAMES[0])
            self.frames.reload(None)
            self.preview.configure(image="")
            self.photo = None
            self.show_right(force=True)
            return
        v = variants.read(project, self.current)
        self.title.configure(text=f"{project.card_label(v.base)}   ({v.key})")
        self.label.set(v.label)
        self.finish.set(finish_name(v.finish))
        self.chance.set(variants.percent_text(v.permille).rstrip("%"))
        self.frames.reload(variants.frame_of(project, self.current))
        self.draw()
        self.show_right(force=True)

    def show_right(self, force=False):
        '''The right of the tab: the Frames designer when the chosen variant has a design of its own, else
        the card as it is. Said again only when it changed, unless `force`.'''
        project, cid = self.project, self.current
        if cid is None or project is None or not variants.has_own_design(project, cid):
            if force or self.designed_for is not None:
                self.design_box.grid_remove()
                self.plain.grid()
                self.designed_for = None
            return
        name = variants.design_name(project.added[cid].key)
        if self.designed_for == (cid, name) and not force:
            return
        if self.designer is None:
            self.designer = ui_frames.FramesPage(self.design_box, DesignHost(self.app), locked={"style": name, "card": cid})
            self.designer.pack(fill="both", expand=True, pady=(4, 0))
            self.designer.fill()
        else:
            self.designer.lock(name, cid)
        self.plain.grid_remove()
        self.design_box.grid()
        self.designed_for = (cid, name)

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
        choice = self.frames.choice()
        frame = self.frames.frame_image()
        window = variants.window_of_choice(self.project, choice)
        if frame is None and variants.shows_game_frame(self.project, choice) and self.wa is not None:
            frame = card_icons.card_frame(self.wa, self.project.cards[self.project.base_of(self.current)].shown_frame())
        card = variants.card_picture(self.picture_of(self.current), frame, px(self, PLAIN_W), window)
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
            if finish_key(self.finish.get()) != before.finish:
                variants.set_finish(project, cid, finish_key(self.finish.get()))
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
        self.show_right()
        self.applied()
        return True

    def commit(self):
        return self.apply() if self.current is not None else True

    def choose_picture(self):
        cid = self.current
        if cid is None:
            return
        path = file_dialogs.askopenfilename(parent=self, title=f"A picture for {self.project.card_label(cid)}",
                                            filetypes=[("Pictures", "*.png *.jpg *.jpeg"), ("PNG images", "*.png"),
                                                       ("All files", "*.*")])
        if path:
            self.use_picture(path)

    def use_picture(self, path, whole=None) -> bool:
        """`path` as the chosen variant's picture (the button, and tests). `whole` (else the Full art box)
        keeps all of the picture and covers the card with it."""
        whole = self.whole.get() if whole is None else whole
        try:
            notes = variants.set_art(self.project, self.current, pngio.read(path), whole)
        except (OSError, pngio.PngError, ValueError) as problem:
            messagebox.showerror("FM Editor", f"Could not use {path}: {problem}", parent=self)
            return False
        self.app.changed()
        self.fill()
        self.tree.selection_set(str(self.current))
        self.frames.reload(variants.frame_of(self.project, self.current))
        self.draw()
        self.show_right(force=True)
        self.status.configure(text=f"{Path(path).name} is the picture" + (": " + "; ".join(notes) if notes else "."))
        return True

    def layers(self):
        """The picture made of a background and a foreground, each its own file, placed on the card here, and again
        on the hand's small card (their proportions differ: each has its own places)."""
        cid = self.current
        if cid is None:
            return
        found = variants.read_layers(self.project, cid)
        state = {name: {"image": found[name][0] if name in found else None,
                        "label": "kept in the mod" if name in found else "none"}
                 for name in variants.LAYER_NAMES}
        fields = {"card": {}, "hand": {}}               # mode -> layer -> x, y, width: the text in the boxes
        mode = tk.StringVar(value="card")

        def number(value):
            return f"{value:g}" if isinstance(value, float) else str(value)

        def build(dialog, body):
            ttk.Label(body, text="Two pictures laid into one: the background, and the foreground over it (a figure on "
                                 "a clear background, say). Place them on the card, then on the hand's small card, "
                                 "which has other proportions. Places are in card units (the card is 140 x 196, the "
                                 "hand's card 52 x 60); what runs past is cut off.", style="Hint.TLabel",
                      wraplength=px(self, 400), justify="left").grid(row=0, column=0, columnspan=3, sticky="w")
            switch = ttk.Frame(body)
            switch.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
            ttk.Label(switch, text="Place them on").pack(side="left")
            for value, text in (("card", "the card"), ("hand", "the hand's card")):
                ttk.Radiobutton(switch, text=text, value=value, variable=mode, command=lambda: show(dialog)).pack(
                    side="left", padx=(8, 0))
            for row, name in enumerate(variants.LAYER_NAMES):
                line = ttk.Frame(body)
                line.grid(row=2 + row, column=0, columnspan=3, sticky="w", pady=(8, 0))
                ttk.Label(line, text=name.capitalize(), width=11).pack(side="left")
                ttk.Button(line, text="Choose...", command=lambda n=name: choose(dialog, n)).pack(side="left", padx=4)
                state[name]["text"] = ttk.Label(line, text=state[name]["label"], style="Hint.TLabel")
                state[name]["text"].pack(side="left", padx=4)
            dialog.sets = {}
            for which in ("card", "hand"):
                frame = ttk.Frame(body)
                dialog.sets[which] = frame
                for row, name in enumerate(variants.LAYER_NAMES):
                    ttk.Label(frame, text=name.capitalize(), width=11).grid(row=row, column=0, sticky="w", pady=(6, 0))
                    fields[which][name] = {}
                    place = None
                    if name in found:
                        place = found[name][1] if which == "card" else (found[name][2] or
                                                                         variants.default_hand_layer(found[name][1]))
                    for column, key in enumerate(("x", "y", "width")):
                        ttk.Label(frame, text=key.capitalize()).grid(row=row, column=1 + column * 2, sticky="e",
                                                                     pady=(6, 0))
                        var = tk.StringVar(value=number(place[key]) if place else "")
                        box = ttk.Spinbox(frame, from_=-400, to=800, width=6, textvariable=var,
                                          command=lambda: draw(dialog))
                        box.grid(row=row, column=2 + column * 2, sticky="w", padx=(2, 8), pady=(6, 0))
                        box.bind("<Return>", lambda e: draw(dialog))
                        box.bind("<FocusOut>", lambda e: draw(dialog))
                        fields[which][name][key] = var
            dialog.preview = ttk.Label(body)
            dialog.preview.grid(row=0, column=3, rowspan=6, padx=(14, 0))
            dialog.photo = None
            show(dialog)

        def show(dialog):
            for which, frame in dialog.sets.items():
                if which == mode.get():
                    frame.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
                else:
                    frame.grid_remove()
            draw(dialog)

        def place_of(which, name):
            try:
                return {key: float(fields[which][name][key].get()) for key in ("x", "y", "width")}
            except ValueError:
                return None

        def chosen(which):
            out = []
            for name in variants.LAYER_NAMES:
                place = place_of(which, name)
                if state[name]["image"] is not None and place is not None:
                    out.append((state[name]["image"], place["x"], place["y"], place["width"]))
            return out

        def choose(dialog, name):
            path = file_dialogs.askopenfilename(parent=dialog, title=f"The {name}",
                                                filetypes=[("Pictures", "*.png *.jpg *.jpeg"), ("PNG images", "*.png"),
                                                           ("All files", "*.*")])
            if not path:
                return
            try:
                state[name]["image"] = pngio.read(path)
            except (OSError, pngio.PngError, ValueError) as problem:
                messagebox.showerror("FM Editor", f"Could not use {path}: {problem}", parent=dialog)
                return
            state[name]["text"].configure(text=Path(path).name)
            first = variants.default_layer(name, state[name]["image"])
            for which, place in (("card", first), ("hand", variants.default_hand_layer(first))):
                for key, value in place.items():
                    fields[which][name][key].set(number(value))
            draw(dialog)

        def draw(dialog):
            base = self.project.base_of(self.current)
            frame_index = self.project.cards[base].shown_frame()
            if mode.get() == "card":
                composed = variants.compose_layers(chosen("card"), scale=2)
                frame = card_icons.card_frame(self.wa, frame_index) if self.wa is not None else None
                picture = variants.card_picture(composed, frame, px(self, PREVIEW_W),
                                                {"x": 0, "y": 0, "width": 140, "height": 196})
            else:
                composed = variants.compose_layers(chosen("hand"), scale=4, units=variants.HAND_SIZE)
                frame = ui_frames.hand_frame(self.wa, frame_index) if self.wa is not None else None
                picture = variants.hand_picture(composed, frame, px(self, PREVIEW_W))
            dialog.photo = photo(dialog, picture)
            dialog.preview.configure(image=dialog.photo)

        def ok(dialog):
            layers = {}
            for name in variants.LAYER_NAMES:
                card, hand = place_of("card", name), place_of("hand", name)
                if state[name]["image"] is not None and card is not None:
                    layers[name] = (state[name]["image"], card, hand)
            try:
                notes = variants.set_layers(self.project, cid, layers)
            except ValueError as problem:
                return str(problem)
            self.after_picture(notes, "the layers")
            return None

        FormDialog(self, "Layers", build, ok)

    def after_picture(self, notes, what):
        """The tab, shown again after the chosen variant's picture was made (the picture button, the layers)."""
        self.app.changed()
        self.fill()
        self.tree.selection_set(str(self.current))
        self.frames.reload(variants.frame_of(self.project, self.current))
        self.draw()
        self.show_right(force=True)
        self.status.configure(text=f"{what} are the picture" + (": " + "; ".join(notes) if notes else "."))

    def choose_plate(self):
        cid = self.current
        if cid is None:
            return
        path = file_dialogs.askopenfilename(parent=self, title=f"A name plate for {self.project.card_label(cid)}",
                                            filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
        if path:
            self.use_plate(path)

    def use_plate(self, path) -> bool:
        '''`path` as the chosen variant's name plate: the picture the game draws for its name (96x14, up to 4x),
        in place of the name set in the game's own lettering (the button, and tests).'''
        try:
            notes = art.set_image(self.project, self.current, "title", pngio.read(path))
        except (OSError, pngio.PngError, ValueError) as problem:
            messagebox.showerror("FM Editor", f"Could not use {path}: {problem}", parent=self)
            return False
        self.app.changed()
        self.status.configure(text=f"{Path(path).name} is the name plate" + (": " + "; ".join(notes) if notes else "."))
        return True

    # --- the card's own design -----------------------------------------------------------------

    def design(self):
        '''Give the chosen variant a frame style of its own and show the Frames designer for it: the
        right of the tab, edited part by part. Returns the designer page.'''
        cid = self.current
        if cid is None or not self.apply():
            return None
        try:
            variants.own_design(self.project, cid)
            self.app.changed()
            self.fill()
            self.tree.selection_set(str(cid))
            self.frames.reload(variants.frame_of(self.project, cid))
            self.show_right(force=True)
        except Exception as problem:        # never silently: a person pressed a button
            messagebox.showerror("FM Editor", f"The designer could not be shown: {problem}", parent=self)
            raise
        return self.designer

    def remove_design(self):
        cid = self.current
        if cid is None or not variants.has_own_design(self.project, cid):
            return
        if not messagebox.askyesno("Remove the design", "Take this card's own design away? It goes back to the "
                                   "game's frame. Edit > Undo brings it back.", parent=self):
            return
        variants.remove_own_design(self.project, cid)
        self.app.changed()
        self.fill()
        self.tree.selection_set(str(cid))
        self.show(cid)

    # --- making and removing -------------------------------------------------------------

    def make(self, base, image, frame, permille, label, full_art=False, finish="") -> int:
        """A variant, in the project and the list (the dialog's OK, and tests); its card id."""
        cid, notes = variants.add_variant(self.project, base, image, frame, permille, label, full_art=full_art,
                                          finish=finish)
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
            ttk.Button(line, text="Choose a picture...", command=lambda: choose(dialog)).pack(side="left")
            dialog.whole = tk.BooleanVar(value=False)
            ttk.Checkbutton(line, text="Full art", variable=dialog.whole, command=lambda: draw(dialog)).pack(
                side="left", padx=(6, 0))
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
            ttk.Label(body, text="Finish").grid(row=5, column=0, sticky="w", pady=(4, 0))
            dialog.finish = tk.StringVar(value=FINISH_NAMES[0])
            ttk.Combobox(body, textvariable=dialog.finish, values=FINISH_NAMES, state="readonly", width=23).grid(
                row=5, column=1, sticky="w", padx=4, pady=(4, 0))
            dialog.preview = ttk.Label(body)
            dialog.preview.grid(row=0, column=2, rowspan=7, padx=(14, 0))
            dialog.photo = None
            dialog.card.var.trace_add("write", lambda *_: draw(dialog))
            draw(dialog)

        def choose(dialog):
            path = file_dialogs.askopenfilename(parent=dialog, title="A picture for the variant",
                                                filetypes=[("Pictures", "*.png *.jpg *.jpeg"), ("PNG images", "*.png"),
                                                           ("All files", "*.*")])
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
            choice = dialog.frames.choice()
            window = variants.window_of_choice(self.project, choice)
            frame = dialog.frames.frame_image()
            if frame is None and variants.shows_game_frame(self.project, choice) and self.wa is not None and base:
                frame = card_icons.card_frame(self.wa, self.project.cards[base].shown_frame())
            if dialog.whole.get() and state["image"] is not None:       # all of the picture, over the card
                window = variants.full_art_window(image.width / image.height)
            card = variants.card_picture(image, frame, px(self, PREVIEW_W), window)
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
                self.make(base, state["image"], dialog.frames.choice(), chance, dialog.label.get().strip(),
                          full_art=dialog.whole.get(), finish=finish_key(dialog.finish.get()))
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
