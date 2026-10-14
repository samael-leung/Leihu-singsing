const { test } = require('node:test');
const assert = require('node:assert/strict');
const { SongRequestSync, findSong } = require('../static/song-request');

test('matches IDs, normalized names, YouTube track and artist; refuses ambiguous/missing songs', () => {
  const songs = [{ id: '1', title: 'Video title', yt_track: '歌曲', yt_artist: 'A' },
    { id: '2', title: '歌曲', yt_artist: 'B' }];
  assert.equal(findSong(songs, { title: '歌曲', artist: 'A' }).id, '1');
  assert.equal(findSong(songs, { title: 'renamed', leihuId: '2' }).id, '2');
  assert.throws(() => findSong(songs, { title: '歌曲' }), /重複/);
  assert.throws(() => findSong(songs, { title: '不存在' }), /找不到/);
  assert.equal(findSong([{ id: '3', title: 'ＡＢＣ' }], { title: ' abc ' }).id, '3');
});

test('remote revisions select once; manual selections publish once without feedback', async () => {
  let state = { revision: '1', nowPlaying: { title: 'Song A' } };
  const writes = [], opens = [];
  const sync = new SongRequestSync({
    request: async body => {
      if (body) { writes.push(body); state = { revision: '2', nowPlaying: body.song }; }
      return state;
    },
    listSongs: async () => [{ id: 'a', title: 'Song A' }],
    openSong: async id => opens.push(id), status: () => {},
  });
  await sync.tick(); assert.deepEqual(opens, []);
  sync.setEnabled(true);
  await sync.tick(); await sync.tick();
  assert.deepEqual(opens, ['a']); assert.deepEqual(writes, []);
  sync.selected({ id: 'b', title: 'Song B', yt_artist: 'Artist' });
  await sync.tick(); await sync.tick();
  assert.equal(writes.length, 1);
  assert.equal(writes[0].expectedRevision, '1');
  assert.equal(writes[0].song.artist, 'Artist');
  assert.deepEqual(opens, ['a']);
  state = { revision: '3', nowPlaying: null };
  await sync.tick(); assert.deepEqual(opens, ['a']);
});

test('failed writes retry; a newer local choice survives an in-flight response', async () => {
  let resolveWrite, fail = true;
  const writes = [];
  const sync = new SongRequestSync({
    request: async body => {
      if (!body) return { revision: 'server', nowPlaying: null };
      writes.push(body.song.id);
      if (fail) { fail = false; throw new Error('conflict'); }
      return new Promise(resolve => { resolveWrite = resolve; });
    }, listSongs: async () => [], openSong: async () => {}, status: () => {},
  });
  sync.setEnabled(true); sync.selected({ id: 'a', title: 'A' });
  await sync.tick(); assert.equal(sync.pending.id, 'a');
  const tick = sync.tick();
  await new Promise(resolve => setImmediate(resolve));
  sync.selected({ id: 'b', title: 'B' });
  resolveWrite({ revision: 'new' }); await tick;
  assert.equal(sync.pending.id, 'b');
  assert.deepEqual(writes, ['a', 'a']);
});

test('local selection and disabling cancel stale remote reads', async () => {
  let resolveRead;
  const opens = [];
  const sync = new SongRequestSync({
    request: () => new Promise(resolve => { resolveRead = resolve; }),
    listSongs: async () => [{ id: 'a', title: 'A' }],
    openSong: async id => opens.push(id), status: () => {},
  });
  sync.setEnabled(true);
  let tick = sync.tick();
  sync.beginSelection();
  resolveRead({ revision: '1', nowPlaying: { title: 'A' } }); await tick;
  assert.deepEqual(opens, []);
  sync.endSelection(); tick = sync.tick(); sync.setEnabled(false);
  resolveRead({ revision: '1', nowPlaying: { title: 'A' } }); await tick;
  assert.deepEqual(opens, []);
});
