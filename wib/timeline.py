"""The edit as data: cutlist.json -> blocks of shots on a frame-exact output clock.

A block is the sting, a section card, or a section (consecutive cut-list segments with the same
section id). Blocks join with dissolves; shots inside a section are hard cuts. Every duration is a
whole number of frames, so picture and sound line up to the last frame however long the episode is.

Shot layouts:
  screen          the screen recording framed on the WIB canvas (solo: OBS bubble baked in;
                  conversation: the active speaker's face added as a bubble)
  screen-only     the framed screen with no bubble
  screen2         a second screen recording of the take (e.g. the guest's own Mac), framed the same
                  way with the speaker bubble; screen2-only without it
  wide            the camera's wide shot
  close:<person>  a close-up crop of one person from the camera
  auto            (conversation, in the cut list) wide and close-ups switched by who is talking
"""

from dataclasses import dataclass, field

from . import speakers
from .episode import Episode

MIN_SHOT = 2.0       # seconds; shorter speaker runs don't get their own camera shot
MAX_CLOSE = 14.0     # a close-up longer than this gets a wide shot in the middle
WIDE_BREAK = 3.0
OPEN_WIDE = 3.0      # every conversation section opens on the wide shot


@dataclass
class Shot:
    take: str
    src: float           # reference-clock time of the first frame
    frames: int
    layout: str
    person: str | None = None    # bubble or close-up person
    zoom: dict | None = None     # {"t0", "t1" (seconds from shot start), "cx", "cy", "max"}


@dataclass
class Block:
    kind: str            # sting, card, section
    ref: str             # section id (card/section) or file name
    shots: list = field(default_factory=list)
    frames: int = 0
    start: int = 0       # output frame where the block starts
    join: int = 0        # dissolve frames into this block from the previous one
    segments: list = field(default_factory=list)  # section blocks: [(take, start, end, out_frame)]
    skip: int = 0        # sting/card: frames of the file skipped at the start (test renders)


def _frames(sec: float, fps: int) -> int:
    return int(round(sec * fps))


def _speaker_runs(ep: Episode, take: str, a: float, b: float) -> list[list]:
    runs = [[x, y, p if p in ep.people else None] for x, y, p in speakers.activity(ep, take, a, b)]
    merged = []
    for r in runs:  # short runs join the previous shot
        if merged and (r[1] - r[0] < MIN_SHOT or r[2] == merged[-1][2]):
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    if len(merged) > 1 and merged[0][1] - merged[0][0] < MIN_SHOT:
        merged[1][0] = merged[0][0]
        merged.pop(0)
    return merged


def conversation_shots(ep: Episode, take: str, a: float, b: float, layout: str, opens_section: bool) -> list[tuple[float, float, str, str | None]]:
    """[(start, end, layout, person)] for one cut-list segment."""
    closes = ep.get("framing", {}).get("close", {})
    if layout in ("screen", "screen-only", "screen2", "screen2-only"):
        if layout.endswith("-only"):
            return [(a, b, layout, None)]
        return [(x, y, layout, p if p in ep.people else ep.host) for x, y, p in _speaker_runs(ep, take, a, b)]
    if layout != "auto":
        p = layout.split(":", 1)[1] if layout.startswith("close:") else None
        return [(a, b, layout, p)]
    out = []
    for x, y, p in _speaker_runs(ep, take, a, b):
        lay = f"close:{p}" if p and p in closes else "wide"
        if lay != "wide" and y - x > MAX_CLOSE:
            m = (x + y) / 2
            out += [(x, m - WIDE_BREAK / 2, lay, p), (m - WIDE_BREAK / 2, m + WIDE_BREAK / 2, "wide", None), (m + WIDE_BREAK / 2, y, lay, p)]
        else:
            out.append((x, y, lay, p if lay != "wide" else None))
    if opens_section and out and out[0][2] != "wide" and b - a > OPEN_WIDE + MIN_SHOT:
        x, y, lay, p = out[0]
        cut = min(y, a + OPEN_WIDE) if y - a > OPEN_WIDE + MIN_SHOT else y
        out[0] = (a, cut, "wide", None)
        if cut < y:
            out.insert(1, (cut, y, lay, p))
    # neighbours with the same picture become one shot
    merged = []
    for s in out:
        if merged and merged[-1][2] == s[2] and merged[-1][3] == s[3]:
            merged[-1] = (merged[-1][0], s[1], s[2], s[3])
        else:
            merged.append(s)
    return merged


def _split_for_zooms(ep: Episode, take: str, a: float, b: float, zooms: list[dict]) -> list[tuple[float, float, dict | None]]:
    zs = sorted((z for z in zooms if z["take"] == take and a <= z["start"] and z["end"] <= b), key=lambda z: z["start"])
    out, cur = [], a
    for z in zs:
        if z["start"] > cur:
            out.append((cur, z["start"], None))
        out.append((z["start"], z["end"], z))
        cur = z["end"]
    if cur < b:
        out.append((cur, b, None))
    return out


def sections(ep: Episode) -> list[tuple[str, list[dict]]]:
    cl = ep.read("cutlist.json", hint=f"Run `uv run wib cutlist {ep.id}` first.")
    out = []
    for s in cl["segments"]:
        if not out or out[-1][0] != s["section"]:
            out.append((s["section"], []))
        out[-1][1].append(s)
    return out


def build(ep: Episode, kind: str) -> list[Block]:
    """kind: output1 (sting + sections, 0.5 s fades between sections) or
    output2 (sting + card before each carded section + sections, 0.4 s dissolves, gentle zooms)."""
    fps = ep.fps
    zooms = (ep.read("zooms.json", required=False) or {"zooms": []})["zooms"] if kind == "output2" else []
    zmax = float(ep["zoom_max"])
    blocks = [Block("sting", "intro-sting.mp4", frames=_frames(15.0, fps))]
    for sid, segs in sections(ep):
        sec = ep.section(sid)
        if kind == "output2" and sec.get("card"):
            blocks.append(Block("card", sid, frames=_frames(3.0, fps)))
        b = Block("section", sid)
        first = True
        for seg in segs:
            n_seg = _frames(seg["end"] - seg["start"], fps)
            seg_end = seg["start"] + n_seg / fps
            b.segments.append((seg["take"], seg["start"], seg_end, b.frames))
            for x, y, z in _split_for_zooms(ep, seg["take"], seg["start"], seg_end, zooms):
                if ep.conversation:
                    parts = conversation_shots(ep, seg["take"], x, y, seg.get("layout", "auto"), first)
                else:
                    parts = [(x, y, seg.get("layout", "screen"), None)]
                first = False
                for px, py, lay, person in parts:
                    done = b.frames - b.segments[-1][3]
                    n = _frames(py - seg["start"], fps) - done
                    if n <= 0:
                        continue
                    src = seg["start"] + done / fps
                    zz = None
                    if z and lay.startswith("screen"):
                        zz = {"t0": z["start"] - src, "t1": z["end"] - src, "cx": z["cx"], "cy": z["cy"],
                              "max": float(z.get("zoom", zmax)), "ramp": float(z.get("ramp", 2.0))}
                    b.shots.append(Shot(seg["take"], src, n, lay, person, zz))
                    b.frames += n
        blocks.append(b)
    # dissolves and positions
    t = 0
    for k, b in enumerate(blocks):
        if k:
            prev = blocks[k - 1]
            x = 0.5 if (kind == "output1" and prev.kind == "section" and b.kind == "section") else 0.4
            b.join = min(_frames(x, fps), prev.frames // 2, b.frames // 2)
            t -= b.join
        b.start = t
        t += b.frames
    return blocks


def total_frames(blocks: list[Block]) -> int:
    return blocks[-1].start + blocks[-1].frames


def describe(blocks: list[Block], fps: int) -> str:
    lines = []
    for b in blocks:
        layouts = {}
        for s in b.shots:
            layouts[s.layout] = layouts.get(s.layout, 0) + s.frames
        mix = ", ".join(f"{k} {v / fps:.0f}s" for k, v in layouts.items())
        lines.append(f"{b.start / fps:8.2f}s  {b.kind:<8} {b.ref:<14} {b.frames / fps:7.2f}s  {len(b.shots)} shots  {mix}")
    return "\n".join(lines)


def export_otio(ep: Episode, path) -> None:
    """The Output1 edit as an OpenTimelineIO timeline: File > Import > Timeline in DaVinci Resolve.
    One video track per source role (screen, camera) and the reference audio."""
    import opentimelineio as otio
    fps = ep.fps
    tl = otio.schema.Timeline(name=f"{ep.tag} Output1")
    roles = [r for r in ("screen", "screen2", "camera") if any(ep.file(t, r) for t in ep.take_ids())]
    tracks = {r: otio.schema.Track(name=r, kind=otio.schema.TrackKind.Video) for r in roles}
    audio = otio.schema.Track(name="A1", kind=otio.schema.TrackKind.Audio)
    for _sid, segs in sections(ep):
        for s in segs:
            dur = otio.opentime.RationalTime.from_seconds(s["end"] - s["start"], fps)
            for r, tr in list(tracks.items()) + [("ref", audio)]:
                f = ep.reference_file(s["take"]) if r == "ref" else ep.file(s["take"], r)
                if f is None:
                    tr.append(otio.schema.Gap(source_range=otio.opentime.TimeRange(duration=dur)))
                    continue
                off = 0.0 if r == "ref" else ep.offset(s["take"], r)
                tr.append(otio.schema.Clip(name=s["section"], media_reference=otio.schema.ExternalReference(target_url=f.resolve().as_uri()),
                                           source_range=otio.opentime.TimeRange(otio.opentime.RationalTime.from_seconds(s["start"] + off, fps), dur)))
    tl.tracks.extend(list(tracks.values()) + [audio])
    otio.adapters.write_to_file(tl, str(path))
