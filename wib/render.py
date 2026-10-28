"""Render a timeline's picture as small cached pieces, then join them without re-encoding.

Every shot body and every dissolve becomes its own piece (edit/render/pieces/<hash>.mp4), encoded
once at final quality. Re-running skips pieces that already exist, so a crashed or interrupted
render resumes where it stopped, and changing one shot re-renders only that shot. Pieces are
joined with the concat demuxer (stream copy) and the finished audio is muxed on.

Each piece reads only the few seconds it needs (seeked inputs), which keeps memory flat on the
MacBook Air (the Ep01 Output2 render ran out of memory as one giant filter graph).
"""

import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from . import BRAND, ff
from .episode import Episode
from .faces import face_source
from .graphics import hexc
from .timeline import Block, Shot

INK_HEX = "0E0E10"
WATERMARK_ALPHA = 0.85


class Graph:
    def __init__(self):
        self.inputs: list[list[str]] = []
        self.filters: list[str] = []
        self.n = 0

    def input(self, path, pre=()) -> int:
        self.inputs.append([*map(str, pre), "-i", str(path)])
        return len(self.inputs) - 1

    def image(self, path) -> int:
        return self.input(path, ("-loop", "1", "-framerate", "30"))

    def label(self, base="v") -> str:
        self.n += 1
        return f"{base}{self.n}"

    def add(self, f: str):
        self.filters.append(f)


# ---------- geometry ----------
def screen_box(ep: Episode, sw: int, sh: int) -> tuple[int, int, int, int]:
    """Where the screen recording sits on the canvas: Ep01's frame (3216x2010 at 312,30 on 4K) for 16:10,
    the same 2010-px-high content area for any other aspect, leaving the footer band for the wordmark."""
    s = ep.scale
    ch = int(round(2010 * s / 2)) * 2
    cw = int(round(ch * sw / sh / 2)) * 2
    if cw > ep.W:
        cw = ep.W
        ch = int(round(cw * sh / sw / 2)) * 2
    return cw, ch, (ep.W - cw) // 2, int(round(30 * s))


def _assets(ep: Episode) -> Path:
    d = ep.edit / "render" / "assets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ring_png(ep: Episode, size: int, colour: str, rw: int) -> tuple[Path, Path]:
    """A coloured disc (the ring) and a circular alpha mask for a face bubble."""
    d = _assets(ep)
    ring, mask = d / f"ring-{colour.lstrip('#')}-{size}-{rw}.png", d / f"mask-{size}.png"
    if not ring.exists():
        im = Image.new("RGBA", (size + 2 * rw, size + 2 * rw))
        ImageDraw.Draw(im).ellipse((0, 0, im.width - 1, im.height - 1), fill=hexc(colour) + (255,))
        im.save(ring)
    if not mask.exists():
        m = Image.new("RGB", (size, size), (0, 0, 0))
        ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=(255, 255, 255))
        m.save(mask)
    return ring, mask


def wordmark_overlay(g: Graph, ep: Episode, inp: str, x_right: int, y_center: int, alpha: float = 1.0) -> str:
    wm = g.image(BRAND / "assets" / "wib-wordmark-paper.png")
    w = int(round(360 * ep.scale / 2)) * 2
    a, out = g.label("wm"), g.label()
    fx = f",colorchannelmixer=aa={alpha}" if alpha < 1 else ""
    g.add(f"[{wm}:v]scale={w}:-1,format=rgba{fx}[{a}]")
    g.add(f"[{inp}][{a}]overlay=x={x_right}-w:y={y_center}-h/2:shortest=1[{out}]")
    return out


# ---------- one shot (or part of one) to a canvas-sized stream ----------
def shot_stream(g: Graph, ep: Episode, sh: Shot, a: int, n: int) -> str:
    """Frames a..a+n of a shot, as a labelled stream of exactly n frames at canvas size."""
    fps, W, H = ep.fps, ep.W, ep.H
    t = sh.src + a / fps
    dur = n / fps + 0.25
    out = g.label()
    lay = sh.layout

    if lay.startswith("screen") or lay.startswith("image"):
        if lay.startswith("image"):
            path = ep.asset(lay.split(":", 1)[1])
            i = g.input(path, ("-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}"))
            sw, shh = ff.video_size(path)
        else:
            path = ep.file(sh.take, "screen")
            i = g.input(path, ("-ss", f"{t + ep.offset(sh.take, 'screen'):.4f}", "-t", f"{dur:.3f}", "-an"))
            sw, shh = ff.video_size(path)
        cw, ch, X, Y = screen_box(ep, sw, shh)
        src = g.label()
        g.add(f"[{i}:v]setpts=PTS-STARTPTS,fps={fps},trim=end_frame={n},format=yuv420p[{src}]")
        baked = lay.startswith("screen") and not ep.conversation  # OBS bubble is in the picture
        if sh.zoom:
            src = zoom_stream(g, ep, src, sh.zoom, a / fps, sw, shh, baked)
        framed = g.label()
        g.add(f"[{src}]scale={cw}:{ch}:flags=lanczos,pad={W}:{H}:{X}:{Y}:color=0x{INK_HEX},setsar=1[{framed}]")
        cur = framed
        if lay == "screen" and ep.conversation:
            cur = bubble_overlay(g, ep, cur, sh, t, n, X, Y, ch)
        foot_y = Y + ch + (H - (Y + ch)) // 2
        cur = wordmark_overlay(g, ep, cur, X + cw, foot_y)
        g.add(f"[{cur}]fps={fps},format=yuv420p,tpad=stop_mode=clone:stop=3,trim=end_frame={n},setpts=PTS-STARTPTS[{out}]")
        return out

    if lay == "wide" or lay.startswith("close:"):
        cam = ep.file(sh.take, "camera")
        i = g.input(cam, ("-ss", f"{t + ep.offset(sh.take, 'camera'):.4f}", "-t", f"{dur:.3f}", "-an"))
        crop = ""
        if lay.startswith("close:"):
            x, y, w, h = ep["framing"]["close"][lay.split(":", 1)[1]]
            crop = f"crop={int(w)}:{int(h)}:{int(x)}:{int(y)},"
        elif ep.get("framing", {}).get("wide"):
            x, y, w, h = ep["framing"]["wide"]
            crop = f"crop={int(w)}:{int(h)}:{int(x)}:{int(y)},"
        base = g.label()
        g.add(f"[{i}:v]setpts=PTS-STARTPTS,fps={fps},trim=end_frame={n},{crop}"
              f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{ep['camera_grade']},setsar=1,format=yuv420p[{base}]")
        m = int(round(60 * ep.scale))
        cur = wordmark_overlay(g, ep, base, W - m, H - m - int(round(30 * ep.scale)), WATERMARK_ALPHA)
        g.add(f"[{cur}]format=yuv420p,tpad=stop_mode=clone:stop=3,trim=end_frame={n},setpts=PTS-STARTPTS[{out}]")
        return out

    raise SystemExit(f"Unknown layout {lay!r}")


def bubble_overlay(g: Graph, ep: Episode, inp: str, sh: Shot, t: float, n: int, X: int, Y: int, ch: int) -> str:
    """The active speaker's face in a ring, bottom-left of the framed screen (conversation)."""
    s = ep.scale
    size = int(round(550 * s / 2)) * 2
    rw = max(2, int(round(14 * s)))
    src, ft, crop = face_source(ep, sh.take, sh.person, t)
    ring, mask = ring_png(ep, size, ep.person_colour(sh.person or ep.host), rw)
    fi = g.input(src, ("-ss", f"{ft:.4f}", "-t", f"{n / ep.fps + 0.25:.3f}", "-an"))
    ri, mi = g.image(ring), g.image(mask)
    f, fm, m, out1, out2 = g.label("f"), g.label("fm"), g.label("m"), g.label(), g.label()
    x, y = X + int(round(70 * s)), Y + ch - size - int(round(70 * s))
    g.add(f"[{fi}:v]setpts=PTS-STARTPTS,fps={ep.fps},trim=end_frame={n},{crop},scale={size}:{size}:flags=lanczos,{ep['camera_grade']},format=rgba[{f}]")
    g.add(f"[{mi}:v]format=gray[{m}];[{f}][{m}]alphamerge[{fm}]")
    g.add(f"[{inp}][{ri}:v]overlay={x - rw}:{y - rw}:shortest=1[{out1}];[{out1}][{fm}]overlay={x}:{y}:shortest=1[{out2}]")
    return out2


def zoom_stream(g: Graph, ep: Episode, src: str, z: dict, off: float, sw: int, sh: int, baked_bubble: bool) -> str:
    """Ep01's gentle zoom: smoothstep in over `ramp` s, hold, smoothstep out, never past `max`.
    The picture is upscaled 2x first so the zoom never enlarges past source resolution. zoompan can
    drop the last frame, so the stream is padded by a cloned frame or two and trimmed after. When the OBS
    bubble is baked in, it is lifted out, the screen zooms underneath, and the bubble goes back on
    unchanged, so the face stays round and still."""
    R, ZM = z["ramp"], z["max"]
    t0, t1 = z["t0"] - off, z["t1"] - off
    tt = "it"
    s_in = f"clip(({tt}-({t0:.3f}))/{R},0,1)"
    s_out = f"clip(({tt}-({t1 - R:.3f}))/{R},0,1)"
    zexpr = f"1+{ZM - 1:.4f}*({s_in}*{s_in}*(3-2*{s_in})-{s_out}*{s_out}*(3-2*{s_out}))"
    cx, cy = z["cx"], z["cy"]
    main, out = g.label("zm"), g.label("z")
    pre = ""
    b = ep["bubble"]
    if baked_bubble:
        bub, mask, bm = g.label("bb"), g.label("bk"), g.label("bm")
        mi = g.image(BRAND / "assets" / "bubble-mask-440.png")
        g.add(f"[{src}]split[{main}][{bub}]")
        g.add(f"[{bub}]crop={b['size']}:{b['size']}:{b['x']}:{b['y']},format=rgba[{bub}c];[{mi}:v]scale={b['size']}:{b['size']},format=rgba,alphaextract[{mask}];[{bub}c][{mask}]alphamerge[{bm}]")
        pre = f"delogo=x={b['x'] - 6}:y={b['y'] - 6}:w={b['size'] + 12}:h={b['size'] + 12},"
        src_main = main
    else:
        src_main = src
    zz = g.label("zz")
    g.add(f"[{src_main}]{pre}scale={2 * sw}:{2 * sh}:flags=lanczos,zoompan=z='{zexpr}':x='max(0,min({cx * 2}-{sw}/zoom,{2 * sw}-{2 * sw}/zoom))'"
          f":y='max(0,min({cy * 2}-{sh}/zoom,{2 * sh}-{2 * sh}/zoom))':d=1:s={sw}x{sh}:fps={ep.fps},tpad=stop_mode=clone:stop=3[{zz}]")
    if baked_bubble:
        g.add(f"[{zz}][{bm}]overlay={b['x']}:{b['y']}:shortest=1,format=yuv420p[{out}]")
    else:
        g.add(f"[{zz}]format=yuv420p[{out}]")
    return out


def file_stream(g: Graph, ep: Episode, path: Path, a: int, n: int) -> str:
    i = g.input(path, ("-ss", f"{a / ep.fps:.4f}", "-t", f"{n / ep.fps + 0.25:.3f}", "-an"))
    out = g.label()
    g.add(f"[{i}:v]setpts=PTS-STARTPTS,fps={ep.fps},trim=end_frame={n},scale={ep.W}:{ep.H}:flags=lanczos,setsar=1,format=yuv420p,setpts=PTS-STARTPTS[{out}]")
    return out


# ---------- blocks to pieces ----------
def block_spans(ep: Episode, b: Block, f0: int, f1: int) -> list[tuple]:
    """Parts of a block between its own frames f0 and f1: [(shot or path, a, n)]."""
    if b.kind == "sting":
        return [(ep.edit / "assets" / "intro-sting.mp4", f0 + b.skip, f1 - f0)]
    if b.kind == "card":
        return [(ep.edit / "cards" / f"{b.ref}.mp4", f0 + b.skip, f1 - f0)]
    out, pos = [], 0
    for sh in b.shots:
        a, z = max(f0, pos), min(f1, pos + sh.frames)
        if z > a:
            out.append((sh, a - pos, z - a))
        pos += sh.frames
    return out


def spans_stream(g: Graph, ep: Episode, spans) -> str:
    labels = [shot_stream(g, ep, s, a, n) if isinstance(s, Shot) else file_stream(g, ep, s, a, n) for s, a, n in spans]
    if len(labels) == 1:
        return labels[0]
    out = g.label()
    g.add("".join(f"[{l}]" for l in labels) + f"concat=n={len(labels)}:v=1:a=0[{out}]")
    return out


def piece_specs(ep: Episode, blocks: list[Block]) -> list[dict]:
    specs = []
    for k, b in enumerate(blocks):
        nxt = blocks[k + 1] if k + 1 < len(blocks) else None
        lead = b.join
        tail = nxt.join if nxt else 0
        # body, one piece per shot (cards and the sting are one piece)
        body = block_spans(ep, b, lead, b.frames - tail)
        for sp in body:
            specs.append({"kind": "body", "spans": [sp]})
        if nxt and tail:
            specs.append({"kind": "xfade", "a": block_spans(ep, b, b.frames - tail, b.frames),
                          "b": block_spans(ep, nxt, 0, tail), "frames": tail})
    return specs


def _key(ep: Episode, spec: dict, bitrate: str) -> str:
    def enc(sp):
        s, a, n = sp
        if isinstance(s, Shot):
            f = ep.file(s.take, "screen") or ep.file(s.take, "camera")
            return [s.take, round(s.src, 4), s.frames, s.layout, s.person, s.zoom, a, n, str(f), f.stat().st_mtime if f else 0]
        return [str(s), s.stat().st_mtime if s.exists() else 0, a, n]
    blob = {"canvas": ep["canvas"], "fps": ep.fps, "grade": ep["camera_grade"], "framing": ep.get("framing"), "bubble": ep["bubble"],
            "codec": ff.video_codec(bitrate), "spec": {k: ([enc(x) for x in v] if isinstance(v, list) else v)
                                                                             for k, v in spec.items()}}
    return hashlib.sha1(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()[:16]


def render_piece(ep: Episode, spec: dict, out: Path, bitrate: str):
    g = Graph()
    if spec["kind"] == "body":
        final = spans_stream(g, ep, spec["spans"])
        n = spec["spans"][0][2]
    else:
        a, b = spans_stream(g, ep, spec["a"]), spans_stream(g, ep, spec["b"])
        n = spec["frames"]
        final = g.label()
        g.add(f"[{a}]settb=AVTB[{a}t];[{b}]settb=AVTB[{b}t];[{a}t][{b}t]xfade=transition=fade:duration={n / ep.fps:.4f}:offset=0,"
              f"trim=end_frame={n},setpts=PTS-STARTPTS[{final}]")
    graph_file = out.with_suffix(".filter.txt")
    graph_file.write_text(";\n".join(g.filters))
    tmp = out.with_suffix(".part.mp4")
    cmd = [ff.require("ffmpeg"), "-hide_banner", "-v", "error", "-y"]
    for i in g.inputs:
        cmd += i
    cmd += ["-filter_complex_script", str(graph_file), "-map", f"[{final}]", "-frames:v", str(n), "-r", str(ep.fps),
            *ff.video_codec(bitrate), "-video_track_timescale", "15360", "-an", "-f", "mp4", str(tmp)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit(f"Piece failed ({out.name}):\n{proc.stderr[-3000:]}\nFilter: {graph_file}")
    got = ff.probe(tmp)
    frames = next(int(s.get("nb_frames", 0)) for s in got["streams"] if s["codec_type"] == "video")
    if frames != n:
        raise SystemExit(f"Piece {out.name} has {frames} frames, expected {n}. Filter: {graph_file}")
    tmp.rename(out)
    graph_file.unlink()


def render_video(ep: Episode, blocks: list[Block], name: str, bitrate: str, progress=print) -> Path:
    """All pieces, then one stream-copied video file. Returns the silent video path."""
    pdir = ep.edit / "render" / "pieces"
    pdir.mkdir(parents=True, exist_ok=True)
    specs = piece_specs(ep, blocks)
    paths = []
    for k, spec in enumerate(specs):
        p = pdir / f"{_key(ep, spec, bitrate)}.mp4"
        if not p.exists():
            render_piece(ep, spec, p, bitrate)
        paths.append(p)
        progress(f"piece {k + 1}/{len(specs)}")
    lst = ep.edit / "render" / f"{name}-pieces.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))
    silent = ep.edit / "render" / f"{name}-video.mp4"
    ff.run(["-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", "-an", silent])
    return silent


def mux(video: Path, audio: Path, out: Path, frames: int, fps: int) -> Path:
    tmp = out.with_suffix(".part.mp4")
    ff.run(["-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", 48000,
            "-t", f"{frames / fps:.4f}", "-movflags", "+faststart", tmp])
    tmp.rename(out)
    return out
