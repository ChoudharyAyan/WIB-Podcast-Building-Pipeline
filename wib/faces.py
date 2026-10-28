"""Where a person's face is: the OBS bubble (solo) or a square crop of the camera (conversation).
Used by the sting, reels, covers and the speaker bubble on screen shots."""

from pathlib import Path

from .episode import Episode

FACE_LIFT = "eq=brightness=0.03:contrast=1.05:saturation=1.1:gamma=1.04,unsharp=5:5:0.7"  # approved on Ep01 reels


def face_source(ep: Episode, take: str, person: str | None, t: float) -> tuple[Path, float, str]:
    """(file, time in that file, ffmpeg crop filter) for a square face of `person` at reference time t."""
    person = person or ep.host
    face = ep.get("framing", {}).get("face", {}).get(person)
    if face and ep.file(take, "camera"):
        cx, cy, size = face
        return (ep.file(take, "camera"), t + ep.offset(take, "camera"),
                f"crop={int(size)}:{int(size)}:{int(cx - size / 2)}:{int(cy - size / 2)}")
    if ep.file(take, "screen") and not ep.conversation:
        x, y, size = ep["bubble"]["face"]
        return ep.file(take, "screen"), t + ep.offset(take, "screen"), f"crop={size}:{size}:{x}:{y}"
    raise SystemExit(f"No face framing for {person}. Run `uv run wib frame {ep.id}` and set framing.face.{person} in episode.json.")


def close_source(ep: Episode, take: str, person: str, t: float) -> tuple[Path, float, str]:
    """A 16:9 close-up crop of `person` from the camera."""
    box = ep.get("framing", {}).get("close", {}).get(person)
    if not box:
        raise SystemExit(f"No close-up framing for {person}. Set framing.close.{person} = [x, y, w, h] in episode.json.")
    x, y, w, h = box
    return ep.file(take, "camera"), t + ep.offset(take, "camera"), f"crop={int(w)}:{int(h)}:{int(x)}:{int(y)}"
