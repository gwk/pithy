# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from re import compile as re_compile, Match
from typing import Callable, Iterator

from pithy.regex import find_matches_interleaved

from . import A


def linkify(text:str, transform:Callable[[str],str]|None=None) -> Iterator[A|str]:
  '''
  Create a link element if the text looks like it starts with a URL. Otherwise, return the plain text as-is.
  If the URL does not appear to span the entire text, create a link element with the entire text as its content.
  The whitespace, possibly preceded by the characters  `.,;:` terminate a URL.
  '''
  for part in find_matches_interleaved(linkify_re, text):
    if isinstance(part, Match):
      text = part[0]
      yield A(href=text, _=(transform(text) if transform else text))
    else:
      yield part



linkify_re = re_compile(r'''(?x)
( # Must recognize some leading signifier.
  [a-z][a-z0-9.]+:// # Protocol.
| ([\w-]+\.)+([a-z]{2,18})/ # Domain with TLD suffix. Require a trailing slash to avoid matching a filename. Alpha names only; ignores the 'xn--*' punycode names.
| (?<!\d) \d{1,3} \. \d{1,3} \. \d{1,3} \. \d{1,3} (?!=\d) # IPv4 address.
| localhost:\d+ # Localhost with port.
)
[^\s]*(?<![,.:;]) # Accept all non-whitespace characters except for some trailing punctuation.
''')
