/* Browser selection bridge. Kept independent of audio/model processing. */
(function (root) {
  'use strict';
  const normalize = value => String(value || '').normalize('NFKC').trim().toLowerCase();
  const compact = value => normalize(value).replace(/[^\p{L}\p{N}]/gu, '');
  const artistOf = song => song.yt_artist || song.artist || song.lyrics_online?.artist || '';
  const linkKey = song => JSON.stringify([compact(song.title), compact(song.artist)]);
  const noise = /(?:\bofficial\s+(?:music\s*)?(?:video|audio|mv)\b|music\s+video|lyrics?(?:\s+video)?|高清|高音質|高音质|動態歌詞|动态歌词|中英字幕|中文字幕|官方(?:完整)?(?:版|mv|音樂錄影帶|音乐录影带)*|完整版|歌詞版|歌词版|歌詞|歌词|\b(?:hd|hq|4k|1080p|720p|mv)\b)/gi;
  function cleanTitle(value) {
    return String(value || '').normalize('NFKC').trim().replace(/\.(?:mp3|wav|flac|m4a|webm)$/i, '')
      .replace(/[\[【(（]([^\]】)）]*)[\]】)）]/g, (all, inner) => {
        const cleaned = inner.replace(noise, '').replace(/^(?:live|remix|cover(?: by .*)?|instrumental|karaoke|現場(?:版)?|现场(?:版)?|翻唱(?:版)?|伴奏(?:版)?)$/i, '')
          .replace(/[^\p{L}\p{N}]/gu, '');
        return cleaned ? ` ${inner} ` : ' ';
      }).replace(noise, ' ').replace(/[《》「」『』]/g, ' ').replace(/\s+/g, ' ').trim();
  }
  function distance(a, b) {
    const row = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      let previous = row[0]; row[0] = i;
      for (let j = 1; j <= b.length; j++) {
        const old = row[j];
        row[j] = Math.min(row[j] + 1, row[j - 1] + 1, previous + (a[i - 1] === b[j - 1] ? 0 : 1));
        previous = old;
      }
    }
    return row[b.length];
  }
  function variants(song) {
    const titles = [song.yt_track, song.lyrics_online?.track, song.title, ...(song.searchTitles || [])]
      .filter(Boolean).flatMap(value => [value, value.split(/[『「]/)[0]]);
    const artists = [artistOf(song), ...(song.searchArtists || [])].filter(Boolean).map(compact);
    const result = [];
    for (const raw of titles) {
      const cleaned = cleanTitle(raw);
      result.push({ text: compact(cleaned), parsed: false });
      // Keep bracketed song names, and split common artist / title separators.
      for (const group of raw.matchAll(/[《「『]([^》」』]+)[》」』]/g))
        result.push({ text: compact(cleanTitle(group[1])), parsed: true });
      const parts = cleaned.split(/\s*[-–—|/／:]\s*/).map(s => s.trim()).filter(Boolean);
      if (parts.length > 1) for (const part of parts.slice(1))
        result.push({ text: compact(part), parsed: true });
      const chinesePrefix = cleaned.match(/^([\p{Script=Han}]{2,4})\s+(.+)$/u);
      if (chinesePrefix) result.push({ text: compact(chinesePrefix[2]), parsed: true });
      const chineseSuffix = cleaned.match(/^(.+)\s+([\p{Script=Han}]{2,4})$/u);
      if (chineseSuffix) result.push({ text: compact(chineseSuffix[1]), parsed: true });
      for (const artist of artists) {
        const full = compact(cleaned);
        if (full.startsWith(artist) && full.length > artist.length)
          result.push({ text: full.slice(artist.length), parsed: true });
        if (full.endsWith(artist) && full.length > artist.length)
          result.push({ text: full.slice(0, -artist.length), parsed: true });
      }
    }
    return { titles: result.filter(v => v.text.length >= 2), artists };
  }
  function version(value) {
    return normalize(value).match(/\b(?:live|remix|cover|instrumental|karaoke)\b|現場|现场|翻唱|伴奏/g) || [];
  }
  function rankSongs(songs, selected) {
    const queries = variants({ title: selected.title, artist: selected.artist }).titles;
    if (!queries.length) return [];
    const artist = compact(selected.artist);
    return songs.filter(song => !song.steps || song.steps.pitch).map(song => {
      const data = variants(song);
      let score = 0;
      for (const candidate of data.titles) {
        let text = candidate.text;
        if (artist && text.startsWith(artist) && text.length > artist.length) text = text.slice(artist.length);
        for (const { text: query, parsed } of queries) {
          const similarity = text === query ? (candidate.parsed || parsed ? 0.97 : 1) :
            (query.length >= 5 && Math.max(text.length, query.length) <= 200 ?
              (1 - distance(query, text) / Math.max(query.length, text.length)) * 0.96 : 0);
          score = Math.max(score, similarity);
        }
      }
      const raw = cleanTitle(song.title);
      const rawParts = raw.split(/\s*[-–—|/／:]\s*/);
      const inferredArtist = rawParts.length > 1 ? compact(rawParts[0]) : '';
      const chineseArtist = compact(raw.match(/^([\p{Script=Han}]{2,4})\s+/u)?.[1] ||
        raw.match(/^.+\s+([\p{Script=Han}]{2,4})$/u)?.[1]);
      const artistMatches = artist && (data.artists.includes(artist) || inferredArtist === artist || chineseArtist === artist ||
        (/\p{Script=Han}/u.test(artist) && inferredArtist.includes(artist)));
      if (artistMatches) score += 0.08;
      else if (artist && (data.artists.length || inferredArtist || chineseArtist)) score -= 0.16;
      else if (artist) score -= 0.04;
      const requestedVersion = version(selected.title);
      const actualVersion = version(song.title);
      if (actualVersion.some(v => !requestedVersion.includes(v))) score -= 0.12;
      if (requestedVersion.some(v => !actualVersion.includes(v))) score -= 0.2;
      return { song, score };
    }).filter(item => item.score >= 0.55).sort((a, b) => b.score - a.score);
  }

  function findSong(songs, selected, links = []) {
    songs = songs.filter(song => !song.steps || song.steps.pitch);
    const saved = links.find(link => linkKey(link) === linkKey(selected));
    if (saved) {
      const linked = songs.find(song => song.id === saved.songId);
      if (linked) return linked;
    }
    if (selected.leihuId) {
      const byId = songs.find(song => song.id === selected.leihuId);
      if (byId) return byId;
    }
    const ranked = rankSongs(songs, selected);
    const best = ranked[0], runner = ranked[1];
    if (best && best.score >= 0.9 && (!runner || best.score - runner.score >= 0.075)) return best.song;
    const error = new Error(ranked.length ? '歌曲名稱相近或重複，請點選一次確認；之後會自動對應。' : `練唱台找不到歌曲：${selected.title}`);
    error.candidates = ranked.slice(0, 4).map(item => item.song);
    throw error;
  }

  class SongRequestSync {
    constructor({ request, listSongs, openSong, status, loadLinks = async () => [],
      saveLink = async () => {}, listRequestSongs = async () => [], choices = () => {} }) {
      Object.assign(this, { request, listSongs, openSong, status, loadLinks, saveLink, listRequestSongs, choices });
      this.links = null;
      this.unresolved = null;
      this.enabled = false;
      this.busy = false;
      this.pending = null;
      this.revision = null;
      this.choices([]);
      this.generation = 0;
      this.selecting = false;
    }
    setEnabled(enabled) {
      this.enabled = enabled;
      this.generation++;
      this.pending = null;
      this.revision = null;
      this.unresolved = null;
      this.reviewing = false;
      this.choices([]);
    }
    selected(song) {
      if (!this.enabled) return;
      const source = this.unresolved?.source || [...(this.links || [])].reverse().find(link => link.songId === song.id);
      this.pending = { id: song.id, title: source?.title || song.yt_track || song.lyrics_online?.track || cleanTitle(song.title),
        artist: source ? source.artist || '' : artistOf(song), binding: this.unresolved, known: !!source };
      this.generation++;
    }
    confirm(song) { this.selected(song); return this.tick(); }
    review() {
      if (!this.enabled) return;
      this.generation++;
      this.pending = null;
      this.revision = null;
      this.reviewing = true;
      return this.tick();
    }
    async remember(source, songId) {
      const link = { title: source.title, artist: source.artist || '', songId };
      await this.saveLink(link);
      this.links = [...(this.links || []).filter(item => linkKey(item) !== linkKey(link)), link];
    }
    beginSelection() {
      this.selecting = true;
      this.generation++;
    }
    endSelection() { this.selecting = false; }
    async tick() {
      if (!this.enabled || this.busy || this.selecting) return;
      this.busy = true;
      const generation = this.generation;
      const active = () => this.enabled && this.generation === generation;
      try {
        if (!this.links) this.links = await this.loadLinks();
        if (!active()) return;
        const state = await this.request();
        if (!active()) return;
        if (this.pending) {
          const sent = this.pending;
          if (sent.binding && sent.binding.revision !== state.revision) {
            this.pending = null;
            this.unresolved = null;
            this.revision = null;
            this.reviewing = false;
            this.status('正在播放已變更，重新比對中…');
            return;
          }
          const { binding, known, ...song } = sent;
          if (!binding && !known) {
            const remembered = [...this.links].reverse().find(link => link.songId === sent.id);
            if (remembered) {
              song.title = remembered.title; song.artist = remembered.artist || '';
            } else {
              const catalog = await this.listRequestSongs();
              if (!active()) return;
              try {
                const canonical = findSong(catalog, song);
                song.title = canonical.title; song.artist = canonical.artist || '';
              } catch (_) { /* New or ambiguous song: keep the selected local title. */ }
            }
          }
          const updated = await this.request({ song, expectedRevision: state.revision, ...(binding ? { action: 'link' } : {}) });
          if (!active()) return;
          if (binding) {
            await this.openSong(sent.id);
            await this.remember(binding.source, sent.id);
          } else await this.remember(song, sent.id);
          if (!active()) return;
          this.pending = null;
          this.unresolved = null;
          this.reviewing = false;
          this.choices([]);
          this.revision = updated.revision;
        } else if (state.revision !== this.revision) {
          if (state.nowPlaying) {
            const songs = await this.listSongs();
            if (!active()) return;
            let song;
            try {
              if (this.reviewing) {
                const error = new Error('請選擇正確歌曲，之後會記住這次對應。');
                error.candidates = rankSongs(songs, state.nowPlaying).slice(0, 4).map(item => item.song);
                throw error;
              }
              song = findSong(songs, state.nowPlaying, this.links);
            }
            catch (error) {
              this.unresolved = { source: state.nowPlaying, revision: state.revision };
              this.choices(error.candidates || []);
              throw error;
            }
            await this.openSong(song.id);
            if (!active()) return;
            // Bind the existing request instead of replacing its canonical title/requester.
            const updated = await this.request({ action: 'link', expectedRevision: state.revision,
              song: { id: song.id, title: state.nowPlaying.title, artist: state.nowPlaying.artist || '' } });
            if (!active()) return;
            await this.remember(state.nowPlaying, song.id);
            if (!active()) return;
            this.unresolved = null;
            this.reviewing = false;
            this.choices([]);
            this.revision = updated.revision;
          } else {
            this.revision = state.revision;
            this.unresolved = null;
            this.reviewing = false;
            this.choices([]);
          }
        }
        this.status('點歌同步已連線');
      } catch (error) {
        if (active()) this.status(error.message);
      } finally {
        this.busy = false;
      }
    }
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { SongRequestSync, findSong, rankSongs };
  else root.SongRequestSync = SongRequestSync;
})(typeof window === 'undefined' ? globalThis : window);
