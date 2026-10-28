"""Who is speaking when, from each person's own mic. Used to label transcript words (dropping the
bleed one mic picks up from the other person), to switch cameras, and to auto-mix the voices.

Envelopes are in the take's reference clock, one value per HOP seconds, in dB relative to that
mic's own speech level (its 95th percentile), so a hot mic and a quiet mic compare fairly.
"""

from functools import lru_cache

import numpy as np

from . import ff
from .episode import Episode

RATE = 16000
HOP = 0.02            # 20 ms frames
BLEED_MARGIN = 6.0    # dB a mic must lead the others by to own a moment
SILENT = -32.0        # dB below speech level that counts as nobody talking


def _duration(ep: Episode, take: str) -> float:
    return ff.duration(ep.reference_file(take))


def mic_track(ep: Episode, take: str, person: str, rate: int, start: float = 0.0, dur: float | None = None) -> np.ndarray:
    """A person's mic, aligned to the reference clock."""
    dur = _duration(ep, take) - start if dur is None else dur
    off = ep.offset(take, f"mic:{person}")
    return ff.read_audio(ep.file(take, f"mic:{person}"), start + off, dur, rate)


@lru_cache(maxsize=8)
def _envelopes(episode_id: str, take: str) -> tuple[list[str], np.ndarray]:
    ep = Episode(episode_id)
    people = list(ep.takes[take]["mics"])
    n = int(_duration(ep, take) / HOP)
    hop = int(RATE * HOP)
    rows = []
    for p in people:
        x = mic_track(ep, take, p, RATE)[: n * hop]
        x = np.pad(x, (0, n * hop - len(x)))
        rms = np.sqrt(np.mean(x.reshape(n, hop) ** 2, axis=1) + 1e-12)
        db = 20 * np.log10(rms)
        db = np.convolve(db, np.ones(5) / 5, mode="same")  # 100 ms smoothing
        rows.append(db - np.percentile(db, 95))
    return people, np.array(rows)


def envelopes(ep: Episode, take: str) -> tuple[list[str], np.ndarray]:
    return _envelopes(ep.id, take)


def owner_at(ep: Episode, take: str, a: float, b: float) -> str | None:
    """The person whose mic dominates between a and b (reference clock), or None if silent."""
    people, env = envelopes(ep, take)
    i, j = int(a / HOP), max(int(a / HOP) + 1, int(b / HOP))
    seg = env[:, i:j]
    if seg.size == 0:
        return None
    lvl = seg.max(axis=1)
    k = int(np.argmax(lvl))
    return people[k] if lvl[k] > SILENT else None


def word_is_own(ep: Episode, take: str, person: str, a: float, b: float) -> bool:
    """True if this mic leads the other mics during the word (it's not just bleed)."""
    people, env = envelopes(ep, take)
    if len(people) == 1:
        return True
    i, j = int(a / HOP), max(int(a / HOP) + 1, int(b / HOP))
    lvl = env[:, i:j].max(axis=1)
    me = lvl[people.index(person)]
    others = np.delete(lvl, people.index(person))
    return bool(me >= others.max() - BLEED_MARGIN / 2)


def activity(ep: Episode, take: str, a: float, b: float, hold: float = 0.6) -> list[tuple[float, float, str | None]]:
    """Runs of (start, end, speaker or None) between a and b, ignoring flickers shorter than `hold`."""
    people, env = envelopes(ep, take)
    i, j = int(a / HOP), int(b / HOP)
    seg = env[:, i:j]
    if seg.shape[1] == 0:
        return []
    top = np.argmax(seg, axis=0)
    srt = np.sort(seg, axis=0)
    lead = srt[-1] - (srt[-2] if len(people) > 1 else SILENT * 2)
    lab = np.where(srt[-1] < SILENT, -1, np.where(lead >= BLEED_MARGIN, top, -2))  # -1 silence, -2 overlap
    runs, s = [], 0
    for k in range(1, len(lab) + 1):
        if k == len(lab) or lab[k] != lab[s]:
            runs.append([a + s * HOP, a + k * HOP, int(lab[s])])
            s = k
    # absorb short runs into the previous one
    merged = []
    for r in runs:
        if merged and (r[1] - r[0] < hold or r[2] == merged[-1][2]):
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    name = lambda v: people[v] if v >= 0 else (None if v == -1 else "both")
    return [(x, y, name(v)) for x, y, v in merged]


def automix_gains(ep: Episode, take: str, a: float, b: float, rate: int) -> np.ndarray:
    """Per-mic gain curves (people x samples) for a Dugan-style gain-sharing automix: each mic's
    share of the total speech energy, smoothed, with a floor so room tone never drops out."""
    people, env = envelopes(ep, take)
    i, j = int(a / HOP), int(np.ceil(b / HOP)) + 1
    p = 10 ** (env[:, i:j] / 10)
    g = p / (p.sum(axis=0, keepdims=True) + 1e-9)
    g = np.maximum(g, 0.12)
    k = np.ones(10) / 10  # 200 ms release-like smoothing
    g = np.array([np.convolve(r, k, mode="same") for r in g])
    t = a + np.arange(g.shape[1]) * HOP
    ts = a + np.arange(int(round((b - a) * rate))) / rate
    return np.array([np.interp(ts, t, r) for r in g], dtype=np.float32)
