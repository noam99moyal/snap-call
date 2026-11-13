// Snap Call: play a friend online, on Cloudflare. Each room is its own Durable Object, so friends on different networks
// can play. (online/server.mjs is the first version for this Mac, without the pick clock and away status.)
//
//   cd online/worker && npx wrangler deploy          (npx wrangler dev --port 8797 runs it on this Mac)
//
// The Worker in front only makes room codes and sends each request to its room. A room keeps its game in its own
// storage, so it survives both phones going to sleep. It closes after 10 minutes with no card played.
//
// API (JSON over POST, updates over Server-Sent Events):
//   POST /api/rooms                 { set, target }          -> { code, seat, token }     make a room (seat a)
//   POST /api/rooms/CODE/join       { token? }               -> { code, seat, token }     join (seat b), or come back
//   GET  /api/rooms/CODE?token=…                              -> { status }   is my game still there?
//   GET  /api/rooms/CODE/events?token=…                       events: sync, start, picked, snap, over, rematch, left, meta
//   POST /api/rooms/CODE/pick       { token, play, special }  your secret pick (special: a card id or null)
//   POST /api/rooms/CODE/busy       { token, on }             a score card is up on your phone (your pick clock waits)
//   POST /api/rooms/CODE/away       { token }                 your phone went to the background (sent as a beacon)
//   POST /api/rooms/CODE/rematch    { token }
//   POST /api/rooms/CODE/leave      { token }
//   GET  /api/ping                                           -> { ok: true }
//
// The pick clock: once one player has picked, the other has 45 seconds, then a play is picked for them (no special).
// Running out twice in a row ends the game ('stopped', said as { who: 'you' } to the one who stopped).
// Their clock waits while their phone is away or showing a score card. Every event's view says whether your friend's
// phone is connected (present) and who is on the clock (clock: { you, left, running }); 'meta' events say only that.
import SnapRules from '../../look/rules.js';

const { OFF, DEF, fits, newDeal, create } = SnapRules;
const IDLE_MS = 10 * 60 * 1000;   // a room closes 10 minutes after the last card played (or it was made, or joined)
const LEFT_MS = 60 * 1000;        // after someone leaves, the room stays a minute so the other phone hears it
const PICK_MS = 45 * 1000;
const TARGETS = [21, 28, 35];
const KEEP_EVENTS = 60;           // a phone further behind than this gets a sync with the whole board instead
const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS' };
const json = (status, body) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', ...CORS } });
class Refused extends Error { constructor(status, msg) { super(msg); this.status = status; } }
async function readBody(req) {
  const s = await req.text();
  if (s.length > 10000) throw new Refused(413, 'Too big.');
  try { return s ? JSON.parse(s) : {}; } catch { throw new Refused(400, 'Bad JSON.'); }
}
// Four letters, no look-alikes (no I, L, O, 0, 1).
const LETTERS = 'ABCDEFGHJKMNPQRSTUVWXYZ';
const newCode = () => Array.from(crypto.getRandomValues(new Uint32Array(4)), (n) => LETTERS[n % LETTERS.length]).join('');
const newToken = () => Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => b.toString(16).padStart(2, '0')).join('');
const SIDE = { a: 'you', b: 'cpu' };
const otherSeat = (s) => (s === 'a' ? 'b' : 'a');

export default {
  async fetch(req, env) {
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
    const url = new URL(req.url);
    const parts = url.pathname.split('/').filter(Boolean);   // api, rooms, CODE, action
    if (parts[0] !== 'api') return json(404, { error: 'Not found.' });
    if (parts[1] === 'ping') return json(200, { ok: true });
    if (parts[1] !== 'rooms') return json(404, { error: 'Not found.' });
    const room = (code) => env.ROOMS.get(env.ROOMS.idFromName(code));
    if (parts.length === 2 && req.method === 'POST') {
      const body = await req.text();
      // A code that's already in use answers 409; try another.
      for (let i = 0; i < 8; i++) {
        const code = newCode();
        const res = await room(code).fetch(`https://room/${code}/create`, { method: 'POST', body });
        if (res.status !== 409) return res;
      }
      return json(503, { error: 'Couldn’t make a room. Try again.' });
    }
    const code = String(parts[2] || '').toUpperCase();
    if (!/^[A-Z]{4}$/.test(code)) return json(404, { error: 'No game with that code.' });
    return room(code).fetch(new Request(`https://room/${code}/${parts[3] || ''}${url.search}`, req));
  },
};

// ---------- One room ----------
// this.r is everything saved: code, set, target, uid, seats { a, b: { token, events, seq } }, S, picks, rematch,
// status (waiting -> playing -> over -> playing again on a rematch; left), lastPlay, closeAt (after a leave), and
// clock: { seat, left, since } (since: when it started running, or null while it waits). Open streams and which
// phones show a score card (busy) aren't saved.
export class Room {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.idleMs = +env.IDLE_MS || IDLE_MS;   // tests can set IDLE_MS (wrangler dev --var IDLE_MS:20000)
    this.streams = { a: new Set(), b: new Set() };
    this.busy = { a: false, b: false };
    ctx.blockConcurrencyWhile(async () => { this.r = (await ctx.storage.get('room')) || null; this.build(); });
  }
  build() {
    if (this.r) this.rules = create(this.r.set, { NAME: { you: 'A', cpu: 'B' }, verb: (w, b) => b, nextId: () => ++this.r.uid });
  }
  // Save, and set the alarm for whatever comes first: the room closing, or the pick clock running out.
  async persist() {
    const r = this.r;
    await this.ctx.storage.put('room', r);
    const at = [r.status === 'left' ? r.closeAt : r.lastPlay + this.idleMs];
    if (r.status !== 'left' && r.clock && r.clock.since) at.push(r.clock.since + r.clock.left);
    await this.ctx.storage.setAlarm(Math.min(...at));
  }

  async fetch(req) {
    const url = new URL(req.url);
    const [, code, action] = url.pathname.split('/');
    try {
      if (action === 'create') {
        if (this.r) throw new Refused(409, 'Code in use.');
        const { set, target } = await readBody(req);
        this.r = {
          code, set: set === 'twice' ? 'twice' : 'once', target: TARGETS.includes(+target) ? +target : 21, uid: 0,
          seats: { a: this.newSeat(), b: null }, S: null, picks: { a: null, b: null }, rematch: { a: false, b: false },
          status: 'waiting', lastPlay: Date.now(), closeAt: 0, clock: null,
        };
        this.build();
        await this.persist();
        return json(200, { code, seat: 'a', token: this.r.seats.a.token });
      }
      const r = this.r;
      if (!r) throw new Refused(404, 'No game with that code.');
      if (action === 'events' && req.method === 'GET') return this.stream(req, url);
      if (!action && req.method === 'GET') { this.seatOf(url.searchParams.get('token')); return json(200, { status: r.status }); }
      if (req.method !== 'POST') throw new Refused(405, 'Use POST.');
      const b = await readBody(req);
      if (action === 'join') {
        for (const s of ['a', 'b']) if (r.seats[s] && b.token && r.seats[s].token === b.token) return json(200, { code: r.code, seat: s, token: b.token });
        if (r.seats.b) throw new Refused(409, 'That game already has two players.');
        if (r.status !== 'waiting') throw new Refused(404, 'No game with that code.');
        r.seats.b = this.newSeat();
        this.deal();
        this.both('start');
        await this.persist();
        return json(200, { code: r.code, seat: 'b', token: r.seats.b.token });
      }
      const seat = this.seatOf(b.token);
      if (action === 'pick') {
        this.pick(seat, b.play, b.special == null ? null : +b.special);
        await this.persist();
        return json(200, { ok: true });
      }
      if (action === 'away') {
        for (const c of [...this.streams[seat]]) this.drop(seat, c);
        return json(200, { ok: true });
      }
      if (action === 'busy') {
        this.busy[seat] = !!b.on;
        if (this.runClock()) this.meta();
        await this.persist();
        return json(200, { ok: true });
      }
      if (action === 'rematch') {
        if (r.status !== 'over') throw new Refused(409, 'The game isn’t over.');
        r.rematch[seat] = true;
        if (r.rematch[otherSeat(seat)]) { this.deal(); this.both('start'); } else this.both('rematch');
        await this.persist();
        return json(200, { ok: true });
      }
      if (action === 'leave') {
        const was = r.status;
        r.status = 'left';
        r.clock = null;
        r.closeAt = Date.now() + LEFT_MS;
        this.send(otherSeat(seat), 'left', { before: was });
        await this.persist();
        return json(200, { ok: true });
      }
      throw new Refused(404, 'Not found.');
    } catch (e) {
      if (e instanceof Refused) return json(e.status, { error: e.message });
      console.error(e);
      return json(500, { error: 'Something went wrong.' });
    }
  }

  async alarm() {
    const r = this.r;
    if (!r) return;
    const now = Date.now();
    if (now >= (r.status === 'left' ? r.closeAt : r.lastPlay + this.idleMs) - 500) {
      // Closed: the streams end, and a phone that reconnects hears "No game with that code".
      for (const s of ['a', 'b']) for (const c of [...this.streams[s]]) this.drop(s, c, true);
      this.r = null;
      await this.ctx.storage.deleteAll();
      return;
    }
    if (r.clock && r.clock.since && now >= r.clock.since + r.clock.left - 300) {
      try { this.autoPick(r.clock.seat); } catch (e) { r.clock = null; }
    }
    await this.persist();
  }

  newSeat() { return { token: newToken(), events: [], seq: 0 }; }
  seatOf(token) {
    for (const s of ['a', 'b']) if (this.r.seats[s] && token && this.r.seats[s].token === token) return s;
    throw new Refused(403, 'Not in this game.');
  }
  deal() {
    const r = this.r;
    const S = { ...newDeal(), target: r.target, phase: 'pick', snaps: 0 };
    this.rules.dealHands(S);
    r.S = S; r.picks = { a: null, b: null }; r.rematch = { a: false, b: false };
    r.status = 'playing'; r.clock = null; r.lastPlay = Date.now(); r.misses = { a: 0, b: 0 }; r.stoppedBy = null;
    this.busy = { a: false, b: false };
  }

  // The pick clock runs while its player's phone is connected and not showing a score card. Says if that changed.
  runClock() {
    const c = this.r.clock;
    if (!c) return false;
    const run = this.streams[c.seat].size > 0 && !this.busy[c.seat];
    if (run && !c.since) { c.since = Date.now(); return true; }
    if (!run && c.since) { c.left = Math.max(0, c.left - (Date.now() - c.since)); c.since = null; return true; }
    return false;
  }
  autoPick(seat) {
    const r = this.r, S = r.S;
    r.misses = r.misses || { a: 0, b: 0 };
    if (++r.misses[seat] >= 2) {
      r.status = 'left'; r.stoppedBy = seat; r.clock = null; r.closeAt = Date.now() + LEFT_MS;
      this.both('stopped', (s) => ({ who: s === seat ? 'you' : 'cpu' }));
      return;
    }
    const plays = S.poss === SIDE[seat] ? OFF : DEF;
    this.pick(seat, plays[Math.floor(Math.random() * plays.length)], null, true);
  }

  // What one seat may see: its own hand, how many specials the other side holds, and the board, said from that seat.
  view(seat) {
    const r = this.r, S = r.S, me = SIDE[seat], them = SIDE[otherSeat(seat)];
    const base = { code: r.code, set: r.set, target: r.target, status: r.status, seat, stopped: r.stoppedBy ? (r.stoppedBy === seat ? 'you' : 'cpu') : null };
    if (!S) return base;
    const c = r.clock;
    return {
      ...base,
      score: { you: S.score[me], cpu: S.score[them] },
      poss: S.poss === me ? 'you' : 'cpu', pos: S.pos, down: S.down, phase: S.phase, snaps: S.snaps,
      hand: S.hands[me], theirCount: S.hands[them].length,
      picked: { you: !!r.picks[seat], cpu: !!r.picks[otherSeat(seat)] },
      rematch: { you: r.rematch[seat], cpu: r.rematch[otherSeat(seat)] },
      present: { cpu: this.streams[otherSeat(seat)].size > 0 },
      clock: c ? { you: c.seat === seat, left: Math.max(0, c.since ? c.left - (Date.now() - c.since) : c.left), running: !!c.since } : null,
    };
  }
  // Numbered events are kept, so a phone that reconnects gets the ones it missed. 'meta' (who's connected, the clock)
  // isn't kept: it's only ever the latest.
  send(seat, type, data = {}) {
    const st = this.r.seats[seat];
    if (!st) return;
    const ev = { id: ++st.seq, type, data: { ...data, view: this.view(seat) } };
    st.events.push(ev);
    if (st.events.length > KEEP_EVENTS) st.events.shift();
    for (const c of this.streams[seat]) c.event(ev);
  }
  both(type, dataFor) { for (const s of ['a', 'b']) this.send(s, type, dataFor ? dataFor(s) : {}); }
  meta(seats = ['a', 'b']) {
    for (const s of seats) if (this.r.seats[s] && this.r.S) for (const c of this.streams[s]) c.event({ type: 'meta', data: { view: this.view(s) } });
  }

  checkPick(seat, play, special) {
    const r = this.r, S = r.S, me = SIDE[seat];
    if (r.status !== 'playing' || S.phase !== 'pick') throw new Refused(409, 'Not picking right now.');
    if (r.picks[seat]) throw new Refused(409, 'Already picked.');
    const off = S.poss === me;
    const ok = off ? [...OFF, ...(S.pos === this.rules.RED ? ['fg'] : [])] : DEF;
    if (!ok.includes(play)) throw new Refused(400, 'That play isn’t in your hand.');
    let card = null;
    if (special != null) {
      card = S.hands[me].find((c) => c.id === special);
      if (!card) throw new Refused(400, 'That special isn’t in your hand.');
      if (!fits(card.key, play, off ? 'off' : 'def')) throw new Refused(400, 'That special can’t go with that play.');
    }
    return { play, card };
  }
  // A kick needs no defense pick: it goes as soon as the offense picks it. `auto`: the clock ran out and this play was
  // picked for that seat; the snap says so ({ auto: 'you' } to that seat).
  pick(seat, play, special, auto = false) {
    const p = this.checkPick(seat, play, special);
    const r = this.r, S = r.S, me = SIDE[seat];
    const said = (s) => (auto ? { auto: s === seat ? 'you' : 'cpu' } : {});
    if (!auto && r.misses) r.misses[seat] = 0;
    if (p.play === 'fg') {
      r.picks = { a: null, b: null };
      r.clock = null; r.lastPlay = Date.now();
      S.snaps++;
      this.rules.fieldGoal(S, me);
      this.both('snap', (s) => ({ fg: s === seat ? 'you' : 'cpu' }));
      if (S.phase === 'over') { r.status = 'over'; this.both('over'); }
      return;
    }
    r.picks[seat] = p;
    if (!r.picks[otherSeat(seat)]) {
      r.clock = { seat: otherSeat(seat), left: PICK_MS, since: null };
      this.runClock();
      this.send(otherSeat(seat), 'picked'); this.send(seat, 'picked');
      return;
    }
    const picks = { you: r.picks.a, cpu: r.picks.b };
    r.picks = { a: null, b: null };
    r.clock = null; r.lastPlay = Date.now();
    const shown = { you: { ...picks.you }, cpu: { ...picks.cpu } };
    S.snaps++;
    const { off, r: res } = this.rules.playSnap(S, picks);
    this.rules.apply(S, res, off);
    this.both('snap', (s) => ({ picks: { you: shown[SIDE[s]], cpu: shown[SIDE[otherSeat(s)]] }, ...said(s) }));
    if (S.phase === 'over') { r.status = 'over'; this.both('over'); }
  }

  // An event stream for one seat. A phone that reconnects sends the last event it saw and gets the ones it missed,
  // or a sync with the whole board if it's too far behind (or new). Then the latest meta.
  stream(req, url) {
    const seat = this.seatOf(url.searchParams.get('token'));
    const st = this.r.seats[seat];
    const { readable, writable } = new TransformStream();
    const w = writable.getWriter(), enc = new TextEncoder();
    const c = {
      w,
      raw: (s) => { w.write(enc.encode(s)).catch(() => this.drop(seat, c)); },
      event: (ev) => c.raw(`${ev.id ? `id: ${ev.id}\n` : ''}event: ${ev.type}\ndata: ${JSON.stringify(ev.data)}\n\n`),
    };
    c.raw('retry: 1500\n\n');
    const last = +(req.headers.get('last-event-id') || url.searchParams.get('last') || 0);
    const missed = st.events.filter((e) => e.id > last);
    if (!last || (missed.length && missed[0].id !== last + 1)) c.event({ id: st.seq, type: 'sync', data: { view: this.view(seat) } });
    else for (const e of missed) c.event(e);
    const first = this.streams[seat].size === 0;
    this.streams[seat].add(c);
    if (first) { this.runClock(); this.meta(); this.persist(); } else this.meta([seat]);
    c.beat = setInterval(() => c.raw(': beat\n\n'), 5000);
    req.signal?.addEventListener?.('abort', () => this.drop(seat, c));
    return new Response(readable, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no', ...CORS } });
  }
  // A phone's stream ended. If it was that seat's last one, its friend hears it's away and its clock waits.
  drop(seat, c, closing = false) {
    if (!this.streams[seat].delete(c)) return;
    clearInterval(c.beat);
    c.w.close().catch(() => {});
    if (closing || !this.r || this.streams[seat].size) return;
    this.busy[seat] = false;
    this.runClock();
    this.meta([otherSeat(seat)]);
    this.persist();
  }
}
