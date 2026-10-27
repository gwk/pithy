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
          <link rel="stylesheet" href="/static/pithy/pithy.css">
          <link rel="stylesheet" href="/static/pithy/markdown.css"></head><body><main id="fixture"></main></body></html>`;
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
        fixture.removeAttribute('class');
        doc.body.removeAttribute('class');
        doc.documentElement.dataset.theme = 'light';
        try {
          await body();
          report(name, 'pass');
        } catch (error) {
          report(name, 'fail', error instanceof Error ? error.message : String(error));
        }
      }

      await test('Plain pages leave layout, scrolling and semantic containers to the application', () => {
        fixture.innerHTML = '<p>First</p><section><h2>Section</h2><p>Text</p><p>More</p></section>' +
          '<article><p>First</p><p>Second</p></article>';
        const body = win.getComputedStyle(doc.body);
        const root = win.getComputedStyle(doc.documentElement);
        check(body.display === 'block' && body.minHeight === '0px', 'Body imposes layout or a minimum viewport height.');
        check(doc.body.getBoundingClientRect().height < win.innerHeight, 'Body is forced to viewport height.');
        check(root.overflowY === 'visible' && root.containerType === 'normal', 'Root imposes scrolling or containment.');
        const main = win.getComputedStyle(fixture);
        check(main.padding === '0px' && main.flexGrow === '0', 'Main retains document geometry.');
        for (const el of fixture.querySelectorAll('*')) {
          check(win.getComputedStyle(el).marginBlockStart === '0px', `${el.tagName} has implicit flow spacing.`);
        }
      });

      await test('Document layout supplies page geometry and flow in semantic containers', () => {
        doc.body.className = 'document';
        fixture.innerHTML = '<p>First</p><p>Second</p><section><p>First</p><p>Second</p>' +
          '<article><p>First</p><p>Second</p></article></section><div><p>First</p><p>Second</p></div>';
        const main = win.getComputedStyle(fixture);
        check(win.getComputedStyle(doc.body).display === 'flex', 'Document body should be a flex column.');
        check(win.getComputedStyle(doc.documentElement).overflowY === 'scroll', 'Document scrollbar policy is missing.');
        check(main.paddingBlockStart === '16px' && main.flexGrow === '1', 'Document main geometry is missing.');
        check(Math.abs(doc.body.getBoundingClientRect().height - win.innerHeight) < 1,
          'Short document body should fill the viewport.');
        check(style(':scope > p + p').marginBlockStart === '16px', 'Document main should be a flow container.');
        check(style('section').marginBlockStart === '24px', 'Document section should open a new block.');
        check(style('section > p + p').marginBlockStart === '16px', 'Document section should be a flow container.');
        check(style('article > p + p').marginBlockStart === '16px', 'Document article should be a flow container.');
        check(style('div > p + p').marginBlockStart === '0px', 'Document flow leaked into a plain div.');
        fixture.innerHTML = `<div style="height:${3 * win.innerHeight}px"></div>`;
        check(doc.body.getBoundingClientRect().height > 3 * win.innerHeight, 'Document body should grow with long content.');
        fixture.innerHTML = '<div class="bleed">Wide content</div>';
        check(Math.abs(required(fixture.firstElementChild).getBoundingClientRect().width -
          doc.documentElement.clientWidth) < 1, 'Document bleed does not match the root content width.');
      });

      for (const documentLayout of [false, true]) {
        await test(`Explicit flow with document layout ${documentLayout ? 'on' : 'off'}`, () => {
          doc.body.classList.toggle('document', documentLayout);
          fixture.className = 'flow';
          fixture.innerHTML = '<p>First</p><p>Second</p><h2>Heading</h2><p>Text</p><h3>Subheading</h3>' +
            '<h4>Consecutive heading</h4><div><p>Nested first</p><p>Nested second</p></div>';
          check(style('p').marginBlockStart === '0px', 'First child should have no flow margin.');
          check(style('p + p').marginBlockStart === '16px', 'Ordinary flow gap is missing.');
          check(style('h2').marginBlockStart === '24px', 'Large heading gap is missing.');
          check(style('h2 + p').marginBlockStart === '4px', 'Heading should hug its following content.');
          check(style('h3').marginBlockStart === '20px', 'Third-level heading gap is missing.');
          check(style('h4').marginBlockStart === '12px', 'Consecutive heading gap is missing.');
          check(style('div p + p').marginBlockStart === '0px', 'Flow leaked into a nested container.');
          required(fixture.querySelector('div')).className = 'flow flow-tight';
          check(style('div p + p').marginBlockStart === '8px', 'Nested flow must opt in independently.');
          fixture.className = 'flow flow-loose';
          check(style('p + p').marginBlockStart === '32px', 'Loose flow modifier is missing.');
        });
      }

      for (const documentLayout of [false, true]) {
        const label = `Component classes declared before Pithy override flow, document layout ${documentLayout ? 'on' : 'off'}`;
        await test(label, () => {
          const overrides = doc.createElement('style');
          overrides.textContent = '.custom-spacing { margin-block-start: 3px; }';
          doc.head.prepend(overrides);
          try {
            if (documentLayout) doc.body.className = 'document';
            else fixture.className = 'flow';
            fixture.innerHTML = '<p>First</p><p>Second</p><h1>H1</h1><h2>H2</h2><p>Text</p><h3>H3</h3>' +
              '<p>Text</p><h4>H4</h4><p>Text</p><h5>H5</h5><p>Text</p><h6>H6</h6><section>Section</section>' +
              '<article>Article</article>';
            for (const el of fixture.children) {
              el.className = 'custom-spacing';
              check(win.getComputedStyle(el).marginBlockStart === '3px', `${el.tagName} flow defeats a component class.`);
            }
          } finally {
            overrides.remove();
          }
        });
      }

      await test('Reusable components retain their styles in either page layout', () => {
        fixture.innerHTML = '<form class="grid"><label>Label</label><input value="Text"></form>' +
          '<nav class="breadcrumbs"><span>Home</span><span>Page</span></nav>' +
          '<dialog class="modal" open><div class="pane flow"><h2>Title</h2><p>Text</p></div></dialog>' +
          '<markdown-editor></markdown-editor><button>Button</button>';
        function components() {
          return ['form', 'input', 'nav', 'dialog', '.pane', '.pane p', 'markdown-editor', 'button'].map(selector => {
            const s = style(selector);
            return [s.display, s.padding, s.gap, s.border, s.color, s.backgroundColor];
          });
        }
        const plain = components();
        check(style('form').display === 'grid' && style('nav').display === 'flex', 'Form or breadcrumb layout is missing.');
        check(style('dialog').borderTopStyle === 'solid', 'Dialog decoration is missing.');
        check(style('markdown-editor').display === 'grid', 'Markdown editor layout is missing.');
        doc.body.className = 'document';
        check(JSON.stringify(components()) === JSON.stringify(plain), 'Document layout changes component styles.');
      });

      await test('Local text color controls code tints on a custom surface', () => {
        fixture.style.cssText = 'background:#808080;color:white';
        fixture.innerHTML = '<code>Inline code</code>';
        const code = fixture.querySelector('code');
        if (!code) throw new Error('Missing code fixture.');
        const light = pixel(style('code').backgroundColor, '#808080')[0];
        check(light > 128 && light < 255, 'Inline code background should lightly tint gray toward the local white text.');
        code.style.color = 'black';
        const dark = pixel(style('code').backgroundColor, '#808080')[0];
        check(dark > 0 && dark < 128, 'Inline code background did not follow the local change to black text.');
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

      await test('Disclosures use their own state and permit component marker overrides', () => {
        fixture.innerHTML = '<details open><summary>Parent</summary>' +
          '<details id="child"><summary>Child</summary></details></details>' +
          '<details class="test-disclosure" open><summary>Custom</summary></details>';
        const marker = selector => win.getComputedStyle(required(fixture.querySelector(selector)), '::before').content;
        check(marker('details > summary') === '"▾"', 'Open disclosure should show the open marker.');
        check(marker('#child > summary') === '"▸"', 'An open ancestor changed a closed child marker.');
        required(fixture.querySelector('#child')).setAttribute('open', '');
        check(marker('#child > summary') === '"▾"', 'Child disclosure should reflect its own open state.');
        const override = doc.createElement('style');
        override.textContent = '.test-disclosure > summary::before { content: none; }';
        doc.head.prepend(override);
        try {
          check(marker('.test-disclosure > summary') === 'none', 'Component class cannot override the open marker.');
        } finally {
          override.remove();
        }
      });

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
