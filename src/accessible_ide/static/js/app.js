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
  var fontBundledNote = document.getElementById('font-bundled-note');
  var sampleText = document.getElementById('sample-text');
  var fontPreview = document.getElementById('font-preview');
  var fontPreviewText = document.getElementById('font-preview-text');
  var previewStatus = document.getElementById('preview-status');
  var swatches = document.getElementById('swatches');
  var codeColorHex = document.getElementById('code-color-hex');
  var codeColorPicker = document.getElementById('code-color-picker');
  var colourError = document.getElementById('colour-error');
  var btnResetColour = document.getElementById('btn-reset-colour');

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

  // The user's own colour for code text. Empty means "use the theme".
  // Only the base text colour is overridden: the syntax colours stay as
  // the theme set them, because those are contrast-checked on the server
  // and a reader who needs the structure of highlighted code should keep
  // it.
  var customCodeColor = '';

  function codeTextColor(palette) {
    if (!customCodeColor) return contrastAdjust(palette.fg);
    return contrastAdjust(
      ensureReadable(customCodeColor, palette.bg, 4.5));
  }

  function applyTheme(themeKey) {
    var c = themePalette[themeKey] || themePalette;
    if (!c.bg) return;
    CodeMirror.defineStyle('accessible-theme', {
      'background': c.bg,
      'color': codeTextColor(c),
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
    updatePreview();
  }

  // ---------- Fonts ----------
  // The font stacks live in routes.py and arrive here on each <option>
  // as data-family, so there is only ever one copy of them. An earlier
  // version kept a second list in this file, which is how OpenDyslexic
  // could be listed but not actually load.
  var DEFAULT_FONT_FAMILY = '"Atkinson Hyperlegible", sans-serif';

  function fontFamilyFor(fontKey) {
    var option = fontSelect && fontSelect.querySelector(
      'option[value="' + (fontKey || '').replace(/"/g, '') + '"]');
    var family = option && option.getAttribute('data-family');
    return family || DEFAULT_FONT_FAMILY;
  }

  // ---------- Colour ----------
  // The user can pick any colour for their code. That is a genuine
  // accessibility risk: a pale yellow on a light theme, or near-black on
  // a dark one, is unreadable. Rather than block the choice, the colour
  // is moved - along the lightness axis only, so the hue the user chose
  // is preserved - until it clears WCAG AA (4.5:1) against the theme it
  // is being used on. Contrast-mode remapping still applies on top.
  function hexToRgb(hex) {
    var value = String(hex || '').replace('#', '').trim();
    if (value.length === 3) {
      value = value[0] + value[0] + value[1] + value[1] + value[2] + value[2];
    }
    if (!/^[0-9a-fA-F]{6}$/.test(value)) return null;
    return {
      r: parseInt(value.slice(0, 2), 16),
      g: parseInt(value.slice(2, 4), 16),
      b: parseInt(value.slice(4, 6), 16)
    };
  }

  function relativeLuminance(rgb) {
    var channels = [rgb.r, rgb.g, rgb.b].map(function (channel) {
      var part = channel / 255;
      return part <= 0.03928 ? part / 12.92
        : Math.pow((part + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  }

  function contrastRatio(first, second) {
    var a = relativeLuminance(first);
    var b = relativeLuminance(second);
    var lighter = Math.max(a, b);
    var darker = Math.min(a, b);
    return (lighter + 0.05) / (darker + 0.05);
  }

  function rgbToHex(rgb) {
    return '#' + [rgb.r, rgb.g, rgb.b].map(function (channel) {
      return ('0' + Math.max(0, Math.min(255, Math.round(channel)))
        .toString(16)).slice(-2);
    }).join('');
  }

  function ensureReadable(hex, backgroundHex, minimum) {
    var target = minimum || 4.5;
    var rgb = hexToRgb(hex);
    var bg = hexToRgb(backgroundHex);
    if (!rgb || !bg) return hex;
    if (contrastRatio(rgb, bg) >= target) return rgbToHex(rgb);

    // Move away from the background, whichever end is closer, so the
    // user's hue is kept and only the brightness changes.
    var backgroundIsDark = relativeLuminance(bg) < 0.5;
    var step = backgroundIsDark ? 12 : -12;
    var moved = { r: rgb.r, g: rgb.g, b: rgb.b };
    for (var i = 0; i < 40; i++) {
      moved = {
        r: moved.r + step,
        g: moved.g + step,
        b: moved.b + step
      };
      if (moved.r < 0 || moved.r > 255 || moved.g < 0 || moved.g > 255
          || moved.b < 0 || moved.b > 255) {
        break;
      }
      if (contrastRatio(moved, bg) >= target) return rgbToHex(moved);
    }
    return backgroundIsDark ? '#ffffff' : '#000000';
  }

  function applyFont(fontKey) {
    var family = fontFamilyFor(fontKey);
    body.style.fontFamily = family;
    editorEl.style.fontFamily = family;
    // CodeMirror needs the font applied to its content
    var cm = editorEl.querySelector('.CodeMirror');
    if (cm) cm.style.fontFamily = family;
    // Font metrics changed - recalculate the gutter width so line
    // numbers never overlap the code.
    editor.refresh();
    updatePreview();
  }

  function applyFontSize(size) {
    body.style.fontSize = size + 'px';
    editorEl.style.fontSize = size + 'px';
    var cm = editorEl.querySelector('.CodeMirror');
    if (cm) cm.style.fontSize = size + 'px';
    fontSizeLabel.textContent = size + 'px';
    editor.refresh();
    updatePreview();
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
    updateFontNote();
    updatePreview();
    saveConfig({ font: fontSelect.value });
  });

  // ---------- Try it out panel ----------
  // Fonts taken from the computer are not guaranteed to exist on every
  // machine, so the panel says which one is in use rather than leaving
  // the reader to wonder why Arial looks like Liberation Sans.
  function updateFontNote() {
    if (!fontBundledNote || !fontSelect) return;
    var option = fontSelect.options[fontSelect.selectedIndex];
    var bundled = option && option.getAttribute('data-bundled') === 'true';
    var note = option ? option.textContent : '';
    fontBundledNote.textContent = bundled
      ? note + ' is included with the app.'
      : note + ' comes from your computer. If it does not show, an ' +
        'included font will be used instead.';
    fontBundledNote.hidden = false;
  }

  function updatePreview() {
    if (!fontPreview) return;
    var palette = themePalette[themeSelect.value] || themePalette;
    var shown = codeTextColor(palette);
    var option = fontSelect.options[fontSelect.selectedIndex];
    var name = option ? option.textContent : 'your font';
    var sample = sampleText && sampleText.value ? sampleText.value : ' ';

    fontPreview.style.fontFamily = fontFamilyFor(fontSelect.value);
    fontPreview.style.fontSize = fontSize.value + 'px';
    // The preview uses the editor's own background and the same resolved
    // text colour, so it cannot drift from what the editor will show.
    if (palette.bg) fontPreview.style.backgroundColor = palette.bg;
    fontPreview.style.color = shown;

    if (fontPreviewText) fontPreviewText.textContent = sample;

    if (previewStatus) {
      var where = customCodeColor ? 'in ' + customCodeColor : 'in the theme colour';
      var nudged = customCodeColor
        && shown.toLowerCase() !== customCodeColor.toLowerCase();
      previewStatus.textContent = 'Showing ' + name + ' ' + where + '.'
        + (nudged
          ? ' On this theme it was lightened or darkened to ' + shown +
            ' so it stays easy to read.'
          : '');
    }
  }

  function setCodeColor(hex, persist) {
    customCodeColor = hex || '';
    body.setAttribute('data-code-color', customCodeColor);
    applyTheme(themeSelect.value);
    updatePreview();
    if (persist) saveConfig({ code_color: customCodeColor });
  }

  function showColourError(message) {
    if (!colourError) return;
    colourError.textContent = message || '';
    colourError.hidden = !message;
    if (codeColorHex) {
      codeColorHex.setAttribute('aria-invalid', message ? 'true' : 'false');
    }
  }

  // Applied on every keystroke so the preview is instant. An unfinished
  // colour is simply not applied and is never nagged about mid-typing -
  // a red error box appearing after the first keystroke of "#ffd93d" is
  // discouraging, and the reader cannot have made a mistake they have not
  // finished expressing. The complaint waits until they leave the field.
  function onHexInput() {
    var value = (codeColorHex.value || '').trim();
    if (value === '') {
      showColourError('');
      setCodeColor('', false);
      return;
    }
    if (!/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value)) return;
    showColourError('');
    if (codeColorPicker) codeColorPicker.value = expandHex(value);
    setCodeColor(value, false);
  }

  function expandHex(value) {
    return value.length === 7
      ? value
      : '#' + value[1] + value[1] + value[2] + value[2] + value[3] + value[3];
  }

  if (swatches) {
    swatches.addEventListener('change', function (event) {
      if (event.target.name !== 'colour-swatch') return;
      if (codeColorHex) codeColorHex.value = event.target.value;
      showColourError('');
      setCodeColor(event.target.value, true);
    });
  }

  if (codeColorHex) {
    codeColorHex.addEventListener('input', onHexInput);
    codeColorHex.addEventListener('change', function () {
      var value = (codeColorHex.value || '').trim();
      if (/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value)) {
        showColourError('');
        setCodeColor(value, true);
      } else if (value === '') {
        showColourError('');
        setCodeColor('', true);
      } else {
        showColourError('That is not a colour. Use # followed by 3 or 6 '
          + 'letters or digits, like #ffd93d.');
      }
    });
  }

  if (codeColorPicker) {
    codeColorPicker.addEventListener('input', function () {
      if (codeColorHex) codeColorHex.value = codeColorPicker.value;
      showColourError('');
      setCodeColor(codeColorPicker.value, false);
    });
    codeColorPicker.addEventListener('change', function () {
      if (codeColorHex) codeColorHex.value = codeColorPicker.value;
      showColourError('');
      setCodeColor(codeColorPicker.value, true);
    });
  }

  if (btnResetColour) {
    btnResetColour.addEventListener('click', function () {
      if (codeColorHex) codeColorHex.value = '';
      var radios = swatches
        ? swatches.querySelectorAll('input[name="colour-swatch"]')
        : [];
      Array.prototype.forEach.call(radios, function (radio) {
        radio.checked = false;
      });
      showColourError('');
      setCodeColor('', true);
      if (codeColorHex) codeColorHex.focus();
    });
  }

  if (sampleText) {
    sampleText.addEventListener('input', updatePreview);
  }

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
  // A saved colour has to be in place before the theme is built, or the
  // editor would paint in the old colour for a frame.
  customCodeColor = body.getAttribute('data-code-color') || '';
  applyTheme(body.getAttribute('data-theme') || 'high-contrast');
  applyFont(body.getAttribute('data-font') || 'Atkinson Hyperlegible');
  applyFontSize(parseInt(body.getAttribute('data-font-size') || '16', 10));
  applyLineHeight(body.getAttribute('data-line-height') || '1.6');
  applyLetterSpacing(body.getAttribute('data-letter-spacing') || '0.5');
  applyBlurIntensity(body.getAttribute('data-blur-intensity') || '0.5');
  applyFocusMode(body.getAttribute('data-focus-mode') || 'off');
  syncBlurField();
  updateFontNote();
  updatePreview();

  // The swatch matching a saved colour is ticked on load, so the panel
  // does not contradict the colour actually in use.
  if (customCodeColor && swatches) {
    var saved = customCodeColor.toLowerCase();
    var radios = swatches.querySelectorAll('input[name="colour-swatch"]');
    Array.prototype.forEach.call(radios, function (radio) {
      if (radio.value.toLowerCase() === saved) radio.checked = true;
    });
  }

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