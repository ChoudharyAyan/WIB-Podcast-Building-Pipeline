"""Helpers the agent uses while planning cuts and reels: exact word-timed spans and pauses."""

import re

from .episode import Episode
from .transcribe import fmt_time


def _norm(x: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", "", x.lower()).split()


def phrase(episode_id: str, take: str, first: str, last: str | None = None, after: float = 0.0) -> tuple[float, float, str]:
    """Start of the first word of `first` to the end of the last word of `last` (searching from `after`)."""
    ep = Episode(episode_id)
    ws = [w for w in ep.words(take) if w["start"] >= after]
    toks = [(_norm(w["word"]) or [""])[0] for w in ws]

    def find(p, start=0):
        p = _norm(p)
        for i in range(start, len(toks) - len(p) + 1):
            if toks[i:i + len(p)] == p:
                return i
        raise SystemExit(f"Not found in {take}: {' '.join(p)!r}")
    i = find(first)
    j = find(last or first, i)
    j2 = j + len(_norm(last or first)) - 1
    text = " ".join(w["word"] for w in ws[i:j2 + 1])
    print(f"{ws[i]['start']:.2f} {ws[j2]['end']:.2f}  | {text}")
    return ws[i]["start"], ws[j2]["end"], text


def pauses(episode_id: str, take: str, min_gap: float = 1.5) -> list[tuple[float, float]]:
    ep = Episode(episode_id)
    ws = ep.words(take)
    out = [(a["end"], b["start"]) for a, b in zip(ws, ws[1:]) if b["start"] - a["end"] >= min_gap]
    for a, b in out:
        print(f"{fmt_time(a)}  {b - a:4.1f} s  ({a:.2f}–{b:.2f})")
    return out


def words(episode_id: str, take: str, a: float, b: float) -> None:
    ep = Episode(episode_id)
    for w in ep.words(take):
        if a <= w["start"] <= b:
            print(f"{w['start']:8.2f} {w['end']:8.2f}  {w['speaker']:>8}  {w['word']}")
