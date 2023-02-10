# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from . import HTTPStatus, Request, Response
from .app import WebApp


class EchoApp(WebApp):

  def handle_expect_100_continue(self, request: Request) -> Response:
    from pithy.io import errP
    errP('EchoApp.handle_expect_100_continue', request)
    return Response(status=HTTPStatus.CONTINUE)


  def handle_request(self, request:Request) -> Response:
    if request.content_length:
      if request.method == 'POST':
        rb = '\n'.join(f'{k!r} : {v!r}' for k, v in request.post_params_single.items())
      else:
        lines = request.body_bytes.split(b'\n')
        body_repr = '\n'.join(repr(line) for line in lines)
    else:
      rb = ''
    if rb: rb = '\n\nbody:\n' + rb
    from pprint import pformat
    body = f'EchoApp response:\n{pformat(request, indent=2, width=128)}{rb}\n'
    return Response(body=body, media_type='text/plain')


  def fill_response_headers(self, request:Request, response:Response, close_connection:bool) -> None:
    'Override hack to show all response headers in the body.'
    super().fill_response_headers(request, response, close_connection)
    header_text = '\n'.join(f'  {k!r}: {v!r}' for k, v in response.headers.items())
    addendum = f'\nresponse headers: {header_text}\n'
    assert isinstance(response.body, bytes)
    response.body += addendum.encode()


def main() -> None:
  from sys import argv
  arg = argv[1]
  host = 'localhost'
  port = 8080
  match arg:
    case 'gunicorn':
      from pithy.task import exec
      cmd = [
        'gunicorn',
        f'--bind={host}:{port}',
        '--workers=2',
        '--access-logfile=-',
        '--reload',
        'pithy.http.echoapp:EchoApp()']
      exec(cmd)
    case 'pithy':
      from ..http.server import HttpServer
      server = HttpServer(host=host, port=port, app=EchoApp())
      server.serve_forever()
    case 'werkzeug':
      from werkzeug.serving import run_simple
      run_simple(hostname=host, port=port, application=EchoApp(), use_reloader=True, reloader_type='watchdog')
    case _:
      raise ValueError(arg)

if __name__ == '__main__': main()
