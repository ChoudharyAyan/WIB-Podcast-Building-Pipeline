"""Stage 7: the WIB intro sting, 15 s, in 16:9 (long form) and 9:16 (reels). Approved on Ep01 (v2).

Scenes (120 BPM grid):
  0.00–2.75  volt: WIB badge, WHAT / I / BUILT pop in, orange dot, PODCAST, tagline; orange wipe from 2.25
  2.75–6.25  orange: cast floating, the episode's words pop in one per beat
  6.25–9.50  scrolling rows with the talking face(s) popping in (video only, no sound)
  9.50–12.0  the cast line-up with names
  12.0–15.0  badge, EPISODE NN, tagline, subtitle, cast row, fade to black

Content comes from episode.json "sting" (see episodes/_template). Music: the first 15 s of
"sting.music", faded out, at about -16 LUFS.
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from . import ff
from .episode import Episode
from .faces import FACE_LIFT, face_source
from .graphics import (INK, PAPER, SIGNAL, VOLT, Encoder, back, badge, circle, eo, font, hexc, load, mascot, paste,
                       still, text_im, video_frames)

FPS, DUR, P = 30, 15.0, 0.4
ROWTXT = "AGENTS  •  WORKFLOWS  •  AUTOMATIONS  •  "

LAYOUT = {
    "h": dict(size=(1920, 1080), badge=(960, 300, 1.05), w1_scale=0.8, w1_gap=50, w1_y=640, dot_dy=50, podc=(960, 820), tag=(960, 905),
              word=(960, 545), word_max=1800, rows=9, face=(960, 540), face_sc=1.0, faces2=[(650, 540), (1270, 540)],
              cast_hdr=(960, 190), logo=(960, 430, 1.45), ep=(960, 150), tagl=(960, 740), sub=(960, 830), row_y=1060,
              floats=[(260, 230, -12), (1660, 210, 10), (210, 860, 8), (1700, 850, -9), (960, 120, 0), (520, 980, 6), (1400, 980, -6)]),
    "v": dict(size=(1080, 1920), badge=(540, 640, 1.35), w1_scale=0.55, w1_gap=34, w1_y=1010, dot_dy=35, podc=(540, 1150), tag=(540, 1235),
              word=(540, 960), word_max=960, rows=15, face=(540, 960), face_sc=1.35, faces2=[(540, 700), (540, 1260)],
              cast_hdr=(540, 420), logo=(540, 800, 1.7), ep=(540, 420), tagl=(540, 1180), sub=(540, 1270), row_y=1700,
              floats=[(230, 420, -12), (850, 400, 10), (220, 1540, 8), (860, 1560, -9), (540, 260, 0), (160, 980, 6), (920, 1000, -6)]),
}


def BLACK(s):
    return font("Inter.ttf", s, 900)


def MONO(s):
    return font("JBMono.ttf", s, 700)


def cast_images(ep: Episode, cfg: dict) -> list[tuple[Image.Image, str, tuple, str]]:
    """[(image, label, colour)] for the cast scene: mascots, or people's faces in a ring."""
    out = []
    for c in cfg.get("cast", []):
        col = hexc(c.get("colour") or (ep.person_colour(c["person"]) if "person" in c else "volt"))
        kind = "art"
        if "mascot" in c:
            im = mascot(c["mascot"])
        elif "image" in c:
            im = load(ep.asset(c["image"]))
        else:
            kind = "face"
            src, t, crop = face_source(ep, c["take"], c["person"], c["at"])
            im = circle(still(src, t, f"{crop},scale=420:420:flags=lanczos,{FACE_LIFT}", (420, 420)), col, 14)
        label = c.get("label") or ep.people.get(c.get("person"), {}).get("name", "")
        out.append((im, label, col, kind))
    return out


def face_clips(ep: Episode, cfg: dict, n: int) -> list[list[Image.Image]]:
    clips = []
    for f in cfg.get("faces", [])[:2]:
        src, t, crop = face_source(ep, f["take"], f.get("person"), f["at"])
        col = hexc(ep.person_colour(f.get("person") or ep.host)) if ep.conversation else VOLT
        clips.append([circle(Image.fromarray(fr), col, 12)
                      for fr in video_frames(src, t, n / FPS, f"{crop},scale=470:470:flags=lanczos,{FACE_LIFT}", (470, 470), FPS)])
    return clips


def make_frame_fn(ep: Episode, cfg: dict, L: dict, cast, faces):
    SX, SY = L["size"]
    W1 = [text_im(w, BLACK(230), INK) for w in ("WHAT", "I", "BUILT")]
    DOT = Image.new("RGBA", (60, 60))
    ImageDraw.Draw(DOT).ellipse((0, 0, 59, 59), fill=SIGNAL)
    words = cfg.get("words") or ["A", "PODCAST", "FOR", "AI", "BUILDERS"]
    beats = [3.0 + k * (2.3 / max(1, len(words) - 1)) for k in range(len(words))]
    WORD_IM = {w: text_im(w, BLACK(240 if len(w) < 7 else 200), INK) for w in words}
    ROW = text_im(ROWTXT, BLACK(120), SIGNAL)
    ROW_DIM = text_im(ROWTXT, BLACK(120), tuple(int(c * 0.35 + i * 0.65) for c, i in zip(SIGNAL, INK)))
    STEP = BLACK(120).getlength(ROWTXT)
    EP = text_im(f"EPISODE {ep.get('number', '01')}", MONO(46 if SX > SY else 48), VOLT)
    TAG = text_im("A Podcast for AI Builders", font("Inter.ttf", 64 if SX > SY else 56, 600), PAPER)
    SUB = text_im(cfg.get("subtitle", ep.get("title", "")), font("Inter.ttf", 44 if SX > SY else 40, 500), (170, 170, 178))
    PODC = text_im("PODCAST", MONO(64), INK)
    TAGV = text_im("A Podcast for AI Builders", font("Inter.ttf", 52, 600), INK)
    HDR = text_im(cfg.get("cast_title", "MEET THE CAST"), MONO(44 if SX > SY else 48), VOLT)
    BADGE = badge()
    NAMES = [text_im(lbl, font("Lilita.ttf", 64), col) for _, lbl, col, _k in cast]
    floats = [(cast[k % len(cast)][0], *L["floats"][k]) for k in range(min(len(L["floats"]), max(len(cast), 5)))] if cast else []
    is_face = [c[3] == "face" for c in cast]

    def frame(t: float) -> Image.Image:
        img = Image.new("RGBA", (SX, SY), INK + (255,))
        d = ImageDraw.Draw(img)
        if t < 2.75:
            d.rectangle((0, 0, SX, SY), fill=VOLT)
            bx, by, bs = L["badge"]
            paste(img, BADGE, bx, by, sc=bs * back((t - 0.1) / P), rot=-10 * (1 - eo((t - 0.1) / 0.6)))
            S, gap = L["w1_scale"], L["w1_gap"]
            tot = sum(i.width for i in W1) * S + 2 * gap + 56 * S / 0.8
            x0, xs = SX / 2 - tot / 2, []
            for i in W1:
                xs.append(x0 + i.width * S / 2)
                x0 += i.width * S + gap
            for k, im in enumerate(W1):
                paste(img, im, xs[k], L["w1_y"], sc=S * back((t - 0.55 - k * 0.3) / P))
            paste(img, DOT, xs[2] + W1[2].width * S / 2 + 14 * S / 0.8, L["w1_y"] + L["dot_dy"], sc=S * back((t - 1.45) / 0.3))
            paste(img, PODC, *L["podc"], a=eo((t - 1.55) / 0.4))
            paste(img, TAGV, *L["tag"], a=eo((t - 1.75) / 0.4))
            if t > 2.25:
                x = SX * (1 - eo((t - 2.25) / 0.5))
                d.rectangle((x, 0, SX, SY), fill=SIGNAL)
        elif t < 6.25:
            d.rectangle((0, 0, SX, SY), fill=SIGNAL)
            for k, (im, x, y, r) in enumerate(floats):
                p = (t - 2.75 - k * 0.12) / 0.45
                bob = 14 * math.sin((t * 1.6 + k) * math.pi)
                sc = (0.95 if not is_face[k % len(cast)] else 0.62) * back(p)
                paste(img, im, x, y + bob, sc=sc, rot=r + 4 * math.sin(t * 2.2 + k))
            cur = [k for k, s0 in enumerate(beats) if t >= s0]
            if cur:
                k = cur[-1]
                wi = WORD_IM[words[k]]
                paste(img, wi, *L["word"], sc=min(1.0, L["word_max"] / wi.width) * back((t - beats[k]) / 0.3))
        elif t < 9.5:
            for r in range(L["rows"]):
                y = -40 + r * 135
                dirn = 1 if r % 2 else -1
                off = (t - 6.25) * 380 * dirn
                x = -((off % STEP) + STEP)
                while x < SX:
                    img.alpha_composite(ROW if r % 2 == 0 else ROW_DIM, (int(round(x)), y))
                    x += STEP
            p = (t - 6.4) / P
            sc = back(p) if t < 9.1 else 1 - eo((t - 9.1) / 0.35)
            spots = [L["face"]] if len(faces) == 1 else L["faces2"]
            for k, clip in enumerate(faces):
                fi = min(len(clip) - 1, max(0, int((t - 6.4) * FPS)))
                if p > 0:
                    paste(img, clip[fi], *spots[k], sc=L["face_sc"] * sc * (0.85 if len(faces) > 1 else 1))
        elif t < 12.0:
            paste(img, HDR, *L["cast_hdr"], a=eo((t - 9.5) / 0.4))
            n = len(cast)
            for k, (im, *_r) in enumerate(cast):
                if SX > SY:
                    x, y = SX / 2 + (k - (n - 1) / 2) * min(350, 1700 / max(1, n)), 540
                    sc0 = 1.25 if not is_face[k] else 0.85
                else:
                    row = [(290, 760), (790, 760), (180, 1240), (540, 1240), (900, 1240)] if n > 2 else [(540, 760), (540, 1300)]
                    x, y = row[k % len(row)]
                    sc0 = 1.05 if not is_face[k] else 0.8
                p = (t - 9.6 - k * 0.22) / 0.45
                hop = 16 * abs(math.sin((t - 9.5) * 1.6 * math.pi)) if t > 11.0 else 0
                paste(img, im, x, y - hop, sc=sc0 * back(p))
                paste(img, NAMES[k], x, y + (250 if SX > SY else 200 if n > 2 else 230), sc=back((t - 9.85 - k * 0.22) / 0.4))
        else:
            g = eo((t - 12.0) / 0.5)
            lx, ly, ls = L["logo"]
            paste(img, BADGE, lx, ly, sc=ls * back((t - 12.0) / 0.45), rot=-8 * (1 - g))
            paste(img, EP, *L["ep"], a=eo((t - 12.2) / 0.4))
            paste(img, TAG, *L["tagl"], a=eo((t - 12.4) / 0.4))
            paste(img, SUB, *L["sub"], sc=min(1.0, (SX - 120) / SUB.width), a=eo((t - 12.6) / 0.4))
            n = len(cast)
            step = 200 if SX > SY else 190
            for k, (im, *_r) in enumerate(cast):
                x = SX / 2 + (k - (n - 1) / 2) * step
                paste(img, im, x, L["row_y"] - 120 * eo((t - 12.7 - k * 0.1) / 0.4), sc=0.62 if not is_face[k] else 0.36)
            if t > 14.4:
                img.alpha_composite(Image.new("RGBA", (SX, SY), (0, 0, 0, int(255 * eo((t - 14.4) / 0.6)))))
        return img.convert("RGB")
    return frame


def render(ep: Episode, orient: str = "h", stills: list[float] | None = None) -> Path:
    cfg = ep.get("sting", {})
    L = LAYOUT[orient]
    cast = cast_images(ep, cfg)
    faces = face_clips(ep, cfg, int(3.2 * FPS)) if cfg.get("faces") else []
    frame = make_frame_fn(ep, cfg, L, cast, faces)
    out_dir = ep.edit / "assets"
    if stills:
        for t in stills:
            frame(t).save(out_dir / f"sting-{orient}-{t:.2f}.jpg", quality=88)
        print(f"stills in {out_dir}")
        return out_dir
    silent = out_dir / f"sting-{orient}-silent.mp4"
    enc = Encoder(silent, L["size"], FPS, crf=14)
    for i in range(int(DUR * FPS)):
        enc.write(frame(i / FPS))
    enc.close()
    out = out_dir / ("intro-sting.mp4" if orient == "h" else "intro-sting-vertical.mp4")
    music = cfg.get("music") or ep.get("music_bed")
    if music:
        ff.run(["-i", silent, "-i", ep.asset(music), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                "-af", f"atrim=0:{DUR},loudnorm=I=-16:TP=-2,afade=t=in:d=0.05,afade=t=out:st={DUR - 1.2}:d=1.2",
                "-c:a", "aac", "-b:a", "320k", "-ar", 48000, "-t", DUR, out])
    else:
        print("No sting music set (episode.json sting.music): the sting is silent.", file=sys.stderr)
        ff.run(["-i", silent, "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                "-c:a", "aac", "-t", DUR, out])
    silent.unlink()
    print(f"wrote {out}")
    return out


def run(episode_id: str, orient: str = "both", stills: list[float] | None = None):
    ep = Episode(episode_id)
    for o in (["h", "v"] if orient == "both" else [orient]):
        render(ep, o, stills)
