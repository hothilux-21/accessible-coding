# AccessibleIDE

A fully accessible IDE for dyslexic and neurodivergent learners.

Python-first. Dyslexia-friendly fonts. Focus mode. Text-to-speech. Plain-English errors. Custom themes.

> **Motivation:** Enable dyslexic classmates and neurodivergent learners to code comfortably; driven by empathy and shared experience.

---

(Sorry guys, but as well as being so vibe-coded, I really wanted a solution. The MD files got pushed and I could close them but ig it's transparency.

- I'm proficient in Python and HTML, CSS and even batch scripting in Windows with several personal security and performance scripts I have made in the past by myself.
- And I've even modded in Android assembly (smali) disassembling .dex (dalvik executable files manually)...
- But I just want to push solutions and fill up my account with repo projects to build my career and make a difference to everyone esp. my friends and classmates.

---

## Contents

Jump to any section:

- [Key features](#key-features)
- [Try it now](#try-it-now)
- [Getting started](#getting-started)
- [Project structure](#project-structure)
- [MVP checklist](#mvp-checklist)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Full specification](#full-specification)
- [Contact](#contact)

---

## Key features

- **Editor** — CodeMirror Python editor with syntax highlighting
- **Execution** — built-in Python runner (10-second safety timeout)
- **Fonts** — OpenDyslexic, Atkinson Hyperlegible, Comic Sans, Courier New
- **Focus mode** — hide the gutter, or blur every line except the one you are on
- **Themes** — high contrast, dark, pastel, and light
- **Text-to-speech** — reads your code and errors aloud
- **Errors** — plain-English messages, no jargon
- **Storage** — offline-first, settings saved to your computer
- **Platforms** — browser web app and Windows `.exe`

[↑ Back to contents](#contents)

---

## Try it now

- **Web app:** [https://accessible-coding.onrender.com](https://accessible-coding.onrender.com)
- **Windows exe:** download `AccessibleIDE.exe` from the [Releases page](https://github.com/hothilux-21/accessible-coding/releases)

[↑ Back to contents](#contents) · [↓ Next: Getting started](#getting-started)

---

## Getting started

### Windows desktop (.exe)

1. Download `AccessibleIDE.exe` from the [latest build](https://github.com/hothilux-21/accessible-coding/releases/latest/download/AccessibleIDE.exe) (always matches the web app)
2. Double-click to run. Your browser opens with the IDE.
3. Write Python, then press **Run** (or `Ctrl+Enter`).

### Browser (web)

Open [https://accessible-coding.onrender.com](https://accessible-coding.onrender.com). No install needed.

### Development

```bash
git clone https://github.com/hothilux-21/accessible-coding.git
cd accessible-coding
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000

### Build the exe yourself

```bash
pip install pyinstaller
pyinstaller AccessibleIDE.spec --noconfirm
```

Your exe is at `dist/AccessibleIDE.exe`.

### Run tests

```bash
python smoke_test.py
```

[↑ Back to contents](#contents) · [↓ Next: Project structure](#project-structure)

---

## Project structure

```
accessible-coding/
├── .github/workflows/       # CI: tests + exe build on release tags
├── docs/                    # Documentation
├── src/accessible_ide/
│   ├── assets/              # Fonts (OpenDyslexic, Atkinson Hyperlegible)
│   ├── static/              # CSS + JavaScript (CodeMirror, app logic)
│   ├── templates/           # HTML page
│   ├── config/              # Settings load/save
│   └── utils/               # Helpers (error translation)
├── tests/                   # Test suite
├── accessible-ide-requirements.md  # Full specification
├── AGENTS.md                # Agent instructions
└── README.md                # This file
```

[↑ Back to contents](#contents) · [↓ Next: MVP checklist](#mvp-checklist)

---

## MVP checklist

What is done in v0.1.0-beta:

- [x] Python code editor (CodeMirror)
- [x] Built-in Python runner
- [x] Local settings save/load (JSON)
- [x] 4 preset themes (high contrast, dark, pastel, light)
- [x] Dyslexia-friendly font toggle (OpenDyslexic + Atkinson Hyperlegible)
- [x] Focus mode (hide gutter / blur other lines)
- [x] Error messages in plain English
- [x] Flask web version
- [x] Windows `.exe` (PyInstaller)
- [x] GitHub public repo

Coming next (v0.2):

- [ ] Save and open code files
- [ ] Custom theme builder
- [ ] More text-to-speech options
- [ ] Visual error highlighting in the editor
- [ ] Configurable blur zones (blocks, functions)

[↑ Back to contents](#contents) · [↓ Next: Roadmap](#roadmap)

---

## Roadmap

- **v0.1 (now)** — editor, runner, fonts, focus mode, themes, plain errors
- **v0.2** — custom themes, more TTS, file save/open, visual error highlighting
- **v1.0+** — linter, Jupyter, collaboration, plugins, Linux

See the [full specification](#full-specification) for details.

[↑ Back to contents](#contents) · [↓ Next: Contributing](#contributing)

---

## Contributing

- **License:** MIT — free to use, modify, and fork
- **Core development:** solo (owner)
- **External pull requests:** please ask first. Changes are reviewed before merging.
- **Feedback:** very welcome, especially from dyslexic and neurodivergent users.

[↑ Back to contents](#contents) · [↓ Next: Full specification](#full-specification)

---

## Full specification

The complete requirements document is at [accessible-ide-requirements.md](accessible-ide-requirements.md).

It covers:

- Platform and distribution
- Storage and sync model
- Core IDE features
- Accessibility features (fonts, TTS, visual, cognitive)
- Technical stack
- Open source and collaboration model
- Timeline and release strategy
- Validation and testing
- User personas
- Feature checklists
- Success metrics
- Resources and references
- Next steps

[↑ Back to contents](#contents) · [↓ Next: Contact](#contact)

---

## Contact

Built with empathy for dyslexic and neurodivergent learners.

Feedback and testing help are always welcome — especially from the people this is for.

[↑ Back to contents](#contents)

---

*AccessibleIDE — code comfortably.*