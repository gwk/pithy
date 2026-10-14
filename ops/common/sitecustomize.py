# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Keep bytecode caches per user and out of source trees.

`build-python.sh` installs this file into the stdlib directory of the shared Python installation.
Python imports `sitecustomize` during startup, before the main script and before any project code,
and the stdlib directory stays on `sys.path` in every venv created from the installation, so the hook applies there too.
`-I` and `-E` ignore the `PYTHONPYCACHEPREFIX` environment variable but still run this hook; only `-S` skips it.

With a prefix set, Python neither reads nor writes `__pycache__` directories beside the sources.
That matters when several users share a checkout: Python trusts a cached `.pyc` whose header matches the source,
so a cache written by one user would otherwise run as any other user who imports the module.
The prefix is resolved from the password database rather than `HOME`, so the environment cannot redirect it.
An explicit `-X pycache_prefix` or `PYTHONPYCACHEPREFIX` takes precedence.
'''

import sys


def set_pycache_prefix() -> None:
  if sys.pycache_prefix is not None: return
  from os import environ, getuid
  from os.path import join
  from pwd import getpwuid
  cache_home = environ.get('XDG_CACHE_HOME') or join(getpwuid(getuid()).pw_dir, '.cache')
  sys.pycache_prefix = join(cache_home, 'python')


try: set_pycache_prefix()
except Exception as e: # Never break interpreter startup, but never fail silently either.
  print(f'sitecustomize: failed to set the bytecode cache prefix: {e!r}', file=sys.stderr)
