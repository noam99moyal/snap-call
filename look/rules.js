// Snap Call rules: what a snap does, on both rule sets, with no screen code, so a server can run the very same rules
// for online play. look/game.html keeps everything you see, the computer player, and the game state S, which every
// rule here takes as its first argument. The two sides are 'you' and 'cpu' (online: the two players).
// Random choices (who gets the ball first, shuffles, announcer lines) use Math.random.
(function (root) {
  'use strict';
  const other = (w) => (w === 'you' ? 'cpu' : 'you');
  // Each result has a few announcer lines, picked at random, so the play-by-play doesn't repeat itself.
  const say = (lines) => lines[Math.floor(Math.random() * lines.length)];
  const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

  // The two rule sets. ZONES: zones from your own end to the end zone. DOWNS: tries in a zone before a stop costs the ball.
  const RULESETS = {
    once: { name: 'Stopped once', ZONES: 3, RED: 2, MID: 1, DOWNS: 1 },
    twice: { name: 'Stopped twice', ZONES: 5, RED: 4, MID: 2, DOWNS: 2 },
  };

  // win: what happens when the play beats the guess (offense) or the guess is right (defense). lose: the other way.
  const BASE_PLAYS = {
    run:    { side: 'off', name: 'Run', gain: 1, win: 'Not stopped: +1 zone', lose: 'Stopped: their ball' },
    short:  { side: 'off', name: 'Short Pass', gain: 1, win: 'Not stopped: +1 zone', lose: 'Stopped: their ball' },
    deep:   { side: 'off', name: 'Deep Pass', gain: 2, win: 'Not stopped: +2 zones', lose: 'Stopped: intercepted' },
    runD:   { side: 'def', name: 'Stop Run', stops: 'run', win: 'Stopped: your ball', lose: 'Not stopped: they gain' },
    shortD: { side: 'def', name: 'Stop Short', stops: 'short', win: 'Stopped: your ball', lose: 'Not stopped: they gain' },
    deepD:  { side: 'def', name: 'Stop Deep', stops: 'deep', win: 'Stopped: interception', lose: 'Not stopped: they gain' },
  };
  const OFF = ['run', 'short', 'deep'];
  const DEF = ['runD', 'shortD', 'deepD'];

  // A Save only works if you lose the snap; a Bonus only works if you win it.
  // Saves work with any play, so they never decide what you pick. Same-effect pairs keep two names for variety.
  const SPECIALS = {
    juke:      { name: 'Juke', side: 'off', kind: 'save', count: 2, when: 'If your play is stopped', then: 'Still gain 1 zone' },
    grab:      { name: 'Spectacular Catch', side: 'off', kind: 'save', count: 2, when: 'If your play is stopped', then: 'Still gain 1 zone' },
    sack:      { name: 'Sack', side: 'def', kind: 'save', count: 2, when: "If you don’t stop the play", then: 'They go back 1 zone' },
    tfl:       { name: 'Tackle for Loss', side: 'def', kind: 'save', count: 2, when: "If you don’t stop the play", then: 'They go back 1 zone' },
    flag:      { name: 'Challenge Flag', side: 'any', kind: 'save', count: 2, when: 'If you lose the snap', then: 'Replay it' },
    breakaway: { name: 'Breakaway', side: 'off', kind: 'bonus', count: 2, needs: ['run'], when: "If your Run isn’t stopped", then: 'Touchdown' },
    hail:      { name: 'Hail Mary', side: 'off', kind: 'bonus', count: 2, needs: ['deep'], when: "If your Deep Pass isn’t stopped", then: 'Touchdown' },
    picksix:   { name: 'Pick Six', side: 'def', kind: 'bonus', count: 2, needs: ['shortD', 'deepD'], when: 'If you stop a pass', then: 'You score 7' },
    fumble:    { name: 'Forced Fumble', side: 'def', kind: 'bonus', count: 2, needs: ['runD'], when: 'If you stop a Run', then: 'Your ball at midfield' },
  };
  // Whether a special can go with this play on this side right now. The card face already says which side and play it needs.
  function fits(key, play, sd) {
    if (play === 'fg') return false;   // a kick isn't a snap, so no special goes with it
    const s = SPECIALS[key];
    if (s.side !== 'any' && s.side !== sd) return false;
    return !(s.needs && play && !s.needs.includes(play));
  }

  // A fresh deal: who gets the ball first, and the specials shuffled.
  function newDeal() {
    const deck = [];
    for (const [k, sp] of Object.entries(SPECIALS)) for (let i = 0; i < sp.count; i++) deck.push(k);
    return { score: { you: 0, cpu: 0 }, poss: Math.random() < 0.5 ? 'you' : 'cpu', pos: 0, down: 1, hands: { you: [], cpu: [] }, deck: shuffle(deck), discard: [] };
  }

  // The rules for one rule set. names: { NAME, verb } for the announcer lines ("You score 7", "CPU scores 7"; NAME.theirs
  // is "the CPU’s" or, online, "your friend’s". NAME is read each time, so the page can change it for online play);
  // nextId: numbers the special cards dealt.
  function create(set, { NAME, verb, nextId }) {
    const { name, ZONES, RED, MID, DOWNS } = RULESETS[set];
    const TWICE = set === 'twice';
    // The play cards' printed results: Stopped twice cards say "Stopped twice".
    const PLAYS = JSON.parse(JSON.stringify(BASE_PLAYS));
    const stop = TWICE ? 'Stopped twice' : 'Stopped';
    for (const k of OFF) PLAYS[k].lose = `${stop}: ${k === 'deep' ? 'intercepted' : 'their ball'}`;
    for (const k of DEF) PLAYS[k].win = `${stop}: ${k === 'deepD' ? 'interception' : 'your ball'}`;

    function draw(S, w) {
      if (S.hands[w].length >= 3) return;
      if (!S.deck.length) { S.deck = shuffle(S.discard); S.discard = []; }
      if (S.deck.length) S.hands[w].push({ id: nextId(), key: S.deck.pop() });
    }

    // Both start with 2 specials; the side that gets the ball second starts with one more.
    function dealHands(S) {
      for (let i = 0; i < 2; i++) { draw(S, 'you'); draw(S, 'cpu'); }
      draw(S, S.poss === 'you' ? 'cpu' : 'you');
    }

    // ---------- Rules ----------
    // Losers save, winners score: the plain result first, then the loser's Save, then the winner's Bonus.
    // `sp` names the side whose special worked; at most one does.
    function resolve(o, d) {
      const pass = o.play !== 'run';
      if (PLAYS[d.play].stops === o.play) {
        // The offense lost the snap.
        if (o.sp === 'flag') return { kind: 'replay', sp: 'off' };
        if (o.sp === 'juke' || o.sp === 'grab') return { kind: 'gain', zones: 1, how: o.sp, sp: 'off' };
        if (pass && d.sp === 'picksix') return { kind: 'pick6', sp: 'def' };
        if (!pass && d.sp === 'fumble') return { kind: 'fumble', sp: 'def' };
        return { kind: o.play === 'deep' ? 'int' : 'stop' };
      }
      // The defense lost the snap.
      if (d.sp === 'flag') return { kind: 'replay', sp: 'def' };
      if (d.sp === 'sack' || d.sp === 'tfl') return { kind: 'sack', how: d.sp, sp: 'def' };
      if (o.play === 'deep' && o.sp === 'hail') return { kind: 'td', how: 'hail', sp: 'off' };
      if (o.play === 'run' && o.sp === 'breakaway') return { kind: 'td', how: 'breakaway', sp: 'off' };
      return { kind: 'gain', zones: PLAYS[o.play].gain, play: o.play };
    }

    function callText(offWho, o, d) {
      const oc = o.sp === 'hail' ? 'threw a Hail Mary' : 'called ' + PLAYS[o.play].name;
      const dc = 'called ' + PLAYS[d.play].name;
      return `${NAME[offWho]} ${oc}. ${NAME[other(offWho)]} ${dc}.`;
    }

    // Where the ball is, said from the side of `who`, the team with the ball.
    const zoneName = (pos, who) => (TWICE ? [
      who === 'you' ? 'your own 20' : 'their own 20',
      who === 'you' ? 'your own 35' : 'their own 35',
      'midfield',
      who === 'you' ? `${NAME.theirs || 'the CPU’s'} 35` : 'your 35',
      'the Red Zone',
    ] : [who === 'you' ? 'your own 25' : 'their own 25', 'midfield', 'the Red Zone'])[pos];
    const cap = (s) => s[0].toUpperCase() + s.slice(1);
    // Every announcer line stays short enough for two lines on phones.
    const ballAt = (pos, who) => (pos === RED ? 'Ball in the Red Zone.' : `Ball at ${zoneName(pos, who)}.`);
    const GAIN_SAYS = {
      run: ['Good gain. ', 'Found a gap. ', 'Room to run. '],
      short: ['Good gain. ', 'Easy catch. ', 'Moving the chains. '],
      deep: ['Over the top! ', 'Wide open! ', 'Deep ball, caught! '],
    };

    // Winning the ball back with a stop draws nothing: only being scored on draws a special.
    function wonBack(who, text) { return { detail: text, log: text }; }
    function kickoff(S, receiver) { S.poss = receiver; S.pos = 0; S.down = 1; draw(S, receiver); }
    function won(S, who) { if (S.score[who] >= S.target) { S.phase = 'over'; return true; } return false; }
    function score(S, who, pts) { S.score[who] += pts; if (!won(S, who)) kickoff(S, other(who)); }

    function apply(S, r, off) {
      const def = other(off);
      switch (r.kind) {
        case 'replay':
          return { head: 'Flag! Replay', detail: say([`${NAME[r.by]} threw the flag. Snap again.`, 'Flag on the play. Snap again.']), tone: r.by };
        case 'gain': {
          // Every new zone starts the count of tries over.
          S.pos += r.zones; S.down = 1;
          const td = S.pos >= ZONES;
          if (td) score(S, off, 7);
          const rest = td ? `${say(['Into the end zone! ', 'All the way! ', 'Nobody touches it! '])}${NAME[off]} ${verb(off, 'score')} 7.`
            : r.how ? '+1 zone.' : `${say(GAIN_SAYS[r.play])}${ballAt(S.pos, off)}`;
          const head = td ? 'Touchdown!' : r.how === 'juke' ? 'Juke!' : r.how === 'grab' ? 'What a catch!' : `+${r.zones} zone${r.zones > 1 ? 's' : ''}`;
          if (!r.how) return { head, detail: rest, tone: off };
          // A Save turns a stop into a gain, so the log joins it to the picks with "but".
          const save = r.how === 'juke' ? say(['the juke breaks free.', 'one cut and through.', 'a quick juke and gone.'])
            : say(['what a catch!', 'a one-handed grab!', 'hauled in anyway!']);
          return { head, detail: `${cap(save)} ${rest}`, but: `${save} ${rest}`, tone: off };
        }
        case 'td': {
          const lead = r.how === 'hail' ? say(['Caught! ', 'Up for grabs, and caught! ', 'Hail Mary, caught! '])
            : r.how === 'breakaway' ? say(['Breakaway! ', 'Gone! ', 'Untouched! ']) : '';
          score(S, off, 7);
          return { head: 'Touchdown!', detail: `${lead}${NAME[off]} ${verb(off, 'score')} 7.`, tone: off };
        }
        // Stopped once: the defense gets the ball at its own 25, or at midfield when it's a Deep Pass (intercepted).
        // Stopped twice: a first stop costs a try; a second in the same zone gives the ball at its own 20, or midfield.
        case 'stop':
        case 'int':
          if (TWICE) {
            if (S.down < DOWNS) {
              S.down++;
              return { head: 'Stopped once', detail: say(['One more try.', 'Stuffed. One more try.', 'Read it. One more try.', 'No room. One more try.']), tone: def, once: true };
            }
            S.poss = def; S.down = 1;
            if (r.kind === 'int') {
              S.pos = MID;
              return { ...wonBack(def, say([`${NAME[def]} ${verb(def, 'start')} at midfield.`, 'Jumped the route. Ball at midfield.', 'Read it all the way. Ball at midfield.'])), head: 'Intercepted!', tone: def, twice: true };
            }
            S.pos = 0;
            return { ...wonBack(def, say([`${NAME[def]} ${verb(def, 'take')} over at ${def === 'you' ? 'your' : 'their'} own 20.`, `Held again. ${NAME[def]} ${verb(def, 'take')} over.`, `Two stops. ${NAME[def]} ${verb(def, 'take')} over.`])), head: 'Stopped twice', tone: def, twice: true };
          }
          S.poss = def;
          if (r.kind === 'int') {
            S.pos = MID;
            return { head: 'Intercepted!', detail: say([`${NAME[def]} ${verb(def, 'start')} at midfield.`, 'Jumped the route. Ball at midfield.', 'Read it all the way. Ball at midfield.']), tone: def };
          }
          S.pos = 0;
          {
            const at = `${NAME[def]} ${verb(def, 'take')} over at ${def === 'you' ? 'your' : 'their'} 25.`;
            return { head: 'Stopped', detail: say([at, `Stuffed. ${at}`, `Read it. ${at}`]), tone: def };
          }
        case 'sack': {
          const was = S.pos;
          S.pos = Math.max(0, S.pos - 1);
          if (S.pos !== was) S.down = 1;
          const rest = was === 0 ? 'No gain.' : 'Back 1 zone.';
          const how = say(['the defense got through.', 'brought down behind the line.', 'swarmed in the backfield.']);
          return { head: r.how === 'tfl' ? 'Tackle for loss!' : 'Sacked!', detail: `${cap(how)} ${rest}`, but: `${how} ${rest}`, tone: def };
        }
        case 'fumble':
          S.poss = def; S.pos = MID; S.down = 1;
          return { ...wonBack(def, say([`${NAME[def]} ${verb(def, 'recover')} at midfield.`, `Loose ball! ${NAME[def]} ${verb(def, 'fall')} on it.`])), head: 'Fumble!', tone: def };
        case 'pick6':
          score(S, def, 7);
          return { head: 'Pick Six!', detail: `${say(['Picked off!', 'Pick and gone!', 'All the way back!'])} ${NAME[def]} ${verb(def, 'score')} 7.`, tone: def };
      }
    }

    // One snap. picks: { you: { play, card }, cpu: { play, card } }, where card is the special from that hand (or null).
    // Played specials leave the hands and are used up, except that a replayed snap hands the other side's special back;
    // each pick gets a status (worked, wasted, back). Returns the plays as called, the result and its announcer lines.
    function playSnap(S, picks) {
      for (const w of ['you', 'cpu']) {
        const c = picks[w];
        if (c.card) S.hands[w] = S.hands[w].filter((x) => x.id !== c.card.id);
      }
      const off = S.poss, def = other(off);
      const O = picks[off], D = picks[def];
      const o = { play: O.play, sp: O.card ? O.card.key : null };
      const d = { play: D.play, sp: D.card ? D.card.key : null };
      const r = resolve(o, d);
      const firedBy = r.sp ? (r.sp === 'off' ? off : def) : null;
      if (r.kind === 'replay') r.by = firedBy;
      for (const w of ['you', 'cpu']) {
        const c = picks[w];
        if (!c.card) continue;
        if (r.kind === 'replay' && w !== firedBy) { S.hands[w].push(c.card); c.status = 'back'; }
        else { S.discard.push(c.card.key); c.status = w === firedBy ? 'worked' : 'wasted'; }
      }
      return { off, def, o, d, r, firedBy };
    }

    // A field goal from the Red Zone: 3 points.
    function fieldGoal(S, who) { score(S, who, 3); }

    return { set, name, TWICE, ZONES, RED, MID, DOWNS, PLAYS, draw, dealHands, resolve, callText, zoneName, ballAt, kickoff, won, score, apply, playSnap, fieldGoal };
  }

  const SnapRules = { RULESETS, OFF, DEF, SPECIALS, other, say, shuffle, fits, newDeal, create };
  if (typeof module === 'object' && module.exports) module.exports = SnapRules;
  else root.SnapRules = SnapRules;
})(typeof globalThis !== 'undefined' ? globalThis : this);
