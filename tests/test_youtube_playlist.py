"""Playlist listing, queue isolation, restart recovery and HTTP contracts."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

import app as web
import pipeline as P
import youtube_playlist as Y

VIDEOS = [{'video_id': 'abcdefghijk', 'title': '第一首'}, {'video_id': 'lmnopqrstuv', 'title': '第二首'}]


class Jobs:
    def __init__(self):
        self.state, self.workers = {}, {}
    def submit(self, kind, sid, fn, label=''):
        jid = f'job{len(self.state)}'
        self.state[jid] = {'id': jid, 'kind': kind, 'song': sid, 'status': 'queued', 'step': '排隊中', 'progress': 0}
        self.workers[jid] = fn
        return jid
    def get(self, jid):
        return self.state.get(jid)
    def update(self, jid, **values):
        self.state[jid].update(values)
    def active(self):
        return list(self.state.values())
    def run(self, jid):
        self.state[jid]['status'] = 'running'
        try:
            self.workers[jid](lambda *args: None)
            self.state[jid]['status'] = 'done'
        except Exception:
            self.state[jid]['status'] = 'error'
            raise


class PlaylistTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        change = patch.object(P, 'LIB', self.root / 'library')
        change.start(); self.addCleanup(change.stop)
        self.jobs = Jobs()
        self.client = web.app.test_client()

    def test_only_youtube_playlist_urls_are_accepted(self):
        self.assertEqual(Y.clean_url('https://youtu.be/abcdefghijk?list=PL123456'), 'https://www.youtube.com/playlist?list=PL123456')
        for url in ('https://evil.com/?list=PL123456', 'https://youtube.com/watch?v=abcdefghijk',
                    'https://user:password@youtube.com/playlist?list=PL123456', 'https://youtube.com:bad/playlist?list=PL123456'):
            with self.subTest(url=url), self.assertRaises(P.UserError):
                Y.clean_url(url)

    def test_preview_does_not_download_audio_and_marks_private_entries(self):
        output = {'title': '清單', 'entries': [{'id': 'abcdefghijk', 'title': '歌曲'},
                    {'id': 'lmnopqrstuv', 'title': '[Private video]'}, None]}
        with patch.object(Y.subprocess, 'run', return_value=Mock(returncode=0, stdout=json.dumps(output))) as run:
            result = Y.preview('https://youtube.com/playlist?list=PL123456')
        args = run.call_args.args[0]
        self.assertIn('--flat-playlist', args)
        self.assertIn('--skip-download', args)
        self.assertTrue(result['items'][0]['available'])
        self.assertFalse(result['items'][1]['available'])
        self.assertFalse(result['items'][2]['available'])

    def test_partial_playlist_result_keeps_available_entries(self):
        with patch.object(Y.subprocess, 'run', return_value=Mock(returncode=1, stdout=json.dumps({'entries': [{'id': 'abcdefghijk', 'title': '可用影片'}]}))):
            self.assertTrue(Y.preview('https://youtube.com/playlist?list=PL123456')['items'][0]['available'])

    def test_large_playlist_is_paged_with_explicit_next_start(self):
        entries = [{'id': 'abcdefghijk', 'title': '歌曲'}] * 201
        with patch.object(Y.subprocess, 'run', return_value=Mock(returncode=0, stdout=json.dumps({'entries': entries}))):
            result = Y.preview('https://youtube.com/playlist?list=PL123456', start=201)
        self.assertEqual(len(result['items']), 200)
        self.assertEqual(result['next_start'], 401)
        self.assertEqual(result['items'][0]['index'], 201)

    def test_whole_request_is_validated_before_creating_songs(self):
        for items in ([VIDEOS[0], {'video_id': '../../bad'}], [{'video_id': 123}], [], VIDEOS * 101):
            with self.subTest(items=items[:2]), self.assertRaises(P.UserError):
                Y.create(items, None, self.jobs)
        self.assertFalse(P.LIB.exists())

    def test_duplicate_selection_creates_one_song_and_preserves_category(self):
        batch = Y.create([VIDEOS[0], VIDEOS[0]], '中文', self.jobs)
        self.assertEqual(len(batch['items']), 1)
        sid = batch['items'][0]['song_id']
        self.assertEqual(P.read_meta(P.song_dir(sid))['category'], '中文')
        self.assertEqual(len(self.jobs.workers), 1)

    def test_finished_or_active_existing_songs_are_skipped(self):
        batch = Y.create(VIDEOS, None, self.jobs)
        second = Y.create(VIDEOS, None, self.jobs)
        self.assertTrue(all(row['status'] == 'skipped' for row in second['items']))
        self.assertEqual(len(self.jobs.workers), 2)
        for row in batch['items']:
            self.jobs.state[row['job']]['status'] = 'done'
            P.update_meta(P.song_dir(row['song_id']), steps={'import': True, 'separate': True, 'pitch': True})
        third = Y.create(VIDEOS, None, self.jobs)
        self.assertTrue(all(row['status'] == 'skipped' for row in third['items']))

    def test_one_failure_does_not_prevent_next_item_and_retry_reuses_song(self):
        batch = Y.create(VIDEOS, None, self.jobs)
        with patch.object(P, 'youtube_job', side_effect=lambda sid, url: (lambda report: (_ for _ in ()).throw(P.UserError('private video'))) if url.endswith('abcdefghijk') else (lambda report: None)):
            with self.assertRaises(P.UserError):
                self.jobs.run(batch['items'][0]['job'])
            self.jobs.run(batch['items'][1]['job'])
        state = Y.status(batch['id'], self.jobs)
        self.assertEqual([row['status'] for row in state['items']], ['error', 'done'])
        retried = Y.retry(batch['id'], self.jobs)
        self.assertEqual(retried['items'][0]['song_id'], batch['items'][0]['song_id'])
        self.assertEqual(len(self.jobs.workers), 3)
        Y.retry(batch['id'], self.jobs)
        self.assertEqual(len(self.jobs.workers), 3)

    def test_stop_only_cancels_queued_items(self):
        batch = Y.create(VIDEOS, None, self.jobs)
        self.jobs.state[batch['items'][0]['job']]['status'] = 'running'
        Y._update(batch['id'], 0, status='running')
        result = Y.stop(batch['id'], self.jobs)
        self.assertEqual([row['status'] for row in result['items']], ['running', 'cancelled'])
        self.assertEqual(self.jobs.state[batch['items'][0]['job']]['status'], 'running')

    def test_restart_marks_lost_jobs_interrupted_and_retry_resumes_imported_audio(self):
        batch = Y.create([VIDEOS[0]], None, self.jobs)
        sid = batch['items'][0]['song_id']
        d = P.song_dir(sid); (d / 'original.wav').touch()
        P.update_meta(d, steps={'import': True, 'separate': False, 'pitch': False, 'lyrics': True})
        restarted = Jobs()
        self.assertEqual(Y.status(batch['id'], restarted)['items'][0]['status'], 'interrupted')
        retried = Y.retry(batch['id'], restarted)
        with patch.object(P, 'youtube_job') as download, patch.object(P, 'process_song', return_value=lambda report: None) as process:
            restarted.run(retried['items'][0]['job'])
        download.assert_not_called()
        self.assertEqual(process.call_args.args, (sid, ['separate', 'pitch']))

    def test_http_endpoints_and_single_video_are_independent(self):
        with patch.object(web.YP, 'preview', return_value={'items': VIDEOS}) as preview:
            response = self.client.post('/api/youtube/playlist/preview', json={'url': 'playlist', 'start': 1})
        self.assertEqual(response.status_code, 200)
        preview.assert_called_once_with('playlist', 1)
        with patch.object(web, 'jobs', self.jobs), patch.object(P, 'load_categories', return_value=['中文']):
            response = self.client.post('/api/youtube/playlist/import', json={'items': VIDEOS, 'category': '中文'})
            bid = response.json['id']
            self.assertEqual(self.client.get('/api/youtube/playlist/batches').json[0]['id'], bid)
            self.assertEqual(self.client.get('/api/youtube/playlist/batches/' + bid).status_code, 200)
            self.assertEqual(self.client.post('/api/youtube/playlist/batches/' + bid + '/stop', json={}).status_code, 200)
        with patch.object(web.jobs, 'submit', return_value='single'), patch.object(web.jobs, 'active', return_value=[]):
            self.assertEqual(self.client.post('/api/youtube', json={'url': 'https://youtu.be/zyxwvutsrqp'}).json['job'], 'single')

    def test_verbose_downloader_stderr_does_not_deadlock_download_queue(self):
        sid = P.new_youtube_song('https://www.youtube.com/watch?v=abcdefghijk')
        d = P.song_dir(sid)
        program = "import sys;from pathlib import Path;print('TITLE 測試歌曲',flush=True);sys.stderr.write('warning'*30000+'\\n');Path(sys.argv[1]).touch()"
        native = subprocess.Popen
        def spawn(args, **kwargs):
            self.assertIn('--no-playlist', args)
            self.assertEqual(kwargs['stderr'], subprocess.STDOUT)
            return native([sys.executable, '-c', program, str(d / 'original.wav')], **kwargs)
        with patch.object(P, 'ffmpeg_path', return_value='/usr/bin/ffmpeg'), patch.object(subprocess, 'Popen', side_effect=spawn):
            P.step_youtube(d, 'https://www.youtube.com/watch?v=abcdefghijk', lambda *args: None)
        self.assertEqual(P.read_meta(d)['title'], '測試歌曲')


if __name__ == '__main__':
    unittest.main()
