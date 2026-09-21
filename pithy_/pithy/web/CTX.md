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

  def get(self, request:Request, fields:Get) -> Response:
    return Response(body=f'{fields.uid}: {fields.tab}')

  class Post:
    uid:int
    name:str
    email:str

  def post(self, request:Request, fields:Post) -> Response:
    return Response(body=f'{fields.uid}: {fields.name} <{fields.email}>')

router = Router({'/users/{uid:int}': UserEndpoint})
```

For simple GET routes, register a function directly. This is equivalent to the GET handler above:

```python
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

## Browser Regression Tests

Standalone browser regression pages live in `pithy_/test/web/`, relative to the repository root.
When changing `pithy.js` or htmx integration, run the relevant pages in both Chromium and WebKit.
These tests are not run by `just check` or `just typecheck-js`.

Serve the repository root over HTTP and open each test page at its corresponding URL, such as `/pithy_/test/web/checkbox-inclusion.html`.
The pages load the repository's JavaScript through relative paths, run automatically, and display `PASS` with a check count or `FAIL` with error details.

* `checkbox-inclusion.html`: Checks boolean and set checkbox submission through `hx-include` and prefixed attributes, including inheritance, append behavior, disabled controls, and explicit value overrides. All test requests are canceled before transmission.
* `collapsible-tables.html`: Checks collapse toggling, hidden rows, and listener preservation across htmx morphs.
