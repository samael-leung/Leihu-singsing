"""Same-origin bridge to the song queue; target is configured by the operator."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from flask import jsonify, request


def register(app):
    @app.route('/api/song-request/selection', methods=['GET', 'POST'])
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
            if not request.is_json:
                return jsonify(error='必須使用 JSON。'), 415
            origin = request.headers.get('Origin')
            if origin and origin != request.host_url.rstrip('/'):
                return jsonify(error='不允許跨來源選歌。'), 403
            body = json.dumps(request.get_json()).encode('utf-8')
        upstream = Request(base + '/api/integrations/leihu/selection', data=body,
                           headers={'Content-Type': 'application/json'}, method=request.method)
        try:
            with urlopen(upstream, timeout=4) as response:
                return jsonify(json.load(response))
        except HTTPError as error:
            if error.code == 409:
                return jsonify(error='正在播放已變更，稍後重試。'), 409
            return jsonify(error=f'點歌系統回應錯誤（{error.code}）。'), 502
        except (URLError, OSError, ValueError):
            return jsonify(error='無法連接點歌系統，請確認伺服器與 SONG_REQUEST_URL。'), 502
