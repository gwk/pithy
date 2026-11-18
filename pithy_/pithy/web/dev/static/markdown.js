// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'use strict';

const demoMarkdownEditor = document.getElementById('markdown-editor');
if (demoMarkdownEditor instanceof MarkdownEditor) {
  document.getElementById('markdown-reformat')?.addEventListener('click', () => demoMarkdownEditor.reformat());
}

const markdownSource = document.getElementById('markdown-source');
const resultReformat = document.getElementById('markdown-result-reformat');
if (markdownSource && resultReformat instanceof HTMLInputElement) setupSubmission(markdownSource, resultReformat);


/** @param {HTMLElement} source @param {HTMLInputElement} reformat */
function setupSubmission(source, reformat) {
  // Each view starts from the original source, with image positions indexed into that text.
  const text = source.textContent ?? '';
  const images = [];
  let offset = 0;
  for (const child of source.childNodes) {
    if (child instanceof Text) offset += child.length;
    else if (child instanceof HTMLImageElement) images.push({image: child, offset});
  }
  function render() {
    const formatted = reformat.checked ? reformatMarkdown(text, source) : null;
    highlightMarkdown(source, formatted?.text ?? text);

    const walker = document.createTreeWalker(source, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    let start = 0;
    for (const {image, offset: originalOffset} of images) {
      const offset = formatted?.mapOffset(originalOffset) ?? originalOffset;
      while (node instanceof Text && start + node.length < offset) {
        start += node.length;
        node = walker.nextNode();
      }
      if (node instanceof Text) node.splitText(offset - start).before(image);
    }
  }
  reformat.addEventListener('change', render);
  render();
}
