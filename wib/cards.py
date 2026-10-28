"""Stage 7: section cards, 3 s, 1920x1080 (approved on Ep01 as the agent cards).

episode.json sections[].card = {"tag": "Agent 01", "line": "Saves 10–15 hours of status reports a week",
                                "mascot": "nova", "colour": "#9B6BFF"}
The title is the section's title. With no mascot (a conversation chapter) the left side shows the
tag's number large instead. The line must be something said in the episode, never invented.
"""

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw

from .episode import Episode
from .graphics import INK, VOLT, Encoder, back, eo, font, hexc, mascot, paste, text_im

FPS, DUR = 30, 3.0


def render_card(sec: dict, out: Path) -> Path:
    card = sec["card"]
    col = hexc(card.get("colour", "volt"))
    M = mascot(card["mascot"]) if card.get("mascot") else None
    num = re.findall(r"\d+", card.get("tag", ""))
    BIG = text_im(num[-1] if num else "", font("Inter.ttf", 420, 900), col) if not M else None
    NUM = text_im(card.get("tag", "").upper(), font("JBMono.ttf", 40, 700), VOLT)
    TI = text_im(sec.get("title", ""), font("Lilita.ttf", 96), col)
    sc_ti = min(1.0, 980 / TI.width)
    LI = text_im(card.get("line", ""), font("Inter.ttf", 40, 500), (190, 190, 198))
    sc_li = min(1.0, 980 / LI.width)
    enc = Encoder(out, (1920, 1080), FPS, crf=14)
    for i in range(int(DUR * FPS)):
        t = i / FPS
        img = Image.new("RGBA", (1920, 1080), INK + (255,))
        d = ImageDraw.Draw(img)
        d.rectangle((0, 1040, 1920 * eo(t / 0.5), 1080), fill=col)  # colour bar sweeps in
        if M:
            paste(img, M, 520, 540 + 6 * math.sin(t * 4), sc=1.9 * back((t - 0.1) / 0.5))
        elif BIG:
            paste(img, BIG, 470, 540, sc=back((t - 0.1) / 0.5))
        paste(img, NUM, 860 + NUM.width / 2, 400, a=eo((t - 0.35) / 0.4))
        paste(img, TI, 860 + TI.width * sc_ti / 2, 520, sc=sc_ti * back((t - 0.45) / 0.45))
        paste(img, LI, 860 + LI.width * sc_li / 2, 640, sc=sc_li, a=eo((t - 0.7) / 0.4))
        enc.write(img)
    enc.close()
    return out


def run(episode_id: str) -> list[Path]:
    ep = Episode(episode_id)
    outs = []
    for sec in ep["sections"]:
        if sec.get("card"):
            outs.append(render_card(sec, ep.edit / "cards" / f"{sec['id']}.mp4"))
            print(f"card {sec['id']}: {outs[-1]}")
    if not outs:
        print("No section has a card in episode.json.")
    return outs
