"""YouTube subtitles (.srt) for a timeline, from the word-timed transcripts (Ep01 rules).

A cue ends at about 38 characters, at a sentence end once it has more than 12 characters, at a
pause over 0.7 s, or when the speaker changes. Each cue runs 0.2 s past its last word and never
overlaps the next one. Name fixes from episode.json "names" are applied.
"""

from pathlib import Path

from .episode import Episode
from .timeline import Block


def cues(ep: Episode, blocks: list[Block]) -> list[tuple[float, float, str]]:
    fps = ep.fps
    out = []
    for b in blocks:
        if b.kind != "section":
            continue
        for take, s0, s1, f in b.segments:
            base = b.start / fps + f / fps
            ws = [w for w in ep.words(take) if s0 <= w["start"] and w["end"] <= s1 + 0.05]
            chunk = []
            for i, w in enumerate(ws):
                chunk.append(w)
                text = " ".join(x["word"] for x in chunk).strip()
                nxt = ws[i + 1] if i + 1 < len(ws) else None
                if (len(text) > 38 or nxt is None or (text[-1] in ".?!" and len(text) > 12)
                        or nxt["start"] - w["end"] > 0.7 or nxt["speaker"] != w["speaker"]):
                    out.append((base + chunk[0]["start"] - s0, base + w["end"] - s0 + 0.2, text))
                    chunk = []
    for i in range(len(out) - 1):
        if out[i][1] > out[i + 1][0]:
            out[i] = (out[i][0], out[i + 1][0] - 0.01, out[i][2])
    return out


def fmt(x: float) -> str:
    x = max(0.0, x)
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write(ep: Episode, blocks: list[Block], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{i + 1}\n{fmt(a)} --> {fmt(b)}\n{x}\n\n" for i, (a, b, x) in enumerate(cues(ep, blocks))))
    return path
