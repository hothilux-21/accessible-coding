"""Checks that every bundled font is a real font.

OpenDyslexic shipped for several releases as two saved HTML web pages
named ".otf". The browser refused them, the @font-face silently failed,
the stack fell through to the generic `cursive` family, and the server
answered 200 the whole time - so the flagship accessibility font was
simply absent and nothing failed loudly.

These tests check the bytes, not the filename or the HTTP status.
"""

import pathlib
import re
import struct
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = str(REPO_ROOT / "src")
if SRC not in sys.path:
    sys.path.append(SRC)

from accessible_ide import create_app, routes  # noqa: E402

FONT_DIR = REPO_ROOT / "src" / "accessible_ide" / "assets" / "fonts"
TEMPLATE = REPO_ROOT / "src" / "accessible_ide" / "templates" / "index.html"

# Leading bytes of each real font container format.
FONT_MAGIC = {
    b"\x00\x01\x00\x00": "TrueType",
    b"OTTO": "CFF/OpenType",
    b"ttcf": "TrueType Collection",
    b"wOFF": "WOFF",
    b"wOF2": "WOFF2",
}


def embedded_family_name(path):
    """Read the family name out of a TrueType/OpenType name table."""
    data = path.read_bytes()
    if data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"ttcf"):
        return None

    start = struct.unpack(">I", data[12:16])[0] if data[:4] == b"ttcf" else 0
    num_tables = struct.unpack(">H", data[start + 4 : start + 6])[0]

    name_offset = 0
    for index in range(num_tables):
        entry = start + 12 + index * 16
        if data[entry : entry + 4] == b"name":
            name_offset = struct.unpack(">I", data[entry + 8 : entry + 12])[0]
            break
    if not name_offset:
        return None

    count, string_offset = struct.unpack(
        ">HH", data[name_offset + 2 : name_offset + 6]
    )
    found = {}
    for index in range(count):
        record = name_offset + 6 + index * 12
        platform, _enc, _lang, name_id, length, offset = struct.unpack(
            ">HHHHHH", data[record : record + 12]
        )
        if name_id not in (1, 16):
            continue
        raw = data[name_offset + string_offset + offset :][:length]
        try:
            value = raw.decode("utf-16-be") if platform == 3 else raw.decode("latin-1")
        except UnicodeDecodeError:
            continue
        value = value.strip("\x00").strip()
        if value and (name_id not in found or platform == 3):
            found[name_id] = value
    return found.get(16) or found.get(1)


class BundledFontTests(unittest.TestCase):
    def test_every_font_file_is_really_a_font(self):
        fonts = [
            path
            for path in sorted(FONT_DIR.iterdir())
            if path.suffix.lower() in (".ttf", ".otf", ".woff", ".woff2")
        ]
        self.assertTrue(fonts, "no font files found at all")

        for path in fonts:
            with self.subTest(font=path.name):
                head = path.read_bytes()[:4]
                self.assertIn(
                    head,
                    FONT_MAGIC,
                    f"{path.name} is not a font: it starts with {head!r}. "
                    f"It is {path.stat().st_size} bytes and begins "
                    f"{path.read_bytes()[:60]!r}",
                )

    def test_fonts_are_not_trivially_small(self):
        # A real font is tens of kilobytes. A stub or an error page that
        # somehow passed the magic-byte check is still wrong.
        for path in sorted(FONT_DIR.iterdir()):
            if path.suffix.lower() not in (".ttf", ".otf", ".woff", ".woff2"):
                continue
            with self.subTest(font=path.name):
                self.assertGreater(path.stat().st_size, 2000)

    def test_font_family_names_match_the_css(self):
        # The @font-face family name has to match the family inside the
        # file, or the browser downloads the font and then refuses to use
        # it. This is the second half of the OpenDyslexic failure.
        css = TEMPLATE.read_text(encoding="utf-8")
        declared = set(re.findall(r"font-family:\s*'([^']+)'\s*;", css))
        declared |= set(re.findall(r"font-family:\s*'([^']+)',", css))
        self.assertTrue(declared, "no @font-face families found in the template")

        for path in sorted(FONT_DIR.iterdir()):
            if path.suffix.lower() not in (".ttf", ".otf"):
                continue
            with self.subTest(font=path.name):
                family = embedded_family_name(path)
                self.assertIsNotNone(family, f"could not read a family name")
                self.assertIn(
                    family,
                    declared,
                    f"{path.name} contains family {family!r}, which no "
                    f"@font-face declares. Declared: {sorted(declared)}",
                )

    def test_every_listed_font_file_exists(self):
        for key, font in routes.FONTS.items():
            for filename in font["files"]:
                with self.subTest(font=key, file=filename):
                    self.assertTrue(
                        (FONT_DIR / filename).exists(),
                        f"{key} lists {filename}, which is not in {FONT_DIR}",
                    )

    def test_font_families_never_fall_back_to_cursive(self):
        # `cursive` is the browser's handwriting-ish generic. As the last
        # item in a code editor's stack it makes the code very hard to
        # read, and it is what OpenDyslexic silently degraded to.
        for key, font in routes.FONTS.items():
            with self.subTest(font=key):
                last = [part.strip() for part in font["family"].split(",")][-1]
                self.assertNotEqual(last, "cursive")

    def _stack_parts(self, key):
        """The families in a stack, with the CSS quoting removed."""
        return [
            part.strip().strip("'\"")
            for part in routes.FONTS[key]["family"].split(",")
        ]

    def test_every_stack_carries_both_script_fallbacks(self):
        # Mukta carries the Devanagari for Hindi, Almarai the Arabic. They
        # sit in every stack rather than being separate choices, so a reader
        # who picked OpenDyslexic for its Latin still gets readable Hindi
        # instead of boxes.
        for key in routes.FONTS:
            with self.subTest(font=key):
                parts = self._stack_parts(key)
                self.assertIn("Mukta", parts, f"{key} cannot render Devanagari")
                self.assertIn("Almarai", parts, f"{key} cannot render Arabic")

    def test_script_fallbacks_come_after_the_chosen_font(self):
        # The reader's pick has to win for the script it covers. Mukta and
        # Almarai are fallbacks, not overrides.
        for key in routes.FONTS:
            with self.subTest(font=key):
                parts = self._stack_parts(key)
                first_fallback = min(parts.index("Mukta"), parts.index("Almarai"))
                for chosen in parts[:first_fallback]:
                    self.assertNotIn(chosen, ("Mukta", "Almarai"))
                self.assertIn(
                    parts[-1],
                    ("sans-serif", "monospace"),
                    "the stack must still end in a generic family",
                )

    def test_every_bundled_font_is_referenced_by_the_template(self):
        # A font file nobody loads is dead weight in an offline app: it
        # still has to be shipped, downloaded on install, and licence-
        # audited forever. Mukta-ExtraLight sat in the folder for exactly
        # this reason - nothing asks the stack for weight 200.
        css = TEMPLATE.read_text(encoding="utf-8")
        referenced = set(re.findall(r"filename='([^']+)'", css))
        for path in sorted(FONT_DIR.iterdir()):
            if path.suffix.lower() not in (".ttf", ".otf"):
                continue
            with self.subTest(font=path.name):
                self.assertIn(
                    path.name,
                    referenced,
                    f"{path.name} is bundled but no @font-face loads it",
                )

    def test_fonts_endpoint_matches_the_served_files(self):
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        response = client.get("/api/fonts")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(sorted(response.get_json()), sorted(routes.FONTS))
        finally:
            response.close()

        # Every font the app claims to bundle must actually be served, and
        # must arrive as font bytes rather than an error page.
        for key, font in routes.FONTS.items():
            for filename in font["files"]:
                with self.subTest(font=key, file=filename):
                    served = client.get(f"/assets/fonts/{filename}")
                    try:
                        self.assertEqual(served.status_code, 200)
                        self.assertIn(
                            served.data[:4],
                            FONT_MAGIC,
                            f"/assets/fonts/{filename} did not return a font",
                        )
                        # Python has no .ttf entry in mimetypes on Windows,
                        # so this has to be asked for explicitly or the font
                        # arrives as application/octet-stream.
                        self.assertEqual(
                            served.mimetype,
                            routes.FONT_MIME_TYPES[pathlib.Path(filename).suffix.lower()],
                        )
                    finally:
                        served.close()


class FontLicensingTests(unittest.TestCase):
    """What the repository is allowed to ship, and what it must not."""

    # Calibri and Arial belong to Microsoft. Bundling them in an
    # open-source project would be a licence breach and would put the
    # public repository at risk, so they are referenced, never shipped.
    PROPRIETARY = {"calibri", "arial", "comic sans ms", "courier new"}

    def test_no_proprietary_font_is_bundled(self):
        for key, font in routes.FONTS.items():
            if key.lower() in self.PROPRIETARY:
                with self.subTest(font=key):
                    self.assertEqual(
                        font["files"],
                        [],
                        f"{key} is a Microsoft font and must not be bundled",
                    )
                    self.assertFalse(font["bundled"])

    def test_system_fonts_are_labelled_as_not_bundled(self):
        for key, font in routes.FONTS.items():
            with self.subTest(font=key):
                # files and bundled have to agree, or the settings panel
                # will tell the reader a font is included when it is not.
                self.assertEqual(bool(font["files"]), font["bundled"])

    def test_every_bundled_font_ships_its_licence(self):
        licences = FONT_DIR / "licenses"
        self.assertTrue(licences.is_dir(), "no licences folder")

        # Matched on the font's own name, not the file name: the file is
        # OpenDyslexic3-Bold.ttf but its licence file is
        # opendyslexic-ofl.txt, and the version suffix is the kind of
        # detail that should not decide a licensing check.
        present = [
            "".join(char for char in path.name.lower() if char.isalnum())
            for path in licences.iterdir()
        ]
        for key, font in routes.FONTS.items():
            if not font["bundled"]:
                continue
            expected = "".join(char for char in key.lower() if char.isalnum())
            with self.subTest(font=key):
                self.assertTrue(
                    any(name.startswith(expected) for name in present),
                    f"{key} is bundled but has no licence file in {licences}. "
                    f"Found: {sorted(present)}",
                )

    def test_a_licence_file_is_not_empty(self):
        licences = FONT_DIR / "licenses"
        for path in sorted(licences.iterdir()):
            with self.subTest(licence=path.name):
                self.assertGreater(path.stat().st_size, 500)
                self.assertIn("Copyright", path.read_text(encoding="utf-8", errors="ignore"))


if __name__ == "__main__":
    unittest.main()
