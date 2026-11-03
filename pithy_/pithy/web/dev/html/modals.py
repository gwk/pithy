# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Developer reference page demonstrating modal dialogs that need no htmx.
The server renders the dialogs into the page and pithy.js wires them, without inline scripts.
'''

from typing import Literal

from ....html import A, Button, Code, Dialog, Div, H1, H2, Li, Main, P, Ul
from ....markup import Present
from ...request import Request
from ...response import HtmlResponse
from ..pages import dev_page


_context_keywords_ = ['closedby', 'confirmation', 'demo', 'dialog', 'light dismiss', 'notice', 'reusable modal',
  'showModal', 'transient modal']


type ClosedBy = Literal['any','closerequest','none']

closedby_examples:tuple[tuple[ClosedBy,str],...] = (
  ('any', 'A backdrop click or the escape key also closes it. Suits convenience dialogs such as notices and editors.'),
  ('closerequest', 'The escape key also closes it, but a backdrop click does not. '
    'Suits important content that the user may still back out of.'),
  ('none', 'Only the button closes it. Suits a confirmation that requires an explicit choice.'),
)
'The `closedby` values demonstrated by reusable dialogs, with a description of each.'


def dev_html_modals(request:Request, on_load:bool|None) -> HtmlResponse:
  'Demonstrates reusable modal dialogs with each `closedby` value, and optionally a transient dialog shown on load.'
  main = Main(H1('Modals'),
    P('These modal dialogs need no htmx. '
      'The server renders them into the page and pithy.js wires them without inline scripts.'),
    H2('Reusable Dialogs'),
    P('Each dialog stays hidden until its button is clicked, and remains in the page after closing. '
      'Its Close button always closes it; the ', Code('closedby'), ' attribute chooses which other user actions do.'),
    Ul(_=[Li(Button(f'Open closedby={closedby}', type='button', data_open_modal=modal_id(closedby)), ' ', desc)
      for closedby, desc in closedby_examples]),
    *[reusable_modal(closedby, desc) for closedby, desc in closedby_examples],
    H2('Transient Dialog on Load'),
    P('A dialog built with ', Code('Dialog.modal'), ' is transient: pithy.js shows it as soon as it enters the page, '
      'whether in the initial HTML or swapped in by htmx, and removes it when it closes.'),
    P(A(href='/html/modals?on_load=true', _='Load this page with a transient dialog'),
      '. It uses ', Code('closedby="none"'), ', so it must be acknowledged with its button. '
      'A real application would also record the acknowledgement so that the notice does not return.'),
  )
  if on_load:
    main.append(transient_modal())
  return dev_page(title='Modals', breadcrumbs=[('/', 'Home'), ('/html', 'HTML'), ('/html/modals', 'Modals')], main=main)


def modal_id(closedby:ClosedBy) -> str: return f'modal-closedby-{closedby}'


def reusable_modal(closedby:ClosedBy, desc:str) -> Dialog:
  title_id = f'{modal_id(closedby)}-title'
  return Dialog(id=modal_id(closedby), cl='modal', closedby=closedby, aria_labelledby=title_id, _=[
    Div(cl='pane flow', tabindex='-1', _=[
      H2(Code(f'closedby="{closedby}"'), id=title_id), P(desc),
      Button('Close', type='button', data_close_modal=Present(True)),
    ]),
  ])


def transient_modal() -> Dialog:
  modal = Dialog.modal(
    H2('Acknowledgement Required', id='transient-modal-title'),
    P('This dialog was part of the page that the server sent. Neither the backdrop nor the escape key dismisses it.'),
    P('A modal suits a notice that the user must acknowledge before continuing. '
      'For a notice that does not need acknowledgement, prefer a banner.'),
    Button('Acknowledge', type='button', data_close_modal=Present(True)),
    closedby='none', cl='flow')
  modal['aria-labelledby'] = 'transient-modal-title'
  return modal
