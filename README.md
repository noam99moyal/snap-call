# Snap Call

A quick family football card game, prototype A. Secretly call a play, the defense tries to guess it, first to 21 wins.

Play it: https://noam99moyal.github.io/snap-call/

Card art preview (same game, played with the printed card art): https://noam99moyal.github.io/snap-call/preview/

Finished 23-card deck and PNG downloads: https://noam99moyal.github.io/snap-call/artwork/

Played with the finished cards (rules printed on the cards): https://noam99moyal.github.io/snap-call/full-cards/

The 15 play and special cards use the approved wording in `artwork/rules.json`, with exactly two lines on each cream panel. Field, Ball, and score cards are full art without a description panel. The Ball is a plain football without facial features.

## Updating

`game.html` is the game itself. After changing it, run `python3 build.py ~/Desktop/snap-call-itch.zip` to rebuild `index.html` (this website) and the zip for itch.io, then commit and push.

The preview lives in `preview/`: `preview/game.html` is its source and `preview/cards/` holds the card images. Each play and special card is two images, the art (`-top`) and its cream text panel (`-panel`), so the rules stay separate from the illustration. `build.py` rebuilds `preview/index.html` too; the preview never goes into the itch zip.

In the preview, rules remain live text separate from the artwork. Both rows share a font size measured against the longer row, and are refitted after fonts load and when the cards resize. This keeps the original 5:7 shape and two-line layout on phones as well as desktops. `artwork/cards/` contains the finished 1060 × 1484 PNGs for download; replace those independently of the split game assets.

`full-cards/` is the same game as the preview, but every card is the finished printed card from `artwork/cards/`, rules included, so the text always fits. `full-cards/cards/` holds 600px WebP copies with rounded corners. On the stage, a cream veil over a card's printed line fades the outcome that didn't happen. `python3 build.py --netlify ~/Desktop/snap-call-netlify.zip` also zips `full-cards/` as a site of its own for Netlify.

In `full-cards/`, New game asks Normal or Hard. Normal is the original computer. Hard reads your habits but starts from calls nobody can read, so tricking it doesn't pay, and it remembers your last few games on that device. `tools/cpu-sim/` simulates both against scripted players; check Hard there before changing it.
