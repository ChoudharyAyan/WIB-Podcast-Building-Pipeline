"""Loads brand/wib.json. The only place colours and fonts come from."""

import json
from functools import lru_cache

from . import ROOT


@lru_cache
def brand() -> dict:
    return json.loads((ROOT / "brand" / "wib.json").read_text())


def color(name: str) -> str:
    """Hex for a brand colour name (or pass a hex through)."""
    return name if name.startswith("#") else brand()["colors"][name]


def ass_color(name: str, alpha: int = 0) -> str:
    """ASS subtitle colour: &HAABBGGRR."""
    h = color(name).lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()
