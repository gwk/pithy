# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from json import loads as parse_json
from sys import stdin, stdout

from pithy.logs import render_log_text


def main() -> None:
  'Read pithy JSON log lines from stdin and render them as human-readable text.'
  for line in stdin:
    line = line.strip()
    if not line: continue
    try:
      record = parse_json(line)
    except Exception:
      stdout.write(line + '\n')
      continue
    if not isinstance(record, dict):
      stdout.write(line + '\n')
      continue
    stdout.write(fmt_record(record) + '\n')
  stdout.flush()


def fmt_record(record:dict) -> str:
  'Format a JSON log record as human-readable text.'
  level = record.get('level', 'error')
  msg = record.get('_', '')
  exc_lines:list[str] = record.get('exc', [])
  kwargs = {k:v for k, v in record.items() if k not in ('level', '_', 'exc')}
  # Note: exc is stored as pre-formatted lines in JSON, so we pass it separately rather than as a BaseException.
  text = render_log_text(level, msg, **kwargs)
  if exc_lines:
    text += '\n' + ''.join(exc_lines)
  return text


if __name__ == '__main__': main()
