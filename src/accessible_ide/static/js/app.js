/* ============================================================
   AccessibleIDE - Frontend logic
   CodeMirror editor, code runner, config persistence, TTS
   ============================================================ */

(function () {
  'use strict';

  // ---------- Elements ----------
  var editorEl = document.getElementById('editor');
  var outputEl = document.getElementById('output');
  var errorPanel = document.getElementById('error-panel');
  var errorMessage = document.getElementById('error-message');
  var btnRun = document.getElementById('btn-run');
  var btnClear = document.getElementById('btn-clear');
  var btnTts = document.getElementById('tts-toggle');
  var btnSave = document.getElementById('btn-save');
  var btnOpen = document.getElementById('btn-open');
  var btnReadLine = document.getElementById('btn-read-line');
  var fileInput = document.getElementById('file-input');
  var fontSelect = document.getElementById('font-select');
  var fontSize = document.getElementById('font-size');
  var fontSizeLabel = document.getElementById('font-size-label');
  var lineHeight = document.getElementById('line-height');
  var lineHeightLabel = document.getElementById('line-height-label');
  var letterSpacing = document.getElementById('letter-spacing');
  var letterSpacingLabel = document.getElementById('letter-spacing-label');
  var blurIntensity = document.getElementById('blur-intensity');
  var blurIntensityLabel = document.getElementById('blur-intensity-label');
  var blurField = document.getElementById('blur-field');
  var themeSelect = document.getElementById('theme-select');
  var contrastSelect = document.getElementById('contrast-select');
  var focusMode = document.getElementById('focus-mode');
  var ttsVoice = document.getElementById('tts-voice');
  var ttsRate = document.getElementById('tts-rate');
  var ttsRateLabel = document.getElementById('tts-rate-label');
  var ttsState = document.getElementById('tts-state');
  var btnTestVoice = document.getElementById('btn-test-voice');
  var settingsDialog = document.getElementById('settings-dialog');
  var btnSettings = document.getElementById('btn-settings');
  var btnSettingsClose = document.getElementById('btn-settings-close');
  var settingsStatus = document.getElementById('settings-status');
  var btnQuit = document.getElementById('btn-quit');

  var body = document.body;
  var ttsEnabled = btnTts.getAttribute('aria-checked') === 'true';
  var accessCode = localStorage.getItem('accessible_ide_code') || '';
  var settingsOpener = null;
  var speechRate = 0.9;
  var speechVoiceName = '';

  // The blur slider only means something while the "fade the other
  // lines" focus mode is on, so it is disabled rather than hidden -
  // hidden would make the panel jump around as you switch modes.
  function syncBlurField() {
    blurField.classList.toggle('is-disabled', focusMode.value !== 'lines');
    blurIntensity.disabled = focusMode.value !== 'lines';
  }

  function promptForAccessCode() {
    var code = window.prompt('This site is protected. Enter the access code:');
    if (code) {
      accessCode = code;
      localStorage.setItem('accessible_ide_code', code);
      return true;
    }
    return false;
  }

  // ---------- CodeMirror setup ----------
  var editor = CodeMirror(editorEl, {
    mode: 'python',
    lineNumbers: true,
    matchBrackets: true,
    styleActiveLine: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    lineWrapping: true,
    autofocus: true,
    value: '# Welcome to AccessibleIDE!\n# Write Python code and press Run (or Ctrl+Enter).\n\nprint("Hello, world!")\n\nfor i in range(3):\n    print("Counting:", i)\n'
  });

  // ---------- Theme colours ----------
  // The palettes live on the server (routes.THEMES) and arrive from
  // /api/themes. Keeping one copy means the code colours can never drift
  // away from the colours in style.css. Until the fetch lands we fall
  // back to the current theme's background so the editor never flashes
  // white.
  var themePalette = { bg: '#0b0b0b', fg: '#ffffff' };
  var contrastMode = 'normal';

  function fetchThemes() {
    return fetch('/api/themes')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        Object.keys(data).forEach(function (key) {
          themePalette[key] = data[key];
        });
        populateThemeSelect(data);
        applyTheme(themeSelect.value);
      })
      .catch(function () {
        // Offline: the editor keeps its neutral fallback colours.
      });
  }

  function populateThemeSelect(themes) {
    var current = themeSelect.value || body.getAttribute('data-theme');
    themeSelect.innerHTML = '';
    Object.keys(themes).forEach(function (key) {
      var option = document.createElement('option');
      option.value = key;
      option.textContent = themes[key].name;
      if (key === current) option.selected = true;
      themeSelect.appendChild(option);
    });
  }

  // Extra-high contrast pushes the token colours apart without changing
  // the hue, so a reader who needs more separation gets it without
  // having to learn a new colour scheme.
  function contrastAdjust(hex) {
    if (contrastMode !== 'high') return hex;
    var c = contrastPalette[themeSelect.value] || contrastPalette.high;
    return c[hex] || hex;
  }

  // High-contrast remaps, keyed by the exact base hex so a palette change
  // on the server can never silently skip a colour here. Each target is
  // pushed further from its background, not re-hued, so the theme still
  // looks like itself. Verified by tests/test_contrast.py.
  // Keys cover fg, gutter_fg and every syntax colour.
  var contrastPalette = {
    'high-contrast': {
      '#ffffff': '#ffffff', '#a8a8a8': '#d0d0d0', '#e8e8e8': '#ffffff',
      '#93e6a8': '#c9f5d6', '#ff9a9a': '#ffc9c9', '#93d4ff': '#c9e9ff',
      '#b4b4b4': '#e0e0e0', '#ffd93d': '#ffe98a'
    },
    dark: {
      '#e6e6e6': '#ffffff', '#98a0a8': '#c0c8d0',
      '#b9d99f': '#d6efc4', '#8fc0f5': '#c2ddff', '#93a18d': '#bccbb5',
      '#e3c583': '#f5e3bd', '#8ad4e8': '#c4eef7', '#c8cfd6': '#e4e9ee',
      '#c2cad2': '#dee4ea', '#dde2e8': '#f2f5f8'
    },
    pastel: {
      '#453f3a': '#000000', '#6b6258': '#4a443c',
      '#9a4a12': '#6d300a', '#427a20': '#2c5414', '#6f675c': '#4e4840',
      '#8a6412': '#5e440b', '#1f6a94': '#144a67', '#3a4a52': '#26333a',
      '#584f47': '#3a342e'
    },
    light: {
      '#2b2b2b': '#000000', '#565656': '#3a3a3a',
      '#7a1fa2': '#5c1478', '#1b6b2f': '#114a1f', '#5c5c5c': '#3d3d3d',
      '#a03000': '#702100', '#0057b8': '#003d80', '#3d3d3d': '#262626',
      '#4a4a4a': '#333333'
    }
  };

  function applyTheme(themeKey) {
    var c = themePalette[themeKey] || themePalette;
    if (!c.bg) return;
    CodeMirror.defineStyle('accessible-theme', {
      'background': c.bg,
      'color': contrastAdjust(c.fg),
      'gutters': { 'background-color': c.gutter_bg, 'color': c.gutter_fg, 'border': 'none' },
      'gutter': { 'background-color': c.gutter_bg, 'color': c.gutter_fg },
      'cursor': { 'border-left': '2px solid ' + c.cursor },
      'selected': { 'background-color': c.selection },
      'activeline-background': { 'background-color': c.selection + '33' },
      'keyword': { 'color': contrastAdjust(c.keyword), 'font-weight': 'bold' },
      'string': { 'color': contrastAdjust(c.string) },
      'comment': { 'color': contrastAdjust(c.comment), 'font-style': 'italic' },
      'number': { 'color': contrastAdjust(c.number) },
      'def': { 'color': contrastAdjust(c.function) },
      'variable-2': { 'color': contrastAdjust(c.variable) },
      'variable-3': { 'color': contrastAdjust(c.function) },
      'operator': { 'color': contrastAdjust(c.operator) },
      'punctuation': { 'color': contrastAdjust(c.punctuation) },
      'bracket': { 'color': contrastAdjust(c.punctuation) },
      'builtin': { 'color': contrastAdjust(c.function) },
      'atom': { 'color': contrastAdjust(c.number) },
      'meta': { 'color': contrastAdjust(c.comment) }
    });
    editor.setOption('theme', 'accessible-theme');
  }

  // ---------- Fonts ----------
  var FONT_FAMILIES = {
    'OpenDyslexic': '"OpenDyslexic3", "OpenDyslexic", cursive',
    'Atkinson Hyperlegible': '"Atkinson Hyperlegible", sans-serif',
    'Comic Sans MS': '"Comic Sans MS", cursive',
    'Courier New': '"Courier New", monospace'
  };

  function applyFont(fontKey) {
    var family = FONT_FAMILIES[fontKey] || FONT_FAMILIES['Atkinson Hyperlegible'];
    body.style.fontFamily = family;
    editorEl.style.fontFamily = family;
    // CodeMirror needs the font applied to its content
    var cm = editorEl.querySelector('.CodeMirror');
    if (cm) cm.style.fontFamily = family;
    // Font metrics changed - recalculate the gutter width so line
    // numbers never overlap the code.
    editor.refresh();
  }

  function applyFontSize(size) {
    body.style.fontSize = size + 'px';
    editorEl.style.fontSize = size + 'px';
    var cm = editorEl.querySelector('.CodeMirror');
    if (cm) cm.style.fontSize = size + 'px';
    fontSizeLabel.textContent = size + 'px';
    editor.refresh();
  }

  // These three were stored in the config and rendered onto <body>, but
  // nothing ever read them, so the settings did nothing. The tokens
  // already exist in style.css and body already consumes them, so all
  // that is needed is to write the new value.
  function applyLineHeight(value) {
    body.style.setProperty('--line-height', value);
    body.setAttribute('data-line-height', value);
    lineHeightLabel.textContent = value;
    editor.refresh();
  }

  function applyLetterSpacing(value) {
    body.style.setProperty('--letter-spacing', value + 'px');
    body.setAttribute('data-letter-spacing', value);
    letterSpacingLabel.textContent = value + 'px';
    editor.refresh();
  }

  // 0 = barely faded, 1 = strongly faded. A 0 value would hide the other
  // lines completely, so we keep a floor of 0.15.
  function applyBlurIntensity(value) {
    var amount = 0.85 - (value * 0.7);
    body.style.setProperty('--blur-amount', amount.toFixed(2));
    blurIntensityLabel.textContent = value;
  }

  function applyContrast(value) {
    contrastMode = value;
    body.setAttribute('data-contrast', value);
    applyTheme(themeSelect.value);
  }

  function applyFocusMode(mode) {
    body.setAttribute('data-focus-mode', mode);
    // Hide the gutter through CodeMirror's native option rather than CSS
    // display:none. Toggling lineNumbers makes CodeMirror re-measure and
    // drop the gutter column, so the numbers never ghost over the code.
    if (mode === 'gutter') {
      if (editor.getOption('lineNumbers')) editor.setOption('lineNumbers', false);
    } else {
      if (!editor.getOption('lineNumbers')) editor.setOption('lineNumbers', true);
    }
    editor.refresh();
    setTimeout(editor.refresh.bind(editor), 40);
  }

  // ---------- Config persistence ----------
  function saveConfig(partial) {
    var payload = {};
    Object.keys(partial).forEach(function (key) { payload[key] = partial[key]; });
    payload.access_code = accessCode;
    return fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (result) {
        if (result.ok) {
          if (settingsStatus) {
            settingsStatus.textContent = 'Saved.';
            settingsStatus.classList.remove('is-error');
          }
        } else {
          reportSaveError(result.data);
        }
        return result;
      })
      .catch(function () {
        // Offline or server error - the setting still applies for this
        // session, so say so rather than pretending it failed.
        if (settingsStatus) {
          settingsStatus.textContent = 'Changed for now. It will not be remembered until the app is back online.';
          settingsStatus.classList.add('is-error');
        }
      });
  }

  function reportSaveError(data) {
    if (!settingsStatus) return;
    settingsStatus.textContent = (data && data.error) || 'That setting could not be saved.';
    settingsStatus.classList.add('is-error');
  }

  // ---------- Settings dialog ----------
  function openSettings() {
    settingsOpener = document.activeElement;
    syncBlurField();
    if (typeof settingsDialog.showModal === 'function') {
      settingsDialog.showModal();
    } else {
      settingsDialog.setAttribute('open', '');
    }
    // Land focus on the first real control, not the close button.
    var first = settingsDialog.querySelector('select, input, button');
    if (first) first.focus();
  }

  function closeSettings() {
    if (typeof settingsDialog.close === 'function') {
      settingsDialog.close();
    } else {
      settingsDialog.removeAttribute('open');
    }
    // Send focus back where it came from, so keyboard and screen reader
    // users are not dropped at the top of the page.
    if (settingsOpener && typeof settingsOpener.focus === 'function') {
      settingsOpener.focus();
    }
  }

  // ---------- TTS ----------
  function loadVoices() {
    if (!('speechSynthesis' in window) || !ttsVoice) return;
    var voices = window.speechSynthesis.getVoices() || [];
    if (!voices.length) return;

    var current = ttsVoice.value;
    ttsVoice.innerHTML = '';
    var def = document.createElement('option');
    def.value = '';
    def.textContent = 'System default';
    ttsVoice.appendChild(def);

    voices.forEach(function (voice) {
      var option = document.createElement('option');
      // value holds the voice name; the language is shown so a reader
      // can tell two similarly named voices apart.
      option.value = voice.name;
      option.textContent = voice.name + ' (' + voice.lang + ')';
      ttsVoice.appendChild(option);
    });

    if (current) ttsVoice.value = current;
  }

  function pickVoice() {
    if (!('speechSynthesis' in window)) return null;
    var voices = window.speechSynthesis.getVoices() || [];
    for (var i = 0; i < voices.length; i++) {
      if (voices[i].name === speechVoiceName) return voices[i];
    }
    return null;
  }

  function speak(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = speechRate;
    utterance.pitch = 1.0;
    var voice = pickVoice();
    if (voice) utterance.voice = voice;
    window.speechSynthesis.speak(utterance);
  }

  // ---------- Run code ----------
  var errorMarkers = [];

  function clearErrorMarkers() {
    errorMarkers.forEach(function (m) { m.clear(); });
    errorMarkers = [];
  }

  function highlightErrorLine(lineNumber) {
    clearErrorMarkers();
    if (!lineNumber) return;
    var line = lineNumber - 1; // CodeMirror lines are 0-based
    if (line < 0 || line >= editor.lineCount()) return;
    var marker = editor.markText(
      { line: line, ch: 0 },
      { line: line, ch: editor.getLine(line).length },
      { className: 'cm-error-line' }
    );
    errorMarkers.push(marker);
    editor.scrollIntoView({ line: line, ch: 0 }, 100);
    editor.setCursor({ line: line, ch: 0 });
  }

  function runCode() {
    var code = editor.getValue();
    outputEl.textContent = 'Running...';
    errorPanel.hidden = true;
    clearErrorMarkers();

    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code, access_code: accessCode })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.code_required) {
          if (promptForAccessCode()) {
            runCode();
          } else {
            outputEl.textContent = 'Code running is locked.';
            errorMessage.textContent = data.error;
            errorPanel.hidden = false;
          }
          return;
        }
        outputEl.textContent = data.output || '(no output)';
        if (data.error) {
          errorMessage.textContent = data.error;
          errorPanel.hidden = false;
          highlightErrorLine(data.error_line);
          if (ttsEnabled) speak(data.error);
        } else {
          errorPanel.hidden = true;
          if (ttsEnabled) speak(data.output || 'Program finished.');
        }
      })
      .catch(function () {
        outputEl.textContent = 'Could not reach the code runner.';
        errorMessage.textContent = 'The server is not responding. Please try again.';
        errorPanel.hidden = false;
      });
  }

  // ---------- Save / Open files ----------
  function saveFile() {
    var content = editor.getValue();
    var suggestedName = 'my_code.py';

    if (window.showSaveFilePicker) {
      window.showSaveFilePicker({
        suggestedName: suggestedName,
        types: [{ description: 'Python file', accept: { 'text/x-python': ['.py'] } }]
      })
        .then(function (handle) { return handle.createWritable(); })
        .then(function (writable) {
          return writable.write(content).then(function () { return writable.close(); });
        })
        .then(function () {
          outputEl.textContent = 'File saved.';
          errorPanel.hidden = true;
        })
        .catch(function (err) {
          if (err.name !== 'AbortError') {
            outputEl.textContent = 'Could not save the file.';
          }
        });
    } else {
      // Fallback: download the file
      var blob = new Blob([content], { type: 'text/x-python' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = suggestedName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      outputEl.textContent = 'File downloaded.';
      errorPanel.hidden = true;
    }
  }

  function openFile() {
    if (window.showOpenFilePicker) {
      window.showOpenFilePicker({
        types: [{ description: 'Python file', accept: { 'text/x-python': ['.py'] } }]
      })
        .then(function (handles) { return handles[0].getFile(); })
        .then(function (file) { return file.text(); })
        .then(function (text) {
          editor.setValue(text);
          clearErrorMarkers();
          outputEl.textContent = 'File opened.';
          errorPanel.hidden = true;
        })
        .catch(function (err) {
          if (err.name !== 'AbortError') {
            outputEl.textContent = 'Could not open the file.';
          }
        });
    } else {
      fileInput.click();
    }
  }

  // ---------- Read line aloud ----------
  function readLine() {
    var selection = editor.getSelection();
    var text = selection || editor.getLine(editor.getCursor().line);
    if (text && text.trim()) {
      speak(text);
    }
  }

  // ---------- Event wiring ----------
  btnRun.addEventListener('click', runCode);

  btnClear.addEventListener('click', function () {
    outputEl.textContent = '';
    errorPanel.hidden = true;
  });

  btnSave.addEventListener('click', saveFile);

  btnOpen.addEventListener('click', openFile);

  fileInput.addEventListener('change', function () {
    var file = fileInput.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      editor.setValue(reader.result);
      clearErrorMarkers();
      outputEl.textContent = 'File opened.';
      errorPanel.hidden = true;
    };
    reader.readAsText(file);
    fileInput.value = '';
  });

  btnReadLine.addEventListener('click', readLine);

  btnTts.addEventListener('click', function () {
    ttsEnabled = !ttsEnabled;
    btnTts.setAttribute('aria-checked', ttsEnabled ? 'true' : 'false');
    btnTts.classList.toggle('active', ttsEnabled);
    if (ttsState) ttsState.textContent = ttsEnabled ? 'On' : 'Off';
    saveConfig({ tts_enabled: ttsEnabled });
    if (ttsEnabled) {
      speak('Text to speech enabled.');
    }
  });

  fontSelect.addEventListener('change', function () {
    applyFont(fontSelect.value);
    body.setAttribute('data-font', fontSelect.value);
    saveConfig({ font: fontSelect.value });
  });

  fontSize.addEventListener('input', function () {
    applyFontSize(parseInt(fontSize.value, 10));
  });

  fontSize.addEventListener('change', function () {
    saveConfig({ font_size: parseInt(fontSize.value, 10) });
  });

  lineHeight.addEventListener('input', function () {
    applyLineHeight(lineHeight.value);
  });

  lineHeight.addEventListener('change', function () {
    saveConfig({ line_height: parseFloat(lineHeight.value) });
  });

  letterSpacing.addEventListener('input', function () {
    applyLetterSpacing(letterSpacing.value);
  });

  letterSpacing.addEventListener('change', function () {
    saveConfig({ letter_spacing: parseFloat(letterSpacing.value) });
  });

  blurIntensity.addEventListener('input', function () {
    applyBlurIntensity(blurIntensity.value);
  });

  blurIntensity.addEventListener('change', function () {
    saveConfig({ blur_intensity: parseFloat(blurIntensity.value) });
  });

  themeSelect.addEventListener('change', function () {
    applyTheme(themeSelect.value);
    body.setAttribute('data-theme', themeSelect.value);
    saveConfig({ theme: themeSelect.value });
  });

  contrastSelect.addEventListener('change', function () {
    applyContrast(contrastSelect.value);
    saveConfig({ contrast: contrastSelect.value });
  });

  focusMode.addEventListener('change', function () {
    applyFocusMode(focusMode.value);
    syncBlurField();
    saveConfig({ focus_mode: focusMode.value });
  });

  ttsVoice.addEventListener('change', function () {
    speechVoiceName = ttsVoice.value;
    saveConfig({ tts_voice: speechVoiceName });
  });

  ttsRate.addEventListener('input', function () {
    speechRate = parseFloat(ttsRate.value);
    ttsRateLabel.textContent = speechRate.toFixed(1) + 'x';
  });

  ttsRate.addEventListener('change', function () {
    saveConfig({ tts_rate: speechRate });
  });

  btnTestVoice.addEventListener('click', function () {
    speak('This is how your code results will sound when they are read aloud.');
  });

  btnSettings.addEventListener('click', openSettings);

  settingsDialog.addEventListener('cancel', function (event) {
    // Escape was pressed. Let the dialog close itself, then put focus
    // back on the button that opened it.
    event.preventDefault();
    closeSettings();
  });

  if (btnSettingsClose) {
    btnSettingsClose.addEventListener('click', function (event) {
      event.preventDefault();
      closeSettings();
    });
  }

  // Keyboard shortcut: Ctrl+Enter to run
  editor.setOption('extraKeys', {
    'Ctrl-Enter': runCode,
    'Cmd-Enter': runCode
  });

  // ---------- Quit (desktop app only) ----------
  // The Quit button only appears when running on the local desktop app,
  // where it stops the background server cleanly.
  if (btnQuit && (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost')) {
    btnQuit.hidden = false;
    btnQuit.addEventListener('click', function () {
      fetch('/api/shutdown', { method: 'POST' })
        .then(function () {
          window.close();
        })
        .catch(function () {
          window.close();
        });
    });
  }

  // ---------- Init ----------
  contrastMode = contrastSelect.value || 'normal';
  applyContrast(contrastMode);
  applyTheme(body.getAttribute('data-theme') || 'high-contrast');
  applyFont(body.getAttribute('data-font') || 'Atkinson Hyperlegible');
  applyFontSize(parseInt(body.getAttribute('data-font-size') || '16', 10));
  applyLineHeight(body.getAttribute('data-line-height') || '1.6');
  applyLetterSpacing(body.getAttribute('data-letter-spacing') || '0.5');
  applyBlurIntensity(body.getAttribute('data-blur-intensity') || '0.5');
  applyFocusMode(body.getAttribute('data-focus-mode') || 'off');
  syncBlurField();

  speechRate = parseFloat(body.getAttribute('data-tts-rate') || ttsRate.value || '0.9');
  speechVoiceName = body.getAttribute('data-tts-voice') || '';
  ttsRateLabel.textContent = speechRate.toFixed(1) + 'x';

  // Theme names and the voice list both come from the server, so the
  // first paint uses the saved values and these fill in behind them.
  fetchThemes();

  if ('speechSynthesis' in window) {
    loadVoices();
    // Chrome and Edge populate the voice list asynchronously.
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  // Custom fonts load asynchronously. Once they are ready, recalculate
  // the editor layout so the gutter width matches the real font metrics.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      editor.refresh();
    });
  }
})();