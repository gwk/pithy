# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Reusable functions that generate HTML parts.
'''


from typing import Any, Mapping
from urllib.parse import urlencode

from . import A, Div, MuAttrs, Span


def pagination_control(*, count:int|None, limit:int, offset:int, href:str='', hx_get:str='', params:Mapping[str,Any],
 link_attrs:MuAttrs|None=None) -> Div:
  """
  Generate a pagination control component.

  Args:
    count (int | None): Total count of results. None if the query failed.
    limit (int): Maximum number of results per page.
    offset (int): Offset of the current page.
    href (str): Base URL for pagination links.
    hx_get (str): hx-get attribute for pagination links (mutually exclusive with `href`).
    params (Mapping[str, str]): Parameters for generating pagination links.

  Returns:
    Div: Pagination control component as a Div element.

  Example usage:
    pagination = pagination_control(count=100, limit=20, offset=40, params={'param1': 'value1', 'param2': 'value2'})

  Notes:
    If both `href` and `hx_get` are empty, the links will have an empty path and thus lead to the current page.
  """

  if href and hx_get: raise ValueError("`href` and `hx_get` cannot both be provided")

  if link_attrs is None: link_attrs = {}

  first = A(cl='icon', _='⏮️', **link_attrs)
  prev  = A(cl='icon', _='◀️', **link_attrs)
  next_ = A(cl='icon', _='▶️', **link_attrs)
  last  = A(cl='icon', _='⏭️', **link_attrs)
  icons = (first, prev, next_, last)

  msg = Span(cl='msg')
  div = Div(*icons, msg, cl='pagination-control')

  if count is None:
    msg.append('Query failed.')
  elif count == 0:
    msg.append('No results.')
  elif count <= limit:
    msg.append(f'{count} results.')
  else:
    s = offset + 1
    l = min(offset + limit, count)
    msg.append(f'{s:,}-{l:,} of {count:,} results.')

    use_hx = bool(hx_get)
    url_key = 'hx-get' if use_hx else 'href'
    url = hx_get if use_hx else href
    if '#' in url: raise ValueError("`href`/`hx_get` cannot contain fragment character '#'")
    if '?' not in url: url += '?'
    elif not url.endswith('&'): url += '&'
    qp = f'{urlencode(tuple((k, str(v)) for k, v in params.items() if k != 'offset'))}'
    if qp: url += f'{qp}&'

    if offset > 0:
      first[url_key] = f'{url}offset=0'
      prev[url_key]  = f'{url}offset={max(0, offset - limit)}'
    if l < count:
      rem = count % limit
      last_offset = count - (rem or limit)
      next_[url_key] = f'{url}offset={offset + limit}'
      last[url_key]  = f'{url}offset={last_offset}'

  return div
