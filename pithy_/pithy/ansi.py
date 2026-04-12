# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
ANSI Control Sequences.


ANSI Select Graphics Rendition (SGR) and other console control sequences.

Prebaked control sequences are provided. These are strings that can be printed directly to stdout, e.g. RST, BOLD, TXT_R, BG_R.

Additionally, compound sequences can be constructed using the `ctrl_seq` and `sgr` functions.
For a given prebaked command, e.g. `RST` (reset), a corresponding `cRST` is provided that is the raw numeric code.
Numeric codes that do not have a prebaked equivalent are not prefixed, e.g. the named 8-bit colors like R, G, B, etc.

Generally the names are composed of words like the following:

RST: reset

BOLD: bold
ULINE: underline
BLINK: blink
INVERT: invert
TXT: color text
BG: color background

K: black
W: white
D: dim gray
R: red
G: green
Y: yellow
B: blue
M: magenta
C: cyan
L: light gray


# Incomplete

Additional, unimplemented commands are documented below.
As these are implemented, the command chars should be added to the cs_re pattern.

CSI n A CUU: Cursor Up Moves the cursor n (default 1) cells in the given direction.
  If the cursor is already at the edge of the screen, this has no effect.

CSI n B: Cursor Down
CSI n C: Cursor Forward
CSI n D: Cursor Back
CSI n E: Moves cursor to beginning of the line n (default 1) lines down.
CSI n F: Moves cursor to beginning of the line n (default 1) lines up.

CSI n G: Moves the cursor to column n.

CSI n S: Scroll whole page up by n (default 1) lines. New lines are added at the bottom. (not ANSI.SYS)
CSI n T: Scroll whole page down by n (default 1) lines. New lines are added at the top. (not ANSI.SYS)

'''

import re as _re
from sys import stderr, stdout
from typing import Any, Sequence


is_err_tty = stderr.isatty()
is_out_tty = stdout.isatty()

# Use these with `and` expressions to omit sgr for non-tty output, e.g. `TTY_OUT and sgr(...)`.
TTY_ERR = '!TTY_ERR' if is_err_tty else ''
TTY_OUT = '!TTY_OUT' if is_out_tty else ''

# ANSI control sequence indicator.
CSI = '\x1B['

# regex for detecting control sequences in strings.
# TODO: replace .*? wildcard with stricter character set.
ctrl_seq_re = _re.compile(r'\x1B\[.*?[hHJKlmsu]')


def ctrl_seq(c:str, *args:int|str) -> str:
  'Format a control sequence string for command character/terminator `c` and arguments.'
  return f'{CSI}{";".join(_ctrl_seq_arg(a) for a in args)}{c}'


def _ctrl_seq_arg(arg:int|str) -> str:
  'Format an argument for a control sequence.'
  if isinstance(arg, int):
    return str(arg)
  if isinstance(arg, str):
    assert arg[0] > ' ', repr(arg) # Ensure that we are not passing a prebaked control sequence as an argument.
    return arg
  raise TypeError(arg)


def strip_ctrl_seq(text: str) -> str:
  'Strip control sequences from a string.'
  return ctrl_seq_re.sub('', text)


def len_strip_ctrl_seq(s: str) -> int:
  'Calculate the length of string if control sequences were stripped.'
  l = len(s)
  for m in ctrl_seq_re.finditer(s):
    l -= m.end() - m.start()
  return l


def sgr(*seq:Any) -> str:
  'Select Graphic Rendition control sequence string.'
  return ctrl_seq('m', *seq)


def sgr_out(*seq:Any) -> str:
  'Return an SGR string for tty stdout, or a blank line for other stdout.'
  return ctrl_seq('m', *seq) if is_out_tty else ''

def sgr_err(*seq:Any) -> str:
  'Return an SGR string for tty stderr, or a blank line for other stderr.'
  return ctrl_seq('m', *seq) if is_err_tty else ''


def _tty_out_seqs(seqs:tuple[str,...]) -> Sequence[str]:
  return seqs if is_out_tty else tuple('' for _ in seqs)

def _tty_err_seqs(seqs:tuple[str,...]) -> Sequence[str]:
  return seqs if is_err_tty else tuple('' for _ in seqs)


# Reset commands.

cRST = 0
RST = sgr() # The empty sgr sequence is equivalent to sgr(0).
RST_ERR = (TTY_ERR and RST)
RST_OUT = (TTY_OUT and RST)

cRST_BOLD, cRST_ULINE, cRST_BLINK, cRST_INVERT, cRST_TXT, cRST_BG = reset_codes = (22, 24, 25, 27, 39, 49)
RST_BOLD, RST_ULINE, RST_BLINK, RST_INVERT, RST_TXT, RST_BG = reset_seqs = tuple(sgr(c) for c in reset_codes)
RST_BOLD_OUT, RST_ULINE_OUT, RST_BLINK_OUT, RST_INVERT_OUT, RST_TXT_OUT, RST_BG_OUT = _tty_out_seqs(reset_seqs)
RST_BOLD_ERR, RST_ULINE_ERR, RST_BLINK_ERR, RST_INVERT_ERR, RST_TXT_ERR, RST_BG_ERR = _tty_err_seqs(reset_seqs)

# Effect command strings.
cBOLD, cULINE, cBLINK, cINVERT = effect_codes = (1, 4, 5, 7)
BOLD, ULINE, BLINK, INVERT = effect_seqs = tuple(sgr(c) for c in effect_codes)
BOLD_OUT, ULINE_OUT, BLINK_OUT, INVERT_OUT = _tty_out_seqs(effect_seqs)
BOLD_ERR, ULINE_ERR, BLINK_ERR, INVERT_ERR = _tty_err_seqs(effect_seqs)

# 3-bit named colors.
# Note that black and white acronyms are suffixed with T,
# because we prefer to use true black and white from xterm-256color, defined below.

# Text colors: black, red, green, yellow, blue, magenta, cyan, white.
cTXT_KT, cTXT_R, cTXT_G, cTXT_Y, cTXT_B, cTXT_M, cTXT_C, cTXT_WT = txt_color3_codes = range(30, 38)
TXT_KT, TXT_R, TXT_G, TXT_Y, TXT_B, TXT_M, TXT_C, TXT_WT = txt_color3_seqs = tuple(sgr(i) for i in txt_color3_codes)
TXT_KT_OUT, TXT_R_OUT, TXT_G_OUT, TXT_Y_OUT, TXT_B_OUT, TXT_M_OUT, TXT_C_OUT, TXT_WT_OUT = _tty_out_seqs(txt_color3_seqs)
TXT_KT_ERR, TXT_R_ERR, TXT_G_ERR, TXT_Y_ERR, TXT_B_ERR, TXT_M_ERR, TXT_C_ERR, TXT_WT_ERR = _tty_err_seqs(txt_color3_seqs)

# Background colors: black, red, green, yellow, blue, magenta, cyan, white.
cBG_KT, cBG_R, cBG_G, cBG_Y, cBG_B, cBG_M, cBG_C, cBG_WT = bg_color3_codes = range(40, 48)
BG_KT, BG_R, BG_G, BG_Y, BG_B, BG_M, BG_C, BG_WT = bg_color3_seqs = tuple(sgr(i) for i in bg_color3_codes)
BG_KT_OUT, BG_R_OUT, BG_G_OUT, BG_Y_OUT, BG_B_OUT, BG_M_OUT, BG_C_OUT, BG_WT_OUT = _tty_out_seqs(bg_color3_seqs)
BG_KT_ERR, BG_R_ERR, BG_G_ERR, BG_Y_ERR, BG_B_ERR, BG_M_ERR, BG_C_ERR, BG_WT_ERR = _tty_err_seqs(bg_color3_seqs)


# xterm-256 sequence initiators; these should be followed by a single color index.
# both text and background can be specified in a single sgr call.
TXT = '38;5'
BG = '48;5'

# RGB6 color cube: 6x6x6, from black to white.
K = 16  # black.
W = 231 # white.

# Grayscale: the 24 palette values have a suggested 8 bit grayscale range of [8, 238].
middle_gray_codes = range(232, 256)

# Dark, neutral and light gray names.
KD = W + 4
D = W + 7
DN = W + 10
N = W + 13
NL = W + 16
L = W + 19
LW = W + 22

named_gray_codes = (K, KD, D, DN, N, NL, L, LW, W)


def gray26(n:int) -> int:
  assert 0 <= n < 26
  if n == 0: return K
  if n == 25: return W
  return W + n


def rgb6(r:int, g:int, b:int) -> int:
  'index RGB triples into the 256-color palette (returns 16 for black, 231 for white).'
  assert 0 <= r < 6
  assert 0 <= g < 6
  assert 0 <= b < 6
  return (((r * 6) + g) * 6) + b + 16


TXT_K, TXT_KD, TXT_D, TXT_DN, TXT_N, TXT_NL, TXT_L, TXT_LW, TXT_W = txt_gray_seqs = tuple(sgr(TXT, code) for code in named_gray_codes)
TXT_K_OUT, TXT_KD_OUT, TXT_D_OUT, TXT_DN_OUT, TXT_N_OUT, TXT_NL_OUT, TXT_L_OUT, TXT_LW_OUT, TXT_W_OUT = _tty_out_seqs(txt_gray_seqs)
TXT_K_ERR, TXT_KD_ERR, TXT_D_ERR, TXT_DN_ERR, TXT_N_ERR, TXT_NL_ERR, TXT_L_ERR, TXT_LW_ERR, TXT_W_ERR = _tty_err_seqs(txt_gray_seqs)

BG_K, BG_KD, BG_D, BG_DN, BG_N, BG_NL, BG_L, BG_LW, BG_W = bg_gray_seqs = tuple(sgr(BG, code) for code in named_gray_codes)
BG_K_OUT, BG_KD_OUT, BG_D_OUT, BG_DN_OUT, BG_N_OUT, BG_NL_OUT, BG_L_OUT, BG_LW_OUT, BG_W_OUT = _tty_out_seqs(bg_gray_seqs)
BG_K_ERR, BG_KD_ERR, BG_D_ERR, BG_DN_ERR, BG_N_ERR, BG_NL_ERR, BG_L_ERR, BG_LW_ERR, BG_W_ERR = _tty_err_seqs(bg_gray_seqs)


def cursor_pos(x:int, y:int) -> str:
  '''
  Position the cursor.
  Supposedly the 'f' suffix does the same thing.
  x and y parameters are zero based.
  '''
  return ctrl_seq('H', y + 1, x + 1)


ERASE_LINE_F, ERASE_LINE_B, ERASE_LINE = erase_line_seqs = tuple(ctrl_seq('K', i) for i in range(3))
ERASE_LINE_F_OUT, ERASE_LINE_B_OUT, ERASE_LINE_OUT = _tty_out_seqs(erase_line_seqs)
ERASE_LINE_F_ERR, ERASE_LINE_B_ERR, ERASE_LINE_ERR = _tty_err_seqs(erase_line_seqs)

CLEAR_SCREEN_F, CLEAR_SCREEN_B, CLEAR_SCREEN = (ctrl_seq('J', i) for i in range(3))

FILL = ERASE_LINE_F + RST # Erase-line fills the background color to the end of line.
FILL_ERR = (TTY_ERR and FILL)
FILL_OUT = (TTY_OUT and FILL)

CURSOR_SAVE     = ctrl_seq('s')
CURSOR_RESTORE  = ctrl_seq('u')
CURSOR_HIDE     = ctrl_seq('?25l')
CURSOR_SHOW     = ctrl_seq('?25h')
CURSOR_REPORT   = ctrl_seq('6n') # '\x1B[{x};{y}R' appears as if typed into the terminal.

ALT_ENTER = ctrl_seq('?1049h')
ALT_EXIT  = ctrl_seq('?1049l')


def term_pos(x: int, y: int) -> str:
  '''
  position the cursor using 0-indexed x, y integer coordinates.
  (supposedly the 'f' suffix does the same thing).
  '''
  return ctrl_seq('H', y + 1, x + 1)


def show_cursor(show_cursor: Any) -> str:
  return CURSOR_SHOW if show_cursor else CURSOR_HIDE


def sanitize_for_console(*text:str, allow_sgr:bool=False, allow_tab:bool=False, escape:str=INVERT, unescape:str=RST_INVERT
 ) -> list[str]:
  sanitized = []
  for t in text:
    for m in _sanitize_re.finditer(t):
      s = m[0]
      k = m.lastgroup
      if k == 'vis' or (allow_sgr and k == 'sgr') or (allow_tab and k == 'tab'):
        sanitized.append(s)
      else: # Sanitize.
        sanitized.append(f'{escape}{escape_char_for_console(s)}{unescape}')
  return sanitized


_sanitize_re = _re.compile(r'''(?x)
  (?P<vis> [\n -~]+ )
| (?P<sgr> \x1b (?= \[ [\d;]* m ))
| (?P<tab> \t )
| .
''')


def escape_char_for_console(char:str) -> str:
  'Escape characters using ploy syntax.'
  return escape_reprs.get(char) or f'\\{ord(char):x};'

escape_reprs = {
  '\r': '\\r',
  '\t': '\\t',
  '\v': '\\v',
}
