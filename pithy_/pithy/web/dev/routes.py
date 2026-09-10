# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..handler import RoutableHandler
from .controls import DevControlsIndex
from .controls.form import DevControlsForm
from .htmx import DevHtmxIndex
from .htmx.controls import ControlsHtmxUpdate, DevControlsHtmx
from .htmx.modals import DevHtmxModals, EditModalHtmx, UpdateUserHtmx, UserDetailHtmx, UsersTableHtmx
from .pages import DevStaticFiles, IndexHtml, PithyStaticFiles
from .tables import DevTables
from .typography import DevTypography


routes:dict[str,type[RoutableHandler]] = {
  '/': IndexHtml,
  '/typography': DevTypography,
  '/tables': DevTables,
  '/controls': DevControlsIndex,
  '/controls/form': DevControlsForm,
  '/htmx': DevHtmxIndex,
  '/htmx/controls': DevControlsHtmx,
  '/htmx/controls/update.htmx': ControlsHtmxUpdate,
  '/htmx/modals': DevHtmxModals,
  '/htmx/modals/users.htmx': UsersTableHtmx,
  '/htmx/modals/user_detail.htmx': UserDetailHtmx,
  '/htmx/modals/users/{user_id:int}/edit_modal.htmx': EditModalHtmx,
  '/htmx/modals/users/{user_id:int}/update.htmx': UpdateUserHtmx,
  '/static/pithy/{subpath:path}': PithyStaticFiles,
  '/static/dev/{subpath:path}': DevStaticFiles,
}
