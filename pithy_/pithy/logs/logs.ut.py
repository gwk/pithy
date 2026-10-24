# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from io import StringIO
from logging import LogRecord
from typing import cast
from unittest.mock import patch

from pithy.ansi import RST, TXT_G, TXT_N
from pithy.logs import (adjust_log_level, log, LogLevel, PithyLogFormatter, render_log_fn, render_log_journal, render_log_json,
  render_log_record_as_text)
from utest import utest


utest('{"level":"info","_":"hi","n":1}', render_log_json, 'info', 'hi', n=1)

# The journal renderer prefixes the JSON with the syslog priority.
utest('<7>{"level":"debug","_":"d"}', render_log_journal, 'debug', 'd')
utest('<6>{"level":"info","_":"i"}', render_log_journal, 'info', 'i')
utest('<4>{"level":"warn","_":"w"}', render_log_journal, 'warn', 'w')
utest('<3>{"level":"error","_":"e","k":"v"}', render_log_journal, 'error', 'e', k='v')
utest('<5>{"level":"other","_":"o"}', render_log_journal, 'other', 'o')

# A stored JSON record renders back to text.
utest(f'{TXT_G}info{RST}: hi  {TXT_N}n{RST}:1', render_log_record_as_text, '{"level":"info","_":"hi","n":1}')

# Standard logging accepts arbitrary message objects and converts them to strings.
exc = OSError(48, 'Address already in use')
record = LogRecord('test', 40, __file__, 1, exc, (), None)
utest(render_log_fn('error', str(exc)), PithyLogFormatter().format, record)


# The level-parameterized log function respects the logging level threshold like the fixed-level functions.
def captured_log(level:str, message:str, threshold:LogLevel) -> str:
  output = StringIO()
  with redirect_stdout(output), adjust_log_level(threshold), patch('pithy.logs.render_log_fn', render_log_json):
    log(cast(LogLevel, level), message)
  return output.getvalue()

utest('{"level":"info","_":"m"}\n', captured_log, 'info', 'm', 'info')
utest('', captured_log, 'info', 'm', 'error')
utest('{"level":"error","_":"m"}\n', captured_log, 'error', 'm', 'error')
utest('', captured_log, 'error', 'm', 'silent')
utest('{"level":"error","_":"Invalid log level: \'loud\'."}\n{"level":"error","_":"m"}\n', captured_log, 'loud', 'm', 'error')
