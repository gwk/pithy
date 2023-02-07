# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..json import render_json


def htmx_vals(**items) -> str:
  '''
  Render an inline JSON string suitable for the 'hx-vals' attribute.
  '''
  return render_json(items, sort=False, indent=None)
