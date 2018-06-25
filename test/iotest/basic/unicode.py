#!/usr/bin/env python3

from pithy.io import outL, errL
import locale

errL("locale: ", locale.getpreferredencoding(do_setlocale=True))
errL('…')
outL('…')
