# Prompt: zooms for Output2 (stage 9)

## Read
- `edit/cutlist.json` (only `screen` layout stretches, or every stretch in a solo episode)
- the transcripts around those stretches
- frames of the screen: `uv run wib frame <id> --take <take> --at <t>` grabs the camera; for the screen use `ffmpeg -ss <t> -i raw/<screen file> -frames:v 1 edit/frames/screen-<t>.jpg`

## Write `edit/zooms.json`
`{"zooms": [{"take", "start", "end", "cx", "cy", "zoom", "ramp"}]}` in the take's reference clock and screen pixels.

1. One zoom per slide or diagram walk-through ("the sources I use are…"), 25 to 55 s, fully inside one kept segment.
2. Centre on the part being explained, and check every box of the slide still fits at the zoom (the visible width is screen width / zoom). Default `zoom` 1.2; up to 1.4 only for narrow content. `ramp` 2.0.
3. Never on camera shots. Never two zooms closer than 10 s.

Then `uv run wib output2 <id> --test <output seconds of the zoom peak>` and look at the frame: text sharp, every box visible.
