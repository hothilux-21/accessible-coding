"""Translations for the AccessibleIDE interface.

Every visible word in the app comes from a JSON catalogue in this folder.
``en.json`` is the reference: it must define every key, and every other
catalogue must define the same keys. ``tests/test_i18n.py`` enforces both,
because a half-translated interface is worse than an untranslated one -- a
reader hits a key they cannot read and has no way to tell it is a
translation gap rather than something about their own code.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

I18N_DIR = Path(__file__).resolve().parent / "i18n"

DEFAULT_LOCALE = "en"

# ``code`` -> (endonym, english name, text direction)
# The endonym is what appears in the language list. A reader looking for
# their language scans for it in their own script, so "Deutsch" is easier
# to find than "German" -- and an Arabic or Hindi reader will not be
# reading either. Direction is carried now even though the layout work
# for RTL is a separate step, so the language data is right from the start.
LANGUAGES: dict[str, tuple[str, str, str]] = {
    "en": ("English", "English", "ltr"),
    "hi": ("हिन्दी", "Hindi", "ltr"),
    "fr": ("Français", "French", "ltr"),
    "es": ("Español", "Spanish", "ltr"),
    "ar": ("العربية", "Arabic", "rtl"),
}

# Sentences that legitimately stay in English regardless of locale, so
# the leftover-English check does not cry wolf on them.
_ALLOWED_ENGLISH = {
    "AccessibleIDE",
    "GitHub",
    "Python",
    "Windows",
    "Ctrl+Enter",
    "Ctrl+Intro",
    "EDI",
    "IDE",
    "sys",
}


class MissingTranslationError(KeyError):
    """Raised when a catalogue is missing a key that English defines."""


# Config keys to the label the reader already sees in Settings. Validation
# messages quote the setting that was rejected, so pointing at the visible
# label keeps the whole sentence in one language -- and stops the error
# naming "code_color" at someone who only ever saw "Code text colour".
CONFIG_LABELS = {
    "font": "reading.font",
    "font_size": "reading.font_size",
    "code_color": "try.colour_label",
    "locale": "language.label",
    "line_height": "reading.line_height",
    "letter_spacing": "reading.letter_spacing",
    "theme": "colours.theme",
    "focus_mode": "focus.mode",
    "blur_intensity": "focus.fade",
    "contrast": "colours.contrast",
    "reduce_motion": "motion.label",
    "tts_enabled": "speak.toggle",
    "tts_engine": "speak.voice",
    "tts_voice": "speak.voice",
    "tts_rate": "speak.rate",
}


@lru_cache(maxsize=None)
def load_catalogue(locale: str) -> dict[str, str]:
    """Return the message catalogue for ``locale``.

    Falls back to English for any key the catalogue does not define, so a
    partially translated language degrades one string at a time rather than
    raising on every render.
    """
    path = I18N_DIR / f"{locale}.json"
    if not path.is_file():
        return dict(load_catalogue(DEFAULT_LOCALE))
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def reference_keys() -> set[str]:
    """Every key English defines. This is the contract the other files meet."""
    return set(load_catalogue(DEFAULT_LOCALE))


def _format(template: str, values: tuple) -> str:
    out = template
    for index, value in enumerate(values):
        out = out.replace("{" + str(index) + "}", str(value))
    return out


def make_translator(locale: str):
    """Build a ``t(key, *args)`` callable bound to one locale."""
    catalogue = load_catalogue(locale)
    fallback = load_catalogue(DEFAULT_LOCALE)

    def t(key: str, *args) -> str:
        text = catalogue.get(key) or fallback.get(key) or key
        return _format(text, args) if args else text

    return t


def available() -> list[tuple[str, str, str, str]]:
    """``(code, endonym, english name, direction)`` for each shipped locale."""
    return [(code, end, eng, direction) for code, (end, eng, direction) in LANGUAGES.items()]


def endonym(locale: str) -> str:
    entry = LANGUAGES.get(locale)
    return entry[0] if entry else locale


def direction(locale: str) -> str:
    entry = LANGUAGES.get(locale)
    return entry[2] if entry else "ltr"


def normalise(value: object) -> str | None:
    """Return ``value`` if it is a supported locale code, else ``None``."""
    if isinstance(value, str) and value in LANGUAGES:
        return value
    return None


def untranslated_keys(locale: str) -> set[str]:
    """Keys English defines that ``locale`` does not."""
    return reference_keys() - set(load_catalogue(locale))


def latin_letters(text: str) -> str:
    return "".join(re.findall(r"[A-Za-z]+", text))


def untranslated_sentences(locale: str) -> dict[str, str]:
    """Strings in ``locale`` that are byte-identical to English.

    A value identical to English is not automatically wrong -- "GitHub",
    "Python" and a handful of others are correct in every language. This
    exists to catch a whole sentence that was copied over by accident, which
    is the failure that actually reaches a reader.
    """
    reference = load_catalogue(DEFAULT_LOCALE)
    catalogue = load_catalogue(locale)
    allowed = _ALLOWED_ENGLISH
    found = {}
    for key, value in catalogue.items():
        if reference.get(key) != value:
            continue
        words = latin_letters(value)
        if value in allowed or words in allowed:
            continue
        # A short shared string (a single word, a number) is not evidence.
        if len(words.split()) < 2 and len(value) < 12:
            continue
        found[key] = value
    return found
