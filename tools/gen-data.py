#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# official data is found here: http://www.unicode.org/Public/zipped/9.0.0/UCD.zip

from argparse import ArgumentParser
from itertools import chain
from os.path import join as path_join
from sys import stderr
from typing import DefaultDict, Dict, Iterator, List, NamedTuple, Tuple

from pithy.unicode import coalesce_sorted_ranges


CodeRange = Tuple[int,int]


def main() -> None:
  parser = ArgumentParser()
  parser.add_argument('source_dir')

  args = parser.parse_args()

  data_path       = path_join(args.source_dir, 'UnicodeData.txt')
  blocks_path     = path_join(args.source_dir, 'Blocks.txt')
  categories_path = path_join(args.source_dir, 'extracted', 'DerivedGeneralCategory.txt')
  east_asian_path = path_join(args.source_dir, 'extracted', 'DerivedEastAsianWidth.txt')

  block_names_to_codes = { name.replace(' ', '_').replace('-', '_') : codes for codes, (name,) in parse_rows(blocks_path) }

  print('# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.')
  print('# Derived from data published by the Unicode Consortium; see: http://unicode.org/copyright.html.')
  print('# Generated by github.com/gwk/pithy tools/gen-data.py.')
  print('# Source directory: {}.'.format(args.source_dir))
  print()
  print('from typing import Dict, List, Tuple')
  print('\n')

  print('blocks: Dict[str, Tuple[int, int]] = {')
  for name, codes in sorted(block_names_to_codes.items(), key=lambda p: p[1]):
    print('  {!r}: {},'.format(name, repr_pair(codes)))
  print('}\n\n')

  category_ranges = DefaultDict[str,List[CodeRange]](list)
  for codes, (cat,) in parse_rows(categories_path):
    category_ranges[cat].append(codes)

  print('category_ranges: Dict[str, Tuple[Tuple[int, int], ...]] = {')
  for cat, codes_seq in sorted(category_ranges.items()):
    print('  {!r}: ('.format(cat), end='')
    for i, codes in enumerate(codes_seq):
       print((' ' if i % 4 else '\n    '), repr_pair(codes), ',', sep='', end='')
    print('\n  ),\n')
  print('}\n\n')

  # verify that the category ranges cover the entire space.
  all_ranges = sorted(chain(*category_ranges.values()))
  coalesced_range = tuple(coalesce_sorted_ranges(all_ranges))
  assert len(coalesced_range) == 1 and coalesced_range[0] == (0, 0x110000)

# Generate terminal double width ranges.
  east_asian_widths_to_codes = DefaultDict[str,List[CodeRange]](list)
  double_codes = []
  for codes, (width,) in parse_rows(east_asian_path):
    if width == 'N': continue # this is the default for omitted codes, but also appears often in the table.
    east_asian_widths_to_codes[width].append(codes)
    if width in ('F', 'W'):
      double_codes.append(codes)
  double_codes.sort()

  print("double_width_codes: List[Tuple[int, int]] = [ # Code points with East Asian Width 'W' or 'F'.", end='')
  for i, codes in enumerate(coalesce_sorted_ranges(double_codes)):
    print((' ' if i % 4 else '\n  '), repr_pair(codes), ',', sep='', end='')
  print('\n]')

  data = parse_data(data_path)


Row = Tuple[CodeRange, Tuple[str,...]]

def parse_rows(path:str) -> Iterator[Row]:
  for line in open(path):
    line, _, _ = line.partition('#')
    line = line.strip()
    if not line: continue
    els = line.split(';')
    yield (parse_codes(els[0]), tuple(el.strip() for el in els[1:]))


def parse_codes(string:str) -> CodeRange:
    low, dots, high = string.partition('..')
    l = int(low, base=16)
    if dots: return (l, int(high, base=16) + 1) # add one to produce end index.
    else: return (l, l + 1)


def repr_pair(pair:CodeRange) -> str:
  return '(0x{:04X}, 0x{:04X})'.format(*pair)


def parse_data(path:str) -> Dict[int,'CharInfo']:
  d = {}
  for line in open(path):
    row = line.split(';')
    code_str, name, cat, comb, bidi, decomp, decimal, digit, numeric, mirror, _, _, upper, lower, title = row
    code = int(code_str, base=16)
    info = CharInfo(code, name, cat, comb, bidi, decomp, decimal, digit, numeric, mirror, upper, lower, title)
    d[code] = info
  return d


class CharInfo(NamedTuple):
  code:int
  name:str
  cat:str
  comb:str
  bidi:str
  decomp:str
  decimal:str
  digit:str
  numeric:str
  mirror:str
  upper:str
  lower:str
  title:str


if __name__ == '__main__': main()


# UnicodeData.txt columns, taken from http://www.unicode.org/reports/tr44/#UnicodeData.txt.

# 1: Name M N. These names match exactly the names published in the code charts of the Unicode Standard. The derived Hangul Syllable names are omitted from this file; see Jamo.txt for their derivation.

# 2: General_Category E N. This is a useful breakdown into various character types which can be used as a default categorization in implementations. For the property values, see General Category Values.

# 3: Canonical_Combining_Class N N. The classes used for the Canonical Ordering Algorithm in the Unicode Standard. This property could be considered either an enumerated property or a numeric property: the principal use of the property is in terms of the numeric values. For the property value names associated with different numeric values, see DerivedCombiningClass.txt and Canonical Combining Class Values.

# 4: Bidi_Class E N. These are the categories required by the Unicode Bidirectional Algorithm. For the property values, see Bidirectional Class Values. For more information, see Unicode Standard Annex #9, "Unicode Bidirectional Algorithm" [UAX9]. The default property values depend on the code point, and are explained in DerivedBidiClass.txt

# 5: Decomposition_Type, Decomposition_Mapping E/S N. This field contains both values, with the type in angle brackets. The decomposition mappings exactly match the decomposition mappings published with the character names in the Unicode Standard. For more information, see Character Decomposition Mappings.

# 6: Numeric_Type/Numeric_Value E/N N. If the character has the property value Numeric_Type=Decimal, then the Numeric_Value of that digit is represented with an integer value (limited to the range 0..9) in fields 6, 7, and 8. Characters with the property value Numeric_Type=Decimal are restricted to digits which can be used in a decimal radix positional numeral system and which are encoded in the standard in a contiguous ascending range 0..9. See the discussion of decimal digits in Chapter 4, Character Properties in [Unicode].

# 7: Numeric_Type/Numeric_Value E/N N. If the character has the property value Numeric_Type=Digit, then the Numeric_Value of that digit is represented with an integer value (limited to the range 0..9) in fields 7 and 8, and field 6 is null. This covers digits that need special handling, such as the compatibility superscript digits. Starting with Unicode 6.3.0, no newly encoded numeric characters will be given Numeric_Type=Digit, nor will existing characters with Numeric_Type=Numeric be changed to Numeric_Type=Digit. The distinction between those two types is not considered useful.

 # 8: Numeric_Type/Numeric_Value E/N N. If the character has the property value Numeric_Type=Numeric, then the Numeric_Value of that character is represented with a positive or negative integer or rational number in this field, and fields 6 and 7 are null. This includes fractions such as, for example, "1/5" for U+2155 VULGAR FRACTION ONE FIFTH. Some characters have these properties based on values from the Unihan data files. See Numeric_Type, Han.

# 9: Bidi_Mirrored B N. If the character is a "mirrored" character in bidirectional text, this field has the value "Y"; otherwise "N". See Section 4.7, Bidi Mirrored of [Unicode]. Do not confuse this with the Bidi_Mirroring_Glyph property.

# 10: Unicode_1_Name (Obsolete as of 6.2.0).

# 11: ISO_Comment (Obsolete as of 5.2.0; Deprecated and Stabilized as of 6.0.0).

# 12: Simple_Uppercase_Mapping S N. Simple uppercase mapping (single character result). If a character is part of an alphabet with case distinctions, and has a simple uppercase equivalent, then the uppercase equivalent is in this field. The simple mappings have a single character result, where the full mappings may have multi-character results. For more information, see Case and Case Mapping.

# 13: Simple_Lowercase_Mapping S N. Simple lowercase mapping (single character result).

# 14: Simple_Titlecase_Mapping S N. Simple titlecase mapping (single character result). Note: If this field is null, then the Simple_Titlecase_Mapping is the same as the Simple_Uppercase_Mapping for this character.
