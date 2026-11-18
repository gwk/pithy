// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'use strict';

const markdownSource = document.getElementById('markdown-source');
if (markdownSource) highlightSubmission(markdownSource);


/** @param {HTMLElement} source */
function highlightSubmission(source) {
  // Highlight the complete text so an image inside a line or fence does not interrupt syntax coloring.
  const images = [];
  let offset = 0;
  for (const child of source.childNodes) {
    if (child instanceof Text) offset += child.length;
    else if (child instanceof HTMLImageElement) images.push({image: child, offset});
  }
  highlightMarkdown(source, source.textContent ?? '');

  // Put the original images back at the same text offsets in the highlighted DOM.
  const walker = document.createTreeWalker(source, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  let start = 0;
  for (const {image, offset} of images) {
    while (node instanceof Text && start + node.length < offset) {
      start += node.length;
      node = walker.nextNode();
    }
    if (node instanceof Text) node.splitText(offset - start).before(image);
  }
}
