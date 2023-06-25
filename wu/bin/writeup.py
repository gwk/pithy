# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from sys import stdin, stdout

from pithy.io import errSL

from .. import default_css, default_js, minify_css, minify_js, writeup, writeup_dependencies


__all__ = ['main', 'writeup', 'writeup_dependencies']


SrcLine = tuple[int, str]


def main() -> None:
  arg_parser = ArgumentParser(prog='writeup', description='Converts .wu files to html.')
  arg_parser.add_argument('src_path', nargs='?', help='Input .wu source path; defaults to <stdin>.')
  arg_parser.add_argument('dst_path', nargs='?', help='Output path: defaults to <stdout>.')
  arg_parser.add_argument('-deps', action='store_true',
    help='Print external file dependencies of the input, one per line. Does not output HTML.')
  arg_parser.add_argument('-css-paths', nargs='+', default=(), help='paths to CSS.')
  arg_parser.add_argument('-no-css', action='store_true', help='Omit default CSS.')
  arg_parser.add_argument('-no-js', action='store_true', help='Omit default Javascript.')
  arg_parser.add_argument('-bare', action='store_true', help='Omit the top-level HTML document structure.')
  arg_parser.add_argument('-section', help='Emit only the specified section.')
  arg_parser.add_argument('-dbg', action='store_true', help='print debug info.')

  args = arg_parser.parse_args()

  if args.src_path == '': exit('source path cannot be empty string.')
  if args.dst_path == '': exit('destination path cannot be empty string.')
  if args.src_path == args.dst_path and args.src_path is not None:
    exit(f'source path and destination path cannot be the same path: {args.src_path!r}')

  try:
    f_in  = open(args.src_path) if args.src_path else stdin
    f_out = open(args.dst_path, 'w') if args.dst_path else stdout
  except FileNotFoundError as e: exit(f'writeup error: file does not exist: {e.filename}')
  src_path = f_in.name

  if f_in == stdin and f_in.isatty():
    errSL('writeup: reading from stdin...')

  if args.deps:
    dependencies = writeup_dependencies(
      src_path=src_path,
      text_lines=f_in,
      emit_dbg=args.dbg,
    )
    for dep in dependencies:
      print(dep, file=f_out)
    exit(0)

  css_blocks = [] if (args.bare or args.no_css) else [default_css]
  for path in args.css_paths:
    try:
      with open(path) as f:
        css_blocks.append(f.read())
    except FileNotFoundError:
      exit(f'writeup: css file does not exist: {path!r}')

  else:
    html_lines_gen = writeup(
      src_path=src_path,
      src_lines=enumerate(f_in),
      description='', # TODO.
      author='', # TODO.
      css_lines=minify_css(css_blocks),
      js=(None if args.bare or args.no_js else minify_js(default_js)),
      emit_doc=(not args.bare),
      target_section=args.section,
      emit_dbg=args.dbg,
    )
    for line in html_lines_gen:
      print(line, file=f_out)


if __name__ == '__main__': main()
