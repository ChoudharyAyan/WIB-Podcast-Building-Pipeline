"""Instagram reel covers (1080x1920) and the YouTube thumbnail (1280x720), from episode.json.

Covers keep everything that matters inside the centre 1080x1350 band (y 285-1635) so the 4:5
profile-grid crop still shows the title, the faces and the mascots (Ep01 rule).

episode.json:
  "covers": [{"out": "Cover-Reel-1.jpg", "bg": "signal", "ring": "volt",
              "title": ["2 AI agents that", "save me 10+ hours"], "sub": "For product managers",
              "faces": [{"person": "host", "take": "t1", "at": 312.4}],   # or {"image": "raw/yash.png"}
              "mascots": ["nova", "pixel"]}]
  "thumbnail": {"lines": ["How to be a", {"text": "better vibe coder", "hl": true}],
                "sub": ["A system architect on", "shipping with AI"],
                "faces": [{"person": "host", ...}, {"person": "yash", ...}], "mascots": []}
Face times are in the take's reference clock; pick a smiling frame with `wib frame` first.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .episode import Episode
from .faces import FACE_LIFT, face_source
from .graphics import INK, PAPER, VOLT, badge, circle, font, hexc, load, mascot, paste, still

MASCOT_COL = {"nova": (155, 107, 255), "pixel": VOLT, "luna": (45, 212, 191), "scout": hexc("signal"), "ollie": (255, 176, 32)}


def colour(ep: Episode, c) -> tuple:
    if isinstance(c, (list, tuple)):
        return tuple(c)
    if c in ep.people:
        return hexc(ep.person_colour(c))
    return hexc({"amber": "#FFB020", "violet": "#9B6BFF", "teal": "#2DD4BF"}.get(c, c))


def face_image(ep: Episode, f: dict, size: int) -> Image.Image:
    if f.get("image"):
        im = load(ep.asset(f["image"]))
    else:
        src, t, crop = face_source(ep, f["take"], f.get("person"), float(f["at"]))
        im = still(src, t, f"{crop},scale=1024:1024,{FACE_LIFT}", (1024, 1024))
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
    return im.resize((size, size), Image.LANCZOS)


def cover(ep: Episode, c: dict) -> Image.Image:
    bg = colour(ep, c.get("bg", "volt"))
    title_col = colour(ep, c.get("title_colour", "ink"))
    img = Image.new("RGBA", (1080, 1920), bg + (255,))
    title = c["title"]
    g = Image.new("RGBA", img.size)
    ImageDraw.Draw(g).ellipse((240, 640, 840, 1240), fill=PAPER + (120,))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(60)))
    paste(img, badge(), 540, 400, sc=0.62)
    f = font("Inter.ttf", 84, 900)
    for i, line in enumerate(title):
        ImageDraw.Draw(img).text((540, 545 + i * 92), line, font=f, fill=title_col, anchor="mm")
    faces = c.get("faces", [])
    cy = 1000 + (len(title) - 2) * 40
    if len(faces) == 1:
        ring = colour(ep, c.get("ring", faces[0].get("person") or "ink"))
        paste(img, circle(face_image(ep, faces[0], 520), ring, 18), 540, cy)
    elif faces:  # two people side by side, each in their own colour, slightly overlapping
        for k, fc in enumerate(faces[:2]):
            ring = colour(ep, fc.get("ring") or fc.get("person") or "ink")
            paste(img, circle(face_image(ep, fc, 380), ring, 14), 540 + (k - 0.5) * 380, cy + (k * 2 - 1) * -14)
    ms = c.get("mascots", [])
    n = len(ms)
    if n:
        xs = [540 + (k - (n - 1) / 2) * (190 if n > 2 else 330) for k in range(n)]
        if bg == VOLT:  # Pixel's volt hat disappears on volt, so the cast sits on an ink shelf
            ImageDraw.Draw(img).rounded_rectangle((70, 1318, 1010, 1540), radius=48, fill=INK)
        for k, m in enumerate(ms):
            paste(img, mascot(m), xs[k], 1430, sc=0.85 if n > 2 else 1.05, rot=(-6, 4, -3, 6, -5)[k % 5])
    if c.get("sub"):
        pf = font("Inter.ttf", 40, 800)
        w = int(ImageDraw.Draw(img).textlength(c["sub"], font=pf)) + 64
        ImageDraw.Draw(img).rounded_rectangle((540 - w / 2, 1560, 540 + w / 2, 1626), radius=33, fill=INK)
        ImageDraw.Draw(img).text((540, 1593), c["sub"], font=pf, fill=VOLT, anchor="mm")
    return img.convert("RGB")


def thumbnail(ep: Episode, cfg: dict) -> Image.Image:
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    b = badge().resize((210, 210), Image.LANCZOS)
    img.paste(b, (40, 24), b)
    lines = cfg["lines"]
    size = 78 if max(len(x if isinstance(x, str) else x["text"]) for x in lines) <= 18 else 66
    big, x0, y = font("Inter.ttf", size, 900), 56, 268
    for line in lines:
        text, hl = (line, False) if isinstance(line, str) else (line["text"], line.get("hl"))
        if hl:
            l, t, r, bb = d.textbbox((x0 + 12, y), text, font=big)
            d.rectangle((l - 12, t - 14, r + 12, bb + 16), fill=VOLT)
            d.text((x0 + 12, y), text, font=big, fill=INK)
        else:
            d.text((x0, y), text, font=big, fill=PAPER)
        y += int(size * 1.18)
    sub = font("Inter.ttf", 30, 500)
    for i, s in enumerate(cfg.get("sub", [])):
        d.text((x0 + 4, y + 36 + i * 40), s, font=sub, fill=(190, 190, 198))
    faces = cfg.get("faces", [])
    spots = [(1068, 300, 370)] if len(faces) == 1 else [(980, 250, 300), (1150, 420, 260)]
    for fc, (cx, cy, D) in zip(faces, spots):
        ring = colour(ep, fc.get("ring") or fc.get("person") or "volt")
        sh = Image.new("RGBA", (W, H))
        ImageDraw.Draw(sh).ellipse((cx - D // 2, cy - D // 2 + 12, cx + D // 2, cy + D // 2 + 20), fill=(0, 0, 0, 170))
        sh = sh.filter(ImageFilter.GaussianBlur(16))
        img.paste(sh, (0, 0), sh)
        r = circle(face_image(ep, fc, D), ring, 10)
        img.paste(r, (cx - r.width // 2, cy - r.height // 2), r)
    ms = cfg.get("mascots", [])
    if ms:
        mh, gap = 66, 10
        ims = [mascot(n) for n in ms]
        ims = [m.resize((round(m.width * mh / m.height), mh), Image.LANCZOS) for m in ims]
        cx = spots[0][0] if len(faces) == 1 else 1070
        x = cx - (sum(m.width for m in ims) + gap * (len(ims) - 1)) // 2
        for m in ims:
            img.paste(m, (x, 620 if len(faces) > 1 else 520), m)
            x += m.width + gap
    return img


def run(episode_id: str) -> list[Path]:
    ep = Episode(episode_id)
    out = []
    covers = ep.get("covers", [])
    if covers:
        d = ep.deliver_dir("reels")
        for c in covers:
            p = d / c["out"]
            cover(ep, c).save(p, quality=95)
            out.append(p)
    if ep.get("thumbnail"):
        p = ep.deliver_dir("youtube") / f"{ep.tag}-thumbnail.png"
        thumbnail(ep, ep["thumbnail"]).save(p)
        out.append(p)
    if not out:
        raise SystemExit('Nothing to draw: add "covers" and/or "thumbnail" to episode.json (see the template).')
    for p in out:
        print(p)
    return out
