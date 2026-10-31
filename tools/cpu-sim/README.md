# CPU simulator

Plays thousands of Snap Call games between a computer and scripted players, to check how hard each computer is
and whether it can be tricked. The rules match `full-cards/game.html`.

- `cpu_sim.py` has the game, the computers and the players. `Normal` is the game's Normal computer. `Hard2` is the
  game's Hard computer. `Hard` is a first try, kept because it shows the trap: reading habits without a safe
  fallback lets someone who reads it back win almost 90%.
- `python3 final.py` prints each player's win rate against Normal and Hard.
- `python3 memory.py` plays ten-game series, to show what remembering past games adds.
- `./check-game-code.sh` runs the Hard code from the game itself (macOS) and should give the same numbers as `memory.py`.

Results from 2026-10-31 (player win %, games 2 to 10 of ten-game series):

| Player | Normal | Hard (remembers) |
|---|---|---|
| Mixes at random | 53 | 51 |
| Has a favorite play | 38 | 37 |
| Same call in each zone | 50 | 25 |
| Goes in order (Run, Short, Deep…) | 64 | 0.3 |
| Trickster: 3 Runs, then 2 passes | 40 | 2 |
| Trickster: calls what it hasn't lately | 65 | 29 |
| Trickster: reads the CPU back | 51 | 33 |
| Two people share one phone | 47 | 44 |
| Knows the CPU's exact odds (worst case) | 74 | 64 |
