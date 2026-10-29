"""The voice track for a timeline, then the approved processing and the final mix.

1. Assemble (numpy, sample-exact): every kept segment's audio at its output position, 30 ms fades
   at every cut. Conversation: each person's own mic, auto-mixed (gain sharing) so the room bleed
   from the other mic doesn't double the voice.
2. Process the voice (ffmpeg): Output1 uses the clean chain to -14 LUFS; Output2 and reels use the
   denser "present" chain Ayan approved on Ep01 (about -11 LUFS, no reverb or denoise).
3. Mix (ffmpeg): voice + the sting's own audio + the music bed, which lifts under the cards.
"""

from pathlib import Path

import numpy as np

from . import ff, speakers
from .episode import Episode
from .timeline import Block

RATE = 48000

CHAINS = {
    # Output1 (Ep01): rumble cut, light denoise, gentle compression, YouTube loudness.
    "clean": "highpass=f=80,afftdn=nf=-28,acompressor=threshold=-20dB:ratio=2.5:attack=10:release=150:makeup=2,loudnorm=I=-14:TP=-1.5:LRA=9",
    # Output2 and reels (Ep01, approved): warmth and clarity, tighter compression, two limiters. ~-11 LUFS.
    "present": ("highpass=f=75,equalizer=f=180:t=q:w=1:g=2,equalizer=f=3200:t=q:w=1.2:g=2.5,"
                "acompressor=threshold=-30dB:ratio=3:attack=5:release=120,volume=22dB,alimiter=limit=0.5:attack=3:release=60:level=false,"
                "volume=5.5dB,alimiter=limit=0.89:attack=1:release=30:level=false"),
}


def fade(x: np.ndarray, fin: float, fout: float) -> np.ndarray:
    x = x.copy()
    a, b = min(len(x), int(fin * RATE)), min(len(x), int(fout * RATE))
    if a:
        x[:a] *= np.linspace(0, 1, a, dtype=np.float32)
    if b:
        x[-b:] *= np.linspace(1, 0, b, dtype=np.float32)
    return x


def segment_voice(ep: Episode, take: str, a: float, b: float) -> np.ndarray:
    """One kept range of a take, all mics, automixed when there is more than one."""
    n = int(round((b - a) * RATE))
    if ep.takes[take].get("voice"):  # one shared track already carries everyone
        return ff.read_audio(ep.file(take, "voice"), a + ep.offset(take, "voice"), n / RATE, RATE)
    people = list(ep.takes[take]["mics"])
    if len(people) == 1:
        p = people[0]
        return ff.read_audio(ep.file(take, f"mic:{p}"), a + ep.offset(take, f"mic:{p}"), n / RATE, RATE)
    gains = speakers.automix_gains(ep, take, a, b, RATE)[:, :n]
    out = np.zeros(n, np.float32)
    for k, p in enumerate(people):
        x = speakers.mic_track(ep, take, p, RATE, a, n / RATE)[:n]
        out[:len(x)] += x * gains[k, :len(x)]
    return out


def voice_track(ep: Episode, blocks: list[Block], kind: str) -> np.ndarray:
    fps = ep.fps
    total = blocks[-1].start + blocks[-1].frames
    out = np.zeros(int(round(total / fps * RATE)) + RATE, np.float32)
    for k, b in enumerate(blocks):
        if b.kind != "section":
            continue
        sec = []
        for take, s0, s1, _f in b.segments:
            sec.append(fade(segment_voice(ep, take, s0, s1), 0.03, 0.03))
        x = np.concatenate(sec)
        nxt = blocks[k + 1] if k + 1 < len(blocks) else None
        if kind == "output1":  # crossfades between sections (Ep01: acrossfade 0.5 s), 0.4 s in from the sting
            x = fade(x, b.join / fps, (nxt.join / fps) if nxt else 0.0)
        else:                  # Output2: each section eases in and out around the cards
            x = fade(x, 0.15, 0.25)
        i = int(round(b.start / fps * RATE))
        out[i:i + len(x)] += x[: len(out) - i]
    return out[: int(round(total / fps * RATE))]


def process(src: Path, dst: Path, chain: str) -> Path:
    ff.run(["-i", src, "-af", CHAINS[chain], "-ar", RATE, "-ac", 1, "-c:a", "pcm_f32le", dst])
    return dst


def mix(ep: Episode, blocks: list[Block], voice: Path, dst: Path, music: Path | None, bed: float = 0.085, lift: float = 0.30,
        sting_gain_db: float = -3.0) -> Path:
    """Voice + sting audio (at its block) + music bed from the first section to the end, lifted under cards."""
    fps = ep.fps
    total = (blocks[-1].start + blocks[-1].frames) / fps
    sting = next((b for b in blocks if b.kind == "sting"), None)
    args, fc, ins = ["-i", voice], [], ["[0:a]"]
    if sting:
        args += ["-i", ep.edit / "assets" / "intro-sting.mp4"]
        fc.append(f"[1:a]atrim=start={sting.skip / fps:.4f},asetpts=PTS-STARTPTS,aresample={RATE},aformat=channel_layouts=mono,"
                  f"volume={sting_gain_db}dB,adelay={int(sting.start / fps * 1000)}:all=1[st]")
        ins.append("[st]")
    if music:
        mi = len(args) // 2
        first = next(b for b in blocks if b.kind != "sting")
        ms = max(0.0, first.start / fps - 0.3)
        cards = [(b.start / fps, (b.start + b.frames) / fps) for b in blocks if b.kind == "card"]
        up = "+".join(f"clip((t-{a - ms - 0.6:.2f})/0.6,0,1)*clip(({c - ms + 0.6:.2f}-t)/0.6,0,1)" for a, c in cards) or "0"
        args += ["-stream_loop", "-1", "-i", music]
        fc.append(f"[{mi}:a]aresample={RATE},aformat=channel_layouts=mono,atrim=0:{total - ms:.2f},asetpts=PTS-STARTPTS,"
                  f"volume='{bed}+{lift - bed}*min(1,{up})':eval=frame,afade=t=in:d=2,afade=t=out:st={max(0, total - ms - 4):.2f}:d=4,"
                  f"adelay={int(ms * 1000)}:all=1[mu]")
        ins.append("[mu]")
    fc.append("".join(ins) + f"amix=inputs={len(ins)}:normalize=0:duration=first,atrim=0:{total:.3f},aformat=channel_layouts=mono,"
              f"alimiter=limit=0.84:attack=1:release=30:level=false[out]")
    ff.run([*args, "-filter_complex", ";".join(fc), "-map", "[out]", "-ar", RATE, "-c:a", "pcm_f32le", dst])
    return dst


def build(ep: Episode, blocks: list[Block], kind: str, chain: str, music: Path | None) -> Path:
    d = ep.edit / "render"
    raw = ff.write_wav(d / f"{kind}-voice-raw.wav", voice_track(ep, blocks, kind), RATE)
    voice = process(raw, d / f"{kind}-voice.wav", chain)
    sting_db = 0.0 if kind == "output1" else -3.0
    return mix(ep, blocks, voice, d / f"{kind}-mix.wav", music, sting_gain_db=sting_db)


# ---------- legacy: clean a single file (kept for quick checks) ----------
def clean_file(src: Path, dst: Path) -> Path:
    return process(src, dst, "clean")
