import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from featurecache import features


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'sensor.csv';self.source.write_text('value\n1\n2\n3\n4\n5\n')
        self.cache=self.root/'cache'

    def tearDown(self):self.temp.cleanup()

    def call(self,windows=(2,3)):
        return features(self.source,'value',windows,self.cache)

    def test_reuse_and_parameter_invalidation(self):
        a,cols,first=self.call();b,_,second=self.call()
        np.testing.assert_equal(a,b);self.assertTrue(first['computed']);self.assertFalse(second['computed'])
        _,_,third=self.call((2,4));self.assertNotEqual(first['key'],third['key'])

    def test_changed_input_invalidates(self):
        a,_,first=self.call();self.source.write_text('value\n1\n2\n3\n4\n99\n')
        b,_,second=self.call();self.assertNotEqual(first['key'],second['key']);self.assertNotEqual(a[-1,0],b[-1,0])

    def test_corruption_recomputes(self):
        a,_,first=self.call();manifest=json.loads((self.cache/f"{first['key']}.json").read_text())
        (self.cache/manifest['payload']).write_bytes(b'corrupt')
        b,_,second=self.call();np.testing.assert_equal(a,b);self.assertTrue(second['computed']);self.assertEqual(second['status'],'invalid')

    def test_interrupted_manifest_does_not_become_hit(self):
        _,_,first=self.call();(self.cache/f"{first['key']}.json").write_text('{')
        _,_,second=self.call();self.assertTrue(second['computed'])

    def test_manifest_path_traversal_rejected(self):
        _,_,first=self.call();path=self.cache/f"{first['key']}.json";entry=json.loads(path.read_text())
        entry['payload']='../outside.npz';path.write_text(json.dumps(entry))
        _,_,second=self.call();self.assertTrue(second['computed'])

    def test_concurrent_writers_compute_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results=list(executor.map(lambda _:self.call(),range(4)))
        self.assertEqual(sum(r[2]['computed'] for r in results),1)
        for r in results:np.testing.assert_equal(results[0][0],r[0])

    def test_future_values_do_not_change_past_features(self):
        a,_,_=self.call();self.source.write_text('value\n1\n2\n3\n4\n999\n')
        b,_,_=self.call();np.testing.assert_equal(a[:-1],b[:-1])


if __name__=='__main__':unittest.main()
