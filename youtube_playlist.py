"""Public YouTube playlist preview and durable, sequential import batches."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from urllib.parse import parse_qs, urlsplit

import pipeline as P

LIMIT = 200
_lock = threading.RLock()


def clean_url(value):
    if not isinstance(value, str):
        raise P.UserError('請貼上 YouTube 播放清單網址。')
    try:
        url = urlsplit(value.strip() if '://' in value else 'https://' + value.strip())
        port = url.port
    except ValueError as error:
        raise P.UserError('播放清單網址格式不正確。') from error
    playlist = (parse_qs(url.query).get('list') or [''])[0]
    if (url.scheme not in ('http', 'https') or url.hostname not in P.YOUTUBE_HOSTS or
            url.username or url.password or port not in (None, 80, 443) or
            not re.fullmatch(r'[A-Za-z0-9_-]{2,200}', playlist)):
        raise P.UserError('請貼上包含 list= 的 YouTube 播放清單網址。')
    return 'https://www.youtube.com/playlist?list=' + playlist


def preview(value, start=1):
    url = clean_url(value)
    if isinstance(start, bool) or not isinstance(start, int) or not 1 <= start <= 100000:
        raise P.UserError('播放清單起始項目必須是 1–100000 的整數。')
    args = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--flat-playlist', '--dump-single-json',
            '--skip-download', '--ignore-errors', '--no-warnings', '--socket-timeout', '15',
            '--playlist-start', str(start), '--playlist-end', str(start + LIMIT), url]
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                timeout=120, creationflags=0x08000000 if sys.platform == 'win32' else 0)
        data = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise P.UserError('讀取播放清單失敗或逾時，請確認為公開清單、網路可用並更新 yt-dlp 後重試。') from error
    if not isinstance(data, dict):
        raise P.UserError('無法讀取這個播放清單；私人、需登入或已刪除的清單可能無法使用。')
    entries = data.get('entries') or []
    if not isinstance(entries, list):
        raise P.UserError('播放清單回傳格式不正確。')
    items = []
    for offset, entry in enumerate(entries[:LIMIT]):
        entry = entry if isinstance(entry, dict) else {}
        vid = entry.get('id') or ''
        available = isinstance(vid, str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{11}', vid)) and entry.get('availability') not in (
            'private', 'needs_auth', 'premium_only', 'subscriber_only') and entry.get('title') not in (
            '[Private video]', '[Deleted video]')
        items.append({'video_id': vid, 'title': entry.get('title') or '無法取得影片資訊',
                      'index': entry.get('playlist_index') or start + offset, 'available': available})
    if not items:
        raise P.UserError('這一頁沒有可列出的影片，請確認清單或起始項目。')
    return {'url': url, 'title': data.get('title') or 'YouTube 播放清單', 'items': items,
            'next_start': start + LIMIT if len(entries) > LIMIT else None}


def path(bid):
    if not isinstance(bid, str) or not re.fullmatch(r'[a-f0-9]{16}', bid):
        raise P.UserError('批量編號不正確。')
    return P.LIB / '.youtube-batches' / (bid + '.json')


def load(bid):
    file = path(bid)
    if not file.is_file():
        raise P.UserError('找不到這筆批量匯入。')
    return json.loads(file.read_text('utf-8'))


def save(batch):
    file = path(batch['id'])
    file.parent.mkdir(parents=True, exist_ok=True)
    staged = file.with_suffix('.tmp')
    staged.write_text(json.dumps(batch, ensure_ascii=False), 'utf-8')
    staged.replace(file)


def status(bid, jobs):
    with _lock:
        batch = load(bid)
        changed = False
        for row in batch['items']:
            job = jobs.get(row.get('job', ''))
            if row['status'] in ('queued', 'running') and not job:
                row.update(status='interrupted', error='程式上次已關閉，可按重試繼續。')
                changed = True
            if job:
                row['step'], row['progress'] = job['step'], job['progress']
        if changed:
            save(batch)
        return batch


def recent(jobs):
    folder = P.LIB / '.youtube-batches'
    files = sorted(folder.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:30]
    batches = []
    for file in files:
        try:
            batch = status(file.stem, jobs)
            batches.append({'id': batch['id'], 'created': batch['created'], 'total': len(batch['items'])})
        except (P.UserError, OSError, ValueError, KeyError):
            continue
    return batches


def _update(bid, index, **values):
    with _lock:
        batch = load(bid)
        batch['items'][index].update(values)
        save(batch)


def _enqueue(batch, index, jobs, after=None):
    row = batch['items'][index]
    sid = row.get('song_id')
    if not sid or not (P.LIB / sid).is_dir():
        sid = P.new_youtube_song(row['url'])
        row['song_id'] = sid
        P.update_meta(P.song_dir(sid), title=row['title'], category=batch.get('category'))
    row.update(status='queued', error=None)
    bid, url = batch['id'], row['url']

    def run(report):
        _update(bid, index, status='running')
        try:
            d = P.song_dir(sid)
            steps = P.read_meta(d).get('steps', {})
            if steps.get('import') and ((d / 'original.wav').is_file() or P.stem_path(d, 'mix').is_file()):
                remaining = [step for step in ('separate', 'pitch', 'lyrics') if not steps.get(step)]
                P.process_song(sid, remaining)(report)
            else:
                P.youtube_job(sid, url)(report)
            if P.read_meta(d).get('dl_state') == 'paused':
                _update(bid, index, status='paused', error='YouTube 暫時限制下載，解除限制後可重試。')
                return
            if after:
                after(sid)
            _update(bid, index, status='done')
        except Exception as error:
            _update(bid, index, status='error', error=str(error))
            raise
    row['job'] = jobs.submit('playlist', sid, run, label='playlist:' + bid)


def create(items, category, jobs, after=None):
    if not isinstance(items, list) or not 1 <= len(items) <= LIMIT:
        raise P.UserError('請勾選 1–200 首影片。')
    selected, seen = [], set()
    # Validate the entire request before creating any library entries.
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get('video_id'), str) or
                not re.fullmatch(r'[A-Za-z0-9_-]{11}', item['video_id'])):
            raise P.UserError('播放清單影片編號不正確。')
        vid = item['video_id']
        if vid in seen:
            continue
        seen.add(vid)
        selected.append({'video_id': vid, 'url': 'https://www.youtube.com/watch?v=' + vid,
                         'title': str(item.get('title') or 'YouTube 歌曲')[:200], 'status': 'queued', 'error': None})
    with _lock:
        existing = {song.get('source_url'): song for song in P.list_songs() if song.get('source_url')}
        active = {job['song'] for job in jobs.active() if job['status'] in ('queued', 'running')}
        batch = {'id': uuid.uuid4().hex[:16], 'created': time.time(), 'category': category, 'items': selected}
        save(batch)
        for index, row in enumerate(batch['items']):
            old = existing.get(row['url'])
            if old:
                row['song_id'] = old['id']
                steps = old.get('steps', {})
                if old['id'] in active or all(steps.get(s) for s in ('import', 'separate', 'pitch')):
                    row.update(status='skipped', error='歌曲已存在或正在處理，未重複下載。')
                    continue
            _enqueue(batch, index, jobs, after)
        save(batch)
        return batch


def stop(bid, jobs):
    with _lock:
        batch = status(bid, jobs)
        for row in batch['items']:
            job = jobs.get(row.get('job', ''))
            if row['status'] == 'queued' and job and job['status'] == 'queued':
                jobs.update(job['id'], status='cancelled', step='已停止')
                row['status'] = 'cancelled'
        save(batch)
        return batch


def retry(bid, jobs, after=None):
    with _lock:
        batch = status(bid, jobs)
        active = {job['song'] for job in jobs.active() if job['status'] in ('queued', 'running')}
        for index, row in enumerate(batch['items']):
            if row['status'] in ('error', 'interrupted', 'cancelled', 'paused') and row.get('song_id') not in active:
                _enqueue(batch, index, jobs, after)
        save(batch)
        return batch
