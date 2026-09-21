# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..router import RouteTarget
from .form import dev_form_index
from .form.controls import DevControlsForm
from .form.misc import DevFormMisc
from .form.nonportable import DevFormNonportable
from .htmx import dev_htmx_index
from .htmx.controls import ControlsHtmxUpdate, dev_controls_htmx
from .htmx.modals import dev_htmx_modals, edit_modal_htmx, UpdateUserHtmx, user_detail_htmx, users_table_htmx
from .markdown import dev_markdown, MarkdownSettingsHtmx, MarkdownValueHtmx
from .pages import DevStaticFiles, index_html, PithyStaticFiles
from .tables import dev_tables
from .typography import dev_typography


routes:dict[str,RouteTarget] = {
  '/': index_html,
  '/typography': dev_typography,
  '/tables': dev_tables,
  '/form': dev_form_index,
  '/form/controls': DevControlsForm,
  '/form/misc': DevFormMisc,
  '/form/nonportable': DevFormNonportable,
  '/htmx': dev_htmx_index,
  '/htmx/controls': dev_controls_htmx,
  '/htmx/controls/update.htmx': ControlsHtmxUpdate,
  '/htmx/modals': dev_htmx_modals,
  '/htmx/modals/users.htmx': users_table_htmx,
  '/htmx/modals/user_detail.htmx': user_detail_htmx,
  '/htmx/modals/users/{user_id:int}/edit_modal.htmx': edit_modal_htmx,
  '/htmx/modals/users/{user_id:int}/update.htmx': UpdateUserHtmx,
  '/markdown': dev_markdown,
  '/markdown/settings.htmx': MarkdownSettingsHtmx,
  '/markdown/value.htmx': MarkdownValueHtmx,
  '/static/pithy/{subpath:path}': PithyStaticFiles,
  '/static/dev/{subpath:path}': DevStaticFiles,
}
