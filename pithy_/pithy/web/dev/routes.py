# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..router import RouteTarget
from .color_ramps import dev_color_ramps
from .colors import dev_colors
from .html import dev_html_index
from .html.controls import DevControlsForm, DevImageButtonForm
from .html.html_to_json import dev_html_to_json
from .html.nonportable import DevFormNonportable
from .htmx import dev_htmx_index
from .htmx.controls import ControlsHtmxUpdate, dev_controls_htmx
from .htmx.modals import dev_htmx_modals, edit_modal_htmx, UpdateUserHtmx, user_detail_htmx, users_table_htmx
from .markdown import dev_markdown, MarkdownRender, MarkdownSettingsHtmx
from .pages import DevStaticFiles, index_html, PithyStaticFiles
from .tables import dev_tables
from .tests import dev_tests
from .typography import dev_typography


routes:dict[str,RouteTarget] = {
  '/': index_html,
  '/colors': dev_colors,
  '/colors/ramps': dev_color_ramps,
  '/typography': dev_typography,
  '/tables': dev_tables,
  '/tests': dev_tests,
  '/html': dev_html_index,
  '/html/html-to-json': dev_html_to_json,
  '/html/controls': DevControlsForm,
  '/html/controls/image': DevImageButtonForm,
  '/html/nonportable': DevFormNonportable,
  '/htmx': dev_htmx_index,
  '/htmx/controls': dev_controls_htmx,
  '/htmx/controls/update.htmx': ControlsHtmxUpdate,
  '/htmx/modals': dev_htmx_modals,
  '/htmx/modals/users.htmx': users_table_htmx,
  '/htmx/modals/user_detail.htmx': user_detail_htmx,
  '/htmx/modals/users/{user_id:int}/edit_modal.htmx': edit_modal_htmx,
  '/htmx/modals/users/{user_id:int}/update.htmx': UpdateUserHtmx,
  '/markdown': dev_markdown,
  '/markdown/render': MarkdownRender,
  '/markdown/settings.htmx': MarkdownSettingsHtmx,
  '/static/pithy/{subpath:path}': PithyStaticFiles,
  '/static/dev/{subpath:path}': DevStaticFiles,
}
