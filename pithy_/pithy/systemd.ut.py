# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import environ, fstat
from socket import AF_UNIX, SOCK_DGRAM, socket
from sys import stderr
from tempfile import TemporaryDirectory

from pithy.systemd import is_journal_stream, sd_notify, sd_notify_ready
from utest import utest, utest_val


with TemporaryDirectory() as tmp_dir:

  # Journal stream detection compares JOURNAL_STREAM against the file's device and inode.
  with open(f'{tmp_dir}/stream', 'w') as f:
    st = fstat(f.fileno())
    environ.pop('JOURNAL_STREAM', None)
    utest(False, is_journal_stream, f)
    environ['JOURNAL_STREAM'] = f'{st.st_dev}:{st.st_ino}'
    utest(True, is_journal_stream, f)
    environ['JOURNAL_STREAM'] = f'{st.st_dev}:{st.st_ino + 1}'
    utest(False, is_journal_stream, f)
    environ['JOURNAL_STREAM'] = 'garbage'
    utest(False, is_journal_stream, f)
    del environ['JOURNAL_STREAM']

  # sd_notify is a no-op without NOTIFY_SOCKET, and otherwise sends a datagram to the socket.
  environ.pop('NOTIFY_SOCKET', None)
  utest(False, sd_notify_ready)

  path = f'{tmp_dir}/notify'
  with socket(AF_UNIX, SOCK_DGRAM) as server:
    try: server.bind(path)
    except PermissionError as e: # Some sandboxes forbid binding unix sockets.
      print(f'systemd.ut: skipping sd_notify socket test; bind failed: {e}', file=stderr)
      exit(0)
    server.settimeout(2)
    environ['NOTIFY_SOCKET'] = path
    utest(True, sd_notify_ready)
    utest_val(b'READY=1', server.recv(64), 'ready datagram')
    utest(True, sd_notify, 'STATUS=working\nWATCHDOG=1')
    utest_val(b'STATUS=working\nWATCHDOG=1', server.recv(64), 'multi-line datagram')
    del environ['NOTIFY_SOCKET']
