#!/usr/bin/env python3

from utest import *
from urllib.parse import urlsplit
from pithy.path_encode import *


# Demonstrate the behavior of urlsplit.

parts = urlsplit('scheme://host/dir/name?query=1&r=2#fragment')
utest_val('scheme',       parts.scheme) # ':' suffix removed.
utest_val('host',         parts.netloc) # '//' prefix removed.
utest_val('/dir/name',    parts.path)
utest_val('query=1&r=2',  parts.query) # '?' prefix removed.
utest_val('fragment',     parts.fragment) # '#' prefix removed.

# URLs with path only.

parts = urlsplit('path')
utest_val('',     parts.netloc)
utest_val('path', parts.path)

parts = urlsplit('path/')
utest_val('',       parts.netloc)
utest_val('path/',  parts.path)

parts = urlsplit('/path')
utest_val('',       parts.netloc)
utest_val('/path',  parts.path)

parts = urlsplit('d.com/path')
utest_val('d.com/path', parts.path) # '.com' suffix has no effect.

# URL with scheme and path.
parts = urlsplit('scheme:path')
utest_val('scheme', parts.scheme)
utest_val('', parts.netloc)
utest_val('path', parts.path)

# URL with host (netloc).
parts = urlsplit('//host')
utest_val('', parts.scheme)
utest_val('host', parts.netloc)
utest_val('', parts.path)


parts = urlsplit('scheme://')
utest_val('scheme', parts.scheme)
utest_val('', parts.netloc)
utest_val('', parts.path)

parts = urlsplit('scheme://host/')
utest_val('scheme', parts.scheme)
utest_val('host', parts.netloc)
utest_val('/', parts.path)

utest('+/+', path_for_url, 'scheme://')

utest('scheme/host/path', path_for_url, 'scheme://host/path', scheme=COMP)
utest('host/path,', path_for_url, '//host/path/')

utest('scheme+3a,,host/path', path_for_url, 'scheme://host/path', scheme=COMP, host=SQUASH)

