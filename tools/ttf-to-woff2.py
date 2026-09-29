#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from io import BytesIO
from pathlib import Path

from fontTools.ttLib import TTLibError
from fontTools.ttLib.woff2 import compress
from pithy.cmdparse import Cmd, pos


class TtfToWoff2(Cmd):
  'Compress a TTF to a sibling WOFF2 file, preserving all glyphs and variable font axes. Requires FontTools and Brotli.'

  ttf:str = pos(doc='Input .ttf file. The output has the same name with a .woff2 extension.')


def main() -> None:
  args = TtfToWoff2.parse_or_exit()
  source = Path(args.ttf)
  if source.suffix.lower() != '.ttf': raise SystemExit(f'Expected a .ttf file: {source}')
  output = source.with_suffix('.woff2')
  try:
    # Finish compression before writing, so conversion errors do not truncate an existing output.
    buffer = BytesIO()
    compress(source, buffer)
    output.write_bytes(buffer.getvalue())
  except (OSError, TTLibError, ImportError) as exc:
    raise SystemExit(f'Could not convert {source}: {exc}') from None
  print(output)


if __name__ == '__main__': main()
