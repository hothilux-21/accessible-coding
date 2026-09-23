# AccessibleIDE

A fully accessible IDE prioritizing dyslexic & neurodivergent learners, with Python-first support, dyslexia-friendly fonts, configurable focus/blur modes, text-to-speech, and customizable syntax highlighting.

> **Motivation:** Enable dyslexic classmates and neurodivergent learners to code comfortably; driven by empathy and shared experience.

---

## ✨ Key Features

| Category | Features |
|----------|----------|
| **Editor** | Monaco/CodeMirror-based Python editor with syntax highlighting |
| **Execution** | Built-in Python REPL/runner (embedded interpreter) |
| **Fonts** | OpenDyslexic, Atkinson Hyperlegible, Comic Sans, Courier New + custom `.ttf`/`.woff` upload |
| **Focus Mode** | Configurable blur zones: lines, blocks, functions, gutter/line numbers |
| **Themes** | High-contrast, pastel, dark/light presets + full custom theme builder |
| **TTS** | ReciteMe (API) + open-source: pyttsx3, eSpeak-ng, Coqui TTS |
| **Errors** | Plain-English messages, step-by-step debugging, visual highlighting |
| **Storage** | Offline-first (local JSON/TOML), optional Google Drive/OneDrive sync (opt-in) |
| **Platforms** | Browser web app (primary), Windows `.exe` via PyInstaller |

---

## 🎯 MVP Checklist (v0.1)

- [ ] Python code editor (Monaco/CodeMirror)
- [ ] Built-in Python REPL/runner
- [ ] Local file save/load (JSON config)
- [ ] 2–3 preset themes (high contrast, dark, pastel)
- [ ] Dyslexia-friendly font toggle (OpenDyslexic + Atkinson)
- [ ] Focus mode (blur line numbers OR entire gutter)
- [ ] Error messages in plain English
- [ ] Streamlit or Flask web version
- [ ] Windows `.exe` (PyInstaller)
- [ ] GitHub public repo ✅

---

## 🛠 Tech Stack (Decisions Pending)

| Component | Options |
|-----------|---------|
| **Browser Framework** | Streamlit vs Flask/FastAPI |
| **Editor** | Monaco Editor, CodeMirror, or Ace |
| **Desktop Packaging** | PyInstaller (primary), PyO3/Nuitka (future) |
| **Config Format** | JSON or TOML |
| **Deployment** | Vercel, Streamlit Cloud, Railway, Render |

> **Priority:** Reliable uptime > fancy features.

---

## ♿ Accessibility Standards

- **WCAG 2.1 AA** minimum
- Dyslexia-friendly fonts bundled (not downloaded at runtime)
- Plain-language UI copy everywhere
- Full keyboard navigation
- Screen-reader compatible

---

## 📦 Project Structure

```
accessible-coding/
├── .github/workflows/       # CI/CD (to be added)
├── docs/                    # Documentation
├── src/accessible_ide/
│   ├── assets/              # Fonts, static assets
│   ├── components/          # Editor, focus mode, TTS, theme builder UI
│   ├── config/              # JSON/TOML settings load/save
│   └── utils/               # Helpers (error translation, TTS wrappers)
├── tests/                   # Test suite
├── accessible-ide-requirements.md  # Full specification
├── AGENTS.md                # Agent instructions
└── README.md                # This file
```

---

## 🚀 Getting Started (Once Built)

### Browser (Recommended)
```bash
# Visit the deployed site (TBD)
```

### Windows Desktop
```bash
# Download latest .exe from Releases
```

### Development
```bash
git clone https://github.com/hothilux-21/accessible-coding.git
cd accessible-coding
# Setup instructions TBD after stack finalization
```

---

## 📋 Roadmap

| Phase | Target | Highlights |
|-------|--------|------------|
| **v0.1** | ~1 month | Editor + runner + fonts + focus mode + themes + plain errors |
| **v0.2–0.3** | +1–2 months | Custom theme builder, multiple TTS, cloud sync, debugger UI, configurable blur |
| **v1.0+** | Future | Linter, Jupyter, collaboration, plugins, Linux |

See [accessible-ide-requirements.md](accessible-ide-requirements.md) for full specification.

---

## 🤝 Contributing

- **License:** Open source (MIT/GPL/Apache 2.0 — TBD)
- **Core dev:** Solo (owner)
- **External PRs:** Require permission before merging (review-then-merge)
- **Issues/Feedback:** Welcome — especially from dyslexic/neurodivergent users

---

## 📄 Full Specification

See [`accessible-ide-requirements.md`](accessible-ide-requirements.md) for the complete requirements document including:
- Platform & distribution details
- Storage & sync model
- Core IDE features (execution, editor, languages)
- Accessibility features (fonts, TTS, visual, cognitive)
- Technical stack
- Open source & collaboration model
- Timeline & release strategy
- Validation & testing
- User personas
- MVP/Should-Have/Nice-to-Have checklists
- Success metrics
- Resources & references
- Next steps

---

## 📞 Contact

Built with empathy for dyslexic and neurodivergent learners. Feedback and testing help welcome — especially from the target community.