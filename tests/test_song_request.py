import io
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from flask import Flask
import song_request


class SongRequestTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        song_request.register(app)
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


if __name__ == '__main__':
    unittest.main()
