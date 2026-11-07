#!/usr/bin/env python3
"""Snap Call (Stopped once): today's sure field goal vs a Block Kick card for the defense.

Today:      in the Red Zone the offense may play Kick Field Goal instead of a snap: 3 points, always.
Block Kick: in the Red Zone the defense also has a Block Kick card, picked in secret like a Stop card.
            Kick vs Block Kick: no points, the defense takes over at its own 25.
            Kick vs a Stop card: 3 points. A play vs Block Kick: the play isn't stopped (in the Red Zone, a touchdown).
            Specials don't go with a kick or a block; a special played against a kick goes back to its hand.

Part 1 finds the best odds for every call and guess, without the specials: each side leaves the other nothing to
gain by switching. It plays for wins (first to 21), so it also knows how the odds change near the end.
Part 2 plays thousands of whole games with the specials, both sides using those odds, and compares the rules.
"Today, kicking 45%" is today's game as the CPU plays it: kick when 3 points win, otherwise 45% of the time.

    python3 tools/rules-sim/block_kick.py            # 20000 games per rule
    python3 tools/rules-sim/block_kick.py 5000 28    # 5000 games, first to 28
"""
import random
import statistics
import sys

PLAYS = ('run', 'short', 'deep')
GAIN = {'run': 1, 'short': 1, 'deep': 2}
DECK = ['juke', 'grab', 'sack', 'tfl', 'flag', 'breakaway', 'hail', 'picksix', 'fumble'] * 2
RED = 2


# ---------- Small zero-sum games (row player maximizes) ----------
def solve(M):
    """Best mixes for a small payoff matrix: (value, row odds, column odds). Simplex on the standard LP."""
    m, n = len(M), len(M[0])
    shift = 1 - min(min(r) for r in M)
    A = [[M[i][j] + shift for j in range(n)] for i in range(m)]
    # Column player: max sum(y) s.t. A y <= 1, y >= 0. Its dual gives the row player's odds.
    T = [A[i][:] + [1.0 if k == i else 0.0 for k in range(m)] + [1.0] for i in range(m)]
    z = [-1.0] * n + [0.0] * m + [0.0]
    basis = [n + i for i in range(m)]
    while True:
        col = min(range(n + m), key=lambda k: (z[k], k))
        if z[col] >= -1e-12:
            break
        rows = [(T[i][-1] / T[i][col], i) for i in range(m) if T[i][col] > 1e-12]
        _, r = min(rows)
        p = T[r][col]
        T[r] = [x / p for x in T[r]]
        for i in range(m):
            if i != r and abs(T[i][col]) > 1e-15:
                f = T[i][col]
                T[i] = [a - f * b for a, b in zip(T[i], T[r])]
        f = z[col]
        z = [a - f * b for a, b in zip(z, T[r])]
        basis[r] = col
    total = z[-1]
    y = [0.0] * n
    for i, b in enumerate(basis):
        if b < n:
            y[b] = T[i][-1]
    x = [z[n + i] for i in range(m)]
    return 1 / total - shift, [v / total for v in x], [v / total for v in y]


def matrix(W, a, b, pos, block, target):
    """The offense's chance to win from here, for each call (rows) against each guess (columns).
    W[(a, b, pos)] is the chance that the team with the ball wins: a = its score, b = the other team's."""
    def after_score(pts):
        return 1.0 if a + pts >= target else 1 - W[(b, a + pts, 0)]
    lose_ball = 1 - W[(b, a, 0)]          # the other team starts at its own 25
    intercepted = 1 - W[(b, a, 1)]        # ...or at midfield
    rows = list(PLAYS) + (['kick'] if pos == RED else [])
    cols = list(PLAYS) + (['block'] if pos == RED and block else [])
    M = []
    for o in rows:
        row = []
        for d in cols:
            if o == 'kick':
                row.append(lose_ball if d == 'block' else after_score(3))
            elif d == o:
                row.append(intercepted if o == 'deep' else lose_ball)
            else:
                to = pos + GAIN[o]
                row.append(after_score(7) if to > RED else W[(a, b, to)])
        M.append(row)
    return rows, cols, M


def best_odds(target, block):
    """Value iteration on the chance to win; returns W and the best odds in every spot."""
    states = sorted(((a, b, p) for a in range(target) for b in range(target) for p in range(3)), key=lambda s: -(s[0] + s[1]))
    W = {s: 0.5 for s in states}
    for it in range(400):
        diff = 0
        for s in states:
            rows, cols, M = matrix(W, *s, block, target)
            if s[2] == RED and not block:
                # Today the kick is a sure thing: the offense compares it with the guessing game.
                v_play = solve([r for r in M[:3]])[0]
                v = max(v_play, M[3][0])
            else:
                v = solve(M)[0]
            diff = max(diff, abs(v - W[s]))
            W[s] = v
        if diff < 1e-7:
            break
    odds = {}
    for s in states:
        rows, cols, M = matrix(W, *s, block, target)
        if s[2] == RED and not block:
            v_play, x, y = solve(M[:3])
            kick = M[3][0] >= v_play
            odds[s] = ({'kick': 1.0} if kick else dict(zip(PLAYS, x)), dict(zip(PLAYS, y)), dict(zip(PLAYS, x)))
        else:
            _, x, y = solve(M)
            odds[s] = (dict(zip(rows, x)), dict(zip(cols, y)), dict(zip(rows, x)))
    return W, odds


# ---------- Whole games with the specials ----------
def off_special(rng, hand, play, pos):
    if play == 'deep' and 'hail' in hand and pos == 0 and rng.random() < 0.6:
        return 'hail'
    if play == 'run' and 'breakaway' in hand and pos < RED and rng.random() < 0.6:
        return 'breakaway'
    jc = 'juke' if 'juke' in hand else 'grab' if 'grab' in hand else None
    if jc and rng.random() < (0.5 if play == 'deep' else 0.35):
        return jc
    if 'flag' in hand and rng.random() < 0.2:
        return 'flag'
    return None


def def_special(rng, hand, guess):
    if 'picksix' in hand and guess in ('short', 'deep') and rng.random() < 0.5:
        return 'picksix'
    if 'fumble' in hand and guess == 'run' and rng.random() < 0.6:
        return 'fumble'
    ts = 'tfl' if 'tfl' in hand else 'sack' if 'sack' in hand else None
    if ts and rng.random() < 0.4:
        return ts
    if 'flag' in hand and rng.random() < 0.2:
        return 'flag'
    return None


def resolve(o, osp, d, dsp):
    if d == o:
        if osp == 'flag':
            return 'replay', 'off'
        if osp in ('juke', 'grab'):
            return 'gain', 1
        if o != 'run' and dsp == 'picksix':
            return 'pick6', 0
        if o == 'run' and dsp == 'fumble':
            return 'fumble', 0
        return ('int' if o == 'deep' else 'stop'), 0
    if dsp == 'flag':
        return 'replay', 'def'
    if dsp in ('sack', 'tfl'):
        return 'sack', 0
    if o == 'deep' and osp == 'hail':
        return 'td', 0
    if o == 'run' and osp == 'breakaway':
        return 'td', 0
    return 'gain', GAIN[o]


def pick(rng, odds):
    r = rng.random()
    for k, p in odds.items():
        r -= p
        if r <= 0:
            return k
    return k


def play_game(rng, target, block, odds, habit=False, block_rate=0.0):
    """`odds[(a, b, pos)]` are the best odds from part 1. `habit`: kick 45% of the time in the Red Zone, like
    today's CPU (with Block Kick, only while 3 points don't win: then both sides use the best odds).
    `block_rate`: with Block Kick, how often the defense blocks while 3 points don't win."""
    score = {'A': 0, 'B': 0}
    other = {'A': 'B', 'B': 'A'}
    deck = DECK[:]
    rng.shuffle(deck)
    discard = []
    hands = {'A': [], 'B': []}

    def draw(w):
        nonlocal deck, discard
        if len(hands[w]) >= 3:
            return
        if not deck:
            deck, discard = discard, []
            rng.shuffle(deck)
        if deck:
            hands[w].append(deck.pop())

    for _ in range(2):
        draw('A')
        draw('B')
    poss, pos = 'A', 0
    g = {'snaps': 0, 'red': [], 'lead_changes': 0, 'max_behind': {'A': 0, 'B': 0}, 'sure_end': False}
    leader = None

    def scores(w, pts):
        nonlocal poss, pos, leader
        score[w] += pts
        lead = 'A' if score['A'] > score['B'] else 'B' if score['B'] > score['A'] else leader
        if leader and lead != leader:
            g['lead_changes'] += 1
        leader = lead
        for t in 'AB':
            g['max_behind'][t] = max(g['max_behind'][t], score[other[t]] - score[t])
        if score[w] >= target:
            return True
        poss, pos = other[w], 0
        draw(poss)
        return False

    for _ in range(3000):
        g['snaps'] += 1
        offw, defw = poss, other[poss]
        ko, kd = odds[(score[offw], score[defw], pos)][:2]
        if pos == RED and block and habit and target - score[offw] > 3:
            plays = odds[(score[offw], score[defw], pos)][2]
            ko = {'kick': 0.45, **{k: 0.55 * plays[k] / sum(plays[x] for x in PLAYS) for k in PLAYS}}
            kd = {'block': block_rate, **{k: (1 - block_rate) * kd[k] / sum(kd[x] for x in PLAYS) for k in PLAYS}}
        if pos == RED and not block:
            if target - score[offw] <= 3:
                g['sure_end'] = True      # the offense needs 3 or less and the kick can't miss
            if habit:
                if target - score[offw] <= 3 or rng.random() < 0.45:
                    ko = {'kick': 1.0}
                else:
                    ko = odds[(score[offw], score[defw], pos)][2]
        o, d = pick(rng, ko), pick(rng, kd)
        if o == 'kick':
            if d == 'block':
                g['red'].append('blocked')
                poss, pos = defw, 0
                continue
            g['red'].append('FG')
            if scores(offw, 3):
                break
            continue
        osp = off_special(rng, hands[offw], o, pos)
        dsp = None if d == 'block' else def_special(rng, hands[defw], d)
        for w, c in ((offw, osp), (defw, dsp)):
            if c:
                hands[w].remove(c)
        kind, z = resolve(o, osp, d, dsp)
        for side, w, c in (('off', offw, osp), ('def', defw, dsp)):
            if c:
                (hands[w] if kind == 'replay' and z != side else discard).append(c)
        if kind == 'replay':
            continue
        was = pos
        if kind == 'gain':
            pos += z
            if pos > RED:
                if was == RED:
                    g['red'].append('TD')
                if scores(offw, 7):
                    break
        elif kind == 'td':
            if was == RED:
                g['red'].append('TD')
            if scores(offw, 7):
                break
        elif kind in ('stop', 'int', 'fumble', 'pick6'):
            if was == RED:
                g['red'].append('lost')
            if kind == 'pick6':
                if scores(defw, 7):
                    break
            else:
                poss, pos = defw, (0 if kind == 'stop' else 1)
        elif kind == 'sack':
            pos = max(0, pos - 1)
    winner = 'A' if score['A'] > score['B'] else 'B'
    g['first_wins'] = winner == 'A'
    g['comeback7'] = g['max_behind'][winner] >= 7
    g['margin'] = abs(score['A'] - score['B'])
    return g


def summary(name, games):
    red = [r for g in games for r in g['red']]
    n = len(red)
    share = lambda k: sum(1 for r in red if r == k) / n * 100
    snaps = sorted(g['snaps'] for g in games)
    q = lambda p: snaps[int(p * (len(snaps) - 1))]
    out = (f"{name}\n"
           f"  each snap in the Red Zone: touchdown {share('TD'):4.1f}%  field goal {share('FG'):4.1f}%  "
           f"blocked {share('blocked'):4.1f}%  ball lost {share('lost'):4.1f}%\n"
           f"  snaps per game: median {statistics.median(snaps):.0f} (most games {q(0.1)}-{q(0.9)})   "
           f"lead changes {statistics.mean(g['lead_changes'] for g in games):.1f}   "
           f"winner came back from 7+ down {sum(g['comeback7'] for g in games) / len(games) * 100:4.1f}%   "
           f"close games (7 or less) {sum(g['margin'] <= 7 for g in games) / len(games) * 100:4.1f}%   "
           f"first team wins {sum(g['first_wins'] for g in games) / len(games) * 100:4.1f}%")
    if any(g['sure_end'] for g in games):
        out += f"\n  games where a team reached the Red Zone needing 3 or less (a sure win): {sum(g['sure_end'] for g in games) / len(games) * 100:4.1f}%"
    return out


def fmt(d):
    names = {'run': 'Run', 'short': 'Short', 'deep': 'Deep', 'kick': 'Kick', 'block': 'Block'}
    return '  '.join(f"{names[k]} {v * 100:3.0f}%" for k, v in d.items())


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 21
    results = {}
    for block in (False, True):
        W, odds = best_odds(target, block)
        results[block] = (W, odds)

    print(f"Part 1: best odds, first to {target}\n")
    for block, label in ((False, 'Today (the kick always scores)'), (True, 'With Block Kick')):
        W, odds = results[block]
        print(label)
        print(f"  team with the ball first wins {W[(0, 0, 0)] * 100:.1f}%")
        for (a, b), why in (((0, 0), 'start of the game, 0-0'), ((14, 14), 'tied 14-14'), ((14, 21 - 14 if target == 21 else 7), 'ahead by 7'),
                            ((7, 14), 'behind by 7'), ((target - 3, target - 7), f'needs 3 or less ({target - 3}-{target - 7})'),
                            ((target - 3, target - 3), f'both need 3 ({target - 3}-{target - 3})')):
            ko, kd = odds[(a, b, RED)][:2]
            print(f"  Red Zone, {why:28s} offense: {fmt(ko):44s} defense: {fmt(kd):40s} offense wins {W[(a, b, RED)] * 100:5.1f}%")
        print()

    print(f"Part 2: {n} whole games each, with the specials\n")
    for i, (block, habit, rate, label) in enumerate((
            (False, True, 0, 'Today, kicking 45% (the CPU)'),
            (True, True, 0.0, 'With Block Kick, kicking 45%, blocking only when 3 points win'),
            (True, True, 0.2, 'With Block Kick, kicking 45%, blocking 20% (best odds when 3 points win)'),
            (False, False, 0, 'Today, best play'),
            (True, False, 0, 'With Block Kick, best play'))):
        W, odds = results[block]
        rng = random.Random(2026 + i)
        print(summary(label, [play_game(rng, target, block, odds, habit, rate) for _ in range(n)]))
        print()
