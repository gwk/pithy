# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from .app import WebApp
from .request import Request
from .response import Response


class EchoApp(WebApp):

  def handle_request(self, request:Request) -> Response:
    query = f'?{request.query_str}' if request.query_str else ''
    lines = [f'{request.method}: {request.path}{query}']
    for name, value in sorted(request.headers.items()):
      lines.append(f'{name}: {value}')
    req_body_str = ''
    match request.media_type:
      case 'application/x-www-form-urlencoded':
        params = request.parse_urlencoded(max_bytes=16_384)
        if params:
          req_body_str = '\n'.join(f'{k}: {v}' for k, vs in params.items() for v in vs)
      case 'application/json':
        data = request.parse_json(max_bytes=16_384)
        # TODO: use a nicer json renderer implemented in pithy.json.render.
        if isinstance(data, dict) and data:
          req_body_str = '\n'.join(f'{k}: {v}' for k, v in data.items())
      case 'text/plain':
        raw = request.read_body(max_bytes=16_384)
        if raw: req_body_str = raw.decode()
      case 'multipart/form-data':
        parts = request.parse_multipart(max_bytes=16_384)
        if parts:
          part_lines = []
          for k, vs in parts.items():
            for v in vs:
              if isinstance(v, str):
                part_lines.append(f'{k}: {v}')
              else:
                part_lines.append(f'{k}: {v.filename} ({v.content_type}, {len(v.data)} bytes)')
          req_body_str = '\n'.join(part_lines)
      case _:
        raw = request.read_body(max_bytes=16_384)
        if raw: req_body_str = f'[unknown content type: {request.content_type}, {len(raw)} bytes]'

    if req_body_str:
      lines.append('')
      lines.append(req_body_str)
    body = '\n'.join(lines)
    return Response(body=body, media_type='text/plain')


def main() -> None:
  from .server import WebServer
  app = EchoApp()
  server = WebServer(app=app)
  server.serve_forever()


if __name__ == '__main__': main()
