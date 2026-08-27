# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page showing the baseline styling of tables.'

from ...date import Date, DateTime, dt_IMp, dt_Ymd_IMp, Time
from ...html import Code, Div, H1, H2, Main, P, Section, Table, Td, Th, Tr
from ..endpoint import Endpoint, NoFields
from ..request import Request
from ..response import HtmlResponse
from .pages import dev_page


# (name, count, weight, nocturnal, discovered, last fed, wakes at, description) rows for the demo tables.
rows = [
  ('Alligator', 2, 453.59, False, Date(1807, 1, 1), DateTime(2026, 8, 24, 8, 5), Time(6, 30),
    'A broad-snouted reptile that patrols the demo marsh.'),
  ('Bat', 128, 0.03, True, Date(1758, 1, 1), DateTime(2026, 8, 24, 19, 45), Time(19, 15),
    'A tiny flying mammal that keeps the demo orchard free of mosquitoes.'),
  ('Cat', 4, 4.72, True, Date(1758, 1, 1), DateTime(2026, 8, 25, 7, 30), Time(5, 55),
    'A patient feline that supervises the demo keyboard.'),
  ('Dog', 12, 27.40, False, Date(1758, 1, 1), DateTime(2026, 8, 25, 17, 0), Time(6, 10),
    'A cheerful canine that retrieves sticks from the demo field.'),
  ('Elephant', 3, 4892.75, False, Date(1758, 1, 1), DateTime(2026, 8, 26, 14, 20), Time(5, 40),
    'A gentle proboscidean that waters the imaginary demo garden with its trunk.'),
  ('Fox', 7, 6.85, True, Date(1758, 1, 1), DateTime(2026, 8, 26, 21, 10), Time(20, 5),
    'A quick red canid that follows moonlit paths through the demo woods.'),
]


def _table(wide:bool=False) -> Table:
  'Return a demo table. If `wide`, add a column that is too wide to fit the page column.'
  head = [Th('Animal'), Th('Count', cl='num'), Th('Weight (kg)', cl='num'), Th('Nocturnal'),
    Th('Described', cl='isodate'), Th('Last fed', cl='isodate'), Th('Wakes at', cl='nowrap')]
  if wide: head.append(Th('Description', cl='nowrap'))
  table = Table()
  table.head(head)
  table.rows([
    Tr(Td(name), Td(f'{count:,}', cl='num'), Td(f'{weight:,.2f}', cl='num'), Td('Yes' if nocturnal else 'No'),
      Td(discovered.isoformat(), cl='isodate'), Td(dt_Ymd_IMp(last_fed), cl='isodate'),
      Td(dt_IMp(wakes_at), cl='nowrap'), *([Td(description, cl='nowrap')] if wide else []))
    for name, count, weight, nocturnal, discovered, last_fed, wakes_at, description in rows])
  return table


class DevTables(Endpoint):
  'Baseline styling of tables.'

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmlResponse:
    plain = _table().caption('Animals')

    collapsible = _table().caption('Animals')
    collapsible.append_class('collapsible')

    main = Main(
      H1('Tables'),
      P('A table shrinks to fit its content and takes no margin of its own;'
        ' the vertical spacing comes from the flow rule on its container.'),

      Section(_=[
        H2('Plain'),
        Div(cl='overflow-x-auto', _=plain),
        P(cl='muted', _=['Rows alternate shading. Cells marked ', Code('num'),
          ' are right-aligned; cells marked ', Code('isodate'), ' do not wrap.']),
      ]),

      Section(_=[
        H2('Collapsible'),
        P('A ', Code('collapsible'), ' table hides its body when the caption is clicked. This is wired up by ',
          Code('pithy.js'), '.'),
        Div(cl='overflow-x-auto', _=collapsible),
      ]),

      Section(_=[
        H2('Full width'),
        P('The ', Code('w100'), ' utility makes a table fill the page column.'),
        Div(cl='overflow-x-auto', _=_table().caption('Animals, full width').append_class('w100')),
      ]),

      Section(_=[
        H2('Too wide to fit'),
        P('A table that cannot be made narrower would otherwise widen the whole page. Wrapping it in a ',
          Code('overflow-x-auto'), ' div confines the overflow to the table.'),
        Div(cl='overflow-x-auto', _=_table(wide=True).caption('Animals, with descriptions')),
      ]),

      Section(_=[
        H2('Full bleed'),
        P('A ', Code('bleed'), ' div escapes the page column and spans the window, which gives a wide table more'
          ' room before it has to scroll. Combining it with ', Code('overflow-x-auto'),
          ' gives a table that uses the whole window and scrolls only when even that is not enough.'),
        Div(cl='bleed overflow-x-auto', _=_table(wide=True).caption('Animals, full bleed')),
      ]),
    )
    return dev_page(title='Tables', main=main,
      breadcrumbs=[('/', 'Home'), ('/tables', 'Tables')])
