"""Build the website from game.html.

game.html is the game as published on Claude (no <head>). This wraps it into a full
index.html for GitHub Pages, and optionally zips that for itch.io:

    python3 build.py                       # writes index.html, preview/index.html and full-cards/index.html
    python3 build.py ~/Desktop/snap-call-itch.zip   # also writes the zip
    python3 build.py --netlify ~/Desktop/snap-call-netlify.zip   # also zips full-cards/ as a whole site

preview/ is the card art version of the game (preview/game.html plus the card images in
preview/cards/). full-cards/ is the same game played with the finished printed cards. Both are
built next to the live game but never go into the itch zip. The Netlify zip holds full-cards/
on its own: index.html plus cards/, ready to drop onto Netlify.
"""
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESC = "A quick family football card game. Secretly call a play, the defense tries to guess it, first to 21 wins."
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E%3Crect width='40' height='40' rx='9' fill='%230f3d29'/%3E"
        "%3Cellipse cx='20' cy='20' rx='15' ry='9' fill='%238b4a29'/%3E%3Cpath d='M13 20h14M16 17.5v5M19 17.5v5M22 17.5v5M25 17.5v5' "
        "stroke='%23ecf3e8' stroke-width='1.6' stroke-linecap='round'/%3E%3C/svg%3E")


def build(folder, title):
    src = (folder / "game.html").read_text(encoding="utf-8")
    start = src.index('<link rel="preconnect"')
    split = src.index('<svg width="0"')
    head_assets, body = src[start:split].rstrip(), src[split:].rstrip()

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{DESC}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{DESC}">
<meta property="og:type" content="website">
<meta name="theme-color" content="#0a2c1d">
<link rel="icon" href="{ICON}">
{head_assets}
</head>
<body>
{body}
</body>
</html>
"""
    (folder / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {(folder / 'index.html').relative_to(HERE)}")


build(HERE, "Snap Call")
build(HERE / "preview", "Snap Call: card art preview")
build(HERE / "full-cards", "Snap Call")

args = sys.argv[1:]
if "--netlify" in args:
    i = args.index("--netlify")
    netlify = Path(args[i + 1]).expanduser()
    del args[i:i + 2]
    site = HERE / "full-cards"
    with zipfile.ZipFile(netlify, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(site / "index.html", "index.html")
        for f in sorted((site / "cards").glob("*.webp")):
            z.write(f, f"cards/{f.name}")
    print(f"wrote {netlify}")

if args:
    out = Path(args[0]).expanduser()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HERE / "index.html", "index.html")
    print(f"wrote {out}")
