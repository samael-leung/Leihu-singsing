import io
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from flask import Flask
import song_request


class SongRequestTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.links = Path(folder.name) / 'links.json'
        app = Flask(__name__)
        song_request.register(app, links_file=self.links,
                              list_songs=lambda: [{'id': 'songaa', 'title': '张韶涵 - 亲爱的那不是爱情',
                                                   'yt_artist': '张韶涵', 'yt_track': '亲爱的那不是爱情'}])
        self.client = app.test_client()
        self.env = patch.dict(os.environ, {'SONG_REQUEST_URL': 'http://127.0.0.1:3000'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_read_and_write_forwarding(self):
        with patch.object(song_request, 'urlopen', return_value=io.BytesIO(b'{"revision":"1","nowPlaying":null}')) as send:
            response = self.client.get('/api/song-request/selection')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['revision'], '1')
            self.assertEqual(send.call_args.args[0].full_url,
                             'http://127.0.0.1:3000/api/integrations/leihu/selection')
        body = {'song': {'id': 'a', 'title': 'A'}, 'expectedRevision': '1'}
        with patch.object(song_request, 'urlopen', return_value=io.BytesIO(b'{"revision":"2"}')) as send:
            self.assertEqual(self.client.post('/api/song-request/selection', json=body).status_code, 200)
            import json
            self.assertEqual(json.loads(send.call_args.args[0].data), body)

    def test_connection_failure_conflict_and_validation(self):
        for error, status in [(URLError('offline'), 502),
                              (HTTPError('http://local', 409, 'conflict', {}, None), 409)]:
            with patch.object(song_request, 'urlopen', side_effect=error):
                self.assertEqual(self.client.get('/api/song-request/selection').status_code, status)
        self.assertEqual(self.client.post('/api/song-request/selection', data='{}').status_code, 415)
        self.assertEqual(self.client.post('/api/song-request/selection', json={},
                                         headers={'Origin': 'https://other.example'}).status_code, 403)
        with patch.dict(os.environ, {'SONG_REQUEST_URL': 'file:///etc/passwd'}):
            self.assertEqual(self.client.get('/api/song-request/selection').status_code, 503)

    def test_links_survive_recreation_and_overwrite_only_the_same_song_identity(self):
        first = {'title': '下一個天亮', 'artist': '郭靜', 'songId': 'songaa'}
        self.assertEqual(self.client.post('/api/song-request/links', json=first).status_code, 200)
        replacement = dict(first, songId='songbb')
        self.assertEqual(self.client.post('/api/song-request/links', json=replacement).status_code, 200)
        other = dict(first, artist='另一位歌手', songId='songcc')
        self.assertEqual(self.client.post('/api/song-request/links', json=other).status_code, 200)
        app = Flask('restarted')
        song_request.register(app, links_file=self.links)
        self.assertEqual(app.test_client().get('/api/song-request/links').json, [replacement, other])
        self.assertFalse(self.links.with_suffix('.json.tmp').exists())

    def test_links_reject_invalid_and_cross_origin_writes_and_preserve_corrupt_files(self):
        self.assertEqual(self.client.post('/api/song-request/links', json={'title': ''}).status_code, 400)
        self.assertEqual(self.client.post('/api/song-request/links', json={},
                                         headers={'Origin': 'https://other.example'}).status_code, 403)
        self.links.write_text('not json')
        self.assertEqual(self.client.get('/api/song-request/links').status_code, 500)
        self.assertEqual(self.links.read_text(), 'not json')

    def test_library_adds_title_and_artist_search_forms_and_catalog_uses_existing_sheet(self):
        songs = self.client.get('/api/song-request/library').json
        self.assertEqual(songs[0]['title'], '张韶涵 - 亲爱的那不是爱情')
        self.assertIn('亲爱的那不是爱情', songs[0]['searchTitles'])
        self.assertIn('张韶涵', songs[0]['searchArtists'])
        self.assertIn('親愛的那不是愛情', songs[0]['searchTitles'])
        with patch.object(song_request, 'urlopen', return_value=io.BytesIO(b'[]')) as send:
            self.assertEqual(self.client.get('/api/song-request/catalog').status_code, 200)
            self.assertEqual(send.call_args.args[0].full_url, 'http://127.0.0.1:3000/api/songs')
        import json
        catalog = [{'title': '親愛的那不是愛情', 'artist': '張韶涵'}]
        with patch.object(song_request, 'urlopen', return_value=io.BytesIO(json.dumps(catalog).encode())):
            result = self.client.get('/api/song-request/catalog').json
            self.assertEqual(result[0]['title'], catalog[0]['title'])
            self.assertIn('亲爱的那不是爱情', result[0]['searchTitles'])


if __name__ == '__main__':
    unittest.main()
