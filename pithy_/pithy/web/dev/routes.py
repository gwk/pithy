# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..handler import RoutableHandler
from .controls import DevControlsIndex
from .controls.form import DevControlsForm
from .controls.htmx import ControlsHtmxUpdate, DevControlsHtmx
from .pages import DevStaticFiles, IndexHtml, PithyStaticFiles
from .typography import DevTypography


routes:dict[str,type[RoutableHandler]] = {
  '/': IndexHtml,
  '/typography': DevTypography,
  '/controls': DevControlsIndex,
  '/controls/form': DevControlsForm,
  '/controls/htmx': DevControlsHtmx,
  '/controls/htmx/update.htmx': ControlsHtmxUpdate,
  '/static/pithy/{subpath:path}': PithyStaticFiles,
  '/static/dev/{subpath:path}': DevStaticFiles,
}
