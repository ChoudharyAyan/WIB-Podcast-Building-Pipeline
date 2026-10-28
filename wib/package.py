"""`wib package`: the delivery folders, ready to post, plus small previews for the shared folder.

  Output1 - without effects/   master + .otio for Resolve
  Output2 - with effects long form/   YouTube upload + .srt
  YouTube/   thumbnail, title, description with chapters
  Instagram videos/   reels + covers + captions.txt
Previews (under 20 MB each) go to edit/previews/ to share for a quick look.
"""

from pathlib import Path

from . import ff, timeline
from .episode import Episode

PREVIEW_MB = 19


def stamp(s: int) -> str:
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def chapters(ep: Episode) -> list[str]:
    """YouTube chapter lines from the Output2 timeline: 0:00 Intro, then each section (at its card when it has one)."""
    blocks = timeline.build(ep, "output2")
    out = ["0:00 Intro"]
    for k, b in enumerate(blocks):
        if b.kind != "section":
            continue
        start = blocks[k - 1].start if k and blocks[k - 1].kind == "card" else b.start
        out.append(f"{stamp(int(start / ep.fps))} {ep.section(b.ref).get('title', b.ref)}")
    return out


def preview(src: Path, dst: Path) -> Path:
    dur = max(1.0, ff.duration(src))
    kbps = max(200, int(PREVIEW_MB * 8192 / dur) - 96)
    w = 1280 if ff.video_size(src)[0] > ff.video_size(src)[1] else 540
    ff.run(["-i", src, "-vf", f"scale={w}:-2", "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{kbps}k",
            "-maxrate", f"{kbps}k", "-bufsize", f"{2 * kbps}k", "-c:a", "aac", "-b:a", "96k", dst])
    return dst


def run(episode_id: str, previews: bool = True) -> Path:
    ep = Episode(episode_id)
    yt = ep.deliver_dir("youtube")
    meta = ep.get("youtube", {})
    desc = [meta.get("description", ep.get("title", "")), "", *chapters(ep), "", *meta.get("links", [])]
    (yt / "title.txt").write_text(meta.get("title", ep.get("title", "")) + "\n")
    (yt / "description.txt").write_text("\n".join(desc).strip() + "\n")
    reels = ep.read("reels.json", required=False) or {"reels": []}
    cap = [f"{r.get('out', r['id'])}\n{r.get('caption', r.get('title', ''))}\n" for r in reels["reels"]]
    (ep.deliver_dir("reels") / "captions.txt").write_text("\n".join(cap))
    if previews:
        pv = ep.edit / "previews"
        pv.mkdir(exist_ok=True)
        files = [ep.edit / f"{ep.tag}-Output1.mp4", ep.edit / f"{ep.tag}-Output2.mp4", *sorted(ep.deliver_dir("reels").glob("*.mp4"))]
        for f in files:
            if f.exists():
                print(preview(f, pv / f"{f.stem}-preview.mp4"))
    print(f"Delivery folder: {ep.delivery}")
    for p in sorted(ep.delivery.rglob("*")):
        if p.is_file() and "_older versions" not in p.parts:
            print(f"  {p.relative_to(ep.delivery)}  ({p.stat().st_size / 1e6:.1f} MB)")
    return ep.delivery
