"""Shared drawing helpers for the motion graphics (sting, cards, reels, covers). Pillow frames piped to ffmpeg.
Every frame is a pure function of time, so any frame can be rendered alone as a still to check it."""

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import BRAND
from .brand import brand

FONTS = BRAND / "fonts"


def hexc(h: str) -> tuple[int, int, int]:
    h = brand()["colors"].get(h, h).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


INK, PAPER, VOLT, SIGNAL = (hexc(k) for k in ("ink", "paper", "volt", "signal"))


def font(name: str, size: float, weight: int | None = None) -> ImageFont.FreeTypeFont:
    """name: Inter.ttf (variable: optical size + weight), JBMono.ttf (weight), Lilita.ttf."""
    f = ImageFont.truetype(str(FONTS / name), max(1, int(round(size))))
    if weight:
        f.set_variation_by_axes([32, weight] if name == "Inter.ttf" else [weight])
    return f


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def eo(x):
    """Ease out cubic."""
    x = clamp(x)
    return 1 - (1 - x) ** 3


def back(x, s=1.7):
    """Ease out with a small overshoot: the WIB 'pop'."""
    x = clamp(x) - 1
    return x * x * ((s + 1) * x + s) + 1


def text_im(s: str, f, fill, stroke: int = 0, sfill=INK) -> Image.Image:
    l, t, r, b = f.getbbox(s, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 8, b - t + 8))
    ImageDraw.Draw(im).text((4 - l, 4 - t), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)
    return im


def paste(img: Image.Image, im: Image.Image, cx, cy, sc=1.0, a=1.0, rot=0.0):
    if sc <= 0.01 or a <= 0.01:
        return
    if sc != 1:
        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    if rot:
        im = im.rotate(rot, Image.BICUBIC, expand=True)
    if a < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    img.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def pill(text: str, bg, fg, f, pad=(28, 14)) -> Image.Image:
    t = text_im(text, f, fg)
    im = Image.new("RGBA", (t.width + 2 * pad[0], t.height + 2 * pad[1]))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=im.height // 2, fill=bg)
    im.alpha_composite(t, (pad[0], pad[1]))
    return im


def circle(im: Image.Image, ring=None, rw: int = 0) -> Image.Image:
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0, im.width - 1, im.height - 1), fill=255)
    o = im.convert("RGBA").copy()
    o.putalpha(m)
    if not ring:
        return o
    r = Image.new("RGBA", (im.width + 2 * rw, im.height + 2 * rw))
    ImageDraw.Draw(r).ellipse((0, 0, r.width - 1, r.height - 1), fill=ring)
    r.alpha_composite(o, (rw, rw))
    return r


def load(path: Path | str) -> Image.Image:
    return Image.open(path).convert("RGBA")


def mascot(name: str) -> Image.Image:
    return load(BRAND / "mascots" / f"{name}.png")


def badge() -> Image.Image:
    return load(BRAND / "assets" / "wib-badge-ink.png")


def wordmark(paper: bool = True) -> Image.Image:
    return load(BRAND / "assets" / ("wib-wordmark-paper.png" if paper else "wib-wordmark-ink.png"))


# ---------- video in and out ----------
def video_frames(src: Path, start: float, dur: float, vf: str, size: tuple[int, int], fps: int = 30):
    """Yield RGB numpy frames of `src` from `start`, run through filter `vf` that outputs `size`.
    Holds the last frame if the source runs short."""
    n = int(round(dur * fps))
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{max(0, start):.3f}", "-t", f"{dur + 0.5:.3f}", "-i", str(src), "-an",
                          "-vf", f"fps={fps},{vf}", "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    last, nb = None, size[0] * size[1] * 3
    for _ in range(n):
        b = p.stdout.read(nb)
        if len(b) == nb:
            last = np.frombuffer(b, np.uint8).reshape(size[1], size[0], 3)
        yield last if last is not None else np.zeros((size[1], size[0], 3), np.uint8)
    p.kill()
    p.wait()


def still(src: Path, t: float, vf: str, size: tuple[int, int]) -> Image.Image:
    fr = next(video_frames(src, t, 1 / 30, vf, size, 30))
    return Image.fromarray(fr).convert("RGBA")


class Encoder:
    """Write RGB frames to an mp4 (x264 CRF 14 by default, the quality Ep01's graphics used)."""

    def __init__(self, out: Path, size: tuple[int, int], fps: int = 30, crf: int = 14, preset: str = "medium"):
        out.parent.mkdir(parents=True, exist_ok=True)
        self.p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
                                   "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                                   "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)

    def write(self, img):
        self.p.stdin.write((img.convert("RGB") if isinstance(img, Image.Image) else img).tobytes())

    def close(self):
        self.p.stdin.close()
        if self.p.wait():
            raise SystemExit("ffmpeg failed while encoding graphics")
