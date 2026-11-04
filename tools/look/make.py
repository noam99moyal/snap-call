# Run: python3 tools/look/make.py, then python3 build.py.
# Builds look/game.html from full-cards/game.html: the current design ("Old look") plus the proposed one
# ("New look"), switched in the header. Old look = full-cards exactly; New look = scoped CSS + new wording.
import re, sys
from pathlib import Path
root = Path.home() / "Desktop/snap-call"
s = (root / "full-cards/game.html").read_text()

def rep(old, new):
    global s
    n = s.count(old)
    if n != 1:
        sys.exit(f"expected 1 match, got {n}: {old[:70]!r}")
    s = s.replace(old, new)

rep("""says whether the play was stopped. */""",
"""says whether the play was stopped.
     Look preview: the Old look / New look switch in the header flips this page between the current design (Old,
     the same as full-cards/) and a proposed one (New): the scoreboard is the only box, the snap is played on the
     turf with the two cards facing each other across a chalk line of scrimmage, labels are in plain case instead
     of spaced-out capitals, the announcer has a few lines per result, and How to play walks through one drive. */""")

rep("  .rules ul { margin:", "  .rules ul, .rules ol { margin:")

rep("</style>", """
  /* ---------- Look preview ---------- */
  .look-pick { display: inline-flex; border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
  .look-pick button {
    font: 600 13px/1 var(--ui); letter-spacing: 0.02em; color: var(--chalk-dim);
    background: transparent; border: 0; padding: 5px 8px; cursor: pointer; white-space: nowrap;
  }
  .look-pick button[aria-pressed="true"] { background: var(--chalk); color: var(--turf-deep); }
  .look-pick button:focus-visible { outline: 2px solid var(--chalk); outline-offset: -2px; }
  .new-look .old-only, html:not(.new-look) .new-only { display: none; }

  /* New look: everything below only applies when the switch is on New. */
  .new-look .team .label { font: 700 19px/1 var(--ui); letter-spacing: 0.01em; text-transform: none; }
  .new-look .who-ez { font: 700 13px/1 var(--ui); letter-spacing: 0; text-transform: none; }
  .new-look .slot-label { font: 700 17px/1 var(--ui); letter-spacing: 0.01em; text-transform: none; }
  .new-look .lvl-tag { font: 700 14px/1 var(--ui); letter-spacing: 0; text-transform: none; }
  /* The snap is played on the turf itself: no box, just a soft light. */
  .new-look .stage {
    background: radial-gradient(ellipse 60% 55% at 50% 42%, rgba(236, 243, 232, 0.09), transparent 72%);
    border: 0; border-radius: 0; padding: 6px 0 4px;
  }
  /* The line of scrimmage: offense on one side, defense on the other. */
  .new-look .table { position: relative; }
  .new-look .table::before {
    content: ''; position: absolute; left: 50%; top: 22px; bottom: -4px; width: 2px; margin-left: -1px;
    background: repeating-linear-gradient(180deg, var(--chalk-faint) 0 9px, transparent 9px 16px);
  }
  .new-look .medal { position: relative; background: var(--turf-deep); }
  .new-look .medal.hit { background: var(--tone); }
  /* The play-by-play loses its box: a chalk rule on top is enough. */
  .new-look .box { background: none; border: 0; border-top: 2px solid var(--line); border-radius: 0; padding: 14px 0 0; }
  /* Phones: the title and the buttons don't fit on one row, so both rows are centered. */
  @media (max-width: 500px) {
    .new-look .top { flex-direction: column; align-items: center; gap: 10px; }
    .new-look .brand { flex: none; justify-content: center; }
    .new-look .top-actions { margin-left: 0; }
  }
</style>""")

rep('<span class="chip">Finished cards</span>',
    '<div class="look-pick" role="group" aria-label="Screen design">'
    '<button type="button" data-look="old" aria-pressed="false">Old look</button>'
    '<button type="button" data-look="new" aria-pressed="true">New look</button></div>')

rep("$('#snap').textContent = S.poss === 'you' ? 'Snap' : 'Snap · Defend';",
    "$('#snap').textContent = S.poss === 'you' ? 'Snap' : newLook ? 'Defend' : 'Snap · Defend';")

# ---- How to play: the current bullets (Old) and the one-drive version (New)
rep("        <ul>\n          <li>The field has 3 zones", "        <ul class=\"old-only\">\n          <li>The field has 3 zones")
rep("""          <li>Press and hold any card to see it big.</li>
        </ul>
""", """          <li>Press and hold any card to see it big.</li>
        </ul>

        <p class="new-only">Each snap, the offense secretly picks a play and the defense tries to guess it. Both cards flip at once. A wrong guess moves the ball. A right guess stops the play, and the defense gets the ball.</p>
        <h3 class="new-only">One drive, snap by snap</h3>
        <ol class="new-only">
          <li>You start at your own 25 and call Run. The CPU guesses Stop Short. Wrong guess, so you gain a zone to midfield.</li>
          <li>At midfield you call Short Pass, and the CPU guesses Stop Run. Wrong again, and you’re in the Red Zone.</li>
          <li>From the Red Zone you could kick a field goal for 3, but you call Deep Pass and the CPU guesses Stop Short. Touchdown, 7 points.</li>
          <li>The CPU gets the ball at its own 25 and draws a special. It calls Run, you guess Stop Run, and the ball is yours at your own 25.</li>
        </ol>
        <p class="new-only">Run and Short Pass gain 1 zone, and Deep Pass gains 2. A guessed Deep Pass is intercepted, and the defense starts at midfield.</p>
        <p class="new-only">First to 21 wins. Press and hold any card to see it big.</p>
""")
rep("""Only one special can work per snap, and a played special is used up either way.</p>""",
"""Only one special can work per snap, and a played special is used up either way.</p>
        <p class="new-only">You start with 2 specials. You draw one when you’re scored on, and you can hold 3. The marks under CPU show how many it holds, but not which ones.</p>""")

# ---- Announcer: New look picks one of a few lines; Old look keeps the current line
rep("  let S;\n", """  let S;
  // Look preview: which design is showing (the switch in the header). Remembered on this device.
  const LOOK_KEY = 'snap-call-look-style';
  let newLook = true;
  try { newLook = localStorage.getItem(LOOK_KEY) !== 'old'; } catch (e) { /* New look */ }
""")
rep("  const cap = (s) => s[0].toUpperCase() + s.slice(1);",
"""  const cap = (s) => s[0].toUpperCase() + s.slice(1);
  // New look: each result has a few announcer lines, picked at random, so the play-by-play doesn't repeat itself.
  // Old look: the current line (the first one, unless given). Every line stays short enough for two lines on phones.
  const say = (lines, old = lines[0]) => (newLook ? lines[Math.floor(Math.random() * lines.length)] : old);
  const ballAt = (pos, who) => (newLook && pos === ZONES.length - 1 ? 'Ball in the Red Zone.' : `Ball at ${zoneName(pos, who)}.`);
  const GAIN_SAYS = {
    run: ['Good gain. ', 'Found a gap. ', 'Room to run. '],
    short: ['Good gain. ', 'Easy catch. ', 'Moving the chains. '],
    deep: ['Over the top! ', 'Wide open! ', 'Deep ball, caught! '],
  };""")
rep("    return { kind: 'gain', zones: PLAYS[o.play].gain };",
    "    return { kind: 'gain', zones: PLAYS[o.play].gain, play: o.play };")
rep("detail: `${NAME[r.by]} threw the flag: snap again.`",
    "detail: say([`${NAME[r.by]} threw the flag. Snap again.`, 'Flag on the play. Snap again.'], `${NAME[r.by]} threw the flag: snap again.`)")
rep("const rest = td ? `${NAME[off]} ${verb(off, 'score')} 7.` : r.how ? '+1 zone.' : `Ball at ${zoneName(S.pos, off)}.`;",
    "const rest = td ? `${say(['Into the end zone! ', 'All the way! ', 'Nobody touches it! '], '')}${NAME[off]} ${verb(off, 'score')} 7.`\n"
    "          : r.how ? '+1 zone.' : `${say(GAIN_SAYS[r.play], '')}${ballAt(S.pos, off)}`;")
rep("const save = r.how === 'juke' ? 'the juke breaks free.' : 'what a catch!';",
    "const save = r.how === 'juke' ? say(['the juke breaks free.', 'one cut and through.', 'a quick juke and gone.'])\n"
    "          : say(['what a catch!', 'a one-handed grab!', 'hauled in anyway!']);")
rep("const lead = r.how === 'hail' ? 'Caught! ' : r.how === 'breakaway' ? 'Breakaway! ' : '';",
    "const lead = r.how === 'hail' ? say(['Caught! ', 'Up for grabs, and caught! ', 'Hail Mary, caught! '])\n"
    "          : r.how === 'breakaway' ? say(['Breakaway! ', 'Gone! ', 'Untouched! ']) : '';")
rep("""      case 'stop':
        S.poss = def; S.pos = 0;
        return { head: 'Stopped', detail: `${NAME[def]} ${verb(def, 'take')} over at ${def === 'you' ? 'your' : 'their'} 25.`, tone: def };""",
"""      case 'stop': {
        S.poss = def; S.pos = 0;
        const at = `${NAME[def]} ${verb(def, 'take')} over at ${def === 'you' ? 'your' : 'their'} 25.`;
        return { head: 'Stopped', detail: say([at, `Stuffed. ${at}`, `Read it. ${at}`]), tone: def };
      }""")
rep("return { head: 'Intercepted!', detail: `${NAME[def]} ${verb(def, 'start')} at midfield.`, tone: def };",
    "return { head: 'Intercepted!', detail: say([`${NAME[def]} ${verb(def, 'start')} at midfield.`, 'Jumped the route. Ball at midfield.', 'Read it all the way. Ball at midfield.']), tone: def };")
rep("return { head: r.how === 'tfl' ? 'Tackle for loss!' : 'Sacked!', detail: `The defense got through. ${rest}`, but: `got through. ${rest}`, tone: def };",
    "const how = say(['the defense got through.', 'brought down behind the line.', 'swarmed in the backfield.']);\n"
    "        return { head: r.how === 'tfl' ? 'Tackle for loss!' : 'Sacked!', detail: `${cap(how)} ${rest}`, but: newLook ? `${how} ${rest}` : `got through. ${rest}`, tone: def };")
rep("return { head: 'Fumble!', detail: `${NAME[def]} ${verb(def, 'recover')} at midfield.`, tone: def };",
    "return { head: 'Fumble!', detail: say([`${NAME[def]} ${verb(def, 'recover')} at midfield.`, `Loose ball! ${NAME[def]} ${verb(def, 'fall')} on it.`]), tone: def };")
rep("detail: `Picked off! ${NAME[def]} ${verb(def, 'score')} 7.`",
    "detail: `${say(['Picked off!', 'Pick and gone!', 'All the way back!'])} ${NAME[def]} ${verb(def, 'score')} 7.`")
rep("const detail = `${NAME[who]} ${verb(who, 'kick')} it through. 3 points.`;",
    "const detail = say([`${NAME[who]} ${verb(who, 'kick')} it through. 3 points.`, 'Right down the middle. 3 points.', 'It’s good! 3 points.']);")

# ---- The switch
rep("  for (const b of document.querySelectorAll('.lvl-pick')) b.addEventListener(",
"""  function setLook(on) {
    newLook = on;
    document.documentElement.classList.toggle('new-look', on);
    for (const b of document.querySelectorAll('.look-pick button')) b.setAttribute('aria-pressed', String((b.dataset.look === 'new') === on));
    try { localStorage.setItem(LOOK_KEY, on ? 'new' : 'old'); } catch (e) { /* this device just won't remember */ }
  }
  setLook(newLook);
  for (const b of document.querySelectorAll('.look-pick button')) b.addEventListener('click', () => { setLook(b.dataset.look === 'new'); render(); });
  for (const b of document.querySelectorAll('.lvl-pick')) b.addEventListener(""")

# ---- Own Hard memory, so the preview doesn't change the main game's
rep("const HARD_KEY = 'snap-call-hard';", "const HARD_KEY = 'snap-call-look-hard';")

# ---- Card images come from full-cards/
s = re.sub(r"(?<![\w/.])cards/", "../full-cards/cards/", s)
(root / "look/game.html").write_text(s)
print("ok")
