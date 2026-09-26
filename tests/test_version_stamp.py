"""Tests for the build version stamp and the manifest it publishes.

The failure these guard against is subtle and bad: the build stamps one
version into the program and a different one into the manifest, the app
compares a version against itself, and either every reader is told there is
an update that does not exist, or a real update is never offered. So the two
are checked against each other here, not just on their own.
"""

import hashlib
import importlib
import json
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import stamp_version  # noqa: E402
from accessible_ide import updater  # noqa: E402


class StampTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.init = pathlib.Path(self.tmp.name) / "__init__.py"
        self.init.write_text(
            '"""Docstring."""\n'
            '__version__ = "0.0.1"\n'
            '__author__ = "Someone"\n'
            '\n'
            'def create_app():\n'
            '    return None\n',
            encoding='utf-8',
        )

    def test_the_version_is_written_in(self):
        stamp_version.stamp_version(self.init, "0.2.2-beta.dev.181")
        self.assertIn('__version__ = "0.2.2-beta.dev.181"', self.init.read_text(encoding="utf-8"))

    def test_nothing_else_in_the_file_is_touched(self):
        before = self.init.read_text(encoding="utf-8")
        stamp_version.stamp_version(self.init, "1.2.3")
        after = self.init.read_text(encoding="utf-8")
        self.assertEqual(before.replace('"0.0.1"', '"1.2.3"'), after)

    def test_a_leading_v_is_dropped(self):
        stamp_version.stamp_version(self.init, "v1.2.3")
        self.assertIn('__version__ = "1.2.3"', self.init.read_text(encoding="utf-8"))

    def test_stamping_twice_replaces_rather_than_appends(self):
        stamp_version.stamp_version(self.init, "1.0.0")
        stamp_version.stamp_version(self.init, "1.0.1")
        text = self.init.read_text(encoding="utf-8")
        self.assertEqual(text.count("__version__"), 1)
        self.assertIn('"1.0.1"', text)

    def test_something_that_is_not_a_version_is_refused(self):
        for bad in ("latest", "", "1.2.3; rm -rf /", "../../etc", "one.two"):
            with self.subTest(version=bad):
                with self.assertRaises(stamp_version.StampError):
                    stamp_version.stamp_version(self.init, bad)

    def test_a_file_with_no_version_line_is_refused(self):
        # Silently shipping the old version is worse than failing the build.
        self.init.write_text("x = 1\n", encoding="utf-8")
        with self.assertRaises(stamp_version.StampError):
            stamp_version.stamp_version(self.init, "1.0.0")


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exe = pathlib.Path(self.tmp.name) / "AccessibleIDE.exe"
        self.exe.write_bytes(b"MZ" + b"pretend this is a program" * 100)
        self.url = f"{updater.RELEASES_BASE}/download/latest/{updater.ASSET_NAME}"

    def test_the_manifest_describes_the_file_that_was_built(self):
        described = stamp_version.build_manifest(
            "0.2.2-beta.dev.181", self.exe, self.url, "Notes.", prerelease=True)
        self.assertEqual(described["size"], self.exe.stat().st_size)
        self.assertEqual(
            described["sha256"],
            hashlib.sha256(self.exe.read_bytes()).hexdigest(),
        )
        self.assertEqual(described["version"], "0.2.2-beta.dev.181")
        self.assertEqual(described["url"], self.url)
        self.assertTrue(described["prerelease"])

    def test_the_manifest_is_accepted_by_the_app_that_reads_it(self):
        # The point of the whole exercise: what CI writes has to pass the
        # checks in the app, or every build looks like it needs replacing.
        described = stamp_version.build_manifest(
            "0.2.2-beta.dev.181", self.exe, self.url, "Notes.", prerelease=True)
        raw = json.dumps(described).encode()

        original = updater._open_url
        updater._open_url = lambda url, timeout, accept: _Body(raw)
        try:
            manifest = updater.fetch_manifest()
        finally:
            updater._open_url = original
        self.assertEqual(manifest["version"], "0.2.2-beta.dev.181")
        self.assertTrue(updater.is_newer(manifest["version"], "0.2.2-beta"))

    def test_an_insecure_download_address_is_refused(self):
        with self.assertRaises(stamp_version.StampError):
            stamp_version.build_manifest(
                "1.0.0", self.exe,
                "http://github.com/a/b/releases/download/v1/x.exe", "", True)

    def test_the_addresses_the_workflows_write_are_ones_the_app_allows(self):
        # The two workflows build their addresses differently: the moving
        # build names the literal tag "latest", a tagged release names its
        # own tag. Both have to clear the app's allowlist, or the release it
        # just published cannot be installed from.
        base = f"https://github.com/hothilux-21/accessible-coding/releases/download"
        for url in (f"{base}/latest/{updater.ASSET_NAME}",
                    f"{base}/v0.2.3-beta/{updater.ASSET_NAME}"):
            with self.subTest(url=url):
                self.assertEqual(updater._allowed_asset_url(url), url)

    def test_an_address_on_another_site_is_still_refused(self):
        with self.assertRaises(updater.UpdateError):
            updater._allowed_asset_url(
                "https://example.com/releases/download/v1/AccessibleIDE.exe")

    def test_a_stamped_build_offers_itself_as_an_update(self):
        # The round trip: stamp the real package, read the version back the
        # way the app does, and confirm the manifest is newer.
        #
        # Reload rather than deleting the module from sys.modules. Deleting
        # it makes the next "from accessible_ide import updater" build a
        # second, different updater module, and any test holding a patch on
        # the first one is then quietly patching nothing.
        init = REPO_ROOT / "src" / "accessible_ide" / "__init__.py"
        original = init.read_text(encoding="utf-8")
        import accessible_ide

        def put_back():
            init.write_text(original, encoding="utf-8")
            importlib.reload(accessible_ide)

        self.addCleanup(put_back)

        stamp_version.stamp_version(init, "999.0.0")
        importlib.reload(accessible_ide)
        stamped = accessible_ide.__version__
        self.assertEqual(stamped, "999.0.0")

        described = stamp_version.build_manifest(
            "999.0.1", self.exe, self.url, "", True)
        self.assertTrue(updater.is_newer(described["version"], stamped))
        # And the version already installed is not offered to itself.
        self.assertFalse(updater.is_newer(stamped, stamped))


class _Body:
    """A tiny stand-in for a downloaded file."""

    def __init__(self, data):
        self.data = data
        self.headers = {}
        self._sent = 0

    def read(self, size=-1):
        if self._sent >= len(self.data):
            return b""
        piece = self.data[self._sent:self._sent + size] if size and size > 0 else self.data[self._sent:]
        self._sent += len(piece)
        return piece

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


if __name__ == "__main__":
    unittest.main()
