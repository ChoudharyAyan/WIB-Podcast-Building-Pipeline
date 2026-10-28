# Prompt: cut plan (stage 6)

Claude Code: `/cut <episode>`. Codex: "follow prompts/cut-plan.md for episode <episode>".

## Read
- `episodes/<id>/episode.json` (format, people, sections)
- `episodes/<id>/edit/transcripts/<take>.md` for every take (compact, timestamped, speaker names)
- `episodes/<id>/raw/script.md` or `outline.md` if present

## Write `episodes/<id>/edit/cuts.json`
Schema and rules: WORKFLOW.md stage 6. Example: `episodes/_template/examples/cuts.json`.

1. Per take: `start` 0.1 to 0.2 s before the first word of the first real sentence (after the clap and any mic check), `end` null (last word) or the last word's end, `tail` 0.7 (1.5 on the closing).
2. `remove` only retakes (keep the last fluent version), false starts, doubled words, apologies, off-topic interruptions (a phone, "can we start again"), and dead air over 2.5 s when nothing changes on screen. Give each a short reason.
3. Every cut boundary sits in a gap between words. Confirm with `uv run wib words <id> <take> <a-2> <b+2>` around each one.
4. Conversation: add `chapters` at the question that opens each section, and update `sections` in `episode.json` to match what was actually discussed (titles in sentence case, card `line` = a real quote or claim, under 60 characters). Add `"tighten": {"max_pause": 1.2, "keep": 0.5}`. Add `layouts` with `screen` for stretches where the screen is the point.
5. Don't tighten anyone's style or remove "so" at sentence starts.

## Then
`uv run wib cutlist <id>` and paste its summary into the handoff log. Don't ask Ayan to approve it.
