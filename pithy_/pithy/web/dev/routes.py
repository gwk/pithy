# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..endpoint import Endpoint
from .controls.form import DevControlsForm
from .controls.htmx import ControlsHtmxUpdate, DevControlsHtmx
from .pages import IndexHtml, PithyCss


routes:dict[str,type[Endpoint]] = {
  '/': IndexHtml,
  '/controls/form': DevControlsForm,
  '/controls/htmx': DevControlsHtmx,
  '/controls/htmx/update.htmx': ControlsHtmxUpdate,
  '/pithy.css': PithyCss,
}
