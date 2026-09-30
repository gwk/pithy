# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Developer reference for the semantic palette and its component uses in both color schemes.

The page renders the same components inside a light and a dark themed subtree,
then colors.js resolves every color variable to sRGB and checks the declared foreground/background pairs with APCA.
It also checks that adjacent background surfaces and table shades stay separated in OKLCH lightness,
because small steps between dark tones are the first distinctions lost on a dim display or under glare.
The stylesheet records the tuned values; nothing depends on the checks at runtime.
'''

from collections.abc import Callable

from ...html import (A, Button, Code, Dialog, Div, H1, H2, H3, HtmlNode, Input, Label, Main, P, Pre, Section, Span, Table, Td,
  Th, Tr)
from ..request import Request
from ..response import HtmlResponse
from .pages import dev_page


type Scheme = str


def dev_colors(request:Request) -> HtmlResponse:
  return dev_page(title='Colors',
    breadcrumbs=[('/', 'Home'), ('/colors', 'Colors')],
    css_paths=['/static/dev/colors.css'],
    js_paths=['/static/dev/colors.js'],
    main=Main(_=[

    H1('Colors', id='colors'),
    Div(cl='color-intro', _=[
      Section(
        H2('Using the palette'),
        P(Code('pithy.css'), ' provides semantic CSS variables for light and dark themes. '
          'Use these variables in site styles, for example ', Code('color: var(--fg-muted)'), '.'),
        P('Neutral colors are OKLab mixes of the canvas ', Code('--bg'), ' and primary text ', Code('--fg'), '. '
          'Accent and error colors keep their hues across themes, with lightness and chroma tuned for each.'),
        P('Use ', Code('--bg'), ' for the page and editable fields, ', Code('--bg-subtle'),
          ' for page headers, navigation bars, footers and groups of related settings or filters, and ',
          Code('--bg-distinct'), ' for panels and overlays. '
          'Surfaces darken in light mode and lighten in dark mode to provide increasing separation.'),
        P(Code('.subtle'), ' and ', Code('.distinct'), ' set only the background to ',
          Code('--bg-subtle'), ' and ', Code('--bg-distinct'), ', respectively. '
          'They leave text color, borders, padding and layout unchanged.'),
        P('Use ', Code('class="panel"'), ' for a bordered container on ', Code('--bg-distinct'), ', or ',
          Code('class="panel subtle"'), ' for the same container on ', Code('--bg-subtle'), '. '
          'Choose subtle for quiet grouping and distinct when a result, summary or overlay should stand out.'),
        P('Local decorations use translucent ', Code('currentColor'), ' tints: ', Code('--tint-subtle'),
          ', ', Code('--tint-distinct'), ' and ', Code('--tint-active'), ' for fills; ', Code('--tint-border'),
          ' and ', Code('--tint-border-strong'), ' for edges. Code, buttons and table stripes adapt to their surroundings. '
          'Nested tints accumulate. Panels and overlays use opaque surfaces with the theme foreground.'),
      ),
      Section(
        H2('Theme configuration'),
        P('The theme follows the system preference by default. Set ', Code('data-theme="light"'), ' or ', Code('data-theme="dark"'),
          ' on ', Code('<html>'), ' to choose a theme for the site, or on a container to theme its contents.'),
        P('Load site styles after ', Code('pithy.css'), '. Override ', Code('--bg'), ', ', Code('--fg'), ', ',
          Code('--accent-base'), ' and ', Code('--error-base'), ' on ', Code(':root'), ' to customize the palette. '
          'Use ', Code('light-dark(light-value, dark-value)'), ' for theme-specific colors. '
          'Check text, borders and control states in both themes after changes.'),
      ),
    ]),

    comparison_section('Complete palette', columns=palette_sample, intro=[
      P('Every semantic variable, with its resolved sRGB value and computed color in each theme.')]),

    comparison_section('Surface steps', columns=surface_steps_sample, cl='color-steps', intro=[
      P('Adjacent background surfaces and table shades need a minimum separation that the foreground checks do not measure. '
        'Each pair must differ by at least ', Code(f'{surface_min_delta_l:.2f}'), ' in OKLCH lightness; pairs below that are marked. '
        'Table shades are translucent tints, measured after compositing over the canvas.'),
      P('The threshold comes from measurements on the ', A('color ramps page', href='/colors/ramps'), '. '
        'Dark steps look flatter on a dim display and are lost under glare on a glossy one. '
        'No practical step size survives strong glare; raise the display brightness or use the light theme there.')]),

    comparison_section('Foreground and background pairs', columns=contrast_sample, cl='color-pairs', intro=[
      P('The tables measure selected color pairs with APCA (Accessible Perceptual Contrast Algorithm), version ',
        Span(cl='apca-version'), '. Targets use the magnitude of Lc; missed targets are marked. '
        'Readability also depends on text size and weight.')]),

    comparison_section('Backgrounds and their uses', columns=surfaces_sample, intro=[
      P('These samples show the same text and controls on each background. '
        'The background variables set only a color. Only the page-background sample has a boundary border. '
        'The nested examples below demonstrate panel classes with padding, borders and rounded corners.')]),

    comparison_section('Nested surfaces', columns=nested_sample, intro=[
      P('Panel classes add padding, a border and rounded corners to a background surface. Panels nest with increasing emphasis.')]),

    Section(
      H2('Local decoration'),
      P('These examples set only their background and text colors. Tint percentages are shared by both themes.'),
      Div(cl='color-decorations', _=[
        decoration_sample('Gray surface', cl='color-decoration-gray'),
        decoration_sample('Colored surface', cl='color-decoration-colored')])),

    comparison_section('Controls and states', columns=controls_sample, intro=[
      P('Hover, press, and tab through controls to inspect their states.')]),

    comparison_section('Tables', columns=tables_sample, intro=[
      P('Striped rows use translucent tints over the canvas; a subheading row groups the rows that follow.')]),

    comparison_section('Overlays', columns=overlays_sample, intro=[
      P('A modal shows a distinct pane with a strong border over a dimmed, blurred page.')]),

  ]))


# Semantic color variables and their uses, in the order shown in the palette listing.
palette = (
  ('fg', 'Primary text'),
  ('fg-muted', 'Secondary text on theme surfaces'),
  ('fg-error', 'Errors'),
  ('bg', 'Page canvas and editable fields'),
  ('bg-subtle', 'Headers, navigation, footers and related settings or filters'),
  ('bg-distinct', 'Panels, overlays and emphasized surfaces'),
  ('border', 'Panels and input borders'),
  ('border-strong', 'Modal borders'),
  ('accent', 'Links, focus rings and native selection'),
  ('tint-subtle', 'Code, buttons and table stripes'),
  ('tint-distinct', 'Hover states and table headings'),
  ('tint-active', 'Pressed buttons'),
  ('tint-border', 'Code borders and dividers'),
  ('tint-border-strong', 'Button borders and table rules'),
  ('tr-subheading-background-color', 'Table headings'),
  ('tr-even-background-color', 'Even table rows'),
  ('tr-odd-background-color', 'Odd table rows'),
)

# APCA Lc targets by role. See https://github.com/Myndex/SAPC-APCA/blob/master/documentation/APCA_in_a_Nutshell.md.
lc_body = 75 # Body text.
lc_secondary = 60 # Muted text, and text on panels.
lc_ui = 45 # Large UI text, and error text: a red that clears the higher targets on a dark canvas is pastel.
lc_non_text = 30 # Borders and other essential non-text elements.
lc_visible = 15 # The minimum for any visible difference.

# Foreground/background variable pairs to check, with the target |Lc| or None for informational surface steps.
contrast_pairs:tuple[tuple[str,str,int|None],...] = (
  ('fg', 'bg', lc_body),
  ('fg', 'bg-subtle', lc_body),
  ('fg', 'bg-distinct', lc_body),
  ('fg-muted', 'bg', lc_secondary),
  ('fg-muted', 'bg-subtle', lc_secondary),
  ('fg-muted', 'bg-distinct', lc_secondary),
  ('fg-error', 'bg', lc_ui),
  ('fg-error', 'bg-subtle', lc_ui),
  ('fg-error', 'bg-distinct', lc_ui),
  ('accent', 'bg', lc_body),
  ('accent', 'bg-subtle', lc_body),
  ('accent', 'bg-distinct', lc_secondary),
  ('border-strong', 'bg', lc_non_text),
  ('border-strong', 'bg-subtle', lc_non_text),
  ('border', 'bg', lc_visible),
  ('border', 'bg-distinct', lc_visible),
  ('bg-subtle', 'bg', None),
  ('bg-distinct', 'bg', None),
  ('bg-distinct', 'bg-subtle', None),
)

# Adjacent tone pairs checked for a minimum OKLCH lightness difference, as (lower variable, upper variable, description).
# The table shades are translucent tints; colors.js composites them over the canvas before measuring.
# A description of None shows the variable names.
surface_steps:tuple[tuple[str,str,str|None],...] = (
  ('bg', 'bg-subtle', None),
  ('bg-subtle', 'bg-distinct', None),
  ('bg', 'tr-odd-background-color', 'Odd table row over canvas'),
  ('tr-odd-background-color', 'tr-subheading-background-color', 'Table heading over odd row'),
)

# Minimum OKLCH lightness difference between adjacent tones, on the 0-1 scale.
# Measured with the color ramps page on a glossy IPS display: a step of 0.013 was borderline and 0.025 was clearly distinct.
surface_min_delta_l = 0.02


def comparison_section(title:str, *, intro:list[HtmlNode], columns:Callable[[Scheme],list[HtmlNode]], cl:str='') -> Section:
  '''
  A section comparing the themes: a heading panel above light and dark columns, all on a neutral gray canvas.
  The gray surrounds both columns so that neither looks like the page's own mode.
  `columns` builds the children of one themed column; `cl` is added to each column for colors.js to find it.
  '''
  return Section(cl='color-section', _=[
    Div(cl='panel flow', _=[H2(title), *intro]),
    Div(cl='color-comparison', _=[scheme_section(scheme, title.lower(), columns(scheme), cl=cl) for scheme in ('light', 'dark')]),
  ])


def scheme_section(scheme:Scheme, label:str, children:list[HtmlNode], *, cl:str='') -> Section:
  '''
  A themed column of a `.color-comparison` grid.
  The section is a subgrid that spans one shared row per child, so that the light and dark columns stay aligned
  when corresponding children differ in height. Both columns must have the same number of children.
  '''
  return Section(cl=f'color-scheme {cl}'.rstrip(), data_theme=scheme, aria_label=f'{scheme.title()} {label}',
    style=f'grid-row:span {len(children)}', _=children)


def palette_sample(scheme:Scheme) -> list[HtmlNode]:
  return [
    Div(cl='color-palette', _=[
      Div(cl='color-token', _=[
        Span(cl='color-chip', style=f'background-color:var(--{token})', aria_hidden='true'),
        Div(
          Div(Code(f'--{token}'), Code(cl='color-value', data_color_token=token), cl='color-token-heading'),
          P(description, cl='muted')),
      ]) for token, description in palette
    ]),
  ]


def surface_steps_sample(scheme:Scheme) -> list[HtmlNode]:
  return [
    P(cl='color-summary', _='Resolving colors requires JavaScript.'),
    surface_steps_table(),
  ]


def contrast_sample(scheme:Scheme) -> list[HtmlNode]:
  return [
    P(cl='color-summary', _='Resolving colors requires JavaScript.'),
    contrast_table(),
  ]


def surfaces_sample(scheme:Scheme) -> list[HtmlNode]:
  return [Div(cl='color-surfaces', _=[surface_sample(token) for token in ('bg', 'bg-subtle', 'bg-distinct')])]


def nested_sample(scheme:Scheme) -> list[HtmlNode]:
  return [
    Div(cl='panel subtle flow', _=[
      P(Code('.panel.subtle'), ' groups related content on ', Code('--bg-subtle'), '.'),
      P('A nested ', Code('.panel'), ' gives a result or summary stronger emphasis:'),
      Div(cl='panel flow', _=[
        P(Code('.panel'), ' uses ', Code('--bg-distinct'), ' and ', Code('--border'), '.'),
        Pre('Code block inside a panel.'),
      ]),
    ]),
  ]


def controls_sample(scheme:Scheme) -> list[HtmlNode]:
  return [
    Div(cl='flow flow-tight', _=[
      Div(cl='form_grid', _=[
        Label('Project name', for_=f'colors-input-{scheme}'),
        Input(id=f'colors-input-{scheme}', value='Field notes'),
        Label('Unavailable field', for_=f'colors-disabled-{scheme}'),
        Input(id=f'colors-disabled-{scheme}', value='Read only while syncing', disabled=True),
      ]),
      Div(Label(Input(type='checkbox', checked=True), 'Checkbox')),
      Div(cl='color-actions', _=[Button('Save', type='button'), Button('Disabled', type='button', disabled=True),
        Button('Delete', type='button', cl='dangerous')]),
      P(cl='error-red', _='Example validation error: enter a project name.'),
      P(cl='muted', _='Muted guidance text.'),
    ]),
  ]


def tables_sample(scheme:Scheme) -> list[HtmlNode]:
  return [
    Table(cl='w100').head([Th('Surface'), Th('Use')]).rows([
      Tr(Td('Odd row'), Td('Striped data')),
      Tr(Td('Even row'), Td('Striped data')),
      Tr(cl='subheading', _=[Th('Subheading', colspan=2)]),
      Tr(Td('Even row'), Td('Grouped data')),
    ]),
  ]


def overlays_sample(scheme:Scheme) -> list[HtmlNode]:
  modal_id = f'colors-modal-{scheme}'
  return [
    Div(_=[ # The modal shares a wrapper with its button, so that every child of the section is one grid row.
      Div(cl='color-actions', _=[
        Button('Open modal', type='button', onclick=f"document.getElementById('{modal_id}').showModal()"),
      ]),
      Dialog(id=modal_id, cl='modal', aria_label=f'{scheme.title()} modal', _=[
        Div(cl='pane flow', _=[H3(f'{scheme.title()} modal'), P('Distinct pane, strong border and modal backdrop.'),
          Button('Close', type='button', onclick=f"document.getElementById('{modal_id}').close()")]),
      ]),
    ]),
  ]


def surface_sample(token:str) -> Div:
  description = {
    'bg': 'Page canvas and editable fields. The border here marks the sample boundary.',
    'bg-subtle': 'Gentle separation for headers, navigation, footers and groups of related settings or filters.',
    'bg-distinct': 'Stronger separation for result panels, summaries and modal panes.',
  }[token]
  background_class = token.removeprefix('bg-') if token != 'bg' else ''
  return Div(cl=f'color-surface flow flow-tight {background_class}', data_surface=token,
    style=('background-color:var(--bg)' if token == 'bg' else ''), _=[
    Code(f'--{token}'),
    P(description),
    P('Primary text ', Span('and muted text.', cl='muted')),
    P(A('Example link', href='#colors'), ' ', Span('Error message.', cl='error-red')),
    Pre('Code block on this surface.'),
    Div(cl='color-actions', _=[Button('Button', type='button'), Button('Disabled', type='button', disabled=True)]),
    Div(cl='color-border', _=Code('--border')),
    Div(cl='color-border color-border-strong', _=Code('--border-strong')),
  ])


def decoration_sample(label:str, *, cl:str='') -> Div:
  'The same local decorations on a custom surface, without palette overrides.'
  return Div(cl=f'color-decoration flow {cl}', _=[
    P(label, ': ', Code('inline code'), ' uses the surrounding text color.'),
    Pre(Code('Code block with the same tint.')),
    Div(cl='color-actions', _=[Button('Button', type='button'), Button('Disabled', type='button', disabled=True)]),
    Table(cl='w100').head([Th('Table heading'), Th('Value')]).rows([
      Tr(Td('Striped row'), Td('One')), Tr(Td('Unshaded row'), Td('Two'))]),
  ])


def pair_sample(fg:str, bg:str) -> Span:
  'A swatch showing `fg` over `bg`: text for text colors, an edge for borders, and an inset square for surfaces.'
  if fg.startswith('border'):
    return Span(cl='color-sample color-sample-border', aria_hidden='true',
      style=f'background-color:var(--{bg});border-color:var(--{fg})')
  if fg.startswith('bg'):
    return Span(cl='color-sample', aria_hidden='true', style=f'background-color:var(--{bg})',
      _=Span(cl='color-sample-inset', style=f'background-color:var(--{fg})'))
  return Span('Ag', cl='color-sample', aria_hidden='true', style=f'color:var(--{fg});background-color:var(--{bg})')


def contrast_table() -> Table:
  'The pair table skeleton; colors.js fills the resolved values and Lc, and marks each row as pass or fail.'
  rows = []
  for fg, bg, target in contrast_pairs:
    rows.append(Tr(data_fg=fg, data_bg=bg, data_target=('' if target is None else str(target)), _=[
      Td(pair_sample(fg, bg)),
      Td(Code(f'--{fg}'), Span(' on ', cl='muted'), Code(f'--{bg}')),
      Td(Code(cl='color-fg-value')),
      Td(Code(cl='color-bg-value')),
      Td(Span(cl='color-lc'), cl='num'),
      Td('' if target is None else str(target), cl='num'),
    ]))
  return Table(cl='w100 color-contrast').head([Th(''), Th('Pair'), Th('Foreground'), Th('Background'), Th('Lc'),
    Th('Target')]).rows(rows)


def step_sample(lower:str, upper:str) -> Span:
  'A swatch showing `lower` and `upper` side by side over the canvas, so that a translucent tint is composited as it is in use.'
  return Span(cl='color-sample color-sample-split', aria_hidden='true', style='background-color:var(--bg)', _=[
    Span(style=f'background-color:var(--{lower})'), Span(style=f'background-color:var(--{upper})')])


def surface_steps_table() -> Table:
  'The adjacent tone pair table skeleton; colors.js fills the resolved values, OKLCH L and delta L.'
  rows = []
  for lower, upper, description in surface_steps:
    pair:list[HtmlNode|str] = [description] if description else [
      Code(f'--{upper}'), Span(' over ', cl='muted'), Code(f'--{lower}')]
    rows.append(Tr(data_lower=lower, data_upper=upper, _=[
      Td(step_sample(lower, upper)),
      Td(_=pair, title=f'--{upper} over --{lower}'),
      Td(Code(cl='color-lower-value')),
      Td(Span(cl='color-lower-l'), cl='num'),
      Td(Code(cl='color-upper-value')),
      Td(Span(cl='color-upper-l'), cl='num'),
      Td(Span(cl='color-metric color-delta-l'), cl='num'),
    ]))
  return Table(cl='w100 color-contrast color-surface-steps', data_min_delta_l=str(surface_min_delta_l)).head([
    Th(''), Th('Pair'), Th('Lower'), Th('L'), Th('Upper'), Th('L'), Th('Delta L')]).rows(rows)
