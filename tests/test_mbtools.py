
import os
import types
import unittest
from unittest.mock import patch

os.environ['MBTOOLS_TEST_FAST'] = '1'

from mbtools import utils_mb

class FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

class TestUltraSafe(unittest.TestCase):
    def test_recording_rating_ok(self):
        with patch.object(utils_mb, '_session') as sess:
            sess.get.return_value = FakeResp(200, {"rating": {"value": 4.5, "votes-count": 10}})
            out = utils_mb.mb_get_recording_rating('rec123', 'UA')
            self.assertEqual(out, (4.5, 10))
            # cached second call
            out2 = utils_mb.mb_get_recording_rating('rec123', 'UA')
            self.assertEqual(out2, (4.5, 10))
            self.assertEqual(sess.get.call_count, 1)

    def test_rg_fallback_rating_ok(self):
        # Sequence: recording->releases, release->rg, rg->rating
        calls = []
        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append(url)
            if '/recording/' in url and params.get('inc') == 'releases':
                return FakeResp(200, {"releases": [{"id": "rel1"}]})
            if '/release/' in url and params.get('inc') == 'release-groups':
                return FakeResp(200, {"release-group": {"id": "rg1"}})
            if '/release-group/' in url and params.get('inc') == 'ratings':
                return FakeResp(200, {"rating": {"value": 3.7, "votes-count": 5}})
            return FakeResp(404, {})
        with patch.object(utils_mb, '_session') as sess:
            sess.get.side_effect = fake_get
            rel = utils_mb.mb_get_first_release_id_for_recording('recX', 'UA')
            rgid = utils_mb.mb_get_release_group_id(rel, 'UA')
            rating = utils_mb.mb_get_release_group_rating(rgid, 'UA')
            self.assertEqual(rel, 'rel1')
            self.assertEqual(rgid, 'rg1')
            self.assertEqual(rating, (3.7, 5))

if __name__ == '__main__':
    unittest.main()
