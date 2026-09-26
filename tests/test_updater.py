"""Tests for the update check.

The two things that could genuinely hurt a reader are both tested here: a
comparison that offers a downgrade, and a manifest that points the download
somewhere it should not. Everything that touches the network is faked, so
these run offline and in a second.
"""

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from accessible_ide import updater  # noqa: E402


class VersionOrderingTests(unittest.TestCase):
    def test_ordinary_numbers_compare_as_expected(self):
        self.assertTrue(updater.is_newer("0.2.3", "0.2.2"))
        self.assertTrue(updater.is_newer("0.3.0", "0.2.9"))
        self.assertTrue(updater.is_newer("1.0.0", "0.9.9"))
        self.assertFalse(updater.is_newer("0.2.2", "0.2.2"))
        self.assertFalse(updater.is_newer("0.2.1", "0.2.2"))

    def test_missing_parts_are_treated_as_zero(self):
        # A tag written "0.3" must not look older than the released "0.2.9".
        self.assertTrue(updater.is_newer("0.3", "0.2.9"))
        self.assertTrue(updater.is_newer("1", "0.9.9"))
        self.assertFalse(updater.is_newer("0.2", "0.2.0"))

    def test_a_stable_build_is_newer_than_its_own_pre_releases(self):
        self.assertTrue(updater.is_newer("0.3.0", "0.3.0-dev.12"))
        self.assertTrue(updater.is_newer("0.3.0", "0.3.0-beta"))
        self.assertFalse(updater.is_newer("0.3.0-dev.12", "0.3.0"))

    def test_development_builds_follow_the_run_number(self):
        # This is what makes the ever-increasing CI run number a usable
        # ordering: a later build of the same version is a newer build.
        self.assertTrue(updater.is_newer("0.3.0-dev.121", "0.3.0-dev.120"))
        self.assertFalse(updater.is_newer("0.3.0-dev.119", "0.3.0-dev.120"))

    def test_a_leading_v_is_accepted(self):
        self.assertTrue(updater.is_newer("v0.2.3", "0.2.2"))
        self.assertFalse(updater.is_newer("v0.2.2", "0.2.2"))

    def test_surrounding_whitespace_is_accepted(self):
        self.assertTrue(updater.is_newer("  0.2.3\n", "0.2.2"))

    def test_nonsense_never_counts_as_newer(self):
        # Guessing here means offering someone a downgrade, so anything that
        # cannot be read is treated as "not newer" rather than raising.
        for bad in ("", "latest", "not-a-version", "0.2.2 and then some", None, 3):
            with self.subTest(version=bad):
                self.assertFalse(updater.is_newer(bad, "0.2.2"))

    def test_parse_version_reports_what_it_cannot_read(self):
        with self.assertRaises(updater.UpdateError):
            updater.parse_version("latest")


class DownloadAddressTests(unittest.TestCase):
    def test_a_release_asset_of_this_project_is_allowed(self):
        url = f"{updater.RELEASES_BASE}/download/v1.0/AccessibleIDE.exe"
        self.assertEqual(updater._allowed_asset_url(url), url)

    def test_somewhere_else_is_refused(self):
        # The manifest is fetched from the internet and names the file to
        # run. Anything not on this project's releases is refused outright.
        for url in (
            "https://evil.example.com/AccessibleIDE.exe",
            "https://github.com/someone-else/project/releases/download/v1/a.exe",
            f"{updater.RELEASES_BASE}/../../evil.exe",
            "http://github.com/hothilux-21/accessible-coding/releases/download/v1/a.exe",
            "https://github.com/hothilux-21/accessible-coding/releases/latest",
            "",
            None,
        ):
            with self.subTest(url=url):
                with self.assertRaises(updater.UpdateError):
                    updater._allowed_asset_url(url)

    def test_a_path_that_climbs_out_is_refused(self):
        url = f"{updater.RELEASES_BASE}/download/../../../../evil.exe"
        with self.assertRaises(updater.UpdateError):
            updater._allowed_asset_url(url)


def swapped(test, obj, name, value):
    """Replace obj.name for one test, then put the real one back.

    The original has to be captured *before* the replacement. Registering
    the cleanup with the value read after replacing it restores the fake
    instead, and because unittest orders classes by name rather than by
    where they were written, one leaking fake can quietly break a whole
    class of tests for a reason that has nothing to do with them.
    """
    original = getattr(obj, name)
    setattr(obj, name, value)
    test.addCleanup(setattr, obj, name, original)
    return original


class FakeResponse:
    """Just enough of a file-like object for the download path."""

    def __init__(self, body=b"", headers=None, chunks=1):
        self.body = body
        self.headers = headers or {}
        self._chunk_size = max(1, len(body) // chunks) if body else 1
        self._sent = 0

    def read(self, size=-1):
        if self._sent >= len(self.body):
            return b""
        if size is None or size < 0:
            size = len(self.body) - self._sent
        piece = self.body[self._sent:self._sent + min(size, self._chunk_size)]
        self._sent += len(piece)
        return piece

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Point the cache and the download folder inside the temp directory
        # so a test never writes to the machine it runs on.
        swapped(self, updater, "cache_path",
                lambda: pathlib.Path(self.tmp.name) / "check.json")
        swapped(self, updater, "update_dir",
                lambda: pathlib.Path(self.tmp.name) / "updates")

    def serve(self, body, headers=None, chunks=1):
        swapped(self, updater, "_open_url",
                lambda url, timeout, accept: FakeResponse(body, headers, chunks))

    def good_manifest(self, **overrides):
        manifest = {
            "version": "9.9.9",
            "url": f"{updater.RELEASES_BASE}/download/v9.9.9/AccessibleIDE.exe",
            "sha256": "a" * 64,
            "size": 3,
            "notes": "A test build.",
        }
        manifest.update(overrides)
        return manifest

    def test_a_good_manifest_is_accepted(self):
        self.serve(json.dumps(self.good_manifest()).encode())
        manifest = updater.fetch_manifest()
        self.assertEqual(manifest["version"], "9.9.9")
        self.assertIn("sha256", manifest)

    def test_every_required_field_is_required(self):
        for field in ("version", "url", "sha256", "size"):
            with self.subTest(missing=field):
                broken = self.good_manifest()
                del broken[field]
                self.serve(json.dumps(broken).encode())
                with self.assertRaises(updater.UpdateError):
                    updater.fetch_manifest()

    def test_a_manifest_pointing_elsewhere_is_refused(self):
        self.serve(json.dumps(self.good_manifest(
            url="https://evil.example.com/a.exe")).encode())
        with self.assertRaises(updater.UpdateError):
            updater.fetch_manifest()

    def test_something_that_is_not_json_is_refused(self):
        self.serve(b"<html>not json</html>")
        with self.assertRaises(updater.UpdateError):
            updater.fetch_manifest()

    def test_a_json_list_is_refused(self):
        self.serve(b"[1, 2, 3]")
        with self.assertRaises(updater.UpdateError):
            updater.fetch_manifest()

    def test_an_oversized_manifest_is_refused_before_it_is_read(self):
        self.serve(b"{}", headers={"Content-Length": str(updater.MAX_MANIFEST_BYTES + 1)})
        with self.assertRaises(updater.UpdateError):
            updater.fetch_manifest()


class StagingTests(unittest.TestCase):
    """The download is only trusted once the bytes have been checked."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        swapped(self, updater, "update_dir",
                lambda: pathlib.Path(self.tmp.name) / "updates")

    def serve(self, body, headers=None, chunks=1):
        swapped(self, updater, "_open_url",
                lambda url, timeout, accept: FakeResponse(body, headers, chunks))

    def manifest_for(self, body, **overrides):
        import hashlib
        manifest = {
            "version": "9.9.9",
            "url": f"{updater.RELEASES_BASE}/download/v9.9.9/AccessibleIDE.exe",
            "sha256": hashlib.sha256(body).hexdigest(),
            "size": len(body),
        }
        manifest.update(overrides)
        return manifest

    def test_a_good_download_is_kept(self):
        body = b"MZ" + b"payload" * 500
        self.serve(body, chunks=7)
        path = updater.stage(self.manifest_for(body))
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_bytes(), body)
        self.assertEqual(updater.sha256_of(path), self.manifest_for(body)["sha256"])

    def test_a_download_that_does_not_match_its_checksum_is_thrown_away(self):
        body = b"MZ" + b"payload" * 500
        self.serve(body, chunks=7)
        with self.assertRaises(updater.UpdateError):
            updater.stage(self.manifest_for(body, sha256="b" * 64))
        # Nothing left behind that could be mistaken for a good build.
        leftovers = list(pathlib.Path(self.tmp.name).rglob("AccessibleIDE.exe"))
        self.assertEqual(leftovers, [])

    def test_the_wrong_size_is_refused(self):
        body = b"MZ" + b"payload" * 10
        self.serve(body, chunks=3)
        with self.assertRaises(updater.UpdateError):
            updater.stage(self.manifest_for(body, size=len(body) + 1))

    def test_an_empty_download_is_refused(self):
        self.serve(b"", chunks=1)
        with self.assertRaises(updater.UpdateError):
            updater.stage(self.manifest_for(b""))

    def test_a_checksum_that_is_not_a_checksum_is_refused(self):
        body = b"MZ" + b"payload"
        self.serve(body, chunks=2)
        with self.assertRaises(updater.UpdateError):
            updater.stage(self.manifest_for(body, sha256="not-a-checksum"))

    def test_a_download_from_somewhere_else_is_never_started(self):
        called = []
        swapped(self, updater, "_open_url",
                lambda *a, **k: called.append(a) or FakeResponse(b""))
        with self.assertRaises(updater.UpdateError):
            updater.stage({
                "url": "https://evil.example.com/a.exe",
                "sha256": "a" * 64,
                "size": 1,
            })
        self.assertEqual(called, [])


class CheckIntervalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        swapped(self, updater, "cache_path",
                lambda: pathlib.Path(self.tmp.name) / "check.json")

    def test_a_first_launch_always_checks(self):
        self.assertTrue(updater.should_check(now=1000.0))

    def test_a_recent_check_is_not_repeated(self):
        updater.remember_check(now=1000.0)
        self.assertFalse(updater.should_check(now=1000.0 + 60))
        self.assertFalse(updater.should_check(
            now=1000.0 + updater.CHECK_INTERVAL_SECONDS - 1))

    def test_an_old_check_is_repeated(self):
        updater.remember_check(now=1000.0)
        self.assertTrue(updater.should_check(
            now=1000.0 + updater.CHECK_INTERVAL_SECONDS))

    def test_asking_by_hand_ignores_the_interval(self):
        updater.remember_check(now=1000.0)
        self.assertTrue(updater.should_check(force=True, now=1000.0 + 1))

    def test_a_corrupt_cache_file_is_not_fatal(self):
        updater.cache_path().parent.mkdir(parents=True, exist_ok=True)
        updater.cache_path().write_text("not json at all", encoding="utf-8")
        self.assertTrue(updater.should_check(now=1000.0))


class CheckResultTests(unittest.TestCase):
    def test_the_website_does_not_offer_an_exe(self):
        os.environ.pop("ACCESSIBLE_IDE_UPDATE_TEST", None)
        result = updater.check(force=True)
        self.assertFalse(result["applicable"])
        self.assertFalse(result["update_available"])

    def test_a_failure_is_reported_rather_than_raised(self):
        # The reader is trying to open an editor. A check that cannot reach
        # the network must never be the reason that fails.
        os.environ["ACCESSIBLE_IDE_UPDATE_TEST"] = "1"
        self.addCleanup(os.environ.pop, "ACCESSIBLE_IDE_UPDATE_TEST", None)

        def explode():
            raise updater.UpdateError("could not reach GitHub to check for updates")
        swapped(self, updater, "fetch_manifest", explode)

        result = updater.check(force=True)
        self.assertFalse(result["update_available"])
        self.assertIn("could not reach", result["error"])

    def test_a_newer_build_is_offered(self):
        os.environ["ACCESSIBLE_IDE_UPDATE_TEST"] = "1"
        self.addCleanup(os.environ.pop, "ACCESSIBLE_IDE_UPDATE_TEST", None)
        swapped(self, updater, "fetch_manifest", lambda: {
            "version": "99.0.0",
            "url": f"{updater.RELEASES_BASE}/download/v99/AccessibleIDE.exe",
            "sha256": "a" * 64,
            "size": 1,
            "notes": "Fixed the thing.",
        })
        result = updater.check(force=True)
        self.assertTrue(result["update_available"])
        self.assertEqual(result["latest"], "99.0.0")
        self.assertEqual(result["notes"], "Fixed the thing.")

    def test_the_same_build_is_not_offered(self):
        os.environ["ACCESSIBLE_IDE_UPDATE_TEST"] = "1"
        self.addCleanup(os.environ.pop, "ACCESSIBLE_IDE_UPDATE_TEST", None)
        swapped(self, updater, "fetch_manifest", lambda: {
            "version": updater.current_version(),
            "url": f"{updater.RELEASES_BASE}/download/v/AccessibleIDE.exe",
            "sha256": "a" * 64,
            "size": 1,
        })
        result = updater.check(force=True)
        self.assertFalse(result["update_available"])


if __name__ == "__main__":
    unittest.main()
