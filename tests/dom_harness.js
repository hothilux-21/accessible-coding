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
  'reduce-motion', 'reduce-motion-state',
  'tts-toggle', 'tts-state', 'tts-voice', 'tts-rate', 'tts-rate-label',
  'btn-test-voice',
  'font-bundled-note', 'sample-text', 'font-preview', 'font-preview-text',
  'preview-status', 'swatches', 'code-color-hex', 'code-color-picker',
  'colour-error', 'btn-reset-colour',
  'language-select',
  // The two JSON script blocks the server embeds. They are not elements
  // app.js draws with, but without them every t() call falls back to
  // returning the key, and this harness would stop testing translations
  // at all while still reporting success.
  'i18n-data', 'i18n-meta',
]);

// The swatch colours, mirroring the list rendered into the panel.
const FONT_COLOURS = [
  '#ffd93d', '#93e6a8', '#8ad4e8', '#8fc0f5', '#c9a8f0',
  '#ff9a9a', '#e3c583', '#b4b4b4', '#ffffff', '#000000',
];

const numericIds = new Set([
  'font-size', 'line-height', 'letter-spacing', 'blur-intensity', 'tts-rate',
]);

const lookups = [];
const noop = () => {};
const reloads = [];
let reloadsBefore = 0;

function makeClassList() {
  const set = new Set();
  return {
    add: (c) => set.add(c),
    remove: (c) => set.delete(c),
    toggle: (c, force) => (force === undefined ? (set.has(c) ? set.delete(c) : set.add(c)) : (force ? set.add(c) : set.delete(c))),
    contains: (c) => set.has(c),
  };
}

function makeElement(id, extraAttributes = {}, extraProps = {}) {
  const attributes = {
    'aria-checked': 'true',
    'aria-pressed': 'false',
    'data-theme': 'high-contrast',
    'data-font': 'OpenDyslexic',
    'data-font-size': '16',
    'data-code-color': '',
    'data-line-height': '1.6',
    'data-letter-spacing': '0.5',
    'data-blur-intensity': '0.5',
    'data-focus-mode': 'off',
    'data-contrast': 'normal',
    'data-tts-voice': '',
    'data-tts-rate': '0.9',
    ...extraAttributes,
  };

  // Listeners are recorded rather than discarded so the harness can fire
  // them afterwards. A handler that throws is the failure mode that
  // matters: it silently stops that control working.
  const listeners = {};

  // style is a real object, not a swallowing proxy, so the harness can
  // read back what the code actually set. The preview's resolved colour is
  // the whole point of the panel, and it has to be checkable.
  const style = { setProperty: noop, removeProperty: noop };

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
    style,
    classList: makeClassList(),
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
    ...extraProps,
  };
  el.__listeners = listeners;
  el.__attributes = attributes;
  return el;
}

// The font list, mirroring what routes.py renders into the <option> tags.
// app.js reads the CSS stack from data-family rather than keeping its own
// copy, so these attributes are what the real code depends on.
const FONT_OPTIONS = [
  ['Atkinson Hyperlegible', 'Atkinson Hyperlegible', 'true'],
  ['OpenDyslexic', 'OpenDyslexic', 'true'],
  ['Lexend', 'Lexend', 'true'],
  ['Nunito', 'Nunito', 'true'],
  ['Almarai', 'Almarai (Arabic)', 'true'],
  ['Calibri', 'Calibri', 'false'],
  ['Arial', 'Arial', 'false'],
  ['Comic Sans MS', 'Comic Sans MS', 'false'],
  ['Courier New', 'Courier New', 'false'],
].map(([value, label, bundled]) => makeElement(value, {
  'data-family': `"${value}", sans-serif`,
  'data-bundled': bundled,
}, { value, textContent: label }));

// The font <select> needs a real option list for fontFamilyFor() and
// updateFontNote() to work against.
const FONT_SELECT = makeElement('font-select', {}, { options: FONT_OPTIONS });

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

// The real English catalogue, so the harness exercises the same
// translations the browser would. Reading it from disk means a key that is
// removed from en.json shows up here as a key rather than as empty text.
const CATALOGUE = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, '..', 'src', 'accessible_ide', 'i18n', 'en.json'),
    'utf8'
  )
);
const I18N_SCRIPTS = {
  'i18n-data': makeElement('i18n-data', {}, { textContent: JSON.stringify(CATALOGUE) }),
  'i18n-meta': makeElement(
    'i18n-meta',
    {},
    { textContent: JSON.stringify({ locale: 'en', direction: 'ltr' }) }
  ),
};

const documentStub = {
  body: makeElement('body'),
  documentElement: makeElement('html'),
  // The Settings button has focus when it is pressed, which is the case
  // openSettings/closeSettings are written to handle.
  activeElement: null,
  getElementById: (id) => {
    lookups.push(id);
    if (id === 'font-select') {
      if (!elements.has('font-select')) elements.set('font-select', FONT_SELECT);
      return FONT_SELECT;
    }
    if (id in I18N_SCRIPTS) {
      if (!elements.has(id)) elements.set(id, I18N_SCRIPTS[id]);
      return elements.get(id);
    }
    if (id === 'language-select') {
      // The stub's default value is a font name, which is not a locale.
      if (!elements.has(id)) {
        elements.set(id, makeElement(id, {}, { value: 'en' }));
      }
      return elements.get(id);
    }
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
const configPosts = [];
function fetchStub(url, options) {
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
  if (String(url).includes('/api/config') && options && options.body) {
    try {
      configPosts.push(JSON.parse(options.body));
    } catch (error) {
      configPosts.push({ __unparseable: String(options.body) });
    }
  }
  return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
}

const sandbox = {
  console,
  document: documentStub,
  navigator: { language: 'en-GB', userAgent: 'stub' },
  // app.js asks the operating system whether motion should be reduced. The
  // stub reports "no", which is the ordinary case; the seeding check below
  // then proves the switch can also be flipped the other way.
  matchMedia: (query) => ({
    media: query,
    matches: false,
    addEventListener: noop,
    removeEventListener: noop,
  }),
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
      reload: () => { reloads.push(true); },
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
  ['reduce-motion', 'click'],
  ['tts-toggle', 'click'], ['tts-voice', 'change'],
  ['tts-rate', 'input'], ['tts-rate', 'change'],
  ['btn-test-voice', 'click'],
  ['btn-settings', 'click'], ['btn-settings-close', 'click'],
  ['settings-dialog', 'cancel'],
  ['sample-text', 'input'],
  ['code-color-hex', 'input'], ['code-color-hex', 'change'],
  ['code-color-picker', 'input'], ['code-color-picker', 'change'],
  ['btn-reset-colour', 'click'],
  // language-select is deliberately absent: it is fired below with a real
  // language code, because the reload it triggers has to be counted.
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

// ---------------------------------------------------------------------------
// The "Try it out" panel. These are the checks that matter most: the whole
// point of letting someone choose a colour is that the code stays readable,
// so the resolved colour is measured against the preview background rather
// than assumed to be fine.
//
// This runs after a tick because the theme palette arrives from /api/themes,
// and until it does there is no background to measure against.
// ---------------------------------------------------------------------------

function relativeLuminance(hex) {
  const value = hex.replace('#', '');
  const channels = [0, 2, 4].map((i) => {
    const part = parseInt(value.slice(i, i + 2), 16) / 255;
    return part <= 0.03928 ? part / 12.92 : Math.pow((part + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrastRatio(first, second) {
  const a = relativeLuminance(first);
  const b = relativeLuminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

function fire(id, type, event = fakeEvent) {
  const el = elements.get(id);
  if (!el) return null;
  for (const handler of el.__listeners[type] || []) handler(event);
  return el;
}

function runPanelChecks() {
  const preview = elements.get('font-preview');
  const hexInput = elements.get('code-color-hex');
  const errorText = elements.get('colour-error');
  const swatchGroup = elements.get('swatches');
  const bodyNow = documentStub.body.__attributes;

  if (!preview.style.backgroundColor) {
    failed = true;
    console.log('FAIL the preview was never given the editor background');
    return;
  }

  // Every swatch, and a few colours a reader might invent, must land on
  // the preview as a colour that clears WCAG AA against that background.
  const candidates = [...FONT_COLOURS, '#1a1a1a', '#fefefe', '#808080'];

  for (const candidate of candidates) {
    hexInput.value = candidate;
    fire('code-color-hex', 'input');

    const shown = preview.style.color;
    const background = preview.style.backgroundColor;
    if (!shown || !/^#[0-9a-f]{6}$/i.test(shown)) {
      failed = true;
      console.log(`FAIL choosing ${candidate} left the preview colour as ${shown}`);
      continue;
    }
    const ratio = contrastRatio(shown, background);
    if (ratio < 4.5) {
      failed = true;
      console.log(`FAIL ${candidate} resolved to ${shown} on ${background}, ` +
                  `which is only ${ratio.toFixed(2)}:1`);
    }
    if (bodyNow['data-code-color'] !== candidate) {
      failed = true;
      console.log(`FAIL ${candidate} was not recorded on the body`);
    }
  }
  console.log(`     all ${candidates.length} chosen colours clear 4.5:1 on the preview background`);

  // A half-typed colour must not be nagged about, and must not be stored.
  // Typing "#ff" on the way to "#ffd93d" is normal, and an error box
  // appearing on the first keystroke would be discouraging.
  hexInput.value = '#ff';
  fire('code-color-hex', 'input');
  if (errorText.hidden !== true) {
    failed = true;
    console.log('FAIL a part-typed colour showed an error while the reader was still typing');
  }

  hexInput.value = 'nonsense';
  fire('code-color-hex', 'input');
  if (errorText.hidden !== true) {
    failed = true;
    console.log('FAIL nonsense nagged the reader mid-typing');
  }
  console.log('     part-typed colours are left alone, with no error shown');

  // Leaving the field is where a real mistake is reported - and refused.
  fire('code-color-hex', 'change');
  if (errorText.hidden !== false || !errorText.textContent) {
    failed = true;
    console.log('FAIL leaving the field with nonsense did not explain the problem');
  }
  if (bodyNow['data-code-color'] === 'nonsense') {
    failed = true;
    console.log('FAIL nonsense was saved to the config');
  }

  hexInput.value = 'red';
  fire('code-color-hex', 'change');
  if (bodyNow['data-code-color'] === 'red') {
    failed = true;
    console.log('FAIL a named colour was saved to the config');
  }
  console.log('     a colour that is not a hex code is explained, and never saved');

  // A swatch click records the colour and clears the error.
  hexInput.value = '';
  swatchGroup.__listeners.change.forEach((handler) =>
    handler({ target: { name: 'colour-swatch', value: '#8fc0f5' } }));
  if (bodyNow['data-code-color'] !== '#8fc0f5') {
    failed = true;
    console.log(`FAIL swatch click saved ${bodyNow['data-code-color']} instead of #8fc0f5`);
  }
  if (errorText.hidden !== true) {
    failed = true;
    console.log('FAIL picking a swatch did not clear the earlier error');
  }
  console.log('     swatches record the colour and clear the error');

  // The sample text the reader typed is what the preview shows.
  const sample = elements.get('sample-text');
  sample.value = 'Pack my box with five dozen liquor jugs';
  fire('sample-text', 'input');
  const previewText = elements.get('font-preview-text');
  if (previewText.textContent !== sample.value) {
    failed = true;
    console.log(`FAIL the preview shows "${previewText.textContent}" ` +
                `instead of the typed sample`);
  } else {
    console.log('     the preview follows the sample text');
  }

  // Reset goes back to the theme colour.
  fire('btn-reset-colour', 'click');
  if (bodyNow['data-code-color'] !== '') {
    failed = true;
    console.log(`FAIL reset left data-code-color as "${bodyNow['data-code-color']}"`);
  }
  if (hexInput.value !== '') {
    failed = true;
    console.log('FAIL reset did not clear the hex field');
  }
  console.log('     "Use theme colour" clears the custom colour');
}

// ---------------------------------------------------------------------------
// The language picker. Every string app.js shows now comes from the embedded
// catalogue, so the checks here are that the catalogue is actually in use and
// that choosing a language saves it and reloads, rather than only swapping
// the JavaScript strings and leaving the markup in the old language.
// ---------------------------------------------------------------------------
function runLanguageChecks() {
  const select = elements.get('language-select');
  const body = documentStub.body.__attributes;
  const before = configPosts.length;

  // The firing loop did not touch this control, so nothing is in flight
  // and the counts below are exact.
  select.value = 'fr';
  reloadsBefore = reloads.length;
  fire('language-select', 'change');

  const posted = configPosts.slice(before).map((p) => p.locale).filter(Boolean);
  if (!posted.includes('fr')) {
    failed = true;
    console.log('FAIL choosing a language did not save it: ' +
                JSON.stringify(configPosts.slice(before)));
  }
  if (body['data-locale'] !== 'fr') {
    failed = true;
    console.log(`FAIL data-locale is "${body['data-locale']}" after picking French`);
  } else {
    console.log('     choosing a language saves it and marks the page');
  }

  // The catalogue really is loaded, so t() returns words rather than keys.
  const status = elements.get('preview-status');
  if (status.textContent && status.textContent.indexOf('theme.') === 0) {
    failed = true;
    console.log('FAIL strings still show raw keys: ' + status.textContent);
  } else {
    console.log('     strings come from the catalogue, not raw keys');
  }
}

// Reloading is what re-renders the markup - settings labels, aria labels and
// titles - into the new language, which a JavaScript-only swap could never
// do. The save is a promise, so this runs a tick after the change.
function runLanguageReloadCheck() {
  if (reloads.length !== reloadsBefore + 1) {
    failed = true;
    console.log(`FAIL choosing a language caused ${reloads.length - reloadsBefore} ` +
                'reloads instead of one');
  } else {
    console.log('     the page reloads so the markup is re-rendered');
  }
  runLanguageNoopCheck();
}

// Picking the language already in use must not bounce the page.
function runLanguageNoopCheck() {
  const select = elements.get('language-select');
  const beforeNoop = reloads.length;
  select.value = 'fr';
  fire('language-select', 'change');
  setTimeout(() => {
    if (reloads.length !== beforeNoop) {
      failed = true;
      console.log('FAIL re-picking the current language reloaded the page');
    } else {
      console.log('     re-picking the current language changes nothing');
    }
    runMotionChecks();
  }, 10);
}

// ---------------------------------------------------------------------------
// The reduce-motion switch. The body attribute is what the stylesheet reads,
// so getting it wrong means the switch looks right and the app still moves.
// The firing loop above already clicked it once, so this checks the state
// that click produced rather than starting from scratch.
// ---------------------------------------------------------------------------
function runMotionChecks() {
  const button = elements.get('reduce-motion');
  const label = elements.get('reduce-motion-state');
  const body = documentStub.body.__attributes;

  const flips = body['data-reduce-motion'];
  if (flips !== 'true' && flips !== 'false') {
    failed = true;
    console.log(`FAIL data-reduce-motion is "${flips}" after clicking the switch`);
  } else {
    console.log(`     clicking the switch set data-reduce-motion="${flips}"`);
  }

  if (button.getAttribute('aria-checked') !== flips) {
    failed = true;
    console.log(`FAIL the switch says aria-checked="${button.getAttribute('aria-checked')}" ` +
                `but the page is set to "${flips}"`);
  } else {
    console.log('     the switch and the page agree with each other');
  }

  if (!label.textContent || label.textContent.indexOf('switch.') === 0) {
    failed = true;
    console.log('FAIL the switch label is missing or shows a raw key: ' + label.textContent);
  } else {
    console.log('     the switch label is a translated word');
  }

  const saved = configPosts.filter((p) => 'reduce_motion' in p);
  if (!saved.length) {
    failed = true;
    console.log('FAIL the motion choice was never saved');
  } else if (typeof saved[saved.length - 1].reduce_motion !== 'boolean') {
    failed = true;
    console.log('FAIL reduce_motion was saved as ' +
                JSON.stringify(saved[saved.length - 1].reduce_motion) + ' rather than true/false');
  } else {
    console.log('     the choice is saved as true or false, not "unset"');
  }

  console.log('     fetch calls: ' + (fetchCalls.length ? fetchCalls.join(', ') : '(none)'));
  process.exit(failed ? 1 : 0);
}

setTimeout(() => {
  runPanelChecks();
  runLanguageChecks();
  setTimeout(runLanguageReloadCheck, 10);
}, 50);
