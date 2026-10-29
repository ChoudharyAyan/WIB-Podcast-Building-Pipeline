"""End to end on synthetic media: a two-person, same-room take (screen + Ayan's mic, a camera, the
guest's own recorder), each starting at a different moment, with room bleed between the mics.
No real footage or Whisper needed: transcripts are faked in the shape Whisper returns.

Renders run at 960x540 with x264 so the whole suite finishes in a few minutes on any machine."""

import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

import wib
from wib import ff

RATE = 48000
DUR = 40.0                      # reference (screen) length
CAM_OFF, YASH_OFF = 2.0, 3.5    # camera / Yash's recorder started this much earlier than OBS
HOST = [(2, 9), (18, 24), (32, 37.5)]
YASH = [(10, 17), (25, 31)]
CLAP = 1.0


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True)


G0, G1 = -5.0, 50.0            # global clock range the synthetic room covers


def voice(seed, spans):
    """Speech-like noise (syllable envelope at ~4 Hz) inside `spans`, on the global clock."""
    n = int((G1 - G0) * RATE)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / RATE + G0
    x = rng.standard_normal(n).astype(np.float32)
    x = np.convolve(x, np.ones(6) / 6, mode="same")
    env = np.zeros(n, np.float32)
    for a, b in spans:
        env[(t >= a) & (t < b)] = 1
    syl = 0.55 + 0.45 * np.sin(2 * np.pi * 4.2 * t + seed)
    return 0.25 * x * env * syl


def clap():
    x = np.zeros(int((G1 - G0) * RATE), np.float32)
    i = int((CLAP - G0) * RATE)
    x[i:i + 400] = np.random.default_rng(1).standard_normal(400) * np.linspace(0.9, 0, 400)
    return x


def fake_whisper(spans, off, prefix):
    """Words every 0.45 s inside spans, in the mic file's own clock (reference + off)."""
    words = []
    for a, b in spans:
        t, k = a + 0.1, 0
        while t + 0.35 < b:
            k += 1
            words.append({"start": round(t + off, 2), "end": round(t + off + 0.35, 2),
                          "word": f" {prefix}{len(words)}" + ("." if k % 6 == 0 else "")})
            t += 0.45
    return {"segments": [{"start": words[0]["start"], "end": words[-1]["end"], "words": words}]}


@pytest.fixture(scope="module")
def ep_id(tmp_path_factory):
    root = tmp_path_factory.mktemp("episodes")
    mp = pytest.MonkeyPatch()
    mp.setattr(wib, "EPISODES", root)
    mp.setenv("WIB_ENCODER", "x264")
    mp.setenv("WIB_X264_PRESET", "ultrafast")
    tpl = json.loads((Path(wib.ROOT) / "episodes/_template/episode.conversation.json").read_text())
    d = root / "wib-099"
    raw = d / "raw"
    raw.mkdir(parents=True)
    (d / "music").mkdir()
    # global clock: g = reference time
    H, Y, C = voice(11, HOST), voice(23, YASH), clap()

    def track(t0, dur, host_g, yash_g):
        i = int((t0 - G0) * RATE)
        return (host_g * H + yash_g * Y + C)[i:i + int(dur * RATE)]
    ff.write_wav(raw / "host.wav", track(0, DUR, 1.0, 0.12), RATE)
    ff.write_wav(raw / "t1-yash.wav", track(-YASH_OFF, DUR + YASH_OFF + 2, 0.12, 1.0), RATE)
    ff.write_wav(raw / "cam.wav", track(-CAM_OFF, DUR + CAM_OFF + 2, 0.4, 0.4), RATE)
    ffmpeg("-f", "lavfi", "-i", f"testsrc2=s=1280x800:r=30:d={DUR}", "-i", raw / "host.wav", "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", raw / "t1-screen.mp4")
    ffmpeg("-f", "lavfi", "-i", f"testsrc=s=1920x1080:r=30:d={DUR + CAM_OFF + 2}", "-i", raw / "cam.wav", "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", raw / "t1-camera.mp4")
    for f in ("host.wav", "cam.wav"):
        (raw / f).unlink()
    ffmpeg("-f", "lavfi", "-i", "sine=f=220:d=40", "-f", "lavfi", "-i", "sine=f=330:d=40", "-filter_complex", "amix=2,volume=0.5",
           d / "music" / "bed.mp3")
    ffmpeg("-f", "lavfi", "-i", "sine=f=440:d=16", d / "music" / "sting.mp3")
    tpl.update({
        "id": "wib-099", "number": "99", "canvas": [960, 540], "delivery_root": str(d / "delivery"),
        "takes": [{"id": "t1", "screen": "t1-screen.mp4", "camera": "t1-camera.mp4",
                   "mics": {"host": "t1-screen.mp4", "yash": "t1-yash.wav"}}],
        "framing": {"face": {"host": [500, 520, 420], "yash": [1420, 520, 420]},
                    "close": {"host": [0, 180, 1280, 720], "yash": [640, 180, 1280, 720]}},
    })
    tpl["sting"]["cast"] = [{"person": "host", "take": "t1", "at": 5.0}, {"person": "yash", "take": "t1", "at": 12.0}]
    tpl["sting"]["faces"] = [{"person": "host", "take": "t1", "at": 3.0}, {"person": "yash", "take": "t1", "at": 11.0}]
    tpl["covers"][0]["faces"] = [{"person": "yash", "take": "t1", "at": 12.0}]
    tpl["thumbnail"]["faces"] = [{"person": "host", "take": "t1", "at": 5.0}, {"person": "yash", "take": "t1", "at": 12.0}]
    (d / "episode.json").write_text(json.dumps(tpl, indent=1))
    yield "wib-099"
    mp.undo()


def episode(ep_id):
    from wib.episode import Episode
    return Episode(ep_id)


def test_01_ingest_finds_every_offset(ep_id):
    from wib import ingest
    res = ingest.run(ep_id)["t1"]
    assert res["reference"] == "t1-screen.mp4"
    assert res["offsets"]["t1-camera.mp4"] == pytest.approx(CAM_OFF, abs=0.01)
    assert res["offsets"]["t1-yash.wav"] == pytest.approx(YASH_OFF, abs=0.01)


def test_02_speakers_and_bleed(ep_id):
    from wib import speakers, transcribe
    speakers._envelopes.cache_clear()
    ep = episode(ep_id)
    assert speakers.owner_at(ep, "t1", 4, 6) == "host"
    assert speakers.owner_at(ep, "t1", 12, 14) == "yash"
    assert speakers.owner_at(ep, "t1", 9.4, 9.8) is None
    # each mic "hears" both people, as Whisper would through bleed
    per = {"host": fake_whisper(HOST + YASH, 0.0, "h"), "yash": fake_whisper(HOST + YASH, YASH_OFF, "y")}
    tr = transcribe.merge(ep, "t1", per)
    ep.write("transcripts/t1.json", tr)
    words = [w for s in tr["segments"] for w in s["words"]]
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        who = "host" if any(a <= mid < b for a, b in HOST) else "yash"
        assert w["speaker"] == who, w
    assert {s["speaker"] for s in tr["segments"]} == {"host", "yash"}
    gains = speakers.automix_gains(ep, "t1", 4, 6, 16000)
    assert gains[0].mean() > 0.8 and gains[1].mean() < 0.35


def test_03_cutlist(ep_id):
    from wib import cutlist
    ep = episode(ep_id)
    ep.write("cuts.json", {"takes": {"t1": {"start": 1.9, "end": None, "tail": 0.5, "section": "intro",
                                            "remove": [[20.0, 21.0, "false start"]]}},
                           "chapters": [{"take": "t1", "at": 9.6, "section": "ch1"}, {"take": "t1", "at": 24.5, "section": "ch2"}],
                           "tighten": {"max_pause": 1.2, "keep": 0.5}})
    res = cutlist.run(ep_id)
    segs = res["segments"]
    assert [s["section"] for s in segs][0] == "intro" and segs[-1]["section"] == "ch2"
    assert not any(s["start"] < 20.5 < s["end"] for s in segs)
    assert all(s["layout"] == "auto" for s in segs)


def test_04_timeline_switches_cameras(ep_id):
    from wib import timeline
    ep = episode(ep_id)
    blocks = timeline.build(ep, "output2")
    kinds = [b.kind for b in blocks]
    assert kinds[0] == "sting" and "card" in kinds
    shots = [s for b in blocks for s in b.shots]
    for b in blocks:
        if b.kind == "section":
            assert b.shots[0].layout == "wide"   # every section opens on the wide shot
    assert {s.layout for s in shots} >= {"close:host", "close:yash"}
    for b in blocks:
        if b.kind == "section":
            assert sum(s.frames for s in b.shots) == b.frames


def test_05_sting_cards_covers(ep_id):
    from wib import cards, covers, sting
    sting.run(ep_id, "both")
    ep = episode(ep_id)
    for name in ("intro-sting.mp4", "intro-sting-vertical.mp4"):
        p = ep.edit / "assets" / name
        assert ff.duration(p) == pytest.approx(15.0, abs=0.1)
    assert ff.video_size(ep.edit / "assets" / "intro-sting-vertical.mp4") == (1080, 1920)
    assert len(cards.run(ep_id)) == 2
    outs = covers.run(ep_id)
    assert len(outs) == 2 and all(p.exists() for p in outs)


def test_06_output1(ep_id):
    from wib import output, timeline
    res = output.run(ep_id, "output1")
    ep = episode(ep_id)
    out = Path(res["delivered"])
    assert ff.video_size(out) == (960, 540)
    n = timeline.total_frames(timeline.build(ep, "output1"))
    assert ff.duration(out) == pytest.approx(n / 30, abs=0.1)
    assert (out.parent / "WIB-Ep99-Output1-timeline.otio").exists()
    assert ff.loudness(out)["lufs"] == pytest.approx(-14, abs=1.5)
    assert not ff.decode_errors(out)


def test_07_output2_with_zoom_and_screen_layout(ep_id):
    from wib import cutlist, output
    ep = episode(ep_id)
    cuts = ep.read("cuts.json")
    cuts["layouts"] = [{"take": "t1", "from": 26.0, "to": 31.0, "layout": "screen"}]
    ep.write("cuts.json", cuts)
    cutlist.run(ep_id)
    ep.write("zooms.json", {"zooms": [{"take": "t1", "start": 26.0, "end": 31.0, "cx": 640, "cy": 400, "zoom": 1.3, "ramp": 1.0}]})
    res = output.run(ep_id, "output2")
    out = Path(res["delivered"])
    assert Path(res["srt"]).read_text().count("-->") > 5
    assert not ff.decode_errors(out)
    assert ff.loudness(out)["lufs"] == pytest.approx(-11, abs=2)


def test_08_test_render_window(ep_id):
    from wib import output
    res = output.run(ep_id, "output2", test=12.0)
    assert ff.duration(Path(res["file"])) == pytest.approx(20.0, abs=0.15)


def test_09_reels(ep_id):
    from wib import reels
    ep = episode(ep_id)
    ep.write("reels.json", {"reels": [{
        "id": "r1", "out": "WIB-Ep99-Reel-1.mp4", "title": "Two people\ntalking", "caption": "caption",
        "clips": [{"take": "t1", "start": 2.1, "end": 8.8, "tag": "person:host", "face": "host", "crop": [640, 400, 900],
                   "callouts": [["h3", "A CALLOUT"]]},
                  {"take": "t1", "start": 10.1, "end": 16.8, "tag": "person:yash", "face": "yash",
                   "broll": [{"src": "camera", "at": None}]}]}]})
    ep.write("privacy/t1.json", [{"t0": 2.0, "t1": 6.0, "x": 300, "y": 300, "w": 400, "h": 120}])
    reels.run(ep_id, stills=[1.0, 9.0])
    outs = reels.run(ep_id)
    assert ff.video_size(outs[0]) == (1080, 1920)
    assert not ff.decode_errors(outs[0])


def test_10_check_and_package(ep_id):
    from wib import check, package
    ep = episode(ep_id)
    ok = check.run(ep_id)
    report = (ep.edit / "check" / "report.md").read_text()
    assert "Output1" in report and "Reel-1" in report
    assert "FAIL: size" not in report and "decode errors" not in report
    package.run(ep_id)
    desc = (ep.deliver_dir("youtube") / "description.txt").read_text()
    assert "0:00 Intro" in desc and "What vibe coding is" in desc
    for p in (ep.edit / "previews").glob("*.mp4"):
        assert p.stat().st_size < 20e6


def test_11_cli_new(tmp_path, monkeypatch):
    from wib import cli
    monkeypatch.setattr(wib, "EPISODES", tmp_path)
    monkeypatch.setattr(cli, "EPISODES", tmp_path)
    (tmp_path / "_template").mkdir()
    for f in ("episode.conversation.json", "episode.solo.json"):
        (tmp_path / "_template" / f).write_text((Path(wib.ROOT) / "episodes/_template" / f).read_text())
    cli.main(["new", "wib-005", "--number", "05"])
    data = json.loads((tmp_path / "wib-005" / "episode.json").read_text())
    assert data["id"] == "wib-005" and data["number"] == "05" and data["format"] == "conversation"


def test_13_shared_voice_track_and_second_screen(ep_id):
    """One wireless receiver mixing both mics (the sound), a phone near Yash only to tell who talks,
    and Yash's own screen recording as a second screen."""
    import shutil
    from wib import cutlist, ingest, output, speakers, transcribe
    src = Path(wib.EPISODES) / ep_id
    d = Path(wib.EPISODES) / "wib-097"
    raw = d / "raw"
    raw.mkdir(parents=True)
    H, Y, C = voice(11, HOST), voice(23, YASH), clap()
    cut = lambda t0, dur: slice(int((t0 - G0) * RATE), int((t0 - G0) * RATE) + int(dur * RATE))
    ff.write_wav(raw / "mix.wav", (H + Y + C)[cut(0, DUR)], RATE)
    ff.write_wav(raw / "t1-yash-phone.wav", (0.35 * H + Y + C)[cut(-YASH_OFF, DUR + YASH_OFF + 2)], RATE)
    ff.write_wav(raw / "s2.wav", (0.3 * (H + Y) + C)[cut(-1.0, DUR + 3)], RATE)
    ffmpeg("-f", "lavfi", "-i", f"testsrc2=s=1280x800:r=30:d={DUR}", "-i", raw / "mix.wav", "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", raw / "t1-screen.mp4")
    ffmpeg("-f", "lavfi", "-i", f"mandelbrot=s=1280x800:r=30", "-i", raw / "s2.wav", "-map", "0:v", "-map", "1:a", "-t", DUR + 3,
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", raw / "t1-yash-screen.mp4")
    for f in ("mix.wav", "s2.wav"):
        (raw / f).unlink()
    shutil.copy(src / "raw" / "t1-camera.mp4", raw / "t1-camera.mp4")
    shutil.copytree(src / "music", d / "music")
    shutil.copytree(src / "edit" / "assets", d / "edit" / "assets")
    data = json.loads((src / "episode.json").read_text())
    data.update({"id": "wib-097", "delivery_root": str(d / "delivery")})
    data["takes"] = [{"id": "t1", "screen": "t1-screen.mp4", "screen2": "t1-yash-screen.mp4", "camera": "t1-camera.mp4",
                      "voice": "t1-screen.mp4", "mics": {"yash": "t1-yash-phone.wav"}}]
    (d / "episode.json").write_text(json.dumps(data))

    res = ingest.run("wib-097")["t1"]["offsets"]
    assert res["t1-yash-phone.wav"] == pytest.approx(YASH_OFF, abs=0.01)
    assert res["t1-yash-screen.mp4"] == pytest.approx(1.0, abs=0.01)
    ep = episode("wib-097")
    assert ep.take_people("t1") == ["host", "yash"]
    speakers._envelopes.cache_clear()
    assert speakers.owner_at(ep, "t1", 4, 6) == "host"
    assert speakers.owner_at(ep, "t1", 12, 14) == "yash"
    assert speakers.owner_at(ep, "t1", 9.4, 9.8) is None
    tr = transcribe.label_shared(ep, "t1", fake_whisper(HOST + YASH, 0.0, "w"))
    words = [w for s in tr["segments"] for w in s["words"]]
    wrong = [w for w in words if w["speaker"] != ("host" if any(a <= (w["start"] + w["end"]) / 2 < b for a, b in HOST) else "yash")]
    assert len(wrong) <= 0.05 * len(words), wrong
    ep.write("transcripts/t1.json", tr)
    ep.write("cuts.json", {"takes": {"t1": {"start": 1.9, "end": None, "tail": 0.5, "section": "intro"}},
                           "layouts": [{"take": "t1", "from": 11.0, "to": 16.0, "layout": "screen2"}]})
    segs = cutlist.run("wib-097")["segments"]
    assert any(s["layout"] == "screen2" for s in segs)
    out = Path(output.run("wib-097", "output1", test=14.0)["file"])
    assert ff.duration(out) == pytest.approx(20.0, abs=0.15)
    assert not ff.decode_errors(out)
