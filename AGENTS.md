# AGENTS.md — AccessibleIDE (Dyslexia IDE)

## Project Overview

AccessibleIDE is a fully accessible, open-source IDE prioritizing dyslexic and neurodivergent learners. Python-first, with dyslexia-friendly fonts, configurable focus/blur modes, text-to-speech, plain-English errors, and customizable syntax highlighting.

- **Authoritative spec:** `accessible-ide-requirements.md` (root) — read this before planning any feature. The MVP feature checklist is in section 10.
- **Status:** Pre-development. The requirements doc was created 2026-09-23; no application code exists yet.

## Repository Layout

```
Dyslexia IDE/
├── AGENTS.md                     # This file
├── accessible-ide-requirements.md # Full requirements & specifications
└── accessible-coding/             # Intended application repository root
    ├── .github/workflows/         # CI (empty — to be added)
    ├── docs/                      # Documentation (empty)
    ├── src/accessible_ide/
    │   ├── assets/                # Fonts (OpenDyslexic, Atkinson Hyperlegible), static assets
    │   ├── components/            # Editor, focus mode, TTS, theme builder UI
    │   ├── config/                # JSON/TOML settings load/save
    │   └── utils/                 # Helpers (error translation, TTS wrappers, etc.)
    └── tests/                     # Test suite (empty)
```

All directories are currently empty scaffolding. Do not assume existing patterns — establish them as code is written.

## Key Constraints (from requirements)

- **MVP target:** ~1 month; ship incrementally (semantic versioning from 0.1.0), not one big v1.
- **Platforms:** Browser web app first, Windows `.exe` (PyInstaller) second; Linux later. Offline-first — all work saved locally.
- **Language support:** Python only for MVP. Multi-language is future work.
- **Stack (open decisions):** Streamlit vs Flask/FastAPI undecided; editor is Monaco, CodeMirror, or Ace — finalize before building the editor.
- **Storage:** Local JSON/TOML config; cloud sync (Google Drive/OneDrive) is optional and opt-in only.
- **Accessibility bar:** WCAG 2.1 AA minimum. Every UI change should be checked against this.
- **License/repo:** Open source (MIT/GPL/Apache 2.0), public GitHub from day 1. Solo development; external PRs require permission and review-then-merge.
- **Priority rule:** Reliable uptime > fancy features.

## Working Agreements

- Prefer plain-language, accessible UI copy everywhere — error messages must be jargon-free English.
- Persist user preferences (fonts, themes, blur config) to the config store; never hardcode them.
- Dyslexia-friendly fonts are bundled, not downloaded at runtime (OpenDyslexic, Atkinson Hyperlegible, plus Comic Sans/Courier New options and user-uploaded `.ttf`/`.woff`).
- Validation is user-feedback-driven: iterate feature → test with dyslexic users → refine → deploy.
- Deployment: push to GitHub and update the hosted site on each feature completion.

## Next Steps (from spec §13)

1. UI mockups (focus mode, theme customizer)
2. Finalize tech stack (Streamlit vs Flask; editor component)
3. Minimal prototype: Python editor + runner
4. TTS integration tests (ReciteMe, pyttsx3, eSpeak-ng, Coqui)
5. Recruit 2–3 dyslexic testers
6. Deploy v0.1 MVP
