"""Quality gates before anything is called finished (WORKFLOW.md stage 12).

Every delivered file is checked for: format (size, fps, codec), loudness and true peak against
the approved targets, a clean full decode, and a duration that matches the render plan. The
report goes to edit/check/report.md with a frame every few minutes for a visual look.
Exit code 1 when any gate fails, so an agent can't miss it.
"""

import json
from pathlib import Path

from . import ff
from .episode import Episode

# (width, height, lufs target, tolerance, max true peak)
GATES = {
    "output1": (3840, 2160, -14.5, 1.0, -1.0),  # Ep01 gate: -14 to -15 LUFS
    "output2": (3840, 2160, -10.5, 1.5, 0.0),   # the denser chain approved on Ep01 (~-10.4 LUFS)
    "reels": (1080, 1920, -10.5, 1.5, 0.0),
}


def _video(path: Path) -> dict:
    return next(s for s in ff.probe(path)["streams"] if s.get("codec_type") == "video")


def check_file(path: Path, kind: str, ep: Episode, expect_s: float | None = None) -> list[str]:
    W, H, lufs, tol, tp_max = GATES[kind]
    if kind != "reels":
        W, H = ep.W, ep.H
    issues = []
    v = _video(path)
    if (int(v["width"]), int(v["height"])) != (W, H):
        issues.append(f"size {v['width']}x{v['height']}, expected {W}x{H}")
    num, den = (int(x) for x in v.get("avg_frame_rate", "0/1").split("/"))
    if den and abs(num / den - ep.fps) > 0.05:
        issues.append(f"{num / den:.2f} fps, expected {ep.fps}")
    if not ff.has_audio(path):
        issues.append("no audio stream")
    else:
        loud = ff.loudness(path)
        if loud["lufs"] is None or abs(loud["lufs"] - lufs) > tol:
            issues.append(f"loudness {loud['lufs']} LUFS, target {lufs} ± {tol}")
        if loud["true_peak"] is not None and loud["true_peak"] > tp_max:
            issues.append(f"true peak {loud['true_peak']} dBFS, max {tp_max}")
    dur = ff.duration(path)
    if expect_s and abs(dur - expect_s) > 0.2:
        issues.append(f"duration {dur:.2f} s, plan says {expect_s:.2f} s")
    if kind == "reels" and dur > 90:
        issues.append(f"reel is {dur:.0f} s; Instagram reels must be 90 s or less")
    err = ff.decode_errors(path)
    if err:
        issues.append("decode errors: " + err.splitlines()[0])
    return issues


def targets(ep: Episode, kind: str | None) -> list[tuple[str, Path, float | None]]:
    out = []
    for k in ("output1", "output2"):
        if kind in (None, k):
            res = ep.read(f"render/{k}-result.json", required=False)
            if res and Path(res.get("delivered", res["file"])).exists():
                out.append((k, Path(res.get("delivered", res["file"])), res["seconds"]))
    if kind in (None, "reels"):
        d = ep.deliver_dir("reels")
        out += [("reels", p, None) for p in sorted(d.glob("*.mp4"))]
    return out


def run(episode_id: str, kind: str | None = None) -> bool:
    ep = Episode(episode_id)
    todo = targets(ep, kind)
    if not todo:
        raise SystemExit("Nothing rendered yet to check.")
    d = ep.edit / "check"
    d.mkdir(parents=True, exist_ok=True)
    lines, ok = [f"# Checks: {ep.tag}", ""], True
    for k, path, expect in todo:
        issues = check_file(path, k, ep, expect)
        loud = ff.loudness(path) if ff.has_audio(path) else {}
        dur = ff.duration(path)
        lines.append(f"## {path.name} ({k})")
        lines.append(f"- {dur / 60:.1f} min, {loud.get('lufs')} LUFS, true peak {loud.get('true_peak')} dBFS")
        lines += [f"- FAIL: {i}" for i in issues] or ["- All gates pass."]
        step = 180 if dur > 300 else max(2.0, dur / 6)
        t, n = 1.0, 0
        while t < dur - 0.5 and n < 40:
            ff.grab(path, t, d / f"{path.stem}-{n:02d}.jpg")
            t, n = t + step, n + 1
        lines += [f"- {n} frames in edit/check/ to look at", ""]
        ok &= not issues
    (d / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    ep.write("check/result.json", {"ok": ok})
    return ok
