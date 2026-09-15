# pithy.web

`pithy.web` provides an HTTP 1.1 web server framework.
The web developer creates Endpoint subclasses, each of which defines a handler method per accepted HTTP method
(`get`, `post`, etc.), optionally paired with an inner fields class of the same name (`Get`, `Post`, etc.).
The router dispatches to that endpoint, and a fresh fields instance for the request method (exposed as `self.fields`) is constructed.
The fields object is filled and validated from path params, query params, and body params, then passed to the handler.

Goals:
* identify developer errors rather than ignore them;
* reject weird requests with missing or extra parameters;
* reduce boilerplate;
* generally make development easier while remaining simple.
