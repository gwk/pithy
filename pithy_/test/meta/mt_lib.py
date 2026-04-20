# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from importlib.machinery import ModuleSpec

from pithy.meta import caller_module_name, caller_module_spec


test_caller_module_info:list[tuple[str|None,ModuleSpec]] = []

def test_meta_module_spec() -> None:
  name = caller_module_name(1)
  spec = caller_module_spec(1)
  test_caller_module_info.append((name, spec))
