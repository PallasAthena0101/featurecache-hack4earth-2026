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


if __name__ == '__main__':
    unittest.main()
