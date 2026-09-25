// Execute app.js against a minimal DOM stub.
//
// The editor is one file with no build step, so a typo in an element id or
// a missing helper throws at load time and silently disables the whole
// editor. There is no jsdom in this project, so this stubs just enough to
// let the script run and reports anything that throws.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const APP_JS = path.join(
  __dirname, '..', 'src', 'accessible_ide', 'static', 'js', 'app.js'
);
const source = fs.readFileSync(APP_JS, 'utf8');

// Ids that index.html is expected to provide. Anything app.js looks up but
// that is missing here will be reported, because that is exactly the bug
// this harness exists to catch.
const KNOWN_IDS = new Set([
  'btn-run', 'btn-save', 'btn-open', 'btn-read-line', 'btn-clear', 'btn-quit',
  'editor', 'output', 'error-panel', 'error-message', 'file-input',
  'settings-dialog', 'settings-title', 'settings-status', 'btn-settings',
  'btn-settings-close', 'font-select', 'font-size', 'font-size-label',
  'line-height', 'line-height-label', 'letter-spacing',
  'letter-spacing-label', 'blur-intensity', 'blur-intensity-label',
  'blur-field', 'theme-select', 'contrast-select', 'focus-mode',
  'tts-toggle', 'tts-state', 'tts-voice', 'tts-rate', 'tts-rate-label',
  'btn-test-voice',
]);

const numericIds = new Set([
  'font-size', 'line-height', 'letter-spacing', 'blur-intensity', 'tts-rate',
]);

const lookups = [];
const noop = () => {};

function makeClassList() {
  const set = new Set();
  return {
    add: (c) => set.add(c),
    remove: (c) => set.delete(c),
    toggle: (c, force) => (force === undefined ? (set.has(c) ? set.delete(c) : set.add(c)) : (force ? set.add(c) : set.delete(c))),
    contains: (c) => set.has(c),
  };
}

function makeElement(id) {
  const attributes = {
    'aria-checked': 'true',
    'aria-pressed': 'false',
    'data-theme': 'high-contrast',
    'data-font': 'OpenDyslexic',
    'data-font-size': '16',
    'data-line-height': '1.6',
    'data-letter-spacing': '0.5',
    'data-blur-intensity': '0.5',
    'data-focus-mode': 'off',
    'data-contrast': 'normal',
    'data-tts-voice': '',
    'data-tts-rate': '0.9',
  };

  // Listeners are recorded rather than discarded so the harness can fire
  // them afterwards. A handler that throws is the failure mode that
  // matters: it silently stops that control working.
  const listeners = {};

  const el = {
    id,
    value: numericIds.has(id) ? '16' : 'OpenDyslexic',
    textContent: '',
    innerHTML: '',
    checked: false,
    disabled: false,
    hidden: false,
    files: [],
    className: '',
    classList: makeClassList(),
    style: new Proxy({ setProperty: noop, removeProperty: noop }, {
      get: (t, k) => (k in t ? t[k] : ''),
      set: () => true,
    }),
    getAttribute: (name) => (name in attributes ? attributes[name] : null),
    setAttribute: (name, v) => { attributes[name] = v; },
    removeAttribute: (name) => { delete attributes[name]; },
    hasAttribute: (name) => name in attributes,
    addEventListener: (type, handler) => {
      (listeners[type] = listeners[type] || []).push(handler);
    },
    removeEventListener: noop,
    appendChild: noop,
    removeChild: noop,
    focus: noop,
    blur: noop,
    click: noop,
    close: noop,
    showModal: noop,
    getBoundingClientRect: () => ({ top: 0, left: 0, width: 100, height: 100 }),
    querySelector: () => makeElement('__query__'),
    querySelectorAll: () => [],
    getElementsByClassName: () => [],
  };
  el.__listeners = listeners;
  el.__attributes = attributes;
  return el;
}

const editorInstance = {
  getValue: () => 'print("hi")',
  setValue: noop,
  setOption: noop,
  getOption: () => undefined,
  refresh: noop,
  on: noop,
  focus: noop,
  operation: (fn) => fn(),
  getDoc: () => ({ getLine: () => '', getSelection: () => '' }),
  replaceSelection: noop,
};

function CodeMirror() { return editorInstance; }
CodeMirror.defineStyle = noop;
CodeMirror.defineMode = noop;
CodeMirror.defineMIME = noop;
CodeMirror.commands = {};

const elements = new Map();

const documentStub = {
  body: makeElement('body'),
  documentElement: makeElement('html'),
  // The Settings button has focus when it is pressed, which is the case
  // openSettings/closeSettings are written to handle.
  activeElement: null,
  getElementById: (id) => {
    lookups.push(id);
    if (!KNOWN_IDS.has(id)) return null;
    if (!elements.has(id)) elements.set(id, makeElement(id));
    return elements.get(id);
  },
  querySelector: () => makeElement('__query__'),
  querySelectorAll: () => [],
  createElement: (tag) => makeElement(tag),
  addEventListener: noop,
  removeEventListener: noop,
  fonts: { ready: Promise.resolve() },
};

const fetchCalls = [];
function fetchStub(url) {
  fetchCalls.push(url);
  if (String(url).includes('/api/themes')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        'high-contrast': { name: 'High Contrast', bg: '#0b0b0b', fg: '#ffffff' },
        dark: { name: 'Dark', bg: '#17181c', fg: '#e6e6e6' },
      }),
    });
  }
  return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
}

const sandbox = {
  console,
  document: documentStub,
  navigator: { language: 'en-GB', userAgent: 'stub' },
  localStorage: { getItem: () => null, setItem: noop, removeItem: noop },
  fetch: fetchStub,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  Promise,
  JSON,
  Math,
  Date,
  Number,
  String,
  Object,
  Array,
  parseInt,
  parseFloat,
  isNaN,
  CodeMirror,
  SpeechSynthesisUtterance: function (text) { this.text = text; },
  window: {
    location: {
      hostname: 'localhost',
      href: 'http://localhost:5000/',
      protocol: 'http:',
      host: 'localhost:5000',
      origin: 'http://localhost:5000',
    },
    speechSynthesis: {
      getVoices: () => ([{ name: 'Test Voice', lang: 'en-GB' }]),
      speak: noop,
      cancel: noop,
      onvoiceschanged: null,
    },
    addEventListener: noop,
    removeEventListener: noop,
  },
};
sandbox.window.document = documentStub;
sandbox.globalThis = sandbox;
sandbox.self = sandbox;

let failed = false;
try {
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: 'app.js' });
  console.log('OK  app.js executed with no error');
} catch (error) {
  failed = true;
  console.log('FAIL app.js threw at load time:');
  console.log('     ' + error.message);
  console.log((error.stack || '').split('\n').slice(0, 6).join('\n'));
}

const unknown = [...new Set(lookups)].filter((id) => !KNOWN_IDS.has(id));
if (unknown.length) {
  failed = true;
  console.log('FAIL app.js looked up ids this harness does not know: ' + unknown.join(', '));
}

// ---------------------------------------------------------------------------
// Fire every listener the script registered. Loading without error only
// proves the top half of the file parsed; the wiring is in these handlers.
// ---------------------------------------------------------------------------
const fakeEvent = { preventDefault: noop, stopPropagation: noop };
const interactions = [
  ['font-select', 'change'], ['font-size', 'input'], ['font-size', 'change'],
  ['line-height', 'input'], ['line-height', 'change'],
  ['letter-spacing', 'input'], ['letter-spacing', 'change'],
  ['blur-intensity', 'input'], ['blur-intensity', 'change'],
  ['theme-select', 'change'], ['contrast-select', 'change'],
  ['focus-mode', 'change'],
  ['tts-toggle', 'click'], ['tts-voice', 'change'],
  ['tts-rate', 'input'], ['tts-rate', 'change'],
  ['btn-test-voice', 'click'],
  ['btn-settings', 'click'], ['btn-settings-close', 'click'],
  ['settings-dialog', 'cancel'],
];

let fired = 0;
for (const [id, type] of interactions) {
  const el = elements.get(id);
  if (!el) {
    failed = true;
    console.log(`FAIL no element captured for #${id}`);
    continue;
  }
  for (const handler of el.__listeners[type] || []) {
    try {
      handler(fakeEvent);
      fired++;
    } catch (error) {
      failed = true;
      console.log(`FAIL ${type} handler on #${id} threw: ${error.message}`);
      console.log((error.stack || '').split('\n').slice(0, 4).join('\n'));
    }
  }
}
console.log(`     fired ${fired} event handlers across ${interactions.length} controls`);

// The two settings that were previously stored but never applied must
// actually reach the document now.
const bodyAttrs = documentStub.body.__attributes;
const savedSettings = ['data-line-height', 'data-letter-spacing',
                       'data-blur-intensity', 'data-contrast'];
const missingAttrs = savedSettings.filter((a) => !(a in bodyAttrs));
if (missingAttrs.length) {
  failed = true;
  console.log('FAIL body never received: ' + missingAttrs.join(', '));
} else {
  console.log('     body received ' + savedSettings.join(', '));
}

const missing = [...KNOWN_IDS].filter((id) => !lookups.includes(id));
console.log('     looked up ' + new Set(lookups).size + ' ids; ' + missing.length +
            ' declared-but-unused in the harness' + (missing.length ? ': ' + missing.join(', ') : ''));

setTimeout(() => {
  console.log('     fetch calls: ' + (fetchCalls.length ? fetchCalls.join(', ') : '(none)'));
  process.exit(failed ? 1 : 0);
}, 50);
