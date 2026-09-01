# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from json import loads as parse_json
from queue import Empty, Queue
from re import compile as re_compile, Pattern
from select import select
from subprocess import PIPE, Popen, run, STDOUT
from sys import exit, stdin, stdout
from termios import tcgetattr, TCSADRAIN, tcsetattr
from threading import Thread
from time import monotonic, sleep
from tty import setcbreak
from typing import Any, Iterable

from pithy.ansi import CLEAR_SCREEN_F, ctrl_seq, CURSOR_HIDE, CURSOR_SHOW, RST, TXT_G, TXT_N, TXT_R, TXT_Y
from pithy.cmdparse import Cmd, opt, pos
from pithy.logs import render_log_record_as_text


show_props = ('Id', 'ActiveState', 'SubState', 'Result', 'NRestarts', 'InactiveExitTimestamp')


class WatchSystemdUnitsCmd(Cmd):
  '''
  Watch systemd units after a deploy until they are healthy.

  The watch combines two sources:
  * `systemctl show`, polled once per second, for each unit's active state, result, and restart count.
  * `journalctl`, streaming all specified unit log records, process exits, and unit failures as they happen.

  Warn and error log records are surfaced as they arrive.
  Log levels use the journal PRIORITY field. Pithy JSON messages are parsed for readiness matching and structured display.

  Repeat `-ready UNIT1=REGEX -ready UNIT2=REGEX` to specify readiness patterns for individual units.
  Repeat `-message-key UNIT1=KEY -message-key UNIT2=KEY` when a unit's structured JSON uses a message key other than `_`.

  A unit is ready when its regex matches a log message, or, if no regex is given, when its ActiveState is `active`.
  With Type=notify units, active means the service reported readiness itself.
  The watch ends when either:
  * the timeout elapses;
  * when every unit is either:
    * failed;
    * ready and has stayed clean for the settle period.
  The exit status is 0 only when every unit is ready with no failures and no error records.
  On interruption, the exit status reflects the observed state: 0 if all units are ready and clean, 1 if any unit has a known
  failure or error, and 130 if any unit has not yet become ready.
  In a terminal, press `q` to quit with the same state-dependent exit status without interrupting a parent process.
  '''

  units:list[str] = pos(metavar='UNIT', doc='Unit names to watch; the .service suffix is optional.')
  ready:list[str] = opt(default_factory=list, metavar='UNIT=REGEX',
    doc='Repeat for each unit whose readiness is indicated by a log message matching REGEX.')
  message_key:list[str] = opt(default_factory=list, metavar='UNIT=KEY',
    doc='Repeat for each unit whose structured JSON message key is not `_`.')
  since:str|None = opt(default=None, doc='journalctl --since spec; defaults to the earliest recent start among the units.')
  settle:float = opt(default=30, doc='Seconds a unit must stay clean after becoming ready.')
  timeout:float = opt(default=600, doc='Seconds to wait before giving up.')
  interval:float = opt(default=1, doc='Seconds between systemctl polls.')


def main() -> None:
  args = WatchSystemdUnitsCmd.parse_or_exit()

  units = [unit_name(u) for u in args.units]
  ready_patterns = parse_ready_specs(args.ready)
  message_keys = parse_message_key_specs(args.message_key)
  for opt_name, mapping in (('-ready', ready_patterns), ('-message-key', message_keys)):
    for name in mapping:
      if name not in units: exit(f'error: {opt_name} unit is not being watched: {name!r}')

  watcher = Watcher(units=units, ready_patterns=ready_patterns, message_keys=message_keys, settle=args.settle,
    timeout=args.timeout, interval=args.interval)
  try: code = watcher.run(since=args.since)
  except KeyboardInterrupt:
    watcher.finish()
    code = 130
  exit(code)


def parse_ready_specs(specs:list[str]) -> dict[str,Pattern[str]]:
  pats:dict[str,Pattern[str]] = {}
  for spec in specs:
    name, eq, regex = spec.partition('=')
    if not eq or not name or not regex: exit(f'error: -ready spec must be UNIT=REGEX; received: {spec!r}')
    pats[unit_name(name)] = re_compile(regex)
  return pats


def parse_message_key_specs(specs:list[str]) -> dict[str,str]:
  message_keys:dict[str,str] = {}
  for spec in specs:
    name, eq, key = spec.partition('=')
    if not eq or not name or not key: exit(f'error: -message-key spec must be UNIT=KEY; received: {spec!r}')
    message_keys[unit_name(name)] = key
  return message_keys


def unit_name(s:str) -> str:
  return s.removesuffix('.service')


@dataclass
class Event:
  unit:str
  kind:str # 'warn', 'error', 'exit', 'fail', 'info', 'tool'.
  text:str # Rendered text for display.
  msg:str = '' # Plain message text for ready matching.
  ok:bool = True # For 'exit' events: whether the exit was clean.


@dataclass
class UnitStatus:
  name:str
  ready_pat:Pattern[str]|None = None
  active:str = ''
  sub:str = ''
  result:str = ''
  restarts:int = 0
  ready_time:float|None = None
  failures:list[str] = field(default_factory=list)
  warns:int = 0
  errors:int = 0

  @property
  def is_ready(self) -> bool: return self.ready_time is not None

  @property
  def is_failed(self) -> bool: return bool(self.failures)

  @property
  def is_clean(self) -> bool: return not self.failures and not self.errors

  def is_settled(self, now:float, settle:float) -> bool:
    return self.ready_time is not None and (now - self.ready_time) >= settle

  def is_terminal(self, now:float, settle:float) -> bool:
    return self.is_failed or self.is_settled(now, settle)

  def state_label(self, now:float, settle:float) -> str:
    if self.is_failed: return f'{TXT_R}FAILED{RST}'
    if self.errors: return f'{TXT_R}ERRORS{RST}'
    if self.is_settled(now, settle): return f'{TXT_G}ok{RST}    '
    if self.is_ready: return f'{TXT_G}ready{RST} '
    return f'{TXT_Y}wait{RST}  '

  def update_from_show(self, props:dict[str,str]) -> list[str]:
    'Apply a polled property block. Returns descriptions of newly detected failures.'
    new_failures:list[str] = []
    self.active = props.get('ActiveState', '')
    self.sub = props.get('SubState', '')
    self.result = props.get('Result', '')
    try: self.restarts = int(props.get('NRestarts', '0'))
    except ValueError: pass
    if self.active == 'failed': new_failures.append(f'unit is failed: {self.result}')
    elif self.result not in ('', 'success'): new_failures.append(f'result: {self.result}')
    added = [f for f in new_failures if f not in self.failures]
    self.failures.extend(added)
    if self.ready_pat is None and self.ready_time is None and self.active == 'active':
      self.ready_time = monotonic()
    return added


def interrupt_exit_code(units:Iterable[UnitStatus]) -> int:
  'Return an exit status reflecting unit state observed before an interrupt.'
  units = list(units)
  if any(not unit.is_clean for unit in units): return 1
  if all(unit.is_ready for unit in units): return 0
  return 130


class Watcher:

  def __init__(self, units:list[str], ready_patterns:dict[str,Pattern[str]], message_keys:dict[str,str], settle:float,
   timeout:float, interval:float) -> None:
    self.units = {name: UnitStatus(name=name, ready_pat=ready_patterns.get(name)) for name in units}
    self.message_keys = message_keys
    self.settle = settle
    self.timeout = timeout
    self.interval = interval
    self.is_tty = stdout.isatty()
    self.tty_attrs:list[Any]|None = None
    self.block_lines = 0 # Number of lines in the last drawn status block.
    self.start_time = monotonic()
    self.pending:list[str] = [] # Event lines to print above the block on the next draw.
    self.queue:Queue[str|None] = Queue()
    self.proc:Popen[str]|None = None


  def run(self, since:str|None) -> int:
    show = systemctl_show(list(self.units))
    if since is None: since = default_since(show)
    self.apply_show(show)
    self.start_journal(since)
    if self.is_tty:
      stdout.write(CURSOR_HIDE)
      if stdin.isatty():
        self.tty_attrs = tcgetattr(stdin)
        setcbreak(stdin)
    self.note(f'watching {len(self.units)} units since {since!r}; settle {self.settle:g}s; timeout {self.timeout:g}s.')
    next_poll = monotonic() + self.interval
    journal_ended = False
    try:
      while True:
        journal_ended = self.drain_journal() or journal_ended
        now = monotonic()
        if now >= next_poll:
          self.apply_show(systemctl_show(list(self.units)))
          next_poll = now + self.interval
        self.draw(now)
        if journal_ended: return 0 if self.conclude('journal stream ended') else 1
        if all(u.is_terminal(now, self.settle) for u in self.units.values()):
          return 0 if self.conclude('all units settled or failed') else 1
        if now - self.start_time >= self.timeout: return 0 if self.conclude('timed out') else 1
        if self.quit_requested(): return self.conclude_early('quit')
        sleep(0.25)
    except KeyboardInterrupt:
      return self.conclude_early('interrupt')
    finally:
      self.finish()


  def finish(self) -> None:
    if self.proc is not None and self.proc.poll() is None:
      self.proc.terminate()
      self.proc = None
    if self.tty_attrs is not None:
      tcsetattr(stdin, TCSADRAIN, self.tty_attrs)
      self.tty_attrs = None
    if self.is_tty: stdout.write(CURSOR_SHOW)
    stdout.flush()


  def quit_requested(self) -> bool:
    if self.tty_attrs is None: return False
    readable, _, _ = select([stdin], [], [], 0)
    return bool(readable) and stdin.read(1).lower() == 'q'


  def conclude_early(self, action:str) -> int:
    self.drain_journal()
    code = interrupt_exit_code(self.units.values())
    if code == 0: self.note(f'{TXT_G}accepted on {action}{RST}: all units are ready and clean.')
    elif code == 1: self.note(f'{TXT_R}not verified{RST}: {action} with known failures or errors.')
    else: self.note(f'{TXT_R}not verified{RST}: {action} before all units became ready.')
    self.draw(monotonic(), final=True)
    return code


  def conclude(self, reason:str) -> bool:
    ok = all(u.is_ready and u.is_clean for u in self.units.values())
    verdict = f'{TXT_G}verified{RST}' if ok else f'{TXT_R}not verified{RST}'
    self.note(f'{verdict}: {reason}.')
    self.draw(monotonic(), final=True)
    return ok


  # Journal.

  def start_journal(self, since:str) -> None:
    cmd = ['journalctl', '-f', '-q', '--no-pager', '-o', 'json', '--since', since]
    for name in self.units: cmd += ['-u', name]
    try: self.proc = Popen(cmd, stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)
    except FileNotFoundError: exit('error: journalctl not found.')
    assert self.proc.stdout is not None
    Thread(target=read_lines, args=(self.proc.stdout, self.queue), daemon=True).start()


  def drain_journal(self) -> bool:
    'Process queued journal lines. Returns True if the stream has ended.'
    while True:
      try: line = self.queue.get_nowait()
      except Empty: return False
      if line is None:
        code = self.proc.poll() if self.proc else None
        self.note(f'{TXT_R}journalctl exited{RST}: {code}')
        return True
      line = line.strip()
      if not line: continue
      if not line.startswith('{'):
        self.pending.append(f'{TXT_R}journalctl{RST}: {line}')
        continue
      try: record = parse_json(line)
      except Exception: self.pending.append(f'{TXT_R}unparseable journal line{RST}: {line}'); continue
      if isinstance(record, dict): self.handle_record(record)


  def handle_record(self, record:dict[str,Any]) -> None:
    event = classify_record(record, message_keys=self.message_keys)
    unit = self.units.get(event.unit)
    if unit is None: return # Not one of ours, e.g. a message about a dependency.
    if event.kind == 'exit':
      if not event.ok:
        unit.failures.append(event.text)
        self.pending.append(f'{TXT_R}exit{RST} {unit.name}: {event.text}')
      elif unit.ready_pat is not None: # Run-to-completion units cycle by design; show the exit but do not count it.
        self.pending.append(f'{TXT_N}exit{RST} {unit.name}: {event.text}')
    elif event.kind == 'fail':
      unit.failures.append(event.text)
      self.pending.append(f'{TXT_R}fail{RST} {unit.name}: {event.text}')
    elif event.kind == 'error':
      unit.errors += 1
      self.pending.append(f'{unit.name}: {event.text}')
    elif event.kind == 'warn':
      unit.warns += 1
      self.pending.append(f'{unit.name}: {event.text}')
    if unit.ready_pat is not None and unit.ready_time is None and unit.ready_pat.search(event.msg):
      unit.ready_time = monotonic()
      self.pending.append(f'{TXT_G}ready{RST} {unit.name}: {event.msg}')


  # Status.

  def apply_show(self, show:dict[str,dict[str,str]]) -> None:
    for name, unit in self.units.items():
      props = show.get(name)
      if props is None: continue
      for failure in unit.update_from_show(props):
        self.pending.append(f'{TXT_R}fail{RST} {name}: {failure}')


  def note(self, text:str) -> None:
    self.pending.append(f'{TXT_N}watch-systemd-units{RST}: {text}')


  # Display.

  def draw(self, now:float, final:bool=False) -> None:
    lines = self.status_lines(now)
    if self.is_tty:
      out = ''
      if self.block_lines: out += ctrl_seq('A', self.block_lines) + '\r' + CLEAR_SCREEN_F
      out += ''.join(f'{l}\n' for l in self.pending)
      out += ''.join(f'{l}\n' for l in lines)
      stdout.write(out)
      self.block_lines = len(lines)
    else:
      out = ''.join(f'{l}\n' for l in self.pending)
      if final: out += ''.join(f'{l}\n' for l in lines)
      stdout.write(out)
    stdout.flush()
    self.pending.clear()


  def status_lines(self, now:float) -> list[str]:
    width = max(len(name) for name in self.units)
    elapsed = int(now - self.start_time)
    lines = [f'{TXT_N}elapsed {elapsed}s{RST}']
    for unit in self.units.values():
      state = f'{unit.active}/{unit.sub}' if unit.active else '?'
      counts = f'restarts:{unit.restarts} warn:{unit.warns} err:{unit.errors}'
      detail = f'  {TXT_R}{unit.failures[-1]}{RST}' if unit.failures else ''
      lines.append(f'  {unit.state_label(now, self.settle)}  {unit.name:<{width}}  {state:<20}  {counts}{detail}')
    lines.append('Press q to quit.')
    return lines


def read_lines(f:Any, queue:'Queue[str|None]') -> None:
  for line in f: queue.put(line)
  queue.put(None)


def systemctl_show(units:list[str]) -> dict[str,dict[str,str]]:
  'Return the selected properties of each unit, keyed by unit name.'
  cmd = ['systemctl', 'show', '--no-pager', '-p', ','.join(show_props), '--', *units]
  try: res = run(cmd, capture_output=True, text=True)
  except FileNotFoundError: exit('error: systemctl not found.')
  if res.returncode != 0: exit(f'error: systemctl show failed: {res.stderr.strip()}')
  return parse_show_output(res.stdout)


def parse_show_output(text:str) -> dict[str,dict[str,str]]:
  'Parse `systemctl show` output: blocks of KEY=VALUE lines, one block per unit, separated by blank lines.'
  units:dict[str,dict[str,str]] = {}
  for block in text.split('\n\n'):
    props:dict[str,str] = {}
    for line in block.splitlines():
      key, eq, val = line.partition('=')
      if eq: props[key] = val
    if 'Id' in props: units[unit_name(props['Id'])] = props
  return units


def default_since(show:dict[str,dict[str,str]]) -> str:
  '''
  Choose a journal start time: one second before the earliest last-start among the units, so that each unit's own
  startup records are included. Falls back to one minute ago for units that have never started.
  '''
  starts = [ts for props in show.values() if (ts := parse_systemd_timestamp(props.get('InactiveExitTimestamp', '')))]
  if not starts: return '-1min'
  return (min(starts) - timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')


def parse_systemd_timestamp(s:str) -> datetime|None:
  'Parse a `systemctl show` timestamp like "Tue 2026-08-25 10:00:00 PDT" as a naive local datetime.'
  parts = s.split()
  for idx, part in enumerate(parts[:-1]):
    if len(part) == 10 and part[4] == '-' and part[7] == '-':
      try: return datetime.strptime(f'{part} {parts[idx+1]}', '%Y-%m-%d %H:%M:%S')
      except ValueError: return None
  return None


def classify_record(record:dict[str,Any], message_keys:dict[str,str]|None=None) -> Event:
  'Classify a `journalctl -o json` record into an Event.'
  unit = record.get('_SYSTEMD_UNIT')
  if not isinstance(unit, str) or unit == 'init.scope': # Messages from systemd itself carry the subject unit in UNIT.
    unit = record.get('UNIT', unit)
  unit = unit_name(unit) if isinstance(unit, str) else ''

  msg = record.get('MESSAGE', '')
  if isinstance(msg, list): # journald renders non-UTF8 messages as byte arrays.
    try: msg = bytes(msg).decode(errors='replace')
    except (TypeError, ValueError): msg = repr(msg)
  if not isinstance(msg, str): msg = str(msg)

  if 'EXIT_CODE' in record: # systemd's process exit message, e.g. "Main process exited, code=exited, status=1/FAILURE".
    ok = (record.get('EXIT_CODE') == 'exited' and str(record.get('EXIT_STATUS')) == '0')
    return Event(unit=unit, kind='exit', text=msg, msg=msg, ok=ok)

  job_result = record.get('JOB_RESULT')
  if isinstance(job_result, str) and job_result not in ('done', 'skipped'):
    return Event(unit=unit, kind='fail', text=msg, msg=msg)

  level = level_for_priority(record.get('PRIORITY'))
  text = msg
  is_pithy = False
  if msg.startswith('{') and msg.endswith('}'): # Pithy JSON log line.
    try: parsed = parse_json(msg)
    except Exception: parsed = None
    if isinstance(parsed, dict):
      is_pithy = True
      message_key = message_keys.get(unit, '_') if message_keys is not None else '_'
      msg = str(parsed.get(message_key, ''))
      if message_key != '_': parsed.pop(message_key, None)
      parsed['_'] = msg
      parsed['level'] = level
      try: text = render_log_record_as_text(parsed, infer_journald=False)
      except Exception: pass
  if not is_pithy and level in ('warn', 'error'):
    color = TXT_Y if level == 'warn' else TXT_R
    text = f'{color}{level}{RST}: {msg}'
  kind = level if level in ('warn', 'error') else 'info'
  return Event(unit=unit, kind=kind, text=text, msg=msg)


def level_for_priority(priority:Any) -> str:
  try: p = int(priority)
  except (TypeError, ValueError): return 'info'
  if p <= 3: return 'error'
  if p == 4: return 'warn'
  return 'info'


if __name__ == '__main__': main()
