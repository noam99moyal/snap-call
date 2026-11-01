#!/usr/bin/env python3
"""Snap Call: today's rules vs a longer field with downs.

Today: 3 zones (Own 25, Midfield, Red Zone), any stop is a turnover.
New:   5 zones (Own 20, Own 35, Midfield, Their 35, Their 20 = Red Zone), 2 downs in each zone.
       A stop costs a down; a stop on the last down is a turnover at their own 20.
       Every time the ball moves to another zone it is 1st down again.

Both sides call plays at random (the fair baseline: nobody reads anybody) and play specials with the
game's CPU habits, so the numbers show the rules themselves.
"""
import random
import statistics
import sys

PLAYS = ('run', 'short', 'deep')
GAIN = {'run': 1, 'short': 1, 'deep': 2}
DECK = ['juke', 'grab', 'sack', 'tfl', 'flag', 'breakaway', 'hail', 'picksix', 'fumble'] * 2


def off_special(rng, hand, play, pos, zones):
    # A Hail Mary or Breakaway only helps when the play wouldn't score anyway.
    if play == 'deep' and 'hail' in hand and pos + 2 < zones and rng.random() < 0.6:
        return 'hail'
    if play == 'run' and 'breakaway' in hand and pos + 1 < zones and rng.random() < 0.6:
        return 'breakaway'
    jc = 'juke' if 'juke' in hand else 'grab' if 'grab' in hand else None
    if jc and rng.random() < (0.5 if play == 'deep' else 0.35):
        return jc
    if 'flag' in hand and rng.random() < 0.2:
        return 'flag'
    return None


def def_special(rng, hand, guess):
    if 'picksix' in hand and guess != 'run' and rng.random() < 0.5:
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


def play_game(rng, zones, downs, deep_int, target, today_kicks, second_extra=False):
    red, mid = zones - 1, zones // 2
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
    if second_extra:
        draw('B')   # the team that gets the ball second starts with one more special
    poss, pos, down = 'A', 0, 1
    g = {'snaps': 0, 'drives': [], 'lead_changes': 0, 'max_behind': {'A': 0, 'B': 0}}
    drive = {'stops': 0}
    leader = None

    def end_drive(result):
        nonlocal drive
        g['drives'].append((result, drive['stops']))
        drive = {'stops': 0}

    def scores(w, pts, result):
        nonlocal poss, pos, down, leader
        end_drive(result)
        score[w] += pts
        lead = 'A' if score['A'] > score['B'] else 'B' if score['B'] > score['A'] else leader
        if leader and lead != leader:
            g['lead_changes'] += 1
        leader = lead
        for t in 'AB':
            g['max_behind'][t] = max(g['max_behind'][t], score[other[t]] - score[t])
        if score[w] >= target:
            return True
        poss, pos, down = other[w], 0, 1
        draw(poss)
        return False

    def turnover(new_pos, result):
        nonlocal poss, pos, down
        end_drive(result)
        poss, pos, down = other[poss], new_pos, 1

    for _ in range(2000):
        if pos == red:
            need3 = target - score[poss] <= 3
            kick = (need3 or rng.random() < 0.45) if today_kicks else (need3 or down == downs)
            if kick:
                g['snaps'] += 1
                if scores(poss, 3, 'FG'):
                    break
                continue
        g['snaps'] += 1
        offw, defw = poss, other[poss]
        o = rng.choice(PLAYS)
        d = rng.choice(PLAYS)
        osp = off_special(rng, hands[offw], o, pos, zones)
        dsp = def_special(rng, hands[defw], d)
        for w, c in ((offw, osp), (defw, dsp)):
            if c:
                hands[w].remove(c)
        kind, z = resolve(o, osp, d, dsp)
        for side, w, c in (('off', offw, osp), ('def', defw, dsp)):
            if c:
                # On a replay, the special of the side that didn't throw the flag goes back to its hand.
                (hands[w] if kind == 'replay' and z != side else discard).append(c)
        if kind == 'replay':
            continue
        if kind == 'int' and (deep_int == 'never' or (deep_int == 'last' and down < downs)):
            kind = 'stop'
        if kind == 'gain':
            pos += z
            down = 1
            if pos >= zones and scores(offw, 7, 'TD'):
                break
        elif kind == 'td':
            if scores(offw, 7, 'TD'):
                break
        elif kind == 'stop':
            drive['stops'] += 1
            if down < downs:
                down += 1
            else:
                turnover(0, 'stopped')
        elif kind == 'int':
            drive['stops'] += 1
            turnover(mid, 'interception')
        elif kind == 'fumble':
            drive['stops'] += 1
            turnover(mid, 'fumble')
        elif kind == 'sack':
            if pos > 0:
                pos -= 1
                down = 1
        elif kind == 'pick6':
            drive['stops'] += 1
            if scores(defw, 7, 'pick six'):
                break
    winner = 'A' if score['A'] > score['B'] else 'B'
    g['first_wins'] = winner == 'A'
    g['comeback7'] = g['max_behind'][winner] >= 7
    g['margin'] = abs(score['A'] - score['B'])
    return g


def summary(name, games):
    drives = [d for g in games for d in g['drives']]
    n = len(drives)
    res = lambda r: sum(1 for d in drives if d[0] == r) / n
    lost = [d for d in drives if d[0] in ('stopped', 'interception', 'fumble', 'pick six')]
    on_first = sum(1 for d in lost if d[1] == 1) / max(1, len(lost))
    first = [d[0] for d in lost if d[1] == 1]
    why = ', '.join(f"{r} {first.count(r)/n*100:.1f}%" for r in ('stopped', 'interception', 'fumble', 'pick six'))
    snaps = sorted(g['snaps'] for g in games)
    q = lambda p: snaps[int(p * (len(snaps) - 1))]
    return (f"{name}\n"
            f"  drives: touchdown {res('TD')*100:4.1f}%  field goal {res('FG')*100:4.1f}%  lose the ball {len(lost)/n*100:4.1f}%"
            f"  (of those, on the very first stop {on_first*100:4.1f}%)\n"
            f"  lost on the first stop, % of all drives: {why}\n"
            f"  snaps per game: median {statistics.median(snaps):.0f}  (most games {q(0.1)}-{q(0.9)})   drives per game {n/len(games):.1f}\n"
            f"  team with the ball first wins {sum(g['first_wins'] for g in games)/len(games)*100:4.1f}%   "
            f"winner came back from 7+ down {sum(g['comeback7'] for g in games)/len(games)*100:4.1f}%   "
            f"lead changes {statistics.mean(g['lead_changes'] for g in games):.1f}   "
            f"close games (7 or less) {sum(g['margin'] <= 7 for g in games)/len(games)*100:4.1f}%")


VARIANTS = {
    'today': dict(zones=3, downs=1, deep_int='now', target=21, today_kicks=True),
    'new, guessed Deep = interception': dict(zones=5, downs=2, deep_int='now', target=21, today_kicks=False),
    'new, guessed Deep = interception only on last down': dict(zones=5, downs=2, deep_int='last', target=21, today_kicks=False),
    'new, guessed Deep = like any stop': dict(zones=5, downs=2, deep_int='never', target=21, today_kicks=False),
    'last-down Deep, first to 14': dict(zones=5, downs=2, deep_int='last', target=14, today_kicks=False),
    'last-down Deep, first to 28': dict(zones=5, downs=2, deep_int='last', target=28, today_kicks=False),
    'last-down Deep, 2nd team starts with 3 specials': dict(zones=5, downs=2, deep_int='last', target=21, today_kicks=False, second_extra=True),
    'last-down Deep, first to 14, 2nd team starts with 3 specials': dict(zones=5, downs=2, deep_int='last', target=14, today_kicks=False, second_extra=True),
}

if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    picks = sys.argv[2:] or list(VARIANTS)
    for i, k in enumerate(picks):
        rng = random.Random(2026 + i)
        print(summary(k, [play_game(rng, **VARIANTS[k]) for _ in range(n)]))
