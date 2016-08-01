# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
ANSI Control Sequences.


ANSI Select Graphics Rendition (SGR) sequences.

RST: reset

BOLD: bold
UNDERLINE: underline
BLINK: blink
INVERT: invert
TXT: color text
BG: color background

K: black
W: white
D: dark gray
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


# ANSI control sequence indicator.
CSI = '\x1B['

# regex for detecting control sequences in strings.
# TODO: replace .*? wildcard with stricter character set.
ansi_ctrl_seq_re = _re.compile(r'\x1B\[.*?[hHJKlmsu]')


def ansi_ctrl_seq(c, *args):
  'Format a control sequence string for command character `c` and arguments.'
  return '{}{}{}'.format(CSI, ';'.join(str(a) for a in args), c)


def strip_ansi_ctrl_seq(text):
  'Strip control sequences from a string.'
  return ansi_ctrl_seq_re.sub('', text)


def len_strip_ansi_ctrl_seq(s):
  'Calculate the length of string if control sequences were stripped.'
  l = len(s)
  for m in ansi_ctrl_seq_re.finditer(s):
    l -= m.end() - m.start()
  return l


def ansi_sgr(*seq):
  'Select Graphic Rendition control sequence string.'
  return ansi_ctrl_seq('m', *seq)


# reset command strings.
RST, RST_BOLD, RST_UNDERLINE, RST_BLINK, RST_INVERT, RST_TXT, RST_BG = \
(ansi_sgr(i) for i in (0, 22, 24, 25, 27, 39, 49))

# effect command strings.
BOLD, UNDERLINE, BLINK, INVERT = (ansi_sgr(i) for i in (1, 4, 5, 7))

# color text: dark gray, red, green, yellow, blue, magenta, cyan, light gray.
ansi_text_primaries = tuple(ansi_sgr(i) for i in range(30, 38))
TXT_D, TXT_R, TXT_G, TXT_Y, TXT_B, TXT_M, TXT_C, TXT_L = ansi_text_primaries

# color background: dark gray, red, green, yellow, blue, magenta, cyan, light gray
ansi_background_primaries = tuple(ansi_sgr(i) for i in range(40, 48))
BG_D, BG_R, BG_G, BG_Y, BG_B, BG_M, BG_C, BG_L = ansi_background_primaries


ERASE_LINE_F, ERASE_LINE_B, ERASE_LINE = (ansi_ctrl_seq('K', i) for i in range(3))

CLEAR_SCREEN_F, CLEAR_SCREEN_B, CLEAR_SCREEN = (ansi_ctrl_seq('J', i) for i in range(3))

CURSOR_SAVE     = ansi_ctrl_seq('s')
CURSOR_RESTORE  = ansi_ctrl_seq('u')
CURSOR_HIDE     = ansi_ctrl_seq('?25l')
CURSOR_SHOW     = ansi_ctrl_seq('?25h')
CURSOR_REPORT   = ansi_ctrl_seq('6n') # not sure how to interpret the results.

ALT_ENTER = ansi_ctrl_seq('?1049h')
ALT_EXIT  = ansi_ctrl_seq('?1049l')


def ansi_term_pos(x, y):
  '''
  position the cursor using 0-indexed x, y integer coordinates.
  (supposedly the 'f' suffix does the same thing).
  '''
  return ansi_ctrl_seq('H', y + 1, x + 1)


def ansi_show_cursor(show_cursor):
  return CURSOR_SHOW if ansi_show_cursor else CURSOR_HIDE


