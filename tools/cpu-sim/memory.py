"""Does remembering past games help? Each CPU plays series of 10 games against the same player; game 1 is skipped."""
import sys
from cpu_sim import *


class DeepLover(Player):
    name = 'Loves Deep Pass'

    def offense(self, ctx):
        return pick(self.rng, [0.15, 0.30, 0.55])

    def defense(self, ctx):
        return pick(self.rng, [0.20, 0.30, 0.50])


class Family(Player):
    """Two people with opposite habits take turns on one phone."""
    name = 'Two people share one phone'

    def __init__(self, rng, cpu=None):
        super().__init__(rng, cpu)
        self.people = [Favorite(rng, cpu), DeepLover(rng, cpu)]
        self.turn = 1

    def new_game(self):
        self.turn = 1 - self.turn
        self.people[self.turn].new_game()

    def offense(self, ctx):
        return self.people[self.turn].offense(ctx)

    def defense(self, ctx):
        return self.people[self.turn].defense(ctx)

    def saw(self, poss, o, d, pos):
        self.people[self.turn].saw(poss, o, d, pos)


series = int(sys.argv[1]) if len(sys.argv) > 1 else 400
players = [Random, Favorite, ByZone, Cycler, Bait, Balancer, Reader, Oracle, Family]
cpus = (('Normal (today)', lambda r: Normal(r)), ('Hard, fresh each game', lambda r: Hard2(r)), ('Hard, remembers', lambda r: Hard2(r, memory=True)))
print(f'Player win % in games 2-10 of {series} ten-game series ({series * 9} games per cell)')
print(f"{'':42s}" + ''.join(f'{n:>24s}' for n, _ in cpus))
for i, P in enumerate(players):
    cells = [run(make, P, series * 10, seed=5000 + i, series=10)[0] for _, make in cpus]
    print(f'{P.name:42s}' + ''.join(f'{c*100:23.1f}%' for c in cells))
