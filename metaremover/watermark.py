"""Pixel-structure disruption. Delegates to realism.structure_pass.

Google SynthID and similar frequency-domain marks are not guaranteed gone.
"""
from __future__ import annotations

from PIL import Image

from . import realism

_MAP = {
    "light": "subtle",
    "medium": "subtle",
    "subtle": "subtle",
    "strong": "strong",
    "nuclear": "nuclear",
}


def disrupt_pixel_watermarks(im: Image.Image, strength: str = "medium") -> Image.Image:
    return realism.structure_pass(im, strength=_MAP.get(strength, "subtle"))
