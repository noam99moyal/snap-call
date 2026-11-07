#!/usr/bin/env python3
"""Snap Call (Stopped once): what happens to the other side's special when a Challenge Flag cancels the snap.

Today ("back"):  it goes back to its owner's hand, so the flag thrower has now seen it.
Used up ("used"): it is used up like any other played special, so the flag also burns it.

Plays and guesses use the best odds from block_kick.py (today's rules, the CPU kicking 45% of the time in the
Red Zone); specials are played with the CPU's habits, the flag 1 time in 5 while you hold one. The flag fires
only when its side loses the snap.

A card's worth: how much more often a team wins when it starts with that card (plus one random special) than with
two random specials. The team with the ball first, which wins about 53% anyway, is the one tested.

    python3 tools/rules-sim/flag.py          # 40000 games per line
"""
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from block_kick import DECK, RED, best_odds, def_special, off_special, pick, resolve  # noqa: E402

NAMES = {'juke': 'Juke', 'grab': 'Spectacular Catch', 'sack': 'Sack', 'tfl': 'Tackle for Loss', 'flag': 'Challenge Flag',
         'breakaway': 'Breakaway', 'hail': 'Hail Mary', 'picksix': 'Pick Six', 'fumble': 'Forced Fumble'}


def play_game(rng, odds, rule, start=None, target=21):
    score = {'A': 0, 'B': 0}
    other = {'A': 'B', 'B': 'A'}
    deck = DECK[:]
    if start:
        deck.remove(start)
    rng.shuffle(deck)
    discard = []
    hands = {'A': [start] if start else [], 'B': []}
    stats = {'flags': 0, 'other': Counter()}

    def draw(w):
        nonlocal deck, discard
        if len(hands[w]) >= 3:
            return
        if not deck:
            deck, discard = discard, []
            rng.shuffle(deck)
        if deck:
            hands[w].append(deck.pop())

    for w in 'AB':
        while len(hands[w]) < 2:
            draw(w)
    poss, pos = 'A', 0

    def scores(w, pts):
        nonlocal poss, pos
        score[w] += pts
        if score[w] >= target:
            return True
        poss, pos = other[w], 0
        draw(poss)
        return False

    for _ in range(3000):
        offw, defw = poss, other[poss]
        ko, kd, plays = odds[(score[offw], score[defw], pos)]
        if pos == RED:
            ko = {'kick': 1.0} if target - score[offw] <= 3 or rng.random() < 0.45 else plays
        o, d = pick(rng, ko), pick(rng, kd)
        if o == 'kick':
            if scores(offw, 3):
                break
            continue
        osp = off_special(rng, hands[offw], o, pos)
        dsp = def_special(rng, hands[defw], d)
        for w, c in ((offw, osp), (defw, dsp)):
            if c:
                hands[w].remove(c)
        kind, z = resolve(o, osp, d, dsp)
        if kind == 'replay':
            stats['flags'] += 1
            other_sp = dsp if z == 'off' else osp
            stats['other'][other_sp or 'none'] += 1
        for side, w, c in (('off', offw, osp), ('def', defw, dsp)):
            if c:
                back = kind == 'replay' and z != side and rule == 'back'
                (hands[w] if back else discard).append(c)
        if kind == 'replay':
            continue
        if kind == 'gain':
            pos += z
            if pos > RED and scores(offw, 7):
                break
        elif kind == 'td':
            if scores(offw, 7):
                break
        elif kind == 'pick6':
            if scores(defw, 7):
                break
        elif kind in ('stop', 'int', 'fumble'):
            poss, pos = defw, (0 if kind == 'stop' else 1)
        elif kind == 'sack':
            pos = max(0, pos - 1)
    stats['a_wins'] = score['A'] > score['B']
    return stats


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    W, odds = best_odds(21, False)
    base = {}
    worth = {}
    fired = {}
    for i, rule in enumerate(('back', 'used')):
        rng = random.Random(77 + i)
        games = [play_game(rng, odds, rule) for _ in range(n)]
        base[rule] = sum(g['a_wins'] for g in games) / n
        flags = sum(g['flags'] for g in games)
        other = Counter()
        for g in games:
            other.update(g['other'])
        fired[rule] = (flags / n, other, flags)
        worth[rule] = {}
        for j, k in enumerate(NAMES):
            rng = random.Random(1000 * (i + 1) + j)
            worth[rule][k] = sum(play_game(rng, odds, rule, k)['a_wins'] for _ in range(n)) / n - base[rule]

    per, other, flags = fired['back']
    print(f"A flag cancels a snap {per:.2f} times per game. When it does, the other side had played:")
    print('  ' + ', '.join(f"{NAMES.get(k, 'nothing')} {v / flags * 100:.0f}%" for k, v in other.most_common()))
    print()
    print(f"What starting with a card is worth ({n} games per line; about ±0.5 points of noise)")
    print(f"  {'card':20s} {'today (back)':>14s} {'used up':>10s}")
    for k in sorted(NAMES, key=lambda k: -worth['back'][k]):
        print(f"  {NAMES[k]:20s} {worth['back'][k] * 100:+13.1f}% {worth['used'][k] * 100:+9.1f}%")
