"""`uv run wib <command> <episode>`: one subcommand per pipeline stage. WORKFLOW.md has the stage table."""

import argparse
import json
import shutil

from . import EPISODES


def cmd_new(a):
    dst = EPISODES / a.episode
    if dst.exists():
        raise SystemExit(f"{dst} already exists.")
    src = EPISODES / "_template"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("episode.*.json", "*.example.json"))
    tpl = src / f"episode.{a.format}.json"
    data = json.loads(tpl.read_text())
    data["id"] = a.episode
    if a.number:
        data["number"] = a.number
    (dst / "episode.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"Created {dst} ({a.format}). Fill in episode.json, then put the recordings in {dst / 'raw'}.")


def floats(s):
    return [float(x) for x in s.split(",")] if s else None


def main(argv=None):
    p = argparse.ArgumentParser(prog="wib", description="WIB podcast building pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("episode", help="episode id, e.g. wib-002")
        return sp

    sp = add("new", "create an episode folder from the template")
    sp.add_argument("--format", choices=["solo", "conversation"], default="conversation")
    sp.add_argument("--number", help='two-digit episode number, e.g. "02"')
    sp.set_defaults(fn=cmd_new)

    add("ingest", "sync every file of every take by the clap (writes edit/sync.json)").set_defaults(
        fn=lambda a: __import__("wib.ingest", fromlist=["run"]).run(a.episode))
    sp = add("review", "raw levels, pace and talk share per person")
    sp.set_defaults(fn=lambda a: __import__("wib.review", fromlist=["run"]).run(a.episode))
    sp = add("frame", "camera stills with a pixel grid for framing.face / framing.close")
    sp.add_argument("--take")
    sp.add_argument("--at", type=float, default=60.0)
    sp.set_defaults(fn=lambda a: __import__("wib.review", fromlist=["frame"]).frame(a.episode, a.take, a.at))
    sp = add("transcribe", "word-timed transcript per take, one per mic, speakers labelled")
    sp.add_argument("--take")
    sp.set_defaults(fn=lambda a: __import__("wib.transcribe", fromlist=["run"]).run(a.episode, a.take))

    sp = add("find", "exact span of a phrase: wib find EP TAKE 'first words' ['last words']")
    sp.add_argument("take")
    sp.add_argument("first")
    sp.add_argument("last", nargs="?")
    sp.add_argument("--after", type=float, default=0.0)
    sp.set_defaults(fn=lambda a: __import__("wib.find", fromlist=["phrase"]).phrase(a.episode, a.take, a.first, a.last, a.after))
    sp = add("pauses", "pauses longer than --min seconds in a take")
    sp.add_argument("take")
    sp.add_argument("--min", type=float, default=1.5)
    sp.set_defaults(fn=lambda a: __import__("wib.find", fromlist=["pauses"]).pauses(a.episode, a.take, a.min))
    sp = add("words", "every word with times between two reference times")
    sp.add_argument("take")
    sp.add_argument("start", type=float)
    sp.add_argument("end", type=float)
    sp.set_defaults(fn=lambda a: __import__("wib.find", fromlist=["words"]).words(a.episode, a.take, a.start, a.end))

    add("cutlist", "edit/cuts.json to edit/cutlist.json (the kept segments)").set_defaults(
        fn=lambda a: __import__("wib.cutlist", fromlist=["run"]).run(a.episode))
    sp = add("sting", "the 15 s intro sting (horizontal and vertical)")
    sp.add_argument("--orient", choices=["h", "v", "both"], default="both")
    sp.add_argument("--stills", help="comma-separated seconds: write PNG stills only")
    sp.set_defaults(fn=lambda a: __import__("wib.sting", fromlist=["run"]).run(a.episode, a.orient, floats(a.stills)))
    add("cards", "3 s section cards for Output2").set_defaults(fn=lambda a: __import__("wib.cards", fromlist=["run"]).run(a.episode))

    for kind, help_ in (("output1", "clean long-form master (+ .otio)"), ("output2", "YouTube long form with effects (+ .srt)")):
        sp = add(kind, help_)
        sp.add_argument("--test", type=float, help="render only ~20 s starting at this output second")
        sp.add_argument("--plan", action="store_true", help="print the timeline, render nothing")
        sp.set_defaults(fn=lambda a, k=kind: __import__("wib.output", fromlist=["run"]).run(a.episode, k, a.test, a.plan))

    sp = add("reels", "Instagram reels from edit/reels.json")
    sp.add_argument("--only", help="one reel id")
    sp.add_argument("--stills", help="comma-separated seconds: write PNG stills only")
    sp.set_defaults(fn=lambda a: __import__("wib.reels", fromlist=["run"]).run(a.episode, a.only, floats(a.stills)))
    add("covers", "reel covers and the YouTube thumbnail").set_defaults(fn=lambda a: __import__("wib.covers", fromlist=["run"]).run(a.episode))

    sp = add("check", "quality gates on every delivered file (exit 1 on failure)")
    sp.add_argument("--kind", choices=["output1", "output2", "reels"])
    sp.set_defaults(fn=lambda a: None if __import__("wib.check", fromlist=["run"]).run(a.episode, a.kind) else exit(1))
    sp = add("package", "title, description with chapters, reel captions, small previews")
    sp.add_argument("--no-previews", action="store_true")
    sp.set_defaults(fn=lambda a: __import__("wib.package", fromlist=["run"]).run(a.episode, not a.no_previews))

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
