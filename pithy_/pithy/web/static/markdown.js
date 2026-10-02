// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

/*
 * markdown.js defines the `markdown-editor` custom element: a plain textarea with Markdown syntax coloring.
 * It requires markdown.css and has no other dependencies. Usage:
 *
 *   <markdown-editor><textarea name="body">Some *Markdown*.</textarea></markdown-editor>
 *
 * The textarea is ordinary page content: it holds the text, takes all input, and submits with its form.
 * The element adds a coloring layer, drawn over the textarea, that repeats the text as styled spans.
 * The text is never transformed and no syntax is hidden; the editor shows exactly the characters that are submitted.
 * Add the `auto-resize` attribute to grow with the text instead of scrolling at a fixed height.
 *
 * Add the `attachments` attribute to accept pasted images; its value is the form field name for the image files.
 * A pasted image is inserted as a reference, e.g. `![Image 1](attachment:image-1.png)`, and shown in a strip below the text.
 * The text is the source of truth: an image is attached for as long as the text refers to it.
 * Deleting the reference detaches the image, and undoing the deletion attaches it again.
 * On submission the referenced images are added to the form data as files named as in their references.
 * The form must therefore use `method="post"` and `enctype="multipart/form-data"`.
 * The thumbnails use `blob:` URLs; a Content Security Policy must allow them with `img-src blob:`.
 *
 * This file is compatible with a strict Content Security Policy, including Trusted Types.
 * It creates no style elements, sets no style attributes, parses no HTML strings, and evaluates no code.
 *
 * Coloring is computed per line. Fenced code blocks are the only construct tracked across lines;
 * emphasis and links that span a line break are not colored.
 *
 * Scripts that assign `textarea.value` directly must call `refresh()`, because that assignment fires no event.
 * Assigning the element's own `value` property refreshes automatically.
 */

'use strict';

// Style bits for a character. A character can carry several, e.g. a marker inside strong text.
const mdMarker = 1, mdEm = 2, mdStrong = 4, mdStrike = 8, mdCode = 16, mdLink = 32, mdUrl = 64, mdTag = 128, mdList = 256,
  mdComment = 512;

// CSS class names, indexed by style bit position.
const mdClasses = ['md-marker', 'md-em', 'md-strong', 'md-strike', 'md-code', 'md-link', 'md-url', 'md-tag', 'md-list',
  'md-comment'];

// Block patterns. The sticky patterns are applied at an offset by `mdMatchAt`.
const mdFenceOpenRe = /^[ \t]*(`{3,}|~{3,})(.*)$/;
const mdFenceCloseRe = /^[ \t]*(`{3,}|~{3,})[ \t]*$/;
const mdQuoteRe = / {0,3}>[ \t]?/y;
const mdHeadingRe = / {0,3}#{1,6}(?=[ \t]|$)/y;
const mdHeadingCloseRe = /[ \t]+#+[ \t]*$/;
const mdRuleRe = / {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/y;
const mdListRe = /[ \t]*(?:[-*+]|\d{1,9}[.)])(?=[ \t]|$)/y;
const mdTaskRe = /[ \t]+\[[ xX]\](?=[ \t]|$)/y;

// Inline patterns.
const mdCommentRe = /<!--.*?-->/y;
const mdAutolinkRe = /<(?:https?:\/\/|mailto:)[^\s<>]*>/y;
const mdTagRe = /<\/?[A-Za-z][\w.:-]*(?:\s[^<>]*)?\/?>/y;
const mdUrlRe = /https?:\/\/[^\s<>`]+/y;
const mdUrlTrailRe = /[.,;:!?'"*_~]+$/;
const mdEscapableRe = /[!-\/:-@\[-`{-~]/; // ASCII punctuation.
const mdPunctRe = /[\p{P}\p{S}]/u;
const mdSpaceRe = /\s/;
const mdWordRe = /\w/;

// A reference to an attachment, as inserted by a paste.
const mdAttachmentRe = /\]\(attachment:([\w.-]+)\)/g;
const mdAttachmentNumRe = /^image-(\d+)\./;

// File name extensions for the common image types; other types use their subtype.
/** @type {Record<string,string>} */
const mdImageExts = {'image/gif': 'gif', 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'};


class MarkdownEditor extends HTMLElement {

  /** The coloring layer. It is kept when detached so that it can be restored without rendering again.
   * @type {HTMLDivElement|null} */
  #layer = null;

  /** One key per rendered line; equal keys imply equal rendering.
   * @type {string[]} */
  #keys = [];

  /** Pasted images by attachment name, each with a `blob:` URL for its thumbnail.
   * Entries outlive their references so that undo can restore them. The URLs are never revoked, for the same reason.
   * @type {Map<string, {file:File, url:string}>} */
  #attachments = new Map();

  /** The attachment strip. It is in the document only while the text refers to an attachment.
   * @type {HTMLDivElement|null} */
  #strip = null;

  /** The names shown by the strip, joined by newlines. */
  #stripKey = '';

  #observer = new MutationObserver(records => this.#onMutations(records));

  #onInput = () => this.refresh();

  /** @param {Event} event */
  #onReset = (event) => {
    // A form reset changes the text after this event is dispatched and without an input event.
    if (event.target === this.textarea?.form) setTimeout(() => this.refresh());
  };


  /** @param {ClipboardEvent} event */
  #onPaste = (event) => {
    const data = event.clipboardData;
    if (!this.getAttribute('attachments') || !data || event.target !== this.textarea) return;
    // A copy from a document can offer both text and a rendering of it; the text is the better paste.
    if (data.types.includes('text/plain')) return;
    const images = [...data.files].filter(file => file.type.startsWith('image/'));
    if (!images.length) return;
    event.preventDefault();
    this.attach(images);
  };

  /** @param {FormDataEvent} event */
  #onFormData = (event) => {
    const name = this.getAttribute('attachments');
    if (!name || event.target !== this.textarea?.form) return;
    for (const file of this.attachments) event.formData.append(name, file);
  };


  connectedCallback() {
    this.addEventListener('input', this.#onInput);
    this.addEventListener('paste', this.#onPaste);
    document.addEventListener('reset', this.#onReset);
    document.addEventListener('formdata', this.#onFormData); // The event bubbles, and the textarea's form can change.
    // Observe children so that the editor survives DOM replacement, such as an htmx morph or late parsing of the textarea.
    this.#observer.observe(this, {childList: true, subtree: true, characterData: true});
    this.refresh();
  }


  disconnectedCallback() {
    this.removeEventListener('input', this.#onInput);
    this.removeEventListener('paste', this.#onPaste);
    document.removeEventListener('reset', this.#onReset);
    document.removeEventListener('formdata', this.#onFormData);
    this.#observer.disconnect();
  }


  /** The child textarea that holds the text, or null if it is missing.
   * @returns {HTMLTextAreaElement|null} */
  get textarea() {
    const el = this.querySelector(':scope > textarea');
    return el instanceof HTMLTextAreaElement ? el : null;
  }


  /** The Markdown text, exactly as it will be submitted. */
  get value() { return this.textarea?.value ?? ''; }

  set value(text) {
    const textarea = this.textarea;
    if (!textarea) return;
    textarea.value = text;
    this.refresh();
  }


  /** The attached files that the text refers to, in order of first reference. Each is named as in its reference.
   * @returns {File[]} */
  get attachments() {
    return this.#attachmentNames().map(name => mdNonNull(this.#attachments.get(name)).file);
  }


  /**
   * Attach `files` and insert a reference to each at the selection, as a paste does.
   * @param {File[]} files
   */
  attach(files) {
    const textarea = this.textarea;
    if (!textarea) return;
    // Number from the highest number in use, including references that have no attachment, so that names never collide.
    const names = [...this.#attachments.keys(), ...Array.from(textarea.value.matchAll(mdAttachmentRe), m => mdNonNull(m[1]))];
    let num = Math.max(0, ...names.map(name => Number(mdAttachmentNumRe.exec(name)?.[1] ?? 0)));
    const refs = files.map(file => {
      num++;
      const ext = mdImageExts[file.type] ?? (file.type.split('/')[1] ?? '').replace(/\W.*/, '');
      const name = `image-${num}.${ext || 'bin'}`;
      const named = new File([file], name, {type: file.type});
      this.#attachments.set(name, {file: named, url: URL.createObjectURL(named)});
      return `![Image ${num}](attachment:${name})`;
    });
    mdInsertText(textarea, refs.join(' '));
  }


  /** Bring the coloring layer up to date with the textarea. Lines that have not changed keep their elements. */
  refresh() {
    const textarea = this.textarea;
    if (!textarea) return;
    let layer = this.#layer;
    if (!layer) {
      layer = this.#layer = document.createElement('div');
      layer.className = 'md-highlight';
      layer.setAttribute('aria-hidden', 'true');
    }
    if (layer.parentNode !== this) this.append(layer);
    this.#refreshStrip();
    if (layer.childNodes.length !== this.#keys.length) { // The layer was altered externally; render it from scratch.
      layer.replaceChildren();
      this.#keys = [];
    }

    const lines = textarea.value.split('\n');
    /** @type {string[]} */
    const fences = []; // The open fence preceding each line.
    let fence = '';
    const keys = lines.map(line => {
      fences.push(fence);
      const key = fence + '\n' + line;
      fence = mdFenceAfter(line, fence);
      return key;
    });

    // Replace only the lines between the common prefix and the common suffix of the old and new keys.
    const oldKeys = this.#keys;
    let start = 0;
    while (start < oldKeys.length && start < keys.length && oldKeys[start] === keys[start]) start++;
    let oldEnd = oldKeys.length;
    let end = keys.length;
    while (oldEnd > start && end > start && oldKeys[oldEnd - 1] === keys[end - 1]) { oldEnd--; end--; }
    const following = layer.childNodes[oldEnd] ?? null;
    for (let i = start; i < oldEnd; i++) mdNonNull(layer.childNodes[start]).remove();
    for (let i = start; i < end; i++) layer.insertBefore(mdLineElement(mdNonNull(lines[i]), mdNonNull(fences[i])), following);
    this.#keys = keys;
  }


  /** The names of the attachments that the text refers to, in order of first reference.
   * @returns {string[]} */
  #attachmentNames() {
    const names = Array.from(this.value.matchAll(mdAttachmentRe), m => mdNonNull(m[1]));
    return [...new Set(names)].filter(name => this.#attachments.has(name));
  }


  /** Bring the attachment strip up to date with the references in the text. */
  #refreshStrip() {
    const names = this.#attachmentNames();
    let strip = this.#strip;
    if (!names.length) {
      strip?.remove();
      return;
    }
    if (!strip) {
      strip = this.#strip = document.createElement('div');
      strip.className = 'md-attachments';
      this.#stripKey = '';
    }
    const key = names.join('\n');
    if (key !== this.#stripKey || strip.childNodes.length !== names.length) {
      strip.replaceChildren(...names.map(name => {
        const {file, url} = mdNonNull(this.#attachments.get(name));
        const el = document.createElement('span');
        el.className = 'md-attachment';
        const img = document.createElement('img');
        img.src = url;
        img.alt = '';
        el.append(img, `${name} (${mdFormatSize(file.size)})`);
        return el;
      }));
      this.#stripKey = key;
    }
    if (strip.parentNode !== this) this.append(strip);
  }


  /** @param {MutationRecord[]} records */
  #onMutations(records) {
    const layer = this.#layer;
    // Changes within the layer are our own rendering, unless they left it with the wrong number of lines.
    if (!layer || layer.childNodes.length !== this.#keys.length || records.some(record => !layer.contains(record.target))) {
      this.refresh();
    }
  }
}


/**
 * Return the open fence following `line`, given the open fence preceding it.
 * A fence is represented by its opening run of backticks or tildes; the empty string means no fence is open.
 * @param {string} line
 * @param {string} fence
 * @returns {string}
 */
function mdFenceAfter(line, fence) {
  if (fence) return mdIsFenceClose(line, fence) ? '' : fence;
  const m = mdFenceOpenRe.exec(line);
  if (!m) return '';
  const run = mdNonNull(m[1]);
  return (run[0] === '`' && mdNonNull(m[2]).includes('`')) ? '' : run; // The info string of a backtick fence cannot contain one.
}


/**
 * @param {string} line
 * @param {string} fence
 * @returns {boolean}
 */
function mdIsFenceClose(line, fence) {
  const m = mdFenceCloseRe.exec(line);
  if (!m) return false;
  const run = mdNonNull(m[1]);
  return run[0] === fence[0] && run.length >= fence.length;
}


/**
 * Build the element for one line of text.
 * @param {string} line
 * @param {string} fence - The open fence preceding the line.
 * @returns {HTMLDivElement}
 */
function mdLineElement(line, fence) {
  const el = document.createElement('div');
  const styles = new Uint16Array(line.length);
  let className = '';
  if (fence) { // Within a code block.
    className = 'md-code';
    if (mdIsFenceClose(line, fence)) styles.fill(mdMarker);
  } else if (mdFenceAfter(line, fence)) { // The opening fence.
    className = 'md-code';
    const indent = line.length - line.trimStart().length;
    let runEnd = indent;
    while (line[runEnd] === line[indent]) runEnd++;
    styles.fill(mdMarker, indent, runEnd);
  } else {
    className = mdStyleBlock(line, styles);
  }
  if (className) el.className = className;

  if (!line) el.append(document.createElement('br')); // An empty block has no height.
  for (let i = 0; i < line.length;) {
    const style = mdNonNull(styles[i]);
    let j = i + 1;
    while (j < line.length && styles[j] === style) j++;
    const text = line.slice(i, j);
    if (style) {
      const span = document.createElement('span');
      span.className = mdClasses.filter((_, bit) => style & (1 << bit)).join(' ');
      span.textContent = text;
      el.append(span);
    } else {
      el.append(text);
    }
    i = j;
  }
  return el;
}


/**
 * Set the styles for a line outside of a code block. Return the class name for the line.
 * @param {string} line
 * @param {Uint16Array} styles
 * @returns {string}
 */
function mdStyleBlock(line, styles) {
  let className = '';
  let pos = 0;
  for (let end; (end = mdMatchAt(mdQuoteRe, line, pos)) >= 0; pos = end) { // Block quote markers nest.
    styles.fill(mdMarker, pos, end);
    className = 'md-quote';
  }
  let end = mdMatchAt(mdRuleRe, line, pos); // Test for a rule before a list item: `* * *` is a rule.
  if (end >= 0) {
    styles.fill(mdMarker, pos, end);
    return className;
  }
  end = mdMatchAt(mdHeadingRe, line, pos);
  if (end >= 0) {
    styles.fill(mdMarker, pos, end);
    mdStyleInline(line, end, styles);
    const close = mdHeadingCloseRe.exec(line);
    if (close && close.index >= end) styles.fill(mdMarker, close.index);
    return (className + ' md-heading').trimStart();
  }
  end = mdMatchAt(mdListRe, line, pos);
  if (end >= 0) {
    styles.fill(mdList, pos, end);
    pos = end;
    end = mdMatchAt(mdTaskRe, line, pos);
    if (end >= 0) {
      styles.fill(mdList, pos, end);
      pos = end;
    }
  }
  mdStyleInline(line, pos, styles);
  return className;
}


/**
 * Set the styles for inline constructs in `text` from `start` to the end.
 * @param {string} text
 * @param {number} start
 * @param {Uint16Array} styles
 */
function mdStyleInline(text, start, styles) {
  /** @param {number} bits @param {number} from @param {number} to */
  function add(bits, from, to) {
    for (let k = from; k < to; k++) styles[k] = mdNonNull(styles[k]) | bits;
  }
  const length = text.length;
  /** @type {MdDelimiter[]} */
  const delimiters = [];
  /** @type {number[]} */
  const brackets = []; // Positions of unmatched opening brackets.

  for (let i = start; i < length;) {
    const char = mdNonNull(text[i]);

    if (char === '\\' && i + 1 < length && mdEscapableRe.test(mdNonNull(text[i + 1]))) {
      add(mdMarker, i, i + 1);
      i += 2;
      continue;
    }

    if (char === '`') { // A code span closes at the next run of backticks of equal length.
      let open = i + 1;
      while (text[open] === '`') open++;
      const count = open - i;
      let close = -1;
      for (let j = open; j < length;) {
        if (text[j] !== '`') { j++; continue; }
        let runEnd = j + 1;
        while (text[runEnd] === '`') runEnd++;
        if (runEnd - j === count) { close = j; break; }
        j = runEnd;
      }
      if (close >= 0) {
        add(mdCode | mdMarker, i, open);
        add(mdCode, open, close);
        add(mdCode | mdMarker, close, close + count);
        i = close + count;
      } else {
        i = open;
      }
      continue;
    }

    if (char === '<') {
      let end = mdMatchAt(mdCommentRe, text, i);
      if (end >= 0) {
        add(mdComment, i, end);
        i = end;
        continue;
      }
      end = mdMatchAt(mdAutolinkRe, text, i);
      if (end >= 0) {
        add(mdMarker, i, i + 1);
        add(mdUrl, i + 1, end - 1);
        add(mdMarker, end - 1, end);
        i = end;
        continue;
      }
      end = mdMatchAt(mdTagRe, text, i);
      if (end >= 0) {
        add(mdTag, i, end);
        i = end;
        continue;
      }
    }

    if (char === '[') {
      brackets.push(i);
      i++;
      continue;
    }

    if (char === ']' && brackets.length) { // An inline link or image: `[text](destination)`.
      const open = mdNonNull(brackets.pop());
      const close = (text[i + 1] === '(') ? mdParenClose(text, i + 2) : -1;
      if (close >= 0) {
        const isImage = open > start && text[open - 1] === '!';
        add(mdMarker, isImage ? open - 1 : open, open + 1);
        add(mdLink, open + 1, i);
        add(mdMarker, i, i + 2);
        add(mdUrl, i + 2, close);
        add(mdMarker, close, close + 1);
        i = close + 1;
        continue;
      }
    }

    if (char === '*' || char === '_' || char === '~') { // Record the delimiter run; they are paired below.
      let end = i + 1;
      while (text[end] === char) end++;
      const prev = i > start ? mdNonNull(text[i - 1]) : ' ';
      const next = text[end] ?? ' ';
      const prevSpace = mdSpaceRe.test(prev), nextSpace = mdSpaceRe.test(next);
      const prevPunct = mdPunctRe.test(prev), nextPunct = mdPunctRe.test(next);
      const left = !nextSpace && (!nextPunct || prevSpace || prevPunct); // Left-flanking, as defined by CommonMark.
      const right = !prevSpace && (!prevPunct || nextSpace || nextPunct);
      const intraword = char === '_'; // Underscores within a word are not emphasis.
      delimiters.push({char, pos: i, count: end - i, length: end - i,
        canOpen: left && (!intraword || !right || prevPunct),
        canClose: right && (!intraword || !left || nextPunct)});
      i = end;
      continue;
    }

    if (char === 'h' && (i === start || !mdWordRe.test(mdNonNull(text[i - 1])))) { // A bare URL.
      let end = mdMatchAt(mdUrlRe, text, i);
      if (end >= 0) {
        end -= mdUrlTrailRe.exec(text.slice(i, end))?.[0].length ?? 0; // Sentence punctuation is not part of the URL.
        for (let depth = 0, k = i; k < end; k++) { // Nor is a closing parenthesis that the URL did not open.
          if (text[k] === '(') depth++;
          else if (text[k] === ')' && --depth < 0) { end = k; break; }
        }
        add(mdUrl, i, end);
        i = end;
        continue;
      }
    }

    i++;
  }

  // Pair the delimiter runs, following the CommonMark emphasis algorithm.
  for (let closerIdx = 0; closerIdx < delimiters.length; closerIdx++) {
    const closer = mdNonNull(delimiters[closerIdx]);
    if (!closer.canClose) continue;
    while (closer.count > 0) {
      let openerIdx = closerIdx - 1;
      for (; openerIdx >= 0; openerIdx--) {
        const opener = mdNonNull(delimiters[openerIdx]);
        if (opener.char !== closer.char || !opener.canOpen || opener.count === 0) continue;
        if (closer.char === '~') { // Strikethrough uses one or two tildes, matched in number.
          if (opener.count === closer.count && closer.count <= 2) break;
          continue;
        }
        // The "rule of three" disambiguates runs that can both open and close.
        const isAmbiguous = (opener.canClose || closer.canOpen) && (opener.length + closer.length) % 3 === 0
          && (opener.length % 3 !== 0 || closer.length % 3 !== 0);
        if (!isAmbiguous) break;
      }
      if (openerIdx < 0) break;
      const opener = mdNonNull(delimiters[openerIdx]);
      const used = (closer.char === '~') ? closer.count : ((opener.count >= 2 && closer.count >= 2) ? 2 : 1);
      const style = (closer.char === '~') ? mdStrike : ((used === 2) ? mdStrong : mdEm);
      const openEnd = opener.pos + opener.count; // The opener is consumed from its end; the closer from its start.
      add(mdMarker, openEnd - used, openEnd);
      add(style, openEnd, closer.pos);
      add(mdMarker, closer.pos, closer.pos + used);
      opener.count -= used;
      closer.pos += used;
      closer.count -= used;
      for (let k = openerIdx + 1; k < closerIdx; k++) mdNonNull(delimiters[k]).count = 0; // Enclosed runs cannot pair outward.
    }
  }
}


/**
 * A run of emphasis or strikethrough delimiter characters.
 * `count` is the number of characters not yet paired; `length` is the original count.
 * @typedef {{char:string, pos:number, count:number, length:number, canOpen:boolean, canClose:boolean}} MdDelimiter
 */


/**
 * Return the index of the parenthesis closing a link destination that begins at `from`, or -1.
 * @param {string} text
 * @param {number} from
 * @returns {number}
 */
function mdParenClose(text, from) {
  let depth = 1;
  for (let i = from; i < text.length; i++) {
    const char = text[i];
    if (char === '\\') i++;
    else if (char === '(') depth++;
    else if (char === ')' && --depth === 0) return i;
  }
  return -1;
}


/**
 * Replace the selection of `textarea` with `text`, as if typed.
 * @param {HTMLTextAreaElement} textarea
 * @param {string} text
 */
function mdInsertText(textarea, text) {
  textarea.focus();
  // `execCommand` is deprecated, but it is the only insertion that joins the undo history of the textarea.
  if (document.execCommand('insertText', false, text)) return;
  textarea.setRangeText(text, textarea.selectionStart, textarea.selectionEnd, 'end');
  textarea.dispatchEvent(new InputEvent('input', {bubbles: true}));
}


/**
 * @param {number} size - A byte count.
 * @returns {string}
 */
function mdFormatSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} kB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}


/**
 * Match the sticky pattern `re` at `pos`. Return the end index of the match, or -1.
 * @param {RegExp} re
 * @param {string} text
 * @param {number} pos
 * @returns {number}
 */
function mdMatchAt(re, text, pos) {
  re.lastIndex = pos;
  return re.test(text) ? re.lastIndex : -1;
}


/**
 * @template T
 * @param {T} val
 * @returns {NonNullable<T>}
 */
function mdNonNull(val) {
  if (val == null) throw new Error('Unexpected null value.');
  return val;
}


customElements.define('markdown-editor', MarkdownEditor); // Last, because defining upgrades existing elements immediately.
