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
  var fontSelect = document.getElementById('font-select');
  var fontSize = document.getElementById('font-size');
  var fontSizeLabel = document.getElementById('font-size-label');
  var themeSelect = document.getElementById('theme-select');
  var focusMode = document.getElementById('focus-mode');

  var body = document.body;
  var ttsEnabled = btnTts.getAttribute('aria-pressed') === 'true';

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
    editor.refresh();
  }

  // ---------- Config persistence ----------
  function saveConfig(partial) {
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(partial)
    }).catch(function () {
      // Offline or server error - settings still apply for this session
    });
  }

  // ---------- Run code ----------
  function runCode() {
    var code = editor.getValue();
    outputEl.textContent = 'Running...';
    errorPanel.hidden = true;

    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        outputEl.textContent = data.output || '(no output)';
        if (data.error) {
          errorMessage.textContent = data.error;
          errorPanel.hidden = false;
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

  // ---------- Init ----------
  applyTheme(body.getAttribute('data-theme') || 'high-contrast');
  applyFont(body.getAttribute('data-font') || 'Atkinson Hyperlegible');
  applyFontSize(parseInt(body.getAttribute('data-font-size') || '16', 10));
  applyFocusMode(body.getAttribute('data-focus-mode') || 'off');
})();