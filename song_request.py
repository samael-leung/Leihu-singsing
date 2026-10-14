"""Same-origin bridge to the song queue; target is configured by the operator."""
import json
import os
import re
import threading
import unicodedata
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from flask import jsonify, request


def register(app, list_songs=lambda: [], links_file=None):
    links_path = Path(links_file) if links_file else Path(__file__).with_name('song-request-links.json')
    lock = threading.Lock()
    converters = None

    def read_links():
        if not links_path.exists():
            return []
        data = json.loads(links_path.read_text('utf-8'))
        if not isinstance(data, list) or any(not isinstance(item, dict) or
                any(not isinstance(item.get(field, ''), str) for field in ('title', 'artist', 'songId')) for item in data):
            raise ValueError('Invalid song links')
        return data

    def key(link):
        return tuple(''.join(c for c in unicodedata.normalize('NFKC', link.get(field, '')).casefold()
                             if c.isalnum()) for field in ('title', 'artist'))

    def reject_write():
        if not request.is_json:
            return jsonify(error='必須使用 JSON。'), 415
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/'):
            return jsonify(error='不允許跨來源選歌。'), 403

    def searchable(songs):
        nonlocal converters
        # OpenCC is already part of the app's requirements; no extra dependency.
        if converters is None:
            try:
                from opencc import OpenCC
                converters = [OpenCC('t2s'), OpenCC('s2t')]
            except ImportError:
                converters = []

        def forms(values):
            return list(dict.fromkeys(text for value in values if value
                                     for text in [value, *(converter.convert(value) for converter in converters)]))

        return [{**song,
                         'searchTitles': forms([song.get('title'), song.get('yt_track'),
                                                (song.get('lyrics_online') or {}).get('track')]),
                         'searchArtists': forms([song.get('artist'), song.get('yt_artist'),
                                                 (song.get('lyrics_online') or {}).get('artist')])}
                        for song in songs]

    @app.get('/api/song-request/library')
    def library():
        return jsonify(searchable(list_songs()))

    @app.route('/api/song-request/links', methods=['GET', 'POST'])
    def links():
        try:
            with lock:
                saved = read_links()
                if request.method == 'GET':
                    return jsonify(saved)
                rejected = reject_write()
                if rejected:
                    return rejected
                body = request.get_json() or {}
                if (not isinstance(body, dict) or not isinstance(body.get('title'), str) or
                        not body['title'].strip() or len(body['title']) > 2000 or
                        not isinstance(body.get('artist', ''), str) or len(body.get('artist', '')) > 500 or
                        not isinstance(body.get('songId'), str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', body['songId'])):
                    return jsonify(error='歌曲對應格式不正確。'), 400
                link = {field: body.get(field, '') for field in ('title', 'artist', 'songId')}
                saved = [item for item in saved if key(item) != key(link)] + [link]
                temporary = links_path.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2), 'utf-8')
                temporary.replace(links_path)
                return jsonify(ok=True)
        except (OSError, ValueError):
            return jsonify(error='無法讀寫歌曲對應紀錄；請檢查資料夾權限與檔案。'), 500

    @app.route('/api/song-request/selection', methods=['GET', 'POST'])
    @app.get('/api/song-request/catalog')
    def selection():
        base = os.environ.get('SONG_REQUEST_URL', 'http://127.0.0.1:3000').rstrip('/')
        try:
            parsed = urlsplit(base)
        except ValueError:
            return jsonify(error='SONG_REQUEST_URL 格式不正確。'), 503
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
                parsed.username or parsed.password or parsed.query or parsed.fragment):
            return jsonify(error='SONG_REQUEST_URL 必須是 HTTP(S) 伺服器網址。'), 503
        body = None
        if request.method == 'POST':
            rejected = reject_write()
            if rejected:
                return rejected
            body = json.dumps(request.get_json()).encode('utf-8')
        target = '/api/songs' if request.path.endswith('/catalog') else '/api/integrations/leihu/selection'
        upstream = Request(base + target, data=body,
                           headers={'Content-Type': 'application/json'}, method=request.method)
        try:
            with urlopen(upstream, timeout=4) as response:
                data = json.load(response)
                return jsonify(searchable(data) if target == '/api/songs' else data)
        except HTTPError as error:
            if error.code == 409:
                return jsonify(error='正在播放已變更，稍後重試。'), 409
            return jsonify(error=f'點歌系統回應錯誤（{error.code}）。'), 502
        except (URLError, OSError, ValueError):
            return jsonify(error='無法連接點歌系統，請確認伺服器與 SONG_REQUEST_URL。'), 502
