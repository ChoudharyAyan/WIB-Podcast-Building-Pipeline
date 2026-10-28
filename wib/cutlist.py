"""Stage 6: turn the agent's cut plan (edit/cuts.json) into the edit everything renders from (edit/cutlist.json).

cuts.json is written by Claude or Codex after reading the transcripts (rules: WORKFLOW.md stage 6):

{
  "takes": {
    "<take>": {"start": 5.70,             # first kept moment (just before the first real sentence)
               "end": null,               # last word's end, or a time; null = the take's last word
               "tail": 0.7,               # seconds kept after the last word
               "remove": [[177.9, 180.5, "dead air while Chrome opens"]],
               "section": "intro"}        # optional; defaults to the take id
  },
  "chapters": [{"take": "part1", "at": 612.3, "section": "ch2"}],   # split a long take into sections
  "tighten": {"max_pause": 1.2, "keep": 0.5},                        # conversation: shorten silent pauses
  "layouts": [{"take": "part1", "from": 100.0, "to": 160.0, "layout": "screen"}]
}

All times are in the take's reference clock. Takes play in episode.json order.
"""

from . import speakers
from .episode import Episode

MIN_SEG = 0.25


def _layout_default(ep: Episode) -> str:
    return "auto" if ep.conversation else "screen"


def silent_gaps(ep: Episode, take: str, a: float, b: float, max_pause: float, keep: float) -> list[tuple[float, float, str]]:
    """Pauses between words longer than max_pause where every mic is quiet (so laughs and untranscribed
    reactions stay). Each is shortened to `keep` seconds."""
    words = [w for w in ep.words(take) if a <= w["start"] and w["end"] <= b]
    out = []
    for w, nxt in zip(words, words[1:]):
        g0, g1 = w["end"], nxt["start"]
        if g1 - g0 <= max_pause:
            continue
        c0, c1 = g0 + keep / 2, g1 - keep / 2
        if c1 - c0 < 0.3 or speakers.owner_at(ep, take, c0, c1) is not None:
            continue
        out.append((round(c0, 2), round(c1, 2), f"pause {g1 - g0:.1f} s"))
    return out


def build(ep: Episode, plan: dict) -> tuple[list[dict], list[dict]]:
    segs, rows = [], []
    tighten = plan.get("tighten")
    chapters = sorted(plan.get("chapters", []), key=lambda c: (ep.take_ids().index(c["take"]), c["at"]))
    for take in ep.take_ids():
        p = plan["takes"].get(take)
        if p is None:
            continue
        words = ep.words(take)
        if not words:
            raise SystemExit(f"Take {take} has no transcript words.")
        start = float(p["start"])
        end = float(p["end"]) if p.get("end") is not None else words[-1]["end"]
        end = round(end + float(p.get("tail", 0.7)), 2)
        cuts = [tuple(c) for c in p.get("remove", [])]
        if tighten:
            cuts += silent_gaps(ep, take, start, end, tighten.get("max_pause", 1.2), tighten.get("keep", 0.5))
        cuts = sorted((max(start, c[0]), min(end, c[1]), c[2] if len(c) > 2 else "") for c in cuts if c[1] > start and c[0] < end)
        keep, cur = [], start
        for a, b, _ in cuts:
            if a > cur:
                keep.append((cur, a))
            cur = max(cur, b)
        keep.append((cur, end))
        # section boundaries inside this take
        marks = [(c["at"], c["section"]) for c in chapters if c["take"] == take]
        section = p.get("section", take)
        for a, b in keep:
            pieces, x = [], a
            for at, sid in marks:
                if a < at < b:
                    pieces.append((x, at, section)); x = at; section = sid
                elif at <= a:
                    section = sid
            pieces.append((x, b, section))
            for x0, x1, sid in pieces:
                if x1 - x0 >= MIN_SEG:
                    segs.append({"take": take, "start": round(x0, 3), "end": round(x1, 3), "section": sid,
                                 "layout": _layout_default(ep)})
        rows.append({"take": take, "head_cut": f"0–{start:.1f} s", "end": end,
                     "removed": [f"{a:.1f}–{b:.1f} s {why}".strip() for a, b, why in cuts],
                     "kept_s": round(sum(b - a for a, b in keep), 1)})
    for o in plan.get("layouts", []):
        segs = _apply_layout(segs, o)
    return segs, rows


def _apply_layout(segs: list[dict], o: dict) -> list[dict]:
    out = []
    for s in segs:
        if s["take"] != o["take"] or s["end"] <= o["from"] or s["start"] >= o["to"]:
            out.append(s); continue
        a, b = max(s["start"], o["from"]), min(s["end"], o["to"])
        if a > s["start"]:
            out.append({**s, "end": a})
        out.append({**s, "start": a, "end": b, "layout": o["layout"]})
        if b < s["end"]:
            out.append({**s, "start": b})
    return out


def run(episode_id: str) -> dict:
    ep = Episode(episode_id)
    plan = ep.read("cuts.json", hint="Write the cut plan first (WORKFLOW.md stage 6, prompts/cut-plan.md).")
    segs, rows = build(ep, plan)
    ep.write("cutlist.json", {"segments": segs})
    for r in rows:
        print(f"{r['take']}: head {r['head_cut']}, ends {r['end']:.1f} s, kept {r['kept_s']} s")
        for c in r["removed"]:
            print(f"    removed {c}")
    total = sum(r["kept_s"] for r in rows)
    print(f"total kept {int(total // 60)} min {total % 60:.0f} s in {len(segs)} segments")
    return {"segments": segs, "summary": rows}
