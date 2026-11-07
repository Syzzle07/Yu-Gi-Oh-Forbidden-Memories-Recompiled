"""The card numbers and words the Variants designer colors (pictures of white ink, in text_presets_data.py)."""
import base64

from . import text_presets_data


def digits() -> bytes:
    """The ten ATK/DEF digits and their greyed ones, as the game's digit strip."""
    return base64.b64decode("".join(text_presets_data.DIGITS))


SHAPES = (("star", "Star"), ("diamond", "Diamond"), ("heart", "Heart"), ("disc", "Disc"))


def star(name: str) -> bytes:
    """A level star's picture, white ink: star, diamond, heart or disc."""
    return base64.b64decode("".join(getattr(text_presets_data, "STAR_" + name.upper())))


def label(dfd: bool) -> bytes:
    """The word ATK (or DFD) as a picture."""
    return base64.b64decode("".join(text_presets_data.DFD if dfd else text_presets_data.ATK))
