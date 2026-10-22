# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from json import loads

from pithy.web.app import WebApp
from pithy.web.errorrender import (bare_media_type, default_error_media_type, default_error_renderers, error_reason,
  render_error_html, render_error_problem_json, render_error_text)
from pithy.web.errors import BadRequestError, MethodNotAllowedError, NotFoundError, ResponseError
from pithy.web.request import Request
from pithy.web.response import Response
from utest import utest, utest_exc, utest_run, utest_val


def _request(method:str='GET') -> Request:
  return Request(method=method, scheme='http', host='localhost', port=80, path='/', query_str='', headers={},
    client_addr=('127.0.0.1', 0), content_length=None)


@utest_run
def test_reason() -> None:
  utest('Not Found.', error_reason, NotFoundError())
  utest('Unknown parameter.', error_reason, BadRequestError('Unknown parameter'))
  utest('Unknown parameter.', error_reason, BadRequestError('Unknown parameter.'))
  utest('Really?', error_reason, BadRequestError('Really?'))


@utest_run
def test_text() -> None:
  response = render_error_text(_request(), BadRequestError('bad input'))
  utest_val(HTTPStatus.BAD_REQUEST, response.status)
  utest_val('bad input', response.reason)
  utest_val(b'400: bad input.\n', response.body)
  utest_val('text/plain;charset=utf-8', response.headers['content-type'])


@utest_run
def test_html() -> None:
  response = render_error_html(_request(), BadRequestError('<script>'))
  assert isinstance(response.body, bytes)
  utest_val(True, b'<p>400: &lt;script&gt;.</p>' in response.body, desc='escaped reason')
  utest_val(True, b'<title>400 Bad Request</title>' in response.body, desc='title')
  utest_val('text/html;charset=utf-8', response.headers['content-type'])


@utest_run
def test_problem_json() -> None:
  response = render_error_problem_json(_request(), NotFoundError())
  assert isinstance(response.body, bytes)
  utest_val({'status': 404, 'title': 'Not Found'}, loads(response.body))
  utest_val('application/problem+json', response.headers['content-type'])

  detailed = render_error_problem_json(_request(), BadRequestError('bad input'))
  assert isinstance(detailed.body, bytes)
  utest_val({'detail': 'bad input', 'status': 400, 'title': 'Bad Request'}, loads(detailed.body))


@utest_run
def test_error_headers_and_head() -> None:
  'Every renderer preserves the error headers and omits the body for HEAD.'
  error = MethodNotAllowedError(frozenset({'GET', 'POST'}))
  for renderer in (render_error_text, render_error_html, render_error_problem_json):
    response = renderer(_request(), error)
    utest_val('GET, POST', response.headers['allow'], desc=f'{renderer.__name__} allow header')
    head = renderer(_request('HEAD'), error)
    utest_val(None, head.body, desc=f'{renderer.__name__} HEAD body')
    utest_val(None, head.headers.get('content-type'), desc=f'{renderer.__name__} HEAD content-type')
    utest_val('GET, POST', head.headers['allow'], desc=f'{renderer.__name__} HEAD allow header')


@utest_run
def test_defaults() -> None:
  utest('text/plain', bare_media_type, 'text/plain;charset=utf-8')
  utest('text/html', bare_media_type, ' Text/HTML ')
  utest_val(True, default_error_media_type in default_error_renderers, desc='default media type has a renderer')
  def mutate_defaults() -> None:
    default_error_renderers['text/plain'] = render_error_html # type: ignore[index]
  utest_exc(TypeError, mutate_defaults)


@utest_run
def test_app_defaults() -> None:
  'A WebApp without customization renders plain text errors; a declared media type selects its renderer.'
  response = WebApp().error_response(_request(), NotFoundError())
  utest_val(b'404: Not Found.\n', response.body)

  class JsonApp(WebApp):
    error_media_type = 'application/json'
  utest_val('application/problem+json', JsonApp().error_response(_request(), NotFoundError()).headers['content-type'])

  def render_custom(request:Request, error:ResponseError) -> Response:
    return Response(error.status, body='custom', media_type='text/plain')
  class CustomApp(WebApp):
    error_renderers = {**default_error_renderers, 'text/plain': render_custom}
  utest_val(b'custom', CustomApp().error_response(_request(), NotFoundError()).body)

  def define_unrenderable() -> None:
    class UnrenderableApp(WebApp):
      error_media_type = 'text/csv'
  utest_exc(TypeError, define_unrenderable)

  def define_parameterized() -> None:
    class ParameterizedApp(WebApp):
      error_media_type = 'text/plain;charset=utf-8'
  utest_exc(TypeError, define_parameterized)
