# Snap Call

A quick family football card game, prototype A. Secretly call a play, the defense tries to guess it, first to 21 wins.

Play it: https://noam99moyal.github.io/snap-call/

Card art preview (same game, played with the printed card art): https://noam99moyal.github.io/snap-call/preview/

## Updating

`game.html` is the game itself. After changing it, run `python3 build.py ~/Desktop/snap-call-itch.zip` to rebuild `index.html` (this website) and the zip for itch.io, then commit and push.

The preview lives in `preview/`: `preview/game.html` is its source and `preview/cards/` holds the card images. Each play and special card is two images, the art (`-top`) and its cream text panel (`-panel`), so the panel can grow on narrow cards. `build.py` rebuilds `preview/index.html` too; the preview never goes into the itch zip.
