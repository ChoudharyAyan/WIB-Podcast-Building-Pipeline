"""Stages 8 and 9: Output1 (the clean master) and Output2 (YouTube long form with effects).

Output1: sting, then every section, 0.5 s crossfades between sections, clean voice at -14 LUFS,
         WIB wordmark on every frame. Also writes the .otio timeline for DaVinci Resolve.
Output2: Output1's edit unchanged, plus a card before each carded section, gentle zooms from
         edit/zooms.json, the music bed and the "present" voice chain (~-11 LUFS), and the .srt.
         No burned-in captions.
"""

import json
import shutil
import sys
import time

from . import audio, ff, subtitles, timeline
from .episode import Episode
from .render import mux, render_video

SPEC = {
    "output1": {"chain": "clean", "music": False, "bitrate": "30M"},
    "output2": {"chain": "present", "music": True, "bitrate": "40M"},
}


def _check_inputs(ep: Episode, kind: str, blocks):
    need = [ep.edit / "assets" / "intro-sting.mp4"]
    need += [ep.edit / "cards" / f"{b.ref}.mp4" for b in blocks if b.kind == "card"]
    missing = [p for p in need if not p.exists()]
    if missing:
        raise SystemExit("Missing: " + ", ".join(str(p.relative_to(ep.dir)) for p in missing) +
                         f". Run `uv run wib sting {ep.id}` and `uv run wib cards {ep.id}` first.")


def run(episode_id: str, kind: str, test: float | None = None, plan_only: bool = False) -> dict:
    ep = Episode(episode_id)
    spec = SPEC[kind]
    blocks = timeline.build(ep, kind)
    print(timeline.describe(blocks, ep.fps))
    total = timeline.total_frames(blocks)
    print(f"total {total / ep.fps:.2f} s ({total} frames)")
    (ep.edit / "render").mkdir(parents=True, exist_ok=True)
    if plan_only:
        return {"frames": total}
    _check_inputs(ep, kind, blocks)
    if test is not None:  # render ~20 s starting at `test` seconds of the output, to check a spot first
        blocks = _slice(blocks, int(test * ep.fps), int(20 * ep.fps), ep.fps)
        total = timeline.total_frames(blocks)
    music = ep.asset(ep["music_bed"]) if spec["music"] and ep.get("music_bed") else None
    if spec["music"] and not music:
        print("No music_bed in episode.json: rendering without music.", file=sys.stderr)
    t0 = time.time()
    wav = audio.build(ep, blocks, kind, spec["chain"], music)
    video = render_video(ep, blocks, kind, ep.get(f"{kind}_bitrate", spec["bitrate"]),
                         progress=lambda m: print(f"\r{m}", end="", flush=True))
    print()
    name = f"{ep.tag}-{'Output1' if kind == 'output1' else 'Output2'}{'-test' if test is not None else ''}.mp4"
    out = mux(video, wav, ep.edit / name, total, ep.fps)
    result = {"file": str(out), "seconds": round(total / ep.fps, 2), "render_minutes": round((time.time() - t0) / 60, 1)}
    if test is None:
        dest = ep.deliver_dir(kind)
        if kind == "output1":
            timeline.export_otio(ep, dest / f"{ep.tag}-Output1-timeline.otio")
        else:
            srt = subtitles.write(ep, timeline.build(ep, kind), dest / f"{ep.tag}-Output2-subtitles.srt")
            result["srt"] = str(srt)
        shutil.copy2(out, dest / out.name)
        result["delivered"] = str(dest / out.name)
    ep.write(f"render/{kind}{'-test' if test is not None else ''}-result.json", result)
    print(json.dumps(result, indent=1))
    return result


def _slice(blocks, start: int, length: int, fps: int):
    """Blocks cut down to the window [start, start+length) of the output, for test renders.
    Every block is trimmed to the window (the sting and cards by skipping into their files)."""
    import copy
    out = []
    for b in blocks:
        a, z = max(start, b.start), min(start + length, b.start + b.frames)
        if z <= a:
            continue
        nb = copy.deepcopy(b)
        lo, hi = a - b.start, z - b.start
        if b.kind != "section":
            nb.skip = b.skip + lo
        if b.kind == "section":
            shots, pos = [], 0
            for sh in b.shots:
                s0, s1 = max(lo, pos), min(hi, pos + sh.frames)
                if s1 > s0:
                    c = copy.deepcopy(sh)
                    d = (s0 - pos) / fps
                    c.src = sh.src + d
                    if c.zoom:
                        c.zoom = {**c.zoom, "t0": c.zoom["t0"] - d, "t1": c.zoom["t1"] - d}
                    c.frames = s1 - s0
                    shots.append(c)
                pos += sh.frames
            nb.shots = shots
            segs = []
            for take, s0, s1, f in b.segments:
                n = int(round((s1 - s0) * fps))
                x0, x1 = max(lo, f), min(hi, f + n)
                if x1 > x0:
                    segs.append((take, s0 + (x0 - f) / fps, s0 + (x1 - f) / fps, x0 - lo))
            nb.segments = segs
        nb.frames = hi - lo
        nb.join = b.join if lo == 0 and out else 0
        out.append(nb)
    t = 0
    for k, b in enumerate(out):
        b.join = min(b.join, out[k - 1].frames // 2, b.frames // 2) if k else 0
        t -= b.join
        b.start = t
        t += b.frames
    return out
