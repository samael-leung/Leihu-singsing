const { test } = require('node:test');
const assert = require('node:assert/strict');
const { SongRequestSync, findSong } = require('../static/song-request');

test('screenshot titles match automatically without changing the catalog names', () => {
  const cases = [
    ['下一個天亮', '郭靜 下一個天亮 歌詞'],
    ['同手同腳', '溫嵐/同手同腳 ::Lyrics::'],
    ['春泥', 'en - 春泥 『風中你的淚滴 滴滴落在回憶裡，讓我們取名叫做珍惜。』【高音質 動態歌詞Lyrics】'],
    ['親愛的那不是愛情', '親愛的那不是愛情 張韶涵 (歌詞版)'],
    ['缺席', '鄭秀文 Sammi Cheng -《缺席》 Official MV (國)'],
    ['嗯嘛', '【HD】陶晶瑩-嗯嘛 [Official Music Video] 官方完整版MV'],
    ['一無所有', '《一無所有》原曲:なんもねぇ 尼古喵喵 主題曲 粵語版'],
    ['Yellow', 'Coldplay - Yellow (Official Video)'],
    ['Officially Missing You', 'Tamia - Officially Missing You (Official Video)'],
  ];
  const songs = cases.map(([, title], i) => ({ id: String(i), title }));
  for (const [index, [title]] of cases.entries()) assert.equal(findSong(songs, { title }).id, String(index));
  assert.equal(songs[0].title, cases[0][1]);
  assert.equal(findSong([{ id: 'ready', title: '勇氣', steps: { pitch: true } },
    { id: 'unfinished', title: '勇氣', steps: { pitch: false } }], { title: '勇氣' }).id, 'ready');
});

test('artist evidence distinguishes duplicate titles; short prefixes and wrong versions are not auto-picked', () => {
  const songs = [{ id: 'jay', title: '周杰倫 - 晴天 Official MV' }, { id: 'other', title: '五月天 - 晴天 (歌詞版)' }];
  assert.equal(findSong(songs, { title: '晴天', artist: '周杰倫' }).id, 'jay');
  assert.throws(() => findSong(songs, { title: '晴天' }), /確認/);
  assert.throws(() => findSong([songs[1]], { title: '晴天', artist: '周杰倫' }), /確認/);
  assert.throws(() => findSong([{ id: 'long', title: '彩虹金剛' }], { title: '彩虹' }), /找不到/);
  assert.throws(() => findSong([{ id: 'english', title: 'Love Story' }], { title: 'Love' }), /找不到/);
  assert.throws(() => findSong([{ id: 'artist', title: '郭靜 下一個天亮 歌詞' }], { title: '郭靜' }), /找不到/);
  assert.throws(() => findSong([{ id: 'live', title: '郭靜 - 下一個天亮 (Live)' }], { title: '下一個天亮' }), /確認/);
});

test('metadata and Chinese-script aliases are used; persistent links survive renamed titles', () => {
  const song = { id: 'saved', title: 'Unrelated video name', lyrics_online: { track: '下一個天亮', artist: '郭靜' } };
  assert.equal(findSong([song], { title: '下一個天亮', artist: '郭靜' }).id, 'saved');
  const simplified = { id: 'zh', title: '张韶涵 - 亲爱的那不是爱情', searchTitles: ['張韶涵 - 親愛的那不是愛情'], searchArtists: ['張韶涵'] };
  assert.equal(findSong([simplified], { title: '親愛的那不是愛情', artist: '張韶涵' }).id, 'zh');
  assert.equal(findSong([song], { title: 'Completely different request', artist: 'Singer' }, [
    { title: 'Completely different request', artist: 'Singer', songId: 'saved' },
  ]).id, 'saved');
  assert.throws(() => findSong([song], { title: 'Completely different request' }, [
    { title: 'Completely different request', artist: '', songId: 'deleted' },
  ]), /找不到/);
});

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
      if (body) {
        writes.push(body);
        state = { revision: body.action === 'link' ? 'linked' : '2',
          nowPlaying: body.action === 'link' ? { ...state.nowPlaying, leihuId: body.song.id } : body.song };
      }
      return state;
    },
    listSongs: async () => [{ id: 'a', title: 'Song A' }],
    openSong: async id => opens.push(id), status: () => {},
  });
  await sync.tick(); assert.deepEqual(opens, []);
  sync.setEnabled(true);
  await sync.tick(); await sync.tick();
  assert.deepEqual(opens, ['a']); assert.equal(writes.length, 1);
  assert.equal(writes[0].action, 'link');
  sync.selected({ id: 'b', title: 'Song B', yt_artist: 'Artist' });
  await sync.tick(); await sync.tick();
  assert.equal(writes.length, 2);
  assert.equal(writes[1].expectedRevision, 'linked');
  assert.equal(writes[1].song.artist, 'Artist');
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
  await new Promise(resolve => setImmediate(resolve));
  sync.beginSelection();
  resolveRead({ revision: '1', nowPlaying: { title: 'A' } }); await tick;
  assert.deepEqual(opens, []);
  sync.endSelection(); tick = sync.tick(); sync.setEnabled(false);
  resolveRead({ revision: '1', nowPlaying: { title: 'A' } }); await tick;
  assert.deepEqual(opens, []);
});

test('automatic mappings preserve canonical titles and reload after restart, including reverse selections', async () => {
  let state = { revision: '1', nowPlaying: { title: '下一個天亮', artist: '郭靜', requester: 'viewer' } };
  let library = [{ id: 'download', title: '郭靜 下一個天亮 歌詞' }];
  let saved = [];
  const opens = [], writes = [];
  const make = () => new SongRequestSync({
    request: async body => {
      if (body) {
        writes.push(body);
        state = { revision: state.revision + 'x', nowPlaying: body.action === 'link' ?
          { ...state.nowPlaying, leihuId: body.song.id } : body.song };
      }
      return state;
    }, listSongs: async () => library, openSong: async id => opens.push(id), status: () => {},
    loadLinks: async () => saved, saveLink: async link => { saved = [link]; },
  });
  let sync = make(); sync.setEnabled(true); await sync.tick();
  assert.equal(opens.at(-1), 'download');
  assert.equal(writes.at(-1).action, 'link');
  assert.equal(state.nowPlaying.title, '下一個天亮');
  assert.equal(state.nowPlaying.requester, 'viewer');
  assert.equal(saved[0].songId, 'download');
  // A fresh server state and renamed local file still use the durable relationship.
  state = { revision: 'restart', nowPlaying: { title: '下一個天亮', artist: '郭靜', requester: 'new-viewer' } };
  library = [{ id: 'download', title: 'Renamed download with no shared words' }];
  sync = make(); sync.setEnabled(true); await sync.tick();
  assert.equal(opens.at(-1), 'download');
  state = { revision: 'empty', nowPlaying: null }; await sync.tick();
  sync.selected(library[0]); await sync.tick();
  assert.equal(writes.at(-1).song.title, '下一個天亮');
  assert.equal(writes.at(-1).song.artist, '郭靜');
});

test('first-time reverse selection resolves a YouTube title against the request catalog', async () => {
  const writes = [], saved = [];
  const sync = new SongRequestSync({
    request: async body => {
      if (body) writes.push(body);
      return { revision: body ? 'updated' : 'empty', nowPlaying: null };
    }, listSongs: async () => [], openSong: async () => {}, status: () => {},
    listRequestSongs: async () => [{ title: '下一個天亮', artist: '郭靜' }],
    saveLink: async link => saved.push(link),
  });
  sync.setEnabled(true);
  sync.selected({ id: 'new-download', title: '郭靜 下一個天亮 歌詞' }); await sync.tick();
  assert.equal(writes[0].song.title, '下一個天亮');
  assert.equal(writes[0].song.artist, '郭靜');
  assert.equal(saved[0].title, '下一個天亮');
});

test('ambiguous downloads require one click, remember it, and can be explicitly remapped', async () => {
  let state = { revision: '1', nowPlaying: { title: '同名曲', requester: 'original' } };
  const songs = [{ id: 'a', title: '歌手甲 - 同名曲 (歌詞版)' }, { id: 'b', title: '歌手乙 - 同名曲 (歌詞版)' }];
  let candidates = [], saved = [];
  const writes = [], opens = [];
  const sync = new SongRequestSync({
    request: async body => {
      if (body) { writes.push(body); state = { revision: state.revision + 'x', nowPlaying: { ...state.nowPlaying, leihuId: body.song.id } }; }
      return state;
    }, listSongs: async () => songs, openSong: async id => opens.push(id), status: () => {},
    choices: values => { candidates = values; }, saveLink: async link => { saved = [link]; },
  });
  sync.setEnabled(true); await sync.tick();
  assert.equal(opens.length, 0); assert.equal(candidates.length, 2);
  await sync.confirm(songs[1]);
  assert.equal(opens.at(-1), 'b'); assert.equal(saved[0].songId, 'b');
  assert.equal(state.nowPlaying.requester, 'original');
  assert.equal(state.nowPlaying.title, '同名曲');
  assert.equal(writes[0].action, 'link');
  await sync.review(); assert.equal(candidates.length, 2);
  await sync.confirm(songs[0]); assert.equal(saved[0].songId, 'a');
  assert.equal(state.nowPlaying.requester, 'original');
});

test('confirmation for an old request cannot link a newly playing song', async () => {
  let state = { revision: '1', nowPlaying: { title: '同名曲' } };
  const songs = [{ id: 'a', title: '歌手甲 - 同名曲' }, { id: 'b', title: '歌手乙 - 同名曲' }];
  const writes = [], saved = [];
  const sync = new SongRequestSync({
    request: async body => { if (body) writes.push(body); return state; }, listSongs: async () => songs,
    openSong: async () => {}, status: () => {}, saveLink: async link => saved.push(link),
  });
  sync.setEnabled(true); await sync.tick();
  state = { revision: '2', nowPlaying: { title: '新歌' } };
  await sync.confirm(songs[0]);
  assert.equal(writes.length, 0); assert.equal(saved.length, 0);
});
