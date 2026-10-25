'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const express = require(path.join(process.env.SONG_REQUEST_PROJECT || process.cwd(), 'node_modules', 'express'));
const install = require('../leihu-selection-compat');
const source = fs.readFileSync(path.join(__dirname, 'queue-fixture.js'), 'utf8');
function fixtureQueue() {
  const module = { exports: {} };
  vm.runInNewContext(source, { module, exports: module.exports, console, Date, Set });
  return module.exports;
}
async function server(t) {
  const queue = fixtureQueue(), links = [];
  const app = express(); app.use(express.json());
  app.get('/api/leihu/status', (req, res) => res.json({ native: true }));
  install(app, { queue, leihu: { setLink: (...args) => links.push(args) } });
  const listener = app.listen(0, '127.0.0.1');
  await new Promise(resolve => listener.once('listening', resolve));
  t.after(() => new Promise(resolve => listener.close(resolve)));
  const url = `http://127.0.0.1:${listener.address().port}`;
  async function get() { return (await fetch(url + '/api/integrations/leihu/selection')).json(); }
  async function post(song, action, expectedRevision) {
    return fetch(url + '/api/integrations/leihu/selection', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ song, action, expectedRevision: expectedRevision ?? (await get()).revision }) });
  }
  return { queue, links, url, get, post };
}
test('new endpoint preserves native API, links without replacing requester, and rejects stale writes', async t => {
  const s = await server(t);
  assert.equal((await (await fetch(s.url + '/api/leihu/status')).json()).native, true);
  s.queue.addSong({ title: '下一個天亮', requester: 'viewer', key: '-2' });
  s.queue.addSong({ title: 'Later', requester: 'other' });
  const before = await s.get();
  assert.equal((await s.post({ id: 'songaa', title: '郭靜 下一個天亮 歌詞' }, 'link')).status, 200);
  let state = s.queue.getState();
  assert.equal(state.nowPlaying.title, '下一個天亮');assert.equal(state.nowPlaying.requester, 'viewer');assert.equal(state.nowPlaying.key, '-2');assert.equal(state.queue.length, 1);
  assert.deepEqual(s.links[0], ['下一個天亮', '', 'songaa']);
  const linked = await s.get();
  assert.equal((await s.post({ id: 'songaa', title: 'Another title' }, 'link')).status, 200);
  assert.equal((await s.get()).revision, linked.revision);
  assert.equal((await s.post({ id: 'stale', title: 'Stale' }, 'link', before.revision)).status, 409);
});
test('reverse selection promotes an existing request, keeps previous song queued, and is idempotent', async t => {
  const s = await server(t);
  s.queue.addSong({ title: 'First', requester: 'one' });
  s.queue.addSong({ title: 'Requested', artist: 'Artist', key: '-3', requester: 'two', isRandom: true });
  const choice = { id: 'songbb', title: 'Requested', artist: 'Artist' };
  assert.equal((await s.post(choice)).status, 200);
  let state = s.queue.getState();
  assert.equal(state.nowPlaying.requester, 'two');assert.equal(state.nowPlaying.key, '-3');assert.equal(state.nowPlaying.isRandom, true);
  assert.equal(state.queue.length, 1);assert.equal(state.queue[0].title, 'First');
  const revision = (await s.get()).revision;
  assert.equal((await s.post(choice)).status, 200);assert.equal((await s.get()).revision, revision);assert.equal(s.queue.getState().queue.length, 1);
});
test('new songs become current even when current is empty but queued entries exist', async t => {
  const s = await server(t);
  s.queue.addSong({ title: 'Existing', requester: 'viewer' });
  s.queue.moveSong('nowPlaying', 0, 'queue', 0);
  assert.equal(s.queue.getState().nowPlaying, null);
  assert.equal((await s.post({ id: 'newone', title: 'New song' })).status, 200);
  assert.equal(s.queue.getState().nowPlaying.title, 'New song');assert.equal(s.queue.getState().queue[0].title, 'Existing');
});
test('pending candidate selection preserves the requested artist/key and played entries are reused', async t => {
  const s = await server(t);
  s.queue.addPending({ requester: 'pending-viewer', originalRequest: 'Same title', candidates: [
    { title: 'Same title', artist: 'A', key: '2' }, { title: 'Same title', artist: 'B', key: '-4' },
  ] });
  const choice = { id: 'artistb', title: 'Same title', artist: 'B' };
  assert.equal((await s.post(choice)).status, 200);
  let state = s.queue.getState();
  assert.equal(state.pending.length, 0);assert.equal(state.nowPlaying.artist, 'B');assert.equal(state.nowPlaying.key, '-4');assert.equal(state.nowPlaying.requester, 'pending-viewer');
  s.queue.skipSong();
  assert.equal((await s.post(choice)).status, 200);
  state = s.queue.getState();assert.equal(state.playedSongs.length, 0);assert.equal(state.nowPlaying.playedAt, undefined);assert.equal(state.nowPlaying.requester, 'pending-viewer');
});
test('validation blocks bad and cross-origin writes, and queue-only changes preserve revision', async t => {
  const s = await server(t);
  assert.equal((await s.post({ id: 'songaa', title: 'Missing' }, 'link')).status, 409);
  assert.equal((await s.post({ id: '../bad', title: 'Bad' })).status, 400);
  assert.equal((await s.post({ id: 'songaa', title: 'Bad' }, 'unsupported')).status, 400);
  const response = await fetch(s.url + '/api/integrations/leihu/selection', { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: 'https://untrusted.example' }, body: '{}' });
  assert.equal(response.status, 403);
  s.queue.addSong({ title: 'Current', requester: 'viewer' });const revision = (await s.get()).revision;
  s.queue.addSong({ title: 'Queued', requester: 'viewer' });assert.equal((await s.get()).revision, revision);
});
test('ambiguous reverse matches require an artist instead of picking an arbitrary viewer request', async t => {
  const s = await server(t);
  s.queue.addSong({ title: 'Current', requester: 'viewer' });
  s.queue.addSong({ title: 'Same', artist: 'A', requester: 'one' });s.queue.addSong({ title: 'Same', artist: 'B', requester: 'two' });
  assert.equal((await s.post({ id: 'ambig', title: 'Same' })).status, 422);assert.equal(s.queue.getState().queue.length, 2);
});
function project() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'leihu-repair-'));
  fs.mkdirSync(path.join(dir, 'server'));fs.writeFileSync(path.join(dir, 'package.json'), '{}');
  fs.writeFileSync(path.join(dir, 'server', 'queue.js'), source);
  fs.writeFileSync(path.join(dir, 'server', 'leihu.js'), 'module.exports={setLink(){}};');
  fs.writeFileSync(path.join(dir, 'server', 'index.js'), '\ufeffconst app={get(){}};\r\n// keep native routes\r\napp.get(\'/api/leihu/status\',()=>{});\r\n');
  fs.writeFileSync(path.join(dir, '.env'), 'DO_NOT_TOUCH=test-secret');return dir;
}
function run(dir, ...args) { return spawnSync(process.execPath, [path.join(__dirname, '..', 'install.js'), dir, ...args], { encoding: 'utf8' }); }
test('installer preserves bytes/settings, refuses repeated patches and safely restores the backup', t => {
  const dir = project();t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const before = fs.readFileSync(path.join(dir, 'server', 'index.js'));
  const native = fs.readFileSync(path.join(dir, 'server', 'leihu.js'));
  assert.equal(run(dir).status, 0);
  const patched = fs.readFileSync(path.join(dir, 'server', 'index.js'), 'utf8');
  assert.equal(patched.split("require('./leihu-selection-compat')(app);").length, 2);assert.ok(patched.startsWith('\ufeff'));assert.ok(patched.includes('\r\n'));
  assert.deepEqual(fs.readFileSync(path.join(dir, 'server', 'leihu.js')), native);assert.equal(fs.readFileSync(path.join(dir, '.env'), 'utf8'), 'DO_NOT_TOUCH=test-secret');
  assert.notEqual(run(dir).status, 0);
  assert.equal(run(dir, '--undo').status, 0);assert.deepEqual(fs.readFileSync(path.join(dir, 'server', 'index.js')), before);
});
test('installer refuses unknown interfaces and undo refuses to erase later user edits', t => {
  const dir = project();t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  assert.equal(run(dir).status, 0);
  fs.appendFileSync(path.join(dir, 'server', 'index.js'), '// later edit\n');
  assert.notEqual(run(dir, '--undo').status, 0);
  const other = project();t.after(() => fs.rmSync(other, { recursive: true, force: true }));
  const before = fs.readFileSync(path.join(other, 'server', 'index.js'));
  fs.writeFileSync(path.join(other, 'server', 'queue.js'), 'module.exports={};');
  assert.notEqual(run(other).status, 0);assert.deepEqual(fs.readFileSync(path.join(other, 'server', 'index.js')), before);
});
