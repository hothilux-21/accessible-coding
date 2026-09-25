"""Checks on the plain-language explanations for Python errors.

These sentences are the ones a learner actually reads when their code does
not work, and they used to be English-only strings inside routes.py. They now
come from the catalogues, so the tests have two jobs: the English wording
must not drift while it is being translated, and no exception type may be
added without a translation to offer.

Run with:  PYTHONPATH=src python -m unittest discover -s tests -t .
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = str(REPO_ROOT / "src")
if SRC not in sys.path:
    sys.path.append(SRC)

from accessible_ide import i18n, routes  # noqa: E402

# The English wording, pinned. If a change to this file makes one of these
# fail, the change is to the explanation, not to the test - and a change to
# the wording has to be a deliberate one.
EXPECTED_ENGLISH = {
    "SyntaxError": "There's a syntax error in your code. Check for missing parentheses, brackets, or quotes.",
    "IndentationError": "Indentation error. Python uses spaces to group code blocks. Make sure your indentation is consistent.",
    "NameError": "You're using a variable or function name that hasn't been defined yet.",
    "TypeError": "You're trying to do something with the wrong type of data (like adding text to a number).",
    "ValueError": "A function received a value of the right type but an inappropriate value.",
    "IndexError": "You're trying to access an index that doesn't exist in a list or string.",
    "KeyError": "You're trying to access a dictionary key that doesn't exist.",
    "AttributeError": "You're trying to use an attribute or method that doesn't exist on this object.",
    "ImportError": "Python can't find the module you're trying to import.",
    "ModuleNotFoundError": "The module you're trying to import isn't installed.",
    "ZeroDivisionError": "You're dividing by zero, which isn't allowed.",
    "FileNotFoundError": "The file you're trying to open doesn't exist.",
    "PermissionError": "You don't have permission to access this file.",
    "RecursionError": "Your function is calling itself too many times (infinite recursion).",
    "MemoryError": "Your program ran out of memory.",
    "KeyboardInterrupt": "The program was interrupted (Ctrl+C).",
    "EOFError": "Unexpected end of input.",
}

TRACEBACK = (
    'Traceback (most recent call last):\n'
    '  File "C:\\Temp\\abc.py", line 7, in <module>\n'
    '    x = 1 / 0\n'
    'ZeroDivisionError: division by zero\n'
)


class EnglishWordingTests(unittest.TestCase):
    def test_every_exception_explains_itself_in_plain_english(self):
        for name, expected in EXPECTED_ENGLISH.items():
            with self.subTest(exception=name):
                traceback = f'Traceback (most recent call last):\n{name}: whatever\n'
                message, _ = routes.translate_error(traceback)
                self.assertEqual(message, expected)

    def test_the_list_of_explained_exceptions_has_not_shrunk(self):
        # Guards against a refactor quietly dropping a type someone relies on.
        self.assertEqual(
            list(EXPECTED_ENGLISH),
            list(routes.PYTHON_ERROR_KEYS),
        )

    def test_the_line_number_is_offered_with_the_explanation(self):
        message, line = routes.translate_error(TRACEBACK)
        self.assertEqual(line, 7)
        self.assertIn("around line 7", message)
        self.assertTrue(message.startswith(EXPECTED_ENGLISH["ZeroDivisionError"]))

    def test_an_unrecognised_error_still_reaches_the_reader(self):
        message, line = routes.translate_error("SomeNewError: no idea")
        self.assertEqual(line, None)
        self.assertEqual(message, "Error: SomeNewError: no idea")

    def test_no_output_gives_a_calm_answer(self):
        # A blank traceback is what a reader sees when the program dies
        # without saying why. "Error: " on its own tells them nothing.
        for blank in ("", "   ", "\n\n"):
            with self.subTest(traceback=repr(blank)):
                message, line = routes.translate_error(blank)
                self.assertEqual(line, None)
                self.assertEqual(message, "An unknown error occurred.")


class TranslationTests(unittest.TestCase):
    def test_the_explanation_follows_the_readers_language(self):
        expected = {
            "fr": "Vous divisez par zéro, ce qui n'est pas possible.",
            "es": "Estás dividiendo entre cero, lo cual no está permitido.",
            "hi": "आप किसी संख्या को शून्य से भाग दे रहे हैं, जो संभव नहीं है।",
            "ar": "أنت تقسم على صفر، وهذا غير مسموح به.",
        }
        for code, sentence in expected.items():
            with self.subTest(locale=code):
                say = i18n.make_translator(code)
                message, line = routes.translate_error(TRACEBACK, say)
                self.assertTrue(
                    message.startswith(sentence),
                    f"{code} gave {message!r}",
                )
                self.assertEqual(line, 7, "the line number is language-neutral")

    def test_the_line_hint_is_localized_too(self):
        # "around line 7" is part of the sentence, so it has to change with
        # the rest of it rather than leaving English in the middle.
        say = i18n.make_translator("fr")
        message, _ = routes.translate_error(TRACEBACK, say)
        self.assertIn("environ line 7", message)
        self.assertNotIn("around", message)

    def test_every_explained_exception_is_translated_everywhere(self):
        for name in routes.PYTHON_ERROR_KEYS:
            key = f"python.{name}"
            for code in i18n.LANGUAGES:
                with self.subTest(key=key, locale=code):
                    say = i18n.make_translator(code)
                    traceback = f'Traceback (most recent call last):\n{name}: x\n'
                    message, _ = routes.translate_error(traceback, say)
                    self.assertEqual(message, i18n.load_catalogue(code)[key])
                    if code != "en":
                        self.assertNotEqual(
                            message,
                            EXPECTED_ENGLISH[name],
                            f"{key} is still English in {code}",
                        )

    def test_the_helper_keys_exist_in_every_catalogue(self):
        for key in ("python.unknown", "python.fallback", "python.line_hint"):
            for code in i18n.LANGUAGES:
                with self.subTest(key=key, locale=code):
                    self.assertIn(key, i18n.load_catalogue(code))


if __name__ == "__main__":
    unittest.main()
