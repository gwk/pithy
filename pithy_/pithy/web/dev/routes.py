# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import datetime as dt

from ...html import Div, H1, Main, Strong
from ..endpoint import Endpoint
from ..request import Request, UploadedFile
from ..response import HtmlResponse, Response
from ..static import pithy_web_static_dir_path
from .controls import controls_form, controls_htmx, posted_values
from .responses import page_html


pithy_css_path = pithy_web_static_dir_path() + '/pithy.css'
max_body_bytes = 64 * 1024

class IndexHtml(Endpoint):
  'Returns a simple HTML page.'

  def handle_request(self, request:Request) -> HtmlResponse:
    return page_html(title='Index', main=Main('Index page'))



class DevControls(Endpoint):
  'Returns a form for testing controls.'
  max_body_bytes = 64 * 1024

  text: str | None
  email: str | None
  hidden: str | None
  number: str | None
  password: str | None
  tel: str | None
  url: str | None
  search: str | None
  textarea: str | None
  checkbox: str | None
  radio: str | None
  select: str | None
  date: str | None
  time: str | None
  color: str | None
  range: str | None
  submit: str | None
  week: str | None
  month: str | None
  datetime_local: str | None
  select_multiple: list[str] | None
  file: UploadedFile | None

  def _items(self) -> dict[str, str | list[str]]:
    return {name: v for name in self._fields if (v := getattr(self, name))}

  def handle_request(self, request:Request) -> Response:
    main = Main(
      H1('Dev Controls'),
      posted_values(self._items()),
      controls_form(self._items()))
    return page_html(title='Dev Controls', main=main)



class DevControlsHtmx(Endpoint):
  'Returns a page of testing controls as HTMX elements.'
  max_body_bytes = max_body_bytes

  def handle_request(self, request:Request) -> Response:
    main = Main(
      H1('Dev Controls'),
      posted_values(),
      controls_htmx())
    return page_html(title='Dev Controls', main=main)



class ControlsHtmxUpdate(Endpoint):
  'Handles any field update from the HTMX DevControls page.'
  max_body_bytes = max_body_bytes

  text: str | None
  email: str | None
  number: str | None
  password: str | None
  tel: str | None
  url: str | None
  search: str | None
  textarea: str | None
  checkbox: str | None
  radio: str | None
  select: str | None
  date: dt.date | None
  time: dt.time | None
  datetime_local: dt.datetime | None
  month: str | None
  week: str | None
  color: str | None
  range: int | None
  select_multiple: list[str] | None
  file: UploadedFile | None

  def handle_request(self, request:Request) -> Response:
    for name in self._fields:
      val = getattr(self, name)
      if val is None:
        continue
      display = name.replace('_', '-')
      if isinstance(val, UploadedFile):
        return HtmlResponse(body=Div(Strong(display), f': {val.filename} ({len(val.data)} bytes)'))
      return HtmlResponse(body=Div(Strong(display), f': {val}'))
    return HtmlResponse(body=Div())



class PithyCss(Endpoint):
  'Returns the pithy.css stylesheet.'

  def handle_request(self, request:Request) -> Response:
    with open(pithy_css_path, 'r') as f:
      css = f.read()
    return Response(body=css, media_type='text/css')



routes:dict[str,type[Endpoint]] = {
  '/': IndexHtml,
  '/controls': DevControls,
  '/controls-htmx': DevControlsHtmx,
  '/controls-htmx/update': ControlsHtmxUpdate,
  '/pithy.css': PithyCss,
}
