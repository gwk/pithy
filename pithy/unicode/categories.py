# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Counter, Dict, List, NamedTuple


class UnicodeCategory(NamedTuple):
  key:str
  name:str
  desc:str
  subcategories:tuple[str, ...]


def _mk_cat(key:str, name:str, desc:str) -> UnicodeCategory:
  subs = desc.split(' | ')
  return UnicodeCategory(key=key, name=name, desc=desc, subcategories=tuple(subs if len(subs) > 1 else []))


unicode_categories:List[UnicodeCategory] = [ # taken directly from: http://www.unicode.org/reports/tr44/#General_Category_Values.
  _mk_cat('Lu', 'Uppercase_Letter',      'An uppercase letter'),
  _mk_cat('Ll', 'Lowercase_Letter',      'A lowercase letter'),
  _mk_cat('Lt', 'Titlecase_Letter',      'A digraphic character, with first part uppercase'),
  _mk_cat('LC', 'Cased_Letter',          'Lu | Ll | Lt'),
  _mk_cat('Lm', 'Modifier_Letter',       'A modifier letter'),
  _mk_cat('Lo', 'Other_Letter',          'other letters, including syllables and ideographs'),
  _mk_cat('L',  'Letter',                'Lu | Ll | Lt | Lm | Lo'),
  _mk_cat('Mn', 'Nonspacing_Mark',       'A nonspacing combining mark (zero advance width)'),
  _mk_cat('Mc', 'Spacing_Mark',          'A spacing combining mark (positive advance width)'),
  _mk_cat('Me', 'Enclosing_Mark',        'An enclosing combining mark'),
  _mk_cat('M',  'Mark',                  'Mn | Mc | Me'),
  _mk_cat('Nd', 'Decimal_Number',        'A decimal digit'),
  _mk_cat('Nl', 'Letter_Number',         'A letterlike numeric character'),
  _mk_cat('No', 'Other_Number',          'A numeric character of other type'),
  _mk_cat('N',  'Number',                'Nd | Nl | No'),
  _mk_cat('Pc', 'Connector_Punctuation', 'A connecting punctuation mark, like a tie'),
  _mk_cat('Pd', 'Dash_Punctuation',      'A dash or hyphen punctuation mark'),
  _mk_cat('Ps', 'Open_Punctuation',      'An opening punctuation mark (of a pair)'),
  _mk_cat('Pe', 'Close_Punctuation',     'A closing punctuation mark (of a pair)'),
  _mk_cat('Pi', 'Initial_Punctuation',   'An initial quotation mark'),
  _mk_cat('Pf', 'Final_Punctuation',     'A final quotation mark'),
  _mk_cat('Po', 'Other_Punctuation',     'A punctuation mark of other type'),
  _mk_cat('P',  'Punctuation',           'Pc | Pd | Ps | Pe | Pi | Pf | Po'),
  _mk_cat('Sm', 'Math_Symbol',           'A symbol of mathematical use'),
  _mk_cat('Sc', 'Currency_Symbol',       'A currency sign'),
  _mk_cat('Sk', 'Modifier_Symbol',       'A non-letterlike modifier symbol'),
  _mk_cat('So', 'Other_Symbol',          'A symbol of other type'),
  _mk_cat('S',  'Symbol',                'Sm | Sc | Sk | So'),
  _mk_cat('Zs', 'Space_Separator',       'A space character (of various non-zero widths)'),
  _mk_cat('Zl', 'Line_Separator',        'U+2028 LINE SEPARATOR only'),
  _mk_cat('Zp', 'Paragraph_Separator',   'U+2029 PARAGRAPH SEPARATOR only'),
  _mk_cat('Z',  'Separator',             'Zs | Zl | Zp'),
  _mk_cat('Cc', 'Control',               'A C0 or C1 control code'),
  _mk_cat('Cf', 'Format',                'A format control character'),
  _mk_cat('Cs', 'Surrogate',             'A surrogate code point'),
  _mk_cat('Co', 'Private_Use',           'A private-use character'),
  _mk_cat('Cn', 'Unassigned',            'A reserved unassigned code point or a noncharacter'),
  _mk_cat('C',  'Other',                 'Cc | Cf | Cs | Co | Cn'),
  _mk_cat('CE', 'Other_Encodable',       'Cc | Cf | Co | Cn'), # This category is a Legs invention; excludes unencodable surrogates.
]


unicode_category_aliases:Dict[str,UnicodeCategory] = { cat.key : cat for cat in unicode_categories }

def _add_aliases() -> None:
  unicode_category_aliases.update((cat.name, cat) for cat in unicode_categories)
  # add first-word aliases wherever they are unambiguous.
  first_word_counts:Counter[str] = Counter()
  first_word_categories = {}
  for cat in unicode_categories:
    first = cat.name.partition('_')[0]
    if first in unicode_category_aliases: continue
    first_word_counts[first] += 1
    first_word_categories[first] = cat
  unicode_category_aliases.update(p for p in first_word_categories.items() if first_word_counts[p[0]] == 1)

_add_aliases()
