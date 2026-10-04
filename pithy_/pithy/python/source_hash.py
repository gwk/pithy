# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Hash the source files of the running program.

A program that generates files can record `program_source_hash()` in its outputs.
A later run compares the recorded hash to its own and skips the work when neither the program nor its inputs changed.

The hash covers the modules that are loaded at the time of the call.
Call it from `main` or later, after the imports have run. Modules that are imported lazily after the call are not covered.
'''

import sys
from hashlib import sha256


_context_keywords_ = ['build cache', 'fingerprint', 'program hash', 'self hash', 'sys.modules']


def program_source_hash(*packages:str) -> str:
  '''
  Return a SHA-256 hex digest of the files of the loaded modules, as selected by `loaded_module_paths`.
  The digest covers each module name and the bytes of its file.
  It does not cover the file paths, so identical sources in different checkouts hash the same.
  Any change to a file changes the digest, including comments and whitespace.
  '''
  h = sha256()
  for name, path in sorted(loaded_module_paths(*packages).items()):
    with open(path, 'rb') as f: data = f.read()
    for part in (name.encode(), data): # Prefix each part with its length so that the parts cannot run together.
      h.update(len(part).to_bytes(8, 'little'))
      h.update(part)
  return h.hexdigest()


def loaded_module_paths(*packages:str) -> dict[str,str]:
  '''
  Return a dictionary of module names to file paths for the loaded modules.
  If `packages` are given, select the modules of those top-level packages.
  Otherwise select every module outside of the standard library. This includes `__main__`,
  which is the entry point script when the program is run from a console script and the module itself when run with `-m`.
  Name the packages explicitly for a hash that does not depend on how the program was launched.
  Extension modules are included; their path is the compiled binary.
  Built-in modules, frozen modules and namespace packages have no file and are omitted.
  '''
  paths:dict[str,str] = {}
  for name, module in list(sys.modules.items()):
    top_name = name.partition('.')[0]
    if packages:
      if top_name not in packages: continue
    elif top_name in sys.stdlib_module_names: continue
    spec = getattr(module, '__spec__', None)
    if spec is None: path = getattr(module, '__file__', None) # `__main__` has no spec when it is run as a script.
    elif spec.has_location: path = spec.origin
    else: path = None
    if path: paths[name] = path
  return paths
