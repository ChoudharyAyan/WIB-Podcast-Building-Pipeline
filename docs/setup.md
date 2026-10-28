# Setup (Mac, Apple Silicon) — everything free

Total download: roughly 6–8 GB, most of it DaVinci Resolve (~3 GB) and the Whisper model (~1.6 GB, downloaded on first transcription).

## 1. Apps you install yourself

| App | Why | How | Cost |
|---|---|---|---|
| **OBS Studio** | Record screen + mic (+ Pixel or Mac camera) | `brew install --cask obs` or obsproject.com | Free, open source |
| **DaVinci Resolve** (not Studio) | Edit the long episode | blackmagicdesign.com/products/davinciresolve → Free Download → fill the short form | Free |
| **Excalidraw** | Diagrams | excalidraw.com in the browser, nothing to install | Free |
| OBS **Source Record** plugin (optional) | Save the camera as its own file while OBS records the screen | obsproject.com/forum/resources/source-record.1285 | Free |

## 2. Command-line tools (Homebrew)

```bash
# Homebrew, if `brew --version` fails:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install ffmpeg-full uv git && brew link --force ffmpeg-full
```

- **ffmpeg** — every cut, render and loudness check (ffmpeg-full includes Apple's HEVC encoder)
- **uv** — installs and runs the Python side of this repo
- **git** — version control for this repo

## 3. This repo

```bash
cd ~/Projects/wib-podcast-building-pipeline
uv sync --extra mac     # numpy, Pillow, OpenTimelineIO, mlx-whisper
uv run wib --help
uv run pytest           # should pass
```

## 4. Agents

Use whichever you already have: Claude Code (`claude` in this folder; reads CLAUDE.md → AGENTS.md) or Codex CLI (`codex` in this folder; reads AGENTS.md).

## Check it all works

```bash
ffmpeg -version | head -1
uv run python -c "import mlx_whisper, opentimelineio, PIL; print('ok')"
```
