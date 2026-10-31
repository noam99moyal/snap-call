// Same game loop as cpu_sim.py, with the game's own Hard code choosing the CPU's calls and guesses.
const DECK = ['juke', 'grab', 'sack', 'tfl', 'flag', 'breakaway', 'hail', 'picksix', 'fumble'];
const rand = Math.random;
const choose = (d) => { let r = rand(); for (let i = 0; i < 2; i++) { r -= d[i]; if (r <= 0) return OFF[i]; } return OFF[2]; };
function offSp(hand, play, pos) {
  if (play === 'deep' && hand.includes('hail') && pos === 0 && rand() < 0.6) return 'hail';
  if (play === 'run' && hand.includes('breakaway') && rand() < 0.6) return 'breakaway';
  const jc = hand.includes('juke') ? 'juke' : hand.includes('grab') ? 'grab' : null;
  if (jc && rand() < (play === 'deep' ? 0.5 : 0.35)) return jc;
  if (hand.includes('flag') && rand() < 0.2) return 'flag';
  return null;
}
function defSp(hand, guess) {
  if (hand.includes('picksix') && guess !== 'run' && rand() < 0.5) return 'picksix';
  if (hand.includes('fumble') && guess === 'run' && rand() < 0.6) return 'fumble';
  const ts = hand.includes('tfl') ? 'tfl' : hand.includes('sack') ? 'sack' : null;
  if (ts && rand() < 0.4) return ts;
  if (hand.includes('flag') && rand() < 0.2) return 'flag';
  return null;
}
function resolve(o, osp, d, dsp) {
  if (d === o) {
    if (osp === 'flag') return ['replay', 0, 'off'];
    if (osp === 'juke' || osp === 'grab') return ['gain', 1, 'off'];
    if (o !== 'run' && dsp === 'picksix') return ['pick6', 0, 'def'];
    if (o === 'run' && dsp === 'fumble') return ['fumble', 0, 'def'];
    return [o === 'deep' ? 'int' : 'stop', 0, null];
  }
  if (dsp === 'flag') return ['replay', 0, 'def'];
  if (dsp === 'sack' || dsp === 'tfl') return ['sack', 0, 'def'];
  if (o === 'deep' && osp === 'hail') return ['td', 0, 'off'];
  if (o === 'run' && osp === 'breakaway') return ['td', 0, 'off'];
  return ['gain', PLAYS[o].gain, null];
}
const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
let memory = null;
function playGame(bot) {
  // newGame('hard'), as the game does it
  S = { pos: 0, hard: memory || { off: newTracker(), dfn: newTracker() } };
  foldGame(S.hard.off); foldGame(S.hard.dfn);
  const score = { you: 0, cpu: 0 };
  let deck = shuffle([...DECK, ...DECK]), discard = [];
  const hands = { you: [], cpu: [] };
  const draw = (w) => { if (hands[w].length >= 3) return; if (!deck.length) { deck = shuffle(discard); discard = []; } if (deck.length) hands[w].push(deck.pop()); };
  for (let i = 0; i < 2; i++) { draw('you'); draw('cpu'); }
  let poss = 'you';
  bot.newGame();
  const other = (w) => (w === 'you' ? 'cpu' : 'you');
  const scores = (w, pts) => { score[w] += pts; if (score[w] >= 21) return true; poss = other(w); S.pos = 0; draw(poss); return false; };
  for (let n = 0; n < 600; n++) {
    if (S.pos === 2 && (21 - score[poss] <= 3 || rand() < 0.45)) { if (scores(poss, 3)) break; continue; }
    const pos = S.pos, offw = poss, defw = other(poss);
    let o, osp, d, dsp, seen;
    if (poss === 'you') {
      o = bot.offense(pos); osp = offSp(hands.you, o, pos);
      const r = hardGuess(); d = r.play; seen = r.seen; dsp = defSp(hands.cpu, d);
    } else {
      const r = hardCall(); seen = r.seen;
      const h = hands.cpu.includes('hail');
      if (h && pos === 0 && score.you - score.cpu >= 7 && rand() < 0.5) { o = 'deep'; osp = 'hail'; }
      else { o = r.play; osp = offSp(hands.cpu, o, pos); }
      d = bot.defense(pos); dsp = defSp(hands.you, d);
    }
    for (const [w, c] of [[offw, osp], [defw, dsp]]) if (c) hands[w].splice(hands[w].indexOf(c), 1);
    const [kind, zones, fired] = resolve(o, osp, d, dsp);
    const firedw = fired === 'off' ? offw : fired === 'def' ? defw : null;
    for (const [w, c] of [[offw, osp], [defw, dsp]]) if (c) (kind === 'replay' && w !== firedw ? hands[w] : discard).push(c);
    if (poss === 'you') learn(S.hard.off, seen, o); else learn(S.hard.dfn, seen, d);
    bot.saw(poss, o, d);
    if (kind === 'gain') { S.pos += zones; if (S.pos >= 3 && scores(offw, 7)) break; }
    else if (kind === 'td') { if (scores(offw, 7)) break; }
    else if (kind === 'stop') { poss = defw; S.pos = 0; }
    else if (kind === 'int' || kind === 'fumble') { poss = defw; S.pos = 1; }
    else if (kind === 'sack') S.pos = Math.max(0, S.pos - 1);
    else if (kind === 'pick6') { if (scores(defw, 7)) break; }
  }
  memory = JSON.parse(JSON.stringify(S.hard));   // what saveHard() keeps between games
  return score.you > score.cpu;
}
const bots = {
  'Mixes at random': () => ({ newGame() {}, saw() {}, offense: () => choose(EVEN), defense: () => choose(EVEN) }),
  'Has a favorite play': () => ({ newGame() {}, saw() {}, offense: () => choose([0.55, 0.3, 0.15]), defense: () => choose([0.5, 0.3, 0.2]) }),
  'Goes in order': () => { let a = 0, b = 0; return { newGame() { a = b = 0; }, saw(p) { if (p === 'you') a++; else b++; }, offense: () => OFF[a % 3], defense: () => OFF[b % 3] }; },
  'Trickster: 3 Runs, then 2 passes': () => { const P = ['run', 'run', 'run', 'short', 'deep']; let a = 0, b = 0; return { newGame() { a = b = 0; }, saw(p) { if (p === 'you') a++; else b++; }, offense: () => P[a % 5], defense: () => P[b % 5] }; },
};
const out = [];
for (const [name, make] of Object.entries(bots)) {
  for (const remember of [false, true]) {
    let wins = 0, n = 0;
    for (let s = 0; s < 300; s++) {
      memory = null;
      const bot = make();
      for (let g = 0; g < 10; g++) {
        if (!remember) memory = null;
        const won = playGame(bot);
        if (g > 0) { wins += won; n++; }
      }
    }
    out.push(`${name.padEnd(36)} ${remember ? 'remembers' : 'fresh    '}  player wins ${(100 * wins / n).toFixed(1)}%`);
  }
}
out.join('\n');
