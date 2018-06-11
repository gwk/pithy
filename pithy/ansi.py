# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
ANSI Control Sequences.


ANSI Select Graphics Rendition (SGR) sequences.

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


Incomplete

Additional, unimplemented commands are documented below.
As these are implemented, the command chars should be added to the cs_re pattern.

CSI n A CUU – Cursor Up Moves the cursor n (default 1) cells in the given direction.
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
from typing import Any

is_err_tty = stderr.isatty()
is_out_tty = stdout.isatty()


# ANSI control sequence indicator.
CSI = '\x1B['

# regex for detecting control sequences in strings.
# TODO: replace .*? wildcard with stricter character set.
ansi_ctrl_seq_re = _re.compile(r'\x1B\[.*?[hHJKlmsu]')


def ansi_ctrl_seq(c:str, *args:Any, on:bool=True) -> str:
  'Format a control sequence string for command character `c` and arguments.'
  return '{}{}{}'.format(CSI, ';'.join(str(a) for a in args), c) if on else ''


def strip_ansi_ctrl_seq(text: str) -> str:
  'Strip control sequences from a string.'
  return ansi_ctrl_seq_re.sub('', text)


def len_strip_ansi_ctrl_seq(s: str) -> int:
  'Calculate the length of string if control sequences were stripped.'
  l = len(s)
  for m in ansi_ctrl_seq_re.finditer(s):
    l -= m.end() - m.start()
  return l


def ansi_sgr(*seq:Any, on:bool=True) -> str:
  'Select Graphic Rendition control sequence string.'
  return ansi_ctrl_seq('m', *seq, on=on)


# reset command strings.
( RST, RST_ERR, RST_OUT,
  RST_BOLD, RST_BOLD_ERR, RST_BOLD_OUT,
  RST_ULINE, RST_ULINE_ERR, RST_ULINE_OUT,
  RST_BLINK, RST_BLINK_ERR, RST_BLINK_OUT,
  RST_INVERT, RST_INVERT_ERR, RST_INVERT_OUT,
  RST_TXT, RST_TXT_ERR, RST_TXT_OUT,
  RST_BG, RST_BG_ERR, RST_BG_OUT,
) = (ansi_sgr(i, on=on)
  for i in (0, 22, 24, 25, 27, 39, 49)
  for on in (True, is_err_tty, is_out_tty))

# effect command strings.
( BOLD, BOLD_ERR, BOLD_OUT,
  ULINE, ULINE_ERR, ULINE_OUT,
  BLINK, BLINK_ERR, BLINK_OUT,
  INVERT, INVERT_ERR, INVERT_OUT
) = (ansi_sgr(i, on=on)
  for i in (1, 4, 5, 7)
  for on in (True, is_err_tty, is_out_tty))

# color text: dark gray, red, green, yellow, blue, magenta, cyan, light gray.
ansi_txt_primary_indices = range(30, 38)
ansi_txt_primaries = tuple(ansi_sgr(i) for i in ansi_txt_primary_indices)
TXT_D, TXT_R, TXT_G, TXT_Y, TXT_B, TXT_M, TXT_C, TXT_L = ansi_txt_primaries

TXT_D_ERR, TXT_R_ERR, TXT_G_ERR, TXT_Y_ERR, TXT_B_ERR, TXT_M_ERR, TXT_C_ERR, TXT_L_ERR = (
  (c if is_err_tty else '') for c in ansi_txt_primaries)

TXT_D_OUT, TXT_R_OUT, TXT_G_OUT, TXT_Y_OUT, TXT_B_OUT, TXT_M_OUT, TXT_C_OUT, TXT_L_OUT = (
  (c if is_out_tty else '') for c in ansi_txt_primaries)


# color background: dark gray, red, green, yellow, blue, magenta, cyan, light gray.
ansi_bg_primary_indices = range(40, 48)
ansi_bg_primaries = tuple(ansi_sgr(i) for i in ansi_bg_primary_indices)
BG_D, BG_R, BG_G, BG_Y, BG_B, BG_M, BG_C, BG_L = ansi_bg_primaries

BG_D_ERR, BG_R_ERR, BG_G_ERR, BG_Y_ERR, BG_B_ERR, BG_M_ERR, BG_C_ERR, BG_L_ERR = (
  (c if is_err_tty else '') for c in  ansi_bg_primaries)

BG_D_OUT, BG_R_OUT, BG_G_OUT, BG_Y_OUT, BG_B_OUT, BG_M_OUT, BG_C_OUT, BG_L_OUT = (
  (c if is_out_tty else '') for c in  ansi_bg_primaries)


def ansi_cursor_pos(x:int, y:int) -> str:
  '''
  Position the cursor.
  Supposedly the 'f' suffix does the same thing.
  x and y parameters are zero based.
  '''
  return ansi_ctrl_seq('H', y + 1, x + 1)


ERASE_LINE_F, ERASE_LINE_B, ERASE_LINE = (ansi_ctrl_seq('K', i) for i in range(3))

CLEAR_SCREEN_F, CLEAR_SCREEN_B, CLEAR_SCREEN = (ansi_ctrl_seq('J', i) for i in range(3))

CURSOR_SAVE     = ansi_ctrl_seq('s')
CURSOR_RESTORE  = ansi_ctrl_seq('u')
CURSOR_HIDE     = ansi_ctrl_seq('?25l')
CURSOR_SHOW     = ansi_ctrl_seq('?25h')
CURSOR_REPORT   = ansi_ctrl_seq('6n') # '\x1B[{x};{y}R' appears as if typed into the terminal.

ALT_ENTER = ansi_ctrl_seq('?1049h')
ALT_EXIT  = ansi_ctrl_seq('?1049l')


def ansi_term_pos(x: int, y: int) -> str:
  '''
  position the cursor using 0-indexed x, y integer coordinates.
  (supposedly the 'f' suffix does the same thing).
  '''
  return ansi_ctrl_seq('H', y + 1, x + 1)


def ansi_show_cursor(show_cursor: Any) -> str:
  return CURSOR_SHOW if ansi_show_cursor else CURSOR_HIDE


