// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'use strict';

(() => {
  /** @template T @param {T|null|undefined} value @returns {T} */
  function required(value) {
    if (value == null) throw new Error('Missing browser test element or API.');
    return value;
  }

  const runControl = document.querySelector('#tests-run');
  if (!(runControl instanceof HTMLButtonElement)) throw new Error('Missing run button.');
  const runButton = runControl;
  const summary = required(document.querySelector('#tests-summary'));
  const list = required(document.querySelector('#tests-results'));

  function check(condition, message) {
    if (!condition) throw new Error(message);
  }

  async function run() {
    runButton.disabled = true;
    summary.textContent = 'Running...';
    summary.classList.remove('error-red');
    list.replaceChildren();
    /** @type {{name:string, status:string, message:string}[]} */
    const results = [];
    const frame = document.createElement('iframe');
    frame.className = 'tests-frame';
    frame.title = 'Isolated browser test fixtures';
    frame.tabIndex = -1;
    frame.setAttribute('aria-hidden', 'true');

    function report(name, status, message = '') {
      results.push({name, status, message});
      const item = document.createElement('li');
      item.textContent = `${status.toUpperCase()}: ${name}`;
      if (status === 'fail') {
        item.className = 'error-red';
        const detail = document.createElement('pre');
        detail.textContent = message;
        item.append(detail);
      }
      list.append(item);
    }

    try {
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('Fixture frame did not load within 10 seconds.')), 10000);
        frame.onload = () => { clearTimeout(timer); resolve(undefined); };
        frame.srcdoc = `<!doctype html><html><head><meta charset="utf-8"><title>Test fixtures</title>
          <link rel="stylesheet" href="/static/pithy/pithy.css"></head><body><main id="fixture"></main></body></html>`;
        document.body.append(frame);
      });
      const win = required(frame.contentWindow);
      const doc = required(frame.contentDocument);
      const fixture = required(doc.getElementById('fixture'));

      const canvas = doc.createElement('canvas');
      canvas.width = canvas.height = 1;
      const ctx = required(canvas.getContext('2d', {willReadFrequently: true}));
      function pixel(color, background = '') {
        ctx.clearRect(0, 0, 1, 1);
        if (background) {
          ctx.fillStyle = background;
          ctx.fillRect(0, 0, 1, 1);
        }
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, 1, 1);
        return /** @type {[number,number,number,number]} */ ([...ctx.getImageData(0, 0, 1, 1).data]);
      }
      function sameColor(a, b) {
        const expected = pixel(b);
        return pixel(a).every((value, idx) => Math.abs(value - required(expected[idx])) <= 1);
      }
      function style(selector) {
        const el = fixture.querySelector(selector);
        if (!el) throw new Error(`Missing fixture: ${selector}`);
        return win.getComputedStyle(el);
      }
      function colorToken(token) {
        const probe = doc.createElement('span');
        probe.style.color = `var(--${token})`;
        fixture.append(probe);
        const color = win.getComputedStyle(probe).color;
        probe.remove();
        return color;
      }
      async function test(name, body) {
        fixture.replaceChildren();
        fixture.removeAttribute('style');
        fixture.removeAttribute('data-theme');
        doc.documentElement.dataset.theme = 'light';
        try {
          await body();
          report(name, 'pass');
        } catch (error) {
          report(name, 'fail', error instanceof Error ? error.message : String(error));
        }
      }

      await test('Local text color controls code tints on a custom surface', () => {
        fixture.style.cssText = 'background:#808080;color:white';
        fixture.innerHTML = '<code>Inline code</code>';
        const code = fixture.querySelector('code');
        if (!code) throw new Error('Missing code fixture.');
        for (const property of ['backgroundColor', 'borderTopColor']) {
          const light = pixel(style('code')[property], '#808080')[0];
          check(light > 128 && light < 255, `${property} should lightly tint gray toward the local white text.`);
        }
        code.style.color = 'black';
        for (const property of ['backgroundColor', 'borderTopColor']) {
          const dark = pixel(style('code')[property], '#808080')[0];
          check(dark > 0 && dark < 128, `${property} did not follow the local change to black text.`);
        }
      });

      for (const outer of ['light', 'dark']) {
        for (const inner of ['light', 'dark']) {
          await test(`${inner} subtree inside ${outer} root: surfaces and native accents`, async () => {
            doc.documentElement.dataset.theme = outer;
            fixture.dataset.theme = inner;
            fixture.style.color = 'red'; // Opaque components must establish their own matching foreground.
            // Let the theme settle before constructing native controls; WebKit can otherwise reuse the preceding scheme.
            await new Promise(resolve => requestAnimationFrame(resolve));
            fixture.innerHTML = `<div class="panel">Panel</div><input value="Field"><select><option>Option</option></select>
              <textarea>Text</textarea><input type="checkbox"><dialog class="modal">Modal</dialog>`;
            const fg = colorToken('fg');
            const bg = pixel(colorToken('bg'))[0];
            check(inner === 'light' ? bg > 200 : bg < 60, 'Canvas follows the outer theme instead of the subtree.');
            for (const selector of ['.panel', 'input', 'select', 'textarea', 'dialog']) {
              check(sameColor(style(selector).color, fg), `${selector} inherited unrelated foreground text.`);
              check(pixel(style(selector).backgroundColor)[3] === 255, `${selector} needs an opaque surface.`);
            }
            check(sameColor(style('[type=checkbox]').accentColor, colorToken('accent')),
              'Native checkbox accent follows the outer theme instead of the subtree.');
          });
        }
      }

      await test('Code inside a pre has only the block decoration', () => {
        fixture.innerHTML = '<pre><code>Block code</code></pre>';
        check(style('pre').borderTopStyle !== 'none', 'The code block lost its border.');
        check(style('code').borderTopStyle === 'none', 'Nested code adds a second border.');
        check(pixel(style('code').backgroundColor)[3] === 0, 'Nested code adds a second background.');
      });

      await test('Table stripes compose with a custom surface', () => {
        fixture.style.cssText = 'background:#345064;color:white';
        fixture.innerHTML = '<table><tbody><tr><td>Odd</td></tr><tr><td>Even</td></tr></tbody></table>';
        const odd = pixel(style('tr').backgroundColor, '#345064');
        check(odd[0] > 52 && odd[0] < 255, 'Stripe should tint the colored surface toward white.');
        check(pixel(style('tr:nth-child(2)').backgroundColor)[3] === 0, 'Unshaded row replaces the surrounding surface.');
      });

      await test('Popover stays visible when opened on a scrolled page', async () => {
        fixture.innerHTML = `<div style="height:300vh"></div><button popovertarget="test-popover">Open</button>
          <div class="panel" id="test-popover" popover>Popover</div>`;
        const button = fixture.querySelector('button');
        const popover = doc.getElementById('test-popover');
        if (!button || !popover) throw new Error('Missing popover fixture.');
        button.scrollIntoView({block: 'center', behavior: 'instant'});
        const before = win.scrollY;
        check(before > win.innerHeight, 'Fixture did not scroll far enough to exercise the regression.');
        try {
          button.click();
          await new Promise(resolve => requestAnimationFrame(resolve));
          const rect = popover.getBoundingClientRect();
          check(popover.matches(':popover-open'), 'The button did not open its popover.');
          check(rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.bottom <= win.innerHeight,
            'Popover is outside the visible viewport.');
          check(Math.abs(win.scrollY - before) < 1, 'Opening the popover changed the scroll position.');
        } finally {
          if (popover.matches(':popover-open')) popover.hidePopover();
        }
      });
    } catch (error) {
      report('Test setup', 'fail', error instanceof Error ? error.message : String(error));
    } finally {
      frame.remove();
      runButton.disabled = false;
    }
    const failed = results.filter(result => result.status === 'fail').length;
    summary.textContent = `${results.length - failed} passed; ${failed} failed.`;
    summary.classList.toggle('error-red', failed > 0);
    return {status: failed ? 'fail' : 'pass', results};
  }

  function start() {
    // Each run replaces the promise; failures resolve with named results rather than rejecting.
    Object.assign(window, {pithyDevTests: run()});
  }
  runButton.addEventListener('click', start);
  start();
})();
