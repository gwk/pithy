# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from logging import LogRecord

from pithy.ansi import RST, TXT_G, TXT_N
from pithy.logs import PithyLogFormatter, render_log_fn, render_log_journal, render_log_json, render_log_record_as_text
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
