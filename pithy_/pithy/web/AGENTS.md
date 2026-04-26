# pithy.web

`pithy.web` provides an HTTP 1.1 web server framework in development.
Its design allows a web developer to create an Endpoint subclass and when the router dispatches to that endpoint,
the subclass fields are filled and validated from path params, query params, and body params.
The design strives:
* identify developer errors rather than ignore them;
* reject weird requests with missing or extra parameters;
* generally make development easier while remaining simple.
