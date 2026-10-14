/* Browser selection bridge. Kept independent of audio/model processing. */
(function (root) {
  'use strict';
  const normalize = value => String(value || '').normalize('NFKC').trim().toLowerCase();

  function findSong(songs, selected) {
    if (selected.leihuId) {
      const byId = songs.find(song => song.id === selected.leihuId);
      if (byId) return byId;
    }
    const candidates = songs.filter(song => [song.title, song.yt_track].some(
      title => title && normalize(title) === normalize(selected.title)));
    const byArtist = selected.artist ? candidates.filter(song =>
      normalize(song.yt_artist || song.artist || song.lyrics_online?.artist) === normalize(selected.artist)) : [];
    if (byArtist.length === 1) return byArtist[0];
    if (candidates.length === 1) return candidates[0];
    throw new Error(candidates.length ? '歌曲名稱重複，請在練唱台手動選歌以建立對應。' : `練唱台找不到歌曲：${selected.title}`);
  }

  class SongRequestSync {
    constructor({ request, listSongs, openSong, status }) {
      Object.assign(this, { request, listSongs, openSong, status });
      this.enabled = false;
      this.busy = false;
      this.pending = null;
      this.revision = null;
      this.generation = 0;
      this.selecting = false;
    }
    setEnabled(enabled) {
      this.enabled = enabled;
      this.generation++;
      this.pending = null;
      this.revision = null;
    }
    selected(song) {
      if (!this.enabled) return;
      this.pending = { id: song.id, title: song.yt_track || song.title,
        artist: song.yt_artist || song.artist || song.lyrics_online?.artist || '' };
      this.generation++;
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
        const state = await this.request();
        if (!active()) return;
        if (this.pending) {
          const sent = this.pending;
          const updated = await this.request({ song: sent, expectedRevision: state.revision });
          if (!active()) return;
          this.pending = null;
          this.revision = updated.revision;
        } else if (state.revision !== this.revision) {
          if (state.nowPlaying) {
            const songs = await this.listSongs();
            if (!active()) return;
            const song = findSong(songs, state.nowPlaying);
            await this.openSong(song.id);
            if (!active()) return;
          }
          this.revision = state.revision;
        }
        this.status('點歌同步已連線');
      } catch (error) {
        if (active()) this.status(error.message);
      } finally {
        this.busy = false;
      }
    }
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { SongRequestSync, findSong };
  else root.SongRequestSync = SongRequestSync;
})(typeof window === 'undefined' ? globalThis : window);
