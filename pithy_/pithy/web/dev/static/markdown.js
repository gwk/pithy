// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'use strict';

function updateMarkdownPreview() {
  const editor = /** @type {HTMLElement & {getHTML: () => string}} */ (document.getElementById('markdown-editor'));
  const preview = document.getElementById('markdown-preview');
  if (!editor || !preview) return;
  preview.innerHTML = editor.getHTML();
  // getHTML() emits task markers for editing; render them as read-only checkboxes.
  for (const marker of preview.querySelectorAll('.task-list > .syntax-marker')) {
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.disabled = true;
    checkbox.checked = /\[x\]/i.test(marker.textContent || '');
    marker.replaceWith(checkbox, ' ');
  }
}

document.addEventListener('DOMContentLoaded', updateMarkdownPreview);
// Delegate so settings changes can replace or rebuild the editor without losing the preview listener.
for (const eventName of ['ready', 'change']) {
  document.addEventListener(eventName, event => {
    if (event.target instanceof HTMLElement && event.target.id === 'markdown-editor') updateMarkdownPreview();
  });
}
