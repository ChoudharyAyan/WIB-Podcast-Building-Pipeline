"""`wib review`: what the raw footage is like before cutting (levels, pace, framing).
`wib frame`: stills from the camera with a pixel grid, to set framing.face / framing.close in episode.json."""

from PIL import ImageDraw

from . import ff, speakers
from .episode import Episode
from .graphics import font, still


def run(episode_id: str) -> str:
    ep = Episode(episode_id)
    lines = [f"# Raw review: {ep.tag}", ""]
    for take in ep.take_ids():
        ref = ep.reference_file(take)
        lines.append(f"## {take}: {ref.name}, {ff.duration(ref) / 60:.1f} min")
        for p, name in ep.takes[take]["mics"].items():
            f = ep.raw / name
            loud = ff.loudness(f)
            lines.append(f"- {ep.people.get(p, {}).get('name', p)} mic ({name}): {loud['lufs']} LUFS, peak {loud['true_peak']} dBFS"
                         + ("  ← clipping, ask for a re-record of this part if it is a key moment" if (loud["true_peak"] or -99) > -0.5 else ""))
        tr = ep.read(f"transcripts/{take}.json", required=False)
        if tr:
            ws = ep.words(take)
            for p in ep.take_people(take):
                mine = [w for w in ws if w["speaker"] == p]
                talk = sum(w["end"] - w["start"] for w in mine)
                if talk > 10:
                    lines.append(f"- {ep.people.get(p, {}).get('name', p)}: {len(mine)} words, {len(mine) / (talk / 60):.0f} wpm while talking "
                                 f"(target 140-160), {talk / 60:.1f} min of speech")
        if ep.conversation and ep.sync.get(take):
            runs = speakers.activity(ep, take, 0.0, ff.duration(ref))
            share = {p: 0.0 for p in ep.take_people(take)}
            for a, b, p in runs:
                if p in share:
                    share[p] += b - a
            tot = sum(share.values()) or 1.0
            share = {p: v / tot for p, v in share.items()}
            lines.append("- Talk share: " + ", ".join(f"{ep.people.get(p, {}).get('name', p)} {v * 100:.0f}%" for p, v in share.items()))
        lines.append("")
    text = "\n".join(lines)
    (ep.edit / "review.md").write_text(text + "\n")
    print(text)
    return text


def frame(episode_id: str, take: str | None = None, at: float = 60.0) -> list:
    """Camera stills with a 100 px grid so face/close boxes can be read off in camera pixels."""
    ep = Episode(episode_id)
    out = []
    for t in [take] if take else ep.take_ids():
        cam = ep.file(t, "camera") or ep.reference_file(t)
        W, H = ff.video_size(cam)
        im = still(cam, at, f"scale={W}:{H}", (W, H))
        d = ImageDraw.Draw(im)
        f = font("JBMono.ttf", max(14, W // 120), 600)
        step = 100 if W <= 2000 else 200
        for x in range(0, W, step):
            d.line((x, 0, x, H), fill=(212, 255, 58, 110), width=1)
            d.text((x + 4, 4), str(x), font=f, fill=(212, 255, 58))
        for y in range(0, H, step):
            d.line((0, y, W, y), fill=(212, 255, 58, 110), width=1)
            d.text((4, y + 4), str(y), font=f, fill=(212, 255, 58))
        p = ep.edit / "frames" / f"{t}-camera-{at:.0f}s.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        im.convert("RGB").save(p, quality=90)
        print(f"{p}  ({W}x{H})")
        out.append(p)
    print('Set in episode.json: "framing": {"face": {"<person>": [cx, cy, size]}, "close": {"<person>": [x, y, w, h]}}  (camera pixels, close is 16:9)')
    return out
