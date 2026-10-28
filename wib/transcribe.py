"""Stage 5: word-timed transcripts, one per take, in the take's reference clock.

Solo: the host's mic (the reference file's audio). Conversation: every person's own mic is
transcribed separately, so every word already knows its speaker. Words a mic only picked up as
bleed from the other person are dropped (the other mic has them). Output:
edit/transcripts/<take>.json and a readable edit/transcripts/<take>.md.

Backends, tried in order: mlx-whisper (Apple Silicon), faster-whisper (any CPU).
The glossary goes in as Whisper's initial prompt so tool and people names come out right.
"""

import json
from pathlib import Path

from . import ROOT, ff
from .episode import Episode

MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
CPU_MODEL = "large-v3-turbo"


def glossary_prompt(ep: Episode | None = None) -> str:
    path = ROOT / "config" / "glossary.txt"
    terms = [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")] if path.exists() else []
    if ep:
        terms += [p["name"] for p in ep.people.values()] + ep.get("glossary", [])
    return "Glossary: " + ", ".join(dict.fromkeys(terms)) + "." if terms else ""


def _mlx(audio: Path, prompt: str) -> dict:
    import mlx_whisper
    result = mlx_whisper.transcribe(
        str(audio), path_or_hf_repo=MLX_MODEL, language="en", word_timestamps=True,
        condition_on_previous_text=False,     # avoids repetition loops
        initial_prompt=prompt or None,
    )
    return {"language": result.get("language", "en"), "segments": [{
        "start": round(s["start"], 3), "end": round(s["end"], 3), "text": s["text"].strip(),
        "words": [{"start": round(w["start"], 3), "end": round(w["end"], 3), "word": w["word"].strip()}
                  for w in s.get("words", [])]} for s in result["segments"]]}


def _cpu(audio: Path, prompt: str) -> dict:
    from faster_whisper import WhisperModel
    model = WhisperModel(CPU_MODEL, device="cpu", compute_type="int8")
    segs, info = model.transcribe(str(audio), language="en", word_timestamps=True,
                                  condition_on_previous_text=False, initial_prompt=prompt or None, vad_filter=True)
    return {"language": info.language, "segments": [{
        "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
        "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word.strip()} for w in (s.words or [])]}
        for s in segs]}


def transcribe_file(audio: Path, prompt: str = "") -> dict:
    try:
        return _mlx(audio, prompt)
    except ImportError:
        pass
    try:
        return _cpu(audio, prompt)
    except ImportError:
        raise SystemExit("No Whisper backend. On the Mac: uv sync --extra mac (see docs/setup.md).")


def fmt_time(t: float) -> str:
    m, s = divmod(max(0.0, t), 60)
    h, m = divmod(int(m), 60)
    return f"{h:d}:{m:02d}:{s:05.2f}" if h else f"{m:02d}:{s:05.2f}"


def to_markdown(ep: Episode, transcript: dict) -> str:
    """Compact, timestamped text an agent can read cheaply. Speaker names only in conversations."""
    lines = []
    for s in transcript["segments"]:
        who = f"{ep.people.get(s.get('speaker'), {}).get('name', s.get('speaker'))}: " if ep.conversation else ""
        lines.append(f"[{fmt_time(s['start'])}–{fmt_time(s['end'])}] {who}{s['text']}")
    return "\n".join(lines) + "\n"


def merge(ep: Episode, take: str, per_person: dict[str, dict]) -> dict:
    """Shift each mic's words into the reference clock, keep only words that mic owns, and rebuild
    segments as speaker turns (a new segment at every speaker change or pause over 1 s)."""
    from . import speakers
    words = []
    for person, tr in per_person.items():
        off = ep.offset(take, f"mic:{person}")
        for s in tr["segments"]:
            for w in s["words"]:
                a, b = w["start"] - off, w["end"] - off
                if len(per_person) > 1 and not speakers.word_is_own(ep, take, person, a, b):
                    continue
                words.append({"start": round(a, 3), "end": round(b, 3), "word": w["word"], "speaker": person})
    words.sort(key=lambda w: w["start"])
    segments = []
    for w in words:
        cur = segments[-1] if segments else None
        if cur and cur["speaker"] == w["speaker"] and w["start"] - cur["end"] < 1.0:
            cur["words"].append(w); cur["end"] = w["end"]
        else:
            segments.append({"start": w["start"], "end": w["end"], "speaker": w["speaker"], "words": [w]})
    for s in segments:
        s["text"] = " ".join(x["word"] for x in s["words"])
    return {"language": "en", "take": take, "segments": segments}


def run(episode_id: str, only: str | None = None) -> list[Path]:
    ep = Episode(episode_id)
    prompt = glossary_prompt(ep)
    out = []
    for take in ep.take_ids():
        if only and take != only:
            continue
        per_person = {}
        for person in ep.takes[take]["mics"]:
            src = ep.file(take, f"mic:{person}")
            wav = ff.extract_audio(src, ep.edit / "audio" / f"{take}-{person}.wav", rate=16000)
            per_person[person] = transcribe_file(wav, prompt)
        tr = merge(ep, take, per_person)
        path = ep.write(f"transcripts/{take}.json", tr)
        (ep.edit / "transcripts" / f"{take}.md").write_text(to_markdown(ep, tr))
        print(f"{take}: {sum(len(s['words']) for s in tr['segments'])} words, {len(tr['segments'])} turns -> {path}")
        out.append(path)
    return out
