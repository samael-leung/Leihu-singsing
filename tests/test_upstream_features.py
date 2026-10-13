"""Regression checks for imported melody and live lyric features."""
import unittest
from unittest.mock import patch

import numpy as np
import torch
import torchcrepe
import app as web
import pipeline as P


class MelodyTests(unittest.TestCase):
    def test_short_gaps_bridge_without_filling_edges_or_real_note_changes(self):
        source=np.array([np.nan,57,np.nan,np.nan,57.5,np.nan],dtype=np.float32)
        out=P.bridge_gaps(source)
        self.assertTrue(np.isnan(out[0]) and np.isnan(out[-1]))
        self.assertTrue(np.isfinite(out[1:-1]).all())
        self.assertTrue(np.isnan(P.bridge_gaps(np.array([57,np.nan,60],dtype=np.float32))[1]))
        self.assertTrue(np.isnan(P.bridge_gaps(np.array([57]+[np.nan]*13+[57],dtype=np.float32))[1:-1]).all())

    def test_harmonics_distinguish_real_low_note_from_high_octave(self):
        t=np.arange(P.PITCH_SR)/P.PITCH_SR
        low=(np.sin(2*np.pi*220*t)+0.25*np.sin(2*np.pi*660*t)).astype(np.float32)
        high=(np.sin(2*np.pi*440*t)+0.25*np.sin(2*np.pi*880*t)).astype(np.float32)
        self.assertGreater(P.octave_low_score(low,0,40,57),0.35)
        self.assertLess(P.octave_low_score(high,0,40,57),0.12)

    def test_octave_correction_preserves_a_genuine_high_note(self):
        midi=np.array([57]*60+[np.nan]*5+[69]*20+[np.nan]*5+[57]*60,dtype=np.float32)
        t=np.arange(len(midi)*P.HOP)/P.PITCH_SR
        y=np.sin(2*np.pi*220*t).astype(np.float32)
        corrected=P.fix_octaves(midi,y16=y)
        self.assertTrue(np.all(corrected[65:85]==57))
        y[65*P.HOP:85*P.HOP]=np.sin(2*np.pi*440*t[65*P.HOP:85*P.HOP])
        kept=P.fix_octaves(midi,y16=y)
        self.assertTrue(np.all(kept[65:85]==69))

    def test_confidence_extension_does_not_wrap_end_to_beginning(self):
        n=300
        f=torch.full((1,n),220.0)
        p=torch.tensor([[0.3]*20+[0.1]*250+[0.9]*30])
        with patch.object(torchcrepe,'predict',return_value=(f,p)), patch.object(torchcrepe.filter,'median',side_effect=lambda data,width:data), patch('librosa.feature.rms',return_value=np.ones((1,n),dtype=np.float32)):
            out=P.track_pitch(np.ones(n*P.HOP,dtype=np.float32))
        self.assertTrue(np.isnan(out[:20]).all())
        self.assertTrue(np.isfinite(out[-20:]).all())

    def test_strict_recording_pitch_does_not_apply_song_octave_correction(self):
        n=100
        levels=np.array([[0.02]*20+[0.6]*80],dtype=np.float32)
        with patch.object(torchcrepe,'predict',return_value=(torch.full((1,n),220.0),torch.ones((1,n)))), patch.object(torchcrepe.filter,'median',side_effect=lambda data,width:data), patch('librosa.feature.rms',return_value=levels), patch.object(P,'fix_octaves',side_effect=AssertionError('recordings must retain strict scoring')):
            out=P.track_pitch(np.ones(n*P.HOP,dtype=np.float32),strict=True)
        self.assertGreater(np.isfinite(out).sum(),50)


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.client=web.app.test_client()
        with web._ov_lock:
            self.previous=dict(web.OVERLAY)
            web.OVERLAY.update(sid=None,title='',t=0.0,playing=False,rate=1.0,color=True,lines=[],ver=0,at=0.0)
        self.addCleanup(self.restore)

    def restore(self):
        with web._ov_lock:
            web.OVERLAY.clear(); web.OVERLAY.update(self.previous)

    def test_overlay_page_and_versioned_lyrics_are_served(self):
        page=self.client.get('/overlay')
        self.assertEqual(page.status_code,200)
        self.assertIn('直播歌詞',page.get_data(as_text=True))
        page.close()
        with patch.object(web.time,'time',return_value=100):
            self.assertEqual(self.client.post('/api/overlay',json={'sid':'abcdef','t':12,'rate':1.5,'playing':True,'lines':[{'t':1,'text':'測試歌詞'}]}).status_code,200)
        with patch.object(web.time,'time',return_value=102):
            result=self.client.get('/api/overlay').json
            self.assertEqual(result['t'],15)
            self.assertEqual(result['lines'][0]['text'],'測試歌詞')
            cached=self.client.get('/api/overlay',query_string={'ver':result['ver']}).json
            self.assertNotIn('lines',cached)

    def test_switching_song_or_leaving_practice_clears_previous_lyrics(self):
        self.client.post('/api/overlay',json={'sid':'abcdef','lines':[{'t':0,'text':'舊歌詞'}]})
        self.client.post('/api/overlay',json={'sid':'ghijkl','playing':False,'t':5})
        self.assertEqual(self.client.get('/api/overlay').json['lines'],[])
        with patch.object(web.time,'time',return_value=500):
            self.assertEqual(self.client.get('/api/overlay').json['t'],5)
        self.client.post('/api/overlay',json={'sid':None,'playing':False})
        self.assertIsNone(self.client.get('/api/overlay').json['sid'])

    def test_overlay_preview_rejects_unexpected_browser_query(self):
        with patch.object(web.webbrowser,'open') as browser:
            bad=self.client.post('/api/open-overlay',json={'query':'https://example.com'})
            self.assertEqual(bad.status_code,400)
            browser.assert_not_called()
            good=self.client.post('/api/open-overlay',json={'query':'lines=2&size=56'})
            self.assertEqual(good.status_code,200)
            self.assertIn('/overlay?lines=2&size=56',browser.call_args.args[0])


if __name__=='__main__': unittest.main()
