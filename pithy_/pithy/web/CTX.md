# pithy.web

`pithy.web` provides an HTTP 1.1 web server framework.
The web developer creates Endpoint subclasses, each of which defines a handler method per accepted HTTP method
(`get`, `post`, etc.), with fields declared as typed handler parameters or an inner fields class (`Get`, `Post`, etc.).
Handlers receive `self` and `request:Request`, followed by individual field arguments or `fields:Get` (and similarly for other methods).
The router dispatches to that endpoint, and fresh internal field storage is constructed for the request method.
Fields are filled and validated from path params, query params, and body params, then passed to the handler.
Inline fields follow the same conversion rules as fields classes; parameter defaults are not supported.
Custom `expect_100_continue` hooks require object-form handlers, using explicit fields classes or `fields:None`.

Goals:
* identify developer errors rather than ignore them;
* reject weird requests with missing or extra parameters;
* reduce boilerplate;
* generally make development easier while remaining simple.

## Browser Regression Tests

Standalone browser regression pages live in `pithy_/test/web/`, relative to the repository root.
When changing `pithy.js` or htmx integration, run the relevant pages in both Chromium and WebKit.
These tests are not run by `just check` or `just typecheck-js`.

Serve the repository root over HTTP and open each test page at its corresponding URL, such as `/pithy_/test/web/checkbox-inclusion.html`.
The pages load the repository's JavaScript through relative paths, run automatically, and display `PASS` with a check count or `FAIL` with error details.

* `checkbox-inclusion.html`: Checks boolean and set checkbox submission through `hx-include` and prefixed attributes, including inheritance, append behavior, disabled controls, and explicit value overrides. All test requests are canceled before transmission.
* `collapsible-tables.html`: Checks collapse toggling, hidden rows, and listener preservation across htmx morphs.
