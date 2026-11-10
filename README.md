# Snap Call

A quick family football card game, prototype A. Secretly call a play, the defense tries to guess it, first to 21 wins.

Play it: https://noam99moyal.github.io/snap-call/

Card art preview (same game, played with the printed card art): https://noam99moyal.github.io/snap-call/preview/

Finished 24-card deck and PNG downloads: https://noam99moyal.github.io/snap-call/artwork/

Played with the finished cards (rules printed on the cards): https://noam99moyal.github.io/snap-call/full-cards/

Downs test (2 downs per zone on a longer field, kept apart from the main game): https://noam99moyal.github.io/snap-call/downs/
Look preview (today's design with proposed wording and first-game tips, a Stopped once / Stopped twice choice at New game, and the one-screen phone layout): https://noam99moyal.github.io/snap-call/look/
One-screen phone layouts (the three mockups; B is now in the look preview): https://noam99moyal.github.io/snap-call/mockups/phone/

Ideas being tested or still open (Block Kick, the Challenge Flag, phone layouts): [IDEAS.md](IDEAS.md)

The Kick Field Goal choice card shows the existing Red Zone option: score 3 instead of snapping. Its artwork is available alongside the purple Field Goal score card.

The 15 play and special cards use the approved wording in `artwork/rules.json`, with exactly two lines on each cream panel. Field, Ball, and score cards are full art without a description panel. The Ball is a plain football without facial features.

## Updating

`game.html` is the game itself. After changing it, run `python3 build.py ~/Desktop/snap-call-itch.zip` to rebuild `index.html` (this website) and the zip for itch.io, then commit and push.

The preview lives in `preview/`: `preview/game.html` is its source and `preview/cards/` holds the card images. Each play and special card is two images, the art (`-top`) and its cream text panel (`-panel`), so the rules stay separate from the illustration. `build.py` rebuilds `preview/index.html` too; the preview never goes into the itch zip.

In the preview, rules remain live text separate from the artwork. Both rows share a font size measured against the longer row, and are refitted after fonts load and when the cards resize. This keeps the original 5:7 shape and two-line layout on phones as well as desktops. `artwork/cards/` contains the finished 1060 × 1484 PNGs for download; replace those independently of the split game assets.

`full-cards/` is the same game as the preview, but every card is the finished printed card from `artwork/cards/`, rules included, so the text always fits. `full-cards/cards/` holds 600px WebP copies with rounded corners. On the stage, a cream veil over a card's printed line fades the outcome that didn't happen. `python3 build.py --netlify ~/Desktop/snap-call-netlify.zip` also zips `full-cards/` as a site of its own for Netlify.

In `full-cards/`, New game asks Normal or Hard. Normal is the original computer. Hard reads your habits but starts from calls nobody can read, so tricking it doesn't pay, and it remembers your last few games on that device. `tools/cpu-sim/` simulates both against scripted players; check Hard there before changing it.

`downs/` is `full-cards/` with the rules being tested: 5 zones (Own 20, Own 35, Midfield, Their 35, Red Zone) where you can be stopped once and keep the ball (stopped twice in the same zone, they get it), a Deep Pass intercepted only on the second stop, the team that gets the ball second starting with 3 specials, a special drawn when you win the ball back, the Kick Field Goal card in your hand in the Red Zone, and a choice of first to 21, 28 or 35. It uses the card images in `full-cards/cards/`, except `downs/cards/`: stand-in field cards for the three new zones and test copies of the 6 play cards with "Stopped twice" added, until there's real art. `tools/rules-sim/downs.py` is the simulation behind these rules.

`look/` is `full-cards/` (the original rules) in today's design with proposed wording: varied announcer lines on the stage and in the play-by-play, a short How to play list in the cards' own words (Stopped / Not stopped instead of right / wrong guess), Offense / Defense over the hand, and a line under the field that only shows when it adds something (the CPU's field goal, and "stopped once" on Stopped twice). Two tips show every game until its first snap: the kickoff line says what to do, and your empty card spot says to pick a card and hold one to see it big. Who gets the ball first is random (on Stopped twice the other side starts with the third special), and the kickoff line says who. The wording is a proposal; nothing in it has gone into `downs/` or `full-cards/`. In `look/`, the Stopped once page also has the Kick Field Goal card in the Red Zone (instead of the button) and First to 21 / 28 / 35 at New game. `look/downs/` is the same for `downs/` (Stopped twice); the rules choice in New game moves between the two pages. `tools/look/make.py` rebuilds both pages from `full-cards/game.html` and `downs/game.html`. Both keep their own Hard memory. On portrait phones both pages use layout B from the mockups, so a whole snap fits on one screen with no scrolling: a thin score bar with a ⋯ menu (How to play, New game, Play by play), the field as a strip seen from above, the stage drawn on the field card of the zone the ball is in, and your hand along the bottom (plays, then specials, overlapping). Tap a card and it goes on the stage; the circle between the cards becomes the Snap button. Wide screens and landscape phones keep the old layout.
