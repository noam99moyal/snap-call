# Ideas

Ideas we're trying or still deciding on. Nothing here is in the game until it's built into `full-cards/` or `downs/`.

## Block Kick: a defense card for the Red Zone

**Status:** being tested with players. The wording below is agreed for testing.

**The problem.** In the Red Zone, the offense can play Kick Field Goal instead of a play, and it always scores 3. Near the end of a game, reaching the Red Zone when 3 points are enough is a sure win, and the defense can't do anything about it.

**The idea.** When the other side is in the Red Zone, the defense also has a Block Kick card. It's red, like the other defense cards. You pick it in secret, like a Stop card, and both cards flip at once.

| Offense plays | Defense plays a Stop card | Defense plays Block Kick |
| --- | --- | --- |
| Kick Field Goal | It's good: 3 points | Blocked: no points, and the defense gets the ball at its own 25 |
| Run or a pass | Same as today: stopped or not stopped | Not stopped: touchdown |

**Agreed details:**

- Block Kick card text: "✓ They kick: your ball / ✕ They run or pass: touchdown". The art is still to come.
- A blocked kick gives the defense the ball at its own 25.
- No specials can be played with a kick or a block.
- The Kick Field Goal card changes to "Not blocked: score 3 / Blocked: their ball".

**What the simulation says** (`tools/rules-sim/block_kick.py`):

- Kicking is almost never the better call. A play in the Red Zone scores 7 about 2 times in 3, and being stopped there costs nothing extra.
- The real problem is the ending. With the CPU kicking 45% of the time, a game reaches the Red Zone needing 3 or less this often:
  - first to 21: 1 game in 5
  - first to 28: 1 game in 4
  - first to 35: 1 game in 3
- Today that's a sure win. With Block Kick, the kicking side still wins that spot about 85% of the time.
- Games don't get longer.

## Challenge Flag: keep the other side's special a secret

**Status:** being tested with players.

**Today.** If you lose the snap, the Challenge Flag cancels it and both sides pick again. If the other side played a special on that snap, it goes back to their hand.

**The problem.** You've now seen their special, and they still have it. You know what's coming.

**The idea.** They shuffle that special into the deck and draw a new card. Nobody loses a card, and their hand is a secret again.

**A faster version.** If shuffling in the middle of a game is too slow, they slide the card under the deck and draw from the top.

**Other options testers are comparing:**

- Back to their hand (today).
- Used up: it goes to the discard pile like any played special. This is simpler, but the flag costs them a card.

**What the simulation says** (`tools/rules-sim/flag.py`):

- A flag cancels a snap about 0.44 times per game.
- The other side had played a special in only 16% of those snaps.
- Changing what happens to that special barely changes how strong the flag is (less than half a point of win rate). So pick whichever rule feels fairest at the table.

## One screen per snap on phones

**Status:** mockups to try: https://noam99moyal.github.io/snap-call/mockups/phone/ (open it on a phone).

**The problem.** A tester said he has to scroll down to pick his cards and back up to see what happened, every snap. On a phone that shows 390 × 664, the look preview is about 1,490px tall:

- The stage runs from 371 to 685.
- The play cards start at 723, below the bottom of the screen.
- The specials start at 938.

**Three mockups.** Each fits a whole snap with no scrolling, on a usual phone (390 × 664) and on a small one (iPhone SE, 375 × 553). They play a cut-down Stopped once game.

- **A · Compact.** Same order as today, everything smaller:
  - The scoreboard and the field become two thin rows.
  - The line under the field moves into the stage.
  - The specials become gold buttons with the card's rule written out.
  - Snap stays at the bottom.
  - This is the smallest change. Play cards are about 140px tall instead of about 160px.
- **B · Snap in the middle.**
  - The hand sits along the bottom, overlapping like cards in your hand: plays first, then specials.
  - Tap a card and it goes into your spot on the stage, and the VS circle turns into the Snap button. You pick, check and snap in the same place.
  - This gives the biggest cards: about 200px on the stage and 165px in the hand. The cards in the hand overlap, so you read the one you picked on the stage.
- **C · Pick, then reveal.**
  - The screen is your hand, with cards about today's size.
  - When you snap, both cards flip big over the whole screen with the result, then it goes back to your hand. The last result stays in one line at the top.
  - Easiest to read while you pick, but you don't see the stage while you pick.

**Changes that help whichever layout we pick:**

- Rules, New game and the play-by-play go into one ⋯ menu, so the header isn't a whole row on its own.
- The score and "First to" share one thin bar.
- The field row shows small tiles with the ball on the current zone.
- Empty special slots aren't drawn. The rules already say you draw one when you're scored on.

## Still open

- **Field goals:** keep the sure kick, add Block Kick, or drop field goals.
- **Stopped twice:**
  - Show a "Last try" tag on the field after the first stop.
  - Have the CPU save its specials for the last try.
- **Forced Fumble** looks weak in the simulations (about −3.6% for the side that starts with it). Part of that is the CPU playing it too often.
- **Main game:** bring the look preview's wording and first-game tips into `full-cards/` and `downs/`.
