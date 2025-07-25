// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

"use strict";

const assert = console.assert;
const log = console.log;

let scrollbarWidth = 0;


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
  try {
    // @ts-ignore: ts(2552): cannot find name 'htmx'.
    _htmx = htmx;
  } catch (exc) {
    log('htmx is undefined.');
    return;
  }

  // Error handling configuration.
  document.body.addEventListener('htmx:beforeSwap', function (event) {
    // @ts-ignore: ts(2339): 'detail' does not exist on type 'Event'.
    const detail = event.detail;
    const code = detail.xhr.status;
    if (code === 404) {
      alert(`Error 404: resource not found: ${detail.pathInfo.finalRequestPath}`);
    } else if (code === 422) {
      // As suggested by HTMX documentation, use 422 responses to signal that a form was submitted with bad data.
      // The response should contain the result to be rendered.
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
  _onLoadRunOnceAttrs(document.body); // Call immediately.
  _htmx.onLoad(_onLoadRunOnceAttrs);
}


/**
 * This function performs exactly-once initialization of nodes using the 'once' attribute.
 *
 * @param {Element} rootEl
 * @returns {void}
 */
function _onLoadRunOnceAttrs(rootEl) {
  _runOnceAttr(rootEl);
  for (let el of rootEl.querySelectorAll('[once]')) {
    _runOnceAttr(el);
  }
}


/**
 * Helper function for _onLoadRunOnceAttrs. Performs exactly-once initialization of a node using the 'once' attribute.
 *
 * @param {Element} el
 * @returns {void}
 */
function _runOnceAttr(el) {
  if (el.hasAttribute('once-ran')) { return; }
  let once_src = el.getAttribute('once');
  if (!once_src) { return; }
  let once_fn;
  try { once_fn = Function(once_src).bind(el); }
  catch (exc) {
    let err = `error: 'once' compilation failed for element: ${el}\n  exc: ${exc}`;
    log(err);
    el.setAttribute('once-ran', err);
    return;
  }
  try { once_fn(); }
  catch (exc) {
    let err = `error: 'once' function failed for element: ${el}\n  exc: ${exc}`;
    log(err);
    el.setAttribute('once-ran', err);
    return;
  }
  el.setAttribute('once-ran', '');
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
function reqInstance(val, type) {
  if (val instanceof type) return val;
  throw new Error(`Type mismatch: expected ${type}; received type: ${typeof val}; val: \`${val}\`.`);
}


/**
 * Remove an element from its parent.
 * @param {Element} el - The element to remove.
 */
function removeFromParent(el) {
  const parent = el.parentNode;
  if (parent) { parent.removeChild(el); }
}


/**
 * Get the element with the given id; throws an error if the element is not found.
 * @param {string} id - The id of the element to retrieve.
 * @returns {HTMLElement} - The first element with the given id.
 */
function getById(id) {
  const el = document.getElementById(id);
  if (!el) { throw new Error(`Element not found for id: ${id}`); }
  return el;
}


/**
 * Get the element with the given selector.
 * @param {string} selector - The selector of the element to retrieve.
 */
function getForSel(selector) {
  const el = document.querySelector(selector);
  if (!el) { throw new Error(`Element not found: ${selector}`); }
  return el;
}


function emptyFirstForSel(selector) {
  const element = document.querySelector(selector);
  if (element) { element.innerHTML = ''; }
}


function emptyAllForSel(selector) {
  for (const element of document.querySelectorAll(selector)) {
    element.innerHTML = '';
  }
}


function removeAttrForSel(selector, attr) {
  const element = document.querySelector(selector);
  if (element) { element.removeAttribute(attr); }
}


function removeAttrForSelAll(selector, attr) {
  for (const element of document.querySelectorAll(selector)) {
    element.removeAttribute(attr);
  }
}


function clearValueForSel(selector) {
  const element = document.querySelector(selector);
  if (element) {
    element.removeAttribute('value');
  }
}


function clearValueForSelAll(selector) {
  for (const element of document.querySelectorAll(selector)) {
    element.removeAttribute('value');
  }
}


function resetValueForSel(selector) {
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


function resetValueForSelAll(selector) {
  for (const element of document.querySelectorAll(selector)) {
    const default_ = element.getAttribute('default');
    if (default_ === null) {
      element.removeAttribute('value');
    } else {
      element.setAttribute('value', default_);
    }
  }
}


function collapseAllDetails(selector) {
  for (const element of document.querySelectorAll(selector + ' details[open]')) {
    element.removeAttribute('open');
  }
}


function expandAllDetails(selector) {
  for (const element of document.querySelectorAll(selector + ' details:not([open])')) {
    element.setAttribute('open', '');
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
  const desc_singular = container.getAttribute('desc-singular') || 'option'
  first.setCustomValidity(any_checked ? '' : `Select at least one ${desc_singular}`)
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


/**
 * Register a callback that skips confirmation if the element is not checked.
 * This function should be called using the `once` attribute.
 */
function setupHtmxConfirmIfChecked(element) {
  _htmx.on(element, 'htmx:confirm', (event) => {
    event.preventDefault();
    if (element.checked) { /* Show a confirmation. */
      if (!window.confirm(event.detail.question)) { /* Cancel and reset the checkbox. */
        element.checked = false;
        return;
      }
    }
    event.detail.issueRequest(true); /* Skip normal confirmation dialog. */
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
  const form = reqInstance(input.closest('form'), HTMLFormElement);
  const date_input = reqInstance(form.querySelector('input[type=date]'), HTMLInputElement);
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
  const form = reqInstance(input.closest('form'), HTMLFormElement);
  const date_input = reqInstance(form.querySelector('input[type=date]'), HTMLInputElement);
  const date = nonopt(date_input.valueAsDate);
  date.setUTCDate(date.getUTCDate() + days); // Note: must use UTCDate or else will get hung up on daylight savings transitions.
  date_input.valueAsDate = date;
  form.submit();
}


/**
 * Set the date value of the input element's form to today and submit the form.
 * @param {HTMLInputElement} input - The input element triggering the function.
 * @param {string} date: The date to set the input to.
 */
function setDateAndSubmit(input, date) {
  const form = reqInstance(input.closest('form'), HTMLFormElement);
  const date_input = reqInstance(form.querySelector('input[type=date]'), HTMLInputElement);
  date_input.value = date;
  form.submit();
}


/**
 * Dismiss the topmost modal element.
 * @param {HTMLElement} element - The element triggering the function.
 * @param {Event} event - The event object.
  */
function dismissModal(element, event) {
  if (element !== event.target) { return; } // Ignore events that bubble up from children.
  event.stopPropagation();
  const modal = element.closest('.modal');
  if (!modal) { throw new Error('No modal found to dismiss.'); }
  removeFromParent(modal);
}


/**
 * Link the scroll of the vis-scroll and ticks-x-scroll elements.
 * @param {HTMLElement} visGrid - The grid containing the vis-scroll and ticks-x-scroll elements.
 */
function chartsLinkScrollX(visGrid) {
  let activeDiv = null;
  const visScroll = visGrid.querySelector('.vis-scroll');
  const ticksXScroll = visGrid.querySelector('.ticks-x-scroll');

  /**
   * Link the scroll of two elements.
   * @param {Element|null} div - The element to link the scroll of.
   * @param {Element|null} other - The element to link the scroll to.
   */
  function linkScrolling(div, other) {
    if (div === null) { log("error: chartsLinkScrollX: div is null"); return; }
    if (other === null) { log("error: chartsLinkScrollX: other is null"); return; }
    div.addEventListener('mouseenter', (e) => {
      activeDiv = e.target;
    });
    div.addEventListener("scroll", (e) => {
      if (e.target !== activeDiv) return;
      if (e.target === null) return;
      const target = /** @type {HTMLElement} */ (e.target);
      other.scrollLeft = target.scrollLeft;
    });
  }

  linkScrolling(visScroll, ticksXScroll);
  linkScrolling(ticksXScroll, visScroll);
}
