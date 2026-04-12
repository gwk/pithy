# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import argv, stdin, stdout

from pithy.json.fmt import write_formatted_json_bytes


def main() -> None:
  out_raw = stdout.buffer
  args = argv[1:]
  if not args:
    args = ['-']
  for path in args:
    if path == '-':
      f = stdin.buffer
    else:
      f = open(path, 'rb')
    with f:
      write_formatted_json_bytes(out_raw, f, fix=False)


if __name__ == '__main__': main()
