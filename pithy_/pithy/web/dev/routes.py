# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ...html import H1, Main
from ..endpoint import Endpoint
from ..request import Request
from ..response import HtmlResponse, Response
from ..static import pithy_web_static_dir_path
from .controls import controls_form
from .responses import page_html


pithy_css_path = pithy_web_static_dir_path() + '/pithy.css'


class IndexHtml(Endpoint):
  'Returns a simple HTML page.'

  def handle_request(self, request:Request) -> HtmlResponse:
    return page_html(title='Index', main=Main('Index page'))



class DevControls(Endpoint):
  'Returns a form for testing controls.'

  def handle_request(self, request:Request) -> Response:
    main = Main(
      H1('Dev Controls'),
      controls_form())
    return page_html(title='Dev Controls', main=main)


class PithyCss(Endpoint):
  'Returns the pithy.css stylesheet.'

  def handle_request(self, request:Request) -> Response:
    with open(pithy_css_path, 'r') as f:
      css = f.read()
    return Response(body=css, media_type='text/css')



routes:dict[str,type[Endpoint]] = {
  '/': IndexHtml,
  '/controls': DevControls,
  '/pithy.css': PithyCss,
}
