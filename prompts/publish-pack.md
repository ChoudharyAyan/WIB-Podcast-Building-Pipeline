# Prompt: covers, thumbnail and YouTube copy (stage 11)

Fill these in `episode.json`, then run `wib covers` and `wib package`.

- `thumbnail.lines`: 3 to 6 words over 2 or 3 lines, one line highlighted (`{"text", "hl": true}`), sentence case, the promise of the episode. `thumbnail.sub`: two short lines. `faces`: a smiling frame of each person (`take`, `at`; check with `wib frame --at`).
- `covers[]`: per reel, `bg` colour (a person's colour or volt), `title` (2 or 3 short lines, plain and factual), `sub` pill, `faces`.
- `youtube.title`: under 70 characters, topic first, then "| What I Built Ep NN". `youtube.description`: two or three sentences on what viewers learn, plus the guest's links in `youtube.links`. Chapters are added automatically from the section cards.
- No slogans, no clickbait, no claim that wasn't said in the episode.
