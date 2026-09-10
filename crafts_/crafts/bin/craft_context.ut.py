# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from crafts.bin.craft_context import find_src_paths, process_path
from pithy.filestatus import is_dir
from pithy.fs import list_dir
from utest import utest, utest_exc


with TemporaryDirectory() as tmp:
  root = Path(tmp)
  src = root / 'CTX.md'
  src.write_text('Root context.\n')
  nested = root / 'nested'
  nested.mkdir()
  nested_src = nested / 'CTX.md'
  nested_src.write_text('Nested context.\n')
  private = root / 'private'
  private.mkdir()
  (private / 'CTX.md').write_text('Private context.\n')
  link = root / '_plan.md'
  link.symlink_to(private / 'plan.md')
  hidden = root / '.hidden'
  hidden.mkdir()
  (hidden / 'CTX.md').write_text('Hidden context.\n')

  # Model both sandbox EPERM while following a symlink and EACCES while listing a directory.
  # Mock the failures so the tests also exercise them when run by a privileged user.
  def checked_is_dir(path:str, *, follow:bool) -> bool|None:
    if path == str(link): raise PermissionError(1, 'Operation not permitted', path)
    return is_dir(path, follow=follow)

  def checked_list_dir(path:str) -> list[str]:
    if path == str(private): raise PermissionError(13, 'Permission denied', path)
    return list_dir(path)

  with patch('crafts.bin.craft_context.is_dir', side_effect=checked_is_dir), \
    patch('crafts.bin.craft_context.list_dir', side_effect=checked_list_dir):
    utest(sorted([str(src), str(nested_src)]), find_src_paths, [tmp])
    utest_exc(PermissionError, find_src_paths, [str(link)])
    utest_exc(PermissionError, find_src_paths, [str(private)])
    utest([str(src)], find_src_paths, [str(src)])

  # Accessible directory symlinks retain nested context discovery.
  alias = root / 'alias'
  alias.symlink_to(nested, target_is_directory=True)
  utest([str(alias / 'CTX.md')], find_src_paths, [str(alias)])

  # Source and import reads must fail rather than silently producing incomplete instructions.
  with patch('builtins.open', side_effect=PermissionError(13, 'Permission denied')):
    utest_exc(PermissionError, process_path, str(src))
  src.write_text('@nested/CTX.md\n')
  with patch('crafts.bin.craft_context.read_src', side_effect=['@nested/CTX.md', PermissionError(13, 'Permission denied')]):
    utest_exc(PermissionError, process_path, str(src))
