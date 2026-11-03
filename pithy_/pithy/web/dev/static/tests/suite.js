// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

// Shared harness for the fixture pages that the dev app's /tests page runs in frames.

'use strict';

/**
 * @typedef {{checks:string[], error:string}} SuiteOutcome
 * `checks` names each passed check in order; `error` is empty when the suite passed.
 */


/**
 * Run `body` once the document has loaded and report its outcome.
 *
 * `body` receives `check`, which throws `message` when `condition` is false and otherwise records it as passed.
 * The first failure ends the suite.
 * The outcome is shown in `#results` when the page is opened directly,
 * and the `pithyTestSuite` window property is a promise of the outcome for the tests page.
 * Load this script after `pithy.js` so that pithy's own DOMContentLoaded setup runs before `body`.
 * @param {(check:(condition:unknown, message:string) => void) => Promise<void>|void} body
 */
function runTestSuite(body) {
  /** @type {Promise<SuiteOutcome>} */
  const outcome = new Promise(resolve => addEventListener('DOMContentLoaded', async () => {
    /** @type {string[]} */
    const checks = [];
    /** @param {unknown} condition @param {string} message */
    function check(condition, message) {
      if (!condition) throw new Error(message);
      checks.push(message);
    }
    let error = '';
    try {
      await body(check);
    } catch (e) {
      console.error(e);
      // Chromium includes the message in the stack; WebKit does not.
      error = !(e instanceof Error) ? String(e) : e.stack?.includes(e.message) ? e.stack : `${e.message}\n${e.stack}`;
    }
    const results = document.querySelector('#results');
    if (results) results.textContent = error ? `FAIL: ${error}` : `PASS: ${checks.length} checks\n` + checks.join('\n');
    resolve({checks, error});
  }));
  Object.assign(window, {pithyTestSuite: outcome});
}
