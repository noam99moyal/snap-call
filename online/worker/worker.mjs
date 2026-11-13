// Snap Call: play a friend online, on Cloudflare. The same rooms and messages as online/server.mjs (which stays for
// testing on this Mac), but each room is its own Durable Object, so friends on different networks can play.
//
//   cd online/worker && npx wrangler deploy
//
// The Worker in front only makes room codes and sends each request to its room. A room keeps its game in its own
// storage, so it survives both phones going to sleep; it closes after 30 minutes with nobody connected.
// API: the same as online/server.mjs (POST /api/rooms, /join, /pick, /rematch, /leave; GET /events, status, /api/ping).
import SnapRules from '../../look/rules.js';

const { OFF, DEF, fits, newDeal, create } = SnapRules;
const IDLE_MS = 30 * 60 * 1000;
const LEFT_MS = 60 * 1000;   // after someone leaves, the room stays a minute so the other phone hears it
const TARGETS = [21, 28, 35];
const KEEP_EVENTS = 60;      // a phone further behind than this gets a sync with the whole board instead
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
// status (waiting -> playing -> over -> playing again on a rematch; left), idleSince. Open event streams aren't saved.
export class Room {
  constructor(ctx) {
    this.ctx = ctx;
    this.streams = { a: new Set(), b: new Set() };
    ctx.blockConcurrencyWhile(async () => { this.r = (await ctx.storage.get('room')) || null; this.build(); });
  }
  build() {
    if (this.r) this.rules = create(this.r.set, { NAME: { you: 'A', cpu: 'B' }, verb: (w, b) => b, nextId: () => ++this.r.uid });
  }
  save() { return this.ctx.storage.put('room', this.r); }

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
          status: 'waiting', idleSince: Date.now(),
        };
        this.build();
        await this.idle();
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
        await this.idle();
        return json(200, { code: r.code, seat: 'b', token: r.seats.b.token });
      }
      const seat = this.seatOf(b.token);
      if (action === 'pick') {
        this.pick(seat, b.play, b.special == null ? null : +b.special);
        await this.idle();
        return json(200, { ok: true });
      }
      if (action === 'rematch') {
        if (r.status !== 'over') throw new Refused(409, 'The game isn’t over.');
        r.rematch[seat] = true;
        if (r.rematch[otherSeat(seat)]) { this.deal(); this.both('start'); } else this.both('rematch');
        await this.idle();
        return json(200, { ok: true });
      }
      if (action === 'leave') {
        const was = r.status;
        r.status = 'left';
        this.send(otherSeat(seat), 'left', { before: was });
        await this.save();
        await this.ctx.storage.setAlarm(Date.now() + LEFT_MS);
        return json(200, { ok: true });
      }
      throw new Refused(404, 'Not found.');
    } catch (e) {
      if (e instanceof Refused) return json(e.status, { error: e.message });
      console.error(e);
      return json(500, { error: 'Something went wrong.' });
    }
  }

  newSeat() { return { token: newToken(), events: [], seq: 0 }; }
  seatOf(token) {
    for (const s of ['a', 'b']) if (this.r.seats[s] && token && this.r.seats[s].token === token) return s;
    throw new Refused(403, 'Not in this game.');
  }
  // Something happened: save, and the room closes 30 minutes from now unless someone is still connected then.
  async idle() {
    this.r.idleSince = Date.now();
    await this.save();
    if (this.r.status !== 'left') await this.ctx.storage.setAlarm(Date.now() + IDLE_MS);
  }
  async alarm() {
    if (!this.r) return;
    const live = this.streams.a.size + this.streams.b.size > 0;
    if (this.r.status !== 'left' && (live || Date.now() - this.r.idleSince < IDLE_MS - 1000)) {
      await this.ctx.storage.setAlarm(Date.now() + (live ? IDLE_MS : IDLE_MS - (Date.now() - this.r.idleSince)));
      return;
    }
    for (const s of ['a', 'b']) for (const c of [...this.streams[s]]) this.drop(s, c);
    this.r = null;
    await this.ctx.storage.deleteAll();
  }

  deal() {
    const r = this.r;
    const S = { ...newDeal(), target: r.target, phase: 'pick', snaps: 0 };
    this.rules.dealHands(S);
    r.S = S; r.picks = { a: null, b: null }; r.rematch = { a: false, b: false };
    r.status = 'playing';
  }
  // What one seat may see: its own hand, how many specials the other side holds, and the board, said from that seat.
  view(seat) {
    const r = this.r, S = r.S, me = SIDE[seat], them = SIDE[otherSeat(seat)];
    const base = { code: r.code, set: r.set, target: r.target, status: r.status, seat };
    if (!S) return base;
    return {
      ...base,
      score: { you: S.score[me], cpu: S.score[them] },
      poss: S.poss === me ? 'you' : 'cpu', pos: S.pos, down: S.down, phase: S.phase, snaps: S.snaps,
      hand: S.hands[me], theirCount: S.hands[them].length,
      picked: { you: !!r.picks[seat], cpu: !!r.picks[otherSeat(seat)] },
      rematch: { you: r.rematch[seat], cpu: r.rematch[otherSeat(seat)] },
    };
  }
  send(seat, type, data = {}) {
    const st = this.r.seats[seat];
    if (!st) return;
    const ev = { id: ++st.seq, type, data: { ...data, view: this.view(seat) } };
    st.events.push(ev);
    if (st.events.length > KEEP_EVENTS) st.events.shift();
    for (const c of this.streams[seat]) c.event(ev);
  }
  both(type, dataFor) { for (const s of ['a', 'b']) this.send(s, type, dataFor ? dataFor(s) : {}); }

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
  // A kick needs no defense pick: it goes as soon as the offense picks it.
  pick(seat, play, special) {
    const p = this.checkPick(seat, play, special);
    const r = this.r, S = r.S, me = SIDE[seat];
    if (p.play === 'fg') {
      r.picks = { a: null, b: null };
      S.snaps++;
      this.rules.fieldGoal(S, me);
      this.both('snap', (s) => ({ fg: s === seat ? 'you' : 'cpu' }));
      if (S.phase === 'over') { r.status = 'over'; this.both('over'); }
      return;
    }
    r.picks[seat] = p;
    if (!r.picks[otherSeat(seat)]) { this.send(otherSeat(seat), 'picked'); this.send(seat, 'picked'); return; }
    const picks = { you: r.picks.a, cpu: r.picks.b };
    r.picks = { a: null, b: null };
    const shown = { you: { ...picks.you }, cpu: { ...picks.cpu } };
    S.snaps++;
    const { off, r: res } = this.rules.playSnap(S, picks);
    this.rules.apply(S, res, off);
    this.both('snap', (s) => ({ picks: { you: shown[SIDE[s]], cpu: shown[SIDE[otherSeat(s)]] } }));
    if (S.phase === 'over') { r.status = 'over'; this.both('over'); }
  }

  // An event stream for one seat. A phone that reconnects sends the last event it saw and gets the ones it missed,
  // or a sync with the whole board if it's too far behind (or new).
  stream(req, url) {
    const seat = this.seatOf(url.searchParams.get('token'));
    const st = this.r.seats[seat];
    const { readable, writable } = new TransformStream();
    const w = writable.getWriter(), enc = new TextEncoder();
    const c = {
      w,
      raw: (s) => { w.write(enc.encode(s)).catch(() => this.drop(seat, c)); },
      event: (ev) => c.raw(`id: ${ev.id}\nevent: ${ev.type}\ndata: ${JSON.stringify(ev.data)}\n\n`),
    };
    c.raw('retry: 1500\n\n');
    const last = +(req.headers.get('last-event-id') || url.searchParams.get('last') || 0);
    const missed = st.events.filter((e) => e.id > last);
    if (!last || (missed.length && missed[0].id !== last + 1)) c.event({ id: st.seq, type: 'sync', data: { view: this.view(seat) } });
    else for (const e of missed) c.event(e);
    this.streams[seat].add(c);
    c.beat = setInterval(() => c.raw(': beat\n\n'), 20000);
    req.signal?.addEventListener?.('abort', () => this.drop(seat, c));
    return new Response(readable, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no', ...CORS } });
  }
  drop(seat, c) {
    if (!this.streams[seat].delete(c)) return;
    clearInterval(c.beat);
    c.w.close().catch(() => {});
    if (this.r) { this.r.idleSince = Date.now(); this.save(); }
  }
}
