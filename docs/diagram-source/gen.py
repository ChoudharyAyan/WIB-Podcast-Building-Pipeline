# Regenerate: python3 docs/diagram-source/gen.py, then copy podcast-making-workflow.html to docs/architecture.html
import html, pathlib
D = pathlib.Path(__file__).parent
INK = (D / "ink.b64").read_text(); PAPER = (D / "paper.b64").read_text()
e = html.escape

COLX = [40, 370, 700, 1030, 1360]; W = 230
LANES = ["Prep", "Shoot", "Process", "Render", "Deliver"]
# id, col, y, h, title, tools, outputs
ST = [
 ("0", 0, 90, 116, "Episode setup", "wib new", ["episode.json", "people, takes, sections"]),
 ("1", 0, 250, 136, "Outline or script", "Claude or Codex, Excalidraw", ["outline.md or script.md", "board PNGs, mascots"]),
 ("2", 1, 90, 116, "Studio setup, test take", "OBS, Pixel 4K, a mic each", ["60 s test synced", "framing set"]),
 ("3", 1, 250, 136, "Shoot", "OBS screen, Pixel, recorder", ["raw/ per take: screen,", "camera, guest mic", "one clap per take"]),
 ("4", 2, 90, 100, "Ingest and review", "wib ingest, review, frame", ["sync.json, review.md"]),
 ("5", 2, 220, 100, "Transcribe", "wib transcribe (mlx-whisper)", ["transcripts per speaker"]),
 ("6", 2, 350, 100, "Cut plan", "cuts.json, wib cutlist", ["cutlist.json"]),
 ("7", 2, 480, 120, "Sting and cards", "wib sting, wib cards", ["intro sting 16:9 and 9:16", "chapter cards"]),
 ("8", 3, 90, 136, "Output1 clean master", "wib output1", ["camera switching, auto-mix", "4K HEVC, −14 LUFS", "Output1.mp4 and .otio"]),
 ("9", 3, 280, 150, "Output2 YouTube cut", "wib output2, zooms.json", ["cards, gentle zooms, music", "4K HEVC, about −10.5 LUFS", "subtitles .srt"]),
 ("10", 3, 470, 130, "Instagram reels", "wib reels, reels.json", ["1080×1920 face, captions,", "B-roll card, chips"]),
 ("11", 4, 90, 136, "Covers and package", "wib covers, check, package", ["covers, thumbnail", "gates, chapters, previews"]),
]
B = {s[0]: s for s in ST}
def box(s):
    sid, c, y, h, title, tools, outs = s; x = COLX[c]
    o = [f'<g class="st"><rect x="{x}" y="{y}" width="{W}" height="{h}" rx="12" class="box"/>',
         f'<rect x="{x+14}" y="{y+14}" width="{24 if len(sid)<2 else 30}" height="20" rx="6" class="chip"/>',
         f'<text x="{x+14+(12 if len(sid)<2 else 15)}" y="{y+28.5}" class="chipt" text-anchor="middle">{sid}</text>',
         f'<text x="{x+(48 if len(sid)<2 else 54)}" y="{y+29}" class="tt">{e(title)}</text>',
         f'<text x="{x+14}" y="{y+54}" class="tools">{e(tools)}</text>']
    for i, t in enumerate(outs):
        o.append(f'<text x="{x+14}" y="{y+78+i*19}" class="out">{e(t)}</text>')
    o.append(f'<circle cx="{x+W-20}" cy="{y+h-20}" r="7" class="gate"/></g>')
    return "".join(o)
def mid_r(sid): s = B[sid]; return COLX[s[1]] + W, s[2] + s[3] / 2
def mid_l(sid): s = B[sid]; return COLX[s[1]], s[2] + s[3] / 2
def bot(sid): s = B[sid]; return COLX[s[1]] + W / 2, s[2] + s[3]
def top(sid): s = B[sid]; return COLX[s[1]] + W / 2, s[2]
def curve(a, b, label=None, dy=0, lx=None):
    (x1, y1), (x2, y2) = a, b
    mx = (x1 + x2) / 2
    p = f'<path d="M{x1},{y1} C{mx},{y1} {mx},{y2} {x2-4},{y2}" class="ar" marker-end="url(#ah)"/>'
    if label:
        p += f'<text x="{lx or mx}" y="{(y1+y2)/2+dy}" class="lbl" text-anchor="middle">{e(label)}</text>'
    return p
def vline(a, b, label=None):
    (x1, y1), (x2, y2) = a, b
    p = f'<path d="M{x1},{y1} L{x2},{y2-4}" class="ar" marker-end="url(#ah)"/>'
    if label: p += f'<text x="{x1+8}" y="{(y1+y2)/2+4}" class="lbl">{e(label)}</text>'
    return p

svg = ['<svg viewBox="0 0 1630 790" role="img" aria-labelledby="dt dd" xmlns="http://www.w3.org/2000/svg">',
       '<title id="dt">WIB podcast making pipeline</title><desc id="dd">Twelve stages in five lanes, from episode setup to the delivery folders, with the files passed between them.</desc>',
       '<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="ahp"/></marker></defs>']
for i, l in enumerate(LANES):
    x = COLX[i]
    svg.append(f'<text x="{x}" y="46" class="lane">{l}</text><line x1="{x}" y1="60" x2="{x+W}" y2="60" class="laneline"/>')
# arrows first so boxes sit on top
R = lambda c: COLX[c] + W
svg += [vline(bot("0"), top("1")),
        curve(mid_r("1"), mid_l("2"), "outline", -10),
        vline(bot("2"), top("3")),
        curve(mid_r("3"), mid_l("4"), "raw takes", 22),
        vline(bot("4"), top("5")), vline(bot("5"), top("6"), "who said what"), vline(bot("6"), top("7")),
        curve(mid_r("6"), mid_l("8"), "cut list", 40),
        curve((R(2), 530), mid_l("9"), "cards, music", 20),
        curve((R(2), 575), mid_l("10"), "vertical sting", 4),
        vline(bot("8"), top("9"), "same edit, effects on top"),
        curve(mid_r("8"), (COLX[4], 140)),
        curve(mid_r("9"), (COLX[4], 170)),
        curve(mid_r("10"), (COLX[4], 200)),
        vline(bot("11"), (COLX[4] + W / 2, 290))]
svg += [box(s) for s in ST]
# delivery folder
fx, fy = COLX[4], 290
svg.append(f'<rect x="{fx}" y="{fy}" width="{W}" height="296" rx="12" class="folder"/>')
svg.append(f'<text x="{fx+14}" y="{fy+28}" class="tt">Delivery folders</text>')
svg.append(f'<text x="{fx+14}" y="{fy+50}" class="out">~/Documents/Podcast WIB</text><text x="{fx+14}" y="{fy+68}" class="out">all files/EpNN/</text>')
rows = [("Output1 - without effects", "Output1.mp4, timeline .otio"), ("Output2 - with effects", "Output2.mp4, subtitles .srt"),
        ("Instagram videos", "reels, covers, captions"), ("YouTube", "thumbnail, title, chapters")]
for i, (a, b) in enumerate(rows):
    y = fy + 88 + i * 50
    svg.append(f'<rect x="{fx+12}" y="{y}" width="{W-24}" height="42" rx="8" class="row"/>')
    svg.append(f'<text x="{fx+24}" y="{y+18}" class="rt">{e(a)}</text><text x="{fx+24}" y="{y+34}" class="rs">{e(b)}</text>')
# shared band
by = 650
svg.append(f'<rect x="40" y="{by}" width="1550" height="110" rx="14" class="band"/>')
svg.append(f'<text x="64" y="{by+32}" class="lane">Shared by every stage</text>')
shared = [("brand/wib.json", "colours, fonts, caption style"), ("episode.json", "the one file that changes per episode"),
          ("HANDOFF-LOG.md", "STARTED, DONE or PAUSED per stage"), ("Quality gate", "format, loudness, decode, joins, privacy")]
for i, (a, b) in enumerate(shared):
    x = 64 + i * 380
    svg.append(f'<text x="{x}" y="{by+66}" class="out strong">{e(a)}</text><text x="{x}" y="{by+88}" class="tools">{e(b)}</text>')
svg.append(f'<circle cx="1552" cy="{by+28}" r="7" class="gate"/><text x="1538" y="{by+33}" class="tools" text-anchor="end">gate passed before the next stage</text>')
svg.append("</svg>")
SVG = "".join(svg)

CARDS = [
 ("0", "Episode setup", "Topic, guest, chapter guesses", "Episode folder and episode.json", "wib new", "episode.json parses"),
 ("1", "Pre-production", "Topic, guest, things to show", "Outline with a question and takeaway per chapter (or a script for solo), board, mascots", "Claude or Codex, Excalidraw", "Every chapter has a question and a takeaway"),
 ("2", "Studio setup and test take", "Mac, Pixel, two mics", "OBS scene, a synced 60 s test, framing values", "OBS, Pixel 4K on a tripod, phone recorder", "Offsets found, both mics −20 to −14 LUFS, faces sharp"),
 ("3", "Shoot", "Outline, prepared screen", "Screen, camera and guest mic per take", "OBS, Pixel, recorder", "Every file in episode.json exists and plays"),
 ("4", "Ingest and raw review", "raw/", "sync.json, review.md, framing stills", "wib ingest, wib review, wib frame", "Every take synced, no mic below −24 LUFS"),
 ("5", "Transcribe", "Each person's mic, glossary", "Word-timed transcripts with speakers, bleed removed", "wib transcribe (mlx-whisper large-v3-turbo)", "Names right, last word near the take's end"),
 ("6", "Cut plan", "Transcripts", "cuts.json, cutlist.json, chapters", "prompts/cut-plan.md, wib find, wib cutlist", "No clap or warm-up kept, no cut inside a word"),
 ("7", "Sting and cards", "episode.json, faces, music", "15 s sting in 16:9 and 9:16, 3 s chapter cards", "wib sting, wib cards", "Stills checked, licence logged"),
 ("8", "Output1 clean master", "Takes, cut list, sting", "4K master with camera switching and .otio", "wib output1", "wib check: −14 LUFS, decode clean, duration matches"),
 ("9", "Output2 YouTube cut", "Output1 edit, cards, music, zooms.json", "4K cut with effects and .srt", "wib output2", "wib check, zooms sharp, cards in silence"),
 ("10", "Instagram reels", "Transcripts, reels.json, vertical sting", "1080×1920 reels", "wib reels", "Topic in the first 2 s, under 90 s, private data blurred"),
 ("11", "Covers, checks, package", "Face stills, titles, every render", "Covers, thumbnail, title, description with chapters, previews", "wib covers, wib check, wib package", "wib check exits 0"),
]
cards = "".join(f'''<article class="card"><header><span class="num">{n}</span><h3>{e(t)}</h3></header>
<dl><dt>In</dt><dd>{e(i)}</dd><dt>Out</dt><dd>{e(o)}</dd><dt>Tools</dt><dd>{e(tl)}</dd><dt>Gate</dt><dd>{e(g)}</dd></dl></article>''' for n, t, i, o, tl, g in CARDS)

VALUES = [
 ("Long-form frame", "Screen scaled to 3216×2010 on a 3840×2160 ink canvas, WIB wordmark bottom-right in a footer band"),
 ("Output1 voice", "High-pass 80 Hz, light denoise, gentle compression, −14 LUFS"),
 ("Output2 and reel voice", "Tighter compression with warmth and clarity EQ, about −10.5 LUFS, no reverb or denoise"),
 ("Joins", "0.5 s crossfade between sections in Output1, 0.4 s dissolves in Output2, 30 ms audio fades at every cut"),
 ("Camera switching", "Each section opens wide for 3 s, then close-ups of whoever talks; runs under 2 s merge; a wide break in close-ups over 14 s"),
 ("Zooms", "One per agent slide, 1.2x to 1.4x, 2 s ease in and out, every slide box kept in frame"),
 ("Captions", "None burned into long form. An .srt for YouTube. Reels use 3-word kinetic captions"),
 ("Reel layout", "The speaker's face in a ring in their colour, captions in the middle, B-roll card below: screen or the listener's reaction"),
 ("Reel hook", "The first 2 s say the topic and who it's for. Longer reels open with the vertical sting"),
 ("Encodes", "Long form HEVC 30 to 40 Mbps, reels H.264 CRF 16, AAC 48 kHz"),
]
values = "".join(f"<div class=\"kv\"><dt>{e(k)}</dt><dd>{e(v)}</dd></div>" for k, v in VALUES)

page = (D / "template.html").read_text().replace("%%SVG%%", SVG).replace("%%CARDS%%", cards).replace("%%VALUES%%", values)\
    .replace("%%INK%%", INK).replace("%%PAPER%%", PAPER)
(D / "podcast-making-workflow.html").write_text(page)
print(len(page))
