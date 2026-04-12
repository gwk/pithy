# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sys

from ...fs import is_dir, real_path


def pithy_web_static_dir_path() -> str:
  static_module_path = sys.modules[__name__].__path__[0]
  module_dir = real_path(static_module_path)
  assert is_dir(module_dir, follow=False), module_dir
  return module_dir
