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
  var themeSelect = document.getElementById('theme-select');
  var focusMode = document.getElementById('focus-mode');
  var btnQuit = document.getElementById('btn-quit');

  var body = document.body;
  var ttsEnabled = btnTts.getAttribute('aria-pressed') === 'true';
  var accessCode = localStorage.getItem('accessible_ide_code') || '';

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

  // ---------- Theme colors (match server-side THEMES) ----------
  var THEME_COLORS = {
    'high-contrast': {
      bg: '#0d0d0d', fg: '#ffffff', selection: '#ffff00', cursor: '#ffff00',
      gutterBg: '#1a1a1a', gutterFg: '#888888',
      keyword: '#ff6b6b', string: '#69db7c', comment: '#888888',
      number: '#ffd93d', function: '#74b9ff', variable: '#ffffff',
      operator: '#ff6b6b', punctuation: '#ffffff'
    },
    'dark': {
      bg: '#1e1e1e', fg: '#d4d4d4', selection: '#264f78', cursor: '#ffffff',
      gutterBg: '#252526', gutterFg: '#858585',
      keyword: '#569cd6', string: '#ce9178', comment: '#6a9955',
      number: '#b5cea8', function: '#dcdcaa', variable: '#9cdcfe',
      operator: '#d4d4d4', punctuation: '#d4d4d4'
    },
    'pastel': {
      bg: '#fdf6e3', fg: '#586e75', selection: '#eee8d5', cursor: '#586e75',
      gutterBg: '#eee8d5', gutterFg: '#93a1a1',
      keyword: '#cb4b16', string: '#859900', comment: '#93a1a1',
      number: '#b58900', function: '#268bd2', variable: '#2aa198',
      operator: '#586e75', punctuation: '#586e75'
    },
    'light': {
      bg: '#ffffff', fg: '#333333', selection: '#add6ff', cursor: '#333333',
      gutterBg: '#f5f5f5', gutterFg: '#999999',
      keyword: '#0000ff', string: '#008000', comment: '#808080',
      number: '#ff0000', function: '#800080', variable: '#333333',
      operator: '#333333', punctuation: '#333333'
    }
  };

  function applyTheme(themeKey) {
    var c = THEME_COLORS[themeKey] || THEME_COLORS['high-contrast'];
    CodeMirror.defineStyle('accessible-theme', {
      'background': c.bg,
      'color': c.fg,
      'gutters': { 'background-color': c.gutterBg, 'color': c.gutterFg, 'border': 'none' },
      'gutter': { 'background-color': c.gutterBg, 'color': c.gutterFg },
      'cursor': { 'border-left': '2px solid ' + c.cursor },
      'selected': { 'background-color': c.selection },
      'activeline-background': { 'background-color': c.selection + '33' },
      'keyword': { 'color': c.keyword, 'font-weight': 'bold' },
      'string': { 'color': c.string },
      'comment': { 'color': c.comment, 'font-style': 'italic' },
      'number': { 'color': c.number },
      'def': { 'color': c.function },
      'variable': { 'color': c.variable },
      'operator': { 'color': c.operator },
      'punctuation': { 'color': c.punctuation },
      'builtin': { 'color': c.function }
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
    partial.access_code = accessCode;
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(partial)
    }).catch(function () {
      // Offline or server error - settings still apply for this session
    });
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

  // ---------- TTS ----------
  function speak(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.9;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
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
    btnTts.setAttribute('aria-pressed', ttsEnabled ? 'true' : 'false');
    btnTts.classList.toggle('active', ttsEnabled);
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

  themeSelect.addEventListener('change', function () {
    applyTheme(themeSelect.value);
    body.setAttribute('data-theme', themeSelect.value);
    saveConfig({ theme: themeSelect.value });
  });

  focusMode.addEventListener('change', function () {
    applyFocusMode(focusMode.value);
    saveConfig({ focus_mode: focusMode.value });
  });

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
  applyTheme(body.getAttribute('data-theme') || 'high-contrast');
  applyFont(body.getAttribute('data-font') || 'Atkinson Hyperlegible');
  applyFontSize(parseInt(body.getAttribute('data-font-size') || '16', 10));
  applyFocusMode(body.getAttribute('data-focus-mode') || 'off');

  // Custom fonts load asynchronously. Once they are ready, recalculate
  // the editor layout so the gutter width matches the real font metrics.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      editor.refresh();
    });
  }
})();