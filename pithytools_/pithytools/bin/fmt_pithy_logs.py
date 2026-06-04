# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from json import loads as parse_json
from sys import stdin, stdout

from pithy.io import errL
from pithy.logs import render_log_record_as_text


def main() -> None:
  'Read pithy JSON log lines from stdin and render them as human-readable text.'
  for line in stdin:
    line = line.strip()
    if not line: continue
    try:
      record = parse_json(line)
    except Exception as e:
      errL(f'failed to parse log line as JSON: {e}\n', line)
      continue
    if not isinstance(record, dict):
      stdout.write(line + '\n')
      continue
    try:
      text = render_log_record_as_text(record)
    except Exception as e:
      errL(f'failed to render log record: {e}\n', line)
      continue
    stdout.write(text + '\n')
  stdout.flush()


if __name__ == '__main__': main()
