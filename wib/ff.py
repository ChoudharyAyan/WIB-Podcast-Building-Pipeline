"""Thin helpers around ffmpeg / ffprobe. All shelling out to ffmpeg goes through here."""

import json
import shutil
import subprocess
from pathlib import Path


def require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise SystemExit(f"'{tool}' not found. See docs/setup.md.")
    return path


def run(args: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    cmd = [require("ffmpeg"), "-hide_banner", "-y"]
    if quiet:
        cmd += ["-loglevel", "error"]
    cmd += [str(a) for a in args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def run_capture_stderr(args: list[str]) -> str:
    """Run ffmpeg for its analysis output (filters like ebur128 log to stderr)."""
    cmd = [require("ffmpeg"), "-hide_banner", "-nostats"] + [str(a) for a in args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.stderr


def probe(path: Path) -> dict:
    out = subprocess.run(
        [require("ffprobe"), "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def video_size(path: Path) -> tuple[int, int]:
    for s in probe(path)["streams"]:
        if s.get("codec_type") == "video":
            return int(s["width"]), int(s["height"])
    raise SystemExit(f"No video stream in {path}")


def has_audio(path: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in probe(path)["streams"])


def extract_audio(src: Path, dst: Path, rate: int = 48000) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["-i", src, "-vn", "-ac", "1", "-ar", rate, "-c:a", "pcm_s16le", dst])
    return dst


# ---------- encoders ----------
_ENCODERS = None


def encoders() -> str:
    global _ENCODERS
    if _ENCODERS is None:
        _ENCODERS = subprocess.run([require("ffmpeg"), "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return _ENCODERS


def video_codec(bitrate: str) -> list[str]:
    """Final-quality video encode. Apple hardware HEVC on the Mac (what Ep01 used); x264 elsewhere (tests, CI).
    Set WIB_ENCODER=x264 to force the software path."""
    import os
    if os.environ.get("WIB_ENCODER") != "x264" and "hevc_videotoolbox" in encoders():
        return ["-c:v", "hevc_videotoolbox", "-b:v", bitrate, "-tag:v", "hvc1", "-pix_fmt", "yuv420p"]
    preset = os.environ.get("WIB_X264_PRESET", "medium")
    return ["-c:v", "libx264", "-preset", preset, "-crf", "16", "-pix_fmt", "yuv420p"]


# ---------- checks ----------
def loudness(path: Path) -> dict:
    import re
    log = run_capture_stderr(["-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
    summary = log[log.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    return {"lufs": float(i.group(1)) if i else None, "true_peak": float(tp.group(1)) if tp else None}


def decode_errors(path: Path) -> str:
    """Empty string when the whole file decodes cleanly."""
    proc = subprocess.run([require("ffmpeg"), "-hide_banner", "-v", "error", "-i", str(path), "-f", "null", "-"],
                          capture_output=True, text=True)
    return proc.stderr.strip()


def grab(path: Path, t: float, dst: Path, width: int = 960) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["-ss", f"{t:.3f}", "-i", path, "-frames:v", 1, "-vf", f"scale={width}:-2", "-q:v", 3, dst])
    return dst


# ---------- audio as numpy ----------
def read_audio(path: Path, start: float = 0.0, dur: float | None = None, rate: int = 48000):
    """Mono float32 samples of a file (any container), from `start` (may be negative: pads with silence)."""
    import numpy as np
    pad = 0
    if start < 0:
        pad, start = int(round(-start * rate)), 0.0
    args = [require("ffmpeg"), "-hide_banner", "-v", "error", "-ss", f"{start:.4f}", "-i", str(path)]
    if dur is not None:
        args += ["-t", f"{max(0.0, dur - pad / rate):.4f}"]
    args += ["-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"]
    data = np.frombuffer(subprocess.run(args, check=True, capture_output=True).stdout, dtype=np.float32)
    if pad:
        data = np.concatenate([np.zeros(pad, np.float32), data])
    if dur is not None:
        n = int(round(dur * rate))
        data = np.pad(data, (0, max(0, n - len(data))))[:n]
    return data


def write_wav(path: Path, data, rate: int = 48000) -> Path:
    import numpy as np
    path.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen([require("ffmpeg"), "-hide_banner", "-v", "error", "-y", "-f", "f32le", "-ar", str(rate), "-ac", "1",
                          "-i", "-", "-c:a", "pcm_f32le", str(path)], stdin=subprocess.PIPE)
    p.communicate(np.asarray(data, dtype=np.float32).tobytes())
    if p.returncode:
        raise SystemExit(f"Could not write {path}")
    return path
