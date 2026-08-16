# pithy.web

`pithy.web` provides an HTTP 1.1 web server framework.
The web developer creates Endpoint subclasses, each of which declares an inner `Fields` class.
The router dispatches to that endpoint, and a fresh `Fields` instance (exposed as `self.fields`) is constructed.
The fields object is filled and validated from path params, query params, and body params.

Goals:
* identify developer errors rather than ignore them;
* reject weird requests with missing or extra parameters;
* reduce boilerplate;
* generally make development easier while remaining simple.
