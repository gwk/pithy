# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass, replace
from threading import Lock

from ....html import Button, Dialog, Div, H1, H2, Input, Label, Main, P, Select, Table, Tbody, Td, Th, Thead, Tr
from ...endpoint import Endpoint, NoFields
from ...errors import BadRequestError, NotFoundError
from ...htmx import hx_trigger_on
from ...request import Request
from ...response import HtmlResponse, HtmxResponse
from ..domain_events import DomainEvent
from ..pages import dev_page


@dataclass(frozen=True)
class User:
  id:int
  name:str
  role:str


roles = ('Admin', 'Editor', 'Viewer')
users = {user.id: user for user in (User(1, 'Alex Morgan', 'Admin'), User(2, 'Sam Rivera', 'Editor'))}
users_lock = Lock()


def get_user(user_id:int) -> User:
  try: return users[user_id]
  except KeyError: raise NotFoundError('Unknown demo user.') from None


def edit_button(user:User) -> Button:
  'Both views open the same modal endpoint with only the user ID.'
  return Button('Edit', type='button', aria_label=f'Edit {user.name}',
    hx_get=f'/htmx/modals/users/{user.id}/edit_modal.htmx', hx_target='#edit-modal', hx_swap='innerHTML')


def users_table() -> Div:
  return Div(id='users-table', cl='panel flow', hx_get='/htmx/modals/users.htmx',
    hx_trigger=hx_trigger_on(from_body=DomainEvent.user_updated), hx_swap='outerHTML', _=[
      H2('Users'),
      Table(Thead(Tr(Th('Name'), Th('Role'), Th('Edit'))),
        Tbody(_=[Tr(Td(user.name), Td(user.role), Td(edit_button(user))) for user in users.values()])),
    ])


def user_detail() -> Div:
  user = get_user(1)
  return Div(id='user-detail', cl='panel flow', hx_get='/htmx/modals/user_detail.htmx',
    hx_trigger=hx_trigger_on(from_body=DomainEvent.user_updated), hx_swap='outerHTML', _=[
      H2('Account owner'), P(f'Name: {user.name}'), P(f'Role: {user.role}'), edit_button(user),
    ])


class DevHtmxModals(Endpoint):
  'Demonstrates a shared edit modal updating independent views.'

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmlResponse:
    return dev_page(title='HTMX Modals',
      breadcrumbs=[('/', 'Home'), ('/htmx', 'HTMX'), ('/htmx/modals', 'Modals')],
      main=Main(H1('HTMX Modals'),
        P('Edit the account owner from either section. Both views update as you change the name or role.'),
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
        Label('Name', attrs_by_ref={'for': 'edit-user-name'}),
        Input(id='edit-user-name', name='name', value=user.name, required=True, maxlength=100,
          hx_post=url, hx_trigger='change', hx_swap='none'),
        Label('Role', attrs_by_ref={'for': 'edit-user-role'}),
        Select(id='edit-user-role', name='role', hx_post=url, hx_trigger='change', hx_swap='none')
          .options(roles, value=user.role),
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

  def handle_endpoint(self, request:Request, fields:Fields) -> HtmxResponse:
    if (fields.name is None) == (fields.role is None):
      raise BadRequestError('Provide exactly one field to update.')
    with users_lock:
      user = get_user(fields.user_id)
      if fields.name is not None:
        name = fields.name.strip()
        if not name or len(name) > 100: raise BadRequestError('Name must contain 1 to 100 characters.')
        user = replace(user, name=name)
      else:
        if fields.role not in roles: raise BadRequestError('Unknown role.')
        assert fields.role is not None
        user = replace(user, role=fields.role)
      users[user.id] = user
    # Target body explicitly so the event still arrives if the dialog has already been dismissed.
    return HtmxResponse(hx_trigger={DomainEvent.user_updated: {'target': 'body'}})
