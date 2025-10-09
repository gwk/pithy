# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from time import time as now
from typing import Callable

from pithy.fs import file_size, path_exists, remove_path
from pithy.io import confirm, outL, outZ, stderr, stdin
from pithy.string import format_byte_count
from pithy.task import run, UnexpectedExit


PackFn = Callable[[str, str], None]


def main() -> None:
  parser = ArgumentParser(description='Compress files.')
  parser.add_argument('-overwrite', action='store_true', help='remove any existing archive file before writing.')
  parser.add_argument('-quiet', action='store_true', help='do not print compression statistics.')
  parser.add_argument('-level', help='compression level (format specific).')
  parser.add_argument('-br',  action='store_true', help='compress using brotli.')
  parser.add_argument('-gz',  action='store_true', help='compress using gzip.')
  parser.add_argument('-xz',  action='store_true', help='compress using xz.')
  parser.add_argument('-zst', action='store_true', help='compress using zstd.')
  parser.add_argument('paths', nargs='+', help='Paths to pack.')
  args = parser.parse_args()

  if not any((args.br, args.gz, args.xz, args.zst)):
    exit(f'error: please specify at least one compression format: {format_flags}.')

  show_stats = not args.quiet
  kwargs = dict(overwrite=args.overwrite, level=args.level, show_stats=show_stats)
  for path in args.paths:
    if args.br:   pack(path, ext='.br', **kwargs)
    if args.gz:   pack(path, ext='.gz', **kwargs)
    if args.xz:   pack(path, ext='.xz', **kwargs)
    if args.zst:  pack(path, ext='.zst', **kwargs)


def pack(path:str, ext:str, overwrite:bool, level:str|None, show_stats:bool) -> None:
  dst = path + ext
  pack_fn = formats[ext]
  if path_exists(dst, follow=False):
    if not overwrite:
      if stdin.isatty():
        if not confirm(f'archive path {dst!r} exists; remove it?'): exit(1)
      else:
        exit(f'archive path exists: {dst!r}')
    remove_path(dst)
  if show_stats: outZ(dst, ':')
  try:
    start = now()
    pack_fn(path, level=level)
    duration = now() - start
  except Exception as e:
    if show_stats: outL()
    if isinstance(e, UnexpectedExit): exit(1)
    else: raise
  else:
    orig_size = file_size(path)
    pack_size = file_size(dst)
    ratio = (pack_size / orig_size) if orig_size else 0.0
    if show_stats: outL(f' {format_byte_count(orig_size)} -> {format_byte_count(pack_size)} ({ratio:.0%}; {duration:0.2f}s)')


def br(path:str, level:str|None=None) -> None:
  if not level: level = '5'
  run(['brotli', '--keep', f'-{level}', path])

def gz(path:str, level:str|None=None) -> None:
  if not level: level = '5'
  run(['gzip', '--keep', f'-{level}', path])

def xz(path:str, level:str|None=None) -> None:
  if not level: level = '4'
  run(['xz', '--keep', f'-{level}', '--threads=0', path])

def zst(path:str, level:str|None=None) -> None:
  if not level: level = '6'
  run(['zstd', '--keep', f'-{level}', '--threads=0', '-q', path], err=stderr)


formats = {
  '.br'  : br,
  '.gz'  : gz,
  '.xz'  : xz,
  '.zst' : zst,
}

format_flags = ', '.join(ext.replace('.', '-') for ext in formats)
