# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass, replace
from threading import Lock
from typing import get_args, Literal

from ....html import Button, Dialog, Div, H1, H2, Input, Label, Main, P, Select, Span, Table, Tbody, Td, Th, Thead, Tr
from ....markup import Present
from ...endpoint import Endpoint, NoFields
from ...errors import BadRequestError, NotFoundError
from ...htmx import hx_trigger_on
from ...request import Request
from ...response import HtmlResponse, HtmxResponse
from ..domain_events import DomainEvent
from ..pages import dev_page


type UiMode = Literal['auto', 'light', 'dark']


@dataclass(frozen=True)
class User:
  id:int
  name:str
  role:str
  vip:bool
  ui:UiMode


roles = ('Admin', 'Editor', 'Viewer')
ui_modes:tuple[UiMode,...] = get_args(UiMode.__value__)
users = {user.id: user for user in (
  User(1, 'Alex Morgan', 'Admin', vip=False, ui='auto'),
  User(2, 'Sam Rivera', 'Editor', vip=False, ui='light'))}
users_lock = Lock()


def get_user(user_id:int) -> User:
  try: return users[user_id]
  except KeyError: raise NotFoundError('Unknown demo user.') from None


def vip_text(user:User) -> str: return 'Yes' if user.vip else 'No'


def ui_text(ui:UiMode) -> str: return ui.capitalize()


def edit_button(user:User) -> Button:
  'Both views open the same modal endpoint with only the user ID.'
  return Button('Edit', type='button', aria_label=f'Edit {user.name}',
    hx_get=f'/htmx/modals/users/{user.id}/edit_modal.htmx', hx_target='#edit-modal', hx_swap='innerHTML')


def users_table() -> Div:
  return Div(id='users-table', cl='panel flow', hx_get='/htmx/modals/users.htmx',
    hx_trigger=hx_trigger_on(from_body=DomainEvent.user_updated), hx_swap='outerHTML', _=[
      H2('Users'),
      Table(Thead(Tr(Th('Name'), Th('Role'), Th('VIP'), Th('UI'), Th('Edit'))),
        Tbody(_=[Tr(Td(user.name), Td(user.role), Td(vip_text(user)), Td(ui_text(user.ui)), Td(edit_button(user)))
          for user in users.values()])),
    ])


def user_detail() -> Div:
  user = get_user(1)
  return Div(id='user-detail', cl='panel flow', hx_get='/htmx/modals/user_detail.htmx',
    hx_trigger=hx_trigger_on(from_body=DomainEvent.user_updated), hx_swap='outerHTML', _=[
      H2('Account owner'), P(f'Name: {user.name}'), P(f'Role: {user.role}'), P(f'VIP: {vip_text(user)}'),
      P(f'UI: {ui_text(user.ui)}'), edit_button(user),
    ])


class DevHtmxModals(Endpoint):
  'Demonstrates a shared edit modal updating independent views.'

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmlResponse:
    return dev_page(title='HTMX Modals',
      breadcrumbs=[('/', 'Home'), ('/htmx', 'HTMX'), ('/htmx/modals', 'Modals')],
      main=Main(H1('HTMX Modals'),
        P('Edit the account owner from either section. Both views update as you change any field.'),
        P('Changes are shared by visitors and reset when the demo server restarts.'),
        Div(cl='controls-demo-layout', _=[users_table(), user_detail()]), Div(id='edit-modal')))


class UsersTableHtmx(Endpoint):

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmxResponse:
    return HtmxResponse(users_table())


class UserDetailHtmx(Endpoint):

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmxResponse:
    return HtmxResponse(user_detail())


class EditModalHtmx(Endpoint):

  class Fields:
    user_id:int

  def handle_endpoint(self, request:Request, fields:Fields) -> HtmxResponse:
    user = get_user(fields.user_id)
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
        # An unchecked box is omitted from the request, which the update endpoint could not distinguish from another
        # field's update. `hx-vals` with a `js:` expression is evaluated with `this` bound to the element, so it sends
        # the checked state explicitly.
        Input.checkbox(id='edit-user-vip', name='vip', is_checked=user.vip, hx_vals='js:{vip: this.checked}',
          hx_post=url, hx_trigger='change', hx_swap='none'),
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
  methods = 'POST'
  max_body_bytes = 4096

  class Fields:
    user_id:int
    name:str|None
    role:str|None
    vip:bool|None
    ui:UiMode|None

  def handle_endpoint(self, request:Request, fields:Fields) -> HtmxResponse:
    provided = [f for f in (fields.name, fields.role, fields.vip, fields.ui) if f is not None]
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
      else:
        assert fields.ui is not None # The Literal field type rejects unknown modes before this point.
        user = replace(user, ui=fields.ui)
      users[user.id] = user
    # Target body explicitly so the event still arrives if the dialog has already been dismissed.
    return HtmxResponse(hx_trigger={DomainEvent.user_updated: {'target': 'body'}})
