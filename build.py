"""Build the website from game.html.

game.html is the game as published on Claude (no <head>). This wraps it into a full
index.html for GitHub Pages, and optionally zips that for itch.io:

    python3 build.py                       # writes classic/index.html, look/index.html, preview/, full-cards/ and downs/
    python3 build.py ~/Desktop/snap-call-itch.zip   # also writes the zip
    python3 build.py --netlify ~/Desktop/snap-call-netlify.zip   # also zips full-cards/ as a whole site
    python3 build.py --netlify-downs ~/Desktop/snap-call-netlify-downs.zip   # the downs test as a whole site
    python3 build.py --netlify-look ~/Desktop/snap-call-netlify-look.zip     # the look preview as a whole site
    python3 build.py --app-web ios/SnapCall/web   # the look preview for the iPhone app (Xcode runs this itself)

look/ is the game as it will ship: look/game.html (both rule sets, Stopped once and Stopped twice) plus look/rules.js
(the snap rules on their own, with no screen code, so a server can run the same rules for online play; look/index.html
carries a copy inside, so the published page is still one file). It uses the
card images of full-cards/cards/ and, for Stopped twice, downs/cards/. look/downs/ only forwards to look/?rules=twice.

preview/ is the card art version of the game (preview/game.html plus the card images in
preview/cards/). full-cards/ is the same game played with the finished printed cards. downs/ is
full-cards with a test of 2 downs on a longer field. All are built next to the live game but
never go into the itch zip. The Netlify zip holds full-cards/
on its own: index.html plus cards/, ready to drop onto Netlify. The downs Netlify zip is the same for
downs/: its own cards replace full-cards' cards of the same name, and its paths to ../full-cards/cards/
point at cards/.
"""
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESC = "A quick family football card game. Secretly call a play, the defense tries to guess it, first to 21 wins."
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E%3Crect width='40' height='40' rx='9' fill='%230f3d29'/%3E"
        "%3Cellipse cx='20' cy='20' rx='15' ry='9' fill='%238b4a29'/%3E%3Cpath d='M13 20h14M16 17.5v5M19 17.5v5M22 17.5v5M25 17.5v5' "
        "stroke='%23ecf3e8' stroke-width='1.6' stroke-linecap='round'/%3E%3C/svg%3E")


def build(folder, title, out=None):
    src = (folder / "game.html").read_text(encoding="utf-8")
    start = src.index('<link rel="preconnect"')
    split = src.index('<svg width="0"')
    head_assets, body = src[start:split].rstrip(), src[split:].rstrip()
    # look/: the snap rules live in rules.js; the published page carries them inside, so it stays one file and the
    # game can't start without its rules.
    tag = '<script src="rules.js"></script>'
    if tag in body:
        body = body.replace(tag, "<script>\n" + (folder / "rules.js").read_text(encoding="utf-8").rstrip() + "\n</script>")

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
    out = out or folder / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out.relative_to(HERE)}")


# The main address now opens the look version: index.html at the top only forwards to look/ (it is written by hand,
# not built). The first version of the game, game.html, moved to classic/.
build(HERE, "Snap Call: first version", HERE / "classic" / "index.html")
build(HERE / "preview", "Snap Call: card art preview")
build(HERE / "full-cards", "Snap Call")
build(HERE / "downs", "Snap Call: downs test")
build(HERE / "look", "Snap Call")

# Netlify tells browsers to re-check every file before using it again. The game redraws cards as you pick them,
# so on Netlify every card image was re-checked and the screen flashed. Card images may now be kept for a day.
NETLIFY_HEADERS = """/cards/*
  Cache-Control: public, max-age=86400
/downs/cards/*
  Cache-Control: public, max-age=86400
"""

args = sys.argv[1:]
if "--netlify" in args:
    i = args.index("--netlify")
    netlify = Path(args[i + 1]).expanduser()
    del args[i:i + 2]
    site = HERE / "full-cards"
    with zipfile.ZipFile(netlify, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(site / "index.html", "index.html")
        z.writestr("_headers", NETLIFY_HEADERS)
        for f in sorted((site / "cards").glob("*.webp")):
            z.write(f, f"cards/{f.name}")
    print(f"wrote {netlify}")

if "--netlify-downs" in args:
    i = args.index("--netlify-downs")
    netlify = Path(args[i + 1]).expanduser()
    del args[i:i + 2]
    cards = {f.name: f for f in sorted((HERE / "full-cards" / "cards").glob("*.webp"))}
    cards.update({f.name: f for f in sorted((HERE / "downs" / "cards").glob("*.webp"))})
    page = (HERE / "downs" / "index.html").read_text(encoding="utf-8").replace("../full-cards/cards/", "cards/")
    with zipfile.ZipFile(netlify, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.html", page)
        z.writestr("_headers", NETLIFY_HEADERS)
        for name, f in sorted(cards.items()):
            z.write(f, f"cards/{name}")
    print(f"wrote {netlify}")

def look_site():
    """The look preview as a whole site: the page with its card paths made local, both card folders, and
    downs/index.html forwarding to ?rules=twice like look/downs/."""
    page = ((HERE / "look" / "index.html").read_text(encoding="utf-8")
            .replace("../full-cards/cards/", "cards/").replace("../downs/cards/", "downs/cards/"))
    assert "../full-cards/" not in page and "../downs/" not in page, "a card path out of look/ is left in the page"
    files = {"index.html": page.encode(), "downs/index.html": (HERE / "look" / "downs" / "index.html").read_bytes()}
    for f in sorted((HERE / "full-cards" / "cards").glob("*.webp")):
        files[f"cards/{f.name}"] = f
    for f in sorted((HERE / "downs" / "cards").glob("*.webp")):
        files[f"downs/cards/{f.name}"] = f
    return files


if "--netlify-look" in args:
    i = args.index("--netlify-look")
    netlify = Path(args[i + 1]).expanduser()
    del args[i:i + 2]
    with zipfile.ZipFile(netlify, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("_headers", NETLIFY_HEADERS)
        for name, data in look_site().items():
            z.write(data, name) if isinstance(data, Path) else z.writestr(name, data)
    print(f"wrote {netlify}")

if "--app-web" in args:
    # The iPhone app (ios/): the same files as the Netlify look site, written to a folder the app bundles. The app
    # serves them itself, so the saved Hard memory works as on the website. Two app-only tweaks: no pinch zoom, and
    # no iOS copy/save menu when you hold a card (the game uses holding to show it big).
    import shutil
    i = args.index("--app-web")
    web = Path(args[i + 1]).expanduser()
    del args[i:i + 2]
    viewport = '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    app_head = ('<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, '
                'viewport-fit=cover">\n<style>html { -webkit-touch-callout: none; -webkit-user-select: none; user-select: none;'
                ' -webkit-tap-highlight-color: transparent; touch-action: manipulation; }</style>')
    if web.exists():
        shutil.rmtree(web)
    for name, data in look_site().items():
        (web / name).parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, Path):
            shutil.copy2(data, web / name)
        elif name == "index.html":
            page = data.decode()
            assert page.count(viewport) == 1, name
            (web / name).write_text(page.replace(viewport, app_head), encoding="utf-8")
        else:
            (web / name).write_bytes(data)
    print(f"wrote {web}")

if args:
    out = Path(args[0]).expanduser()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HERE / "classic" / "index.html", "index.html")
    print(f"wrote {out}")
