# Prompt: pick reels (stage 10)

Claude Code: `/reels <episode>`. Codex: "follow prompts/reels-pick.md for episode <episode>".

## Read
- the transcripts (`edit/transcripts/*.md`), `edit/cutlist.json` (prefer kept material), `episode.json`

## Write `edit/reels.json`
Schema: the docstring at the top of `wib/reels.py`. Example: `episodes/_template/examples/reels.json`. Rules: WORKFLOW.md stage 10.

1. 3 to 5 reels: a 30 s teaser across the episode, then one per strong chapter, and at least one that is mostly the guest.
2. The first clip's first 2 s state the topic and who it's for. No fear-of-missing-out openers.
3. Each clip is one complete thought: starts on a sentence's first word, ends after its last (`wib find` gives exact times). Cut stutters by splitting the clip.
4. `tag`: `person:<id>` in conversations (name and role in the pill), `section:<id>` for solo agent reels. `face`: who is speaking.
5. B-roll per clip: the listener's reaction or the wide shot (`"src": "camera"`), or the screen region being discussed (`"src": "screen"` with `cx`, `cy`, `w`). Slides first, live demo second.
6. Callouts: 1 to 4 per clip, trigger word + 2 to 5 words that were actually said. Never a number nobody said.
7. `title`: two short lines in sentence case. `caption`: the Instagram caption (hook line, two lines of what you'll learn, "Full episode on YouTube", 3 to 5 hashtags including #whatibuilt).
8. Add a matching entry to `covers` in `episode.json` for each reel.
9. If a reel shows the screen, OCR it for personal data and write `edit/privacy/<take>.json` (WORKFLOW.md stage 10).

Then `uv run wib reels <id> --only <reel> --stills 1,<mid>,<end-1>`, look, then render all.
