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
  if (val === null) throw new Error(`Unexpected null value`);
  if (val === undefined) throw new Error(`Unexpected undefined value`);
  // @ts-ignore
  return val;
}


/**
 * Require that a value is an instance of a given type.
 * Throws an exception if the value is not an instance of the expected type.
 *
 * @template T The expected type of the value.
 * @param {any} val - The value to check.
 * @param {{ new (): T; prototype: T; }} type - The expected type of the value.
 * @returns {T} - The value, asserting that it is an instance of the expected type.
 */
function req_instance(val, type) {
  if (val instanceof type) return val;
  throw new Error(`Type mismatch: expected ${type}; received type: ${typeof val}; val: \`${val}\`.`);
}

/**
 * Set up the browser environment.
*/
function _setupPithy() {
  _setupWindow();
  _setupHtmx();
}


addEventListener('DOMContentLoaded', _setupPithy);


function _setupWindow() {
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
}


let _htmx;

function _setupHtmx() {
  // @ts-ignore: ts(2304): cannot find name 'htmx'.
  _htmx = htmx;
  assert(_htmx !== undefined, 'htmx is undefined.');

  // Error handling configuration.
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

  // Configure universal 'once' callback for all DOM elements that define that attribute.
  _onload_run_once_attrs(document.body); // Call immediately.
  _htmx.onLoad(_onload_run_once_attrs);
}

/**
 * This function performs exactly-once initialization of nodes using the 'once' attribute.
 *
 * @param {HTMLElement} root_el
 * @returns {void}
 */
function _onload_run_once_attrs(root_el) {

  for (let el of _htmx.findAll(root_el, '[once]')) {
    let once_src = el.getAttribute('once');
    if (!once_src) { continue; }
    el.removeAttribute('once');
    let once_fn;
    try { once_fn = Function(once_src).bind(el); }
    catch (exc) {
      el.setAttribute('once-failed', once_src);
      log(`ERROR: _htmx.onLoad: 'once' compilation failed for element: ${el}\n  exc: ${exc}`);
      continue
    }
    try { once_fn(); }
    catch (exc) {
      el.setAttribute('once-failed', once_src);
      log(`ERROR: _htmx.onLoad: 'once' function failed for element: "${el}"\n  exc: ${exc}`);
      continue
    }
    el.setAttribute('once-done', once_src);
  }
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

  // There are two ways to change the value of a date input:
  // * By typing into the input.
  // * By clicking on a calendar date.
  // We want to submit the form when the user is done with either of these.
  // The 'change' event takes care of the click case, but fires prematurely for the typing case.

  let valueOnFocus = input.value;
  let isUserTyping = false;

  function submitIfChanged() {
    if (valueOnFocus !== input.value) {
      //log('value changed; submitting.')
      input.form.submit();
    }
  }

  input.addEventListener('focus', (event) => {
    //log('focus.', event);
    valueOnFocus = input.value;
  });
  input.addEventListener('blur', (event) => {
    //log('blur.', event);
    submitIfChanged();
  });
  input.addEventListener('change', (event) => {
    //log('change.', event);
    if (!isUserTyping) {
      submitIfChanged();
    }
  });
  input.addEventListener('click', (event) => {
    //log('click.', event);
    isUserTyping = false;
  });
  input.addEventListener('keydown', (event) => {
    //log('keydown.', event);
    isUserTyping = true;
    if (event.key == 'Enter') {
      input.blur();
    }
  });
}



/**
 * @param {HTMLElement} element
 */
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
  _htmx.on(element, 'htmx:beforeSend', (event) => {
    const hx_target = document.querySelector(hx_target_sel);
    if (!hx_target) {
      log('ERROR: setupBeforeSendClearHxTargetContent: hx-target not found:', hx_target_sel);
      return;
    }
    hx_target.innerHTML = '';
  });
}


/**
 * Validates that the container contains at least one checked checkbox.
 * @param {HTMLElement} container - A container of checkboxes.
 */
function validateAtLeastOneCheckbox(container) {
  /* Require at least one checkbox be selected. */
  let any_checked = false
  /** @type {NodeListOf<HTMLInputElement>} box */
  const checkboxes = container.querySelectorAll('input[type=checkbox]')
  if (checkboxes.length === 0) { throw new Error(`validateAtLeastOneCheckbox: no checkboxes found in container: ${container}`) }
  for (const box of checkboxes) {
    any_checked = any_checked || box.checked
  }
  /** @type {HTMLInputElement} */
  const first = nonopt(checkboxes[0])
  const desc = container.getAttribute('desc') || 'option'
  first.setCustomValidity(any_checked ? '' : `Select at least one ${desc}`)
}


/**
 * Configures an element with the `validateAtLeastOneCheckbox` handler.
 * Usage: configure an element with this handler: `once='setupValidateAtLeastOneCheckbox(this)'`.
 * @param {HTMLElement} container - A container of checkboxes.
 */
function setupValidateAtLeastOneCheckbox(container) {
  validateAtLeastOneCheckbox(container); // Call immediately to set initial validity.
  container.addEventListener("change", (event) => {
    // @ts-ignore: ts(2345): Argument of type null is not assignable to parameter of type 'HTMLElement'.
    validateAtLeastOneCheckbox(event.currentTarget)
  });
}


function nextDate(date) {
  const next = new Date(date);
  next.setDate(next.getDate() + 1);
  return next;
}

function prevDate(date) {
  const prev = new Date(date);
  prev.setDate(prev.getDate() - 1);
  return prev;
}


/**
 * Decrements the date value of the input element's form by one day and submits the form.
 * @param {HTMLInputElement} input - The input element triggering the function.
 */
function decrementDateAndSubmit(input, days = 1) {
  const form = req_instance(input.closest('form'), HTMLFormElement);
  const date_input = req_instance(form.querySelector('input[type=date]'), HTMLInputElement);
  const date = nonopt(date_input.valueAsDate);
  date.setUTCDate(date.getUTCDate() - days); // Note: must use UTCDate or else will get hung up on daylight savings transitions.
  date_input.valueAsDate = date;
  form.submit();
}


/**
 * Increments the date value of the input element's form by one day and submits the form.
 * @param {HTMLInputElement} input - The input element triggering the function.
 */
function incrementDateAndSubmit(input, days = 1) {
  const form = req_instance(input.closest('form'), HTMLFormElement);
  const date_input = req_instance(form.querySelector('input[type=date]'), HTMLInputElement);
  const date = nonopt(date_input.valueAsDate);
  date.setUTCDate(date.getUTCDate() + days); // Note: must use UTCDate or else will get hung up on daylight savings transitions.
  date_input.valueAsDate = date;
  form.submit();
}
