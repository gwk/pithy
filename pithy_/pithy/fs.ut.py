# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.fs import name_has_any_ext
from utest import utest


utest(True, name_has_any_ext, 'a', frozenset())
utest(True, name_has_any_ext, '.a', frozenset())
utest(True, name_has_any_ext, 'a.e', frozenset(['.e']))
utest(True, name_has_any_ext, '.a.e', frozenset(['.e']))
utest(True, name_has_any_ext, 'a.f', frozenset(['.e', '.f']))
utest(True, name_has_any_ext, 'a.e.f', frozenset(['.f']))
utest(True, name_has_any_ext, 'a.e.f', frozenset(['.e.f']))

utest(False, name_has_any_ext, 'a', frozenset(['.e']))
utest(False, name_has_any_ext, 'a.b', frozenset(['.e']))
utest(False, name_has_any_ext, '.e', frozenset(['.e']))
utest(False, name_has_any_ext, 'a.e.f', frozenset(['.e']))
