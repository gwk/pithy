# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from urllib.parse import urlsplit

from pithy.path_encode import COMP, OMIT, path_encode, path_for_url, SPLIT, SQUASH
from utest import utest, utest_exc, utest_val


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

# path_encode.
utest('', path_encode, '')
utest('+2e', path_encode, '.')
utest('+2e.', path_encode, '..')

# path_for_url.

m_squash = dict(scheme=COMP, host=SQUASH, path=SQUASH, query=SQUASH, fragment=SQUASH)
m_comp = dict(scheme=COMP, host=COMP, path=COMP, query=COMP, fragment=COMP)
m_split = dict(scheme=COMP, host=COMP, path=SPLIT, query=COMP, fragment=COMP)

utest(':,,',    path_for_url, '', **m_squash)
utest(':/,,/+',  path_for_url, '', **m_comp)
utest(':/,,/+',  path_for_url, '', **m_split)

utest(',,', path_for_url, '',   scheme=OMIT, host=COMP, path=SQUASH)
utest(',,/+', path_for_url, '', scheme=OMIT, host=SQUASH, path=COMP)

utest('path',   path_for_url, 'path', scheme=OMIT, host=OMIT, path=COMP)
utest(':path',  path_for_url, 'path', scheme=COMP, host=OMIT, path=SQUASH)
utest(':/path', path_for_url, 'path', scheme=COMP, host=OMIT, path=COMP)

utest(',path',   path_for_url, '/path', scheme=OMIT, host=OMIT, path=COMP)
utest(':,path',  path_for_url, '/path', scheme=COMP, host=OMIT, path=SQUASH)
utest(':/,path', path_for_url, '/path', scheme=COMP, host=OMIT, path=COMP)

utest('scheme:,,host,dir,file+3fquery+23fragment',
  path_for_url, 'scheme://host/dir/file?query#fragment', **m_squash)

utest('scheme:/host/dir,file/+3fquery/+23fragment',
  path_for_url, 'scheme://host/dir/file?query#fragment', **m_comp)

utest('scheme:/host/dir/file/+3fquery/+23fragment',
  path_for_url, 'scheme://host/dir/file?query#fragment', **m_split)


utest_exc(ValueError, path_for_url, '', scheme=SPLIT)
utest_exc(ValueError, path_for_url, '', host=SPLIT)
utest_exc(ValueError, path_for_url, '', query=SPLIT)
utest_exc(ValueError, path_for_url, '', fragment=SPLIT)
