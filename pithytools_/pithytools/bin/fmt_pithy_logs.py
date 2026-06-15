# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import nullcontext
from json import loads as parse_json
from sys import stdin, stdout

from pithy.logs import render_log_record_as_text
from pithy.term import CBreakMode


def main() -> None:
  'Read pithy JSON log lines from stdin and render them as human-readable text.'
  # When stdin is an interactive terminal, canonical input mode truncates long pasted lines at the
  # terminal's MAX_CANON limit. CBreakMode disables canonical mode so that long lines are received intact.
  ctx = CBreakMode() if stdin.isatty() else nullcontext()
  with ctx:
    for line in stdin:
      if line := line.strip():
        format_line(line)
      else:
        stdout.write('\n')
  stdout.flush()


def format_line(line:str) -> None:
  brace_idx = line.find('{')

  if brace_idx == -1 or not line.endswith('}'):
    stdout.write(line + '\n')
    return

  if brace_idx > 0:
    stdout.write(line[:brace_idx])

  json_text = line[brace_idx:]
  try:
    record = parse_json(json_text)
  except Exception as e:
    stdout.write(f'\nfailed to parse log line as JSON: {e}\n{json_text}\n')
    return
  if not isinstance(record, dict):
    stdout.write(json_text + '\n')
    return
  try:
    text = render_log_record_as_text(record)
  except Exception as e:
    stdout.write(f'\nfailed to render log record: {e}\n{json_text}\n')
    return
  stdout.write(text + '\n')


if __name__ == '__main__': main()
