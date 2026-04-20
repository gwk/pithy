#!/usr/bin/env python3

from locale import getpreferredencoding
from sys import stderr


print("locale:", getpreferredencoding(do_setlocale=True), file=stderr)
print('…', file=stderr)
print('…')
