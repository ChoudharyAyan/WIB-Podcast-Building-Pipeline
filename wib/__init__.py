"""WIB podcast building pipeline: post-production for the What I Built podcast."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"
BRAND = ROOT / "brand"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v"}
AUDIO_EXTS = {".wav", ".m4a", ".mp3", ".aac", ".flac"}


def episode_dir(episode_id: str) -> Path:
    path = EPISODES / episode_id
    if not path.is_dir():
        raise SystemExit(f"No episode folder at {path}. Run: uv run wib new {episode_id}")
    return path


def edit_dir(episode_id: str) -> Path:
    path = episode_dir(episode_id) / "edit"
    path.mkdir(exist_ok=True)
    return path
