# Run: python3 tools/look/make.py, then python3 build.py.
# Builds the two look preview pages from the real games, so the "Old look" is always exactly today's page:
#   look/game.html        from full-cards/game.html  (stopped once: one right guess and the defense gets the ball)
#   look/downs/game.html  from downs/game.html       (stopped twice: the longer field being tested)
# Both keep today's design and get the proposed wording: varied announcer lines, How to play as a short list in the
# cards' words, Offense / Defense over the hand, and helper lines only in your first game. New game also has a
# rules choice that opens the other page.
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
     Look preview: today's design (the same as {src}) with proposed wording. The announcer has a few lines per result,
     How to play is a short list in the cards' words (Stopped / Not stopped), the hand says just Offense or Defense, and
     the helper lines (under the field, in the empty card spot, at kickoff) show only in your first game: How to play has
     Show tips again. New game also has the rules choice: Stopped once (look/) or Stopped twice (look/downs/). */"""

CSS = """
  /* ---------- Look preview ---------- */
  /* The rules choice in New game. */
  .rule-set { display: grid; gap: 8px; }
  .rule-set .opts { display: flex; gap: 8px; }
  .rule-set button {
    flex: 1; min-height: 44px; cursor: pointer; border-radius: 8px; padding: 6px 8px;
    background: transparent; color: var(--chalk); border: 1px solid var(--chalk-faint); font: 700 17px/1.1 var(--ui);
  }
  .rule-set button[aria-checked="true"] { background: var(--chalk); color: var(--ink); border-color: var(--chalk); }
  .rule-set p { margin: 0; font: 400 14px/1.35 var(--ui); color: var(--chalk-dim); }
  /* The line under the field only shows when it says something the screen doesn't (see showStatus). While it can
     come and go between snaps, it keeps its room so the cards below don't jump. */
  .status[hidden] { display: none; }
  .status.room { min-height: 48px; }
  @media (min-width: 900px) { .status.room { min-height: 24px; } }
  .rules .tips-again { justify-self: start; }
  /* Phones: the title and the buttons are centered, each on its own row. */
  @media (max-width: 500px) {
    .top { flex-direction: column; align-items: center; gap: 10px; }
    .brand { flex: none; justify-content: center; }
    .top-actions { margin-left: 0; }
  }
</style>"""



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


def state_js():
    return f"""  let S;
  // First-game tips: the helper lines under the field, in the empty card spot and at kickoff. Each one shows until
  // you've done it once (the card spot's until your first snap), and none after your first game on this device.
  // Show tips again (How to play) brings them back.
  const TIPS_KEY = 'snap-call-look-tips';
  const FRESH_TIPS = {{ on: true, off: false, def: false, hold: false }};
  let tips = {{ ...FRESH_TIPS }};
  try {{ tips = {{ ...FRESH_TIPS, ...JSON.parse(localStorage.getItem(TIPS_KEY)) }}; }} catch (e) {{ /* tips on */ }}
  const tip = (k) => tips.on && !tips[k];
  function saveTips() {{ try {{ localStorage.setItem(TIPS_KEY, JSON.stringify(tips)); }} catch (e) {{ /* tips come back next visit */ }} }}
  function tipDone(k) {{ if (tip(k)) {{ tips[k] = true; saveTips(); }} }}
  // A snap teaches the tip for your side, and the game has started, so the card spot's tip goes too.
  function markTips() {{
    tipDone(S.poss === 'you' ? 'off' : 'def');
    tipDone('hold');
  }}
"""


def say_js(red):
    return f"""  const cap = (s) => s[0].toUpperCase() + s.slice(1);
  // Each result has a few announcer lines, picked at random, so the play-by-play doesn't repeat itself.
  // Every line stays short enough for two lines on phones.
  const say = (lines) => lines[Math.floor(Math.random() * lines.length)];
  const ballAt = (pos, who) => (pos === {red} ? 'Ball in the Red Zone.' : `Ball at ${{zoneName(pos, who)}}.`);
  const GAIN_SAYS = {{
    run: ['Good gain. ', 'Found a gap. ', 'Room to run. '],
    short: ['Good gain. ', 'Easy catch. ', 'Moving the chains. '],
    deep: ['Over the top! ', 'Wide open! ', 'Deep ball, caught! '],
  }};"""


def rules_js(other):
    return f"""  // The rules choice in New game opens the other rule set's page, with New game showing.
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
  // The line under the field. `room` keeps its space while it can come and go, so the cards below don't jump.
  function showStatus(head, line, room) {
    $('#status').textContent = head;
    $('#hint').textContent = line;
    const box = $('.status');
    box.hidden = !room && !head && !line;
    box.classList.toggle('room', room);
  }
"""

START = "  window.claude?.hot?.ready ? window.claude.hot.ready(start) : start(window.claude?.hot?.data ?? {});\n"
OPEN_JS = START + """  // Arriving from the other rule set: ask Normal or Hard right away.
  if (new URLSearchParams(location.search).has('new')) { history.replaceState(null, '', location.pathname); if (S) askLevel(); }
"""


def common(p, src, red, other):
    """Everything both pages share: styles, tips, announcer lines for the results both rule sets have, Offense / Defense."""
    p.rep("says whether the play was stopped. */", NOTE.format(src=src))
    p.rep("</style>", CSS)
    p.rep("  let S;\n", state_js())
    p.rep("  const cap = (s) => s[0].toUpperCase() + s.slice(1);", say_js(red))
    p.rep("  for (const b of document.querySelectorAll('.lvl-pick')) b.addEventListener(", rules_js(other))
    p.rep(START, OPEN_JS)
    p.rep("  // ---------- Drawing ----------\n", SET_CARDS_JS)
    p.rep("    $('#hand').innerHTML = keys.map((k) => {", "    setCards($('#hand'), keys.map((k) => {")
    p.rep("    }).join('');\n\n    // Specials", "    }).join(''));\n\n    // Specials")
    p.rep("    $('#specials').innerHTML = sp.join('');", "    setCards($('#specials'), sp.join(''));")
    # The hand just says Offense or Defense: the card colors say the rest, and How to play explains stops.
    p.rep('<span id="handLabel">Your play</span><span id="handHint"></span>', '<span id="handLabel">Offense</span>')
    p.rep("$('#handLabel').textContent = S.poss === 'you' ? 'Your play (offense)' : 'Your guess (defense)';",
          "$('#handLabel').textContent = S.poss === 'you' ? 'Offense' : 'Defense';")
    # Tips: marked as learned by a snap and by holding a card; the first game's end turns them all off.
    p.rep("  function snap() {\n    if (!ready()) return;\n", "  function snap() {\n    if (!ready()) return;\n    markTips();\n")
    p.rep("  function showZoom(img) {\n", "  function showZoom(img) {\n    if (tip('hold')) { tipDone('hold'); render(); }\n")
    p.rep("  function render() {\n", "  function render() {\n    if (S.phase === 'over' && tips.on) { tips.on = false; saveTips(); }\n")
    p.rep("'<div class=\"card empty\"><span class=\"cv\">Pick a card below. Hold one to see it big.</span></div>'",
          "`<div class=\"card empty\"><span class=\"cv\">${tip('hold') ? 'Pick a card below. Hold one to see it big.' : ''}</span></div>`")
    p.rep("remembers your last few games on this device.</p>\n",
          "remembers your last few games on this device.</p>\n"
          "        <button class=\"ghost tips-again\" id=\"tipsAgain\" type=\"button\">Show tips again</button>\n")
    p.rep("  $('#closeRules').addEventListener('click', () => $('#rules').close());\n",
          "  $('#closeRules').addEventListener('click', () => $('#rules').close());\n"
          "  $('#tipsAgain').addEventListener('click', () => { tips = { ...FRESH_TIPS }; saveTips(); $('#rules').close(); render(); });\n")
    p.rep("    return { kind: 'gain', zones: PLAYS[o.play].gain };",
          "    return { kind: 'gain', zones: PLAYS[o.play].gain, play: o.play };")
    p.rep("detail: `${NAME[r.by]} threw the flag: snap again.`",
          "detail: say([`${NAME[r.by]} threw the flag. Snap again.`, 'Flag on the play. Snap again.'])")
    p.rep("const rest = td ? `${NAME[off]} ${verb(off, 'score')} 7.` : r.how ? '+1 zone.' : `Ball at ${zoneName(S.pos, off)}.`;",
          "const rest = td ? `${say(['Into the end zone! ', 'All the way! ', 'Nobody touches it! '])}${NAME[off]} ${verb(off, 'score')} 7.`\n"
          "          : r.how ? '+1 zone.' : `${say(GAIN_SAYS[r.play])}${ballAt(S.pos, off)}`;")
    p.rep("const save = r.how === 'juke' ? 'the juke breaks free.' : 'what a catch!';",
          "const save = r.how === 'juke' ? say(['the juke breaks free.', 'one cut and through.', 'a quick juke and gone.'])\n"
          "          : say(['what a catch!', 'a one-handed grab!', 'hauled in anyway!']);")
    p.rep("const lead = r.how === 'hail' ? 'Caught! ' : r.how === 'breakaway' ? 'Breakaway! ' : '';",
          "const lead = r.how === 'hail' ? say(['Caught! ', 'Up for grabs, and caught! ', 'Hail Mary, caught! '])\n"
          "          : r.how === 'breakaway' ? say(['Breakaway! ', 'Gone! ', 'Untouched! ']) : '';")
    p.rep("return { head: r.how === 'tfl' ? 'Tackle for loss!' : 'Sacked!', detail: `The defense got through. ${rest}`, but: `got through. ${rest}`, tone: def };",
          "const how = say(['the defense got through.', 'brought down behind the line.', 'swarmed in the backfield.']);\n"
          "        return { head: r.how === 'tfl' ? 'Tackle for loss!' : 'Sacked!', detail: `${cap(how)} ${rest}`, but: `${how} ${rest}`, tone: def };")
    p.rep("detail: `Picked off! ${NAME[def]} ${verb(def, 'score')} 7.`",
          "detail: `${say(['Picked off!', 'Pick and gone!', 'All the way back!'])} ${NAME[def]} ${verb(def, 'score')} 7.`")
    p.rep("const detail = `${NAME[who]} ${verb(who, 'kick')} it through. 3 points.`;",
          "const detail = say([`${NAME[who]} ${verb(who, 'kick')} it through. 3 points.`, 'Right down the middle. 3 points.', 'It’s good! 3 points.']);")
    phone_b(p)


# ---------- Phones: one screen per snap (layout B from mockups/phone/) ----------
PHONE_CSS = """
  /* ---------- Phones: one screen per snap ----------
     A portrait phone shows the whole snap at once, with nothing to scroll:
       the score bar, with How to play, New game and Play by play in the ⋯ menu
       the field as a strip seen from above, the ball on the zone it's in
       the stage, drawn on that zone's field card: your card, the medal, the CPU's card, then the result
       your hand along the bottom, plays then specials, overlapping like cards held in a hand
     Tap a card and it goes on the stage; the medal between the two cards becomes the Snap button.
     Landscape phones and wide screens keep the layouts above. */
  .menu-btn, #showLog, .zn { display: none; }
  button.medal { appearance: none; box-sizing: content-box; padding: 0; background: none; cursor: default; }
  .log-sheet { width: min(480px, calc(100% - 32px)); }
  .log-sheet .log { max-height: none; }

  /* ---------- The stage, on every screen ---------- */
  /* A special decided the snap: the medal is gold and says what it did. */
  .medal.gold { font-size: 11.5px; }
  /* The headline under the cards is blue when the offense won the snap and red when the defense did, like the cards. */
  .result { --offense: #7aa2ff; --defense: #ff4b5c; }
  /* Points read as a score. */
  .medal.big { font-size: 21px; }

  /* A kick isn't a matchup: the kicker's card stands alone with the medal, and nobody's card waits face down. */
  .table[data-solo] { justify-content: center; }
  .table[data-solo="you"] { grid-template-columns: minmax(0, 132px) auto; }
  .table[data-solo="cpu"] { grid-template-columns: auto minmax(0, 132px); }
  .table[data-solo="you"] > .slot:last-child, .table[data-solo="cpu"] > .slot:first-child { display: none; }

  /* The special that decided the snap comes to the front, glowing; the play card it beat peeks out behind. */
  .slot .card.won > .cv { translate: 0 -21cqi; rotate: 3deg; transform-origin: 50% 100%; filter: brightness(0.8); }
  .slot .card.cpu.won > .cv { rotate: -3deg; }
  .slot .card.won .tuck { z-index: 1; transform: none; }
  .slot .card.won .tag { display: none; }
  .slot .card.won.fresh .tuck { animation: to-front 0.35s 0.45s ease-out both; }
  .slot .card.cpu.won.fresh .tuck { animation-name: to-front-cpu; }
  .slot .card.won.fresh > .cv { animation: to-back 0.35s 0.45s ease-out both; }
  .slot .card.won.fresh.flip > .cv { animation: flip 0.38s ease-out, to-back 0.35s 0.45s ease-out both; }
  @keyframes to-front { from { transform: translateY(-21cqi) rotate(3deg); z-index: -1; } }
  @keyframes to-front-cpu { from { transform: translateY(-21cqi) rotate(-3deg); z-index: -1; } }
  @keyframes to-back { from { translate: 0 0; rotate: 0deg; filter: none; } }
  @media (max-width: 899px) and (min-height: 460px) {
    .wrap {
      height: 100dvh; box-sizing: border-box; max-width: 540px;
      padding-block: max(8px, env(safe-area-inset-top, 0px)) max(8px, env(safe-area-inset-bottom, 0px));
      padding-left: max(10px, env(safe-area-inset-left, 0px)); padding-right: max(10px, env(safe-area-inset-right, 0px));
      grid-template-columns: minmax(0, 1fr) auto;
      grid-template-rows: auto auto minmax(0, 1fr) auto;
      grid-template-areas: "board menu" "field field" "stage stage" "play play";
      justify-content: stretch; gap: 6px;
    }
    .scoreline { display: contents; }
    .actions, .log-box { display: none; }

    /* Score bar: the CPU's special marks sit beside its name, so both sides are two short lines. */
    .board { grid-area: board; padding: 5px 12px; gap: 6px; }
    .team { gap: 8px; }
    .team .who { gap: 3px; }
    .team .label { font-size: 13px; letter-spacing: 0.12em; }
    .team .score { font-size: 28px; min-width: 1.2em; }
    .poss { font-size: 11px; }
    .poss svg { width: 15px; height: 9px; }
    .team.cpu .who { grid-template-columns: auto auto; align-items: center; column-gap: 6px; }
    .team.cpu .poss { grid-row: 2; grid-column: 1 / -1; }
    .pips { gap: 3px; }
    .pips i { width: 9px; height: 13px; }
    .target { font-size: 11px; }
    .target b { font-size: 17px; margin-top: 1px; }
    .lvl-tag { margin-top: 2px; font-size: 9px; }

    /* The ⋯ menu. The title stays for screen readers. */
    .top { grid-area: menu; display: block; position: relative; }
    .brand { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
    .menu-btn { display: grid; place-items: center; width: 44px; height: 100%; padding: 0; background: var(--board); border-color: var(--line); border-radius: 10px; }
    .menu-btn svg { width: 18px; height: 4px; fill: currentColor; }
    .top.open .menu-btn { border-color: var(--chalk); }
    .top-actions {
      display: none; position: absolute; z-index: 30; right: 0; top: calc(100% + 6px); min-width: 190px;
      flex-direction: column; gap: 2px; padding: 6px;
      background: var(--board); border: 1px solid var(--line); border-radius: 10px; box-shadow: 0 14px 34px rgba(0, 0, 0, 0.55);
    }
    .top.open .top-actions { display: flex; }
    .top-actions .ghost { border: 0; border-radius: 6px; padding: 12px; text-align: left; font-size: 17px; }
    .top-actions .ghost:hover { background: var(--slate); }
    .top-actions .long, #showLog { display: block; }
    .top-actions .short { display: none; }

    /* The field, seen from above and attacking right: mown stripes, hash marks along the sidelines, chalk lines
       between the zones, and the Red Zone and end zone in their field cards' red and blue.
       Hold a zone to see its card. */
    .field { grid-area: field; }
    .zones {
      position: relative; height: 38px; gap: 6px; border-radius: 4px;
      background:
        repeating-linear-gradient(90deg, rgba(236, 243, 232, 0.38) 0 1px, transparent 1px 8px) top / 100% 4px no-repeat,
        repeating-linear-gradient(90deg, rgba(236, 243, 232, 0.38) 0 1px, transparent 1px 8px) bottom / 100% 4px no-repeat,
        repeating-linear-gradient(90deg, #154b31 0 12px, #103d29 12px 24px);
    }
    .zones::after { content: ''; position: absolute; inset: 0; border: 1.5px solid rgba(236, 243, 232, 0.6); border-radius: inherit; pointer-events: none; }
    .zone img { display: none; }
    .zone + .zone::before { content: ''; position: absolute; top: 0; bottom: 0; left: -4px; width: 2px; background: rgba(236, 243, 232, 0.6); }
    .zone:has(+ .ez) { background: rgba(214, 46, 42, 0.5); }
    .zone.ez { background: rgba(43, 95, 214, 0.45); }
    .zn {
      display: block; position: absolute; top: 7px; left: 0; right: 0; text-align: center; white-space: nowrap;
      font: 600 12px/1 var(--ui); font-size: min(12px, 100cqi / 4.9); letter-spacing: 0.05em; text-transform: uppercase; color: var(--chalk-dim);
    }
    .zone.here .zn { color: var(--chalk); font-weight: 700; }
    .who-ez { bottom: 5px; padding: 0; background: none; font-size: 10px; }
    .ball { top: 71%; width: 24px; height: 15px; }
    .trail { top: 71%; height: 4px; }
    .trail b { font-size: 11px; padding: 1px 4px; }

    /* The stage is drawn on the field card of the zone the ball is in (render sets --art), darker at the top and
       bottom where the words are. The cards take whatever height is left. */
    .stage {
      grid-area: stage; position: relative; isolation: isolate; overflow: hidden;
      grid-template-rows: minmax(0, 1fr) auto; gap: 6px; padding: 10px;
      background: var(--board);
    }
    .stage::before {
      content: ''; position: absolute; inset: 0; z-index: -1;
      background:
        linear-gradient(180deg, rgba(8, 21, 15, 0.8), rgba(8, 21, 15, 0.36) 28%, rgba(8, 21, 15, 0.3) 60%, rgba(8, 21, 15, 0.9)),
        var(--art, none) 50% 62% / 128% auto no-repeat;
    }
    .stage.new-art::before { animation: art-in 0.55s ease-out; }
    @keyframes art-in { from { opacity: 0.25; } }
    .table {
      container-type: size; align-content: center; gap: 0 10px;
      --cw: min((100cqw - 84px) / 2, (100cqh - 19px) / 1.635, 150px);
    }
    .slot-label { text-shadow: 0 1px 3px rgba(0, 0, 0, 0.85); }
    .slot-body { padding-top: calc(var(--cw) * 0.235); }
    .slot .card { width: var(--cw); }
    .card.empty .cv { box-sizing: border-box; background: rgba(8, 21, 15, 0.6); border-color: rgba(236, 243, 232, 0.45); color: var(--chalk); }
    .medal { width: 60px; height: 60px; margin-top: calc(19px + var(--cw) * 0.235); background: rgba(8, 21, 15, 0.8); }
    /* Once you've picked, the medal is a raised button with a ring that keeps calling for a tap. The result after
       the snap is flat, so the two never look alike. */
    .medal { position: relative; }
    .medal.go {
      --edge: color-mix(in srgb, var(--you) 55%, #000);
      background: var(--you); border-color: var(--chalk); color: var(--ink); font-size: 12.5px; text-wrap: balance; cursor: pointer;
      box-shadow: inset 0 2px 0 rgba(255, 255, 255, 0.4), 0 5px 0 var(--edge), 0 10px 18px rgba(0, 0, 0, 0.55);
      transition: translate 0.08s ease-out, box-shadow 0.08s ease-out;
    }
    .medal.go::after {
      content: ""; position: absolute; inset: -2px; border-radius: 50%; border: 3px solid var(--you); pointer-events: none;
      animation: ping 1.8s ease-out 0.5s infinite both;
    }
    @keyframes ping { from { scale: 1; opacity: 0.9; } 70%, to { scale: 1.5; opacity: 0; } }
    .medal.go:active { translate: 0 4px; box-shadow: inset 0 2px 0 rgba(255, 255, 255, 0.4), 0 1px 0 var(--edge), 0 3px 8px rgba(0, 0, 0, 0.5); }
    .medal.arm { animation: arm 0.3s cubic-bezier(0.2, 1.4, 0.4, 1) both; }
    @keyframes arm { from { transform: scale(0.6); } }
    @media (prefers-reduced-motion: reduce) { .medal.go::after { animation: none; opacity: 0; } }
    .table[data-solo] { grid-template-columns: auto auto; }
    .result { min-height: 58px; gap: 3px; text-shadow: 0 1px 4px rgba(0, 0, 0, 0.8); }
    .result .head { font-size: 22px; }
    .result .detail { font-size: 13.5px; line-height: 1.3; color: rgba(236, 243, 232, 0.88); }

    /* The line under the field sits at the top of the stage. While it can come and go it keeps its room there;
       otherwise (the CPU's kick after your first game) it shows on a dark band over the stage for a moment. */
    .status {
      grid-area: stage; align-self: start; z-index: 2; margin: 9px 14px 0; justify-items: center; text-align: center;
      gap: 1px; pointer-events: none; text-shadow: 0 1px 4px rgba(0, 0, 0, 0.85);
    }
    .status.room { min-height: 0; }
    .status strong { font-size: 15px; }
    .status span { font: 500 13px/1.25 var(--ui); font-size: 13.5px; color: rgba(236, 243, 232, 0.88); }
    .status:not(.room) { background: rgba(8, 21, 15, 0.92); border-radius: 8px; padding: 6px 10px; text-shadow: none; }
    .wrap:has(.status.room) .stage { padding-top: 48px; }

    /* Your hand: plays, then specials after a small gap, overlapping only as much as they must to fit.
       --n (set in render) is how many cards there are. The card you picked rises out of the hand. */
    .play {
      grid-area: play; container-type: inline-size;
      display: grid; grid-template-columns: auto auto; justify-content: center; align-items: end; column-gap: 12px; row-gap: 0;
      --w: min(23dvh * 0.7143, 128px, (100cqw - 12px) / 3);
      --m: min(6px, (100cqw - var(--w) - 12px) / (var(--n, 5) - 1) - var(--w));
    }
    .play > .section-label { grid-column: 1 / -1; padding: 0 2px; }
    .play > .section-label ~ .section-label { display: none; }
    .play > .section-label > span:first-child { font-size: 14px; color: var(--chalk-dim); }
    .play > .hand, .play > .specials { display: flex; align-items: flex-end; gap: 0; padding-top: 13px; }
    .hand { grid-column: 1; grid-row: 2; }
    .specials { grid-column: 2; grid-row: 2; }
    .play .card { flex: none; width: var(--w); margin-left: var(--m); }
    .hand > .card:first-child { margin-left: 0; }
    .specials .card.empty { display: none; }
    .play:not(:has(.specials > .card:not(.empty))) { column-gap: 0; }
    .play .cv { box-shadow: -3px 0 8px rgba(0, 0, 0, 0.35), 0 6px 14px rgba(0, 0, 0, 0.45); }
    .play .card.on .cv { transform: translateY(-9px); box-shadow: 0 0 0 3px var(--chalk), 0 12px 24px rgba(0, 0, 0, 0.5); }
    .play .card:disabled .cv { opacity: 1; filter: brightness(0.5) saturate(0.45); }
    /* Short phones (iPhone SE): a slightly smaller hand and field strip, so the cards on the stage stay the biggest. */
    @media (max-height: 620px) {
      .play { --w: min(20dvh * 0.7143, 128px, (100cqw - 12px) / 3); }
      .zones { height: 34px; }
      .zn { top: 5px; }
      .result { min-height: 54px; }
      .result .head { font-size: 20px; }
      .wrap:has(.status.room) .stage { padding-top: 44px; }
      .status { margin-top: 7px; }
    }
  }
</style>"""

PHONE_JS = """  // Phones in portrait get the one-screen layout (the last block of styles).
  const phoneB = matchMedia('(max-width: 899px) and (min-height: 460px)');
  let medalGo = false, stageArt = '';
  // When a special decided the snap, the medal says what it did instead of Stopped / Not stopped.
  function spSaid(L) {
    const c = [L.you, L.cpu].find((x) => x && x.status === 'worked');
    if (!c) return '';
    const k = c.card.key;
    if (k === 'flag') return 'Replay';
    if (k === 'sack' || k === 'tfl') return L.at === 0 ? 'No gain' : 'Back<br>1 zone';
    if (k === 'fumble') return 'Turn-<br>over';
    if ((k === 'juke' || k === 'grab') && L.head !== 'Touchdown!') return '+1 zone';
    return '+7';
  }
"""


def phone_b(p):
    """Layout B on phones: one screen per snap, the stage on the current field card, the medal as the Snap button."""
    p.rep("</style>", PHONE_CSS)
    # The field strip shows each zone's name; the field card images stay for wide screens and for holding a zone.
    p.s, n = re.subn(r'(<div class="zone[^"]*"[^>]*><img [^>]*alt="([^"]+)"[^>]*>)', r'\1<span class="zn">\2</span>', p.s)
    if n not in (4, 6):
        sys.exit(f"expected 4 or 6 zones, got {n}")
    # The ⋯ menu: How to play, New game and Play by play (wide screens keep the two buttons).
    p.rep('<div class="top-actions">', '<div class="top-actions" id="menu">')
    p.rep('<button class="ghost" id="newGame" type="button">New game</button>\n      </div>\n',
          '<button class="ghost" id="newGame" type="button">New game</button>\n'
          '        <button class="ghost" id="showLog" type="button">Play by play</button>\n      </div>\n'
          '      <button class="ghost menu-btn" id="menuBtn" type="button" aria-label="Menu" aria-expanded="false" aria-controls="menu">'
          '<svg viewBox="0 0 18 4" aria-hidden="true"><circle cx="2" cy="2" r="2"></circle><circle cx="9" cy="2" r="2"></circle><circle cx="16" cy="2" r="2"></circle></svg></button>\n')
    p.rep('<div class="medal" id="medal">vs</div>', '<button class="medal" id="medal" type="button" disabled>vs</button>')
    p.rep('    <dialog class="rules" id="rules"',
          '    <dialog class="rules log-sheet" id="logSheet" aria-labelledby="logHead">\n'
          '      <div class="head"><h2 id="logHead">Play by play</h2><button class="ghost" id="closeLog" type="button">Close</button></div>\n'
          '      <div class="body"><ol class="log" id="logAll"></ol></div>\n'
          '    </dialog>\n\n'
          '    <dialog class="rules" id="rules"')
    p.rep("  // ---------- Drawing ----------\n", "  // ---------- Drawing ----------\n" + PHONE_JS)
    p.rep("    $('#ball').style.left = zoneX(S.pos);\n",
          """    $('#ball').style.left = zoneX(S.pos);
    // Phones: the stage is drawn on the field card of the zone the ball is in, and fades in when the zone changes.
    const art = field.querySelector(`.zone[data-z="${S.pos}"] img`).src, stage = $('.stage');
    if (art !== stageArt) {
      if (stageArt) { stage.classList.remove('new-art'); void stage.offsetWidth; stage.classList.add('new-art'); }
      stageArt = art;
      stage.style.setProperty('--art', `url("${art}")`);
    }
""")
    p.rep("    setCards($('#specials'), sp.join(''));\n",
          "    setCards($('#specials'), sp.join(''));\n    $('.play').style.setProperty('--n', keys.length + S.hands.you.length);\n")
    p.rep("    // Play by play\n",
          """    // Phones: once you've picked, the medal between the two cards is the Snap button.
    const go = phoneB.matches && ready();
    medal.disabled = !go;
    if (go) {
      medal.className = 'medal go' + (medalGo ? '' : ' arm');
      medal.style.removeProperty('--tone');
      medal.textContent = $('#snap').textContent;
    }
    medalGo = go;

    // Play by play
""")
    p.rep("  $('#snap').addEventListener('click', snap);\n",
          """  $('#snap').addEventListener('click', snap);
  $('#medal').addEventListener('click', snap);
  phoneB.addEventListener('change', render);
  // Phones: How to play, New game and Play by play are in the ⋯ menu. Any tap outside it closes it.
  const topBar = $('.top');
  function openMenu(open) {
    topBar.classList.toggle('open', open);
    $('#menuBtn').setAttribute('aria-expanded', String(open));
  }
  $('#menuBtn').addEventListener('click', () => openMenu(!topBar.classList.contains('open')));
  $('#menu').addEventListener('click', (e) => { if (e.target.closest('button')) openMenu(false); });
  document.addEventListener('pointerdown', (e) => { if (!e.target.closest('.top')) openMenu(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') openMenu(false); });
  $('#showLog').addEventListener('click', () => { $('#logAll').innerHTML = $('#log').innerHTML; $('#logSheet').showModal(); });
  $('#closeLog').addEventListener('click', () => $('#logSheet').close());
""")
    # Cards in the phone hand overlap: a hold opens, and a tap picks, the card on top (the later one).
    p.rep("    // A tucked special sits behind its play card, so the play card wins where they overlap.\n"
          "    const el = hits.find((h) => !h.classList.contains('tuck')) || hits[0];",
          "    // A tucked special sits behind its play card, so the play card wins where they overlap. Where cards in the\n"
          "    // phone hand overlap, the one on top (later on the page) wins.\n"
          "    const el = hits.filter((h) => !h.classList.contains('tuck')).pop() || hits[0];")
    p.rep("  // ---------- Input ----------\n",
          """  // ---------- Input ----------
  // Phones: the hand's cards overlap, and a dimmed special lets taps through to the card under it,
  // so a tap only counts for the card on top where it landed.
  function onTop(b, e) {
    if (!phoneB.matches || !e.detail) return true;
    const inside = (x) => { const r = x.getBoundingClientRect(); return e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom; };
    return [...document.querySelectorAll('.hand .card, .specials .card:not(.empty)')].filter((c) => inside(c) || inside(c.firstElementChild)).pop() === b;
  }
""")
    for k in ("data-play", "data-sp"):
        p.rep(f"    const b = e.target.closest('[{k}]');\n    if (!b || S.phase !== 'pick') return;",
              f"    const b = e.target.closest('[{k}]');\n    if (!b || S.phase !== 'pick' || !onTop(b, e)) return;")


def phone_stage(p):
    """On the finished page: kicks shown alone, a special that decided the snap in front with a gold medal, the
    headline in offense/defense colors (every screen), and the stage art kept on the last play's zone (phones)."""
    # The zone each play happened in, so the stage keeps that zone's art until the next pick.
    p.rep("S.last = { you, cpu, ...out, n: S.snaps, off, guessed:", "S.last = { you, cpu, ...out, n: S.snaps, off, at: pos0, guessed:")
    p.rep("S.last = { fg: true, head: 'Field goal', detail, tone: who, n: S.snaps };",
          "S.last = { fg: true, head: 'Field goal', detail, tone: who, n: S.snaps, at: S.pos };")
    p.rep("    const art = field.querySelector(`.zone[data-z=\"${S.pos}\"] img`).src, stage = $('.stage');\n",
          "    // It stays on the zone where the last play happened until the next pick (or the CPU's kick).\n"
          "    const at = S.phase !== 'busy' && S.showLast && S.last && S.last.at != null ? S.last.at : S.pos;\n"
          "    const art = field.querySelector(`.zone[data-z=\"${at}\"] img`).src, stage = $('.stage');\n")
    # A special that decided the snap goes in front of its play card, and both play cards fade both lines.
    if "${miss === 'both'" not in p.s:
        p.rep("${miss ? `<span class=\"veil ${miss}\"></span>` : ''}",
              "${miss === 'both' ? '<span class=\"veil win\"></span><span class=\"veil lose\"></span>' : miss ? `<span class=\"veil ${miss}\"></span>` : ''}")
    p.s, n = re.subn(r"\n    const miss = (L \? .*;)\n",
                     r"\n    let miss = \1\n    if (L && spSaid(L)) miss = 'both';\n", p.s)
    if n != 1:
        sys.exit(f"miss line: {n}")
    p.rep("return `<div class=\"card ${PLAYS[key].side} ${owner}${flip ? ' flip' : ''}\">",
          "return `<div class=\"card ${PLAYS[key].side} ${owner}${flip ? ' flip' : ''}"
          "${c.status === 'worked' ? ' won' + (S.flip ? ' fresh' : '') : ''}\">")
    p.s, n = re.subn(r"(\n      medal\.innerHTML = .*;\n)(    \} else \{\n)",
                     r"\1      const said = spSaid(L);\n"
                     r"      if (said) { medal.className += ' gold'; medal.style.setProperty('--tone', 'var(--flag)'); medal.innerHTML = said; if (said === '+7') medal.classList.add('big'); }\n\2", p.s)
    if n != 1:
        sys.exit(f"medal line: {n}")
    p.rep("    res.style.setProperty('--tone', `var(--${R.tone})`);\n",
          "    res.style.setProperty('--tone', `var(--${R.tone})`);\n"
          "    // Blue when the offense won the snap (or kicked), red when the defense did, like the cards.\n"
          "    if (L) res.style.setProperty('--tone', L.fg || L.tone === L.off ? 'var(--offense)' : 'var(--defense)');\n")
    p.rep("medal.textContent = '+3'; }", "medal.textContent = '+3'; medal.classList.add('big'); }")
    p.rep("    S.flip = false;\n\n    // Result\n",
          "    // A kick has no matchup, so only the kicker's card shows.\n"
          "    const solo = kicker || (S.sel.play === 'fg' && !(S.showLast && L) ? 'you' : '');\n"
          "    if (solo) $('.table').dataset.solo = solo; else delete $('.table').dataset.solo;\n"
          "    S.flip = false;\n\n    // Result\n")


SPECIALS_P = "Only one special can work per snap, and a played special is used up either way.</p>"


def cards_words(p, home, twice=False):
    """How to play in the cards' own words: stopped / not stopped, not right / wrong guess.
    With two stops, the defense bonuses say they work on the first stop too."""
    first = ", even on their first try," if twice else ","
    p.rep(f"If you guess wrong, they gain nothing and go back 1 zone (never behind their own {home}). They keep the ball.",
          f"If you don’t stop the play, they go back 1 zone instead of gaining (never behind their own {home}).")
    # The one-special rule gets its own paragraph, with the Challenge Flag exception.
    p.rep(" Only one special can work per snap, and a played special is used up either way.</p>",
          "</p>\n        <p>Only one special can work per snap, and a played special is used up either way, except when "
          "a Challenge Flag cancels the snap: then the other side’s special goes back to its hand.</p>")
    p.rep("If you lose the snap, cancel it and both sides pick again. Any other special played on it goes back to its owner.",
          "If you lose the snap, cancel it and both sides pick again.")
    p.rep("If you run and they guess wrong, it goes all the way for a touchdown.",
          "If your Run isn’t stopped, it goes all the way for a touchdown.")
    p.rep("If you throw deep and they guess wrong, it goes all the way for a touchdown.",
          "If your Deep Pass isn’t stopped, it goes all the way for a touchdown.")
    p.rep("If you guess their pass right (Stop Short or Stop Deep), you score 7.",
          f"If you stop a pass (Stop Short or Stop Deep){first} you score 7.")
    p.rep("If you guess their run right, you recover the ball at midfield.",
          f"If you stop a Run{first} you get the ball at midfield.")
    p.rep("It remembers which plays you call and which ones you guess, and leans on your habits. Mix it up.",
          "It remembers which plays you call and which Stop cards you pick, and leans on your habits. Mix it up.")


def how_to_play(p, items):
    """The bullet list at the top of How to play."""
    i = p.s.index("        <ul>\n          <li>The field has ")
    j = p.s.index("        </ul>\n", i) + len("        </ul>\n")
    p.s = p.s[:i] + "        <ul>\n" + "".join(f"          <li>{x}</li>\n" for x in items) + "        </ul>\n" + p.s[j:]


def status_block(p, code):
    """Replace the code that fills the line under the field."""
    i = p.s.index("    // Status\n")
    j = p.s.index("\n\n    // Field", i)
    p.s = p.s[:i] + code + p.s[j:]


TIPS = {
    'off': 'Pick a play. The CPU will try to stop it.',
    'def': 'Pick the Stop card that matches their play.',
}


# ======================= look/: stopped once (from full-cards/) =======================
p = Page("full-cards/game.html")
common(p, "full-cards/", "ZONES.length - 1", "downs/")
p.rep('<span class="chip">Finished cards</span>', '')
p.rep("$('#snap').textContent = S.poss === 'you' ? 'Snap' : 'Snap · Defend';",
      "$('#snap').textContent = S.sel.play === 'fg' ? 'Kick for 3' : S.poss === 'you' ? 'Snap' : 'Defend';")
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
p.rep("    if (!ready()) return;\n    markTips();\n",
      "    if (!ready()) return;\n    markTips();\n    if (S.sel.play === 'fg') { kickFG('you'); render(); return; }\n")
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
how_to_play(p, [
    "The field has 3 zones: your own 25, midfield, the Red Zone. Get past the Red Zone for a touchdown, 7 points. "
    "In the Red Zone you can also kick a field goal instead of a play, for 3.",
    "Each snap, the offense secretly picks a play and the defense secretly picks a Stop card. Both flip at once.",
    "<strong>Not stopped</strong> (the Stop card doesn’t match the play): the ball moves. Run and Short Pass gain 1 zone, Deep Pass gains 2.",
    "<strong>Stopped</strong> (it matches): the defense gets the ball at its own 25. A stopped Deep Pass is intercepted, and they start at midfield.",
    "First to 21 wins, or pick 28 or 35 at New game.",
])
p.rep(SPECIALS_P, SPECIALS_P + """
        <p>You start with 2 specials. You draw one when you’re scored on, and you can hold 3. The marks under CPU show how many it holds, but not which ones.</p>""")
p.rep("If they guess your play, you still gain 1 zone. A guessed Deep Pass gains 1 instead of being intercepted.",
      "If your play is stopped, you still gain 1 zone. A stopped Deep Pass gains 1 instead of being intercepted.")
cards_words(p, "25")
# The line under the field: first-game tips and the CPU's field goal. The scoreboard and the ball on the field
# already show who has the ball and where. The kick line comes and goes with the Red Zone and the kick itself,
# so no room is kept for it after the first game.
status_block(p, f"""    // Status: first-game tips and the CPU's field goal; the scoreboard and the ball on the field show who has the ball and where.
    const kick = S.phase === 'busy';
    const tipLine = S.phase !== 'pick' ? ''
      : S.poss === 'cpu' ? (tip('def') ? '{TIPS['def']}' : '')
      : tip('off') ? '{TIPS['off']}' : '';
    showStatus(kick ? 'CPU lines up a field goal' : '', kick ? 'From the Red Zone, 3 points.' : tipLine, tips.on);""")
p.rep("    $('#handHint').textContent = S.poss === 'you' ? 'If the CPU guesses it, they get the ball' : 'Guess right to get the ball';\n", "")
p.rep("detail: 'You start at your own 25. Pick a play, then snap.'", "detail: tips.on ? 'You start at your own 25. Pick a play, then snap.' : ''")
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
phone_stage(p)
(ROOT / "look/game.html").write_text(p.s)

# ======================= look/downs/: stopped twice (from downs/) =======================
p = Page("downs/game.html")
common(p, "downs/", "RED", "../")
p.rep('<span class="chip">Downs test</span>', '')
p.rep("S.poss === 'you' ? 'Snap' : 'Snap · Defend';", "S.poss === 'you' ? 'Snap' : 'Defend';")
p.rep('        <div class="len" role="radiogroup"',
      rule_set("twice", "Being tested: a longer field, and one more try in each zone.")
      + '        <div class="len" role="radiogroup"')
p.rep("        <p>This page tests a longer field where you get two chances in each zone.</p>\n", "")
how_to_play(p, [
    "The field has 5 zones: your own 20, your own 35, midfield, their 35, the Red Zone. Get past the Red Zone for a "
    "touchdown, 7 points. In the Red Zone you can also kick a field goal instead of a play, for 3.",
    "Each snap, the offense secretly picks a play and the defense secretly picks a Stop card. Both flip at once.",
    "<strong>Not stopped</strong> (the Stop card doesn’t match the play): the ball moves. Run and Short Pass gain 1 zone, Deep Pass gains 2.",
    "<strong>Stopped once</strong> (it matches): the offense keeps the ball and tries again. Reaching a new zone starts the count over.",
    "<strong>Stopped twice</strong> in the same zone: the defense gets the ball at its own 20. If the second stop is on a Deep Pass, it’s intercepted, and they start at midfield.",
    "First to 21 wins, or pick 28 or 35 at New game.",
])
p.rep(SPECIALS_P, SPECIALS_P + """
        <p>You start with 2 specials, or 3 if you get the ball second. You draw one when you’re scored on and when you win the ball back with a stop, and you can hold 3. The marks under CPU show how many it holds, but not which ones.</p>""")
p.rep("If they guess your play, it doesn’t count as a stop: you still gain 1 zone.",
      "If your play is stopped, you still gain 1 zone. A stopped Deep Pass gains 1 instead of being intercepted.")
cards_words(p, "20", twice=True)
# The line under the field: "stopped once" while it's the last try in this zone, the CPU's kick, and first-game tips.
status_block(p, f"""    // Status: "stopped once" while it's the last try in this zone, the CPU's kick, and first-game tips.
    // The scoreboard and the ball on the field show who has the ball and where.
    const last = S.down === DOWNS;   // already stopped once in this zone
    let head = '', line = '';
    if (S.phase === 'busy') {{ head = 'CPU lines up a field goal'; line = 'From the Red Zone, 3 points.'; }}
    else if (S.phase === 'pick' && last) {{
      head = S.poss === 'you' ? 'Your ball: stopped once' : 'CPU ball: stopped once';
      line = S.poss === 'you' ? 'Stopped again here and the CPU gets the ball.' : 'Stop them again to get the ball.';
    }} else if (S.phase === 'pick') {{
      line = S.poss === 'cpu' ? (tip('def') ? '{TIPS['def']}' : '')
        : tip('off') ? '{TIPS['off']}' : '';
    }}
    showStatus(head, line, S.phase !== 'over');""")
p.rep("""    $('#handHint').textContent = S.poss === 'you'
      ? (last ? 'If the CPU guesses it, they get the ball' : 'If the CPU guesses it, you get one more try')
      : (last ? 'Guess right to get the ball' : 'Guess right twice to get the ball');
""", "")
p.rep("detail: 'You start at your own 20. Pick a play, then snap.'", "detail: tips.on ? 'You start at your own 20. Pick a play, then snap.' : ''")
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
phone_stage(p)
(ROOT / "look/downs/game.html").write_text(p.s)
print("built look/ and look/downs/")
