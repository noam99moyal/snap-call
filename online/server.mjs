// Snap Call: play a friend online. A small room server for testing on this Mac (no installs: plain Node 18+).
//
//   node online/server.mjs            then open http://localhost:8796/look/ (or the Wi-Fi address it prints)
//
// It serves the website too, so a phone on the same Wi-Fi can open the printed address and play a browser on the Mac.
// The server keeps each pick secret until both are in, deals the specials, and runs the same look/rules.js as the page.
// Later this moves to a Cloudflare Worker with one Durable Object per room; the messages stay the same.
//
// API (JSON over POST, updates over Server-Sent Events):
//   POST /api/rooms                 { set, target }          -> { code, seat, token }     make a room (seat a)
//   POST /api/rooms/CODE/join       { token? }               -> { code, seat, token }     join (seat b), or come back
//   GET  /api/rooms/CODE?token=…                              -> { status }   is my game still there?
//   GET  /api/rooms/CODE/events?token=…                       an event stream: sync, start, picked, snap, over, rematch, left
//   POST /api/rooms/CODE/pick       { token, play, special }  your secret pick (special: a card id or null)
//   POST /api/rooms/CODE/rematch    { token }
//   POST /api/rooms/CODE/leave      { token }
//   GET  /api/ping                                           -> { ok: true }   the page shows "Play a friend" only if this answers
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { readFile, stat } from 'node:fs/promises';
import { randomBytes, randomInt } from 'node:crypto';
import { networkInterfaces } from 'node:os';
import { join, normalize, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SnapRules = createRequire(import.meta.url)(join(ROOT, 'look/rules.js'));
const { OFF, DEF, SPECIALS, fits, newDeal, create } = SnapRules;
const PORT = +process.env.PORT || 8796;
const IDLE_MS = 30 * 60 * 1000;   // a room nobody is connected to for 30 minutes is closed
const TARGETS = [21, 28, 35];

// ---------- Rooms ----------
// Seat a is 'you' and seat b is 'cpu' in the rules' terms. Each seat gets its own events, said from its own side.
const rooms = new Map();
// Four letters, no look-alikes (no I, L, O, 0, 1).
const LETTERS = 'ABCDEFGHJKMNPQRSTUVWXYZ';
function newCode() {
  for (;;) {
    const code = Array.from({ length: 4 }, () => LETTERS[randomInt(LETTERS.length)]).join('');
    if (!rooms.has(code)) return code;
  }
}
const SIDE = { a: 'you', b: 'cpu' };
const SEAT = { you: 'a', cpu: 'b' };
const otherSeat = (s) => (s === 'a' ? 'b' : 'a');

function makeRoom(set, target) {
  let uid = 0;
  const room = {
    code: newCode(), set, target,
    rules: create(set, { NAME: { you: 'A', cpu: 'B' }, verb: (w, b) => b, nextId: () => ++uid }),
    seats: { a: newSeat(), b: null },
    S: null, picks: { a: null, b: null }, rematch: { a: false, b: false },
    status: 'waiting',   // waiting (for seat b) -> playing -> over (-> playing again on a rematch); left; closed
    idleSince: Date.now(),
  };
  rooms.set(room.code, room);
  return room;
}
function newSeat() { return { token: randomBytes(12).toString('hex'), streams: new Set(), events: [], seq: 0 }; }

function deal(room) {
  const S = { ...newDeal(), target: room.target, phase: 'pick', snaps: 0 };
  room.rules.dealHands(S);
  room.S = S; room.picks = { a: null, b: null }; room.rematch = { a: false, b: false };
  room.status = 'playing';
}

// What one seat may see: its own hand, how many specials the other side holds, and the board. Sides are said from
// that seat ('you' is always the viewer).
function view(room, seat) {
  const S = room.S, me = SIDE[seat], them = SIDE[otherSeat(seat)];
  const base = { code: room.code, set: room.set, target: room.target, status: room.status, seat };
  if (!S) return base;
  return {
    ...base,
    score: { you: S.score[me], cpu: S.score[them] },
    poss: S.poss === me ? 'you' : 'cpu', pos: S.pos, down: S.down, phase: S.phase, snaps: S.snaps,
    hand: S.hands[me], theirCount: S.hands[them].length,
    picked: { you: !!room.picks[seat], cpu: !!room.picks[otherSeat(seat)] },
    rematch: { you: room.rematch[seat], cpu: room.rematch[otherSeat(seat)] },
  };
}

// Each seat keeps a numbered list of its events, so a phone that drops off (locked, backgrounded) gets the ones it
// missed when it reconnects (EventSource sends the last number it saw).
function send(room, seat, type, data = {}) {
  const st = room.seats[seat];
  if (!st) return;
  const ev = { id: ++st.seq, type, data: { ...data, view: view(room, seat) } };
  st.events.push(ev);
  if (st.events.length > 200) st.events.shift();
  for (const res of st.streams) write(res, ev);
}
const both = (room, type, dataFor) => { for (const s of ['a', 'b']) send(room, s, type, dataFor ? dataFor(s) : {}); };
function write(res, ev) { res.write(`id: ${ev.id}\nevent: ${ev.type}\ndata: ${JSON.stringify(ev.data)}\n\n`); }

// ---------- Picks ----------
class Refused extends Error { constructor(status, msg) { super(msg); this.status = status; } }
function checkPick(room, seat, play, special) {
  const S = room.S, me = SIDE[seat];
  if (room.status !== 'playing' || S.phase !== 'pick') throw new Refused(409, 'Not picking right now.');
  if (room.picks[seat]) throw new Refused(409, 'Already picked.');
  const off = S.poss === me;
  const ok = off ? [...OFF, ...(S.pos === room.rules.RED ? ['fg'] : [])] : DEF;
  if (!ok.includes(play)) throw new Refused(400, 'That play isn’t in your hand.');
  let card = null;
  if (special != null) {
    card = S.hands[me].find((c) => c.id === special);
    if (!card) throw new Refused(400, 'That special isn’t in your hand.');
    if (!fits(card.key, play, off ? 'off' : 'def')) throw new Refused(400, 'That special can’t go with that play.');
  }
  return { play, card };
}

// A kick needs no defense pick: it goes as soon as the offense picks it, and the defense keeps any special it chose.
function pick(room, seat, play, special) {
  const p = checkPick(room, seat, play, special);
  const S = room.S, me = SIDE[seat];
  if (p.play === 'fg') {
    room.picks = { a: null, b: null };
    S.snaps++;
    room.rules.fieldGoal(S, me);
    both(room, 'snap', (s) => ({ fg: s === seat ? 'you' : 'cpu' }));
    if (S.phase === 'over') finish(room);
    return;
  }
  room.picks[seat] = p;
  if (!room.picks[otherSeat(seat)]) { send(room, otherSeat(seat), 'picked'); send(room, seat, 'picked'); return; }
  const picks = { you: room.picks.a, cpu: room.picks.b };
  room.picks = { a: null, b: null };
  const shown = { you: { ...picks.you }, cpu: { ...picks.cpu } };   // as picked, before playSnap adds a status
  S.snaps++;
  const { off, r } = room.rules.playSnap(S, picks);
  room.rules.apply(S, r, off);
  // Each side sees its own pick as 'you'.
  both(room, 'snap', (s) => {
    const mine = SIDE[s], theirs = SIDE[otherSeat(s)];
    return { picks: { you: shown[mine], cpu: shown[theirs] } };
  });
  if (S.phase === 'over') finish(room);
}
function finish(room) { room.status = 'over'; both(room, 'over'); }

// ---------- HTTP ----------
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.woff2': 'font/woff2' };
const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS' };
function json(res, status, body) { res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', ...CORS }); res.end(JSON.stringify(body)); }
async function body(req) {
  let s = '';
  for await (const chunk of req) { s += chunk; if (s.length > 10000) throw new Refused(413, 'Too big.'); }
  try { return s ? JSON.parse(s) : {}; } catch { throw new Refused(400, 'Bad JSON.'); }
}
function seatOf(room, token) {
  for (const s of ['a', 'b']) if (room.seats[s] && token && room.seats[s].token === token) return s;
  throw new Refused(403, 'Not in this game.');
}
function roomOf(code) {
  const room = rooms.get(String(code || '').toUpperCase());
  if (!room || room.status === 'closed') throw new Refused(404, 'No game with that code.');
  return room;
}

async function api(req, res, url) {
  const parts = url.pathname.split('/').filter(Boolean);   // api, rooms, CODE, action
  if (parts[1] === 'ping') return json(res, 200, { ok: true });
  if (parts[1] !== 'rooms') throw new Refused(404, 'Not found.');
  if (parts.length === 2 && req.method === 'POST') {
    const { set, target } = await body(req);
    const room = makeRoom(set === 'twice' ? 'twice' : 'once', TARGETS.includes(+target) ? +target : 21);
    return json(res, 200, { code: room.code, seat: 'a', token: room.seats.a.token });
  }
  const room = roomOf(parts[2]);
  const action = parts[3];
  if (action === 'events' && req.method === 'GET') return stream(req, res, room, url);
  if (!action && req.method === 'GET') { seatOf(room, url.searchParams.get('token')); return json(res, 200, { status: room.status }); }
  if (req.method !== 'POST') throw new Refused(405, 'Use POST.');
  const b = await body(req);
  if (action === 'join') {
    for (const s of ['a', 'b']) if (room.seats[s] && b.token && room.seats[s].token === b.token) return json(res, 200, { code: room.code, seat: s, token: b.token });
    if (room.seats.b) throw new Refused(409, 'That game already has two players.');
    room.seats.b = newSeat();
    deal(room);
    json(res, 200, { code: room.code, seat: 'b', token: room.seats.b.token });
    both(room, 'start');
    return;
  }
  const seat = seatOf(room, b.token);
  room.idleSince = Date.now();
  if (action === 'pick') {
    pick(room, seat, b.play, b.special == null ? null : +b.special);
    return json(res, 200, { ok: true });
  }
  if (action === 'rematch') {
    if (room.status !== 'over') throw new Refused(409, 'The game isn’t over.');
    room.rematch[seat] = true;
    if (room.rematch[otherSeat(seat)]) { deal(room); both(room, 'start'); } else both(room, 'rematch');
    return json(res, 200, { ok: true });
  }
  if (action === 'leave') {
    const was = room.status;
    room.status = 'left';
    send(room, otherSeat(seat), 'left', { before: was });
    setTimeout(() => close(room), 60 * 1000);
    return json(res, 200, { ok: true });
  }
  throw new Refused(404, 'Not found.');
}

function stream(req, res, room, url) {
  const seat = seatOf(room, url.searchParams.get('token'));
  const st = room.seats[seat];
  res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', Connection: 'keep-alive', 'X-Accel-Buffering': 'no', ...CORS });
  res.write('retry: 1500\n\n');
  const last = +(req.headers['last-event-id'] || url.searchParams.get('last') || 0);
  const missed = st.events.filter((e) => e.id > last);
  // Too far behind (or a fresh page): a sync with the whole board instead of the missed events.
  if (!last || (missed.length && missed[0].id !== last + 1)) write(res, { id: st.seq, type: 'sync', data: { view: view(room, seat) } });
  else for (const e of missed) write(res, e);
  st.streams.add(res);
  room.idleSince = Date.now();
  const beat = setInterval(() => res.write(': beat\n\n'), 20000);
  req.on('close', () => { clearInterval(beat); st.streams.delete(res); room.idleSince = Date.now(); });
}
function close(room) {
  room.status = 'closed';
  for (const s of ['a', 'b']) if (room.seats[s]) for (const res of room.seats[s].streams) res.end();
  rooms.delete(room.code);
}
// Rooms nobody is connected to close after a while; a phone that comes back gets "No game with that code".
setInterval(() => {
  for (const room of rooms.values()) {
    const live = ['a', 'b'].some((s) => room.seats[s] && room.seats[s].streams.size);
    if (!live && Date.now() - room.idleSince > IDLE_MS) close(room);
  }
}, 60 * 1000).unref();

async function files(req, res, url) {
  let path = decodeURIComponent(url.pathname);
  if (path.endsWith('/')) path += 'index.html';
  const file = normalize(join(ROOT, path));
  if (!file.startsWith(ROOT) || /(^|\/)\.[^/]/.test(path)) { res.writeHead(404); return res.end('Not found'); }
  try {
    const s = await stat(file);
    if (s.isDirectory()) { res.writeHead(301, { Location: url.pathname + '/' }); return res.end(); }
    res.writeHead(200, { 'Content-Type': MIME[extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
    res.end(await readFile(file));
  } catch { res.writeHead(404); res.end('Not found'); }
}

createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  try {
    if (req.method === 'OPTIONS') { res.writeHead(204, CORS); return res.end(); }
    if (url.pathname.startsWith('/api/')) return await api(req, res, url);
    return await files(req, res, url);
  } catch (e) {
    if (e instanceof Refused) return json(res, e.status, { error: e.message });
    console.error(e);
    if (!res.headersSent) json(res, 500, { error: 'Something went wrong.' });
  }
}).listen(PORT, '0.0.0.0', () => {
  const ips = Object.values(networkInterfaces()).flat().filter((i) => i && i.family === 'IPv4' && !i.internal).map((i) => i.address);
  console.log(`Snap Call online: http://localhost:${PORT}/look/`);
  for (const ip of ips) console.log(`  on this Wi-Fi:  http://${ip}:${PORT}/look/`);
});

export { rooms, makeRoom, deal, view, pick };
