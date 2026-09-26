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
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = str(REPO_ROOT / "src")
if SRC not in sys.path:
    sys.path.append(SRC)

from accessible_ide import create_app, i18n, routes  # noqa: E402

APP_JS = REPO_ROOT / "src" / "accessible_ide" / "static" / "js" / "app.js"
STYLESHEET = (
    REPO_ROOT / "src" / "accessible_ide" / "static" / "css" / "style.css"
)

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
    # The "Try it out" panel.
    "font-bundled-note",
    "sample-text",
    "font-preview",
    "font-preview-text",
    "preview-status",
    "swatches",
    "code-color-hex",
    "code-color-picker",
    "colour-error",
    "btn-reset-colour",
)


def render_index():
    """The page as a reader sees it, in English with default settings.

    routes.py reads the config file as module-level globals, so without the
    swap below this renders whatever the developer last chose on their own
    machine. That made the suite order-dependent: a saved locale of "ar"
    turned the English assertions here into failures that had nothing to do
    with the code under test.
    """
    tmp = tempfile.TemporaryDirectory()
    saved = (routes.CONFIG_DIR, routes.CONFIG_FILE, routes.ACCESS_CODE)
    try:
        routes.CONFIG_DIR = pathlib.Path(tmp.name)
        routes.CONFIG_FILE = routes.CONFIG_DIR / "config.json"
        routes.ACCESS_CODE = ""

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        response = client.get("/")
        assert response.status_code == 200, response.status_code
        return response.get_data(as_text=True)
    finally:
        routes.CONFIG_DIR, routes.CONFIG_FILE, routes.ACCESS_CODE = saved
        tmp.cleanup()


class RenderedPageFixture(unittest.TestCase):
    """Shared setup only. Holding no tests keeps subclasses from
    re-running this whole file's suite."""

    @classmethod
    def setUpClass(cls):
        cls.html = render_index()
        cls.js = APP_JS.read_text(encoding="utf-8")
        cls.css = STYLESHEET.read_text(encoding="utf-8")
        cls.html_ids = set(re.findall(r'id="([^"]+)"', cls.html))


class TemplateContractTests(RenderedPageFixture):
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

    def test_every_spacing_slider_has_a_button_either_side_of_it(self):
        # Dragging a slider thumb is hard with a shaky hand and near
        # impossible behind a screen magnifier. The buttons are a second way
        # in, so each spacing slider needs one that lowers it and one that
        # raises it, and they have to name the slider they drive.
        for key in ("line_height", "letter_spacing"):
            control = key.replace("_", "-")
            for direction, sign in (("less", "-"), ("more", "")):
                button_id = f"{control}-{direction}"
                with self.subTest(button=button_id):
                    tag = re.search(
                        r"<button[^>]*id=\"" + button_id + r"\"[^>]*>",
                        self.html,
                    )
                    self.assertIsNotNone(
                        tag, f"no {direction} button for {key}"
                    )
                    if tag is None:
                        continue
                    markup = tag.group(0)
                    # An explicit type. A button inside a form defaults to
                    # submit, and the settings panel is deliberately not a
                    # form, so this is a habit worth keeping.
                    self.assertIn('type="button"', markup)
                    target = re.search(r'data-target="([^"]+)"', markup)
                    self.assertIsNotNone(
                        target, f"{button_id} does not say which slider it drives"
                    )
                    if target is not None:
                        self.assertEqual(
                            target.group(1),
                            control,
                            f"{button_id} points at the wrong slider",
                        )
                    step = re.search(r'data-step="([-\d.]+)"', markup)
                    self.assertIsNotNone(
                        step, f"{button_id} does not say which way it moves"
                    )
                    if step is not None and sign:
                        self.assertTrue(
                            step.group(1).startswith("-"),
                            f"{button_id} should lower the value",
                        )
                    elif step is not None:
                        self.assertFalse(
                            step.group(1).startswith("-"),
                            f"{button_id} should raise the value",
                        )
                    # The step must be one notch of the slider it drives, or
                    # the buttons move by more than the slider does and the
                    # two disagree about where a value sits.
                    slider_step = re.search(
                        r'<input[^>]*id="' + control + r'"[^>]*step="([\d.]+)"',
                        self.html,
                    )
                    if step is not None and slider_step is not None:
                        self.assertEqual(
                            abs(float(step.group(1))),
                            float(slider_step.group(1)),
                            f"{button_id} moves by a different amount than its slider",
                        )

    def test_the_stepper_buttons_are_labelled_and_their_glyphs_are_not_read_aloud(self):
        # The visible glyph is either a minus or a plus. A screen reader
        # announcing "plus" on its own tells a reader nothing about which
        # setting it belongs to, so the name comes from aria-label and the
        # glyph is hidden from it.
        #
        # The key is read from the template and the text from the rendered
        # page, so this checks both halves: that the button asks for a string
        # that exists, and that the string it gets is real prose rather than
        # an empty attribute.
        template = (
            REPO_ROOT / "src" / "accessible_ide" / "templates" / "index.html"
        ).read_text(encoding="utf-8")
        english = i18n.load_catalogue("en")

        for button_id, key in (
            ("line-height-less", "reading.line_height_less"),
            ("line-height-more", "reading.line_height_more"),
            ("letter-spacing-less", "reading.letter_spacing_less"),
            ("letter-spacing-more", "reading.letter_spacing_more"),
        ):
            with self.subTest(button=button_id):
                source = re.search(
                    r"<button[^>]*id=\"" + button_id + r"\"[^>]*>",
                    template,
                    re.DOTALL,
                )
                self.assertIsNotNone(source)
                if source is not None:
                    self.assertIn(
                        f"t('{key}')",
                        source.group(0),
                        f"{button_id} should be named by {key}",
                    )
                self.assertIn(key, english, f"no English string for {key}")

                rendered = re.search(
                    r"<button[^>]*id=\"" + button_id + r"\"[^>]*>.*?</button>",
                    self.html,
                    re.DOTALL,
                )
                self.assertIsNotNone(rendered)
                if rendered is None:
                    continue
                markup = rendered.group(0)
                label = re.search(r'aria-label="([^"]*)"', markup)
                self.assertIsNotNone(
                    label, f"{button_id} has no name for a screen reader"
                )
                if label is not None:
                    self.assertEqual(
                        label.group(1),
                        english[key],
                        f"{button_id} is not named by {key} in English",
                    )
                self.assertIn(
                    'aria-hidden="true"',
                    markup,
                    f"{button_id} lets the bare glyph be read aloud",
                )

    def test_the_stepper_buttons_are_big_enough_to_hit(self):
        # WCAG 2.1 AA asks for a target of at least 24 by 24 CSS pixels,
        # and 44 is the figure this project works to everywhere else, so a
        # button smaller than that is a miss even though it passes the letter
        # of the standard.
        block = re.search(
            r"\.stepper-btn\s*\{([^}]*)\}", self.css, re.DOTALL
        )
        self.assertIsNotNone(block, "no .stepper-btn rule in the stylesheet")
        if block is None:
            return
        rules = block.group(1)
        for dimension in ("min-width", "min-height"):
            with self.subTest(dimension=dimension):
                declared = re.search(dimension + r":\s*(\d+)px", rules)
                self.assertIsNotNone(
                    declared, f".stepper-btn sets no {dimension}"
                )
                if declared is not None:
                    self.assertGreaterEqual(
                        int(declared.group(1)),
                        44,
                        f".stepper-btn {dimension} is under 44px",
                    )

    def test_error_status_is_announced(self):
        # saveConfig reports failures now that the server can reject a
        # setting, and a silent failure is how broken settings survived so
        # long in the first place.
        self.assertIn("aria-live", self.html)
        self.assertIn("reportSaveError", self.js)
        self.assertIn("res.ok", self.js)


class TryItOutPanelTests(RenderedPageFixture):
    """The font-and-colour test panel."""

    def test_the_panel_sits_inside_the_settings_dialog(self):
        # Outside the dialog it would be unreachable: the dialog is modal
        # and the rest of the page is inert while it is open.
        dialog = self.html.split('<dialog id="settings-dialog"', 1)[1]
        dialog = dialog.split("</dialog>", 1)[0]
        for element_id in ("swatches", "code-color-hex", "font-preview",
                           "btn-reset-colour", "sample-text"):
            with self.subTest(element=element_id):
                self.assertIn(f'id="{element_id}"', dialog)

    def test_font_options_carry_their_own_css_stack(self):
        # app.js reads data-family instead of keeping a second copy of the
        # font stacks. Without it, a font can be listed but not applied -
        # which is how OpenDyslexic shipped broken.
        options = re.findall(r"<option value=\"[^\"]+\"[^>]*>", self.html)
        font_options = [o for o in options if "data-family" in o]
        self.assertEqual(len(font_options), len(routes.FONTS))
        for option in font_options:
            with self.subTest(option=option[:60]):
                self.assertRegex(option, r'data-family="[^"]+"')
                self.assertRegex(option, r'data-bundled="(true|false)"')

    def test_the_swatches_are_a_labelled_radio_group(self):
        # Real radios, so arrow keys, Tab and a screen reader all work
        # without any extra scripting.
        self.assertIn('role="radiogroup"', self.html)
        self.assertIn('aria-labelledby="swatch-label"', self.html)
        self.assertIn('id="swatch-label"', self.html)

        radios = re.findall(r'<input type="radio" name="colour-swatch"[^>]*>', self.html)
        self.assertGreaterEqual(len(radios), 8)
        for radio in radios:
            self.assertRegex(radio, r'value="#[0-9a-fA-F]{6}"')
            # The chip carries the colour; the text below it names it, so
            # the swatch is not identified by colour alone.
            self.assertIn("swatch-chip", self.html)
            self.assertIn("swatch-name", self.html)

    def test_the_colour_field_explains_itself_and_reports_problems(self):
        self.assertIn('for="code-color-hex"', self.html)
        self.assertIn('aria-describedby="colour-help colour-error"', self.html)
        # role="alert" is what makes a screen reader say the problem out
        # loud rather than leaving it sitting there visually.
        self.assertRegex(self.html, r'id="colour-error"[^>]*role="alert"')
        # The error starts hidden; app.js reveals it.
        self.assertRegex(self.html, r'id="colour-error"[^>]*hidden')

    def test_the_preview_is_described_for_a_screen_reader(self):
        self.assertIn('aria-labelledby="preview-label"', self.html)
        self.assertIn('id="preview-label"', self.html)
        self.assertIn('id="preview-status"', self.html)
        # The default sample is the pangram, which exercises every letter.
        self.assertIn("The quick brown fox jumps over the lazy dog", self.html)

    def test_the_colour_picker_is_labelled(self):
        # A bare colour input is announced as just "colour" by most
        # screen readers, which is not enough to tell it apart from the
        # hex field beside it.
        self.assertRegex(
            self.html, r'<input type="color"[^>]*aria-label="[^"]+"')

    def test_the_colour_is_remembered_across_reloads(self):
        # The saved colour has to reach the page on load, or a reader who
        # picks a colour and closes the app loses it. Checked on the
        # rendered page, where Jinja has already substituted the value.
        body = re.search(r"<body[^>]*>", self.html)
        self.assertIsNotNone(body)
        assert body is not None  # narrow the type for checkers
        self.assertIn("data-code-color=", body.group(0))
        self.assertIn("code_color", routes.DEFAULT_CONFIG)
        self.assertIn("code_color", routes.CONFIG_TYPES)

    def test_app_js_restores_the_saved_colour_and_font(self):
        # Both have to be read back from the page on init, or the first
        # paint would show the theme colour and the wrong font for a frame.
        self.assertIn("data-code-color", self.js)
        self.assertIn("customCodeColor = body.getAttribute('data-code-color')", self.js)
        self.assertIn("data-family", self.js)


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


class ReducedMotionCssTests(unittest.TestCase):
    """The stylesheet has to answer the switch in Settings.

    If either rule below goes missing, the switch still looks right and the
    app still moves, which is the worst kind of broken: nothing looks wrong
    and nothing reports an error.
    """

    def setUp(self):
        self.css = (
            REPO_ROOT / "src" / "accessible_ide" / "static" / "css" / "style.css"
        ).read_text(encoding="utf-8")

    def test_the_body_attribute_stops_movement(self):
        self.assertIn("body[data-reduce-motion='true']", self.css)
        block = self.css.split("body[data-reduce-motion='true']", 1)[1]
        block = block[: block.index("}")]
        self.assertIn("transition: none", block)
        self.assertIn("animation: none", block)

    def test_the_operating_system_preference_is_still_honoured(self):
        # This one works with no JavaScript at all, so nothing moves before
        # the first paint. The "unset" qualifier is deliberate: once the
        # reader has answered in Settings, their answer outranks the system.
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        block = self.css.split("@media (prefers-reduced-motion: reduce)", 1)[1]
        block = block[: block.index("}")]
        self.assertIn("transition: none", block)
        self.assertIn("body[data-reduce-motion='unset']", block)
        self.assertNotIn(
            "body[data-reduce-motion='unset']",
            self.css.split("@media (prefers-reduced-motion: reduce)", 1)[0],
            "the media query qualifier is not scoped to the media query",
        )

    def test_pseudo_elements_are_covered_too(self):
        # ::before and ::after are where a decorative rule usually hides,
        # and they animate even when their element does not.
        self.assertIn("body[data-reduce-motion='true'] *::before", self.css)
        self.assertIn("body[data-reduce-motion='true'] *::after", self.css)


if __name__ == "__main__":
    unittest.main()
