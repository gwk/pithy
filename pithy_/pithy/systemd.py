# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Minimal systemd integration for services: journal stream detection and sd_notify, without depending on libsystemd.
'''

from os import environ, fstat
from socket import AF_UNIX, SOCK_DGRAM, socket
from sys import stdout
from typing import Any, IO


def is_journal_stream(f:IO[Any]=stdout) -> bool:
  '''
  Return True if `f` is connected directly to the systemd journal.
  When a service's stdout or stderr is connected to the journal,
  systemd sets JOURNAL_STREAM to the "device:inode" of the connection socket; see systemd.exec(5).
  Comparing against fstat of `f` guards against the variable being inherited by a child whose output was redirected.
  '''
  spec = environ.get('JOURNAL_STREAM')
  if not spec: return False
  try:
    dev, ino = spec.split(':', 1)
    st = fstat(f.fileno())
  except (AttributeError, OSError, ValueError): return False
  return dev == str(st.st_dev) and ino == str(st.st_ino)


def sd_notify(state:str) -> bool:
  '''
  Send a state notification to the systemd service manager; see sd_notify(3).
  `state` is a newline-separated list of assignments, e.g. 'READY=1'.
  Returns False if NOTIFY_SOCKET is not set, i.e. the process is not running under a unit with Type=notify.
  '''
  addr = environ.get('NOTIFY_SOCKET')
  if not addr: return False
  if addr.startswith('@'): addr = '\0' + addr[1:] # Abstract socket namespace.
  with socket(AF_UNIX, SOCK_DGRAM) as sock:
    sock.connect(addr)
    sock.sendall(state.encode())
  return True


def sd_notify_ready() -> bool:
  'Tell systemd that service startup is complete; a Type=notify unit is not active until this is sent.'
  return sd_notify('READY=1')


def sd_notify_watchdog() -> bool:
  'Pet the systemd watchdog; required periodically when the unit sets WatchdogSec.'
  return sd_notify('WATCHDOG=1')
