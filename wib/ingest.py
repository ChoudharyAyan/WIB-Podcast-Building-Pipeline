"""Stage 4: sync every file of every take to the take's reference clock.

Each take has one reference file (OBS screen recording, or the camera when there is no screen).
Every other file of the take (camera, phone mics) is matched by cross-correlating its audio with
the reference audio. One loud clap at the start of every take makes the peak unambiguous.
Writes edit/sync.json: {take: {"reference": name, "offsets": {name: seconds}}}.
"""

import json
from pathlib import Path

import numpy as np

from . import ff
from .episode import Episode

SYNC_RATE = 8000       # Hz used for correlation; plenty for speech and claps
REF_WINDOW = 240.0     # seconds of the reference compared
OTHER_WINDOW = 600.0   # seconds of the other file searched (files may start up to ~6 min apart)
MAX_SANE = 120.0       # warn when an offset is larger than this


def find_offset(ref: np.ndarray, other: np.ndarray, rate: int) -> float:
    """Seconds to add to a reference time to get the same moment in `other`."""
    ref = ref - ref.mean()
    other = other - other.mean()
    n = len(ref) + len(other)
    size = 1 << (n - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(other, size) * np.conj(np.fft.rfft(ref, size)), size)
    k = int(np.argmax(corr))
    if k > size // 2:
        k -= size
    return k / rate


def sync_take(ep: Episode, take: str) -> dict:
    t = ep.takes[take]
    ref = ep.reference_file(take)
    files = {ref}
    for role in ("screen", "screen2", "camera", "voice"):
        if ep.file(take, role):
            files.add(ep.file(take, role))
    files |= {ep.raw / m for m in t["mics"].values()}
    for f in files:
        if not f.exists():
            raise SystemExit(f"Take {take}: {f.relative_to(ep.dir)} is missing. Check the file name in episode.json.")
    ref_sig = ff.read_audio(ref, 0, REF_WINDOW, SYNC_RATE)
    offsets = {ref.name: 0.0}
    for f in sorted(files - {ref}):
        sig = ff.read_audio(f, 0, OTHER_WINDOW, SYNC_RATE)
        offsets[f.name] = round(find_offset(ref_sig, sig, SYNC_RATE), 3)
    return {"reference": ref.name, "offsets": offsets}


def run(episode_id: str) -> dict:
    ep = Episode(episode_id)
    result = {}
    for take in ep.take_ids():
        result[take] = sync_take(ep, take)
        print(f"{take}: reference {result[take]['reference']}")
        for name, off in result[take]["offsets"].items():
            warn = "  <- check: no clear clap?" if abs(off) > MAX_SANE else ""
            print(f"  {name}: {off:+.3f} s{warn}")
    (ep.edit / "sync.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
