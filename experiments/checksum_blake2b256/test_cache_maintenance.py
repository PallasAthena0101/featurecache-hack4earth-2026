from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import cache_maintenance as maintenance
from featurecache import features,writer_lock

class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.cache=self.root/'cache'
        self.source=self.root/'values.csv';self.source.write_text('value\n1\n2\n3\n4\n5\n')
        self.values,_,self.info=features(self.source,'value',[2,3],self.cache)
        self.key=self.info['key'];self.manifest=self.cache/f'{self.key}.json'
        self.entry=json.loads(self.manifest.read_text())
    def tearDown(self):self.temp.cleanup()
    def call(self):return features(self.source,'value',[2,3],self.cache)
    def orphan(self):
        path=self.cache/f'{self.key}.{"f"*32}.npz';path.write_bytes((self.cache/self.entry['payload']).read_bytes());return path
    def test_preview_is_read_only_and_cleanup_preserves_hits(self):
        orphan=self.orphan();before={path.name:path.read_bytes() for path in self.cache.iterdir()}
        plan=maintenance.prune_cache(self.cache,min_age_seconds=0)
        self.assertFalse(plan['applied']);self.assertEqual(before,{path.name:path.read_bytes() for path in self.cache.iterdir()})
        result=maintenance.prune_cache(self.cache,min_age_seconds=0,apply=True)
        self.assertIn(orphan.name,result['removed']);self.assertFalse(orphan.exists())
        values,_,info=self.call();self.assertFalse(info['computed']);np.testing.assert_equal(values,self.values)
    def test_capacity_evicts_entry_then_recomputes_exactly(self):
        result=maintenance.prune_cache(self.cache,max_bytes=0,min_age_seconds=0,apply=True)
        self.assertTrue(result['target_met']);self.assertEqual(result['bytes_after'],0)
        values,_,info=self.call();self.assertTrue(info['computed']);np.testing.assert_equal(values,self.values)
    def test_busy_writer_preserved_and_target_reported_unmet(self):
        orphan=self.orphan()
        with writer_lock(self.cache,self.key):
            result=maintenance.prune_cache(self.cache,max_bytes=0,min_age_seconds=0,apply=True)
            self.assertFalse(result['target_met']);self.assertIn(self.key,result['skipped_keys'])
            self.assertTrue(orphan.exists());self.assertTrue((self.cache/f'{self.key}.lock').exists())
        self.assertFalse(self.call()[2]['computed'])
    def test_recent_files_protected_even_when_over_budget(self):
        orphan=self.orphan();result=maintenance.prune_cache(self.cache,max_bytes=0,apply=True)
        self.assertFalse(result['target_met']);self.assertEqual(result['removed'],[]);self.assertTrue(orphan.exists())
    def test_external_path_and_unrecognized_files_preserved(self):
        external=self.root/'outside.npz';external.write_bytes(b'untouched')
        unknown=self.cache/'other-tool.npz';unknown.write_bytes(b'not ours')
        self.entry['payload']='../outside.npz';self.manifest.write_text(json.dumps(self.entry))
        maintenance.prune_cache(self.cache,max_bytes=0,min_age_seconds=0,apply=True)
        self.assertEqual(external.read_bytes(),b'untouched');self.assertEqual(unknown.read_bytes(),b'not ours')
    def test_recheck_under_lock_preserves_newly_committed_payload(self):
        orphan=self.orphan()
        @contextmanager
        def commit_before_cleanup(directory,key,timeout=0):
            with writer_lock(directory,key):
                updated=dict(self.entry);updated['payload']=orphan.name
                self.manifest.write_text(json.dumps(updated));yield
        with patch.object(maintenance,'writer_lock',commit_before_cleanup):
            result=maintenance.prune_cache(self.cache,min_age_seconds=0,apply=True)
        self.assertEqual(result['removed'],[]);self.assertTrue(orphan.exists());self.assertFalse(self.call()[2]['computed'])
    def test_symlink_payload_not_followed_or_removed(self):
        external=self.root/'external.npz';external.write_bytes(b'keep')
        link=self.cache/f'{self.key}.{"e"*32}.npz'
        try:link.symlink_to(external)
        except OSError:self.skipTest('Symlink creation unavailable for this account')
        maintenance.prune_cache(self.cache,min_age_seconds=0,apply=True)
        self.assertTrue(link.is_symlink());self.assertEqual(external.read_bytes(),b'keep')
    def test_invalid_limits_do_not_touch_cache(self):
        for kwargs in [{'max_bytes':-1},{'max_bytes':True},{'min_age_seconds':float('nan')},{'min_age_seconds':-1}]:
            with self.assertRaises(ValueError):maintenance.prune_cache(self.cache,**kwargs)
        self.assertFalse(self.call()[2]['computed'])

if __name__=='__main__':unittest.main()
