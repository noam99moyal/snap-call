#!/usr/bin/env python3
"""Snap Call: today's CPU (Normal) vs a proposed Hard CPU, each against scripted players.

Rules and specials follow full-cards/game.html (RULES_VERSION 4): you get the ball first,
2 specials each to start, one more after you're scored on (hold 3), field goals from the
Red Zone. Players and CPUs use the same special-card habits (today's CPU habits), so only
the play calling differs.
"""
import math
import random
import sys

TARGET = 21
PLAYS = ('run', 'short', 'deep')
IDX = {p: i for i, p in enumerate(PLAYS)}
GAIN = {'run': 1, 'short': 1, 'deep': 2}
DECK = ['juke', 'grab', 'sack', 'tfl', 'flag', 'breakaway', 'hail', 'picksix', 'fumble'] * 2
EVEN = [1 / 3] * 3


def other(w):
    return 'cpu' if w == 'you' else 'you'


def norm(v):
    s = sum(v)
    return [x / s for x in v]


def pick(rng, dist):
    r = rng.random()
    for p, v in zip(PLAYS, dist):
        r -= v
        if r <= 0:
            return p
    return PLAYS[-1]


def peak(i, top=0.6):
    return [top if j == i else (1 - top) / 2 for j in range(3)]


def argmin(v, rng):
    lo = min(v)
    return rng.choice([i for i, x in enumerate(v) if x - lo < 1e-9])


def argmax(v, rng):
    hi = max(v)
    return rng.choice([i for i, x in enumerate(v) if hi - x < 1e-9])


# ---------- Specials: today's CPU habits, used by every player ----------
def off_special(rng, hand, play, pos):
    if play == 'deep' and 'hail' in hand and pos == 0 and rng.random() < 0.6:
        return 'hail'
    if play == 'run' and 'breakaway' in hand and rng.random() < 0.6:
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
    """o: the offense's play; d: the play the defense tried to stop. Returns (kind, zones, side that fired)."""
    if d == o:
        if osp == 'flag':
            return 'replay', 0, 'off'
        if osp in ('juke', 'grab'):
            return 'gain', 1, 'off'
        if o != 'run' and dsp == 'picksix':
            return 'pick6', 0, 'def'
        if o == 'run' and dsp == 'fumble':
            return 'fumble', 0, 'def'
        return ('int' if o == 'deep' else 'stop'), 0, None
    if dsp == 'flag':
        return 'replay', 0, 'def'
    if dsp in ('sack', 'tfl'):
        return 'sack', 0, 'def'
    if o == 'deep' and osp == 'hail':
        return 'td', 0, 'off'
    if o == 'run' and osp == 'breakaway':
        return 'td', 0, 'off'
    return 'gain', GAIN[o], None


def play_game(you, cpu, rng):
    score = {'you': 0, 'cpu': 0}
    deck = DECK[:]
    rng.shuffle(deck)
    discard = []
    hands = {'you': [], 'cpu': []}

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
        draw('you')
        draw('cpu')
    poss, pos = 'you', 0
    you.new_game()
    cpu.new_game()
    st = {'off': 0, 'off_ok': 0, 'def': 0, 'def_ok': 0, 'snaps': 0}

    def scores(w, pts):
        nonlocal poss, pos
        score[w] += pts
        if score[w] >= TARGET:
            return True
        poss, pos = other(w), 0
        draw(poss)
        return False

    for _ in range(600):
        if pos == 2 and (TARGET - score[poss] <= 3 or rng.random() < 0.45):
            if scores(poss, 3):
                break
            continue
        st['snaps'] += 1
        ctx = {'pos': pos, 'lead': score['cpu'] - score['you']}
        offw, defw = poss, other(poss)
        if poss == 'you':
            o = you.offense(ctx)
            osp = off_special(rng, hands['you'], o, pos)
            d, dsp = cpu.defense(ctx, hands['cpu'])
        else:
            o, osp = cpu.offense(ctx, hands['cpu'])
            d = you.defense(ctx)
            dsp = def_special(rng, hands['you'], d)
        for w, c in ((offw, osp), (defw, dsp)):
            if c:
                hands[w].remove(c)
        kind, zones, fired = resolve(o, osp, d, dsp)
        firedw = offw if fired == 'off' else defw if fired == 'def' else None
        for w, c in ((offw, osp), (defw, dsp)):
            if c:
                (hands[w] if kind == 'replay' and w != firedw else discard).append(c)
        if poss == 'you':
            cpu.saw_offense(o)
            st['off'] += 1
            st['off_ok'] += d != o
        else:
            cpu.saw_defense(d)
            st['def'] += 1
            st['def_ok'] += d == o
        you.saw(poss, o, d, ctx['pos'])
        if kind == 'gain':
            pos += zones
            if pos >= 3 and scores(offw, 7):
                break
        elif kind == 'td':
            if scores(offw, 7):
                break
        elif kind == 'stop':
            poss, pos = defw, 0
        elif kind in ('int', 'fumble'):
            poss, pos = defw, 1
        elif kind == 'sack':
            pos = max(0, pos - 1)
        elif kind == 'pick6':
            if scores(defw, 7):
                break
    return score['you'] > score['cpu'], st


# ---------- CPUs ----------
class Normal:
    """Today's CPU, as in cpuPick()."""
    name = 'Normal (today)'

    def __init__(self, rng):
        self.rng = rng

    def new_game(self):
        self.off = {'run': 2, 'short': 2, 'deep': 2}
        self.dfn = {'run': 2, 'short': 2, 'deep': 2}

    def guess_dist(self, ctx):
        tot = sum(self.off.values())
        w = [0.25 / 3 + 0.75 * self.off[p] / tot for p in PLAYS]
        if ctx['pos'] == 2:
            w[2] *= 0.5
        return norm(w)

    def call_dist(self, ctx):
        g = self.dfn
        return norm([1 / g['run'], 1 / g['short'], (0.35 if ctx['pos'] == 2 else 0.8) / g['deep']])

    def defense(self, ctx, hand):
        d = pick(self.rng, self.guess_dist(ctx))
        return d, def_special(self.rng, hand, d)

    def offense(self, ctx, hand):
        if 'hail' in hand and ctx['pos'] == 0 and -ctx['lead'] >= 7 and self.rng.random() < 0.5:
            return 'deep', 'hail'
        o = pick(self.rng, self.call_dist(ctx))
        return o, off_special(self.rng, hand, o, ctx['pos'])

    def saw_offense(self, o):
        self.off[o] += 1

    def saw_defense(self, d):
        self.dfn[d] += 1


class Hunches:
    """Guesses which of run / short / deep a player picks next. Several hunches run at once; each is
    scored on how well it would have guessed lately, and the guess leans on the ones that have been right."""
    NAMES = ('even', 'all', 'recent', 'zone', 'after', 'repeat', 'balance', 'counter')

    def __init__(self, memory, decay, beta):
        self.memory, self.decay, self.beta = memory, decay, beta
        self.past = []   # (pos, prev, choice, weight) from earlier games, when it remembers
        self.game = []
        self.score = dict.fromkeys(self.NAMES, 0.0)
        self.mix_score = 0.0

    def new_game(self):
        if self.memory:
            self.past = [(p, pr, c, w * 0.5) for p, pr, c, w in self.past + [(p, pr, c, 1.0) for p, pr, c in self.game]]
            self.past = [r for r in self.past if r[3] > 0.05]
            self.score = {k: v * 0.5 for k, v in self.score.items()}
            self.mix_score *= 0.5
        else:
            self.score = dict.fromkeys(self.NAMES, 0.0)
            self.mix_score = 0.0
        self.game = []
        self.prev = None

    def _counts(self, rows):
        n = [1.0, 1.0, 1.0]
        for r in rows:
            n[IDX[r[2]]] += r[3]
        return norm(n)

    def predict(self, pos, counter_of, rng):
        """counter_of(naive prediction) -> the pick a player would make to beat the CPU's own plan."""
        hist = self.past + [(p, pr, c, 1.0) for p, pr, c in self.game]
        e = {'even': EVEN, 'all': self._counts(hist)}
        e['recent'] = self._counts([(p, pr, c, 1.0) for p, pr, c in self.game[-5:]])
        e['zone'] = self._counts([r for r in hist if r[0] == pos])
        e['after'] = self._counts([r for r in hist if r[1] == self.prev]) if self.prev else e['all']
        e['repeat'] = peak(IDX[self.prev]) if self.prev else EVEN
        e['balance'] = peak(argmin(self._counts([(p, pr, c, 1.0) for p, pr, c in self.game]), rng))
        w = {k: math.exp(self.beta * self.score[k]) for k in e}
        naive = norm([sum(w[k] * e[k][i] for k in e) for i in range(3)])
        if counter_of:
            e['counter'] = peak(counter_of(naive))
            w['counter'] = math.exp(self.beta * self.score['counter'])
        full = norm([sum(w[k] * e[k][i] for k in e) for i in range(3)])
        return full, (pos, e, full)

    def learn(self, seen, choice):
        pos, e, full = seen
        i = IDX[choice]
        for k, p in e.items():
            self.score[k] = self.decay * self.score[k] + math.log(3 * p[i])
        self.mix_score = self.decay * self.mix_score + math.log(3 * full[i])
        self.game.append((pos, self.prev, choice))
        self.prev = choice


def spread(q, cap, floor):
    """Mix with even odds just enough that no option is above cap or below floor."""
    t = 0.0
    hi, lo = max(q), min(q)
    if hi > cap:
        t = max(t, (hi - cap) / (hi - 1 / 3))
    if lo < floor:
        t = max(t, (floor - lo) / (1 / 3 - lo))
    return [(1 - t) * x + t / 3 for x in q]


class Hard:
    name = 'Hard (first try)'

    def __init__(self, rng, memory=False, cap=0.7, floor=0.12, sharp=2.0, temp=0.35, decay=0.8, beta=1.0, guard=4.0):
        self.rng = rng
        self.cap, self.floor, self.sharp, self.temp, self.guard = cap, floor, sharp, temp, guard
        self.off = Hunches(memory, decay, beta)   # your calls on offense
        self.dfn = Hunches(memory, decay, beta)   # your guesses on defense
        if memory:
            self.name = 'Hard (first try), remembers'

    def new_game(self):
        self.off.new_game()
        self.dfn.new_game()
        self.hits = []   # did its last few guesses / calls work, to notice being read

    def _loose(self):
        """If its reads do worse than plain luck lately, someone is reading it back: play closer to even odds."""
        if not self.guard or len(self.hits) < 4:
            return 0.0
        edge = sum(self.hits[-8:]) / len(self.hits[-8:])
        return min(1.0, max(0.0, -edge * self.guard))

    def _guess_q(self, P, pos):
        value = [1.0, 1.0, 1.6 if pos < 2 else 1.3]   # stopping a Deep Pass is an interception
        q = norm([(P[i] * value[i]) ** self.sharp for i in range(3)])
        q = spread(q, self.cap, self.floor)
        t = self._loose()
        return [(1 - t) * x + t / 3 for x in q]

    def _call_q(self, G, pos):
        ev = []
        for i, p in enumerate(PLAYS):
            td = pos + GAIN[p] >= 3
            gain = min(GAIN[p], 3 - pos) + (1.0 if td else 0.0)
            loss = 1.8 if p == 'deep' else 1.2
            ev.append((1 - G[i]) * gain - G[i] * loss)
        top = max(ev)
        q = norm([math.exp((x - top) / self.temp) for x in ev])
        q = spread(q, self.cap, self.floor)
        t = self._loose()
        return [(1 - t) * x + t / 3 for x in q]

    def guess_dist(self, ctx, keep=False):
        pos = ctx['pos']
        # A player reading the CPU calls the play it is least likely to guess.
        P, seen = self.off.predict(pos, lambda naive: argmin(self._guess_q(naive, pos), self.rng), self.rng)
        if keep:
            self._seen = seen
        return self._guess_q(P, pos)

    def call_dist(self, ctx, keep=False):
        pos = ctx['pos']
        # A player reading the CPU guesses the play it is most likely to call.
        G, seen = self.dfn.predict(pos, lambda naive: argmax(self._call_q(naive, pos), self.rng), self.rng)
        if keep:
            self._seen = seen
        return self._call_q(G, pos)

    def defense(self, ctx, hand):
        d = pick(self.rng, self.guess_dist(ctx, keep=True))
        self._mine = d
        return d, def_special(self.rng, hand, d)

    def offense(self, ctx, hand):
        q = self.call_dist(ctx, keep=True)
        if 'hail' in hand and ctx['pos'] == 0 and -ctx['lead'] >= 7 and self.rng.random() < 0.5:
            o, sp = 'deep', 'hail'
        else:
            o = pick(self.rng, q)
            sp = off_special(self.rng, hand, o, ctx['pos'])
        self._mine = o
        return o, sp

    # Luck alone guesses right 1 time in 3 and gets a play through 2 times in 3.
    def saw_offense(self, o):
        self.off.learn(self._seen, o)
        self.hits.append((1 if self._mine == o else 0) - 1 / 3)

    def saw_defense(self, d):
        self.dfn.learn(self._seen, d)
        self.hits.append((0 if self._mine == d else 1) - 2 / 3)


def gain_loss(pos):
    """What each play is worth to the offense: zones gained (reaching the end zone counts extra), and what a stop costs."""
    gain = [min(GAIN[p], 3 - pos) + (1.0 if pos + GAIN[p] >= 3 else 0.0) for p in PLAYS]
    loss = [1.8 if p == 'deep' else 1.2 for p in PLAYS]
    return gain, loss


def safe_mix(pos):
    """The calls and guesses that can't be read, even by someone who knows these odds (each side makes the other indifferent)."""
    g, l = gain_loss(pos)
    inv = [1 / (g[i] + l[i]) for i in range(3)]
    calls = norm(inv)
    v = (sum(g[i] * inv[i] for i in range(3)) - 1) / sum(inv)
    guesses = norm([max(0.0, (g[i] - v) * inv[i]) for i in range(3)])
    return calls, guesses


class Hard2:
    """Starts from the safe mix, and leans into your habits only as far as its reads have been working."""
    name = 'Hard'

    def __init__(self, rng, memory=False, lean=1.0, conf=0.5, temp=0.3, decay=0.9, beta=1.0, guard=0.0, cap=0.8):
        self.rng = rng
        self.lean, self.conf, self.temp, self.guard, self.cap = lean, conf, temp, guard, cap
        self.off = Hunches(memory, decay, beta)
        self.dfn = Hunches(memory, decay, beta)
        if memory:
            self.name = 'Hard, remembers past games'

    def new_game(self):
        self.off.new_game()
        self.dfn.new_game()
        self.hits = []

    def _trust(self, h):
        """0 = play the safe mix, 1 = play fully into the read."""
        c = max(0.0, min(1.0, h.mix_score / self.conf)) * self.lean
        if len(self.hits) >= 4:
            edge = sum(self.hits[-8:]) / len(self.hits[-8:])
            c *= max(0.0, min(1.0, 1 + edge * self.guard))
        return c

    def _guess_q(self, P, pos):
        g, l = gain_loss(pos)
        # What the offense expects to get if the CPU guesses x.
        payoff = [sum(P[y] * g[y] for y in range(3) if y != x) - P[x] * l[x] for x in range(3)]
        lo = min(payoff)
        read = norm([math.exp(-(x - lo) / self.temp) for x in payoff])
        c = self._trust(self.off)
        safe = safe_mix(pos)[1]
        return spread([(1 - c) * safe[i] + c * read[i] for i in range(3)], self.cap, 0.0)

    def _call_q(self, G, pos):
        g, l = gain_loss(pos)
        ev = [(1 - G[i]) * g[i] - G[i] * l[i] for i in range(3)]
        top = max(ev)
        read = norm([math.exp((x - top) / self.temp) for x in ev])
        c = self._trust(self.dfn)
        safe = safe_mix(pos)[0]
        return spread([(1 - c) * safe[i] + c * read[i] for i in range(3)], self.cap, 0.0)

    def guess_dist(self, ctx, keep=False):
        pos = ctx['pos']
        P, seen = self.off.predict(pos, lambda naive: argmin(self._guess_q(naive, pos), self.rng), self.rng)
        if keep:
            self._seen = seen
        return self._guess_q(P, pos)

    def call_dist(self, ctx, keep=False):
        pos = ctx['pos']
        G, seen = self.dfn.predict(pos, lambda naive: argmax(self._call_q(naive, pos), self.rng), self.rng)
        if keep:
            self._seen = seen
        return self._call_q(G, pos)

    defense = Hard.defense
    offense = Hard.offense
    saw_offense = Hard.saw_offense
    saw_defense = Hard.saw_defense


# ---------- Test players ----------
class Player:
    def __init__(self, rng, cpu=None):
        self.rng, self.cpu = rng, cpu

    def new_game(self):
        self.mine_off, self.mine_def = [], []

    def saw(self, poss, o, d, pos):
        (self.mine_off if poss == 'you' else self.mine_def).append(o if poss == 'you' else d)


class Random(Player):
    name = 'Mixes at random'

    def offense(self, ctx):
        return self.rng.choice(PLAYS)

    def defense(self, ctx):
        return self.rng.choice(PLAYS)


class Favorite(Player):
    name = 'Has a favorite play'

    def offense(self, ctx):
        return pick(self.rng, [0.55, 0.30, 0.15])

    def defense(self, ctx):
        return pick(self.rng, [0.50, 0.30, 0.20])


class ByZone(Player):
    name = 'Same call in each zone'

    def offense(self, ctx):
        main = ('deep', 'short', 'run')[ctx['pos']]
        return main if self.rng.random() < 0.7 else self.rng.choice([p for p in PLAYS if p != main])

    def defense(self, ctx):
        main = ('deep', 'short', 'run')[ctx['pos']]
        return main if self.rng.random() < 0.6 else self.rng.choice([p for p in PLAYS if p != main])


class Cycler(Player):
    name = 'Goes in order (Run, Short, Deep...)'

    def offense(self, ctx):
        return PLAYS[len(self.mine_off) % 3]

    def defense(self, ctx):
        return PLAYS[len(self.mine_def) % 3]


class Bait(Player):
    name = 'Trickster: 3 Runs, then 2 passes'
    PATTERN = ('run', 'run', 'run', 'short', 'deep')

    def offense(self, ctx):
        return self.PATTERN[len(self.mine_off) % 5]

    def defense(self, ctx):
        return self.PATTERN[len(self.mine_def) % 5]


class Balancer(Player):
    name = "Trickster: calls what it hasn't lately"

    def _least(self, mine):
        n = [mine.count(p) for p in PLAYS]
        return PLAYS[argmin(n, self.rng)]

    def offense(self, ctx):
        return self._least(self.mine_off)

    def defense(self, ctx):
        return self._least(self.mine_def)


class Reader(Player):
    """A sharp human: watches the CPU's calls and guesses (by zone, after each play, lately) and plays against them."""
    name = 'Trickster: reads the CPU back'

    def __init__(self, rng, cpu=None):
        super().__init__(rng, cpu)
        self.calls = Hunches(False, 0.8, 1.0)     # the CPU's calls when it has the ball
        self.guesses = Hunches(False, 0.8, 1.0)   # the CPU's guesses when you have the ball

    def new_game(self):
        super().new_game()
        self.calls.new_game()
        self.guesses.new_game()

    def offense(self, ctx):
        pos = ctx['pos']
        q, self._seen = self.guesses.predict(pos, None, self.rng)
        g, l = gain_loss(pos)
        return PLAYS[argmax([(1 - q[i]) * g[i] - q[i] * l[i] for i in range(3)], self.rng)]

    def defense(self, ctx):
        pos = ctx['pos']
        c, self._seen = self.calls.predict(pos, None, self.rng)
        g, l = gain_loss(pos)
        return PLAYS[argmax([c[i] * (g[i] + l[i]) for i in range(3)], self.rng)]

    def saw(self, poss, o, d, pos):
        super().saw(poss, o, d, pos)
        if poss == 'you':
            self.guesses.learn(self._seen, d)
        else:
            self.calls.learn(self._seen, o)


class Oracle(Player):
    name = "Knows the CPU's exact odds (worst case)"

    def offense(self, ctx):
        q = self.cpu.guess_dist(ctx)
        pos = ctx['pos']
        ev = [(1 - q[i]) * (min(GAIN[p], 3 - pos) + (1 if pos + GAIN[p] >= 3 else 0)) - q[i] * (1.8 if p == 'deep' else 1.2)
              for i, p in enumerate(PLAYS)]
        return PLAYS[argmax(ev, self.rng)]

    def defense(self, ctx):
        c = self.cpu.call_dist(ctx)
        value = [1.0, 1.0, 1.6 if ctx['pos'] < 2 else 1.3]
        return PLAYS[argmax([c[i] * value[i] for i in range(3)], self.rng)]


PLAYERS = [Random, Favorite, ByZone, Cycler, Bait, Balancer, Reader, Oracle]


def run(make_cpu, player_cls, games, seed, series=1):
    rng = random.Random(seed)
    wins = n = 0
    tot = {'off': 0, 'off_ok': 0, 'def': 0, 'def_ok': 0, 'snaps': 0}
    for s in range(games // series):
        cpu = make_cpu(rng)
        you = player_cls(rng, cpu)
        for g in range(series):
            won, st = play_game(you, cpu, rng)
            if g == 0 and series > 1:
                continue   # the first game of a series has no memory to use
            wins += won
            n += 1
            for k in tot:
                tot[k] += st[k]
    return wins / n, tot['off_ok'] / max(1, tot['off']), tot['def_ok'] / max(1, tot['def']), tot['snaps'] / n


if __name__ == '__main__':
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    cpus = [('Normal (today)', lambda r: Normal(r)), ('Hard (first try)', lambda r: Hard(r)), ('Hard', lambda r: Hard2(r))]
    print(f'{games} games per row. Player win %, then how often the player\'s play got through on offense, and how often it guessed right on defense.')
    for name, make in cpus:
        print(f'\n{name}')
        for i, P in enumerate(PLAYERS):
            w, ok, gd, sn = run(make, P, games, seed=1000 + i)
            print(f'  {P.name:42s} wins {w*100:5.1f}%   gets through {ok*100:5.1f}%   guesses right {gd*100:5.1f}%   {sn:4.1f} snaps')
