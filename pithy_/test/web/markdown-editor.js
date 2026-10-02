// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

// Checks for markdown-editor.html. Serve the pithy repository root and open that page in a browser.

'use strict';

/** @type {string[]} */
const cspViolations = [];
document.addEventListener('securitypolicyviolation', event => {
  cspViolations.push(`${event.violatedDirective}: ${event.blockedURI}`);
});


/**
 * Coloring cases: Markdown text and the expected layer, as written by `describeLayer`.
 * @type {[string, string][]}
 */
const coloringCases = [
  ['plain text', '|plain text'],
  ['', '|<br>'],
  ['# Title', 'heading|{marker:#} Title'],
  ['## Two ##', 'heading|{marker:##} Two{marker: ##}'],
  ['#hashtag', '|#hashtag'],
  ['> quoted *text*', 'quote|{marker:> }quoted {marker:*}{em:text}{marker:*}'],
  ['> # Quoted heading', 'quote heading|{marker:> #} Quoted heading'],
  ['- item', '|{list:-} item'],
  ['  12. item', '|{list:  12.} item'],
  ['- [x] done', '|{list:- [x]} done'],
  ['-not a list', '|-not a list'],
  ['* * *', '|{marker:* * *}'],
  ['---', '|{marker:---}'],
  ['a **b** c', '|a {marker:**}{strong:b}{marker:**} c'],
  ['a __b__ c', '|a {marker:__}{strong:b}{marker:__} c'],
  ['***both***', '|{marker:*}{marker em:**}{em strong:both}{marker em:**}{marker:*}'],
  ['**a *b* c**', '|{marker:**}{strong:a }{marker strong:*}{em strong:b}{marker strong:*}{strong: c}{marker:**}'],
  ['snake_case_name and 2 * 3 * 4', '|snake_case_name and 2 * 3 * 4'],
  ['unclosed *text', '|unclosed *text'],
  ['~~gone~~ and ~one~', '|{marker:~~}{strike:gone}{marker:~~} and {marker:~}{strike:one}{marker:~}'],
  ['escaped \\*not em\\*', '|escaped {marker:\\}*not em{marker:\\}*'],
  ['use `a*b*` here', '|use {marker code:`}{code:a*b*}{marker code:`} here'],
  ['``a ` b``', '|{marker code:``}{code:a ` b}{marker code:``}'],
  ['unclosed ` tick *em*', '|unclosed ` tick {marker:*}{em:em}{marker:*}'],
  ['[text](https://example.com/a_b_c)', '|{marker:[}{link:text}{marker:](}{url:https://example.com/a_b_c}{marker:)}'],
  ['![alt](img.png)', '|{marker:![}{link:alt}{marker:](}{url:img.png}{marker:)}'],
  ['[a](b(c)d) e', '|{marker:[}{link:a}{marker:](}{url:b(c)d}{marker:)} e'],
  ['[not a link] (x)', '|[not a link] (x)'],
  ['see https://example.com/x_y. Next', '|see {url:https://example.com/x_y}. Next'],
  ['(https://example.com/a)', '|({url:https://example.com/a})'],
  ['<https://example.com>', '|{marker:<}{url:https://example.com}{marker:>}'],
  ['<example name="x">text</example>', '|{tag:<example name="x">}text{tag:</example>}'],
  ['a < b and c > d', '|a < b and c > d'],
  ['<!-- note --> text', '|{comment:<!-- note -->} text'],
];

/** Multi-line cases; lines are joined by newlines in both columns.
 * @type {[string[], string[]][]} */
const blockCases = [
  [['```python', 'x = *1*', '', '```', '*after*'],
   ['code|{marker:```}python', 'code|x = *1*', 'code|<br>', 'code|{marker:```}', '|{marker:*}{em:after}{marker:*}']],
  [['~~~', '```', '~~~', 'out'], ['code|{marker:~~~}', 'code|```', 'code|{marker:~~~}', '|out']],
  [['````', '```', '````'], ['code|{marker:````}', 'code|```', 'code|{marker:````}']],
  [['  ```', '  # not a heading'], ['code|  {marker:```}', 'code|  # not a heading']],
  [['a', ''], ['|a', '|<br>']],
];


/**
 * Describe the coloring layer as text: one line per element, written `classes|content`,
 * with each span written `{classes:text}` and the `md-` prefixes removed.
 * @param {Element} layer
 * @returns {string}
 */
function describeLayer(layer) {
  return [...layer.children].map(line => {
    const content = [...line.childNodes].map(node => {
      if (node instanceof HTMLBRElement) return '<br>';
      if (node instanceof HTMLSpanElement) return `{${node.className.replace(/md-/g, '')}:${node.textContent}}`;
      return node.textContent;
    }).join('');
    return `${line.className.replace(/md-/g, '')}|${content}`;
  }).join('\n');
}


/** Wait for mutation observers and layout. */
function settle() {
  return new Promise(resolve => requestAnimationFrame(() => resolve(null)));
}


async function runMarkdownEditorTests() {
  /** @type {string[]} */
  const results = [];
  /** @param {unknown} condition @param {string} message */
  function check(condition, message) {
    if (!condition) throw new Error(message);
    results.push(message);
  }
  /** @param {unknown} expected @param {unknown} actual @param {string} message */
  function checkEqual(expected, actual, message) {
    if (expected !== actual) throw new Error(`${message}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
    results.push(message);
  }

  const output = /** @type {HTMLElement} */ (document.querySelector('#results'));
  try {
    const editor = /** @type {MarkdownEditor} */ (document.querySelector('#editor'));
    const textarea = /** @type {HTMLTextAreaElement} */ (document.querySelector('#text'));
    const form = /** @type {HTMLFormElement} */ (document.querySelector('#form'));
    const layer = /** @type {HTMLElement} */ (editor.querySelector('.md-highlight'));
    check(editor instanceof MarkdownEditor && layer, 'The element is defined and has a coloring layer');
    const layerText = () => [...layer.children].map(line => line.textContent).join('\n');

    const initial = '# Initial\n\nLiteral \\n and \\t stay as typed.';
    checkEqual(initial, editor.value, 'Literal backslash sequences in the page source are not converted');
    checkEqual(initial, layerText(), 'The layer shows the initial text');

    for (const [text, expected] of coloringCases) {
      editor.value = text;
      checkEqual(expected, describeLayer(layer), `Coloring: ${JSON.stringify(text)}`);
      checkEqual(text, layerText(), `Text is unaltered: ${JSON.stringify(text)}`);
    }
    for (const [lines, expected] of blockCases) {
      editor.value = lines.join('\n');
      checkEqual(expected.join('\n'), describeLayer(layer), `Blocks: ${JSON.stringify(lines)}`);
    }

    // The textarea must never transform its text.
    for (const text of ['a\\nb\\tc\\r', 'tab\there', '<script>alert(1)</script> & &amp;', '\n\nleading and trailing\n\n', ' ']) {
      editor.value = text;
      checkEqual(text, textarea.value, `Value round trip: ${JSON.stringify(text)}`);
      checkEqual(text, layerText(), `Layer round trip: ${JSON.stringify(text)}`);
      checkEqual(text, new FormData(form).get('markdown'), `Form submission: ${JSON.stringify(text)}`);
    }

    // Geometry: the layer and the textarea must lay out the same text identically at any width.
    const paragraph = 'Wrapping **prose** with `code`, [links](https://example.com/a/long/path?query=value) and <tags> '.repeat(6);
    const sample = `# Heading\n\n${paragraph}\n\n- item ${paragraph}\n\n\`\`\`\n${'x'.repeat(300)}\n\tindented\n\`\`\`\n\n日本語 emoji 🙂 **bold 🙂 text**\n`;
    editor.value = sample;
    for (const autoResize of [false, true]) {
      editor.toggleAttribute('auto-resize', autoResize);
      for (const width of ['900px', '613px', '347px', '181px']) {
        editor.style.width = width;
        await settle();
        const mode = `${autoResize ? 'auto-resize' : 'fixed'} at ${width}`;
        checkEqual(layer.offsetHeight, textarea.offsetHeight, `Layer and textarea have equal heights: ${mode}`);
        checkEqual(layer.offsetWidth, textarea.offsetWidth, `Layer and textarea have equal widths: ${mode}`);
        checkEqual(textarea.clientHeight, textarea.scrollHeight, `The textarea text fits its box exactly: ${mode}`);
        checkEqual(0, textarea.scrollTop, `The textarea is not scrolled: ${mode}`);
        if (autoResize) check(editor.scrollHeight <= editor.clientHeight, `The editor grows to fit: ${mode}`);
        else check(editor.scrollHeight > editor.clientHeight, `The editor scrolls: ${mode}`);
      }
    }
    editor.style.removeProperty('width');
    editor.removeAttribute('auto-resize');

    // Incremental rendering keeps the elements of unchanged lines.
    editor.value = 'one\ntwo\nthree\nfour';
    const [first, second, third, fourth] = layer.children;
    editor.value = 'one\ntwo\nnew\n*lines*\nthree\nfour';
    check(layer.children[0] === first && layer.children[1] === second, 'Unchanged leading lines are kept');
    check(layer.children[4] === third && layer.children[5] === fourth, 'Unchanged trailing lines are kept');
    checkEqual('|one\n|two\n|new\n|{marker:*}{em:lines}{marker:*}\n|three\n|four', describeLayer(layer), 'Inserted lines render');
    editor.value = 'one\n```\ntwo\nnew';
    checkEqual('|one\ncode|{marker:```}\ncode|two\ncode|new', describeLayer(layer), 'An opened fence recolors the following lines');
    editor.value = '';
    checkEqual('|<br>', describeLayer(layer), 'Empty text renders one empty line');

    // User input.
    textarea.value = 'typed *text*';
    checkEqual('|<br>', describeLayer(layer), 'Assigning the textarea value directly does not refresh');
    textarea.dispatchEvent(new InputEvent('input', {bubbles: true}));
    checkEqual('|typed {marker:*}{em:text}{marker:*}', describeLayer(layer), 'An input event refreshes');
    textarea.value = 'direct';
    editor.refresh();
    checkEqual('|direct', describeLayer(layer), 'refresh() refreshes');

    // Changing attributes must leave the textarea, its text and its selection alone; see the settings demo in the dev app.
    editor.value = 'keep this selection';
    textarea.focus();
    textarea.setSelectionRange(5, 9);
    editor.setAttribute('auto-resize', '');
    await settle();
    check(editor.querySelector('textarea') === textarea && editor.querySelector('.md-highlight') === layer,
      'An attribute change keeps the textarea and the layer');
    checkEqual('5-9', `${textarea.selectionStart}-${textarea.selectionEnd}`, 'An attribute change keeps the selection');
    check(document.activeElement === textarea, 'An attribute change keeps focus');
    editor.removeAttribute('auto-resize');

    // DOM replacement, as performed by a morph that does not skip the element's children.
    layer.remove();
    await settle();
    check(layer.parentNode === editor, 'A removed layer is restored');
    checkEqual('|keep this selection', describeLayer(layer), 'A restored layer is intact');
    layer.replaceChildren();
    await settle();
    checkEqual('|keep this selection', describeLayer(layer), 'An emptied layer is rendered again');
    const replacement = document.createElement('textarea');
    replacement.name = 'markdown';
    replacement.textContent = '## Replaced';
    textarea.replaceWith(replacement);
    await settle();
    checkEqual('heading|{marker:##} Replaced', describeLayer(layer), 'A replaced textarea is adopted');
    replacement.textContent = '## Default changed';
    await settle();
    checkEqual('heading|{marker:##} Default changed', describeLayer(layer), 'A changed default value refreshes');

    // Form reset.
    editor.value = 'edited';
    form.reset();
    await new Promise(resolve => setTimeout(resolve, 20));
    checkEqual('heading|{marker:##} Default changed', describeLayer(layer), 'A form reset refreshes');

    // Reconnection.
    editor.remove();
    form.append(editor);
    editor.value = '*reconnected*';
    checkEqual('|{marker:*}{em:reconnected}{marker:*}', describeLayer(layer), 'A reconnected editor works');
    checkEqual(1, editor.querySelectorAll('.md-highlight').length, 'A reconnected editor has one layer');

    // Attachments: a pasted image becomes a reference in the text and a file in the form data.
    /** Dispatch a paste of `items` at the selection. Return whether the editor handled it.
     * @param {(File|string)[]} items */
    function paste(...items) {
      const data = new DataTransfer();
      for (const item of items) {
        if (typeof item === 'string') data.items.add(item, 'text/plain');
        else data.items.add(item);
      }
      return !replacement.dispatchEvent(new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true}));
    }
    const attachmentCount = () => editor.querySelectorAll('.md-attachments > .md-attachment > img').length;
    const imageBytes = Uint8Array.from({length: 512}, (_, i) => i % 256); // Every byte value.
    const png = new File([imageBytes], 'Screenshot.png', {type: 'image/png'});
    const jpeg = new File(['jpeg'], 'photo.jpeg', {type: 'image/jpeg'});
    editor.value = 'before  after';
    replacement.focus();
    replacement.setSelectionRange(7, 7);
    check(!paste(png), 'Without the attachments attribute an image paste is not handled');
    editor.setAttribute('attachments', 'images');
    check(!paste(png, 'text'), 'A paste that offers text is not handled');
    check(!paste(new File(['text'], 'notes.txt', {type: 'text/plain'})), 'A paste of a file that is not an image is not handled');
    checkEqual('before  after', editor.value, 'Unhandled pastes do not change the text');
    check(paste(png), 'An image paste is handled');
    checkEqual('before ![Image 1](attachment:image-1.png) after', editor.value, 'An image paste inserts a reference at the selection');
    checkEqual(replacement.value, layerText(), 'The layer shows the reference');
    checkEqual(41, replacement.selectionStart, 'The caret follows the reference');
    await settle();
    checkEqual(1, attachmentCount(), 'The strip shows the attachment');
    checkEqual(layer.offsetHeight, replacement.offsetHeight, 'The strip does not disturb the layout of the layer and textarea');
    const submitted = /** @type {File[]} */ (new FormData(form).getAll('images'));
    checkEqual(1, submitted.length, 'The form data carries the attachment');
    const file = mdNonNull(submitted[0]);
    checkEqual('image-1.png image/png', `${file.name} ${file.type}`, 'The file is named as in its reference');
    checkEqual(imageBytes.join(), new Uint8Array(await file.arrayBuffer()).join(), 'The file data is unaltered');
    check(paste(jpeg, png), 'A paste of several images is handled');
    const three = 'before ![Image 1](attachment:image-1.png)![Image 2](attachment:image-2.jpg) ![Image 3](attachment:image-3.png) after';
    checkEqual(three, editor.value, 'Each image gets a distinct reference');
    checkEqual('image-1.png,image-2.jpg,image-3.png', editor.attachments.map(f => f.name).join(), 'Attachments are in reference order');
    editor.value = three.replace('![Image 1](attachment:image-1.png)', '');
    checkEqual('image-2.jpg,image-3.png', new FormData(form).getAll('images').map(f => /** @type {File} */ (f).name).join(),
      'Deleting a reference detaches its image');
    checkEqual(2, attachmentCount(), 'The strip follows the references');
    editor.value = three + ' ![Image 1](attachment:image-1.png) ![Other](attachment:image-7.png)';
    checkEqual('image-1.png,image-2.jpg,image-3.png', editor.attachments.map(f => f.name).join(),
      'Restoring a reference attaches its image again; repeated and unknown references add nothing');
    replacement.setSelectionRange(0, 0);
    paste(png);
    check(editor.value.startsWith('![Image 8](attachment:image-8.png)'), 'New names do not collide with existing references');
    editor.value = 'no references';
    await settle();
    checkEqual(0, new FormData(form).getAll('images').length, 'Text without references submits no files');
    check(!editor.querySelector('.md-attachments'), 'The strip is removed when there are no attachments');
    checkEqual(1, editor.querySelectorAll('.md-highlight').length, 'The strip does not disturb the layer');

    const style = getComputedStyle(replacement);
    check(style.color === 'rgba(0, 0, 0, 0)', 'The textarea text is transparent');
    checkEqual(0, document.querySelectorAll('markdown-editor [style], style').length, 'No style attributes or elements are created');
    checkEqual('', cspViolations.join('; '), 'No Content Security Policy violations');
    output.textContent = `PASS: ${results.length} checks\n` + results.join('\n');
  } catch (error) {
    output.textContent = 'FAIL: ' + (error instanceof Error ? `${error.message}\n${error.stack}` : String(error));
    throw error;
  }
}


addEventListener('DOMContentLoaded', runMarkdownEditorTests);
