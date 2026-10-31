"""Final check: today's CPU vs the tuned Hard, more games, fresh seeds."""
import sys
from cpu_sim import *

games = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
for name, make in (('Normal (today)', lambda r: Normal(r)), ('Hard', lambda r: Hard2(r))):
    print(f'\n{name}')
    for i, P in enumerate(PLAYERS):
        w, ok, gd, sn = run(make, P, games, seed=90000 + i)
        print(f'  {P.name:42s} wins {w*100:5.1f}%   gets through {ok*100:5.1f}%   guesses right {gd*100:5.1f}%   {sn:4.1f} snaps')
