# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import argv, stdin, stdout

from pithy.json.fmt import write_formatted_json_bytes


def main() -> None:
  out_raw = stdout.buffer
  args = argv[1:]
  if args:
    for path in args:
      with open(path, 'rb') as f:
        write_formatted_json_bytes(out_raw, f)
  else:
    in_raw = stdin.buffer
    write_formatted_json_bytes(out_raw, in_raw)


if __name__ == '__main__': main()
