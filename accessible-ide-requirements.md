# AccessibleIDE — Project Requirements & Specifications

**Project Goal:** Build a fully accessible IDE prioritizing dyslexic & neurodivergent learners, with Python-first support, dyslexia-friendly fonts, configurable focus/blur modes, text-to-speech, and customizable syntax highlighting.

**Motivation:** Enable dyslexic classmates and neurodivergent learners to code comfortably; driven by empathy and shared experience.

---

## 1. Platform & Distribution

| Aspect | Requirement |
|--------|-------------|
| **Primary Platform** | Browser-based web app (Streamlit, Vercel, or similar) |
| **Secondary Platform** | Windows .exe desktop (PyInstaller or equivalent) |
| **Hosting** | Free, reliable service with guaranteed uptime (Vercel, Streamlit Cloud, Railway, etc.) |
| **Linux Support** | Secondary priority; focus browser + Windows exe first |
| **Offline Capability** | Offline-first architecture; all work saved locally |

---

## 2. Storage & Sync Model

| Aspect | Requirement |
|--------|-------------|
| **Local Storage** | JSON or TOML config files saved to disk |
| **Cloud Sync** | Optional: Google Drive or OneDrive (user opt-in) |
| **Sync Scope** | Projects + settings only; no auto-sync |
| **Auth** | Google/OneDrive login to carry settings across devices |
| **Export/Import** | Manual config file export/import supported |

---

## 3. Core IDE Features

### 3.1 Execution & Debugging
- **Built-in Python Interpreter:** Embedded (not external runner)
- **Full IDE Suite:** Runner + debugger + interpreter + compiler
- **Error Presentation:** 
  - Plain English error messages
  - Step-by-step debugging mode
  - Visual error highlighting
  - All three methods available

### 3.2 Editor & Syntax Highlighting
- **Syntax Highlighting Options:**
  - Preset accessible palettes (high contrast, pastel, etc.)
  - Full custom theme builder (user-editable colors)
  - Dark mode + light mode
  - Custom highlight colors per language/token type
- **Focus Mode (Blur):**
  - Configurable blur zones: line ranges, code blocks, functions, line numbers/gutter
  - User can blur around focused code if enabled
  - Fully customizable blur behavior per session

### 3.3 Supported Languages
- **Primary:** Python
- **Future:** Multi-language support (JavaScript, etc.), but Python-first MVP

### 3.4 Target Users
- All skill levels: beginners, intermediate learners, professionals

---

## 4. Accessibility Features

### 4.1 Dyslexia-Friendly Fonts
- **Bundled Fonts:**
  - OpenDyslexic
  - Atkinson Hyperlegible
  - Comic Sans (option)
  - Courier New (accessible monospace)
  - Plus options to upload custom fonts (.ttf/.woff)
- **Font Customization:** Size, weight, line-height, letter-spacing all adjustable
- **Font Onboarding Flow:**
  1. **First Launch:** Simple popup: "Pick your font"
  2. **Font Selector UI:** Radio buttons or dropdown showing each bundled font with live preview sample
  3. **Live Preview:** Show code snippet in selected font (before committing choice)
  4. **Custom Font Option:** "Upload my own font" button (drag-drop or file picker)
  5. **Save to Config:** Selected font persists in JSON/TOML; auto-load on next session
  6. **Easy Switch:** Settings menu allows font change anytime without restarting
  7. **Accessibility:** Font selector screen readable; voice-over compatible

- **Syntax Highlighting + Font Blur Integration:**
  - User can blur syntax highlighting colors AROUND focused code while keeping font readable
  - E.g., blur dim non-focus keywords while sharp-focus on active function name
  - Example config: `"blur": {"function_scope": true, "blur_gutter": true, "keep_syntax_sharp": false}`

### 4.2 Text-to-Speech (TTS)
- **Primary Option:** ReciteMe (if accessible API available)
- **Open-Source Alternatives:** Multiple free options with descriptions
  - pyttsx3
  - espeak
  - Coqui TTS (or similar)
  - eSpeak-ng
- **User Selection:** Users can choose & download TTS engine; descriptions provided for each
- **Integration:** TTS can read code aloud, error messages, comments

### 4.3 Visual Accessibility
- **High Contrast Themes:** Built-in
- **Pastel/Soft Palettes:** For low-light/sensitive users
- **Dark/Light Mode Toggle:** User preference
- **Color Customization:** Full theme maker for syntax highlighting

### 4.4 Cognitive Accessibility
- **Focus Mode:** Blur non-essential UI; keep code center-stage
- **Plain Language:** Error messages in simple, jargon-free English
- **Step-by-Step Debugging:** Not wall-of-text, but guided walkthrough

---

## 5. Technical Stack

| Component | Technology |
|-----------|-----------|
| **Browser App** | Python (Flask/FastAPI/Streamlit) + Frontend (HTML/CSS/JS or React) |
| **Desktop (Windows exe)** | Python + PyInstaller (or PyO3 for Rust backend if needed) |
| **Version Control** | Git + GitHub (public repo from day 1) |
| **Config Format** | JSON or TOML |
| **Editor Component** | Monaco Editor, CodeMirror, or Ace (accessible, themeable) |

**Priority:** Reliable uptime > fancy features.

---

## 6. Open Source & Collaboration Model

| Aspect | Requirement |
|--------|-------------|
| **License** | Open source & free to modify/fork (MIT, GPL, or Apache 2.0) |
| **Repository** | Public GitHub from day 1 |
| **Core Development** | Solo (yourself) |
| **Internal Collaboration** | Classmate feedback via Discord/email (no repo access initially) |
| **Trusted Collaborators** | May grant repo access on case-by-case basis |
| **External Contributors** | Pull request workflow; require permission before merging |
| **Contribution Process** | Review-then-merge; contributors request permission first |

---

## 7. Timeline & Release Strategy

| Aspect | Requirement |
|--------|-------------|
| **MVP Target** | 1 month (bare minimum working version) |
| **Release Cadence** | Incremental feature releases (not waiting for "v1 stable") |
| **Deployment** | Push to GitHub + update hosted site on each feature completion |
| **Version Numbering** | Semantic versioning (0.1.0 → 0.2.0 → 1.0.0) |

---

## 8. Validation & Testing

| Aspect | Requirement |
|--------|-------------|
| **Primary Validation** | User feedback from dyslexic testers (iterative) |
| **Testing Method** | Gather feedback from classmates & real dyslexic users |
| **Iteration Loop** | Feature → test with users → feedback → refine → deploy |
| **Accessibility Audit** | Review against WCAG 2.1 guidelines (minimum AA level) |

---

## 9. User Personas

### 9.1 Primary: Dyslexic Student (Python Learning)
- Struggles with standard IDE cognitive load
- Needs font customization, focus mode, text-to-speech
- Learning Python for school/CS degree
- Values offline capability; wants cloud backup option

### 9.2 Secondary: Neurodivergent Learner (General)
- ADHD, dyspraxia, processing differences
- Benefits from focus mode, high contrast, customizable UI
- May use external TTS or screen readers
- Wants simple, uncluttered interface

### 9.3 Tertiary: Educator (Teaching Accessibility)
- Uses IDE to teach Python to diverse learners
- Appreciates open-source nature (can customize for class)
- Wants easy setup (one-click browser or .exe)

---

## 10. MVP Feature Checklist

### Must-Have (v0.1)
- [ ] Python code editor (Monaco/CodeMirror)
- [ ] Built-in Python REPL/runner
- [ ] Local file save/load (JSON config)
- [ ] 2–3 preset themes (high contrast, dark, pastel)
- [ ] Dyslexia-friendly font toggle (OpenDyslexic + Atkinson)
- [ ] Focus mode (blur line numbers OR entire gutter)
- [ ] Error messages in plain English
- [ ] Streamlit or Flask web version
- [ ] Windows .exe (PyInstaller)
- [ ] GitHub public repo

### Should-Have (v0.2–0.3)
- [ ] Custom theme builder
- [ ] Multiple TTS options (ReciteMe + 2 open-source)
- [ ] Google Drive/OneDrive sync (optional login)
- [ ] Step-by-step debugger UI
- [ ] Visual error highlighting
- [ ] Configurable blur zones (blocks, functions)
- [ ] Multi-language syntax (JS, etc.)

### Nice-to-Have (v1.0+)
- [ ] Linter integration
- [ ] Jupyter Notebook compatibility
- [ ] Collaborative editing
- [ ] Plugin ecosystem
- [ ] Linux .AppImage

---

## 11. Success Metrics

1. **Accessibility:** Dyslexic users report reduced cognitive load when using focus mode + font customization.
2. **Usability:** Time-to-first-run < 2 minutes (browser or exe).
3. **Adoption:** 10+ GitHub stars + 2–3 active external contributors within 3 months.
4. **Uptime:** Browser version maintains 99%+ uptime.
5. **Community:** Positive feedback from dyslexic testers; feature requests received & prioritized.

---

## 12. Resources & References

- **Dyslexia-Friendly Fonts:** OpenDyslexic (free), Atkinson Hyperlegible (free)
- **Python REPL Options:** IPython, built-in `code` module, Jupyter kernel
- **Editor Components:** Monaco (VSCode-based), CodeMirror (lightweight), Ace (customizable)
- **Deployment:** Streamlit Cloud, Vercel, Railway, Render
- **Desktop Packaging:** PyInstaller, PyO3, Nuitka
- **TTS Engines:** pyttsx3, eSpeak, Coqui TTS, ReciteMe (API)
- **Accessibility Standards:** WCAG 2.1, W3C ARIA guidelines

---

## 13. Next Steps

1. **Design Phase:** Sketch UI mockups (focus mode wireframes, theme customizer)
2. **Tech Stack Finalization:** Choose Streamlit vs Flask; decide on editor component
3. **Prototype:** Build minimal Python editor + runner in chosen framework
4. **TTS Integration:** Test ReciteMe + open-source alternatives
5. **User Testing:** Recruit 2–3 dyslexic testers; gather initial feedback
6. **Release:** Deploy v0.1 (MVP) to GitHub + Streamlit Cloud/Vercel
7. **Iterate:** Push updates monthly; prioritize user feedback

---

**Document Created:** 2026-09-23  
**Status:** Ready for development planning  
**Owner:** You  
**Repository:** (To be created on GitHub)
