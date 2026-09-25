/* ============================================================
   AccessibleIDE - Frontend logic
   CodeMirror editor, code runner, config persistence, TTS
   ============================================================ */

(function () {
  'use strict';

  // ---------- Translations ----------
  // The server renders the page in the chosen language and embeds the same
  // catalogue here, so every string below comes from one JSON file rather
  // than being written out twice. A missing key shows the key itself, which
  // is deliberate: tests/test_i18n.py fails on that, and a reader would
  // rather see a gap than silently get English in the middle of Hindi.
  var CATALOGUE = {};
  var META = { locale: 'en', direction: 'ltr' };
  try {
    CATALOGUE = JSON.parse(document.getElementById('i18n-data').textContent) || {};
    META = JSON.parse(document.getElementById('i18n-meta').textContent) || META;
  } catch (err) {
    // No embedded catalogue: fall back to whatever the server already put
    // in the page. The page still works, just without JS-side strings.
  }

  function t(key) {
    var text = CATALOGUE[key];
    if (typeof text !== 'string') return key;
    var args = Array.prototype.slice.call(arguments, 1);
    for (var i = 0; i < args.length; i++) {
      text = text.split('{' + i + '}').join(args[i]);
    }
    return text;
  }

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
  var ttsVoiceGenderEl = document.getElementById('tts-voice-gender');
  var ttsHoverScopeEl = document.getElementById('tts-hover-scope');
  var ttsHoverDelay = document.getElementById('tts-hover-delay');
  var ttsHoverDelayLabel = document.getElementById('tts-hover-delay-label');
  var ttsClickEl = document.getElementById('tts-click');
  var ttsClickState = document.getElementById('tts-click-state');
  var ttsState = document.getElementById('tts-state');
  var btnReduceMotion = document.getElementById('reduce-motion');
  var reduceMotionState = document.getElementById('reduce-motion-state');
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
  var languageSelect = document.getElementById('language-select');

  var body = document.body;
  var ttsEnabled = btnTts.getAttribute('aria-checked') === 'true';
  // True, false, or null while the reader has not chosen and the system
  // preference is standing in.
  var reduceMotion = null;
  var accessCode = localStorage.getItem('accessible_ide_code') || '';
  var settingsOpener = null;
  var speechRate = 0.9;
  var speechVoiceName = '';
  var ttsHoverScopeValue = 'controls';
  var ttsHoverDelayMs = 600;
  var ttsClickToSpeak = true;
  var ttsVoiceGenderValue = 'male';

  // The blur slider only means something while the "fade the other
  // lines" focus mode is on, so it is disabled rather than hidden -
  // hidden would make the panel jump around as you switch modes.
  function syncBlurField() {
    blurField.classList.toggle('is-disabled', focusMode.value !== 'lines');
    blurIntensity.disabled = focusMode.value !== 'lines';
  }

  function promptForAccessCode() {
    var code = window.prompt(t('error.access_code_prompt'));
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
      // Theme names are proper-noun-ish labels the reader has to scan, so
      // they come from the catalogue like every other visible word. The
      // server name is the fallback for a theme added without a translation.
      var translated = CATALOGUE['theme.' + key];
      option.textContent = typeof translated === 'string' ? translated : themes[key].name;
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
    // The server needs a locale so the sentences it sends back match what
    // is on screen. A caller that is changing the language passes its own,
    // and that has to win - overwriting it here made the picker save
    // nothing at all and reload straight back into the old language.
    if (payload.locale) {
      META.locale = payload.locale;
    } else {
      payload.locale = META.locale;
    }
    return fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (result) {
        if (result.ok) {
          if (settingsStatus) {
            settingsStatus.textContent = t('settings.saved');
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
          settingsStatus.textContent = t('settings.not_saved');
          settingsStatus.classList.add('is-error');
        }
      });
  }

  function reportSaveError(data) {
    if (!settingsStatus) return;
    settingsStatus.textContent = (data && data.error) || t('settings.save_failed');
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
  // The browser already knows how to read a line out loud; what it does not
  // know is that this app is meant for people who would rather not have to
  // work out what a button does before pressing it. So four separate
  // decisions decide whether something is spoken: what its name is, whether
  // it is worth saying, which voice says it, and whether to wait first.
  //
  // Nothing here touches the editor or the output. Those are the places
  // where speaking on hover turns into noise - a reader moving the pointer
  // across a screen of code would set off a queue of voices, and worse,
  // cancel the error they were trying to hear.
  var MAX_SPEECH_CHARS = 400;

  // Never read aloud, at any scope: the places a hover would be a nuisance
  // rather than a help.
  var NEVER_SPOKEN = '#editor, #output, .CodeMirror, [contenteditable=""], '
    + '[contenteditable="true"]';

  // What "the things that do something" means for the hover scope. Inputs
  // and selects are in here because their label is exactly the thing a
  // reader wants before touching them, and the name of a text field is
  // usually the one thing the page does not show in the same place.
  var HOVER_CONTROLS = 'button, a[href], input, select, textarea, [role="switch"], '
    + '[role="button"], [role="tab"], summary, label, legend, h1, h2, h3, h4, h5, h6, th';

  // Only read when the scope is "all". This is the difference between a
  // helpful app and an unusable one, which is why it is the reader's call.
  var HOVER_TEXT = 'p, li, td, dt, dd, blockquote, figcaption, caption, '
    + '.field-help, .settings-legend, .switch-text, .notice, .tagline';

  function cleanText(text) {
    return String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
  }

  // Element.closest is avoided deliberately: walking the chain by hand is
  // the same answer, and the DOM test harness has no layout engine to
  // implement it with.
  function closestOf(el, selectors) {
    var node = el;
    while (node && node !== document.body) {
      if (node.matches && node.matches(selectors)) return node;
      node = node.parentNode;
    }
    return null;
  }

  function isHidden(el) {
    return !!(closestOf(el, '[hidden], [aria-hidden="true"]'));
  }

  // The name of a thing, in the order a screen reader would go looking for
  // it. Returns an empty string when there is genuinely nothing to say,
  // which is the signal not to speak rather than to read out a stray
  // punctuation mark.
  function labelFor(el) {
    if (!el) return '';
    var tag = (el.tagName || '').toLowerCase();
    var name = cleanText(el.getAttribute && el.getAttribute('aria-label'));

    if (!name && el.labels && el.labels.length) {
      name = cleanText(el.labels[0].textContent);
    }
    if (!name) {
      var wrapping = closestOf(el, 'label');
      if (wrapping) name = cleanText(wrapping.textContent);
    }

    // A control's own text: what a button says, or which option a
    // dropdown is currently showing. Reading only the label of a dropdown
    // would leave the reader knowing the field name and none of its
    // contents.
    var own = '';
    if (tag === 'select') {
      var option = el.options && el.selectedIndex >= 0
        ? el.options[el.selectedIndex]
        : null;
      own = cleanText(option && (option.textContent || option.text));
    } else if (tag === 'input') {
      if (el.type === 'checkbox' || el.type === 'radio') {
        own = el.checked ? t('speak.on') : t('speak.off');
      } else if (el.type === 'range' || el.type === 'number') {
        own = cleanText(el.value);
      } else {
        own = cleanText(el.getAttribute && el.getAttribute('placeholder'));
      }
    } else if (tag === 'img') {
      own = '';
    } else {
      own = cleanText(el.textContent);
    }

    if (own === name) own = '';
    if (name && own) return name + ', ' + own;
    if (own) return own;
    if (name) return name;

    return cleanText(el.getAttribute && el.getAttribute('title'));
  }

  // A switch is read with its state, the way VoiceOver and NVDA read it.
  // Without the state, "Reduce motion" sounds identical whether the app is
  // about to obey the request or ignore it.
  function withState(text, el) {
    if (!el || !el.getAttribute) return text;
    if (el.getAttribute('role') !== 'switch') return text;
    return text + ', ' + t(el.getAttribute('aria-checked') === 'true'
      ? 'speak.on' : 'speak.off');
  }

  function shorten(text) {
    if (text.length <= MAX_SPEECH_CHARS) return text;
    return text.slice(0, MAX_SPEECH_CHARS).replace(/\s+\S*$/, '') + t('speak.cut_off');
  }

  function whatToSay(el) {
    if (!el || isHidden(el) || closestOf(el, NEVER_SPOKEN)) return '';
    return shorten(withState(labelFor(el), el));
  }

  function loadVoices() {
    if (!('speechSynthesis' in window) || !ttsVoice) return;
    var voices = window.speechSynthesis.getVoices() || [];
    if (!voices.length) return;

    var current = ttsVoice.value;
    ttsVoice.innerHTML = '';
    var def = document.createElement('option');
    def.value = '';
    def.textContent = t('speak.system_default');
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

  // The speech API does not report whether a voice is male or female, so
  // this is a guess from the name, and it is only ever a guess: it is used
  // to order the choices, never to hide a voice the reader picked.
  var FEMALE_VOICE_WORDS = 'female|woman|girl|samantha|karen|serena|moira|tessa|fiona|'
    + 'victoria|zira|allison|ava|amelie|katja|lucia|marlene|nicky|petra|helena|susan|'
    + 'agnes|carla|catherine|alice|joana|leila|maja|nora|sonia|paulina';
  var MALE_VOICE_WORDS = 'male|man|boy|david|daniel|alex|fred|thomas|oliver|james|'
    + 'george|paul|mark|rishi|diego|mateo|riccardo|yannick|albert|aaron|ryan|markus';

  function voiceGender(voice) {
    var name = ((voice && voice.name) || '') + ' ' + ((voice && voice.voiceURI) || '');
    var re = new RegExp('\\b(' + FEMALE_VOICE_WORDS + ')\\b', 'i');
    if (re.test(name)) return 'female';
    re = new RegExp('\\b(' + MALE_VOICE_WORDS + ')\\b', 'i');
    if (re.test(name)) return 'male';
    return 'unknown';
  }

  // Voices that sound the right language first, so a Hindi interface is
  // not read by an English voice simply because it was listed earlier.
  function voicesForLocale(voices) {
    var wanted = String(META.locale || 'en').toLowerCase();
    var exact = [];
    var sameLanguage = [];
    var rest = [];
    voices.forEach(function (voice) {
      var lang = String(voice.lang || '').toLowerCase();
      if (lang === wanted) exact.push(voice);
      else if (lang.split(/[-_]/)[0] === wanted.split(/[-_]/)[0]) sameLanguage.push(voice);
      else rest.push(voice);
    });
    return exact.concat(sameLanguage, rest);
  }

  function pickVoice() {
    if (!('speechSynthesis' in window)) return null;
    var voices = window.speechSynthesis.getVoices() || [];
    if (!voices.length) return null;

    // A voice the reader chose themselves always wins, whatever the
    // gender preference says. They can see the name; the app cannot.
    for (var i = 0; i < voices.length; i++) {
      if (speechVoiceName && voices[i].name === speechVoiceName) return voices[i];
    }
    if (speechVoiceName || ttsVoiceGenderValue === 'any') return null;

    var ordered = voicesForLocale(voices);
    for (var j = 0; j < ordered.length; j++) {
      if (voiceGender(ordered[j]) === ttsVoiceGenderValue) return ordered[j];
    }
    // Nothing installed matches the preference. Saying nothing would be
    // worse than a wrong guess, so the browser picks its own default.
    return null;
  }

  function speak(text) {
    if (!('speechSynthesis' in window)) return;
    var words = cleanText(text);
    if (!words) return;
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(words);
    utterance.rate = speechRate;
    utterance.pitch = 1.0;
    // Without this the voice reads Hindi and French words in an English
    // accent, which is the one thing that makes a foreign interface
    // genuinely hard to follow.
    if (META.locale) utterance.lang = META.locale;
    var voice = pickVoice();
    if (voice) utterance.voice = voice;
    window.speechSynthesis.speak(utterance);
  }

  // ---------- Hover and click ----------
  // Both are delegated from the document, so the page does not grow a
  // listener every time the editor is redrawn.
  var hoverTimer = null;
  var hoverTarget = null;

  function hoverTargetFor(el) {
    if (ttsHoverScope === 'off' || !ttsEnabled) return null;
    var control = closestOf(el, HOVER_CONTROLS);
    if (control) return control;
    if (ttsHoverScope !== 'all') return null;
    return closestOf(el, HOVER_TEXT);
  }

  function clearHover() {
    if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
      hoverTimer = null;
    }
    hoverTarget = null;
  }

  function onMouseOver(event) {
    var target = hoverTargetFor(event && event.target);
    if (!target) {
      clearHover();
      return;
    }
    // Moving between a button and the words inside it is still one thing
    // under the pointer, and a screen reader would not repeat itself here.
    if (target === hoverTarget) return;
    clearHover();
    hoverTarget = target;
    hoverTimer = setTimeout(function () {
      hoverTimer = null;
      var words = whatToSay(hoverTarget);
      if (words) speak(words);
    }, Math.max(0, ttsHoverDelay || 0));
  }

  function onMouseOut(event) {
    var from = hoverTargetFor(event && event.target);
    if (!from) return;
    var to = hoverTargetFor(event && event.relatedTarget);
    if (to === from) return;
    clearHover();
  }

  // Capture phase, and this is the whole reason for it. A click on Run
  // starts the program, whose output then speaks and replaces whatever was
  // said here. Speaking the button name afterwards would cancel the output
  // the reader actually asked for.
  function onClick(event) {
    if (!ttsClickToSpeak || !ttsEnabled) return;
    var el = event && event.target;
    if (!el || closestOf(el, NEVER_SPOKEN)) return;
    if (el.disabled) return;
    var words = whatToSay(el);
    if (words) speak(words);
  }

  document.addEventListener('mouseover', onMouseOver);
  document.addEventListener('mouseout', onMouseOut);
  document.addEventListener('click', onClick, true);

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
    outputEl.textContent = t('output.running');
    errorPanel.hidden = true;
    clearErrorMarkers();

    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code, access_code: accessCode, locale: META.locale })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.code_required) {
          if (promptForAccessCode()) {
            runCode();
          } else {
            outputEl.textContent = t('output.locked');
            errorMessage.textContent = data.error;
            errorPanel.hidden = false;
          }
          return;
        }
        outputEl.textContent = data.output || t('output.no_output');
        if (data.error) {
          errorMessage.textContent = data.error;
          errorPanel.hidden = false;
          highlightErrorLine(data.error_line);
          if (ttsEnabled) speak(data.error);
        } else {
          errorPanel.hidden = true;
          if (ttsEnabled) speak(data.output || t('speak.finished'));
        }
      })
      .catch(function () {
        outputEl.textContent = t('output.runner_unreachable');
        errorMessage.textContent = t('output.server_down');
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
        types: [{ description: t('file.python_type'), accept: { 'text/x-python': ['.py'] } }]
      })
        .then(function (handle) { return handle.createWritable(); })
        .then(function (writable) {
          return writable.write(content).then(function () { return writable.close(); });
        })
        .then(function () {
          outputEl.textContent = t('output.saved');
          errorPanel.hidden = true;
        })
        .catch(function (err) {
          if (err.name !== 'AbortError') {
            outputEl.textContent = t('output.save_failed');
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
      outputEl.textContent = t('output.downloaded');
      errorPanel.hidden = true;
    }
  }

  function openFile() {
    if (window.showOpenFilePicker) {
      window.showOpenFilePicker({
        types: [{ description: t('file.python_type'), accept: { 'text/x-python': ['.py'] } }]
      })
        .then(function (handles) { return handles[0].getFile(); })
        .then(function (file) { return file.text(); })
        .then(function (text) {
          editor.setValue(text);
          clearErrorMarkers();
          outputEl.textContent = t('output.opened');
          errorPanel.hidden = true;
        })
        .catch(function (err) {
          if (err.name !== 'AbortError') {
            outputEl.textContent = t('output.open_failed');
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
      outputEl.textContent = t('output.opened');
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
    if (ttsState) ttsState.textContent = ttsEnabled ? t('speak.on') : t('speak.off');
    saveConfig({ tts_enabled: ttsEnabled });
    if (ttsEnabled) {
      speak(t('speak.enabled'));
    }
  });

  // ---------- Motion ----------
  // The CSS stops transitions and animations when the body says so. What
  // this switch has to get right is the difference between "off" and "not
  // chosen yet": until the reader picks, the operating system preference
  // decides, and the switch shows whatever the system is asking for rather
  // than sitting at a default the reader never agreed to.
  var prefersReducedMotion = window.matchMedia
    ? window.matchMedia('(prefers-reduced-motion: reduce)')
    : { matches: false, addEventListener: null };

  function systemPrefersReducedMotion() {
    return !!(prefersReducedMotion && prefersReducedMotion.matches);
  }

  function paintMotionSwitch() {
    if (!btnReduceMotion) return;
    var on = reduceMotion;
    btnReduceMotion.setAttribute('aria-checked', on ? 'true' : 'false');
    btnReduceMotion.classList.toggle('active', on);
    if (reduceMotionState) {
      reduceMotionState.textContent = on ? t('switch.on') : t('switch.off');
    }
  }

  function applyMotion(on) {
    // 'unset' is never sent back: by this point the system preference has
    // been folded in, and the attribute is always a real answer.
    body.setAttribute('data-reduce-motion', on ? 'true' : 'false');
    reduceMotion = on;
    paintMotionSwitch();
  }

  reduceMotion = body.getAttribute('data-reduce-motion') === 'true';
  if (body.getAttribute('data-reduce-motion') === 'unset') {
    // First run, or nobody has chosen yet: follow the system without
    // writing anything to disk, so a later change to the system setting
    // still takes effect.
    reduceMotion = systemPrefersReducedMotion();
    body.setAttribute('data-reduce-motion', reduceMotion ? 'true' : 'false');
  }
  paintMotionSwitch();

  // While nothing has been chosen, a change in the system setting should
  // take effect without a reload. Once the reader has chosen, their choice
  // stands and the system no longer gets a say here.
  var motionChosenByReader = body.getAttribute('data-reduce-motion') !== 'unset';
  if (prefersReducedMotion && prefersReducedMotion.addEventListener) {
    prefersReducedMotion.addEventListener('change', function () {
      if (!motionChosenByReader) applyMotion(systemPrefersReducedMotion());
    });
  }

  if (btnReduceMotion) {
    btnReduceMotion.addEventListener('click', function () {
      applyMotion(!reduceMotion);
      motionChosenByReader = true;
      saveConfig({ reduce_motion: reduceMotion });
    });
  }

  // ---------- Language ----------
  // Changing the language re-renders the whole page rather than swapping
  // text in place. Every string in the app comes from one catalogue, so the
  // server can produce a page that is entirely in the new language --
  // including the parts that live in HTML attributes, which a client-side
  // pass would leave behind in the old language. The setting is saved
  // first so a reload in the new language cannot bounce back.
  if (languageSelect) {
    languageSelect.addEventListener('change', function () {
      var chosen = languageSelect.value;
      if (!chosen || chosen === META.locale) return;
      body.setAttribute('data-locale', chosen);
      saveConfig({ locale: chosen }).then(function () {
        window.location.reload();
      });
    });
  }

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
      ? t('try.bundled', note)
      : t('try.system_font', note);
    fontBundledNote.hidden = false;
  }

  function updatePreview() {
    if (!fontPreview) return;
    var palette = themePalette[themeSelect.value] || themePalette;
    var shown = codeTextColor(palette);
    var option = fontSelect.options[fontSelect.selectedIndex];
    var name = option ? option.textContent : t('try.your_font');
    var sample = sampleText && sampleText.value ? sampleText.value : ' ';

    fontPreview.style.fontFamily = fontFamilyFor(fontSelect.value);
    fontPreview.style.fontSize = fontSize.value + 'px';
    // The preview uses the editor's own background and the same resolved
    // text colour, so it cannot drift from what the editor will show.
    if (palette.bg) fontPreview.style.backgroundColor = palette.bg;
    fontPreview.style.color = shown;

    if (fontPreviewText) fontPreviewText.textContent = sample;

    if (previewStatus) {
      var nudged = customCodeColor
        && shown.toLowerCase() !== customCodeColor.toLowerCase();
      var text = customCodeColor
        ? t('try.status_custom', name, customCodeColor)
        : t('try.status_theme', name);
      if (nudged) {
        text += ' ' + t('try.status_nudged', shown);
      }
      previewStatus.textContent = text;
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
        showColourError(t('try.error_not_hex'));
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

  // ---------- Hover and click settings ----------
  // The delay is shown in whichever unit the reader can picture: 600 means
  // nothing, 1500 means something. Asking someone to translate 1200 into
  // "is that a long pause" is the kind of small arithmetic that gets in
  // the way of the thing being read.
  function paintHoverDelay(ms) {
    if (!ttsHoverDelayLabel) return;
    if (ms >= 1000) {
      ttsHoverDelayLabel.textContent = (ms / 1000).toFixed(1) + 's';
    } else {
      ttsHoverDelayLabel.textContent = ms + 'ms';
    }
  }

  function paintClickSwitch() {
    if (!ttsClickEl) return;
    ttsClickEl.setAttribute('aria-checked', ttsClickToSpeak ? 'true' : 'false');
    ttsClickEl.classList.toggle('active', ttsClickToSpeak);
    if (ttsClickState) {
      ttsClickState.textContent = ttsClickToSpeak ? t('speak.on') : t('speak.off');
    }
  }

  if (ttsHoverScopeEl) {
    ttsHoverScopeEl.addEventListener('change', function () {
      ttsHoverScopeValue = ttsHoverScopeEl.value;
      // Anything already waiting would now be speaking the wrong amount of
      // the page, so it is dropped rather than left to arrive late.
      clearHover();
      saveConfig({ tts_hover_scope: ttsHoverScopeValue });
    });
  }

  if (ttsHoverDelay) {
    ttsHoverDelay.addEventListener('input', function () {
      ttsHoverDelayMs = parseFloat(ttsHoverDelay.value);
      paintHoverDelay(ttsHoverDelayMs);
    });
    ttsHoverDelay.addEventListener('change', function () {
      saveConfig({ tts_hover_delay: ttsHoverDelayMs });
    });
  }

  if (ttsVoiceGenderEl) {
    ttsVoiceGenderEl.addEventListener('change', function () {
      ttsVoiceGenderValue = ttsVoiceGenderEl.value;
      saveConfig({ tts_voice_gender: ttsVoiceGenderValue });
    });
  }

  if (ttsClickEl) {
    ttsClickEl.addEventListener('click', function () {
      ttsClickToSpeak = !ttsClickToSpeak;
      paintClickSwitch();
      saveConfig({ tts_click_to_speak: ttsClickToSpeak });
    });
  }


  btnTestVoice.addEventListener('click', function () {
    speak(t('speak.demo'));
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

  // The hover and click settings are read from the body rather than from
  // the controls, so the saved answer is what governs from the first
  // pointer movement - a reader should not have to open Settings for
  // hovering to start working.
  ttsHoverScopeValue = body.getAttribute('data-tts-hover-scope') || 'controls';
  ttsHoverDelayMs = parseFloat(body.getAttribute('data-tts-hover-delay') || '600');
  if (isNaN(ttsHoverDelayMs)) ttsHoverDelayMs = 600;
  ttsVoiceGenderValue = body.getAttribute('data-tts-voice-gender') || 'male';
  ttsClickToSpeak = true;
  if (ttsClickEl) {
    ttsClickToSpeak = ttsClickEl.getAttribute('aria-checked') === 'true';
  }
  if (ttsHoverScopeEl) ttsHoverScopeEl.value = ttsHoverScopeValue;
  if (ttsHoverDelay) ttsHoverDelay.value = String(ttsHoverDelayMs);
  if (ttsVoiceGenderEl) ttsVoiceGenderEl.value = ttsVoiceGenderValue;
  paintHoverDelay(ttsHoverDelayMs);
  paintClickSwitch();

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