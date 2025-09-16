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

  if (window.location.hostname == 'localhost') {
    // htmx.logAll() is too noisy for general use.
    _htmx.logger = _htmxLogger;
  }

  // Error handling configuration.
  document.body.addEventListener('htmx:beforeSwap', function (event) {
    // @ts-ignore: ts(2339): 'detail' does not exist on type 'Event'.
    const detail = event.detail;
    const code = detail.xhr.status;
    if (code === 404) {
      alert(`Error 404: resource not found: ${detail.pathInfo.finalRequestPath}\n\n${detail.xhr.responseText}`);
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

  // Show modal dialogs after they are swapped in.
  document.body.addEventListener('htmx:afterSwap', (event) => {
    // @ts-ignore: ts(2339): 'detail' does not exist on type 'Event'.
    const detail = event.detail;
    const target = detail.target;
    for (const modal of target.querySelectorAll('dialog.modal')) {
      if (modal instanceof HTMLDialogElement) {
        modal.showModal();
      }
    }
  });

  // Configure universal 'once' callback for all DOM elements that define that attribute.
  _onLoadRunOnceAttrs(document.body); // Call immediately.
  _htmx.onLoad(_onLoadRunOnceAttrs);
}


let htmxEventsToLog = new Set([
  'htmx:trigger',
  'htmx:beforeSwap',
])


/**
 * A custom logger for htmx events.
 * @param {Element} elt - The element that triggered the event.
 * @param {string} event - The event type.
 * @param {any} data - The event data.
 */
function _htmxLogger(elt, event, data) {
  if (htmxEventsToLog.has(event)) {
    console.log(event, elt, data)
  }
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
 * Find the element with the given id in the document; throws an error if the element is not found.
 * @param {string} id - The id of the element to retrieve.
 * @returns {HTMLElement} - The element with the given id.
 */
function findId(id) {
  const el = document.getElementById(id);
  if (!el) { throw new Error(`Element not found for id: ${id}`); }
  return el;
}


/**
 * Find the element with the given id in the document or return null if not found.
 * @param {string} id - The id of the element to retrieve.
 * @returns {HTMLElement|null} - The element with the given id or null if not found.
 */
function findIdOpt(id) {
  return document.getElementById(id);
}


/**
 * Find the element with the given selector; throws an error if the element is not found.
 * @param {string} selector - The selector of the element to retrieve.
 * @param {Document|Element} root - The element to query.
 * @returns {Element} - The first element with the given selector.
*/
function findSel(selector, root = document) {
  const el = root.querySelector(selector);
  if (!el) { throw new Error(`Element not found for selector: ${selector}; root: ${root}`); }
  return el;
}


/**
 * Find the element with the given selector or return null if not found.
 * @param {string} selector - The selector of the element to retrieve.
 * @param {Document|Element} root - The element to query.
 * @returns {Element|null} - The first element with the given selector or null if not found.
*/
function findSelOpt(selector, root = document) {
  return root.querySelector(selector);
}


/**
 * Find all elements with the given selector.
 * @param {string} selector - The selector of the elements to retrieve.
 * @param {Document|Element} root - The element to query.
 * @returns {NodeListOf<Element>} - The elements with the given selector.
*/
function findSelAll(selector, root = document) {
  return root.querySelectorAll(selector);
}


/**
 * Reset the value of an element to its default value or remove the value if no default is set.
 * @param {Element} el - The element to reset the value of.
 * @returns {void}
 */
function resetValueOfEl(el) {
  const default_ = el.getAttribute('default');
  if (default_ === null) {
    el.removeAttribute('value');
  } else {
    el.setAttribute('value', default_);
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




/**
 * Increment the date by one day.
 * @param {Date} date - The date to increment.
 * @returns {Date} - The incremented date.
*/
function nextDate(date) {
  const next = new Date(date);
  next.setDate(next.getDate() + 1);
  return next;
}


/**
 * Decrement the date by one day.
 * @param {Date} date - The date to decrement.
 * @returns {Date} - The decremented date.
 */
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
 * Close the dialog.modal element closest to the event target, including the target itself.
 * @param {Event} event - The event object.
 * This function can be registered as a click event listener for a child of the modal, e.g. a close button.
  */
function closeClosestModal(event) {
  const target = event.target
  if (!(target instanceof Element)) { throw new Error('closeClosestModal: non-element target.') }
  const modal = target.closest('dialog.modal');
  if (!(modal instanceof HTMLDialogElement)) { throw new Error('No modal found to dismiss.'); }
  event.stopPropagation();
  modal.close();
  removeFromParent(modal);
}


/**
 * Close and remove the dialog.modal element targeted by this event. Used as a 'click' handler on modal dialogs.
 * @param {Event} event - The event object.
  */
function closeTargetModal(event) {
  event.stopPropagation(); // Always stop propagation; clicking on a modal should not affect the non-modal content behind.
  const target = event.target
  if (target != event.currentTarget) return // Ignore clicks on the pane; we only want to respond to ::backdrop clicks.
  if (!(target instanceof HTMLDialogElement)) { throw new Error('closeTargetModal: non-dialog target.') }
  target.close();
}


/**
 * IF the escape key is pressed, call closeAndRemoveClosestModal;
 * @param {Event} event - The event object.
 * This function is intended to be registered as a keyup event listener.'
 */
function onCloseRemoveTargetModal(event) {
  const target = event.target
  if (!(target instanceof HTMLDialogElement)) { throw new Error('onCloseRemoveTargetModal: non-dialog target.') }
  removeFromParent(target);
}


/**
 * Create a modal dialog.
 * @param {...(string|Node)} contents - The content elements to add to the modal.
 * @returns {HTMLDialogElement} The created modal element.
 * The modal is immediately added to the document body and shown.
 * The modal is closed and removed from its parent when the user clicks on the backdrop.
 */
function createModal(...contents) {
  const modal = document.createElement('dialog');
  modal.className = 'modal';
  // As of 2025-08, closedBy is not supported by Safari. Therefore we need to implement our own close handler.
  modal.addEventListener('click', closeTargetModal);
  modal.addEventListener('close', onCloseRemoveTargetModal);
  /* In order to distinguish between the visible modal and the dialog::backdrop, we need to add the pane. */
  const pane = document.createElement('div');
  modal.appendChild(pane);
  pane.className = 'pane';
  pane.setAttribute('tabindex', '-1');
  for (const content of contents) {
    let el;
    if (typeof content === 'string') {
      el = document.createTextNode(content);
    } else if (content instanceof Node) {
      el = content;
    } else {
      throw new Error(`createModal: invalid content type: ${typeof content}`);
    }
    pane.appendChild(el);
  }
  return modal;
}


/**
 * Create a modal dialog, insert it into the document body, and show it.
 * @param {...(string|Node)} contents - The content elements to add to the modal.
 * @returns {HTMLDialogElement} The created modal element.
 */
function createAndShowModal(...contents) {
  const modal = createModal(...contents);
  document.body.appendChild(modal);
  modal.showModal();
  return modal;
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
