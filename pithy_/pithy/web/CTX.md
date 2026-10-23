# pithy.web

`pithy.web` provides an HTTP 1.1 web server framework.
The web developer creates Endpoint subclasses, each of which defines a handler method per accepted HTTP method
(`get`, `post`, etc.), optionally paired with an inner fields class of the same name (`Get`, `Post`, etc.).
The router dispatches to that endpoint, and a fresh fields instance for the request method is constructed.
The fields object is filled and validated from path params, query params, and body params, then passed to the handler.

For example, `uid` comes from the route, GET takes a `tab` query parameter, and POST takes `name` and `email` body fields:

```python
class UserEndpoint(Endpoint):
  max_body_bytes = 4096

  class Get:
    uid:int
    tab:str

  @allow_public
  def get(self, request:Request, fields:Get) -> Response:
    return Response(body=f'{fields.uid}: {fields.tab}')

  class Post:
    uid:int
    name:str
    email:str

  @requires_privileges('users:write')
  def post(self, request:Request, fields:Post) -> Response:
    return Response(body=f'{fields.uid}: {fields.name} <{fields.email}>')

router = Router({'/users/{uid:int}': UserEndpoint})
```

Import the `allow_public` and `requires_privileges` decorators from `pithy.web.auth`. POST requires the `users:write` privilege.
The handler must separately check whether the caller may modify the particular `uid`.

For simple GET routes, decorate and register a function directly:

```python
@allow_public
def user(request:Request, uid:int, tab:str) -> Response:
  return Response(body=f'{uid}: {tab}')

router = Router({'/users/{uid:int}': user})
```

The router adapts the function with `pithy.web.endpoint.get_endpoint`, which generates an `Endpoint` subclass accepting GET and HEAD.
Parameters after `request` are path and query fields following the `Endpoint.Get` rules; defaults are rejected, so optional fields use `T|None`.

Goals:
* identify developer errors rather than ignore them;
* reject weird requests with missing or extra parameters;
* reduce boilerplate;
* generally make development easier while remaining simple.

## Request Lifecycle and Access Control

After constructing a Request, the server drives a fixed lifecycle; the `WebApp` docstring in `app.py` lists the steps and exceptions.
An application overrides only the hooks it needs:
* `check_request` checks deployment-wide constraints before authentication. `pithy.web.auth.SameOriginCheck`, constructed once from the deployment's public origin, refuses cross-site requests except top-level GET navigations, so inbound links and sign-in redirects work; exempt any path that must accept cross-site posts before calling it.
* `authenticate` returns a `frozenset[str]` of effective privileges, stored on `request.privileges`. Empty means anonymous; every nonempty set must contain the reserved `authenticated` privilege. Invalid credentials raise `UnauthorizedError`; malformed authentication results are programming errors. Store application user data in `request.ctx`.
* `error_response` shapes application error bodies; `finish_response` applies policy headers to normal responses and those errors. Protocol rejections before Request construction and bare 500 responses bypass both hooks.

Declare every Endpoint method or GET function with `@allow_public` or `@requires_privileges('privilege', ...)`.
To give every method of a route handler class the same policy, decorate the class instead; low-level handlers such as FilesHandler declare only this way.
Use `@requires_privileges('authenticated')` for any authenticated caller. Privilege names match exactly; punctuation has no special meaning.
The Router validates and snapshots declarations at registration with `pithy.web.auth.freeze_required_privileges`, which defines the rules.
Its `resolve_route` method returns a `ResolvedRoute` without constructing a handler.
The server checks the resolved destination's required privileges before calling its `get_handler` method or reading a body.
Decorators only attach metadata; direct function calls do not enforce access. See `pithy.web.auth` for the contract and explicit checks.
The Starlette adapter in `pithy.web.starlette` translates the same declarations into Starlette `requires` scopes.

`Router` and `RouterApp` accept `default_public=True` for applications that permit undeclared routes; explicit restrictions still apply.
For a simple WebApp, decorate `handle_request`; its declaration is validated and snapshotted when the subclass is defined.
The default `resolve_destination` returns an `AppDestination` for the app itself. RouterApp overrides that hook to return a resolved route.
Both participate in the same server authorization step. A custom resolver must return a `Destination` with explicit requirements and defer handler construction to `get_handler`.

## Browser Regression Tests

Standalone browser regression pages live in `pithy_/test/web/`, relative to the repository root.
When changing `pithy.js` or htmx integration, run the relevant pages in both Chromium and WebKit.
These tests are not run by `just check` or `just typecheck-js`.

Serve the repository root over HTTP and open each test page at its corresponding URL, such as `/pithy_/test/web/checkbox-inclusion.html`.
The pages load the repository's JavaScript through relative paths, run automatically, and display `PASS` with a check count or `FAIL` with error details.

* `checkbox-inclusion.html`: Checks boolean and set checkbox submission through `hx-include` and prefixed attributes, including inheritance, append behavior, disabled controls, and explicit value overrides. All test requests are canceled before transmission.
* `markdown-editor.html`: Checks the `markdown-editor` element of `static/markdown.js` under a strict Content Security Policy: syntax coloring, exact text round trips, equal layout of the textarea and its coloring layer, survival of DOM replacement, and pasted image attachments. Its checks are in `markdown-editor.js`, because the policy forbids inline scripts.
* `collapsible-tables.html`: Checks collapse toggling, hidden rows, and listener preservation across htmx morphs.
