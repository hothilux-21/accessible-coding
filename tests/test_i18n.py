"""Tests for the translation catalogues.

The rule these enforce: no visible word is written directly in the
template or in app.js, and every catalogue defines every key English
defines. A language option that silently falls back to English is worse
than one that is not offered, because the reader has no way to tell.
"""

import json
import re
import unittest
from pathlib import Path

from accessible_ide import i18n

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "src" / "accessible_ide" / "templates" / "index.html"
APP_JS = ROOT / "src" / "accessible_ide" / "static" / "js" / "app.js"

LOCALES = ("en", "hi", "fr", "es", "ar")


class CatalogueCompleteness(unittest.TestCase):
    def test_every_locale_file_exists(self):
        for code in LOCALES:
            path = i18n.I18N_DIR / f"{code}.json"
            self.assertTrue(path.is_file(), f"missing catalogue: {path}")

    def test_every_locale_defines_every_reference_key(self):
        reference = i18n.reference_keys()
        self.assertGreater(len(reference), 100)
        for code in LOCALES:
            with self.subTest(locale=code):
                self.assertEqual(
                    i18n.untranslated_keys(code), set(),
                    f"{code} is missing keys English defines",
                )

    def test_no_locale_defines_a_key_english_does_not(self):
        reference = i18n.reference_keys()
        for code in LOCALES:
            with self.subTest(locale=code):
                extra = set(i18n.load_catalogue(code)) - reference
                self.assertEqual(extra, set(), f"{code} has stray keys: {extra}")

    def test_no_value_is_blank(self):
        for code in LOCALES:
            catalogue = i18n.load_catalogue(code)
            for key, value in catalogue.items():
                with self.subTest(locale=code, key=key):
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip(), f"{code}/{key} is blank")

    def test_no_whole_sentence_left_in_english(self):
        for code in LOCALES:
            if code == "en":
                continue
            with self.subTest(locale=code):
                left = i18n.untranslated_sentences(code)
                self.assertEqual(left, {}, f"{code} still has English: {left}")

    def test_placeholders_match_the_reference(self):
        pattern = re.compile(r"\{(\d+)\}")
        reference = i18n.load_catalogue("en")
        for code in LOCALES:
            catalogue = i18n.load_catalogue(code)
            for key, value in reference.items():
                with self.subTest(locale=code, key=key):
                    self.assertEqual(
                        sorted(pattern.findall(catalogue[key])),
                        sorted(pattern.findall(value)),
                        f"{code}/{key} lost or gained a placeholder",
                    )

    def test_catalogue_files_are_utf8_json(self):
        for code in LOCALES:
            path = i18n.I18N_DIR / f"{code}.json"
            raw = path.read_bytes()
            with self.subTest(locale=code):
                raw.decode("utf-8")
                json.loads(raw.decode("utf-8"))


class Translator(unittest.TestCase):
    def test_formats_positional_arguments(self):
        t = i18n.make_translator("en")
        self.assertEqual(
            t("try.status_custom", "Lexend", "#ffd93d"),
            "Showing Lexend in #ffd93d.",
        )

    def test_substitutes_every_occurrence(self):
        t = i18n.make_translator("en")
        rendered = t("try.system_font", "Arial")
        self.assertIn("Arial", rendered)
        self.assertNotIn("{0}", rendered)

    def test_returns_the_key_when_missing(self):
        t = i18n.make_translator("en")
        self.assertEqual(t("no.such.key"), "no.such.key")

    def test_unknown_locale_falls_back_to_english(self):
        t = i18n.make_translator("zz")
        self.assertEqual(t("nav.run"), "Run")
        self.assertEqual(t("nav.run"), i18n.make_translator("en")("nav.run"))

    def test_known_locale_does_not_return_english_text(self):
        for code in LOCALES:
            if code == "en":
                continue
            with self.subTest(locale=code):
                t = i18n.make_translator(code)
                self.assertNotEqual(t("nav.run"), "Run")
                self.assertNotEqual(t("settings.title"), "Settings")


class LocaleRegistry(unittest.TestCase):
    def test_five_languages_are_registered(self):
        self.assertEqual(sorted(i18n.LANGUAGES), sorted(LOCALES))

    def test_every_language_is_named_in_its_own_script(self):
        for code in LOCALES:
            with self.subTest(locale=code):
                endonym, english, direction = i18n.LANGUAGES[code]
                self.assertTrue(endonym.strip())
                self.assertTrue(english.strip())
                self.assertIn(direction, ("ltr", "rtl"))

    def test_arabic_is_the_only_rtl_language(self):
        rtl = [c for c, (_, _, d) in i18n.LANGUAGES.items() if d == "rtl"]
        self.assertEqual(rtl, ["ar"])

    def test_normalise_rejects_unknown_and_non_strings(self):
        for value in ("zz", "", None, 5, ["fr"], True):
            with self.subTest(value=value):
                self.assertIsNone(i18n.normalise(value))
        self.assertEqual(i18n.normalise("fr"), "fr")


class NoHardcodedStrings(unittest.TestCase):
    """The whole point of the catalogues: no English left in the markup."""

    # A character written as an HTML entity is not prose, and the version
    # badge is a fixed string. Numeric (&#8722;) and named (&minus;) forms
    # are both allowed, because the stepper buttons need a minus sign and
    # naming it is far clearer at the point of use than the codepoint.
    # Everything else between tags must be a t() call.
    ALLOWED_LITERAL = re.compile(r"^(?:v[\w.-]+|&#\d+;|&[a-zA-Z][a-zA-Z0-9]*;)$")

    def test_template_has_no_bare_text_in_body(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        body = html.split("<body", 1)[1]
        for text in re.findall(r">([^<>{}]+)<", body):
            cleaned = text.strip()
            if not cleaned or self.ALLOWED_LITERAL.match(cleaned):
                continue
            with self.subTest(text=cleaned):
                self.fail(f"literal text in template body: {cleaned!r}")

    def test_every_visible_string_in_the_template_goes_through_t(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        # The lookbehind matters: without it this matches the tail of
        # format('truetype') in the @font-face src and demands a catalogue
        # entry for "truetype".
        for key in re.findall(r"(?<![\w.])t\('([^']+)'\)", html):
            with self.subTest(key=key):
                self.assertIn(key, i18n.reference_keys())

    def test_every_key_app_js_asks_for_exists(self):
        js = APP_JS.read_text(encoding="utf-8")
        keys = set(re.findall(r"\bt\('([^']+)'", js))
        self.assertGreater(len(keys), 15, "expected app.js to translate a lot")
        for key in sorted(keys):
            with self.subTest(key=key):
                self.assertIn(key, i18n.reference_keys())

    def test_app_js_has_no_leftover_sentence_literals(self):
        js = APP_JS.read_text(encoding="utf-8")
        # A sentence-shaped literal is what a missed extraction looks like.
        for literal in re.findall(r"'([A-Z][a-z]+[^']{6,}?[.!?])'", js):
            with self.subTest(literal=literal):
                self.fail(f"untranslated sentence literal in app.js: {literal!r}")

    def test_html_lang_attribute_is_dynamic(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('<html lang="{{ locale }}">', html)

    def test_language_selector_is_built_from_the_registry(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('id="language-select"', html)
        # The options must come from the registry, not be typed out in the
        # markup, or a new language would need a template edit.
        self.assertIn("{% for code, endonym_label, english_name, lang_direction in languages %}",
                      html)
        self.assertIn('lang="{{ code }}"', html)
        self.assertIn("{% if config.locale == code %}selected{% endif %}", html)

    def test_language_selector_has_an_option_per_registered_language(self):
        # i18n.available() is exactly what the template iterates over, so the
        # count here is the count of <option> elements a reader will see.
        self.assertEqual([row[0] for row in i18n.available()], list(LOCALES))

    def test_toolbar_is_labelled_by_its_own_key(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        # A toolbar is not a settings dialog; borrowing settings_title would
        # tell a screen reader the wrong thing about the whole strip.
        self.assertIn("""role="toolbar" aria-label="{{ t('nav.tools') }}\"""", html)
        self.assertNotIn("""role="toolbar" aria-label="{{ t('nav.settings_title') }}\"""", html)


if __name__ == "__main__":
    unittest.main()
