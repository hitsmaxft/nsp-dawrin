"""Production package/rewrite pipeline exercised with our own tiny application."""
from pathlib import Path
import tempfile
import unittest
from fixture_app import application, build, executable, validate
from content import ContentError, ContentSet


class FixtureAppTests(unittest.TestCase):
    def test_fixture_is_deterministic_and_has_real_executables(self):
        self.assertEqual(application(), application())
        self.assertEqual(executable()[:4], b'NSO0')
        self.assertNotEqual(executable(), executable(expected=1))
        with tempfile.TemporaryDirectory() as directory:
            manifest = build(directory)
            self.assertLess(sum(item['bytes'] for item in manifest['files'].values()), 100_000)
            root = Path(directory)
            with self.assertRaisesRegex(ContentError, 'newer'):
                ContentSet([root / 'base.nsp', root / 'addon.nsp'], root / 'fixture.keys')
            damaged = root / 'truncated.nsp'
            damaged.write_bytes(application()[:-1])
            with self.assertRaises(ContentError):
                ContentSet([damaged], root / 'fixture.keys')

    def test_package_update_dlc_and_production_rewriter(self):
        with tempfile.TemporaryDirectory() as directory:
            result = validate(directory)
            self.assertEqual(result, dict(package='passed', update='passed', dlc='passed',
                                          rewrite='passed', native_execution='not_run'))


if __name__ == '__main__':
    unittest.main()
