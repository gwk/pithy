# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ast import parse as parse_ast
from hashlib import sha256
from json import dumps, loads
from os import utime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time_ns
from unittest.mock import patch

from crafts.bin.craft_context import (ContextModule, CraftContext, extract_context_meta, FileRecord, find_src_paths,
  generated_warning, Index, load_context_index, load_project_context, process_path, Query, query_context_modules,
  refresh_context_index, Validate)
from pithy.filestatus import is_dir
from pithy.fs import list_dir
from utest import utest, utest_exc, utest_val


# Nested assignments must not override module metadata, and a standalone annotation is not a value assignment.
utest((['file locking', 'flock'], 'experimental'), extract_context_meta, parse_ast('''
_context_keywords_:list[str]
_context_keywords_:list[str] = ['file locking', 'flock']
_context_status_:str
_context_status_:str = 'experimental'
class Example:
  _context_keywords_ = ['class']
  _context_status_ = 'class'
def example():
  _context_keywords_ = ['function']
if True:
  _context_keywords_ = ['conditional']
'''))
utest(([], ''), extract_context_meta, parse_ast('"No metadata."'))
utest(([], 'obsolete; use pithy.fs'), extract_context_meta, parse_ast('_context_status_ = "obsolete; use pithy.fs"'))

# An empty declaration still counts when rejecting reassignment.
utest_exc(ValueError, extract_context_meta, parse_ast('_context_keywords_ = []\n_context_keywords_ = ["second"]'))
utest_exc(ValueError('_context_status_ at line 2: repeated declaration.'), extract_context_meta,
  parse_ast('_context_status_ = "a"\n_context_status_ = "b"'))

# Reject computed expressions without evaluating them, and reject literals with the wrong shape.
for expression in ('print("Must not execute")', '["a"] + ["b"]', '("a", "b")', '["a", 1]'):
  utest_exc(ValueError, extract_context_meta, parse_ast(f'_context_keywords_ = {expression}'))
for expression in ('print("Must not execute")', '"a" + "b"', '["a"]', '1'):
  utest_exc(ValueError('_context_status_ at line 1: expected a literal string.'), extract_context_meta,
    parse_ast(f'_context_status_ = {expression}'))
for status in ('""', '"-"', '"a\\nb"', '"a\\tb"'):
  utest_exc(ValueError, extract_context_meta, parse_ast(f'_context_status_ = {status}'))

utest_exc(ValueError("_context_keywords_ at line 1: duplicate keyword: 'flock'."), extract_context_meta,
  parse_ast('_context_keywords_ = ["flock", "file locking", "flock"]'))
utest_exc(ValueError("_context_keywords_ at line 1: keywords must be in sorted order: ['file locking', 'flock']."),
  extract_context_meta, parse_ast('_context_keywords_ = ["flock", "file locking"]'))
utest_exc(ValueError("_context_keywords_ at line 1: keywords must be in sorted order: ['HTTP', 'api']."), extract_context_meta,
  parse_ast('_context_keywords_ = ["api", "HTTP"]'))
for blank in ('""', '" "', '"---"', '"_"'):
  utest_exc(ValueError(f'_context_keywords_ at line 1: keyword has no matchable words: {blank[1:-1]!r}.'),
    extract_context_meta, parse_ast(f'_context_keywords_ = [{blank}]'))
utest((['A', 'a'], ''), extract_context_meta, parse_ast('_context_keywords_ = ["A", "a"]'))
utest((['fcntl.flock', 'three word phrase'], ''), extract_context_meta,
  parse_ast('_context_keywords_ = ["fcntl.flock", "three word phrase"]'))
utest_exc(ValueError("_context_keywords_ at line 1: keyword has more than 3 words: 'a four word phrase'."),
  extract_context_meta, parse_ast('_context_keywords_ = ["a four word phrase"]'))
utest(CraftContext(cmd=Validate(paths=['pkg'], root='library')), CraftContext.parse,
  ['validate', '-root', 'library', 'pkg'])


modules = [
  ContextModule(path='locking.py', keywords=['locking'], status=''),
  ContextModule(path='advisory_lock.py', keywords=['file locking', 'flock', 'advisory lock'], status=''),
  ContextModule(path='files.py', keywords=['file', 'file format'], status='obsolete'),
]
expected_matches = [
  (2, 'advisory_lock.py', '', ['file locking']),
  (1, 'files.py', 'obsolete', ['file', 'file format']),
  (1, 'locking.py', '', ['locking']),
]
utest(expected_matches, query_context_modules, modules, ['FILE locking'])
utest(expected_matches, query_context_modules, modules, ['file', 'locking', 'file'])
utest(expected_matches, query_context_modules, modules, ['file_locking'])
utest([(1, 'advisory_lock.py', '', ['flock'])], query_context_modules, modules, ['flock', 'unknown'])
utest([(1, 'advisory_lock.py', '', ['advisory lock'])], query_context_modules, modules, ['lock'])
utest([(1, 'files.py', 'obsolete', [])], query_context_modules, modules, ['files'])
utest([], query_context_modules, modules, ['floc'])

# Module name words match as keywords; package modules take the package name, and compound suffixes are dropped.
name_modules = [
  ContextModule(path='pkg/web_server/__init__.py', keywords=['http'], status=''),
  ContextModule(path='pkg/tool/__main__.py', keywords=['cli'], status=''),
  ContextModule(path='pkg/pool.ut.py', keywords=['tests'], status=''),
]
utest([(2, 'pkg/web_server/__init__.py', '', ['http'])], query_context_modules, name_modules, ['server', 'http', 'init'])
utest([(1, 'pkg/tool/__main__.py', '', [])], query_context_modules, name_modules, ['tool', 'main'])
utest([(1, 'pkg/pool.ut.py', '', [])], query_context_modules, name_modules, ['pool', 'ut'])
utest_exc(ValueError, query_context_modules, modules, ['---'])
utest_exc(ValueError, query_context_modules, modules, [])
utest(CraftContext(cmd=Query(words=['file locking'], root='library')), CraftContext.parse,
  ['query', '-root', 'library', 'file locking'])


with TemporaryDirectory() as tmp:
  workspace = Path(tmp)
  project = workspace / 'project'
  dependency = workspace / 'library'
  (project / 'deps').mkdir(parents=True)
  (project / 'context').mkdir()
  (project / 'file.py').write_text('_context_keywords_ = ["file"]\n_context_status_ = "unmaintained"\n')
  (dependency / 'context').mkdir(parents=True)
  (dependency / 'lock.py').write_text('_context_keywords_ = ["fcntl.flock", "file locking"]\n')
  (project / 'deps/library').symlink_to(dependency, target_is_directory=True)
  (project / 'deps/library-alias').symlink_to(dependency, target_is_directory=True)
  (project / 'deps/self').symlink_to(project, target_is_directory=True)
  (project / 'deps/unindexed').mkdir()
  dep_index = dependency / 'context/index.json'
  expected_local = ContextModule(path=f'{project}/file.py', keywords=['file'], status='unmaintained')
  expected_dep = ContextModule(path=f'{project}/deps/library/lock.py', keywords=['fcntl.flock', 'file locking'], status='')

  # Indexing the project does not create or refresh dependency indexes.
  with patch('crafts.bin.craft_context.outL'):
    Index(root=str(project)).run()
  utest(False, dep_index.exists)
  with patch('crafts.bin.craft_context.errL') as errors:
    utest([expected_local], load_project_context, str(project))
    utest(2, lambda: errors.call_count)
  utest(False, dep_index.exists)
  with patch('crafts.bin.craft_context.outL'):
    Index(root=str(dependency)).run()

  # Queries use stored keywords even after sources change, without scanning or acquiring a writer lock.
  (dependency / 'lock.py').write_text('def broken(\n')
  (project / 'file.py').unlink()
  (project / 'context/index.lock').unlink()
  (dependency / 'context/index.lock').unlink()
  project_index = project / 'context/index.json'
  snapshots = [(path, path.read_bytes(), path.stat().st_mtime_ns) for path in (project_index, dep_index)]
  with patch('crafts.bin.craft_context.scan_context_files', side_effect=AssertionError('Query scanned sources')), \
   patch('crafts.bin.craft_context.advisory_lock', side_effect=AssertionError('Query acquired a lock')), \
   patch('crafts.bin.craft_context.errL') as errors, patch('crafts.bin.craft_context.outL') as output:
    utest([expected_local, expected_dep], load_project_context, str(project))
    Query(root=str(project), words=['file locking']).run()
    utest([((f'{project}/deps/library/lock.py: file locking',), {}), ((f'{project}/file.py (unmaintained): file',), {})],
      lambda: output.call_args_list)
    utest(2, lambda: errors.call_count)
  for path, data, mtime_ns in snapshots:
    utest(data, path.read_bytes)
    utest(mtime_ns, lambda: path.stat().st_mtime_ns)
    utest(['index.json'], list_dir, str(path.parent))
  utest(False, (project / 'deps/unindexed/context').exists)

  # Do not recurse into dependencies' own dependency trees.
  (dependency / 'deps/transitive/context').mkdir(parents=True)
  (dependency / 'deps/transitive/context/index.json').write_text('invalid JSON')
  with patch('crafts.bin.craft_context.errL'):
    utest([expected_local, expected_dep], load_project_context, str(project))

  # Invalid or outdated indexes fail without being rewritten.
  for invalid in ('invalid JSON', dumps({'version': 0, 'modules': []})):
    dep_index.write_text(invalid)
    utest_exc(ValueError, load_project_context, str(project))
    utest(invalid, dep_index.read_text)
  with patch('crafts.bin.craft_context.load_context_index', side_effect=PermissionError('Cannot read')):
    utest_exc(PermissionError, load_project_context, str(project))
  with patch('crafts.bin.craft_context.errL'):
    utest_exc(ValueError, load_project_context, str(project / 'deps/unindexed'))
  utest_exc(ValueError, load_project_context, str(workspace / 'missing'))


old_time_ns = 1_000_000_000_000_000_000 # An mtime well before any index build.

def write_source(path:Path, text:str, mtime_ns:int=old_time_ns) -> None:
  'Write a source file with a fixed mtime so that stat comparisons are deterministic.'
  path.write_text(text)
  utime(path, ns=(mtime_ns, mtime_ns))


with TemporaryDirectory() as tmp:
  root = Path(tmp)
  lock_source = ('"""Do not index this docstring."""\n_context_keywords_ = ["file locking", "flock"]\n'
    'raise RuntimeError("Do not import")\n')
  write_source(root / 'lock.py', lock_source)
  write_source(root / 'undocumented.py', '"Only a docstring."\n')
  write_source(root / 'empty.py', '_context_keywords_ = []\n')
  # A real dependency checkout is indexed at its own root, not by the dependent project.
  (root / 'deps/library').mkdir(parents=True)
  write_source(root / 'deps/library/lock.py', '_context_keywords_ = ["dependency"]\n')
  index = root / 'context/index.json'
  Validate(root=tmp).run()
  utest(False, index.parent.exists)
  with patch('crafts.bin.craft_context.outL') as output:
    Index(root=tmp).run()
    utest([((f'craft-context: wrote {tmp}/context/index.json',), {})], lambda: output.call_args_list)
  lock_record = FileRecord(size=len(lock_source), mtime_ns=old_time_ns, sha256=sha256(lock_source.encode()).hexdigest(),
    keywords=['file locking', 'flock'], status='')
  utest({'version': 2, 'files': {
    'empty.py': FileRecord(size=24, mtime_ns=old_time_ns, sha256=sha256(b'_context_keywords_ = []\n').hexdigest(), keywords=[],
      status=''),
    'lock.py': lock_record,
    'undocumented.py': FileRecord(size=20, mtime_ns=old_time_ns, sha256=sha256(b'"Only a docstring."\n').hexdigest(),
      keywords=[], status='')}}, loads, index.read_text())
  utest((loads(index.read_text()), index.stat().st_mtime_ns), load_context_index, str(index))
  first_build = index.read_bytes()
  index_mtime_ns = index.stat().st_mtime_ns
  Validate(root=tmp).run()
  utest(index_mtime_ns, lambda: index.stat().st_mtime_ns)

  # Unchanged files are skipped by stat without hashing or writing; overlapping paths are visited once.
  with patch('crafts.bin.craft_context.outL') as output, patch('crafts.bin.craft_context.sha256') as digest:
    Index(root=tmp, paths=[str(root / 'lock.py'), 'lock.py']).run()
    utest([((f'craft-context: up to date: {tmp}/context/index.json',), {})], lambda: output.call_args_list)
    utest(0, lambda: digest.call_count)
  utest(index_mtime_ns, lambda: index.stat().st_mtime_ns)

  # A bumped mtime with identical content is confirmed by digest without parsing, and the stat is recorded.
  utime(root / 'lock.py', ns=(old_time_ns + 1, old_time_ns + 1))
  with patch('crafts.bin.craft_context.outL'), patch('crafts.bin.craft_context.parse_ast') as parse:
    Index(root=tmp).run()
    utest(0, lambda: parse.call_count)
  utest({**lock_record, 'mtime_ns': old_time_ns + 1}, lambda: loads(index.read_text())['files']['lock.py'])

  # Changed content is reparsed.
  write_source(root / 'lock.py', '_context_keywords_ = ["changed"]\n')
  with patch('crafts.bin.craft_context.outL'):
    Index(root=tmp).run()
  utest(['changed'], lambda: loads(index.read_text())['files']['lock.py']['keywords'])

  # A file whose mtime is not older than the index is digested on every run, guarding against racy writes.
  future_ns = time_ns() + 10**12
  utime(root / 'lock.py', ns=(future_ns, future_ns))
  for _ in range(2):
    with patch('crafts.bin.craft_context.outL'), patch('crafts.bin.craft_context.sha256', wraps=sha256) as digest:
      Index(root=tmp).run()
      utest(1, lambda: digest.call_count)
  write_source(root / 'lock.py', lock_source)
  with patch('crafts.bin.craft_context.outL'):
    Index(root=tmp).run()
  utest(first_build, index.read_bytes)

  # Reject malformed sources and metadata without publishing a partial index.
  bad_source = root / 'bad.py'
  for source in ('_context_keywords_ = [42]', '_context_keywords_ = ["flock", "flock"]', '_context_keywords_ = [" "]',
   '_context_keywords_ = ["flock", "file locking"]', '_context_status_ = ""', 'def broken('):
    write_source(bad_source, source)
    with patch('crafts.bin.craft_context.errL'), patch('crafts.bin.craft_context.outL') as output:
      utest_exc(SystemExit('craft-context index: 1 source errors; index not written.'), Index(root=tmp).run)
      utest_exc(SystemExit('craft-context validate: 1 source errors.'), Validate(root=tmp).run)
      utest([], lambda: output.call_args_list)
    utest(first_build, index.read_bytes)
  bad_source.unlink()

  # Scanning a subset refreshes only records under the given paths; a full scan drops the rest.
  (root / 'sub').mkdir()
  write_source(root / 'sub/a.py', '_context_keywords_ = ["a"]\n')
  write_source(root / 'sub/b.py', '_context_keywords_ = ["b"]\n')
  with patch('crafts.bin.craft_context.outL'):
    Index(root=tmp).run()
  (root / 'sub/b.py').unlink()
  (root / 'undocumented.py').unlink()
  with patch('crafts.bin.craft_context.outL'):
    Index(root=tmp, paths=['sub']).run()
  utest(['empty.py', 'lock.py', 'sub/a.py', 'undocumented.py'], lambda: list(loads(index.read_text())['files']))
  with patch('crafts.bin.craft_context.outL'):
    Index(root=tmp).run()
  utest(['empty.py', 'lock.py', 'sub/a.py'], lambda: list(loads(index.read_text())['files']))
  (root / 'sub/a.py').unlink()
  (root / 'sub').rmdir()
  write_source(root / 'undocumented.py', '"Only a docstring."\n')
  with patch('crafts.bin.craft_context.outL'):
    Index(root=tmp).run()
  utest(first_build, index.read_bytes)

  # Relative paths still locate the source after moving the project; querying leaves cached records intact.
  moved_root = root / 'moved'
  moved_root.mkdir()
  (root / 'context').rename(moved_root / 'context')
  (root / 'lock.py').rename(moved_root / 'lock.py')
  index = moved_root / 'context/index.json'
  with patch('crafts.bin.craft_context.outL') as output, patch('crafts.bin.craft_context.parse_ast') as parse:
    Query(root=str(moved_root), words=['locking']).run()
    utest([((f'{moved_root}/lock.py: file locking',), {})], lambda: output.call_args_list)
    utest(0, lambda: parse.call_count)
  utest(['empty.py', 'lock.py', 'undocumented.py'], lambda: list(loads(index.read_text())['files']))
  moved_build = index.read_bytes()

  # A failed replacement leaves the old index intact and cleans up the temporary directory.
  write_source(moved_root / 'lock.py', '"No keywords."\n')
  with patch('crafts.bin.craft_context.replace', side_effect=OSError('Cannot replace')):
    utest_exc(OSError, Index(root=str(moved_root)).run)
  utest(moved_build, index.read_bytes)
  utest(['index.json', 'index.lock'], list_dir, str(index.parent))

  # Rebuilding drops keywords whose source no longer advertises them.
  with patch('crafts.bin.craft_context.outL'):
    utest(([], True), refresh_context_index, str(moved_root), ['.'], command='index')

  # A status alone is enough for a module to be returned.
  write_source(moved_root / 'lock.py', '_context_status_ = "obsolete"\n')
  with patch('crafts.bin.craft_context.outL'):
    utest(([ContextModule(path='lock.py', keywords=[], status='obsolete')], True), refresh_context_index, str(moved_root), ['.'],
      command='index')
  write_source(moved_root / 'lock.py', '"No keywords."\n')

  # Loading raises without logging or modifying the index; refresh handles invalid indexes by rebuilding.
  utest_exc(FileNotFoundError, load_context_index, str(moved_root / 'missing.json'))
  for invalid in (dumps({'version': 0, 'modules': []}), 'invalid JSON',
   dumps({'version': 1, 'files': {'bad.py': {'size': 1, 'mtime_ns': 1, 'sha256': '', 'keywords': []}}}),
   dumps({'version': 2, 'files': []}), dumps({'version': 2, 'files': {'': {}}}),
   dumps({'version': 2, 'files': {'/absolute.py': {'size': 1, 'mtime_ns': 1, 'sha256': '', 'keywords': [], 'status': ''}}}),
   dumps({'version': 2, 'files': {'bad.py': {'size': 1.0, 'mtime_ns': 1, 'sha256': '', 'keywords': [], 'status': ''}}}),
   dumps({'version': 2, 'files': {'bad.py': {'size': 1, 'mtime_ns': 1, 'sha256': '', 'keywords': [1], 'status': ''}}}),
   dumps({'version': 2, 'files': {'bad.py': {'size': 1, 'mtime_ns': 1, 'sha256': '', 'keywords': []}}})):
    index.write_text(invalid)
    with patch('crafts.bin.craft_context.errL') as errors:
      utest_exc(ValueError, load_context_index, str(index))
      utest(0, lambda: errors.call_count)
      utest(invalid, index.read_text)
      utest(([], True), refresh_context_index, str(moved_root), ['.'], command='index')
      utest(1, lambda: errors.call_count)
    utest(['lock.py'], lambda: list(load_context_index(str(index))[0]['files']))
  with patch('crafts.bin.craft_context.load_context_index', side_effect=PermissionError('Cannot read')):
    utest_exc(PermissionError, refresh_context_index, str(moved_root), ['.'], command='index')


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


# Import tokens are quoted in the generated file so that Claude Code does not import the files a second time.
# A repeated import is quoted but emitted once; an existing code span is left alone.
with TemporaryDirectory() as tmp:
  root = Path(tmp)
  src = root / 'CTX.md'
  src.write_text('Root.\n@sub/a.md and `@literal`.\n* @sub/b.md\n')
  sub_dir = root / 'sub'
  sub_dir.mkdir()
  (sub_dir / 'a.md').write_text('A.\n@./b.md\n')
  (sub_dir / 'b.md').write_text('B.\n')
  with patch('crafts.bin.craft_context.outL'): process_path(str(src))
  utest('\n\n'.join([
    generated_warning,
    'Root.\n`@sub/a.md` and `@literal`.\n* `@sub/b.md`',
    'Contents of sub/a.md:\n\nA.\n`@./b.md`',
    'Contents of sub/b.md:\n\nB.']) + '\n',
    (root / 'AGENTS.md').read_text)
  utest(True, (root / 'CLAUDE.md').is_symlink)


# A chain of four import hops is the deepest that Claude Code loads; a fifth hop is an error rather than a silent omission.
with TemporaryDirectory() as tmp:
  root = Path(tmp)
  src = root / 'CTX.md'
  src.write_text('@1.md\n')
  for i in range(1, 4): (root / f'{i}.md').write_text(f'@{i+1}.md\n')
  (root / '4.md').write_text('Four.\n')
  with patch('crafts.bin.craft_context.outL'): process_path(str(src))
  utest_val(True, (root / 'AGENTS.md').read_text().endswith('Contents of 4.md:\n\nFour.\n'), 'four hops are expanded')
  (root / '4.md').write_text('@5.md\n')
  (root / '5.md').write_text('Five.\n')

  def depth_error() -> bool:
    try: process_path(str(src))
    except SystemExit as e: return 'import exceeds the maximum depth of 4.' in str(e)
    return False

  utest(True, depth_error)
