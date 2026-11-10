#!/usr/bin/env python3
"""Snap Call: specials at the start, on both rule sets.

Two rules from the Stopped twice test, each on and off:
  - the side that gets the ball second starts with 3 specials instead of 2;
  - a stop that wins the ball back (stopped twice, interception, Forced Fumble) draws a special.
Same model as downs.py (both sides call plays at random, specials with the game's CPU habits).

Result (40,000 games each, first to 21; 28 and 35 read the same):
  Stopped twice: the side with the ball first wins 56.7% with neither, 53.6% with the third special,
  55.8% with only the stop draw. The stop draw adds about one special per game and a few less close games.
  Stopped once: 53.1% today, 50.6% with the third special.
So the look preview gives the side that gets the ball second a third special on both rule sets and has no stop draw.

Usage: python3 start_specials.py [games per row]
"""
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from downs import DECK, PLAYS, GAIN, off_special, def_special, resolve  # noqa: E402


def play_game(rng, zones, downs, deep_int, target, today_kicks, second_extra=False, stop_draw=False):
    red, mid = zones - 1, zones // 2
    score = {'A': 0, 'B': 0}
    other = {'A': 'B', 'B': 'A'}
    deck = DECK[:]
    rng.shuffle(deck)
    discard = []
    hands = {'A': [], 'B': []}
    g = {'snaps': 0, 'played': 0, 'full_draws': 0, 'max_behind': {'A': 0, 'B': 0}, 'specials_at_end': 0}

    def draw(w):
        nonlocal deck, discard
        if len(hands[w]) >= 3:
            g['full_draws'] += 1
            return
        if not deck:
            deck, discard = discard, []
            rng.shuffle(deck)
        if deck:
            hands[w].append(deck.pop())

    for _ in range(2):
        draw('A')
        draw('B')
    if second_extra:
        draw('B')
    poss, pos, down = 'A', 0, 1

    def scores(w, pts):
        nonlocal poss, pos, down
        score[w] += pts
        for t in 'AB':
            g['max_behind'][t] = max(g['max_behind'][t], score[other[t]] - score[t])
        if score[w] >= target:
            return True
        poss, pos, down = other[w], 0, 1
        draw(poss)
        return False

    def turnover(new_pos):
        nonlocal poss, pos, down
        poss, pos, down = other[poss], new_pos, 1
        if stop_draw:
            draw(poss)

    for _ in range(2000):
        if pos == red:
            need3 = target - score[poss] <= 3
            kick = (need3 or rng.random() < 0.45) if today_kicks else (need3 or down == downs)
            if kick:
                g['snaps'] += 1
                if scores(poss, 3):
                    break
                continue
        g['snaps'] += 1
        offw, defw = poss, other[poss]
        o, d = rng.choice(PLAYS), rng.choice(PLAYS)
        osp = off_special(rng, hands[offw], o, pos, zones)
        dsp = def_special(rng, hands[defw], d)
        for w, c in ((offw, osp), (defw, dsp)):
            if c:
                hands[w].remove(c)
                g['played'] += 1
        kind, z = resolve(o, osp, d, dsp)
        for side, w, c in (('off', offw, osp), ('def', defw, dsp)):
            if c:
                (hands[w] if kind == 'replay' and z != side else discard).append(c)
        if kind == 'replay':
            continue
        if kind == 'int' and (deep_int == 'never' or (deep_int == 'last' and down < downs)):
            kind = 'stop'
        if kind == 'gain':
            pos += z
            down = 1
            if pos >= zones and scores(offw, 7):
                break
        elif kind == 'td':
            if scores(offw, 7):
                break
        elif kind == 'stop':
            if down < downs:
                down += 1
            else:
                turnover(0)
        elif kind in ('int', 'fumble'):
            turnover(mid)
        elif kind == 'sack':
            if pos > 0:
                pos -= 1
                down = 1
        elif kind == 'pick6':
            if scores(defw, 7):
                break
    winner = 'A' if score['A'] > score['B'] else 'B'
    g['first_wins'] = winner == 'A'
    g['comeback7'] = g['max_behind'][winner] >= 7
    g['margin'] = abs(score['A'] - score['B'])
    return g


def line(name, games):
    n = len(games)
    return (f"{name:<44} first team wins {sum(g['first_wins'] for g in games)/n*100:4.1f}%  "
            f"snaps {statistics.median(g['snaps'] for g in games):3.0f}  "
            f"specials played {statistics.mean(g['played'] for g in games):4.1f}  "
            f"close (7 or less) {sum(g['margin'] <= 7 for g in games)/n*100:4.1f}%  "
            f"comeback 7+ {sum(g['comeback7'] for g in games)/n*100:4.1f}%")


TWICE = dict(zones=5, downs=2, deep_int='last', today_kicks=False)
ONCE = dict(zones=3, downs=1, deep_int='now', today_kicks=True)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
for target in ((21, 28, 35) if __name__ == '__main__' else ()):
    print(f"--- first to {target}")
    rows = [
        ('Stopped twice: neither', dict(TWICE, target=target)),
        ('Stopped twice: 3 specials for 2nd team only', dict(TWICE, target=target, second_extra=True)),
        ('Stopped twice: stop draw only', dict(TWICE, target=target, stop_draw=True)),
        ('Stopped twice: both (before 2026-11-10)', dict(TWICE, target=target, second_extra=True, stop_draw=True)),
        ('Stopped once: today', dict(ONCE, target=target)),
        ('Stopped once: 3 specials for 2nd team', dict(ONCE, target=target, second_extra=True)),
        ('Stopped once: with a stop draw', dict(ONCE, target=target, stop_draw=True)),
    ]
    for i, (name, kw) in enumerate(rows):
        rng = random.Random(7000 + target * 10 + i)
        print(line(name, [play_game(rng, **kw) for _ in range(N)]))
