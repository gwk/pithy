# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass, replace
from threading import Lock
from typing import get_args, Literal

from ....html import Button, Dialog, Div, H1, H2, Input, Label, Main, P, Select, Span, Table, Tbody, Td, Th, Thead, Tr
from ....markup import Present
from ...endpoint import Endpoint
from ...errors import BadRequestError, NotFoundError
from ...htmx import hx_trigger_on
from ...request import Request
from ...response import HtmlResponse, HtmxResponse
from ..domain_events import DomainEvent
from ..pages import dev_page


type UiMode = Literal['auto', 'light', 'dark']
type Privilege = Literal['publish', 'moderate', 'billing']


@dataclass(frozen=True)
class User:
  id:int
  name:str
  role:str
  vip:bool
  privileges:frozenset[Privilege]
  ui:UiMode


roles = ('Admin', 'Editor', 'Viewer')
privilege_labels:dict[Privilege,str] = {'publish': 'Publish', 'moderate': 'Moderate', 'billing': 'Billing'}
ui_modes:tuple[UiMode,...] = get_args(UiMode.__value__)
users = {user.id: user for user in (
  User(1, 'Alex Morgan', 'Admin', vip=False, privileges=frozenset({'publish'}), ui='auto'),
  User(2, 'Sam Rivera', 'Editor', vip=False, privileges=frozenset(), ui='light'))}
users_lock = Lock()


def get_user(user_id:int) -> User:
  try: return users[user_id]
  except KeyError: raise NotFoundError('Unknown demo user.') from None


def vip_text(user:User) -> str: return 'Yes' if user.vip else 'No'


def privileges_text(user:User) -> str:
  'List the user privileges in canonical order, or "None".'
  return ', '.join(label for p, label in privilege_labels.items() if p in user.privileges) or 'None'


def ui_text(ui:UiMode) -> str: return ui.capitalize()


def edit_button(user:User) -> Button:
  'Both views open the same modal endpoint with only the user ID.'
  return Button('Edit', type='button', aria_label=f'Edit {user.name}',
    hx_get=f'/htmx/modals/users/{user.id}/edit_modal.htmx', hx_target='#edit-modal', hx_swap='innerHTML')


def user_row(user:User) -> Tr:
  'The privileges column absorbs the remaining table width; the other cells do not wrap, so that updates do not reflow.'
  return Tr(Td(user.name, cl='nowrap'), Td(user.role, cl='nowrap'), Td(vip_text(user), cl='nowrap'),
    Td(privileges_text(user)), Td(ui_text(user.ui), cl='nowrap'), Td(edit_button(user)))


def users_table() -> Div:
  return Div(id='users-table', cl='panel flow', hx_get='/htmx/modals/users.htmx',
    hx_trigger=hx_trigger_on(from_body=DomainEvent.user_updated), hx_swap='outerHTML', _=[
      H2('Users'),
      Table(cl='w100', _=[Thead(Tr(Th('Name'), Th('Role'), Th('VIP'), Th('Privileges', cl='w100'), Th('UI'), Th('Edit'))),
        Tbody(_=[user_row(user) for user in users.values()])]),
    ])


def user_detail() -> Div:
  user = get_user(1)
  return Div(id='user-detail', cl='panel flow', hx_get='/htmx/modals/user_detail.htmx',
    hx_trigger=hx_trigger_on(from_body=DomainEvent.user_updated), hx_swap='outerHTML', _=[
      H2('Account owner'), P(f'Name: {user.name}'), P(f'Role: {user.role}'), P(f'VIP: {vip_text(user)}'),
      P(f'Privileges: {privileges_text(user)}'), P(f'UI: {ui_text(user.ui)}'), edit_button(user),
    ])


def dev_htmx_modals(request:Request) -> HtmlResponse:
  'Demonstrates a shared edit modal updating independent views.'
  return dev_page(title='HTMX Modals',
    breadcrumbs=[('/', 'Home'), ('/htmx', 'HTMX'), ('/htmx/modals', 'Modals')],
    main=Main(H1('HTMX Modals'),
      P('Edit the account owner from either section. Both views update as you change any field.'),
      P('Changes are shared by visitors and reset when the demo server restarts.'),
      Div(cl='controls-demo-layout', _=[users_table(), user_detail()]), Div(id='edit-modal')))


def users_table_htmx(request:Request) -> HtmxResponse:
  return HtmxResponse(users_table())


def user_detail_htmx(request:Request) -> HtmxResponse:
  return HtmxResponse(user_detail())


def edit_modal_htmx(request:Request, user_id:int) -> HtmxResponse:
  user = get_user(user_id)
  url = f'/htmx/modals/users/{user.id}/update.htmx'
  modal = Dialog.modal(
    H2('Edit user', id='edit-user-title'),
    P('Changes save automatically. Click outside this dialog when done.'),
    Div(cl='form_grid', _=[
      Label('Name', for_='edit-user-name'),
      Input(id='edit-user-name', name='name', value=user.name, required=True, maxlength=100,
        hx_post=url, hx_trigger='change', hx_swap='none'),
      Label('Role', for_='edit-user-role'),
      Select(id='edit-user-role', name='role', hx_post=url, hx_trigger='change', hx_swap='none')
        .options(roles, value=user.role),
      Label('VIP', for_='edit-user-vip'),
      # A bool checkbox always sends 'true' or 'false'; see `Input.bool_checkbox` and pithy.js.
      Input.bool_checkbox(id='edit-user-vip', name='vip', is_checked=user.vip, hx_post=url, hx_trigger='change',
        hx_swap='none'),
      Label('Privileges'),
      # The span is the htmx source, so every member of the set is sent; an empty set sends the NUL marker.
      Span(cl='input-labels-inline', hx_post=url, hx_trigger='change', hx_swap='none').labeled_checkboxes('privileges',
        require_one=False, choices=privilege_labels, checked=user.privileges),
      Label('UI'),
      Span(cl='input-labels-inline', _=[
        Label(Input(type='radio', name='ui', value=mode, checked=Present(mode == user.ui),
          hx_post=url, hx_trigger='change', hx_swap='none'), ui_text(mode))
        for mode in ui_modes]),
    ]),
  )
  modal['aria-labelledby'] = 'edit-user-title'
  return HtmxResponse(modal)


class UpdateUserHtmx(Endpoint):
  max_body_bytes = 4096

  class Post:
    user_id:int
    name:str|None
    role:str|None
    vip:bool|None
    privileges:list[Privilege]|None
    ui:UiMode|None

  def post(self, request:Request, fields:Post) -> HtmxResponse:
    provided = [f for f in (fields.name, fields.role, fields.vip, fields.privileges, fields.ui) if f is not None]
    if len(provided) != 1: raise BadRequestError('Provide exactly one field to update.')
    with users_lock:
      user = get_user(fields.user_id)
      if fields.name is not None:
        name = fields.name.strip()
        if not name or len(name) > 100: raise BadRequestError('Name must contain 1 to 100 characters.')
        user = replace(user, name=name)
      elif fields.role is not None:
        if fields.role not in roles: raise BadRequestError('Unknown role.')
        user = replace(user, role=fields.role)
      elif fields.vip is not None:
        user = replace(user, vip=fields.vip)
      elif fields.privileges is not None:
        user = replace(user, privileges=frozenset(fields.privileges))
      else:
        assert fields.ui is not None # The Literal field type rejects unknown modes before this point.
        user = replace(user, ui=fields.ui)
      users[user.id] = user
    # Target body explicitly so the event still arrives if the dialog has already been dismissed.
    return HtmxResponse(hx_trigger={DomainEvent.user_updated: {'target': 'body'}})
