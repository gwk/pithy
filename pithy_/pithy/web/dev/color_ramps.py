# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Gray ramps for measuring how a display renders tones near black and near the theme canvases.

The palette's background surfaces differ by small lightness steps.
Whether a step is visible depends on the display's black level and tone response, and on the surround that the eye adapts to.
Each block fixes a surround and shows neutral grays against it, so that a floor and a minimum visible step can be read per display.
Swatch values are computed here as 8-bit sRGB grays and labeled statically; nothing depends on the browser parsing colors.
'''

from math import cbrt

from ...html import A, Button, Code, Div, H1, H2, Main, P, Section, Span
from ..request import Request
from ..response import HtmlResponse
from .pages import dev_page


# The theme canvas lightnesses in OKLCH. These mirror `--bg` in pithy.css and must change with it.
canvas_l_dark = 0.20
canvas_l_light = 0.99

offset_deltas = (0.0125, 0.025, 0.0375, 0.05, 0.075, 0.10) # OKLCH L offsets from the canvas for the separated boxes.
staircase_steps = (0.0125, 0.025, 0.0375, 0.05) # OKLCH L step sizes; one staircase each.
staircase_len = 5


def srgb_decode(v:float) -> float:
  'The sRGB transfer function from an encoded component in 0-1 to linear light.'
  return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def srgb_encode(v:float) -> float:
  'The sRGB transfer function from linear light to an encoded component in 0-1.'
  return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def oklch_l_for_gray(v:int) -> float:
  'OKLCH lightness of an 8-bit sRGB gray. For neutrals the OKLab transform reduces to the cube root of linear light.'
  return cbrt(srgb_decode(v / 255))


def gray_for_oklch_l(l:float) -> int:
  'The 8-bit sRGB gray nearest to an OKLCH lightness.'
  return round(255 * srgb_encode(l ** 3))


def gray_hex(v:int) -> str:
  return f'#{v:02X}{v:02X}{v:02X}'


def swatch(v:int, note:str) -> Div:
  'A gray box labeled with its hex value and a note.'
  return Div(cl='ramp-swatch', _=[
    Div(cl='ramp-box', style=f'background-color:{gray_hex(v)}', aria_hidden='true'), Code(gray_hex(v)), Span(note)])


def strip(label:str, grays:list[int], *, abut:bool=False, relative_to:int|None=None) -> Div:
  '''
  A labeled row of swatches. `abut` removes the gaps so that neighbors share an edge.
  Notes show each gray's OKLCH L, or its signed L offset from the gray `relative_to`.
  '''
  def note(v:int) -> str:
    if relative_to is None: return f'L {oklch_l_for_gray(v):.3f}'
    return f'{oklch_l_for_gray(v) - oklch_l_for_gray(relative_to):+.3f}'
  return Div(cl='ramp-strip', _=[
    P(label),
    Div(cl=('ramp-swatches abut' if abut else 'ramp-swatches'), _=[swatch(v, note(v)) for v in grays])])


def block_head(title:str) -> Div:
  return Div(cl='ramp-head', _=[H2(title),
    Button('Full screen', type='button', onclick="this.closest('.ramp').requestFullscreen()")])


def floor_block() -> Section:
  'Grays on true black, for finding the darkest tone that a display separates from black.'
  # The lowest OKLCH steps all quantize to black, so duplicates are dropped.
  oklch_grays = sorted({gray_for_oklch_l(i * 0.025) for i in range(10)})
  return Section(cl='ramp ramp-dark', style='background-color:#000000', _=[
    block_head('Floor: grays on black'),
    P('The first box that separates from the surround is the floor. A canvas at or below the floor reads as black.'),
    strip('sRGB steps of 8.', list(range(0, 0x40, 0x08))),
    strip('OKLCH steps of 0.025, quantized to 8-bit sRGB.', oklch_grays),
  ])


def canvas_block(scheme:str, canvas_l:float, sign:int) -> Section:
  '''
  Grays on a theme canvas, stepping away from it in the direction `sign`, followed by the palette's current surfaces.
  The surround is the fixed canvas gray, which is what the eye adapts to on a page in that theme.
  '''
  canvas = gray_for_oklch_l(canvas_l)
  offsets = [gray_for_oklch_l(canvas_l + sign * d) for d in offset_deltas]
  staircases = [
    strip(f'Steps of {step}.', [gray_for_oklch_l(canvas_l + sign * step * k) for k in range(1, staircase_len + 1)], abut=True)
    for step in staircase_steps]
  return Section(cl=f'ramp ramp-{scheme}', style=f'background-color:{gray_hex(canvas)}', data_theme=scheme, _=[
    block_head(f'{scheme.title()} canvas: {gray_hex(canvas)}, L {oklch_l_for_gray(canvas):.3f}'),
    P('Separated boxes at increasing offsets from the canvas. '
      'The first visible box is the minimum step for a surface that sits directly on the canvas.'),
    strip('Offset from the canvas.', offsets, relative_to=canvas),
    P('Staircases with one step size each. The first box is one step from the canvas and neighbors share an edge. '
      'The smallest step size at which every edge is visible is the minimum step between adjacent surfaces.'),
    Div(cl='ramp-staircases', _=staircases),
    P('The current palette: ', Code('--bg-subtle'), ' with a nested ', Code('--bg-distinct'), ', and ',
      Code('--bg-distinct'), ' directly on the canvas.'),
    Div(cl='ramp-surfaces', _=[
      Div(cl='ramp-surface subtle', _=[Code('--bg-subtle'), Div(cl='ramp-surface distinct', _=Code('--bg-distinct'))]),
      Div(cl='ramp-surface distinct', _=Code('--bg-distinct')),
    ]),
  ])


def dev_color_ramps(request:Request) -> HtmlResponse:
  return dev_page(title='Color ramps', main=Main(
    H1('Color ramps'),
    P('Use these ramps to measure what a display can separate near black and near each theme canvas. '
      'The results set the thresholds for the surface step check on the ', A('colors page', href='/colors'), '.'),
    P('View each block in full screen so that its surround fills the display, and give your eyes a few seconds to adapt. '
      'Compare displays at the brightness you normally use. All swatches are neutral grays; any tint comes from the display.'),
    floor_block(),
    canvas_block('dark', canvas_l_dark, 1),
    canvas_block('light', canvas_l_light, -1),
    cl='ramp-page',
  ), breadcrumbs=[('/', 'Home'), ('/colors', 'Colors'), ('/colors/ramps', 'Ramps')],
    css_paths=['/static/dev/color_ramps.css'])
