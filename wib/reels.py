"""Stage 10: Instagram reels, 1080x1920, from edit/reels.json (the layout approved on Ep01).

  top     the speaker's face in a ring in their colour (OBS bubble when solo, camera crop with a guest),
          with the section's mascot beside it and a tag pill underneath
  middle  kinetic captions: 3-word chunks, the spoken word lit in volt
  bottom  the B-roll card (a slow push-in on the screen, the camera, or an image) with callouts
          popping in on their trigger words, optional LIVE DEMO badge and floating tool icons
  end     WIB badge, "FULL EPISODE ON YOUTUBE", the cast

edit/reels.json:
{"reels": [{
  "id": "teaser", "out": "WIB-Ep02-Teaser-30s.mp4",
  "title": "Two lines of title\\nshown over the first 2 s",
  "sting": false,                       # true: the 15 s vertical sting plays first (long reels)
  "end": ["FULL EPISODE ON YOUTUBE", "What I Built, episode 02"],
  "progress": true, "live_label": false,
  "icons": [{"icon": "grok", "label": "GROKBOT", "trigger": "grok"}],
  "cast": ["nova", "pixel"],            # mascots on the end card (default: every carded section's mascot)
  "clips": [{
     "take": "part1", "start": 812.4, "end": 819.0,      # one complete sentence, reference clock
     "tag": "section:a1" | "person:yash",                # what the pill says, and the ring colour
     "face": "yash",                                     # whose face (default: who speaks first)
     "crop": [1250, 800, 1500],                          # B-roll crop on the screen: centre x, y, width
     "callouts": [["15", "15–20 HRS / WEEK"]],           # trigger word, chip text
     "broll": [{"dur": 5.0, "at": null, "src": "screen", "cx": 1250, "cy": 800, "w": 1500},
               {"at": 190.0, "src": "screen", "cx": 1400, "cy": 800, "w": 1500}]   # last one fills the rest
  }]}]}

"at": null means "the screen at the moment the words are said"; a time cuts to another moment
(the live demo). "src" may be "screen", "screen2" (a second screen recording), "camera" or "image:<path>".
"""

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import BRAND, ff
from .audio import CHAINS
from .episode import Episode
from .faces import FACE_LIFT, face_source
from .graphics import INK, PAPER, SIGNAL, VOLT, back, badge, clamp, eo, font, hexc, mascot, paste, pill, text_im, video_frames, wordmark

FPS = 30
SX, SY = 1080, 1920
FACE_D, FACE_C = 560, (540, 560)
CARD = (60, 1090, 1020, 1690)
CW, CH = CARD[2] - CARD[0], CARD[3] - CARD[1]
END_D = 2.6


def F(n, s, w=None):
    return font(n, s, w)


class Reel:
    def __init__(self, ep: Episode, plan: dict):
        self.ep, self.P = ep, plan
        self.F_CAP, self.F_CHIP, self.F_MONO, self.F_TITLE = F("Inter.ttf", 86, 900), F("Inter.ttf", 44, 800), F("JBMono.ttf", 34, 700), F("Inter.ttf", 58, 800)
        self.sting = ep.edit / "assets" / "intro-sting-vertical.mp4" if plan.get("sting") else None
        if self.sting and not self.sting.exists():
            raise SystemExit(f"Run `uv run wib sting {ep.id}` first (needs edit/assets/intro-sting-vertical.mp4).")
        self.ST = 15.0 if self.sting else 0.0
        self.clips, t = [], self.ST
        for c in plan["clips"]:
            c = dict(c)
            cx, cy, cw = c.get("crop", [1280, 800, 1800])
            c["broll"] = c.get("broll") or [{"at": None, "src": "screen" if ep.file(c["take"], "screen") else "camera", "cx": cx, "cy": cy, "w": cw}]
            c["t0"], c["t1"] = t, t + c["end"] - c["start"]
            t = c["t1"]
            self.clips.append(c)
        self.SPEECH, self.TOTAL = t, t + END_D
        self._words()
        self._tags()
        self.callouts = []
        for k, c in enumerate(self.clips):
            for slot, (trig, text) in enumerate(c.get("callouts", [])):
                hit = [w for w in self.words if w[3] == k and w[2].lower().strip(".,!?") == trig.lower().strip(".,!?")]
                self.callouts.append((hit[0][0] if hit else c["t0"] + 0.3, k, text, slot))
        self.icons = [(Image.open(BRAND / "icons" / f"{i['icon']}.png").convert("RGBA").resize((128, 128), Image.LANCZOS), i["label"], i.get("trigger", i["icon"]))
                      for i in plan.get("icons", [])]
        self.icon_t0 = None
        if self.icons:
            named = [w[0] for w in self.words if w[2].lower().startswith(self.icons[0][2].lower())]
            self.icon_t0 = named[0] if named else self.ST
        self.live = False
        self._static()

    # ---------- words and captions ----------
    def _words(self):
        self.words = []  # (t0, t1, word, clip index, speaker)
        for k, c in enumerate(self.clips):
            for w in self.ep.words(c["take"]):
                if c["start"] - 0.02 <= w["start"] and w["end"] <= c["end"] + 0.08:
                    wt = w["word"].strip()
                    if wt.startswith("-") and self.words and self.words[-1][3] == k:  # "follow" + "-ups"
                        p0 = self.words.pop()
                        self.words.append((p0[0], c["t0"] + w["end"] - c["start"], p0[2] + wt, k, p0[4]))
                        continue
                    self.words.append((c["t0"] + w["start"] - c["start"], c["t0"] + w["end"] - c["start"], wt, k, w["speaker"]))
            if not c.get("face"):
                first = next((w for w in self.words if w[3] == k), None)
                c["face"] = first[4] if first else self.ep.host
        self.chunks, cur = [], []
        for i, w in enumerate(self.words):
            cur.append(w)
            nxt = self.words[i + 1] if i + 1 < len(self.words) else None
            if len(cur) == 3 or nxt is None or nxt[3] != w[3] or w[2][-1:] in ".,?!" or (nxt and nxt[0] - w[1] > 0.45) or (nxt and nxt[4] != w[4]):
                self.chunks.append(cur)
                cur = []

    def _tags(self):
        ep = self.ep
        for c in self.clips:
            tag = c.get("tag") or (f"person:{c['face']}" if ep.conversation else "")
            if tag.startswith("section:"):
                sec = ep.section(tag.split(":", 1)[1])
                card = sec.get("card", {})
                c["_tag"] = f"{card.get('tag', '').upper()}  ·  {sec.get('title', '').upper()}".strip(" ·")
                c["_col"] = hexc(card.get("colour", "volt"))
                c["_mascot"] = c.get("mascot", card.get("mascot"))
            else:
                pid = tag.split(":", 1)[1] if tag.startswith("person:") else c["face"]
                p = ep.people.get(pid, {})
                c["_tag"] = ", ".join(x for x in (p.get("name", ""), p.get("title", "")) if x).upper()
                c["_col"] = hexc(ep.person_colour(pid))
                c["_mascot"] = c.get("mascot")
        self.mascots = {m: mascot(m) for m in {c["_mascot"] for c in self.clips if c.get("_mascot")} | set(self.P.get("cast", []))}

    def _static(self):
        self.BG = Image.new("RGBA", (SX, SY), INK + (255,))
        g = Image.new("RGBA", (SX, SY))
        gd = ImageDraw.Draw(g)
        for r in range(900, 0, -12):
            gd.ellipse((540 - r, 560 - r, 540 + r, 560 + r), fill=VOLT + (int(10 * (1 - r / 900) ** 2 * 255 / 40),))
        self.BG.alpha_composite(g.filter(ImageFilter.GaussianBlur(40)))
        self.HDR = text_im(f"WHAT I BUILT  ·  EP {self.ep.get('number', '01')}", self.F_MONO, VOLT)
        self.TITLE = [text_im(l, self.F_TITLE, PAPER) for l in self.P.get("title", "").split("\n") if l]
        self.MASK_FACE = Image.new("L", (FACE_D, FACE_D))
        ImageDraw.Draw(self.MASK_FACE).ellipse((0, 0, FACE_D - 1, FACE_D - 1), fill=255)
        self.MASK_CARD = Image.new("L", (CW, CH))
        ImageDraw.Draw(self.MASK_CARD).rounded_rectangle((0, 0, CW - 1, CH - 1), radius=36, fill=255)
        self.BADGE, self.WORDMARK = badge(), wordmark(True)
        self.cap_cache, self.chip_cache = {}, {}
        cast = self.P.get("cast") or [c["_mascot"] for c in self.clips if c.get("_mascot")]
        self.cast = [self.mascots[m] for m in dict.fromkeys(cast) if m in self.mascots]

    def cap_word(self, w, hi):
        k = (w, hi)
        if k not in self.cap_cache:
            self.cap_cache[k] = text_im(w.upper(), self.F_CAP, VOLT if hi else PAPER, stroke=6)
        return self.cap_cache[k]

    def chip(self, text, col):
        if (text, col) not in self.chip_cache:
            self.chip_cache[(text, col)] = pill(text, col, INK, self.F_CHIP)
        return self.chip_cache[(text, col)]

    # ---------- one frame ----------
    def draw(self, t, face, broll, k):
        img = self.BG.copy()
        c = self.clips[k] if k is not None else None
        paste(img, self.HDR, 540, 150, a=eo((t - self.ST) / 0.4))
        if c is not None:
            col = c["_col"]
            first_of_tag = k == 0 or self.clips[k - 1]["_tag"] != c["_tag"] or self.clips[k - 1]["face"] != c["face"]
            since = t - c["t0"] if first_of_tag else 9
            ring = Image.new("RGBA", (FACE_D + 24, FACE_D + 24))
            ImageDraw.Draw(ring).ellipse((0, 0, FACE_D + 23, FACE_D + 23), fill=col)
            fi = Image.fromarray(face).convert("RGBA")
            fi.putalpha(self.MASK_FACE)
            ring.alpha_composite(fi, (12, 12))
            paste(img, ring, *FACE_C, sc=0.94 + 0.06 * back(since / 0.35) if since < 1 else 1.0)
            if c["_tag"]:
                paste(img, pill(c["_tag"], col, INK, F("Inter.ttf", 30, 800), (22, 11)), 540, 888, sc=back((since - 0.1) / 0.35))
            if c.get("_mascot"):
                paste(img, self.mascots[c["_mascot"]], 880, 650 + 8 * math.sin(t * 3.2), sc=0.9 * back((since - 0.2) / 0.4), rot=-6)
            bi = Image.fromarray(broll).convert("RGBA")
            bi.putalpha(self.MASK_CARD)
            frame = Image.new("RGBA", (CW + 8, CH + 8))
            ImageDraw.Draw(frame).rounded_rectangle((0, 0, CW + 7, CH + 7), radius=40, fill=col)
            frame.alpha_composite(bi, (4, 4))
            cs = t - c["t0"]
            paste(img, frame, (CARD[0] + CARD[2]) / 2, (CARD[1] + CARD[3]) / 2, sc=0.96 + 0.04 * eo(cs / 0.25), a=eo(cs / 0.2) if first_of_tag else 1)
            live = [co for co in self.callouts if co[1] == k and co[0] <= t]
            x, row = 100, 0
            for n, (ct, _, text, _slot) in enumerate(live):
                ch = self.chip(text, PAPER if n % 2 else col)
                if x + ch.width > SX - 80 and x > 100:
                    x, row = 100, row + 1
                paste(img, ch, x + ch.width / 2, 1640 - row * 84, sc=back((t - ct) / 0.3), rot=(-3 if n % 2 else 2) * (1 - eo((t - ct) / 0.4)))
                x += ch.width + 18
            now = [chk for chk in self.chunks if chk[0][0] - 0.05 <= t <= chk[-1][1] + 0.12]
            if now:
                chk = now[-1]
                ims = [self.cap_word(w[2], w[0] <= t <= w[1] + 0.05) for w in chk]
                tot = sum(i.width for i in ims) + 22 * (len(ims) - 1)
                sc = min(1.0, 980 / tot)
                x = 540 - tot * sc / 2
                pop = back((t - chk[0][0]) / 0.18)
                for im in ims:
                    paste(img, im, x + im.width * sc / 2, 990, sc=sc * (0.85 + 0.15 * pop))
                    x += (im.width + 22) * sc
            ts = t - self.ST
            if ts < 2.4 and self.TITLE:
                a = eo(ts / 0.25) * (1 - eo((ts - 2.0) / 0.4))
                img.alpha_composite(Image.new("RGBA", (SX, 260), INK + (int(225 * a),)), (0, 1080))
                for i, im in enumerate(self.TITLE):
                    paste(img, im, 540, 1160 + i * 78, a=a, sc=min(1.0, 980 / im.width) * (0.9 + 0.1 * back(ts / 0.35)))
            if self.icons and self.icon_t0 is not None and t >= self.icon_t0:
                for j, (ic, lbl, _trig) in enumerate(self.icons):
                    tj = t - self.icon_t0 - j * 0.6
                    if tj < 0:
                        continue
                    y = CARD[1] + 90 + j * 158 + 10 * math.sin(t * 2.6 + j * 1.7)
                    paste(img, ic, CARD[2] - 90, y, sc=back(tj / 0.4), rot=6 * math.sin(t * 1.8 + j))
                    lp = pill(lbl, PAPER, INK, F("Inter.ttf", 28, 800), (18, 9))
                    paste(img, lp, CARD[2] - 170 - lp.width / 2, y, sc=back((tj - 0.15) / 0.35))
            if self.P.get("live_label") and self.live:
                on = 0.55 + 0.45 * math.sin(t * 6)
                lp = pill("  LIVE DEMO", INK, PAPER, F("Inter.ttf", 30, 800), (20, 10))
                ImageDraw.Draw(lp).ellipse((18, lp.height / 2 - 9, 36, lp.height / 2 + 9), fill=(255, int(60 + 40 * on), 60))
                paste(img, lp, CARD[0] + 30 + lp.width / 2, CARD[1] + 34)
        else:
            te = t - self.SPEECH
            end = self.P.get("end", ["FULL EPISODE ON YOUTUBE", f"What I Built, episode {self.ep.get('number', '01')}"])
            paste(img, self.BADGE, 540, 640, sc=1.6 * back(te / 0.45), rot=-8 * (1 - eo(te / 0.6)))
            paste(img, text_im(end[0], F("Inter.ttf", 64, 900), VOLT), 540, 1020, sc=back((te - 0.25) / 0.35))
            paste(img, text_im(end[1], F("Inter.ttf", 44, 600), PAPER), 540, 1110, a=eo((te - 0.45) / 0.4))
            n = len(self.cast)
            for j, m in enumerate(self.cast):
                paste(img, m, 540 + (j - (n - 1) / 2) * 160, 1380 + 10 * math.sin(t * 4 + j), sc=0.7 * back((te - 0.5 - j * 0.08) / 0.35))
        if self.P.get("progress"):
            ImageDraw.Draw(img).rounded_rectangle((60, 96, 60 + (SX - 120) * clamp(t / self.TOTAL), 104), radius=4, fill=VOLT)
        paste(img, self.WORDMARK, SX - 60 - 120, SY - 70, sc=240 / self.WORDMARK.width, a=0.85)
        return img.convert("RGB")

    # ---------- media ----------
    def face_frames(self, c):
        src, t, crop = face_source(self.ep, c["take"], c["face"], c["start"])
        return video_frames(src, t, c["end"] - c["start"], f"{crop},scale={FACE_D}:{FACE_D}:flags=lanczos,{FACE_LIFT}", (FACE_D, FACE_D), FPS)

    def _privacy(self, take, start, d):
        boxes = self.ep.read(f"privacy/{take}.json", required=False) or []
        out = ""
        for k, bx in enumerate(boxes):
            if bx["t1"] < start or bx["t0"] > start + d:
                continue
            a0, a1 = bx["t0"] - start, bx["t1"] - start
            out += (f"split[pa{k}][pb{k}];[pb{k}]crop={bx['w']}:{bx['h']}:{bx['x']}:{bx['y']},boxblur=18:2[pbb{k}];"
                    f"[pa{k}][pbb{k}]overlay={bx['x']}:{bx['y']}:enable='between(t,{a0:.2f},{a1:.2f})',")
        return out

    def broll_source(self, c, seg, start, d):
        src = seg.get("src", "screen")
        ep = self.ep
        z = f"zoompan=z='(1+0.08*on/{max(1, int(d * FPS))})':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={CW}x{CH}:fps={FPS}"
        if src.startswith("image:"):
            path = ep.asset(src.split(":", 1)[1])
            return path, 0.0, f"scale={CW * 2}:{CH * 2}:force_original_aspect_ratio=increase,crop={CW * 2}:{CH * 2},{z}", True
        role = src if src in ("camera", "screen2") else "screen"
        path = ep.file(c["take"], role)
        sw, sh = ff.video_size(path)
        w = min(seg.get("w", sw), sw)
        h = min(w / 1.6, sh)
        w = h * 1.6
        x0 = clamp(seg.get("cx", sw / 2) - w / 2, 0, sw - w)
        y0 = clamp(seg.get("cy", sh / 2) - h / 2, 0, sh - h)
        b = ep["bubble"]
        if role == "screen" and not ep.conversation and x0 < b["x"] + b["size"] and y0 + h > b["y"]:  # keep the OBS bubble out
            if b["x"] + b["size"] + w <= sw:
                x0 = b["x"] + b["size"]
            else:
                y0 = max(0, b["y"] - h)
        blur = self._privacy(c["take"] if role == "screen" else f"{c['take']}-screen2", start, d) if role != "camera" else ""
        grade = f",{ep['camera_grade']}" if role == "camera" else ""
        vf = f"{blur}crop={int(w)}:{int(h)}:{int(x0)}:{int(y0)}{grade},scale={CW * 2}:{CH * 2}:flags=lanczos,{z}"
        return path, start + ep.offset(c["take"], role), vf, False

    def broll_frames(self, c, n):
        left, prev, used = n, None, 0.0
        segs = c["broll"]
        for j, seg in enumerate(segs):
            dur = seg["dur"] if seg.get("dur") is not None and j < len(segs) - 1 else (c["end"] - c["start"]) - used
            st = seg["at"] if seg.get("at") is not None else c["start"] + used
            m = left if j == len(segs) - 1 else int(round(dur * FPS))
            used += dur
            path, ft, vf, still_img = self.broll_source(c, seg, st, m / FPS + 0.2)
            self.live = seg.get("at") is not None
            if still_img:
                gen = video_frames_image(path, vf, m)
            else:
                gen = video_frames(path, ft, m / FPS + 0.2, vf, (CW, CH), FPS)
            last = None
            for q in range(m):
                last = next(gen, last)
                out = last
                if prev is not None and q < 8 and last is not None:
                    a = (q + 1) / 9
                    out = (last.astype(np.float32) * a + prev.astype(np.float32) * (1 - a)).astype(np.uint8)
                yield out
            prev = last
            left -= m

    # ---------- render ----------
    def render(self, out: Path, stills: list[float] | None = None) -> Path:
        ep = self.ep
        silent = ep.edit / "render" / f"reel-{self.P['id']}-silent.mp4"
        enc = None
        if not stills:
            silent.parent.mkdir(parents=True, exist_ok=True)
            enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{SX}x{SY}", "-r", str(FPS), "-i", "-",
                                    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
            if self.sting:
                for fr in video_frames(self.sting, 0, self.ST, f"scale={SX}:{SY}", (SX, SY), FPS):
                    enc.stdin.write(fr.tobytes())
        want = sorted(stills) if stills else None
        for k, c in enumerate(self.clips):
            n = int(round((c["end"] - c["start"]) * FPS))
            if want and not any(c["t0"] <= s < c["t1"] for s in want):
                continue
            faces = self.face_frames(c)
            brolls = self.broll_frames(c, n)
            lf = lb = None
            for i in range(n):
                lf = next(faces, lf)
                lb = next(brolls, lb)
                t = c["t0"] + i / FPS
                if want:
                    for s in want:
                        if abs(s - t) < 0.5 / FPS:
                            self.draw(t, lf, lb, k).save(ep.edit / "render" / f"reel-{self.P['id']}-{s:.1f}.jpg", quality=90)
                else:
                    enc.stdin.write(self.draw(t, lf, lb, k).tobytes())
        if want:
            for s in want:
                if s >= self.SPEECH:
                    self.draw(s, None, None, None).save(ep.edit / "render" / f"reel-{self.P['id']}-{s:.1f}.jpg", quality=90)
            print(f"stills in {ep.edit / 'render'}")
            return ep.edit / "render"
        for i in range(int(round(END_D * FPS))):
            enc.stdin.write(self.draw(self.SPEECH + i / FPS, None, None, None).tobytes())
        enc.stdin.close()
        if enc.wait():
            raise SystemExit("Reel video encode failed")
        self.mix_audio(silent, out)
        silent.unlink()
        return out

    def mix_audio(self, silent: Path, out: Path):
        """Approved voice chain, light music bed (0.10, lifting to 0.40 on the end card), sting audio at -2 dB."""
        from .audio import RATE, segment_voice, fade
        ep = self.ep
        voice = np.concatenate([fade(segment_voice(ep, c["take"], c["start"], c["end"]), 0.04, 0.06) for c in self.clips])
        raw = ff.write_wav(ep.edit / "render" / f"reel-{self.P['id']}-voice.wav", voice, RATE)
        args = ["-i", silent, "-i", raw]
        fc = [f"[1:a]{CHAINS['present']},adelay={int(self.ST * 1000)}:all=1,apad=whole_dur={self.TOTAL:.3f}[vo]"]
        mixin = "[vo]"
        music = ep.get("music_bed")
        if music:
            args += ["-stream_loop", "-1", "-i", ep.asset(music)]
            S = self.SPEECH
            fc.append(f"[2:a]aresample={RATE},aformat=channel_layouts=mono,atrim=0:{self.TOTAL:.3f},asetpts=PTS-STARTPTS,"
                      f"volume='if(lt(t,{S - 0.3:.2f}),0.1,0.1+0.3*clip((t-{S - 0.3:.2f})/0.5,0,1))':eval=frame,"
                      f"afade=t=out:st={self.TOTAL - 1.0:.2f}:d=1.0,afade=t=in:st={self.ST:.2f}:d=1.0,volume='if(lt(t,{self.ST:.2f}),0,1)':eval=frame[mu]")
            mixin += "[mu]"
        if self.sting:
            si = len(args) // 2 if not music else 3
            args += ["-i", self.sting]
            fc.append(f"[{si}:a]aresample={RATE},aformat=channel_layouts=mono,volume=-2dB,apad=whole_dur={self.TOTAL:.3f}[sa]")
            mixin += "[sa]"
        fc.append(f"{mixin}amix=inputs={mixin.count('[')}:normalize=0:duration=first,alimiter=limit=0.84:attack=1:release=30:level=false[a]")
        ff.run([*args, "-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                "-movflags", "+faststart", "-t", f"{self.TOTAL:.3f}", out])


def video_frames_image(path: Path, vf: str, n: int):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(path), "-vf", vf, "-frames:v", str(n),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    nb = CW * CH * 3
    last = None
    for _ in range(n):
        b = p.stdout.read(nb)
        if len(b) == nb:
            last = np.frombuffer(b, np.uint8).reshape(CH, CW, 3)
        yield last if last is not None else np.zeros((CH, CW, 3), np.uint8)
    p.kill()
    p.wait()


def run(episode_id: str, only: str | None = None, stills: list[float] | None = None) -> list[Path]:
    ep = Episode(episode_id)
    plans = ep.read("reels.json", hint="Pick the reel moments first (WORKFLOW.md stage 10, prompts/reels-pick.md).")["reels"]
    outs = []
    for plan in plans:
        if only and plan["id"] != only:
            continue
        r = Reel(ep, plan)
        dest = ep.deliver_dir("reels")
        out = dest / plan.get("out", f"{ep.tag}-Reel-{plan['id']}.mp4")
        if out.exists() and not stills:
            older = dest / "_older versions"
            older.mkdir(exist_ok=True)
            out.rename(older / out.name)
        res = r.render(out, stills)
        print(f"{plan['id']}: {res} ({r.TOTAL:.1f} s)")
        outs.append(res)
    return outs
