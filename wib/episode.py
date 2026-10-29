"""episode.json: the one file that changes between episodes. Everything else reads it through here.

Times everywhere in the pipeline are in a take's *reference clock* (the take's reference file,
usually the OBS screen recording, or the camera when there is no screen). `wib ingest` measures
how far every other file of the take is offset from that clock.
"""

import json
from functools import cached_property
from pathlib import Path

from . import BRAND, ROOT, edit_dir, episode_dir

DEFAULTS = {
    "format": "solo",
    "canvas": [3840, 2160],
    "fps": 30,
    "zoom_max": 1.2,
    "camera_grade": "eq=brightness=0.02:contrast=1.04:saturation=1.06",
    "bubble": {"x": 56, "y": 1104, "size": 440, "face": [91, 1112, 370]},
    "names": {},
    "framing": {},
    "sections": [],
    "people": {"host": {"name": "Ayan", "role": "Host", "colour": "volt"}},
}

PERSON_COLOURS = {"volt": "#D4FF3A", "signal": "#FF5B2E", "violet": "#9B6BFF", "teal": "#2DD4BF", "amber": "#FFB020"}


class Episode:
    def __init__(self, episode_id: str):
        self.id = episode_id
        self.dir = episode_dir(episode_id)
        self.raw = self.dir / "raw"
        self.edit = edit_dir(episode_id)
        path = self.dir / "episode.json"
        if not path.exists():
            raise SystemExit(f"{path} is missing. Copy one from episodes/_template/ and fill it in (WORKFLOW.md stage 0).")
        self.data = {**DEFAULTS, **json.loads(path.read_text())}
        if not self.data.get("takes"):
            raise SystemExit("episode.json has no takes. List every recording under \"takes\".")

    # ---------- basics ----------
    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def conversation(self) -> bool:
        return self.data["format"] == "conversation"

    @property
    def W(self) -> int:
        return int(self.data["canvas"][0])

    @property
    def H(self) -> int:
        return int(self.data["canvas"][1])

    @property
    def fps(self) -> int:
        return int(self.data["fps"])

    @property
    def scale(self) -> float:
        """Canvas size relative to 4K. Every pixel constant tuned on Ep01's 4K master is multiplied by this."""
        return self.W / 3840

    @property
    def people(self) -> dict:
        return self.data["people"]

    def person_colour(self, pid: str) -> str:
        c = self.people.get(pid, {}).get("colour", "volt")
        return PERSON_COLOURS.get(c, c)

    @property
    def host(self) -> str:
        return next((k for k, v in self.people.items() if v.get("role", "").lower() == "host"), next(iter(self.people)))

    # ---------- takes ----------
    @cached_property
    def takes(self) -> dict:
        out = {}
        for t in self.data["takes"]:
            t = dict(t)
            if "mics" not in t:  # solo: the host's mic is in the reference file
                t["mics"] = {self.host: t.get("screen") or t.get("camera")}
            t.setdefault("reference", "screen" if t.get("screen") else "camera")
            out[t["id"]] = t
        return out

    def take_people(self, take: str) -> list[str]:
        """Everyone heard in a take: each person with a mic, plus, when the take has a shared "voice"
        track, the one person without a mic of their own."""
        t = self.takes[take]
        if not t.get("voice"):
            return list(t["mics"])
        rest = [p for p in self.people if p not in t["mics"]]
        if len(rest) != 1:
            raise SystemExit(f'Take {take} has a "voice" track: give every person but one a detection mic under "mics" '
                             f"(people without one: {', '.join(rest) or 'none'}).")
        return [p for p in self.people if p in t["mics"] or p in rest]

    def take_ids(self) -> list[str]:
        return list(self.takes)

    def file(self, take: str, role: str) -> Path | None:
        """role: screen, camera, or mic:<person>."""
        t = self.takes[take]
        name = t["mics"].get(role[4:]) if role.startswith("mic:") else t.get(role)
        return self.raw / name if name else None

    def reference_file(self, take: str) -> Path:
        return self.file(take, self.takes[take]["reference"])

    @cached_property
    def sync(self) -> dict:
        path = self.edit / "sync.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def offset(self, take: str, role: str) -> float:
        """Seconds to add to a reference-clock time to get the same moment in that file."""
        f = self.file(take, role)
        if f is None or f == self.reference_file(take):
            return 0.0
        try:
            return float(self.sync[take]["offsets"][f.name])
        except KeyError:
            raise SystemExit(f"No sync offset for {f.name} in take {take}. Run `uv run wib ingest {self.id}` first.")

    # ---------- sections ----------
    def section(self, sid: str) -> dict:
        for s in self.data["sections"]:
            if s["id"] == sid:
                return s
        return {"id": sid, "title": sid}

    # ---------- edit files ----------
    def read(self, name: str, required: bool = True, hint: str = ""):
        path = self.edit / name
        if not path.exists():
            if required:
                raise SystemExit(f"edit/{name} is missing. {hint}".strip())
            return None
        return json.loads(path.read_text())

    def write(self, name: str, data) -> Path:
        path = self.edit / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        return path

    def transcript(self, take: str) -> dict:
        return self.read(f"transcripts/{take}.json", hint=f"Run `uv run wib transcribe {self.id}`.")

    def words(self, take: str) -> list[dict]:
        """Every word of a take in reference-clock order, with `speaker` set."""
        ws = []
        for s in self.transcript(take)["segments"]:
            for w in s["words"]:
                ws.append({**w, "word": self.fix_names(w["word"].strip()), "speaker": w.get("speaker", s.get("speaker", self.host))})
        return sorted(ws, key=lambda w: w["start"])

    def fix_names(self, text: str) -> str:
        for a, b in self.data["names"].items():
            text = text.replace(a, b)
        return text

    # ---------- assets and delivery ----------
    def asset(self, rel: str) -> Path:
        """Paths in episode.json are relative to the episode folder, else to the repo root."""
        for base in (self.dir, ROOT, BRAND):
            p = base / rel
            if p.exists():
                return p
        raise SystemExit(f"Asset not found: {rel} (looked in the episode folder, the repo root and brand/).")

    @property
    def delivery(self) -> Path:
        root = self.data.get("delivery_root") or f"~/Documents/Podcast WIB all files/Ep{self.data.get('number', '00')}"
        return Path(root).expanduser()

    def deliver_dir(self, kind: str) -> Path:
        names = {"output1": "Output1 - without effects", "output2": "Output2 - with effects long form",
                 "reels": "Instagram videos", "youtube": "YouTube"}
        d = self.delivery / names[kind]
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def tag(self) -> str:
        return f"WIB-Ep{self.data.get('number', '00')}"
