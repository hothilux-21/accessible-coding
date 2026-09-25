"""Checks the contract between index.html and app.js.

The front end wires everything up with getElementById and then uses the
result immediately. A control that is renamed in only one of the two
files produces a null reference that stops the rest of the script from
running - which in a single-file app means the whole editor stops
responding, with nothing in the console a user could act on.

So: every id the script looks up has to exist in the rendered template,
and the settings panel has to be complete.

Run with:  PYTHONPATH=src python -m unittest discover -s tests -t .
"""

import pathlib
import re
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = str(REPO_ROOT / "src")
if SRC not in sys.path:
    sys.path.append(SRC)

from accessible_ide import create_app, routes  # noqa: E402

APP_JS = REPO_ROOT / "src" / "accessible_ide" / "static" / "js" / "app.js"

# Controls the settings panel is expected to provide. Listed separately
# from the automatic scan so a missing control produces a clear message
# rather than only showing up as a generic scan failure.
REQUIRED_SETTINGS_IDS = (
    "settings-dialog",
    "settings-title",
    "settings-status",
    "btn-settings",
    "btn-settings-close",
    "font-select",
    "font-size",
    "font-size-label",
    "line-height",
    "line-height-label",
    "letter-spacing",
    "letter-spacing-label",
    "blur-intensity",
    "blur-intensity-label",
    "blur-field",
    "theme-select",
    "contrast-select",
    "focus-mode",
    "tts-toggle",
    "tts-state",
    "tts-voice",
    "tts-rate",
    "tts-rate-label",
    "btn-test-voice",
)


def render_index():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200, response.status_code
    return response.get_data(as_text=True)


class TemplateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = render_index()
        cls.js = APP_JS.read_text(encoding="utf-8")
        cls.html_ids = set(re.findall(r'id="([^"]+)"', cls.html))

    def test_every_element_the_script_looks_up_exists(self):
        wanted = set(
            re.findall(r"getElementById\(\s*'([^']+)'\s*\)", self.js)
        )
        self.assertTrue(wanted, "failed to scan app.js for getElementById calls")
        missing = sorted(wanted - self.html_ids)
        self.assertEqual(
            missing,
            [],
            "app.js looks these up but index.html has no matching element: "
            + ", ".join(missing),
        )

    def test_settings_panel_is_complete(self):
        missing = [
            element for element in REQUIRED_SETTINGS_IDS if element not in self.html_ids
        ]
        self.assertEqual(
            missing, [], "settings panel is missing: " + ", ".join(missing)
        )

    def test_settings_dialog_is_a_real_modal(self):
        # A native <dialog> gives focus trapping, Escape handling and an
        # inert background without hand-rolled JavaScript.
        self.assertIn('<dialog id="settings-dialog"', self.html)
        self.assertIn("showModal", self.js)
        self.assertIn("aria-labelledby=\"settings-title\"", self.html)

    def test_settings_panel_is_not_a_form(self):
        # A form method="dialog" closes the panel whenever it is
        # submitted, and pressing Enter while a select has focus submits
        # it - so choosing a setting would slam the panel shut.
        dialog = self.html.split('<dialog id="settings-dialog"', 1)[1]
        dialog = dialog.split("</dialog>", 1)[0]
        self.assertNotIn("<form", dialog)

    def test_every_button_in_the_panel_declares_its_type(self):
        # Without an explicit type a button inside a form is a submit
        # button, and a bare button defaults to submit as well.
        dialog = self.html.split('<dialog id="settings-dialog"', 1)[1]
        dialog = dialog.split("</dialog>", 1)[0]
        for button in re.findall(r"<button[^>]*>", dialog):
            match = re.search(r'id="([^"]+)"', button)
            name = match.group(1) if match else button
            with self.subTest(button=name):
                self.assertIn(
                    'type="',
                    button,
                    f"button #{name} has no explicit type attribute: " + button,
                )

    def test_settings_controls_are_labelled(self):
        # Every range and select needs a label or aria-label, otherwise a
        # screen reader announces only "slider" with no name.
        for control in re.findall(r"<input[^>]*type=\"range\"[^>]*>", self.html):
            match = re.search(r'id="([^"]+)"', control)
            self.assertIsNotNone(match, f"range input has no id: {control}")
            element_id = match.group(1) if match else ""
            with self.subTest(control=element_id):
                self.assertTrue(
                    f'<label for="{element_id}"' in self.html
                    or "aria-label=" in control,
                    f"range input #{element_id} has no label",
                )

        for control in re.findall(r"<select[^>]*>", self.html):
            match = re.search(r'id="([^"]+)"', control)
            self.assertIsNotNone(match, f"select has no id: {control}")
            element_id = match.group(1) if match else ""
            with self.subTest(control=element_id):
                self.assertTrue(
                    f'<label for="{element_id}"' in self.html
                    or "aria-label=" in control,
                    f"select #{element_id} has no label",
                )

    def test_tts_toggle_is_a_switch_with_state(self):
        # role="switch" plus aria-checked is what makes the on/off state
        # announceable; the old markup used aria-pressed on a button that
        # had no visible state.
        self.assertIn('id="tts-toggle"', self.html)
        self.assertIn('role="switch"', self.html)
        self.assertIn("aria-checked=", self.html)
        self.assertIn("aria-checked", self.js)

    def test_removed_topbar_controls_are_not_duplicated(self):
        # The settings that moved into the panel must not still be in the
        # top bar, or there would be two controls fighting over one
        # setting with no obvious source of truth.
        header = self.html.split("<footer", 1)[0]
        for control in ("font-select", "font-size", "theme-select", "focus-mode"):
            with self.subTest(control=control):
                self.assertNotIn(
                    f'id="{control}"',
                    header,
                    f"#{control} is still in the top bar as well as the panel",
                )

    def test_body_carries_the_saved_settings(self):
        # The first paint reads these attributes, so a setting that is
        # saved but not rendered here would only take effect after a
        # reload.
        body_match = re.search(r"<body[^>]*>", self.html)
        self.assertIsNotNone(body_match, "index.html has no <body> tag")
        body_tag = body_match.group(0) if body_match else ""
        for attribute in (
            "data-theme",
            "data-font",
            "data-font-size",
            "data-line-height",
            "data-letter-spacing",
            "data-focus-mode",
            "data-blur-intensity",
            "data-contrast",
            "data-tts-voice",
            "data-tts-rate",
        ):
            with self.subTest(attribute=attribute):
                self.assertIn(f"{attribute}=", body_tag)

    def test_theme_palette_is_not_duplicated_in_javascript(self):
        # The palettes live on the server and are fetched at runtime. A
        # second hardcoded copy in app.js is what let the code colours
        # drift away from the rest of the theme.
        self.assertNotIn("THEME_COLORS", self.js)
        self.assertIn("/api/themes", self.js)

    def test_saved_values_apply_without_a_reload(self):
        # The three settings that used to be stored but never read.
        for token in (
            "--line-height",
            "--letter-spacing",
            "--blur-amount",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.js)

    def test_slider_bounds_match_the_server_ranges(self):
        # If a range is widened on the server but not on the slider, the
        # new value can never be reached from the panel, and the server
        # rejection is never the thing a reader sees.
        for key, (low, high) in routes.CONFIG_RANGES.items():
            # Config keys use underscores; the control ids are hyphenated.
            control_id = key.replace("_", "-")
            with self.subTest(key=key):
                tag = re.search(
                    r'<(?:input|select)[^>]*id="' + control_id + r'"[^>]*>',
                    self.html,
                )
                self.assertIsNotNone(
                    tag, f"no range control for the {key} setting"
                )
                if tag is None:
                    continue
                markup = tag.group(0)
                slider_low = re.search(r'min="([-\d.]+)"', markup)
                slider_high = re.search(r'max="([-\d.]+)"', markup)
                self.assertIsNotNone(slider_low, f"{key} has no min")
                self.assertIsNotNone(slider_high, f"{key} has no max")
                if slider_low is None or slider_high is None:
                    continue
                self.assertEqual(
                    float(slider_low.group(1)),
                    float(low),
                    f"slider min for {key} disagrees with CONFIG_RANGES",
                )
                self.assertEqual(
                    float(slider_high.group(1)),
                    float(high),
                    f"slider max for {key} disagrees with CONFIG_RANGES",
                )

    def test_error_status_is_announced(self):
        # saveConfig reports failures now that the server can reject a
        # setting, and a silent failure is how broken settings survived so
        # long in the first place.
        self.assertIn("aria-live", self.html)
        self.assertIn("reportSaveError", self.js)
        self.assertIn("res.ok", self.js)


class StaticAssetsTests(unittest.TestCase):
    def test_stylesheet_and_script_are_served(self):
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        for path in ("/static/css/style.css", "/static/js/app.js"):
            with self.subTest(path=path):
                response = client.get(path)
                try:
                    self.assertEqual(response.status_code, 200)
                finally:
                    response.close()

    def test_stylesheet_defines_the_settings_panel(self):
        css = (
            REPO_ROOT / "src" / "accessible_ide" / "static" / "css" / "style.css"
        ).read_text(encoding="utf-8")
        self.assertEqual(css.count("{"), css.count("}"), "unbalanced CSS braces")
        for selector in (".settings", ".settings-group", ".switch-track"):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)
        self.assertIn('body[data-contrast="high"]', css)


if __name__ == "__main__":
    unittest.main()
