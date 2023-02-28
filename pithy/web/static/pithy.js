// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

const log = console.log;

let scrollbarWidth = 0;


addEventListener('DOMContentLoaded', ()=>{
  // Set safari class on body if browser is Safari.
  if (window.safari !== undefined) {
    document.body.classList.add('safari');
  }

  // Calculate the width of the scrollbar.
  const body = document.querySelector('body');
  scrollbarWidth = window.innerWidth - body.clientWidth + 0.1; // Adding a fraction more prevents the horizontal scrollbar.
  createPithyDynamicStyle();
});


function createStyle(title, selectorText) {
  style = document.createElement('style');
  style.type = 'text/css';
  style.title = 'pithy-dynamic';
  style.innerHTML = selectorText;
  log(document.head);
  document.head.appendChild(style);
}


function createPithyDynamicStyle() {
  css = `
  :root {
    --scrollbar-width: ${scrollbarWidth}px;
  }
  `;
  createStyle('pithy-dynamic', css);
}


function setupReloadingDateInput(input) {
  // Configure a date input with this handler: `onfocus='setupReloadingDateInput(this)'`.
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
  // Configure an element with this handler: `onfocus='setupBeforeSendClearHxTargetContent(this)'`.
  element.onfocus = null; // This handler is a lazy initializer; remove it.
  const hx_target_sel = element.getAttribute('hx-target');
  if (!hx_target_sel) {
    log('ERROR: setupBeforeSendClearHxTargetContent: element has no hx-target attribute:', element);
    return;
  }
  htmx.on(element, 'htmx:beforeSend', (event)=>{
    const hx_target = document.querySelector(hx_target_sel);
    if (!hx_target) {
      log('ERROR: setupBeforeSendClearHxTargetContent: hx-target not found:', hx_target_sel);
      return;
    }
    hx_target.innerHTML = '';
  });
}
