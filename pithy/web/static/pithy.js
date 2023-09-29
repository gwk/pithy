// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

"use strict";

const assert = console.assert;
const log = console.log;

let scrollbarWidth = 0;

/**
 * @template T
 * @param {T} val - A possibly null/undefined value.
 * @returns {NonNullable<T>} - The value, asserting that it is not null or undefined.
 */
function nonopt(val) {
  assert(val !== null);
  assert(val !== undefined);
  // @ts-ignore
  return val;
}


addEventListener('DOMContentLoaded', () => {
  // Set `safari` class on the root element if browser is Safari; `chrome` for Chrome.
  // @ts-ignore: ts(2339): 'safari' does not exist.
  if (window.safari !== undefined) {
    document.documentElement.classList.add('safari');
  }
  // @ts-ignore: ts(2339): 'chrome' does not exist.
  if (!!window.chrome) {
    document.documentElement.classList.add('chrome');
  }

  // Calculate the width of the scrollbar.
  const body = nonopt(document.querySelector('body'));
  scrollbarWidth = window.innerWidth - body.clientWidth + 0.1; // Adding a fraction more prevents the horizontal scrollbar.
  createPithyDynamicStyle();

  _setupHtmx();
});


function _setupHtmx() {
  document.body.addEventListener('htmx:beforeSwap', function (event) {
    // @ts-ignore: ts(2339): 'detail' does not exist on type 'Event'.
    const detail = event.detail;
    const code = detail.xhr.status;
    if (code === 404) {
      alert(`Error 404: resource not found: ${detail.pathInfo.finalRequestPath}`);
    } else if (code === 422) {
      // As suggested by HTMX documentation, use 422 responses to signal that a form was submitted with bad data.
      // The esponse should contain the result to be rendered.
      detail.shouldSwap = true;
      detail.isError = false; // Do not log errors in the console.
    } else if (code >= 500) {
      alert(`Server error ${code}: ${detail.xhr.statusText}\n\n${detail.xhr.responseText}`);
      log(detail);
    } else if (code >= 400) {
      alert(`Client error ${code}: ${detail.xhr.statusText}\n\n${detail.xhr.responseText}`);
      log(detail);
    }
  });
}


function createStyle(title, selectorText) {
  const style = document.createElement('style');
  style.title = title;
  style.innerHTML = selectorText;
  document.head.appendChild(style);
}


function createPithyDynamicStyle() {
  const css = `:root {
    --scrollbar-width: ${scrollbarWidth}px;
  }`;
  createStyle('pithy-dynamic', css);
}


function emptyFirstForSelector(selector) {
  const element = document.querySelector(selector);
  if (element) { element.innerHTML = ''; }
}

function emptyAllForSelector(selector) {
  for (const element of document.querySelectorAll(selector)) {
    element.innerHTML = '';
  }
}


function removeAttrForSelector(selector, attr) {
  const element = document.querySelector(selector);
  if (element) { element.removeAttribute(attr); }
}


function removeAttrForSelectorAll(selector, attr) {
  for (const element of document.querySelectorAll(selector)) {
    element.removeAttribute(attr);
  }
}


function clearValueForSelector(selector) {
  const element = document.querySelector(selector);
  if (element) {
    element.removeAttribute('value');
  }
}


function clearValueForSelectorAll(selector) {
  for (const element of document.querySelectorAll(selector)) {
    element.removeAttribute('value');
  }
}


function resetValueForSelector(selector) {
  const element = document.querySelector(selector);
  if (element) {
    const default_ = element.getAttribute('default');
    if (default_ === null) {
      element.removeAttribute('value');
    } else {
      element.setAttribute('value', default_);
    }
  }
}


function resetValueForSelectorAll(selector) {
  for (const element of document.querySelectorAll(selector)) {
    const default_ = element.getAttribute('default');
    if (default_ === null) {
      element.removeAttribute('value');
    } else {
      log('resetValueForSelectorAll:', selector, 'default:', default_);
      element.setAttribute('value', default_);
    }
  }
}


function setupReloadingDateInput(input) {
  // Usage: configure a date input with this handler: `onfocus='setupReloadingDateInput(this)'`.
  input.onfocus = null; // This handler is a lazy initializer; remove it.
  let dateValueOnFocus = input.value;
  input.addEventListener('focus', (event) => {
    //log('focus', event);
    dateValueOnFocus = input.value;
  });
  input.addEventListener('blur', (event) => {
    //log('blur', event);
    if (dateValueOnFocus !== input.value) {
      input.form.submit();
    }
  });
  input.addEventListener('keydown', (event) => {
    //log('keydown', event);
    if (event.key == 'Enter') {
      input.blur();
    }
  });
}


function setupBeforeSendClearHxTargetContent(element) {
  // Configures an element with an event handler so that before an htmx request is sent,
  // the content of the target element is cleared.
  // Usage: configure an element with this handler: `onfocus='setupBeforeSendClearHxTargetContent(this)'`.
  element.onfocus = null; // This handler is a lazy initializer; remove it.
  const hx_target_sel = element.getAttribute('hx-target');
  if (!hx_target_sel) {
    log('ERROR: setupBeforeSendClearHxTargetContent: element has no hx-target attribute:', element);
    return;
  }
  // @ts-ignore: ts(2304): cannot find name 'htmx'.
  htmx.on(element, 'htmx:beforeSend', (event) => {
    const hx_target = document.querySelector(hx_target_sel);
    if (!hx_target) {
      log('ERROR: setupBeforeSendClearHxTargetContent: hx-target not found:', hx_target_sel);
      return;
    }
    hx_target.innerHTML = '';
  });
}


function validateAtLeastOneCheckbox(span) {
  /* Require at least one checkbox be selected. */
  let any_checked = false
  const inputs = span.getElementsByTagName('input')
  for (const input of inputs) {
    any_checked = any_checked || input.checked
  }
  const first_input = span.querySelector('input')
  const desc = span.desc || 'option'
  first_input.setCustomValidity(any_checked ? '' : `Select at least one ${desc}`)
}
