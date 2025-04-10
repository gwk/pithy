# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Reusable functions that generate HTML parts.
'''


from typing import Mapping
from urllib.parse import urlencode

from . import A, Div, Span


def pagination_control(count:int|None, limit:int, offset:int, params:Mapping[str,str]) -> Div:
  """
  Generate a pagination control component.

  Args:
      count (int | None): Total count of results. None if the query failed.
      limit (int): Maximum number of results per page.
      offset (int): Offset of the current page.
      params (Mapping[str, str]): Parameters for generating pagination links.

  Returns:
      Div: Pagination control component as a Div element.

  Example usage:
      pagination = pagination_control(100, 20, 40, {'param1': 'value1', 'param2': 'value2'})
  """
  first = A(cl='icon', _='⏮️')
  prev  = A(cl='icon', _='◀️')
  next_ = A(cl='icon', _='▶️')
  last  = A(cl='icon', _='⏭️')
  icons = (first, prev, next_, last)

  msg = Span(cl='msg')
  div = Div(*icons, msg, cl='pagination-control')

  if count is None:
    msg.append('Query failed.')
  elif count > 0:
    if count > limit:
      s = offset + 1
      l = min(offset + limit, count)
      msg.append(f'{s:,}-{l:,} of {count:,} results.')
      qp = f'{urlencode(tuple((k, str(v)) for k, v in params.items() if k != "offset"))}'
      if offset > 0:
        first['href'] = f'?{qp}'
        prev['href']  = f'?{qp}&offset={offset - limit}'
      if l < count:
        next_['href'] = f'?{qp}&offset={offset + limit}'
        last['href']  = f'?{qp}&offset={count - limit}'
    else:
      msg.append(f'{count} results.')
  else:
    msg.append('No results.')

  return div
