# raw/: the recordings (never edited by the pipeline)

Name files `<take>-<role>`, and list them under `takes` in episode.json.

Solo (Ep01 setup)
- `<take>-screen.mp4`: OBS screen with the face bubble and your mic. This is the sync reference.

Same room, two people (Ep02 setup, full guide in WORKFLOW.md stage 1)
- `<take>-screen.mp4`: OBS screen + Ayan's mic. Reference clock.
- `<take>-camera.mp4`: the Pixel on a tripod, 4K 30 fps, both of you in frame, recorded on the phone.
- `<take>-yash-phone.m4a`: Voice Memos on Yash's phone, face-down near him. With one wireless receiver
  mixing both mics into the OBS file, this is only used to tell who is talking (`"voice"` in episode.json).
  With separate mic tracks, it's his mic file instead.
- `<take>-yash-screen.mov`: optional, Yash's own screen recording (`"screen2"`).

At the start of every take: everything recording, then ONE loud clap in view of the camera.
