"""Who is speaking when, from each person's own mic. Used to label transcript words (dropping the
bleed one mic picks up from the other person), to switch cameras, and to auto-mix the voices.

Envelopes are in the take's reference clock, one value per HOP seconds, in dB relative to that
mic's own speech level (its 95th percentile), so a hot mic and a quiet mic compare fairly.

Shared voice track (one wireless receiver mixing everyone): the take's "voice" file says when anyone
is talking, and each detection mic (a phone near that person) says whether it is them: a detection
mic that is close to the voice track's level is its owner speaking; well below it, someone else.
The split point is found per take from the data (two clusters), so phone placement doesn't need
tuning. The result is turned into ordinary per-person envelopes, so everything downstream is unchanged.
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


def _level(x: np.ndarray, n: int) -> np.ndarray:
    hop = int(RATE * HOP)
    x = np.pad(x[: n * hop], (0, max(0, n * hop - len(x))))
    db = 20 * np.log10(np.sqrt(np.mean(x.reshape(n, hop) ** 2, axis=1) + 1e-12))
    db = np.convolve(db, np.ones(5) / 5, mode="same")  # 100 ms smoothing
    return db - np.percentile(db, 95)


def _split(v: np.ndarray) -> float:
    """Threshold between the two clusters of a 1-D sample (2-means)."""
    lo, hi = np.percentile(v, 10), np.percentile(v, 90)
    for _ in range(50):
        t = (lo + hi) / 2
        a, b = v[v < t], v[v >= t]
        if not len(a) or not len(b):
            break
        lo, hi = a.mean(), b.mean()
    return float((lo + hi) / 2)


@lru_cache(maxsize=8)
def _envelopes(episode_id: str, take: str) -> tuple[list[str], np.ndarray]:
    ep = Episode(episode_id)
    people = ep.take_people(take)
    n = int(_duration(ep, take) / HOP)
    if not ep.takes[take].get("voice"):
        return people, np.array([_level(mic_track(ep, take, p, RATE), n) for p in people])
    v = _level(ff.read_audio(ep.file(take, "voice"), ep.offset(take, "voice"), n * HOP, RATE), n)
    speech = v > SILENT
    detect = [p for p in people if p in ep.takes[take]["mics"]]
    owner = np.full(n, -1)
    for p in detect:
        d = _level(mic_track(ep, take, p, RATE), n) - v
        t = _split(d[speech]) if speech.sum() > 50 else 0.0
        owner[speech & (d >= t) & (owner == -1)] = people.index(p)
    rest = next(p for p in people if p not in detect)
    owner[speech & (owner == -1)] = people.index(rest)
    rows = np.full((len(people), n), -60.0)
    for k in range(len(people)):
        rows[k, owner == k] = v[owner == k]
    rows[:, ~speech] = np.minimum(rows[:, ~speech], v[~speech])
    return people, rows


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
