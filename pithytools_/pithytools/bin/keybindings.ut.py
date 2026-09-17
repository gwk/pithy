# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
import pty
import select
import signal
import subprocess
import sys
import termios
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from pithytools.bin.keybindings import (Binding, decode_key, Keybindings, keystrokes, mode_bindings, parse_bindings, table_rows,
  ZshState)
from utest import utest, utest_run, utest_val


program = Path(__file__).resolve().with_name('keybindings.py')


def skip_without_pty(test_name:str) -> bool:
  '''
  Return True after printing a warning if pty allocation is denied.
  The Claude command sandbox denies write access to `/dev/ptmx`; this is a known limitation of that sandbox only.
  Probe `os.openpty` directly because `pty.openpty` masks the EPERM as 'out of pty devices'.
  '''
  try: master, slave = os.openpty()
  except PermissionError:
    print(f'warning: {test_name} skipped: pty allocation denied; known limitation of the Claude sandbox only.', file=sys.stderr)
    return True
  os.close(master)
  os.close(slave)
  return False


@utest_run
def test_live_bindings() -> None:
  'The wrapper captures changes absent from startup files, including custom maps and macros.'
  init = subprocess.run([sys.executable, str(program), '-init'], capture_output=True, text=True, check=True).stdout
  script = init + r'''
    bindkey -v
    bindkey -M main '^S' session-only-widget
    bindkey -M main -s '^Xq' 'echo "hello"^M'
    bindkey -N 'custom map'
    bindkey -M 'custom map' ' ' custom-space-widget
    bindkey -N $'map\nwith newline'
    bindkey -M $'map\nwith newline' '^A' newline-map-widget
    unsetopt FLOW_CONTROL
    KEYTIMEOUT=73
    keybindings
  '''
  # A new session detaches the controlling terminal but can still inherit a tty on stdin.
  result = subprocess.run(['zsh', '-f', '-c', script], stdin=subprocess.DEVNULL, capture_output=True,
    text=True, check=True, start_new_session=True)
  output = result.stdout
  assert 'Keybindings: main' in output
  assert 'unavailable: no controlling terminal' in output
  assert 'timeout: 73' in output and 'Flow control: off' in output
  assert 'main = viins' in output
  assert 'session-only-widget' in output
  assert 'Type keys:' in output and 'hello' in output
  assert 'custom-space-widget' not in output and 'newline-map-widget' not in output
  assert 'zle:.safe' not in output
  assert 'printable ASCII characters, including space, insert themselves.' in output
  assert 'Sp – ~' not in output


@utest_run
def test_startup_and_terminal_restoration() -> None:
  'Read a configured shell without leaving its stty changes on the caller terminal.'
  if skip_without_pty('test_startup_and_terminal_restoration'): return
  with TemporaryDirectory() as directory:
    root = Path(directory)
    (root / '.zshrc').write_text('''\
print 'Startup message.'
bindkey '^S' configured-widget
stty -ixon
''')
    master, slave = pty.openpty()
    try:
      attrs = termios.tcgetattr(slave)
      attrs[0] |= termios.IXON
      attrs[6][termios.VSTOP] = b'\x13'
      attrs[6][termios.VQUIT] = bytes([os.fpathconf(slave, 'PC_VDISABLE')])
      termios.tcsetattr(slave, termios.TCSANOW, attrs)
      before = termios.tcgetattr(slave)
      result = subprocess.run([sys.executable, str(program)], stdin=slave, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, check=True, start_new_session=True, env={**os.environ, 'ZDOTDIR': directory})
      utest_val(before, termios.tcgetattr(slave))
      output = result.stdout
      assert 'configured-widget' in output
      assert '⌃ S' in output and 'tty:stop' in output and 'Pause output' in output
      assert 'tty:quit' not in output
      assert 'Enabled outside ZLE' not in output
      assert 'Startup message.' not in output
      # An early exit in a startup file must also restore the terminal and report a useful error.
      (root / '.zshrc').write_text('stty -ixon\nexit 7\n')
      result = subprocess.run([sys.executable, str(program)], stdin=slave, capture_output=True,
        text=True, start_new_session=True, env={**os.environ, 'ZDOTDIR': directory})
      utest_val(1, result.returncode)
      utest_val(before, termios.tcgetattr(slave))
      assert 'keybindings:' in result.stderr and 'Traceback' not in result.stderr
    finally:
      os.close(slave)
      os.close(master)


@utest_run
def test_invalid_snapshot() -> None:
  with TemporaryDirectory() as directory:
    snapshot = Path(directory) / 'snapshot'
    snapshot.write_text('invalid')
    result = subprocess.run([sys.executable, str(program), '-zsh-state', str(snapshot)], capture_output=True, text=True,
      start_new_session=True)
    utest_val(1, result.returncode)
    assert 'zsh did not return a keybinding snapshot' in result.stderr
    assert 'Traceback' not in result.stderr


@utest_run
def test_controlling_terminal() -> None:
  'An interactive collector must not take foreground ownership from the reporting process.'
  if skip_without_pty('test_controlling_terminal'): return
  with TemporaryDirectory() as directory:
    (Path(directory) / '.zshrc').write_text("bindkey '^S' controlling-terminal-widget\nstty -ixon\n")
    probe = '''\
import os, subprocess, sys, termios
before_group = os.tcgetpgrp(0)
before_attrs = termios.tcgetattr(0)
result = subprocess.run([sys.executable, sys.argv[1]], capture_output=True, text=True, timeout=5)
assert result.returncode == 0, result.stderr
assert 'controlling-terminal-widget' in result.stdout
assert os.tcgetpgrp(0) == before_group, 'Foreground process group changed.'
assert termios.tcgetattr(0) == before_attrs, 'Terminal attributes changed.'
print('CONTROLLING TERMINAL OK', flush=True)
'''
    pid, master = pty.fork()
    if pid == 0:
      os.execve(sys.executable, [sys.executable, '-c', probe, str(program)], {**os.environ, 'ZDOTDIR': directory})
    output = bytearray()
    child_status:int|None = None
    try:
      deadline = time.monotonic() + 8
      while time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], 0.05)
        if ready:
          try: chunk = os.read(master, 65536)
          except OSError: break # Linux reports EIO when the slave closes.
          if not chunk: break
          output.extend(chunk)
        waited_pid, status = os.waitpid(pid, os.WNOHANG | os.WUNTRACED)
        if waited_pid:
          child_status = status
          break
      assert b'CONTROLLING TERMINAL OK' in output, output.decode(errors='replace')
    finally:
      if child_status is None or os.WIFSTOPPED(child_status):
        waited_pid, _ = os.waitpid(pid, os.WNOHANG)
        if not waited_pid:
          os.kill(pid, signal.SIGKILL)
          os.waitpid(pid, 0)
      os.close(master)


@utest_run
def test_format_and_sort() -> None:
  cases = {'^R':'⌃ R', '^[r':'⌥ R', '^[R':'⌥ ⇧ R', '^[^R':'⌃ ⌥ R', '^Xr':'⌃ X R',
    '^[[A':'↑', '^[OA':'↑', '^[[1;6D':'⌃ ⇧ ←', '^[[Z':'⇧ ⇥', '^?':'⌫', '^I':'⇥', '^M':'↩',
    r'\M-r':'Meta[0xF2]', r'\\':'\\', r'\^':'^', r'\033r':'⌥ R'}
  for raw, expected in cases.items():
    utest_val(expected, ' '.join(map(str, keystrokes(decode_key(raw)))))
  bindings = [Binding(decode_key(key), key, 'test') for key in ('^[b', '^[A', '^B', 'a', '^A', '^[a')]
  utest_val(['A', '⌃ A', '⌥ A', '⌥ ⇧ A', '⌃ B', '⌥ B'], [row[0] for row in table_rows(bindings)])
  utest_val('main', Keybindings.parse([]).mode)
  utest_val('visual', Keybindings.parse(['-mode', 'visual']).mode)


@utest_run
def test_mode_overrides() -> None:
  state = ZshState('off', '40', '', {'main':'"^A" global-a\n"^B" global-b',
    'isearch':'"^A" local-a', 'vicmd':'"i" insert\n"iwx" longer\n"a" append', 'viopp':'"iw" word'})
  bindings = mode_bindings(state, 'isearch')
  utest_val([('global-a', 'Overridden by isearch'), ('global-b', ''), ('local-a', '')],
    [(b.action, b.status) for b in bindings])
  rows = table_rows(bindings + [Binding('\x01', 'Terminal A', 'tty:test')])
  utest_val(['⌃ A', '⌃ A', '⌃ A', '⌃ B'], [row[0] for row in rows])
  bindings = mode_bindings(state, 'viopp')
  utest_val([('insert', 'Overridden by viopp'), ('longer', ''), ('append', ''), ('word', '')],
    [(b.action, b.status) for b in bindings])
  utest([Binding('a', 'safe', 'zle:.safe')], mode_bindings, ZshState('off', '40', '', {'.safe':'"a" safe'}), 'main')


@utest_run
def test_range_collisions() -> None:
  state = ZshState('off', '40', '', {'main':'"a"-"z" self-insert', 'isearch':'"m" local-m'})
  rows = table_rows(mode_bindings(state, 'isearch'))
  utest_val(['A – L', 'M', 'M', 'N – Z'], [row[0] for row in rows])
  assert any(row[4:] == ('self-insert', 'Overridden by isearch') for row in rows)


@utest_run
def test_zsh_quoting() -> None:
  for key in ('^', '\\', 'a\\b', '\\n', '\\^A', '\\' * 2, '"', '$', '\x1c', 'é'):
    result = subprocess.run(['zsh', '-f', '-c',
      'bindkey -N probe; bindkey -M probe "$1" probe-widget; bindkey -M probe', 'probe',
      key.replace('\\', '\\\\').replace('^', '\\^')], capture_output=True, text=True, check=True)
    bindings = parse_bindings(result.stdout, 'probe')
    utest_val(1, len(bindings))
    expected = key.encode('utf8').decode('latin1')
    utest_val(expected, bindings[0].raw)
    if key == 'é': utest_val('é', bindings[0].label)
