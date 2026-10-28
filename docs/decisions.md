# Decisions log

Newest first. Add a line whenever a tool, format or rule changes.

| Date | Decision | Why |
|---|---|---|
| 2026-10-28 | Ep01's hand-edited scripts became `wib` commands driven by `episode.json`; one repo, WIB-Podcast-Building-Pipeline | Repeatable episodes; any agent can run any stage |
| 2026-10-28 | Conversation format for guests in the same room: one Pixel 4K camera on both, each person on their own mic, OBS screen as the sync reference, clap per take | Ep02 with Yash; sharp faces for reels, clean voices |
| 2026-10-28 | Speaker labels and camera switching come from each person's own mic (6 dB lead), no diarization model; voices auto-mixed by gain sharing | Free, local, accurate when each person has a mic |
| 2026-10-28 | Renders are cached pieces joined by stream copy; every duration is whole frames | Resumable, memory-flat on the MacBook Air, A/V stays in sync |
| 2026-10-28 | Ep02 onward: music from the YouTube Audio Library or Pixabay Music, track names logged here | Ep01's sting track has no confirmed YouTube licence |
| 2026-10-21 | Reel hooks state the topic; personal data blurred; floating tool icons for named tools | Ayan's reel feedback |
| 2026-10-20 | Output1 clean chain −14 LUFS; Output2 and reels the denser chain (about −10.5 LUFS), no reverb or denoise | Ayan approved on Ep01 |
| 2026-10-20 | No burned-in captions on long form (`.srt`); zooms 1.2–1.4x with 2 s ease; effects never cut audio | Ayan's Ep01 feedback |
| 2026-10-20 | Claude decides cuts and delivers finished renders; Ayan doesn't review cut lists | Ayan's instruction |
| 2026-10-20 | Long form: 4K ink canvas, screen 3216×2010, WIB wordmark bottom-right on every frame; 15 s sting v2 | Approved on Ep01 |
| 2026-10-19 | Verified transcription (mlx-whisper) and silence cut (auto-editor 29.3.1) on Apple Silicon; Python pinned to 3.13; ffmpeg-full instead of ffmpeg | Plain Homebrew ffmpeg 9 lacks libass (no `subtitles` filter); torch has no Python 3.15 wheels |
| 2026-10-19 | clean-audio uses two-pass loudnorm; QA frame grabs convert to full-range before JPEG | ffmpeg 9 single-pass loudnorm undershot to -15.6 LUFS; ffmpeg 9 mjpeg rejects limited-range YUV |
| 2026-10-19 | Repo created with stages 0–4, 7, 9b, 10 built; Remotion graphics and face tracking planned | Build order: automate the boring parts first, graphics after episode 2 |
| 2026-10-19 | Pixel records locally at 4K as the main face camera; Mac camera optional second angle; sync by clap | Pixel USB webcam mode is capped at 1080p and softer; needs USB 2.0 cable on Mac |
| 2026-10-19 | OBS for recording (not Cap or Screen Studio) | Cap free is personal-use only with a 5-min limit; Screen Studio is paid |
| 2026-10-19 | DaVinci Resolve free as the editor; the repo replaces its Studio-only features (transcription, subtitles, voice cleanup, reframe) | Zero subscriptions |
| 2026-10-19 | Zero spend on app subscriptions; free / open-source only | Ayan's rule |
| 2026-10-13 | Brand: Ink #0E0E10, Paper #F2EFE6, Volt #D4FF3A, Signal #FF5B2E; Inter Black, Instrument Serif Italic, JetBrains Mono; ticket system WIB-00X | WIB brand decisions |
