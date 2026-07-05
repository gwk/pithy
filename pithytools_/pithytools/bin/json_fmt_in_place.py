# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser

from pithy.fs import walk_files
from pithy.io import errL
from pithy.json.fmt import write_formatted_json_bytes


def main() -> None:
  parser = ArgumentParser(description='Format JSON files in place.')
  parser.add_argument('paths', nargs='*', help='paths to search for JSON files; directories are walked recursively.')
  parser.add_argument('-fix', action='store_true', help='fix malformed JSON (missing/extra commas; comments).')
  parser.add_argument('-trailing-commas', action='store_true', help='allow trailing commas in fixed output.')
  parser.add_argument('-comments', action='store_true', help='preserve comments instead of stripping them.')
  args = parser.parse_args()

  for path in walk_files(*args.paths, file_exts=['.json', '.jsonc']):
    print(path)
    try:
      with open(path, 'rb') as f_in:
        input = f_in.read()
      with open(path, 'wb') as f_out:
        write_formatted_json_bytes(f_out, input, fix=args.fix, allow_trailing_commas=args.trailing_commas,
          allow_comments=args.comments)
    except Exception as e:
      errL(f'error: {path}: {e}')


if __name__ == '__main__': main()
