# WIB podcast making workflow

The full, step-by-step pipeline for one episode of **What I Built (WIB)**, from preparing the episode to the finished YouTube long form and Instagram reels, ready to post. Posting, stories and promotion are out of scope for now.

It runs like a build pipeline. Each stage has inputs, outputs, one command, and a quality gate. A stage is done only when its gate passes, and the next stage starts from the previous stage's files on disk, never from chat memory. That is what lets Claude or Codex pick up any stage cold, at the same quality, when the other one runs out of usage.

Everything is free. The values here are the ones that produced Episode 01 and that Ayan approved. Change them only through the decision log ([docs/decisions.md](docs/decisions.md)).

Two formats are supported, set by `"format"` in `episode.json`:

- **solo**: Ayan alone, screen recording with the OBS face bubble (Episode 01).
- **conversation**: Ayan and a guest in the same room, one camera on both, each person on their own mic, plus the OBS screen (Episode 02 with Yash).

---

## Contents

1. Rules for every stage
2. The commands at a glance
3. Folder layout and file contracts
4. How to run, hand off and resume
5. Stage 0: Episode setup
6. Stage 1: Pre-production
7. Stage 2: Studio setup and test take
8. Stage 3: Shoot
9. Stage 4: Ingest, raw review and framing
10. Stage 5: Transcribe
11. Stage 6: Cut plan
12. Stage 7: Sting and cards
13. Stage 8: Output1, the clean master
14. Stage 9: Output2, YouTube long form with effects
15. Stage 10: Instagram reels
16. Stage 11: Covers, thumbnail, checks and package
17. Known failures and fixes

---

## 1. Rules for every stage

| Rule | Why |
|---|---|
| Free and open-source tools only. No paid apps, plans or API keys. | Ayan's standing rule. |
| Everything runs locally on Ayan's MacBook Air (Apple Silicon). | Footage is large and private. |
| `raw/` is read-only. Outputs go to `edit/` or the delivery folders. | Raw footage is the only thing that can't be regenerated. |
| The agent makes the editing calls (cuts, zooms, reel lines, covers) and delivers finished files. Ayan does not review cut lists or timestamps. | Ayan's instruction, 2026-10-20. He reviews finished files only. |
| No effect may cut or shift audio. Effects only change the picture. | Output2 and reels sit on top of Output1's edit. |
| Zooms are slow and gentle: 1.2x to 1.4x, 2 s smoothstep in and out. | Ayan rejected an abrupt 2x zoom. |
| No burned-in transcript captions on long form; a `.srt` instead. Reels use short kinetic captions. | Ayan: full captions "disrupt the view". |
| Final renders at full quality. Previews for the shared project folder are under 20 MB. | The shared folder has a 20 MB limit. |
| Brand values come from `brand/wib.json` and `brand/`. | One source of truth. |
| Visuals: real WIB logo, sentence case, no dot-joined word strings, no AI-slop copy, WIB wordmark on every frame. | Ayan's style rules. |
| Blur personal data (emails, billing lines, account names) before anything leaves the Mac. | Ep01's Grok screens showed a Gmail address. |
| Media and episode data never go in git. | Size and privacy. `.gitignore` enforces it. |
| Test-render a short window (`--test`, `--stills`) before any full render. Never start a long render nobody asked for. | Usage and time. |
| Run long renders under `caffeinate -dimsu -t 18000`, charger in, lid open. | The Mac sleeping kills renders. |

---

## 2. The commands at a glance

Every command is `uv run wib <command> <episode-id>`, run from the repo folder.

| Stage | Command | Writes |
|---|---|---|
| 0 | `wib new wib-002 --number 02` (add `--format solo` for a solo episode) | `episodes/wib-002/episode.json`, `raw/`, `edit/` |
| 4 | `wib ingest` | `edit/sync.json` (offset of every file to the take's reference) |
| 4 | `wib review` | `edit/review.md` (levels, pace, talk share) |
| 4 | `wib frame [--take t1 --at 90]` | `edit/frames/*.jpg` with a pixel grid for framing |
| 5 | `wib transcribe` | `edit/transcripts/<take>.json` and `.md`, speakers labelled |
| 6 | `wib find <take> "first words" ["last words"]`, `wib pauses <take>`, `wib words <take> <from> <to>` | prints exact times |
| 6 | `wib cutlist` | `edit/cutlist.json` from the agent's `edit/cuts.json` |
| 7 | `wib sting [--stills 1,4,8,11,14]` | `edit/assets/intro-sting.mp4` and `intro-sting-vertical.mp4` |
| 7 | `wib cards` | `edit/cards/<section>.mp4` |
| 8 | `wib output1 [--plan] [--test 120]` | Output1 master, `.otio` timeline |
| 9 | `wib output2 [--plan] [--test 300]` | Output2, `.srt` |
| 10 | `wib reels [--only r1] [--stills 1,6,20]` | each reel in `Instagram videos/` |
| 11 | `wib covers` | reel covers and the YouTube thumbnail |
| 11 | `wib check [--kind reels]` | `edit/check/report.md`, exit 1 on any failure |
| 11 | `wib package` | YouTube title and description with chapters, reel captions, previews |

---

## 3. Folder layout and file contracts

```
wib-podcast-building-pipeline/          this repo (code, brand, prompts, docs)
  brand/                                wib.json, fonts, mascots, badge, wordmark, icons
  config/glossary.txt                   names Whisper must spell right
  episodes/_template/                   episode.conversation.json, episode.solo.json, examples/
  episodes/wib-0NN/                     one per episode, never committed
    episode.json                        the episode's settings
    music/                              sting.mp3, bed.mp3 (licensed, see stage 7)
    raw/                                recordings, read-only
    edit/
      sync.json                         stage 4
      transcripts/<take>.json, .md      stage 5
      cuts.json                         stage 6, written by the agent
      cutlist.json                      stage 6, written by `wib cutlist`
      zooms.json                        stage 9, written by the agent
      reels.json                        stage 10, written by the agent
      privacy/<take>.json               blur boxes, stage 10
      assets/, cards/                   stage 7
      render/                           cached render pieces (safe to delete)
      check/, previews/                 stage 11
~/Documents/Podcast WIB all files/EpNN/ what Ayan opens
  Output1 - without effects/            master .mp4 and .otio
  Output2 - with effects long form/     YouTube upload .mp4 and .srt
  Instagram videos/                     reels, covers, captions.txt, _older versions/
  YouTube/                              thumbnail, title.txt, description.txt
~/Projects/wib-hq/HANDOFF-LOG.md        STARTED, DONE, PAUSED lines from Claude and Codex
```

### Clocks

Each take has a **reference file**: the OBS screen recording, or the camera when there is no screen. Every time in `cuts.json`, `zooms.json`, `reels.json`, `episode.json` and the transcripts is in seconds of that reference file. `wib ingest` measures where every other file (camera, guest mic) sits relative to it, so nobody ever has to convert times by hand.

### `episode.json`

Start from `episodes/_template/episode.conversation.json` or `episode.solo.json` (`wib new` copies the right one). Keys:

| Key | What |
|---|---|
| `id`, `number`, `title` | `wib-002`, `"02"`, the episode title in sentence case |
| `format` | `solo` or `conversation` |
| `people` | `{"host": {"name", "role": "Host", "colour"}, "yash": {...}}`. Colours: `volt`, `signal`, `violet`, `teal`, `amber`. The host is the person with role Host. |
| `takes` | In episode order. `{"id", "screen", "camera", "mics": {"host": file, "yash": file}, "reference"}`. Solo takes need only `screen`. A mic may be the screen file itself (Ayan's mic is inside the OBS recording). |
| `framing` | Conversation only. `face.<person> = [cx, cy, size]` (a square around the face) and `close.<person> = [x, y, w, h]` (a 16:9 close-up), in camera pixels. Optional `wide = [x, y, w, h]`. Set with `wib frame`. |
| `bubble` | Solo only: where the OBS bubble sits in the screen recording (Ep01: x 56, y 1104, 440 px; face crop 91, 1112, 370). |
| `names`, `glossary` | Transcript spelling fixes and extra Whisper hints. |
| `sections` | `{"id", "title", "card": {"tag", "line", "mascot"?, "colour"?}}`. A section with a card gets a 3 s card before it in Output2 and a YouTube chapter. |
| `sting` | `words` (one per beat), `subtitle`, `cast_title`, `cast` (mascots, images, or `{person, take, at}` faces), `faces` (up to two talking faces), `music`. |
| `music_bed` | Path to the bed track, relative to the episode folder. |
| `covers`, `thumbnail`, `youtube` | Stage 11 copy (see there). |
| `canvas`, `fps`, `zoom_max`, `camera_grade` | Defaults 3840×2160, 30, 1.2, a light grade. Leave them. |
| `delivery_root` | Default `~/Documents/Podcast WIB all files/EpNN`. |

---

## 4. How to run, hand off and resume

1. Open a terminal in the repo and start `claude` or `codex`. Both read `AGENTS.md`, which points here.
2. Say: "Run stage N of WORKFLOW.md for episode wib-0NN" or "Edit episode wib-0NN end to end".
3. The agent:
   - reads the newest lines of `~/Projects/wib-hq/HANDOFF-LOG.md`, and stops if another agent has an open STARTED line on the same episode;
   - appends `YYYY-MM-DD HH:MM · <Claude|Codex> · STARTED · Stage N <name> · <episode>`;
   - checks the stage's inputs exist (each command also refuses with a clear message when one is missing);
   - does the steps, then the stage's gate;
   - appends `DONE` with the key numbers, or `PAUSED` with what's left.
4. Every command is safe to re-run. It overwrites only its own outputs. Renders are cached in pieces under `edit/render/pieces/`: an interrupted render resumes where it stopped, and a change re-renders only the shots it touches.
5. Usage: planning and checking cost usage; renders run on the Mac and cost almost none. Plan once, test a window, check it, then do one full render.

---

## 5. Stage 0: Episode setup

| | |
|---|---|
| Input | Topic, guest, rough chapter list |
| Output | `episodes/wib-0NN/` with `episode.json` filled in |
| Command | `uv run wib new wib-0NN --number NN [--format solo]` |

Steps
1. Run the command.
2. Fill in `title`, `people` (guest name, role, a colour that is not volt), takes (expected file names, see stage 3), `sections` (intro plus a guess at chapters; refine after the transcript), `sting`, `youtube.title`.
3. Add the guest's name, company and tools to `glossary`.
4. Put the licensed music in `episodes/wib-0NN/music/` (stage 7).

Gate: `python3 -m json.tool episodes/wib-0NN/episode.json` parses.

---

## 6. Stage 1: Pre-production

| | |
|---|---|
| Input | Topic, guest, agents or projects to show |
| Output | `raw/script.md` (solo) or `raw/outline.md` (conversation), board PNGs, mascots if any |
| Tools | Claude or Codex, Excalidraw (free, no sign-in) |

Solo (Ep01): a script per agent in Build Loop order: pain (30 s, to camera), how it works on the board (1 min), live demo (2.5 min), result and where to get the code (1 min). One board frame per agent and one mascot per agent (transparent PNG in `brand/mascots/`).

Conversation (Ep02):
1. **Outline, not a script.** Intro (Ayan introduces the topic and the guest in 30 s), then 3 to 5 chapters, each with one opening question and two follow-ups. Each chapter should end on a concrete takeaway the guest can state in one sentence: those lines become reel hooks and card lines.
2. **One hook question** to ask early: "What's the one thing most vibe coders get wrong?" Short, opinionated answers make the best reels.
3. **Screen moments**: anything the guest should show (a repo, a prompt, a diagram). Note which chapter. These become `screen` layout segments and reel B-roll.
4. Send the guest the outline the day before so answers come out clean.

Gate: every board frame passes the style rules; every chapter has a question and an expected takeaway.

---

## 7. Stage 2: Studio setup and test take

### Solo (Ep01 setup)
| Setting | Value |
|---|---|
| OBS canvas and output | 2560×1600, 30 fps, Apple VT H.264, 40 Mbps, Hybrid MP4 |
| Scene | Screen capture full frame plus the round webcam bubble bottom-left (440 px at x 56, y 1104) |
| Webcam | Pixel over USB in Webcam mode. **Auto-rotate off** or the feed flips. |
| Mic | A wired or USB mic is best. Ep01 used Dime Evo earbuds (16 kHz, phone-call tone). |

### Same room, two people (Ep02 setup)
| Item | How |
|---|---|
| **Camera** | The Pixel on a tripod about 2 m away at eye height, both people in frame, sitting slightly angled toward each other. Rear camera, **4K 30 fps, recorded on the phone** (not as a webcam: webcam mode is 1080p and softer). Do Not Disturb on, charger plugged in, at least 30 GB free (4K is about 20 GB an hour). Lock exposure and focus (long-press on the frame). |
| **Framing** | Leave space above heads. Each face should be at least 500 px tall in the 4K frame so close-ups and reel faces stay sharp. The pipeline crops close-ups and reel faces from this one shot. |
| **Ayan's mic** | Into OBS as before (the OBS file is the sync reference and carries his voice). |
| **Yash's mic** | His own: a second pair of earbuds or a lav into his phone's voice recorder (or a free app that records WAV at 48 kHz). Phone face-down near him, not between you. |
| **Screen** | OBS records the screen as usual, **without the webcam bubble** (the edit adds the speaker's face). If nothing will be shown on screen, OBS still records: it carries Ayan's mic. |
| **Light** | Both faces lit from the front. No window behind either person. |
| **Room** | Soft room if possible (curtains, a bed, a sofa). Fans and AC off. Phones on silent. |

Test take (60 s, both talking in turn, one clap):
```bash
uv run wib ingest wib-0NN    # the offsets print; each must be found (no "check" warning)
uv run wib review wib-0NN    # each mic about -20 to -14 LUFS, no clipping
uv run wib frame wib-0NN     # check the framing, set framing.face and framing.close
```

Gate: offsets found, both mics in range, both faces sharp and lit in the frame grab, framing values set in `episode.json`.

---

## 8. Stage 3: Shoot

Every take
1. Start the Pixel recording, Yash's recorder, then OBS.
2. **One loud clap** in view of the camera, hands near both mics. This is how `wib ingest` syncs the files.
3. Talk. Fluffed a line? Pause two seconds and say the whole sentence again. Don't stop.
4. Pace: 140 to 160 words a minute. Leave a one-second pause after each key point: clean cut points for reels.
5. Say results as numbers when you have them ("cut our review time in half"). Those lines become hooks and card lines.
6. Stop OBS, the recorder, then the Pixel. A take can be the whole conversation. Split only if something breaks.
7. Copy files into `raw/` with the names in `episode.json` (`t1-screen.mp4`, `t1-camera.mp4`, `t1-yash.m4a`). Use OpenMTP for the Pixel.

Gate: every file in `episode.json` exists in `raw/` and plays to the end.

---

## 9. Stage 4: Ingest, raw review and framing

```bash
uv run wib ingest wib-0NN
uv run wib review wib-0NN
uv run wib frame wib-0NN --at 120     # conversation: set framing from this grid
```

- `ingest` cross-correlates every file's audio with the reference (the clap makes the peak unambiguous) and writes `edit/sync.json`. An offset over two minutes prints a warning: check the clap.
- `review` writes `edit/review.md`: per-mic loudness and peaks, words a minute per person (after stage 5), talk share.
- `frame` saves a camera still with a pixel grid. Read off `framing.face` (a square around each face, a little headroom) and `framing.close` (a 16:9 box per person, about half the frame width).

Gate: every take synced, no mic below −24 LUFS or clipping, framing set. Tell Ayan only what he must fix before the next shoot.

---

## 10. Stage 5: Transcribe

```bash
uv run wib transcribe wib-0NN
```

- mlx-whisper `large-v3-turbo` (downloaded once, about 1.6 GB), word timestamps on, `condition_on_previous_text=False`, the glossary and people's names as the prompt.
- **Conversation**: each person's own mic is transcribed separately. A word is kept only when that person's mic is clearly the loudest at that moment (6 dB lead), which drops the other person's voice bleeding into the mic. Words are moved to the reference clock and rebuilt as speaker turns. No diarization model needed.
- Output: `edit/transcripts/<take>.json` (segments with `speaker`, words with times) and a compact `.md` ("[12:04–12:31] Yash: …") that agents read.

Gate: every take has a transcript, the last word is near the take's end, names are spelled right (fix with `names` in `episode.json`, never by editing times).

---

## 11. Stage 6: Cut plan

The agent reads the transcripts and writes `edit/cuts.json`; `wib cutlist` turns it into the edit everything renders from. Prompt: [prompts/cut-plan.md](prompts/cut-plan.md). Example: `episodes/_template/examples/cuts.json`.

```json
{"takes": {"t1": {"start": 12.4, "end": null, "tail": 0.7, "section": "intro",
                  "remove": [[301.2, 318.9, "Yash restarts the answer"]]}},
 "chapters": [{"take": "t1", "at": 245.0, "section": "ch1"}],
 "tighten": {"max_pause": 1.2, "keep": 0.5},
 "layouts": [{"take": "t1", "from": 1400.0, "to": 1520.0, "layout": "screen"}]}
```

Cut rules (both formats)
1. **Head**: start 0.1 to 0.2 s before the first word of the first real sentence. Remove mic checks, warm-ups ("cool then", "awesome"), the clap, silence.
2. **Tail**: 0.7 s after the last word (1.5 s on the closing).
3. **Inside**, remove only: retakes (keep the last complete fluent version), false starts, doubled words, apologies, dead air over 2.5 s when the screen barely changes.
4. Every cut lands between sentences or at a breath, never mid-word. Check with `wib find` and `wib words`.
5. Don't tighten someone's way of speaking. Output1 is a clean record, not a rewrite.

Conversation extras
6. **Chapters**: split the conversation into the `sections` from `episode.json` at the question that opens each one. Rename or add sections to match what was actually discussed. Each card `line` must be something said in the episode.
7. **Tighten**: `max_pause 1.2, keep 0.5` shortens silent pauses where both mics are quiet. Laughs and reactions are never cut because a mic is active.
8. **Crosstalk**: don't cut inside overlapping speech. Remove a whole exchange only if it adds nothing.
9. **Layouts**: default `auto` (camera switching). Set `screen` for stretches where the screen is what matters (a demo, a diagram); the active speaker's face shows as a bubble. `screen-only` for no bubble, `wide` or `close:<person>` to force a shot.

How camera switching works (`auto`)
- Speaker activity comes from the two mics. Runs shorter than 2 s join their neighbour.
- Each section opens on the wide shot for 3 s, then cuts to whoever is talking (`close:<person>`).
- A close-up longer than 14 s gets a 3 s wide shot in the middle so it never feels static.
- Silence and overlap go wide.

Run `uv run wib cutlist wib-0NN`. It prints per take the head cut, every removed range and the kept time. Log it in the handoff log; don't send it to Ayan.

Gate: no clap or warm-up kept (`wib words` around each segment start), no cut inside a word, sensible total length.

---

## 12. Stage 7: Sting and cards

```bash
uv run wib sting wib-0NN --stills 1,4,8,11,14   # check layout first
uv run wib sting wib-0NN                        # both orientations, 15 s each
uv run wib cards wib-0NN
```

### Intro sting (15 s, 120 BPM grid, the Ep01 v2 design)
| Time | What happens |
|---|---|
| 0–2.75 s | Volt: WIB badge pops in, "WHAT", "I", "BUILT", the orange dot, "PODCAST", "A Podcast for AI Builders". Orange wipe from 2.25 s. |
| 2.75–6.25 s | Orange: the cast floating, `sting.words` popping in one per beat. |
| 6.25–9.5 s | Scrolling rows and the talking face(s) in rings (up to two people, silent clips from `sting.faces`). |
| 9.5–12 s | Cast line-up with names (`sting.cast`: mascots, or each person's face in their colour). |
| 12–15 s | Badge, "EPISODE NN", tagline, `sting.subtitle`, fade out. |

Pick `faces` and `cast` times where each person is smiling or mid-sentence and looking roughly at camera (use `wib frame --at` to check).

### Cards (3 s, 1920×1080, scaled into the long form)
Ink background, colour bar sweep, the mascot (or the chapter number large when there is no mascot), the tag, the title in the colour, then the line. The line is a real quote or claim from the episode.

### Music
- `music/sting.mp3`: a cheerful beat-led track; the first 15 s are used, loudness-matched, faded.
- `music/bed.mp3`: a soft, steady instrumental. It loops under the whole episode.
- **Licence**: use the YouTube Audio Library (free, licence stated per track; pick "no attribution required") or Pixabay Music. Record the track name in `docs/decisions.md`. Ep01's brag-skill track has no confirmed YouTube licence: don't reuse it.

Gate: stills checked for spelling and sentence case, faces sharp, nothing clipped; the sting's audio fades out cleanly.

---

## 13. Stage 8: Output1, the clean master

```bash
uv run wib output1 wib-0NN --plan          # prints the timeline, renders nothing
uv run wib output1 wib-0NN --test 120      # 20 s window starting at 2:00 of the output
caffeinate -dimsu -t 18000 uv run wib output1 wib-0NN
```

What it does
- Builds a frame-exact timeline: the sting, then each section; 0.4 s dissolve out of the sting, 0.5 s crossfades between sections, hard cuts inside a section with 30 ms audio fades.
- **Solo picture**: the 16:10 screen scaled to 3216×2010 on a 3840×2160 ink canvas at x 312, y 30, a 120 px footer band with the 360 px paper WIB wordmark bottom-right. The OBS bubble is in the recording.
- **Conversation picture**: the camera shots per the cut plan (wide, close-ups) with the wordmark bottom-right at 85%; `screen` stretches use the framed screen with the speaker's face bubble (550 px, a ring in their colour).
- **Voice**: each person's own mic, auto-mixed (gain sharing: whoever is louder takes most of the gain, so room bleed doesn't double the voice), then the clean chain `highpass=f=80, afftdn=nf=-28, acompressor=threshold=-20dB:ratio=2.5:attack=10:release=150:makeup=2, loudnorm=I=-14:TP=-1.5:LRA=9`.
- **Encode**: HEVC (Apple hardware) 30 Mbps, AAC 320 kbps. Each shot is its own cached piece; pieces are joined without re-encoding.
- Copies the file to `Output1 - without effects/` with `WIB-EpNN-Output1-timeline.otio` (File → Import → Timeline in DaVinci Resolve, if Ayan ever wants it).

Gate: `wib check --kind output1` passes (4K, 30 fps, −13.5 to −15.5 LUFS, true peak ≤ −1, decode clean, duration matches the plan). Look at the frames in `edit/check/` and the test window around two joins.

---

## 14. Stage 9: Output2, YouTube long form with effects

```bash
uv run wib output2 wib-0NN --plan
uv run wib output2 wib-0NN --test <seconds at a zoom or card>
caffeinate -dimsu -t 18000 uv run wib output2 wib-0NN
```

Output2 is Output1's edit exactly. Effects only go on top.

- **Structure**: sting → intro → card → chapter 1 → card → chapter 2 … with 0.4 s dissolves. Cards sit between sections, so they never cover speech.
- **Zooms** (`edit/zooms.json`, prompt [prompts/zooms.md](prompts/zooms.md)): on `screen` stretches only. One gentle zoom per diagram or slide walk-through, 25 to 55 s, inside one kept segment, centred so every box on the slide stays in frame. Default 1.2x, up to 1.4x for narrow content. 2 s smoothstep in and out, 2x upscale first so text stays sharp; in solo the OBS bubble is lifted out and put back so the face stays round and still.
- **Music**: bed at 0.085 under speech, lifting to 0.30 across each card with 0.6 s ramps; fades in over 2 s, out over the last 4 s.
- **Voice** (approved, about −10.5 LUFS): `highpass=f=75, equalizer=f=180:t=q:w=1:g=2, equalizer=f=3200:t=q:w=1.2:g=2.5, acompressor=threshold=-30dB:ratio=3:attack=5:release=120, volume=22dB, alimiter=limit=0.5:attack=3:release=60:level=false, volume=5.5dB, alimiter=limit=0.89:attack=1:release=30:level=false`. No reverb, no denoise. Sting audio at −3 dB, final limiter 0.84.
- **Subtitles**: `WIB-EpNN-Output2-subtitles.srt` from the transcripts on the Output2 clock: a cue ends at about 38 characters, a sentence end, a pause over 0.7 s, or a speaker change.
- Encode HEVC 40 Mbps, copied to `Output2 - with effects long form/`.

Gate: `wib check --kind output2` passes; the frame at each zoom's peak is sharp with every box visible; each card sits in silence; the `.srt` lines up at the start, middle and end.

---

## 15. Stage 10: Instagram reels

```bash
uv run wib reels wib-0NN --only r1 --stills 1,6,20   # layout stills first
uv run wib reels wib-0NN                              # every reel in edit/reels.json
```

The agent writes `edit/reels.json` (prompt [prompts/reels-pick.md](prompts/reels-pick.md), example `episodes/_template/examples/reels.json`).

### Layout (1080×1920, approved on Ep01)
| Zone | Content |
|---|---|
| Top bar | "WHAT I BUILT · EP NN", JetBrains Mono, volt; thin progress bar. |
| Face | The speaker's face in a 560 px ring in their colour (camera crop in a conversation, OBS bubble in solo), lifted slightly. Their mascot beside it if the section has one. |
| y 888 | Tag pill: the person's name and role (`person:yash`) or the section (`section:ch1`). |
| y 990 | Kinetic captions: 3-word chunks, Inter Black, the spoken word lit in volt. |
| y 1090–1690 | B-roll card, 960×600, rounded, border in the colour, slow 1.00 → 1.08 push-in. |
| Card edge | Callout chips popping in on their trigger word. |
| End, 2.6 s | WIB badge, "FULL EPISODE ON YOUTUBE", "What I Built, episode NN", the cast. |

### Picking hook moments (conversation)
1. **The first 2 s say what the reel is about and who it's for.** No vague fear-of-missing-out openers. Best: the guest's direct answer to a sharp question ("The biggest mistake is …").
2. A reel is a list of clips, each a complete thought. A question from Ayan (short) followed by the guest's answer works well; cut the question if the answer stands alone.
3. Prefer lines with a number, a strong opinion, or a visible result.
4. Lengths: teaser 30 s, topic reels 30 to 60 s, a long reel up to 85 s (open long reels with the vertical sting, `"sting": true`).
5. Make 3 to 5 reels: one teaser across the episode, then one per strong chapter. Give the guest at least one reel of their own.

### B-roll in the card
- `"src": "camera"` shows the camera at the same moment: in a conversation, use the *other* person's reaction or the wide shot. `"src": "screen"` with `crop` shows the screen region being discussed. `"image:<path>"` for a board PNG.
- `"at": null` means the same moment; a time cuts to another moment (a demo).
- Chips: 1 to 4 per clip, the fact said in 2 to 5 words, never a number nobody said.

### Privacy
OCR screen B-roll frames (tesseract is free) for emails, phone numbers, billing lines, account names. Write hits to `edit/privacy/<take>.json` as `[{"t0","t1","x","y","w","h"}]` in screen pixels and the reference clock; reels blur them. Ask Ayan only if a hit is ambiguous.

### Audio
The present voice chain, music at 0.10 under speech rising to 0.40 on the end card, sting at −2 dB. About −10.5 LUFS.

Gate: `wib check --kind reels` passes (1080×1920, ≤ 90 s, loudness, decode); stills at the hook, a chip and the end card look right; topic stated in the first 2 s.

---

## 16. Stage 11: Covers, thumbnail, checks and package

```bash
uv run wib covers wib-0NN
uv run wib check wib-0NN
uv run wib package wib-0NN
```

- **Reel covers** (`episode.json` `covers`): 1080×1920, one colour per reel, the WIB badge, a plain factual title in sentence case, one or two faces in rings, mascots if any, a sub pill. Everything that matters sits in the centre 1080×1350 band (y 285 to 1635) so the 4:5 profile-grid crop still shows it.
- **YouTube thumbnail** (`thumbnail`): 1280×720 on ink, badge top-left, a 3 to 6 word headline with one highlighted line, one face (solo) or two overlapping faces (conversation) on the right.
- **check** runs every gate on every delivered file and writes `edit/check/report.md` with frames to look at. Any FAIL means not done.
- **package** writes `YouTube/title.txt`, `YouTube/description.txt` (with chapters from the cards: `0:00 Intro`, then each chapter), `Instagram videos/captions.txt` (each reel's caption from `reels.json`), and previews under 20 MB in `edit/previews/` for the shared folder.

Delivery folders when done
| Folder | Files |
|---|---|
| Output1 - without effects | `WIB-EpNN-Output1.mp4`, `WIB-EpNN-Output1-timeline.otio` |
| Output2 - with effects long form | `WIB-EpNN-Output2.mp4`, `WIB-EpNN-Output2-subtitles.srt` |
| Instagram videos | reels, covers, `captions.txt`, `_older versions/` |
| YouTube | `WIB-EpNN-thumbnail.png`, `title.txt`, `description.txt` |

Gate: `wib check` exits 0. Log a DONE line listing every delivered file with its duration and loudness.

---

## 17. Known failures and fixes

| Symptom | Cause | Fix |
|---|---|---|
| `ingest` warns about a big offset | No clear clap, or a file recorded from a different take | Clap louder next time. Check the file names in `takes`. |
| A person's words missing from the transcript | Their mic is too quiet relative to the other mic | Raise their mic gain next shoot. For now, lower `BLEED_MARGIN` in `wib/speakers.py` to 4 and re-run `transcribe`. |
| Camera switches too often | Short interjections ("yeah") | Raise `MIN_SHOT` in `wib/timeline.py`, or force a layout for that stretch in `cuts.json`. |
| Close-up looks soft | Face too small in the frame | Sit closer to the camera. Keep `close` boxes at least 1280 px wide. |
| Webcam bubble flips | Pixel auto-rotate | Auto-rotate off; OBS Transform → Rotate. |
| Render stopped partway | Mac slept, or out of memory | Re-run the same command: finished pieces are reused. Use `caffeinate`. |
| A piece has the wrong frame count | A source file shorter than the cut list says | Check `end` in `cuts.json` against the take's length. |
| First seconds frozen | Two renders wrote the same file | Never run two renders of the same output at once. Delete `edit/render/pieces/` entries from that time and re-run. |
| Mix too loud or distorted | Gains stacked | Check `music_bed` loudness (aim about −20 LUFS for the file). Re-run: only the audio is rebuilt if pieces are cached. |
| Zoom crops a slide box | Too tight | 1.2x, or move the centre. |
| A path with "PM" "doesn't exist" | macOS puts a narrow no-break space before PM in screenshot names | Glob for it instead of typing the name. |
| Agent spends usage on work nobody asked for | An ambiguous request | Ask which output a fix is for. Never start a long render that wasn't asked for. |
