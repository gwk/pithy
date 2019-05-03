# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
HTML tools.
'''

from . import semantics
from ..xml import Xml


class Html(Xml):

  type_name = 'Html'
  void_elements = semantics.void_elements
  ws_sensitive_tags = semantics.ws_sensitive_elements
