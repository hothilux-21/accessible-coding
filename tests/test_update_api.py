"""Tests for the version and update-check endpoints.

The rule these protect: whether the app checks for an update is decided on
the server, from the saved setting, and not by whatever the page asks for.
A browser that asks for a check anyway must not get one when the reader has
turned automatic checking off - but a check the reader asked for themselves
must always be answered.

Isolation: as in test_config_api, routes.py reads its config paths as
module-level globals, so both are repointed at a temporary directory here.
"""

import os
import pathlib
import re
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = str(REPO_ROOT / "src")
if SRC not in sys.path:
    sys.path.append(SRC)

from accessible_ide import create_app, i18n, routes, updater  # noqa: E402


class UpdateEndpointTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp_path = pathlib.Path(self._tmp.name)

        self._saved = {
            "CONFIG_DIR": routes.CONFIG_DIR,
            "CONFIG_FILE": routes.CONFIG_FILE,
            "ACCESS_CODE": routes.ACCESS_CODE,
        }
        routes.CONFIG_DIR = tmp_path
        routes.CONFIG_FILE = tmp_path / "config.json"
        routes.ACCESS_CODE = ""

        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

        # Pretend to be the packaged app, and stop any test reaching the
        # real GitHub or the real user's cache file.
        os.environ["ACCESSIBLE_IDE_UPDATE_TEST"] = "1"
        self.addCleanup(os.environ.pop, "ACCESSIBLE_IDE_UPDATE_TEST", None)
        self.patch(updater, "cache_path", lambda: tmp_path / "check.json")
        self.addCleanup(self._restore)

    def patch(self, obj, name, value):
        original = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, original)

    def _restore(self):
        for key, value in self._saved.items():
            setattr(routes, key, value)
        self._tmp.cleanup()

    def fake_manifest(self, version, **extra):
        manifest = {
            "version": version,
            "url": f"{updater.RELEASES_BASE}/download/v/{updater.ASSET_NAME}",
            "sha256": "a" * 64,
            "size": 10,
            "notes": "Something changed.",
        }
        manifest.update(extra)
        return manifest

    def set_manifest(self, version, **extra):
        self.patch(updater, "fetch_manifest",
                   lambda *a, **k: self.fake_manifest(version, **extra))

    def fail_manifest(self, message="could not reach GitHub to check for updates",
                      code="network"):
        def explode(*args, **kwargs):
            raise updater.UpdateError(message, code=code)
        self.patch(updater, "fetch_manifest", explode)

    def check(self, **payload):
        return self.client.post("/api/update/check", json=payload)


class VersionEndpointTests(UpdateEndpointTestCase):
    def test_it_reports_the_running_version(self):
        from accessible_ide import __version__
        body = self.client.get("/api/version").get_json()
        self.assertEqual(body["version"], __version__)

    def test_it_says_whether_the_running_copy_can_update_itself(self):
        body = self.client.get("/api/version").get_json()
        self.assertTrue(body["applicable"])

    def test_the_website_reports_that_it_cannot_update_itself(self):
        # The hosted version is updated by redeploying the server. Offering
        # to replace an exe there would be nonsense.
        os.environ.pop("ACCESSIBLE_IDE_UPDATE_TEST", None)
        body = self.client.get("/api/version").get_json()
        self.assertFalse(body["applicable"])


class ManualCheckTests(UpdateEndpointTestCase):
    def test_a_newer_build_is_offered(self):
        self.set_manifest("99.0.0")
        body = self.check(force=True).get_json()
        self.assertTrue(body["update_available"])
        self.assertEqual(body["latest"], "99.0.0")
        self.assertEqual(body["notes"], "Something changed.")

    def test_the_same_build_is_not_offered(self):
        self.set_manifest(updater.current_version())
        self.assertFalse(self.check(force=True).get_json()["update_available"])

    def test_an_older_build_is_not_offered(self):
        # The important one. A manifest left over from an older release, or
        # a rollback, must never be presented as an upgrade.
        self.set_manifest("0.0.1")
        self.assertFalse(self.check(force=True).get_json()["update_available"])

    def test_a_network_failure_is_reported_not_raised(self):
        self.fail_manifest()
        response = self.check(force=True)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertFalse(body["update_available"])
        self.assertIn("could not reach", body["error"])


class AutomaticCheckSettingTests(UpdateEndpointTestCase):
    """The saved setting decides, not the page asking."""

    def test_it_is_on_by_default(self):
        self.assertTrue(routes.load_config()["auto_update"])

    def test_turning_it_off_stops_the_automatic_check(self):
        routes.save_config(dict(routes.load_config(), auto_update=False))
        self.set_manifest("99.0.0")
        body = self.check().get_json()
        self.assertFalse(body["update_available"])
        self.assertFalse(body["automatic"])
        # Nothing was reported because nothing was looked at.
        self.assertNotIn("latest", body)

    def test_turning_it_off_does_not_block_a_check_the_reader_asked_for(self):
        # Refusing to answer a direct question is the same as being broken.
        routes.save_config(dict(routes.load_config(), auto_update=False))
        self.set_manifest("99.0.0")
        body = self.check(force=True).get_json()
        self.assertTrue(body["update_available"])
        self.assertTrue(body["automatic"] is False)

    def test_turning_it_on_restores_the_automatic_check(self):
        routes.save_config(dict(routes.load_config(), auto_update=False))
        self.set_manifest("99.0.0")
        self.check()
        routes.save_config(dict(routes.load_config(), auto_update=True))
        self.assertTrue(self.check().get_json()["update_available"])

    def test_the_setting_survives_a_save_and_reload(self):
        self.client.post("/api/config", json={"auto_update": False})
        self.assertFalse(self.client.get("/api/config").get_json()["auto_update"])

    def test_only_a_real_off_or_on_is_accepted(self):
        for bad in ("no", 1, None, [], "true"):
            with self.subTest(value=bad):
                response = self.client.post("/api/config", json={"auto_update": bad})
                self.assertEqual(response.status_code, 400)
        # The rejected value must not have been written.
        self.assertTrue(self.client.get("/api/config").get_json()["auto_update"])


class UpdateCheckIntervalTests(UpdateEndpointTestCase):
    """Launching the app must not mean asking GitHub every single time."""

    def test_a_recent_check_is_not_repeated_automatically(self):
        self.set_manifest("99.0.0")
        self.assertTrue(self.check().get_json()["update_available"])
        # GitHub would now say 404 because the fake is gone; a second
        # automatic check must not go there at all.
        self.fail_manifest("should not have been called")
        second = self.check().get_json()
        self.assertFalse(second["update_available"])
        self.assertEqual(second["error"], "checked_recently")

    def test_asking_by_hand_always_goes_out(self):
        self.set_manifest("99.0.0")
        self.check()
        self.fail_manifest("should not have been called")
        # Forced, so the interval is ignored and the error surfaces.
        self.assertIn("should not have been called",
                      self.check(force=True).get_json()["error"])


class ErrorTextTests(UpdateEndpointTestCase):
    """The sentence the reader sees must be in the reader's language.

    The updater raises English text on purpose, because that is what belongs
    in a log. Handing it to the interface would put an English sentence in
    front of a reader who reads Hindi, so the code is looked up in the
    catalogue and the code is what travels.
    """

    def test_a_failure_is_sent_as_a_translated_sentence(self):
        self.fail_manifest()
        body = self.check(force=True, locale="fr").get_json()
        self.assertEqual(body["error_code"], "network")
        self.assertEqual(body["error_text"], i18n.make_translator("fr")("update.error_network"))
        self.assertNotEqual(body["error_text"], body["error"])

    def test_the_same_failure_reads_differently_in_each_language(self):
        self.fail_manifest()
        sentences = set()
        for locale in ("en", "hi", "fr", "es", "ar"):
            body = self.check(force=True, locale=locale).get_json()
            sentences.add(body["error_text"])
        self.assertEqual(len(sentences), 5)

    def test_every_code_the_updater_raises_has_a_sentence(self):
        # A new kind of failure added to updater.py must not reach the
        # interface as a raw code. The updater is scanned rather than the
        # mapping being trusted, because the mapping is the thing that gets
        # forgotten when the error is the thing being added.
        source = (pathlib.Path(updater.__file__)).read_text(encoding="utf-8")
        codes = set(re.findall(r"code=['\"]([\w]+)['\"]", source))
        self.assertIn("network", codes)
        unmapped = codes - set(routes.UPDATE_ERROR_KEYS)
        self.assertEqual(unmapped, set(),
                         f"these codes have no sentence: {sorted(unmapped)}")

    def test_every_mapped_key_exists_in_every_language(self):
        for locale in ("en", "hi", "fr", "es", "ar"):
            for key in routes.UPDATE_ERROR_KEYS.values():
                with self.subTest(locale=locale, key=key):
                    self.assertTrue(i18n.make_translator(locale)(key))

    def test_an_unknown_code_still_produces_a_sentence(self):
        self.patch(updater, "fetch_manifest",
                   lambda *a, **k: (_ for _ in ()).throw(
                       updater.UpdateError("something new", code="brand_new")))
        body = self.check(force=True, locale="fr").get_json()
        self.assertEqual(body["error_code"], "brand_new")
        self.assertEqual(body["error_text"], i18n.make_translator("fr")("update.error_unknown"))


class AccessCodeTests(UpdateEndpointTestCase):
    def test_the_check_is_gated_like_the_other_apis(self):
        routes.ACCESS_CODE = "letmein"
        body = self.check(force=True).get_json()
        self.assertTrue(body.get("code_required"))


if __name__ == "__main__":
    unittest.main()
