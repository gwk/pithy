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
    return {name: v for name in self._field_transtructors if (v := getattr(self, name))}

  def handle_request(self, request:Request) -> Response:
    main = Main(
      H1('Dev Controls'),
      posted_values(self._items()),
      controls_form(self._items()))
    return page_html(title='Dev Controls', main=main)



class DevControlsHTMX(Endpoint):
  'Returns a page of testing controls as htmx elements.'
  max_body_bytes = max_body_bytes

  def handle_request(self, request:Request) -> Response:
    main = Main(
			H1('Dev Controls'),
      posted_values(),
			controls_htmx())
    return page_html(title='Dev Controls', main=main)



class TextHTMX(Endpoint):
  'Handles updates to the text input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  text: str | None

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('text'), f': {self.text}'))



class EmailHTMX(Endpoint):
  'Handles updates to the email input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  email: str | None

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('email'), f': {self.email}'))



class NumberHTMX(Endpoint):
  'Handles updates to the number input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  number: str | None

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('number'), f': {self.number}'))



class PasswordHTMX(Endpoint):
  'Handles updates to the password input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  password: str | None

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('password'), f': {self.password}'))



class TelHTMX(Endpoint):
  'Handles updates to the tel input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  tel: str | None

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('tel'), f': {self.tel}'))



class UrlHTMX(Endpoint):
  'Handles updates to the url input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  url: str | None

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('url'), f': {self.url}'))



class SearchHTMX(Endpoint):
  'Handles updates to the search input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  search: str | None

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('search'), f': {self.search}'))



class TextareaHTMX(Endpoint):
  'Handles updates to the textarea input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  textarea: str | None

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('textarea'), f': {self.textarea}'))



class CheckboxHTMX(Endpoint):
  'Handles updates to the checkbox input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  checkbox: str | None

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('checkbox'), f': {self.checkbox}'))



class RadioHTMX(Endpoint):
  'Handles updates to the radio input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  radio: str

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('radio'), f': {self.radio}'))



class SelectHTMX(Endpoint):
  'Handles updates to the select input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  select: str

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('select'), f': {self.select}'))



class DateHTMX(Endpoint):
  'Handles updates to the date input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  date:dt.date

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('date'), f': {self.date}'))



class TimeHTMX(Endpoint):
  'Handles updates to the time input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  time: dt.time

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('time'), f': {self.time}'))



class DatetimeLocalHTMX(Endpoint):
  'Handles updates to the datetime-local input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  datetime_local: dt.datetime

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('datetime-local'), f': {self.datetime_local}'))



class MonthHTMX(Endpoint):
  'Handles updates to the month input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  month: str

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('month'), f': {self.month}'))



class WeekHTMX(Endpoint):
  'Handles updates to the week input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  week: str

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('week'), f': {self.week}'))



class ColorHTMX(Endpoint):
  'Handles updates to the color input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  color: str

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('color'), f': {self.color}'))



class RangeHTMX(Endpoint):
  'Handles updates to the range input on the HTMX DevControls page'
  max_body_bytes = max_body_bytes
  range: int

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('range'), f': {self.range}'))



class SelectMultipleHTMX(Endpoint):
  'Handles updates to the select-multiple input on the HTMX DevControls page.'
  max_body_bytes = max_body_bytes
  select_multiple: list[str]

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('select-multiple'), f': {", ".join(self.select_multiple)}'))



class FileHTMX(Endpoint):
  'Handles file uploads on the HTMX DevControls page.'
  max_body_bytes = max_body_bytes
  file: UploadedFile

  def handle_request(self, request:Request) -> Response:
    return HtmlResponse(body=Div(Strong('file'), f': {self.file.filename} ({len(self.file.data)} bytes)'))



class PithyCss(Endpoint):
  'Returns the pithy.css stylesheet.'

  def handle_request(self, request:Request) -> Response:
    with open(pithy_css_path, 'r') as f:
      css = f.read()
    return Response(body=css, media_type='text/css')



routes:dict[str,type[Endpoint]] = {
  '/': IndexHtml,
  '/controls': DevControls,
  '/controls-htmx': DevControlsHTMX,
  '/controls-htmx/text': TextHTMX,
  '/controls-htmx/email': EmailHTMX,
  '/controls-htmx/number': NumberHTMX,
  '/controls-htmx/password': PasswordHTMX,
  '/controls-htmx/tel': TelHTMX,
  '/controls-htmx/url': UrlHTMX,
  '/controls-htmx/search': SearchHTMX,
  '/controls-htmx/textarea': TextareaHTMX,
  '/controls-htmx/checkbox': CheckboxHTMX,
  '/controls-htmx/radio': RadioHTMX,
  '/controls-htmx/select': SelectHTMX,
  '/controls-htmx/date': DateHTMX,
  '/controls-htmx/time': TimeHTMX,
  '/controls-htmx/datetime-local': DatetimeLocalHTMX,
  '/controls-htmx/month': MonthHTMX,
  '/controls-htmx/week': WeekHTMX,
  '/controls-htmx/color': ColorHTMX,
  '/controls-htmx/range': RangeHTMX,
  '/controls-htmx/select-multiple': SelectMultipleHTMX,
  '/controls-htmx/file': FileHTMX,
  '/pithy.css': PithyCss,
}
