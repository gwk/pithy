# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Reusable functions that generate HTML parts.
'''


from typing import Mapping

from . import Div


def pagination_control(count:int|None, limit:int, offset:int, params:Mapping[str,str]) -> Div:
  raise NotImplementedError # TODO: factor out from select.render_pagination_control.
