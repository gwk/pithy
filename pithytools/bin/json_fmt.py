# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import argv, stdin, stdout

from pithy.json import format_json_bytes


def main() -> None:
  out_raw = stdout.buffer
  args = argv[1:]
  if args:
    for path in args:
      with open(path, 'rb') as f:
        format_json_bytes(f, out_raw)
  else:
    in_raw = stdin.buffer
    format_json_bytes(in_raw, out_raw)


if __name__ == '__main__': main()
