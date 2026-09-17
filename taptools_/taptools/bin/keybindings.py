#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Report terminal controls and the bindings for a zsh editing mode.

After installation, run `eval "$(keybindings -init)"` in zsh to capture the current shell's bindings.
Direct invocation starts an interactive zsh and reads its startup configuration instead.
'''

import os
import pty
import re
import shlex
import subprocess
import sys
import termios
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pithy.cmdparse import Cmd, flag, opt
from pithy.strings import fmt_rows


# Keep the collector in a subshell so its variables cannot change the caller's shell.
# NUL framing preserves whitespace, quotes and newlines in keymap names and bindings.
zsh_collector = r'''(
  builtin zmodload zsh/zleparameter || exit
  builtin printf '%s\0' gloss-keybindings-v1 "${options[flowcontrol]}" "${KEYTIMEOUT}" "$(builtin bindkey -lL)"
  for gloss_keymap in "${keymaps[@]}"; do
    builtin printf '%s\0' "$gloss_keymap" "$(builtin bindkey -M "$gloss_keymap")"
  done
  builtin printf '\0'
)'''


type Mode = Literal['main','emacs','viins','vicmd','viopp','visual','isearch','command','.safe','menuselect']


class Keybindings(Cmd):
  '''
  Print terminal controls and zsh bindings, including custom widgets and keyboard macros.

  For live session bindings after installation, run: eval "$(keybindings -init)"; keybindings
  Without the wrapper, a fresh interactive zsh reads the user's startup files.
  Terminal emulator application shortcuts are not exposed by the tty interface.
  '''
  mode:Mode = opt(default='main', doc='Editing mode; local modes include their underlying global map.')
  init:bool = flag(doc='Print a zsh function that captures the current shell before invoking this program.')
  zsh_state:str = opt('-zsh-state', default='', doc='Read a snapshot supplied by the generated zsh function.')


def main() -> None:
  args = Keybindings.parse_or_exit()
  if args.init:
    print(shell_init())
    return
  fd = open_terminal()
  try:
    attrs = termios.tcgetattr(fd) if fd is not None else None
    if args.zsh_state:
      data = Path(args.zsh_state).read_text()
    else:
      data = collect_zsh_state(attrs)
    print_bindings(parse_zsh_state(data), args.mode, fd, attrs)
  except (OSError, ValueError, termios.error, subprocess.SubprocessError) as exc:
    sys.exit(f'keybindings: {exc}')
  finally:
    if fd is not None: os.close(fd)


@dataclass
class ZshState:
  flow_control:str
  key_timeout:str
  aliases:str
  keymaps:dict[str,str]


def parse_zsh_state(data:str) -> ZshState:
  'Read the collector protocol, allowing startup files to print before or after it.'
  _, marker, payload = data.partition('gloss-keybindings-v1\0')
  if not marker: raise ValueError('zsh did not return a keybinding snapshot.')
  fields = payload.split('\0')
  if len(fields) < 6: raise ValueError('Incomplete zsh keybinding snapshot.')
  flow_control, key_timeout, aliases = fields[:3]
  keymaps:dict[str,str] = {}
  idx = 3
  while idx + 1 < len(fields) and fields[idx]:
    keymaps[fields[idx]] = fields[idx+1]
    idx += 2
  if not keymaps or idx >= len(fields) or fields[idx]:
    raise ValueError('Incomplete zsh keymap list.')
  return ZshState(flow_control, key_timeout, aliases, keymaps)


def shell_init() -> str:
  'Generate a wrapper with the executable path quoted for zsh.'
  executable = shlex.quote(str(Path(__file__).resolve()))
  return f'''keybindings() {{
  command {executable} -zsh-state <({zsh_collector}) "$@"
}}'''


# A flag is identified by its tcgetattr field index and its termios constant name.
control_characters = (
  ('VINTR', 'Interrupt (SIGINT)', ((3, 'ISIG'),)),
  ('VQUIT', 'Quit (SIGQUIT)', ((3, 'ISIG'),)),
  ('VSUSP', 'Suspend (SIGTSTP)', ((3, 'ISIG'),)),
  ('VDSUSP', 'Delayed suspend', ((3, 'ISIG'), (3, 'IEXTEN'))),
  ('VSTART', 'Resume output', ((0, 'IXON'),)),
  ('VSTOP', 'Pause output', ((0, 'IXON'),)),
  ('VEOF', 'End of input', ((3, 'ICANON'),)),
  ('VEOL', 'Additional line delimiter', ((3, 'ICANON'),)),
  ('VEOL2', 'Second line delimiter', ((3, 'ICANON'), (3, 'IEXTEN'))),
  ('VERASE', 'Erase character', ((3, 'ICANON'),)),
  ('VWERASE', 'Erase word', ((3, 'ICANON'), (3, 'IEXTEN'))),
  ('VKILL', 'Erase line', ((3, 'ICANON'),)),
  ('VREPRINT', 'Reprint line', ((3, 'ICANON'), (3, 'IEXTEN'))),
  ('VLNEXT', 'Quote next character', ((3, 'IEXTEN'),)),
  ('VDISCARD', 'Discard output', ((3, 'IEXTEN'),)),
  ('VSTATUS', 'Request status (SIGINFO)', ((3, 'ICANON'), (3, 'IEXTEN'))),
  ('VSWTCH', 'Legacy shell-layer switch', ()),
  ('VSWTC', 'Legacy shell-layer switch', ()),
)


@dataclass(frozen=True)
class Stroke:
  key:str
  ctrl:bool = False
  opt:bool = False
  shift:bool = False
  cmd:bool = False

  @property
  def sort_key(self) -> tuple[str,bool,bool,bool,bool]:
    return self.key, self.cmd, self.shift, self.opt, self.ctrl

  def __str__(self) -> str:
    modifiers = [symbol for flag, symbol in zip((self.ctrl, self.opt, self.shift, self.cmd), '⌃⌥⇧⌘') if flag]
    return ' '.join([*modifiers, self.key])


@dataclass
class Binding:
  raw:str
  action:str
  origin:str
  status:str = ''
  end:str = ''

  @property
  def keys(self) -> tuple[Stroke,...]: return keystrokes(self.raw)

  @property
  def label(self) -> str:
    label = ' '.join(map(str, self.keys))
    return label + (' – ' + ' '.join(map(str, keystrokes(self.end))) if self.end else '')


def decode_key(text:str) -> str:
  'Decode bindkey notation, preserving high-bit Meta separately from Escape-prefixed input.'
  idx = 0
  def char() -> str:
    nonlocal idx
    # Bindkey escapes literal backslashes again when quoting the listing.
    if text.startswith('\\' * 3, idx):
      idx += 4 if text.startswith('\\' * 4, idx) else 3
      return '\\'
    c = text[idx]
    idx += 1
    if c == '^' and idx < len(text):
      c = char()
      return chr(127 if c == '?' else ord(c.upper()) & 159)
    if c != '\\' or idx == len(text): return c
    c = text[idx]
    idx += 1
    if c in 'MC':
      if idx < len(text) and text[idx] == '-': idx += 1
      value = ord(char())
      return chr(value | 128 if c == 'M' else value & 159)
    if c in '01234567xuU':
      pattern = r'[0-7]{0,2}' if c in '01234567' else r'[0-9a-fA-F]{1,' + str({'x':2, 'u':4, 'U':8}[c]) + '}'
      match = re.match(pattern, text[idx:])
      if match:
        idx += len(match[0])
        return chr(int(c + match[0], 8) if c in '01234567' else int(match[0], 16))
    return {'a':'\a', 'b':'\b', 'e':'\x1b', 'E':'\x1b', 'f':'\f', 'n':'\n', 'r':'\r', 't':'\t', 'v':'\v'}.get(c, c)
  chars = []
  while idx < len(text): chars.append(char())
  return ''.join(chars)


# Recognize common terminal encodings before interpreting Escape as Option.
# https://developer.apple.com/design/human-interface-guidelines/keyboards specifies modifier order.
terminal_keys = {'A':'↑', 'B':'↓', 'C':'→', 'D':'←', 'H':'↖', 'F':'↘', 'P':'F1', 'Q':'F2', 'R':'F3', 'S':'F4'}
tilde_keys = {'1':'↖', '2':'Insert', '3':'⌦', '4':'↘', '5':'⇞', '6':'⇟', '7':'↖', '8':'↘',
  '11':'F1', '12':'F2', '13':'F3', '14':'F4', '15':'F5', '17':'F6', '18':'F7', '19':'F8',
  '20':'F9', '21':'F10', '23':'F11', '24':'F12', '200':'Paste start', '201':'Paste end'}
sequence_re = re.compile(r'\x1b(?:\[|O)(?:(\d+)(?:;(\d+))?)?([A-Z~])')


def keystrokes(raw:str) -> tuple[Stroke,...]:
  strokes = []
  idx = 0
  while idx < len(raw):
    if match := sequence_re.match(raw, idx):
      number, modifier, final = match.groups()
      key = tilde_keys.get(number) if final == '~' else '⇥' if final == 'Z' else terminal_keys.get(final)
      if key:
        bits = int(modifier or '1') - 1
        strokes.append(Stroke(key, ctrl=bool(bits & 4), opt=bool(bits & 2), shift=bool(bits & 1) or final == 'Z'))
        idx = match.end()
        continue
    value = ord(raw[idx])
    if 0xC2 <= value <= 0xF4:
      size = 2 if value < 0xE0 else 3 if value < 0xF0 else 4
      try: char = raw[idx:idx+size].encode('latin1').decode('utf8')
      except UnicodeError: pass
      else:
        strokes.append(Stroke(char))
        idx += size
        continue
    c = raw[idx]
    idx += 1
    opt = c == '\x1b' and idx < len(raw)
    if opt:
      c = raw[idx]
      idx += 1
    value = ord(c)
    special = {0:'Sp', 9:'⇥', 13:'↩', 27:'⎋', 32:'Sp', 127:'⌫'}
    if 128 <= value <= 255:
      # High-bit Meta is a byte encoding, not equivalent to an Escape prefix.
      strokes.append(Stroke(f'Meta[0x{value:02X}]', opt=opt))
    elif value in special:
      strokes.append(Stroke(special[value], ctrl=value == 0, opt=opt))
    elif value < 32:
      strokes.append(Stroke(chr(value + 64), ctrl=True, opt=opt))
    else:
      strokes.append(Stroke(c.upper() if c.isascii() and c.isalpha() else c, opt=opt,
        shift=c.isascii() and c.isupper()))
  return tuple(strokes)


binding_re = re.compile(r'"(?P<key>(?:\\.|[^"\\])*)"(?:-"(?P<end>(?:\\.|[^"\\])*)")? (?P<action>.*)')


def parse_bindings(text:str, origin:str) -> list[Binding]:
  bindings:list[Binding] = []
  for line in text.splitlines():
    match = binding_re.fullmatch(line)
    if not match: raise ValueError(f'Unrecognized binding in {origin}: {line!r}')
    action = match['action']
    if action == 'undefined-key': continue
    if action.startswith('"'): action = 'Type keys: ' + action
    start = decode_key(match['key'])
    end = decode_key(match['end']) if match['end'] is not None else ''
    # Expand byte ranges so local overrides and terminal collisions align with individual keys.
    if end:
      if len(start) != 1 or len(end) != 1: raise ValueError(f'Unexpected key range: {line}')
      bindings.extend(Binding(chr(value), action, origin) for value in range(ord(start), ord(end) + 1))
    else: bindings.append(Binding(start, action, origin))
  return bindings


def mode_bindings(state:ZshState, mode:Mode) -> list[Binding]:
  # Local maps override both equal bindings and global bindings that are their prefixes.
  # https://zsh.sourceforge.io/Doc/Release/Zsh-Line-Editor.html#Local-Keymaps
  base = {'viopp':'vicmd', 'visual':'vicmd', 'isearch':'main', 'command':'main', 'menuselect':'main'}.get(mode)
  names = [base, mode] if base else [mode]
  bindings:list[Binding] = []
  for name in names:
    if name == 'main' and name not in state.keymaps: name = '.safe'
    if name not in state.keymaps: raise ValueError(f'Zsh keymap {name!r} is unavailable.')
    local = parse_bindings(state.keymaps[name], 'zle:' + name)
    for binding in bindings:
      if any(other.raw.startswith(binding.raw) for other in local): binding.status = 'Overridden by ' + name
    bindings.extend(local)
  return bindings


def terminal_bindings(attrs:list[Any], disabled:int) -> list[Binding]:
  bindings:list[Binding] = []
  seen_indices:set[int] = set()
  conditions = {'ISIG':'signals', 'IEXTEN':'extended input', 'IXON':'output flow control', 'ICANON':'line input'}
  for name, action, flags in control_characters:
    idx = getattr(termios, name, None)
    if idx is None or idx in seen_indices: continue
    seen_indices.add(idx)
    raw = attrs[6][idx]
    value = raw if isinstance(raw, int) else raw[0]
    if value == disabled: continue
    inactive = [conditions[flag_name] for field, flag_name in flags if not attrs[field] & getattr(termios, flag_name)]
    status = 'Inactive: ' + ', '.join(inactive) + ' off' if inactive else ''
    bindings.append(Binding(chr(value), action, 'tty:' + name[1:].lower(), status))
  return bindings


def table_rows(bindings:list[Binding]) -> list[tuple[str,str,str,str,str,str]]:
  # Compact uninteresting character ranges only when there are no competing bindings.
  counts:dict[str,int] = {}
  for binding in bindings: counts[binding.raw] = counts.get(binding.raw, 0) + 1
  compact:list[Binding] = []
  for binding in sorted(bindings, key=lambda b: (b.origin, b.raw)):
    prev = compact[-1] if compact else None
    if (prev and binding.action == prev.action == 'self-insert' and binding.origin == prev.origin
      and binding.status == prev.status and len(binding.raw) == len(prev.end or prev.raw) == 1
      and ((32 <= ord(prev.raw) <= ord(binding.raw) < 127) or (128 <= ord(prev.raw) <= ord(binding.raw) < 256))
      and ord(binding.raw) == ord(prev.end or prev.raw) + 1 and counts[binding.raw] == counts[prev.raw] == 1):
      prev.end = binding.raw
    else: compact.append(Binding(binding.raw, binding.action, binding.origin, binding.status))
  compact.sort(key=lambda b: (tuple(stroke.sort_key for stroke in b.keys), b.raw, b.origin))
  rows = []
  for binding in compact:
    keys = [binding.label] if binding.end else list(map(str, binding.keys))
    keys.extend(['', ''])
    rows.append((keys[0], keys[1], ' '.join(keys[2:]).rstrip(), binding.origin, binding.action, binding.status))
  return rows


def print_bindings(state:ZshState, mode:Mode, fd:int|None, attrs:list[Any]|None) -> None:
  bindings = mode_bindings(state, mode)
  print(f'Keybindings: {mode}')
  aliases = []
  for line in state.aliases.splitlines():
    parts = shlex.split(line)
    if len(parts) == 4 and parts[:2] == ['bindkey', '-A']: aliases.append(f'{parts[3]} = {parts[2]}')
  if aliases: print('Keymap aliases: ' + '; '.join(aliases))
  print(f'Key sequence timeout: {state.key_timeout} hundredths of a second. Flow control: {state.flow_control}.')
  print('⌥ assumes Option sends Escape; Meta[0xNN] is a distinct high-bit byte. Return = ⌃M; Tab = ⌃I.')
  print('Terminal app shortcuts and multiplexer bindings are not included.')
  if mode in ('isearch', 'command', 'menuselect'):
    print('Fallback assumes main; the active global map can differ when entering this mode.')
    print('Widgets may interpret actions differently here or only accept a subset of them.')
  if fd is None or attrs is None:
    print('Terminal controls unavailable: no controlling terminal or tty on standard input/output/error.')
  else:
    bindings.extend(terminal_bindings(attrs, os.fpathconf(fd, 'PC_VDISABLE')))
    print('TTY controls reflect settings while this command runs. Zsh’s editor and other interactive programs may change them.')
    print('Disabled terminal controls are omitted. With flow control off, ZLE frees ⌃S and ⌃Q.')
  rows = []
  for row in table_rows(bindings):
    key, second, third, origin, action, status = row
    if key == 'Meta[0x80] – Meta[0xFF]' and action == 'self-insert' and not status:
      print(f'Text input ({origin}): bytes 0x80–0xFF use self-insert, allowing ordinary UTF-8 text input.')
    elif key == 'Sp – ~' and action == 'self-insert' and not status:
      print(f'Text input ({origin}): printable ASCII characters, including space, insert themselves.')
    elif key == 'Paste start' and not second and not third and action == 'bracketed-paste' and not status:
      print(f'Bracketed paste ({origin}): pasted text is handled by the bracketed-paste widget.')
    else: rows.append(row)
  print()
  for line in fmt_rows(rows, head=('Key', '2nd', '3rd', 'Origin', 'Action', 'Status'), rjust=(True, True, True, False)):
    print(line.rstrip())


def open_terminal() -> int|None:
  try: return os.open('/dev/tty', os.O_RDONLY | os.O_NOCTTY)
  except OSError:
    for fd in (0, 1, 2):
      if os.isatty(fd): return os.dup(fd)
  return None


def collect_zsh_state(attrs:list[Any]|None) -> str:
  'Run startup files on a private tty in a separate session, preserving the caller terminal and foreground job.'
  master, slave = pty.openpty()
  try:
    if attrs is not None: termios.tcsetattr(slave, termios.TCSANOW, attrs)
    result = subprocess.run(['zsh', '+m', '-i', '-c', zsh_collector], stdin=slave, capture_output=True,
      text=True, check=True, timeout=15, start_new_session=True)
    if result.stderr: print(result.stderr, end='', file=sys.stderr)
    return result.stdout
  finally:
    os.close(slave)
    os.close(master)


if __name__ == '__main__': main()
