# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re


def parse_nm_line(nm_line:str) -> tuple[str,str,str,tuple[str,...]]:
  '''
  'Given a string from the output of `nm <some.swift.o> -g -U -m -s __TEXT __text`, parse the output.
  This is very incomplete.
  '''

  words = nm_line.strip().split()
  addr, seg_sect = words[0:2]
  descriptors = ' '.join(words[2:-1])
  mangled = words[-1]
  return (addr, seg_sect, descriptors, demangle(mangled))


def demangle(mangled:str) -> tuple[str,...]:
  '''
  Demangle a swift symbol. This is very incomplete.
  Swift name mangling references:
  https://github.com/apple/swift/blob/main/docs/ABI/Mangling.rst
  https://github.com/apple/swift/blob/main/lib/Demangling/Demangler.cpp
  '''

  if not mangled.startswith('_$s'): return ()
  mangled = mangled.removeprefix('_$s')
  parts = []
  while m := re.match(r'_|\d+', mangled):
    g = m.group(0)
    if g == '_':
      part_len = 1
    else:
      part_len = int(m.group(0))
    part_start = m.end()
    part_end = part_start + part_len
    part = mangled[part_start:part_end]
    parts.append(part)
    mangled = mangled[part_end:]
  parts.append(mangled)
  return tuple(parts)


def test_main() -> None:

  test_lines = [
    '00000000000002d4 (__TEXT,__text) weak private external _$s5UTest5utest3exp__4file4line3colyx_xyKXKSSyXKs12StaticStringVS2utSQRzlFfA1_',
    '0000000000000318 (__TEXT,__text) weak private external _$s5UTest5utest3exp__4file4line3colyx_xyKXKSSyXKs12StaticStringVS2utSQRzlFfA1_SSycfu_',
    '0000000000000000 (__TEXT,__text) external [no dead strip] _$s9QuiltTest27testBidirectionalCollectionyyF',
    '0000000000000344 (__TEXT,__text) weak private external _$sS2SSKsWl',
    '00000000000002f0 (__TEXT,__text) weak private external _$sSJWOh',
  ]

  for test_line in test_lines:
    print('\ntest:', test_line)
    print(parse_nm_line(test_line))


if __name__ == '__main__': test_main()
