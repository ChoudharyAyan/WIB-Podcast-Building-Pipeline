# AGENTS.md

For Claude Code, Codex or any other coding agent working in this repo. Read this, then the stage you were asked to run in [WORKFLOW.md](WORKFLOW.md).

## Your job

Run one stage (or all of them) of the WIB podcast pipeline for one episode, to the quality gate in WORKFLOW.md, and leave the files so another agent can carry on without asking anything.

## Every time

1. Read the newest 20 lines of `~/Projects/wib-hq/HANDOFF-LOG.md`. If another agent has an open STARTED line on the same episode, stop and ask Ayan.
2. Append: `YYYY-MM-DD HH:MM · <agent> · STARTED · Stage N <name> · <episode>`.
3. Run the stage's `uv run wib ...` command. If it says an input is missing, the previous stage isn't done: run that first or say which, and stop.
4. Where the stage needs a decision (cut plan, chapters, zooms, reel picks, covers), follow the matching file in `prompts/` and write the JSON yourself.
5. Test before any full render: `--plan`, then `--test <seconds>` or `--stills`. Look at the result.
6. Run the gate (`uv run wib check <episode>` for renders). Don't call a stage done until it passes.
7. Append `DONE` with the key numbers (duration, LUFS, files) or `PAUSED` with what's left.

## Hard rules

- Free and open-source tools only. Ask Ayan before installing anything on his Mac.
- Never modify `raw/`. Never commit media, `episodes/<id>/` data or secrets.
- You decide cuts, zooms, reel lines and cover copy yourself. Don't send Ayan cut lists or timestamps to approve. Do ask before anything that can't be undone, and before long renders nobody asked for.
- No effect may cut audio. Zooms are 1.2x to 1.4x with a 2 s ease. No burned-in captions on long form.
- Card lines, chips and reel titles use only what was said in the episode. Never invent a number.
- Visual copy: sentence case, no "·"-joined word strings, no slogans, the WIB wordmark on every frame.
- Blur personal data before anything leaves the Mac.
- Never run two renders of the same output at the same time.
- Ayan's other projects in `~/Projects` are off-limits unless he asks.

## Code map

| Module | Stage |
|---|---|
| `wib/episode.py` | Reads `episode.json`; takes, people, clocks, delivery folders |
| `wib/ingest.py` | Clap sync (FFT cross-correlation) |
| `wib/speakers.py` | Who talks when, from each mic; bleed rejection; auto-mix gains |
| `wib/transcribe.py` | Whisper per mic, merged into speaker turns |
| `wib/find.py`, `wib/cutlist.py` | Phrase lookup; cut plan to cut list |
| `wib/timeline.py` | The edit as frame-exact blocks and shots, camera switching, zoom placement, `.otio` |
| `wib/render.py`, `wib/audio.py`, `wib/output.py` | Cached piece renderer, voice and music mix, Output1/Output2 |
| `wib/sting.py`, `wib/cards.py`, `wib/reels.py`, `wib/covers.py` | Motion graphics, reels, covers, thumbnail |
| `wib/subtitles.py`, `wib/check.py`, `wib/package.py`, `wib/review.py` | `.srt`, quality gates, delivery, raw review |

## If you get stuck

Check WORKFLOW.md section 17. If the fix isn't there, write PAUSED with the exact error and what you tried, then tell Ayan in one line.
