from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from featurecache_cli import main


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'sensor.csv'
        self.source.write_text('value\n1\n2\n3\n4\n5\n')
        self.args = [str(self.source), '--column', 'value', '--windows', '2', '3', '--cache', str(self.root / 'cache')]

    def tearDown(self):
        self.temp.cleanup()

    def test_cli_reuses_and_exports_numeric_payload(self):
        output = self.root / 'features.npz'
        first = StringIO()
        with redirect_stdout(first):
            main(self.args + ['--output', str(output)])
        second = StringIO()
        with redirect_stdout(second):
            main(self.args)
        self.assertTrue(json.loads(first.getvalue())['computed'])
        self.assertFalse(json.loads(second.getvalue())['computed'])
        with np.load(output, allow_pickle=False) as result:
            self.assertEqual(result['values'].shape, (5, 7))
            np.testing.assert_equal(result['values'][:, 0], [1, 2, 3, 4, 5])

    def test_cli_refuses_input_overwrite(self):
        original = self.source.read_bytes()
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            main(self.args + ['--output', str(self.source)])
        self.assertEqual(self.source.read_bytes(), original)

    def test_cli_refuses_export_into_cache(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            main(self.args + ['--output', str(self.root / 'cache' / 'entry.npz')])
        self.assertFalse((self.root / 'cache').exists())

    def test_bypass_matches_cached_export_without_cache_artifacts(self):
        cached = self.root / 'cached.npz'
        bypassed = self.root / 'bypassed.npz'
        with redirect_stdout(StringIO()):
            main(self.args + ['--output', str(cached)])
        cache_snapshot = {p.name: p.read_bytes() for p in (self.root / 'cache').iterdir()}
        result = StringIO()
        with redirect_stdout(result):
            main(self.args[:-2] + ['--no-cache', '--output', str(bypassed)])
        report = json.loads(result.getvalue())
        self.assertEqual(report['status'], 'bypassed')
        self.assertTrue(report['computed'])
        with np.load(cached, allow_pickle=False) as a, np.load(bypassed, allow_pickle=False) as b:
            np.testing.assert_equal(a['values'], b['values'])
            np.testing.assert_array_equal(a['columns'], b['columns'])
        self.assertEqual(cache_snapshot, {p.name: p.read_bytes() for p in (self.root / 'cache').iterdir()})
        self.assertEqual({p.name for p in self.root.iterdir()}, {'sensor.csv', 'cache', 'cached.npz', 'bypassed.npz'})

    def test_bypass_rejects_invalid_windows_and_input_overwrite(self):
        for windows in [['1'], ['2', '2']]:
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                main([str(self.source), '--column', 'value', '--windows', *windows, '--no-cache'])
        original = self.source.read_bytes()
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            main(self.args[:-2] + ['--no-cache', '--output', str(self.source)])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'sensor.csv'})


if __name__ == '__main__':
    unittest.main()
