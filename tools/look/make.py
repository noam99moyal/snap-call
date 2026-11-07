# Run: python3 tools/look/make.py, then python3 build.py.
# Builds the two look preview pages from the real games, so the "Old look" is always exactly today's page:
#   look/game.html        from full-cards/game.html  (stopped once: one right guess and the defense gets the ball)
#   look/downs/game.html  from downs/game.html       (stopped twice: the longer field being tested)
# Each page gets the Old look / New look switch in its header (New = scoped CSS + new wording) and a rules
# choice in New game that opens the other page.
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Page:
    def __init__(self, src):
        self.s = (ROOT / src).read_text()

    def rep(self, old, new):
        n = self.s.count(old)
        if n != 1:
            sys.exit(f"expected 1 match, got {n}: {old[:70]!r}")
        self.s = self.s.replace(old, new)


NOTE = """says whether the play was stopped.
     Look preview: the Old look / New look switch in the header flips this page between the current design (Old,
     the same as {src}) and a proposed one (New): the scoreboard is the only box, the snap is played on the
     turf with the two cards facing each other across a chalk line of scrimmage, labels are in plain case instead
     of spaced-out capitals, the announcer has a few lines per result, and How to play is a short list in the cards' words (Stopped / Not stopped).
     New game also has the rules choice: Stopped once (look/) or Stopped twice (look/downs/). */"""

CSS = """
  /* ---------- Look preview ---------- */
  .look-pick { display: inline-flex; border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
  .look-pick button {
    font: 600 13px/1 var(--ui); letter-spacing: 0.02em; color: var(--chalk-dim);
    background: transparent; border: 0; padding: 5px 8px; cursor: pointer; white-space: nowrap;
  }
  .look-pick button[aria-pressed="true"] { background: var(--chalk); color: var(--turf-deep); }
  .look-pick button:focus-visible { outline: 2px solid var(--chalk); outline-offset: -2px; }
  .new-look .old-only, html:not(.new-look) .new-only { display: none; }
  /* The rules choice in New game. */
  .rule-set { display: grid; gap: 8px; }
  .rule-set .opts { display: flex; gap: 8px; }
  .rule-set button {
    flex: 1; min-height: 44px; cursor: pointer; border-radius: 8px; padding: 6px 8px;
    background: transparent; color: var(--chalk); border: 1px solid var(--chalk-faint); font: 700 17px/1.1 var(--ui);
  }
  .rule-set button[aria-checked="true"] { background: var(--chalk); color: var(--ink); border-color: var(--chalk); }
  .rule-set p { margin: 0; font: 400 14px/1.35 var(--ui); color: var(--chalk-dim); }

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
</style>"""

SWITCH_HTML = ('<div class="look-pick" role="group" aria-label="Screen design">'
               '<button type="button" data-look="old" aria-pressed="false">Old look</button>'
               '<button type="button" data-look="new" aria-pressed="true">New look</button></div>')


def rule_set(current, note):
    once, twice = ("true", "false") if current == "once" else ("false", "true")
    return f"""        <div class="rule-set">
          <div class="opts" role="radiogroup" aria-label="Rules">
            <button type="button" role="radio" data-rules="once" aria-checked="{once}">Stopped once</button>
            <button type="button" role="radio" data-rules="twice" aria-checked="{twice}">Stopped twice</button>
          </div>
          <p>{note}</p>
        </div>
"""


STATE_JS = """  let S;
  // Look preview: which design is showing (the switch in the header). Remembered on this device.
  const LOOK_KEY = 'snap-call-look-style';
  let newLook = true;
  try { newLook = localStorage.getItem(LOOK_KEY) !== 'old'; } catch (e) { /* New look */ }
"""


def say_js(red):
    return f"""  const cap = (s) => s[0].toUpperCase() + s.slice(1);
  // New look: each result has a few announcer lines, picked at random, so the play-by-play doesn't repeat itself.
  // Old look: the current line (the first one, unless given). Every line stays short enough for two lines on phones.
  const say = (lines, old = lines[0]) => (newLook ? lines[Math.floor(Math.random() * lines.length)] : old);
  const ballAt = (pos, who) => (newLook && pos === {red} ? 'Ball in the Red Zone.' : `Ball at ${{zoneName(pos, who)}}.`);
  const GAIN_SAYS = {{
    run: ['Good gain. ', 'Found a gap. ', 'Room to run. '],
    short: ['Good gain. ', 'Easy catch. ', 'Moving the chains. '],
    deep: ['Over the top! ', 'Wide open! ', 'Deep ball, caught! '],
  }};"""


def switch_js(other):
    return f"""  function setLook(on) {{
    newLook = on;
    document.documentElement.classList.toggle('new-look', on);
    for (const b of document.querySelectorAll('.look-pick button')) b.setAttribute('aria-pressed', String((b.dataset.look === 'new') === on));
    try {{ localStorage.setItem(LOOK_KEY, on ? 'new' : 'old'); }} catch (e) {{ /* this device just won't remember */ }}
  }}
  setLook(newLook);
  for (const b of document.querySelectorAll('.look-pick button')) b.addEventListener('click', () => {{ setLook(b.dataset.look === 'new'); render(); }});
  // The rules choice in New game opens the other rule set's page, with New game showing.
  for (const b of document.querySelectorAll('.rule-set button')) b.addEventListener('click', () => {{
    if (b.getAttribute('aria-checked') !== 'true') location.href = '{other}?new';
  }});
  for (const b of document.querySelectorAll('.lvl-pick')) b.addEventListener("""


SET_CARDS_JS = """  // ---------- Drawing ----------
  // Picking a card redraws only what changed: a card whose insides are the same keeps its element and image,
  // and just takes the new class, pressed and disabled state. Redrawing every image made the screen flash on
  // hosts that have the browser re-check each image before showing it again (Netlify).
  function setCards(el, html) {
    const t = document.createElement('template');
    t.innerHTML = html;
    const next = [...t.content.children], cur = [...el.children];
    if (next.length !== cur.length) { el.innerHTML = html; return; }
    next.forEach((n, i) => {
      const c = cur[i];
      if (n.tagName !== c.tagName || n.innerHTML !== c.innerHTML) { c.replaceWith(n); return; }
      for (const a of [...c.attributes]) if (!n.hasAttribute(a.name)) c.removeAttribute(a.name);
      for (const a of [...n.attributes]) if (c.getAttribute(a.name) !== a.value) c.setAttribute(a.name, a.value);
    });
  }
"""

START = "  window.claude?.hot?.ready ? window.claude.hot.ready(start) : start(window.claude?.hot?.data ?? {});\n"
OPEN_JS = START + """  // Arriving from the other rule set: ask Normal or Hard right away.
  if (new URLSearchParams(location.search).has('new')) { history.replaceState(null, '', location.pathname); if (S) askLevel(); }
"""


def common(p, src, red, other):
    """Everything both pages share: switch, styles, announcer lines for the results both rule sets have."""
    p.rep("says whether the play was stopped. */", NOTE.format(src=src))
    p.rep("  .rules ul { margin:", "  .rules ul, .rules ol { margin:")
    p.rep("</style>", CSS)
    p.rep("  let S;\n", STATE_JS)
    p.rep("  const cap = (s) => s[0].toUpperCase() + s.slice(1);", say_js(red))
    p.rep("  for (const b of document.querySelectorAll('.lvl-pick')) b.addEventListener(", switch_js(other))
    p.rep(START, OPEN_JS)
    p.rep("  // ---------- Drawing ----------\n", SET_CARDS_JS)
    p.rep("    $('#hand').innerHTML = keys.map((k) => {", "    setCards($('#hand'), keys.map((k) => {")
    p.rep("    }).join('');\n\n    // Specials", "    }).join(''));\n\n    // Specials")
    p.rep("    $('#specials').innerHTML = sp.join('');", "    setCards($('#specials'), sp.join(''));")
    # New look: no line under the hand saying what a stop does; the status line and How to play cover it.
    p.rep("    $('#handHint').textContent = S.poss === 'you'", "    $('#handHint').textContent = newLook ? '' : S.poss === 'you'")
    p.rep("    return { kind: 'gain', zones: PLAYS[o.play].gain };",
          "    return { kind: 'gain', zones: PLAYS[o.play].gain, play: o.play };")
    p.rep("detail: `${NAME[r.by]} threw the flag: snap again.`",
          "detail: say([`${NAME[r.by]} threw the flag. Snap again.`, 'Flag on the play. Snap again.'], `${NAME[r.by]} threw the flag: snap again.`)")
    p.rep("const rest = td ? `${NAME[off]} ${verb(off, 'score')} 7.` : r.how ? '+1 zone.' : `Ball at ${zoneName(S.pos, off)}.`;",
          "const rest = td ? `${say(['Into the end zone! ', 'All the way! ', 'Nobody touches it! '], '')}${NAME[off]} ${verb(off, 'score')} 7.`\n"
          "          : r.how ? '+1 zone.' : `${say(GAIN_SAYS[r.play], '')}${ballAt(S.pos, off)}`;")
    p.rep("const save = r.how === 'juke' ? 'the juke breaks free.' : 'what a catch!';",
          "const save = r.how === 'juke' ? say(['the juke breaks free.', 'one cut and through.', 'a quick juke and gone.'])\n"
          "          : say(['what a catch!', 'a one-handed grab!', 'hauled in anyway!']);")
    p.rep("const lead = r.how === 'hail' ? 'Caught! ' : r.how === 'breakaway' ? 'Breakaway! ' : '';",
          "const lead = r.how === 'hail' ? say(['Caught! ', 'Up for grabs, and caught! ', 'Hail Mary, caught! '])\n"
          "          : r.how === 'breakaway' ? say(['Breakaway! ', 'Gone! ', 'Untouched! ']) : '';")
    p.rep("return { head: r.how === 'tfl' ? 'Tackle for loss!' : 'Sacked!', detail: `The defense got through. ${rest}`, but: `got through. ${rest}`, tone: def };",
          "const how = say(['the defense got through.', 'brought down behind the line.', 'swarmed in the backfield.']);\n"
          "        return { head: r.how === 'tfl' ? 'Tackle for loss!' : 'Sacked!', detail: `${cap(how)} ${rest}`, but: newLook ? `${how} ${rest}` : `got through. ${rest}`, tone: def };")
    p.rep("detail: `Picked off! ${NAME[def]} ${verb(def, 'score')} 7.`",
          "detail: `${say(['Picked off!', 'Pick and gone!', 'All the way back!'])} ${NAME[def]} ${verb(def, 'score')} 7.`")
    p.rep("const detail = `${NAME[who]} ${verb(who, 'kick')} it through. 3 points.`;",
          "const detail = say([`${NAME[who]} ${verb(who, 'kick')} it through. 3 points.`, 'Right down the middle. 3 points.', 'It’s good! 3 points.']);")


SPECIALS_P = "Only one special can work per snap, and a played special is used up either way.</p>"


def both(p, old, new):
    """The Old look keeps `old`; the New look says `new` instead."""
    p.rep(old, f'<span class="old-only">{old}</span><span class="new-only">{new}</span>')


def cards_words(p, home):
    """How to play in the cards' own words: stopped / not stopped, not right / wrong guess."""
    both(p, f"If you guess wrong, they gain nothing and go back 1 zone (never behind their own {home}). They keep the ball.",
         f"If you don’t stop the play, they go back 1 zone instead of gaining (never behind their own {home}).")
    both(p, "Only one special can work per snap, and a played special is used up either way.",
         "Only one special can work per snap, and a played special is used up either way, except when a Challenge Flag "
         "cancels the snap: then the other side’s special goes back to its hand.")
    both(p, "If you run and they guess wrong, it goes all the way for a touchdown.",
         "If your Run isn’t stopped, it goes all the way for a touchdown.")
    both(p, "If you throw deep and they guess wrong, it goes all the way for a touchdown.",
         "If your Deep Pass isn’t stopped, it goes all the way for a touchdown.")
    both(p, "If you guess their pass right (Stop Short or Stop Deep), you score 7.",
         "If you stop a pass (Stop Short or Stop Deep), you score 7.")
    both(p, "If you guess their run right, you recover the ball at midfield.",
         "If you stop a Run, you get the ball at midfield.")
    both(p, "It remembers which plays you call and which ones you guess, and leans on your habits. Mix it up.",
         "It remembers which plays you call and which Stop cards you pick, and leans on your habits. Mix it up.")

# ======================= look/: stopped once (from full-cards/) =======================
p = Page("full-cards/game.html")
common(p, "full-cards/", "ZONES.length - 1", "downs/")
p.rep('<span class="chip">Finished cards</span>', SWITCH_HTML)
p.rep("$('#snap').textContent = S.poss === 'you' ? 'Snap' : 'Snap · Defend';",
      "$('#snap').textContent = S.sel.play === 'fg' ? 'Kick for 3' : S.poss === 'you' ? 'Snap' : newLook ? 'Defend' : 'Snap · Defend';")
p.rep('        <button class="lvl-pick" type="button" data-level="normal">',
      rule_set("once", "Today’s rules: one right guess and the defense gets the ball.")
      + """        <div class="len" role="radiogroup" aria-label="Game length">
          <span>First to</span>
          <button type="button" role="radio" data-target="21" aria-checked="true">21</button>
          <button type="button" role="radio" data-target="28" aria-checked="false">28</button>
          <button type="button" role="radio" data-target="35" aria-checked="false">35</button>
        </div>
"""
      + '        <button class="lvl-pick" type="button" data-level="normal">')

# ---- From the Stopped twice page: the Kick Field Goal card joins your hand in the Red Zone (no more
# Kick FG button), the stage shows the kick, and New game picks the length: first to 21, 28 or 35.
p.rep("  .hand, .specials { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; align-items: start; }\n",
      "  .hand, .specials { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; align-items: start; }\n"
      "  /* In the Red Zone the Kick Field Goal card joins your plays, four in the row. */\n"
      "  .hand.four { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }\n")
p.rep("    .hand, .specials { grid-template-columns: repeat(3, min((100% - 20px) / 3, max(128px, (100dvh - 400px) / 2.8))); }\n",
      "    .hand, .specials { grid-template-columns: repeat(3, min((100% - 20px) / 3, max(128px, (100dvh - 400px) / 2.8))); }\n"
      "    .hand.four { grid-template-columns: repeat(4, min((100% - 24px) / 4, max(128px, (100dvh - 400px) / 2.8))); }\n")
p.rep("  .lvl-pick span { font: 400 14px/1.35 var(--ui); color: var(--chalk-dim); }\n",
      """  .lvl-pick span { font: 400 14px/1.35 var(--ui); color: var(--chalk-dim); }
  .len { display: flex; align-items: center; gap: 8px; }
  .len > span { font: 600 15px/1 var(--ui); color: var(--chalk-dim); margin-right: 4px; }
  .len button {
    flex: 1; height: 44px; cursor: pointer; border-radius: 8px;
    background: transparent; color: var(--chalk); border: 1px solid var(--chalk-faint); font: 400 20px/1 var(--display);
  }
  .len button[aria-checked="true"] { background: var(--chalk); color: var(--ink); border-color: var(--chalk); }
""")
p.rep('<div class="target">First to<b>21</b>', '<div class="target">First to<b id="targetNum">21</b>')
p.rep('      <button class="fg" id="fg" type="button" hidden>Kick FG +3</button>\n', '')
p.rep("<li>Touchdown is 7 points. From the Red Zone you can kick a field goal for 3 instead of snapping.</li>",
      "<li>Touchdown is 7 points. In the Red Zone, the Kick Field Goal card joins your plays: play it instead of snapping to score 3.</li>")
p.rep("<li>First to 21 wins.</li>", "<li>First to 21 wins. For a longer game, pick 28 or 35 at New game.</li>")
p.rep("  const TARGET = 21;\n", "  const TARGETS = [21, 28, 35];\n  const KICK = 'From the Red Zone → Score 3';\n")
p.rep("  const RULES_VERSION = 4;", "  const RULES_VERSION = 5;")
p.rep("    try { return localStorage.getItem(LEVEL_KEY) === 'hard' ? 'hard' : 'normal'; } catch (e) { return 'normal'; }\n  }\n",
      """    try { return localStorage.getItem(LEVEL_KEY) === 'hard' ? 'hard' : 'normal'; } catch (e) { return 'normal'; }
  }
  // So is the game length.
  const TARGET_KEY = 'snap-call-look-target';
  function savedTarget() {
    try { const t = +localStorage.getItem(TARGET_KEY); return TARGETS.includes(t) ? t : 21; } catch (e) { return 21; }
  }
""")
p.rep("  function newGame(level) {", "  function newGame(level, target = savedTarget()) {")
p.rep("      v: RULES_VERSION, level,\n", "      v: RULES_VERSION, level, target,\n")
p.rep("    try { localStorage.setItem(LEVEL_KEY, level); } catch (e) { /* the next visit starts on Normal */ }",
      "    try { localStorage.setItem(LEVEL_KEY, level); localStorage.setItem(TARGET_KEY, target); } catch (e) { /* the next visit starts on Normal, first to 21 */ }")
p.rep("  function fits(key, play, sd) {\n",
      "  function fits(key, play, sd) {\n    if (play === 'fg') return false;   // a kick isn't a snap, so no special goes with it\n")
p.rep("S.score[who] >= TARGET)", "S.score[who] >= S.target)")
p.rep("  function snap() {\n    if (!ready()) return;\n",
      "  function snap() {\n    if (!ready()) return;\n    if (S.sel.play === 'fg') { kickFG('you'); render(); return; }\n")
p.rep("    S.showLast = false; S.move = null;",
      "    // The stage keeps showing the kick until the next pick.\n    S.showLast = true; S.move = null;")
p.rep("const kick = TARGET - S.score.cpu <= 3", "const kick = S.target - S.score.cpu <= 3")
p.rep("    S.phase = 'busy';\n", "    S.phase = 'busy'; S.flip = true;\n")
p.rep("""  const art = (key, alt) => `<img src="cards/${ART[key]}.webp" alt="${alt}" width="600" height="840" decoding="sync">`;\n""",
      """  const art = (key, alt) => `<img src="cards/${ART[key]}.webp" alt="${alt}" width="600" height="840" decoding="sync">`;
  const kickInner = () => `<span class="cv"><img src="cards/kick-field-goal.webp" alt="Kick Field Goal. ${KICK}." width="600" height="840" decoding="sync"></span>`;
  const NO_SNAP = '<div class="card empty"><span class="cv">No snap</span></div>';
""")
p.rep("    $('#lvlTag').hidden = S.level !== 'hard';\n",
      "    $('#lvlTag').hidden = S.level !== 'hard';\n    $('#targetNum').textContent = S.target;\n")
p.rep("    if (S.showLast && L && !L.fg) {\n",
      """    const kicker = S.phase === 'busy' ? 'cpu' : S.showLast && L && L.fg ? L.tone : null;
    if (kicker) {
      const kick = `<div class="card off ${kicker}${S.flip ? ' flip' : ''}">${kickInner()}</div>`;
      $('#slotYou').innerHTML = kicker === 'you' ? kick : NO_SNAP;
      $('#slotCpu').innerHTML = kicker === 'cpu' ? kick : NO_SNAP;
      if (S.phase === 'busy') { medal.className = 'medal'; medal.style.removeProperty('--tone'); medal.textContent = 'Kick'; }
      else { medal.className = 'medal hit'; medal.style.setProperty('--tone', `var(--${kicker})`); medal.textContent = '+3'; }
    } else if (S.showLast && L) {
""")
p.rep("      $('#slotYou').innerHTML = S.sel.play\n",
      "      $('#slotYou').innerHTML = S.sel.play === 'fg'\n        ? `<div class=\"card off you\">${kickInner()}</div>`\n        : S.sel.play\n")
p.rep("    const keys = S.poss === 'you' ? OFF : DEF;\n",
      "    const keys = S.poss === 'you' ? (S.pos === 2 ? [...OFF, 'fg'] : OFF) : DEF;\n    $('#hand').classList.toggle('four', keys.length === 4);\n")
p.rep("""      return `<button type="button" class="card ${PLAYS[k].side}${on ? ' on' : ''}" data-play="${k}" aria-pressed="${on}"${S.phase !== 'pick' ? ' disabled' : ''}>${faceInner(k)}</button>`;""",
      """      const off = S.phase !== 'pick' ? ' disabled' : '';
      if (k === 'fg') return `<button type="button" class="card off kick${on ? ' on' : ''}" data-play="fg" aria-pressed="${on}"${off}>${kickInner()}</button>`;
      return `<button type="button" class="card ${PLAYS[k].side}${on ? ' on' : ''}" data-play="${k}" aria-pressed="${on}"${off}>${faceInner(k)}</button>`;""")
p.rep("    $('#fg').hidden = !(S.phase === 'pick' && S.poss === 'you' && S.pos === 2);\n", "")
p.rep("  $('#fg').addEventListener('click', () => { if (S.phase === 'pick' && S.poss === 'you' && S.pos === 2) { kickFG('you'); render(); } });\n", "")
p.rep("  function askLevel() {\n", """  let lenPick = 21;
  function setLen(t) {
    lenPick = t;
    for (const b of document.querySelectorAll('.len button')) b.setAttribute('aria-checked', String(+b.dataset.target === t));
  }
  for (const b of document.querySelectorAll('.len button')) b.addEventListener('click', () => setLen(+b.dataset.target));
  function askLevel() {
    setLen(S.target);
""")
p.rep("newGame(b.dataset.level); });", "newGame(b.dataset.level, lenPick); });")
p.rep("'card-back', 'touchdown', 'field-goal']) new Image()", "'card-back', 'touchdown', 'field-goal', 'kick-field-goal']) new Image()")
p.rep("        <ul>\n          <li>The field has 3 zones", "        <ul class=\"old-only\">\n          <li>The field has 3 zones")
p.rep("""          <li>Press and hold any card to see it big.</li>
        </ul>
""", """          <li>Press and hold any card to see it big.</li>
        </ul>

        <ul class="new-only">
          <li>The field has 3 zones: your own 25, midfield, the Red Zone. Get past the Red Zone for a touchdown, 7 points. In the Red Zone you can also kick a field goal instead of a play, for 3.</li>
          <li>Each snap, the offense secretly picks a play and the defense secretly picks a Stop card. Both flip at once.</li>
          <li><strong>Not stopped</strong> (the Stop card doesn’t match the play): the ball moves. Run and Short Pass gain 1 zone, Deep Pass gains 2.</li>
          <li><strong>Stopped</strong> (it matches): the defense gets the ball at its own 25. A stopped Deep Pass is intercepted, and they start at midfield.</li>
          <li>First to 21 wins, or pick 28 or 35 at New game.</li>
        </ul>
""")
p.rep(SPECIALS_P, SPECIALS_P + """
        <p class="new-only">You start with 2 specials. You draw one when you’re scored on, and you can hold 3. The marks under CPU show how many it holds, but not which ones.</p>""")
both(p, "If they guess your play, you still gain 1 zone. A guessed Deep Pass gains 1 instead of being intercepted.",
     "If your play is stopped, you still gain 1 zone. A stopped Deep Pass gains 1 instead of being intercepted.")
cards_words(p, "25")
p.rep("""      case 'stop':
        S.poss = def; S.pos = 0;
        return { head: 'Stopped', detail: `${NAME[def]} ${verb(def, 'take')} over at ${def === 'you' ? 'your' : 'their'} 25.`, tone: def };""",
      """      case 'stop': {
        S.poss = def; S.pos = 0;
        const at = `${NAME[def]} ${verb(def, 'take')} over at ${def === 'you' ? 'your' : 'their'} 25.`;
        return { head: 'Stopped', detail: say([at, `Stuffed. ${at}`, `Read it. ${at}`]), tone: def };
      }""")
p.rep("return { head: 'Intercepted!', detail: `${NAME[def]} ${verb(def, 'start')} at midfield.`, tone: def };",
      "return { head: 'Intercepted!', detail: say([`${NAME[def]} ${verb(def, 'start')} at midfield.`, 'Jumped the route. Ball at midfield.', 'Read it all the way. Ball at midfield.']), tone: def };")
p.rep("return { head: 'Fumble!', detail: `${NAME[def]} ${verb(def, 'recover')} at midfield.`, tone: def };",
      "return { head: 'Fumble!', detail: say([`${NAME[def]} ${verb(def, 'recover')} at midfield.`, `Loose ball! ${NAME[def]} ${verb(def, 'fall')} on it.`]), tone: def };")
p.rep("const HARD_KEY = 'snap-call-hard';", "const HARD_KEY = 'snap-call-look-hard';")
p.s = re.sub(r"(?<![\w/.\-])cards/", "../full-cards/cards/", p.s)
(ROOT / "look/game.html").write_text(p.s)

# ======================= look/downs/: stopped twice (from downs/) =======================
p = Page("downs/game.html")
common(p, "downs/", "RED", "../")
p.rep('<span class="chip">Downs test</span>', SWITCH_HTML)
p.rep("S.poss === 'you' ? 'Snap' : 'Snap · Defend';", "S.poss === 'you' ? 'Snap' : newLook ? 'Defend' : 'Snap · Defend';")
p.rep('        <div class="len" role="radiogroup"',
      rule_set("twice", "Being tested: a longer field, and one more try in each zone.")
      + '        <div class="len" role="radiogroup"')
p.rep("        <p>This page tests a longer field where you get two chances in each zone.</p>\n        <ul>",
      "        <p class=\"old-only\">This page tests a longer field where you get two chances in each zone.</p>\n        <ul class=\"old-only\">")
p.rep("""          <li>Press and hold any card to see it big.</li>
        </ul>
""", """          <li>Press and hold any card to see it big.</li>
        </ul>

        <ul class="new-only">
          <li>The field has 5 zones: your own 20, your own 35, midfield, their 35, the Red Zone. Get past the Red Zone for a touchdown, 7 points. In the Red Zone you can also kick a field goal instead of a play, for 3.</li>
          <li>Each snap, the offense secretly picks a play and the defense secretly picks a Stop card. Both flip at once.</li>
          <li><strong>Not stopped</strong> (the Stop card doesn’t match the play): the ball moves. Run and Short Pass gain 1 zone, Deep Pass gains 2.</li>
          <li><strong>Stopped once</strong> (it matches): the offense keeps the ball and tries again, and the ball turns sideways as a reminder. Reaching a new zone starts the count over.</li>
          <li><strong>Stopped twice</strong> in the same zone: the defense gets the ball at its own 20. If the second stop is on a Deep Pass, it’s intercepted, and they start at midfield.</li>
          <li>First to 21 wins, or pick 28 or 35 at New game.</li>
        </ul>
""")
p.rep(SPECIALS_P, SPECIALS_P + """
        <p class="new-only">You start with 2 specials, or 3 if you get the ball second. You draw one when you’re scored on and when you win the ball back with a stop, and you can hold 3. The marks under CPU show how many it holds, but not which ones.</p>""")
p.rep("<dd>If they guess your play, it doesn’t count as a stop: you still gain 1 zone.</dd>",
      "<dd><span class=\"old-only\">If they guess your play, it doesn’t count as a stop: you still gain 1 zone.</span>"
      "<span class=\"new-only\">If your play is stopped, you still gain 1 zone.</span></dd>")
cards_words(p, "20")
# Winning the ball back: lines now end with a period, and the draw joins subject-led lines with "and"
# (the Old look's lines all are, so they read exactly as before).
p.rep("""    const drew = S.hands[who].length > n ? ` and ${verb(who, 'draw')} a special` : '';
    return { detail: `${text}${drew}.`, log: `${text}.` };""",
      """    if (S.hands[who].length === n) return { detail: text, log: text };
    // "CPU recovers at midfield and draws a special." or "Jumped the route. Ball at midfield. CPU draws a special."
    const detail = text.startsWith(`${NAME[who]} `) && !text.slice(0, -1).includes('.')
      ? `${text.slice(0, -1)} and ${verb(who, 'draw')} a special.` : `${text} ${NAME[who]} ${verb(who, 'draw')} a special.`;
    return { detail, log: text };""")
p.rep("return { head: 'Stopped once', detail: 'One more try.', tone: def, once: true };",
      "return { head: 'Stopped once', detail: say(['One more try.', 'Stuffed. One more try.', 'Read it. One more try.', 'No room. One more try.']), tone: def, once: true };")
p.rep("return { ...wonBack(def, `${NAME[def]} ${verb(def, 'start')} at midfield`), head: 'Intercepted!', tone: def, twice: true };",
      "return { ...wonBack(def, say([`${NAME[def]} ${verb(def, 'start')} at midfield.`, 'Jumped the route. Ball at midfield.', 'Read it all the way. Ball at midfield.'])), head: 'Intercepted!', tone: def, twice: true };")
p.rep("return { ...wonBack(def, `${NAME[def]} ${verb(def, 'take')} over at ${def === 'you' ? 'your' : 'their'} own 20`), head: 'Stopped twice', tone: def, twice: true };",
      "return { ...wonBack(def, say([`${NAME[def]} ${verb(def, 'take')} over at ${def === 'you' ? 'your' : 'their'} own 20.`, `Held again. ${NAME[def]} ${verb(def, 'take')} over.`, `Two stops. ${NAME[def]} ${verb(def, 'take')} over.`])), head: 'Stopped twice', tone: def, twice: true };")
p.rep("return { ...wonBack(def, `${NAME[def]} ${verb(def, 'recover')} at midfield`), head: 'Fumble!', tone: def };",
      "return { ...wonBack(def, say([`${NAME[def]} ${verb(def, 'recover')} at midfield.`, `Loose ball! ${NAME[def]} ${verb(def, 'fall')} on it.`])), head: 'Fumble!', tone: def };")
p.rep("const HARD_KEY = 'snap-call-downs-hard';", "const HARD_KEY = 'snap-call-look-downs-hard';")
p.rep("const TARGET_KEY = 'snap-call-downs-target';", "const TARGET_KEY = 'snap-call-look-downs-target';")
p.s = p.s.replace("../full-cards/", "../../full-cards/")
p.s = re.sub(r"(?<![\w/.\-])cards/", "../../downs/cards/", p.s)
(ROOT / "look/downs").mkdir(exist_ok=True)
(ROOT / "look/downs/game.html").write_text(p.s)
print("built look/ and look/downs/")
