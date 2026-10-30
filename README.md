# Snap Call

A quick family football card game, prototype A. Secretly call a play, the defense tries to guess it, first to 21 wins.

Play it: https://noam99moyal.github.io/snap-call/

Card art preview (same game, played with the printed card art): https://noam99moyal.github.io/snap-call/preview/

Finished 23-card deck and PNG downloads: https://noam99moyal.github.io/snap-call/artwork/

The 15 play and special cards use the approved wording in `artwork/rules.json`, with exactly two lines on each cream panel. Field, Ball, and score cards are full art without a description panel. The Ball is a plain football without facial features.

## Updating

`game.html` is the game itself. After changing it, run `python3 build.py ~/Desktop/snap-call-itch.zip` to rebuild `index.html` (this website) and the zip for itch.io, then commit and push.

The preview lives in `preview/`: `preview/game.html` is its source and `preview/cards/` holds the card images. Each play and special card is two images, the art (`-top`) and its cream text panel (`-panel`), so the rules stay separate from the illustration. `build.py` rebuilds `preview/index.html` too; the preview never goes into the itch zip.

In the preview, rules remain live text separate from the artwork. Both rows share a font size measured against the longer row, and are refitted after fonts load and when the cards resize. This keeps the original 5:7 shape and two-line layout on phones as well as desktops. `artwork/cards/` contains the finished 1060 × 1484 PNGs for download; replace those independently of the split game assets.
