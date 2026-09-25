"""Tests for the settings API (POST /api/config).

The app is offline-first, so a setting that fails to save is a setting
the reader silently loses on the next restart. These tests cover the
new settings and the validation that keeps bad values out of the file.

Isolation: routes.py reads CONFIG_DIR and CONFIG_FILE as module-level
globals, so both are repointed at a fresh temporary directory for every
test. ACCESS_CODE is cleared because it is read once at import time and
a developer machine may have one set.

Run with:  PYTHONPATH=src python -m unittest discover -s tests -t .
"""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = str(REPO_ROOT / "src")
if SRC not in sys.path:
    sys.path.append(SRC)

from accessible_ide import create_app, routes  # noqa: E402


class ConfigApiTestCase(unittest.TestCase):
    """Base class giving each test a private config file."""

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
        self.addCleanup(self._restore)

    def _restore(self):
        for key, value in self._saved.items():
            setattr(routes, key, value)
        self._tmp.cleanup()

    # -- helpers -------------------------------------------------------
    def post_settings(self, **payload):
        return self.client.post("/api/config", json=payload)

    def get_settings(self):
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        return response.get_json()


class NewSettingsTests(ConfigApiTestCase):
    def test_defaults_contain_every_applied_setting(self):
        # line_height, letter_spacing and blur_intensity were stored and
        # rendered for a long time but never read by anything. The panel
        # now applies all of them, so they must all be present.
        for key in (
            "font",
            "font_size",
            "line_height",
            "letter_spacing",
            "blur_intensity",
            "theme",
            "focus_mode",
            "contrast",
            "tts_enabled",
            "tts_voice",
            "tts_rate",
            "locale",
        ):
            with self.subTest(key=key):
                self.assertIn(key, routes.DEFAULT_CONFIG)

    def test_contrast_round_trips(self):
        for value in sorted(routes.CONFIG_VALUES["contrast"]):
            with self.subTest(contrast=value):
                response = self.post_settings(contrast=value)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.get_settings()["contrast"], value)

    def test_tts_voice_round_trips_with_realistic_voice_name(self):
        # Voice names come from the OS and routinely contain spaces,
        # punctuation and parentheses.
        name = "Microsoft David Desktop - English (United States)"
        response = self.post_settings(tts_voice=name)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.get_settings()["tts_voice"], name)

    def test_tts_rate_round_trips(self):
        for value in (0.5, 0.9, 1.25, 2.0):
            with self.subTest(tts_rate=value):
                response = self.post_settings(tts_rate=value)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.get_settings()["tts_rate"], value)

    def test_reading_settings_round_trip(self):
        response = self.post_settings(
            line_height=2.0,
            letter_spacing=1.5,
            blur_intensity=0.75,
        )
        self.assertEqual(response.status_code, 200)
        stored = self.get_settings()
        self.assertEqual(stored["line_height"], 2.0)
        self.assertEqual(stored["letter_spacing"], 1.5)
        self.assertEqual(stored["blur_intensity"], 0.75)


class AccessCodeIsNotASettingTests(ConfigApiTestCase):
    """The browser always sends access_code, including when it is empty.

    It used to be validated as a setting and rejected, so every settings
    change failed with a 400 while appearing to work. It would also have
    been written into config.json in plain text.
    """

    def test_empty_access_code_does_not_block_saving(self):
        response = self.post_settings(font_size=20, access_code="")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.get_settings()["font_size"], 20)

    def test_access_code_is_never_written_to_the_config_file(self):
        routes.ACCESS_CODE = "letmein"
        response = self.post_settings(font_size=21, access_code="letmein")
        self.assertEqual(response.status_code, 200)

        self.assertIn("font_size", routes.CONFIG_FILE.read_text())
        raw = routes.CONFIG_FILE.read_text()
        self.assertNotIn("access_code", raw)
        self.assertNotIn("letmein", raw)

    def test_wrong_access_code_is_still_rejected(self):
        routes.ACCESS_CODE = "letmein"
        response = self.post_settings(font_size=21, access_code="wrong")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(routes.CONFIG_FILE.exists())


class ValidationTests(ConfigApiTestCase):
    def test_out_of_range_values_are_rejected(self):
        for key, (low, high) in routes.CONFIG_RANGES.items():
            for label, value in (("below", low - 1), ("above", high + 1)):
                with self.subTest(key=key, side=label):
                    # Seed a known good value first so we can prove the
                    # bad one did not overwrite it.
                    good = low if isinstance(low, int) else low
                    self.post_settings(**{key: good})
                    response = self.post_settings(**{key: value})
                    self.assertEqual(
                        response.status_code,
                        400,
                        f"{key}={value} should be rejected",
                    )
                    self.assertIn("error", response.get_json())
                    self.assertEqual(self.get_settings()[key], good)

    def test_unknown_setting_is_rejected_with_plain_english(self):
        response = self.post_settings(colour="purple")
        self.assertEqual(response.status_code, 400)
        error = response.get_json()["error"]
        self.assertIn("colour", error)
        # Plain English, not a Python exception or a key dump.
        self.assertNotIn("Traceback", error)

    def test_invalid_contrast_value_is_rejected(self):
        response = self.post_settings(contrast="extra")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.get_settings()["contrast"], "normal")

    def test_overlong_tts_voice_is_rejected(self):
        limit = routes.CONFIG_MAX_LENGTHS["tts_voice"]
        self.assertEqual(self.post_settings(tts_voice="a" * limit).status_code, 200)
        response = self.post_settings(tts_voice="a" * (limit + 1))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.get_settings()["tts_voice"], "a" * limit)

    def test_wrong_type_is_rejected(self):
        cases = [
            {"font_size": "large"},
            {"tts_enabled": "yes"},
            {"tts_rate": "fast"},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.post_settings(**payload).status_code, 400)

    def test_bool_is_not_accepted_where_a_number_is_wanted(self):
        # bool is a subclass of int in Python, so True would otherwise
        # sneak through a numeric check and render as font_size: 1.
        self.assertEqual(self.post_settings(font_size=True).status_code, 400)
        self.assertEqual(self.post_settings(tts_rate=True).status_code, 400)

    def test_a_bad_key_does_not_corrupt_the_good_ones(self):
        # Rejection happens before the save, so a payload mixing a good
        # and a bad setting must leave the previous file untouched.
        self.post_settings(font_size=18, contrast="high")
        response = self.post_settings(theme="dark", font_size=99)
        self.assertEqual(response.status_code, 400)

        stored = self.get_settings()
        self.assertEqual(stored["font_size"], 18)
        self.assertEqual(stored["contrast"], "high")
        self.assertEqual(stored["theme"], routes.DEFAULT_CONFIG["theme"])


class LocaleTests(ConfigApiTestCase):
    """The chosen interface language."""

    def test_every_shipped_language_round_trips(self):
        for code in ("en", "hi", "fr", "es", "ar"):
            with self.subTest(locale=code):
                self.assertEqual(self.post_settings(locale=code).status_code, 200)
                self.assertEqual(self.get_settings()["locale"], code)

    def test_a_language_the_app_does_not_ship_is_rejected(self):
        # Saving "de" would leave the reader with a language picker showing
        # German and an English interface, with no way back.
        response = self.post_settings(locale="de")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.get_settings()["locale"], "en")

    def test_a_non_string_language_is_rejected(self):
        for value in (5, True, ["fr"], None, ""):
            with self.subTest(value=value):
                self.assertEqual(self.post_settings(locale=value).status_code, 400)

    def test_the_rejection_names_the_setting_in_the_chosen_language(self):
        # A reader who has chosen Hindi should not be handed an English
        # sentence, and the sentence should quote the label they actually
        # clicked rather than the key stored in the file. The saved
        # language is the fallback, because the browser sends its own
        # locale and this request is deliberately not carrying one.
        from accessible_ide import i18n

        label_key = i18n.CONFIG_LABELS["contrast"]
        for code in ("en", "hi", "fr", "es", "ar"):
            with self.subTest(locale=code):
                self.assertEqual(self.post_settings(locale=code).status_code, 200)
                error = self.post_settings(contrast="extra").get_json()["error"]
                self.assertIn(i18n.load_catalogue(code)[label_key], error)
                # The label, not the key someone would grep for in the file.
                self.assertNotIn("'contrast'", error)
                self.assertNotIn('"contrast"', error)

    def test_a_sent_locale_beats_the_saved_one(self):
        # The picker saves and reloads, so this is belt and braces, but it
        # is what keeps an error in the language on screen if the save has
        # not landed yet.
        from accessible_ide import i18n

        self.assertEqual(self.post_settings(locale="es").status_code, 200)
        error = self.client.post(
            "/api/config", json={"locale": "ar", "contrast": "extra"}
        ).get_json()["error"]
        self.assertIn(
            i18n.load_catalogue("ar")[i18n.CONFIG_LABELS["contrast"]], error
        )

    def test_the_page_renders_in_the_saved_language(self):
        self.assertEqual(self.post_settings(locale="es").status_code, 200)
        page = self.client.get("/")
        try:
            body = page.data.decode("utf-8")
        finally:
            page.close()
        self.assertIn('<html lang="es">', body)
        self.assertIn("Ajustes", body)

    def test_a_corrupt_locale_in_the_file_falls_back_to_english(self):
        routes.CONFIG_FILE.write_text('{"locale": "klingon"}', encoding="utf-8")
        page = self.client.get("/")
        try:
            body = page.data.decode("utf-8")
        finally:
            page.close()
        self.assertIn('<html lang="en">', body)

    def test_every_theme_name_is_translated(self):
        # The theme picker is built from /api/themes, whose names are English.
        # app.js looks each one up as theme.<key>, so every theme the server
        # offers needs a catalogue entry in every language.
        from accessible_ide import i18n

        for code, theme in routes.THEMES.items():
            for locale in i18n.LANGUAGES:
                key = f"theme.{code}"
                with self.subTest(theme=code, locale=locale):
                    self.assertIn(key, i18n.load_catalogue(locale))


class CodeColorTests(ConfigApiTestCase):
    """The chosen code text colour."""

    def test_a_colour_round_trips(self):
        self.assertEqual(self.post_settings(code_color="#ffd93d").status_code, 200)
        self.assertEqual(self.get_settings()["code_color"], "#ffd93d")

    def test_empty_means_use_the_theme_colour(self):
        self.post_settings(code_color="#ffd93d")
        self.assertEqual(self.post_settings(code_color="").status_code, 200)
        self.assertEqual(self.get_settings()["code_color"], "")

    def test_short_hex_form_is_accepted(self):
        self.assertEqual(self.post_settings(code_color="#f0a").status_code, 200)
        self.assertEqual(self.get_settings()["code_color"], "#f0a")

    def test_capital_letters_are_accepted(self):
        self.assertEqual(self.post_settings(code_color="#FFD93D").status_code, 200)

    def test_anything_that_is_not_a_hex_colour_is_rejected(self):
        # This setting is written into a style attribute, so anything
        # carrying a second CSS declaration has to be refused outright.
        cases = [
            "red",              # a named colour, not a hex code
            "#ff",              # too short
            "#ffff",            # 4 digits: alpha, which hides text
            "#ffffffff",        # 8 digits: the same, with more opacity
            "#gggggg",          # not hex digits
            "ffd93d",           # missing the #
            "#ffd93d; background: url(evil)",   # style injection
            "rgb(255,0,0)",     # another format
            " ",                # whitespace is not a colour
        ]
        for value in cases:
            with self.subTest(code_color=value):
                response = self.post_settings(code_color=value)
                self.assertEqual(response.status_code, 400, f"{value!r} was accepted")
                self.assertEqual(self.get_settings()["code_color"], "")

    def test_a_non_string_colour_is_rejected(self):
        for value in [123, None, ["#ffffff"], {"hex": "#ffffff"}, True]:
            with self.subTest(code_color=value):
                self.assertEqual(self.post_settings(code_color=value).status_code, 400)

    def test_the_error_explains_itself_in_plain_english(self):
        response = self.post_settings(code_color="purple")
        message = response.get_json().get("error", "")
        self.assertIn("#", message)
        self.assertIn("colour", message.lower())
        # Jargon the reader would not know is exactly what this avoids.
        for jargon in ("hex", "regex", "null", "NaN", "invalid"):
            self.assertNotIn(jargon, message)


class ReduceMotionTests(ConfigApiTestCase):
    """The reduce-motion switch.

    Movement is the one setting with three states rather than two, because
    "not chosen yet" has to be distinguishable from "off": until the reader
    decides, the operating system preference decides for them.
    """

    def test_it_keeps_both_directions(self):
        # An OS-level reduced-motion setting must not be the only way to turn
        # movement off, and turning it off in the app must not be impossible
        # for a reader whose computer asks for reduction everywhere else.
        for value in (True, False):
            with self.subTest(reduce_motion=value):
                self.assertEqual(
                    self.post_settings(reduce_motion=value).status_code, 200
                )
                self.assertIs(self.get_settings()["reduce_motion"], value)

    def test_nothing_chosen_reports_unset_rather_than_off(self):
        # None is what the page reads to decide whether to defer to the
        # system, so it must survive as a real null, not collapse to False.
        self.assertIsNone(self.get_settings()["reduce_motion"])
        self.assertIsNone(routes.DEFAULT_CONFIG["reduce_motion"])

    def test_the_page_marks_the_body_before_any_script_runs(self):
        # app.js can adjust the switch, but the stylesheet has to be right
        # from the first paint or things move before the correction lands.
        page = self.client.get("/").data.decode("utf-8")
        self.assertIn('data-reduce-motion="unset"', page)

        self.post_settings(reduce_motion=True)
        page = self.client.get("/").data.decode("utf-8")
        self.assertIn('data-reduce-motion="true"', page)
        self.assertNotIn('data-reduce-motion="unset"', page)

        self.post_settings(reduce_motion=False)
        page = self.client.get("/").data.decode("utf-8")
        self.assertIn('data-reduce-motion="false"', page)

    def test_a_text_value_is_refused_with_a_message_about_the_switch(self):
        response = self.post_settings(reduce_motion="yes")
        self.assertEqual(response.status_code, 400)
        message = response.get_json()["error"]
        # The old wording would have said this is not a setting we
        # recognise, sending the reader hunting for a control that exists.
        self.assertIn("Reduce motion", message)
        self.assertIn("on or off", message)
        self.assertNotIn("not a setting", message)

    def test_the_switch_is_announced_as_a_switch(self):
        page = self.client.get("/").data.decode("utf-8")
        self.assertIn('id="reduce-motion"', page)
        self.assertRegex(page, r'id="reduce-motion"[^>]*role="switch"')
        self.assertIn('aria-describedby="motion-hint"', page)


class WrongTypeTests(ConfigApiTestCase):
    """A known setting sent the wrong sort of value."""

    def test_a_non_bool_for_a_switch_is_rejected(self):
        for value in ("yes", 1, 0, None, [], {}):
            with self.subTest(value=value):
                self.assertEqual(
                    self.post_settings(tts_enabled=value).status_code, 400,
                    f"tts_enabled={value!r} was accepted",
                )
                self.assertEqual(
                    self.post_settings(reduce_motion=value).status_code, 400,
                    f"reduce_motion={value!r} was accepted",
                )

    def test_the_message_names_the_setting_rather_than_dismissing_it(self):
        for key in ("tts_enabled", "reduce_motion"):
            with self.subTest(key=key):
                message = self.post_settings(**{key: "maybe"}).get_json()["error"]
                self.assertNotIn("not a setting we recognise", message)
                self.assertIn("on or off", message)


class ThemeApiTests(ConfigApiTestCase):
    def test_themes_endpoint_serves_the_editor_palettes(self):
        # app.js builds the CodeMirror theme from this response, so the
        # key set here is the contract with the front end.
        response = self.client.get("/api/themes")
        self.assertEqual(response.status_code, 200)
        themes = response.get_json()
        self.assertEqual(sorted(themes), sorted(routes.THEMES))
        for name, palette in themes.items():
            with self.subTest(theme=name):
                for key in ("name", "bg", "fg", "keyword", "string", "comment"):
                    self.assertIn(key, palette)


if __name__ == "__main__":
    unittest.main()
