#!/usr/bin/env python3

from utest import *
from os import chmod
from pithy.task import *
from pithy.fs import *


utest_exc(TaskInstalledCommandNotFound('nonexistent'), run, 'nonexistent')

utest_exc(TaskFileNotFound('./nonexistent'), run, './nonexistent')


make_dir('dir')
make_link(orig='dir', link='dir.link')
utest_exc(TaskNotAFile('./dir'), run, './dir')
utest_exc(TaskNotAFile('./dir.link'), run, './dir.link')


touch_path('empty.py')
make_link(orig='empty.py', link='empty.link')

utest_exc(TaskFileInvokedAsInstalledCommand('empty.py'), run, 'empty.py')
utest_exc(TaskFileInvokedAsInstalledCommand('empty.link'), run, 'empty.link')

utest_exc(TaskFileNotExecutable('./empty.py'), run, './empty.py')
utest_exc(TaskFileNotExecutable('./empty.link'), run, './empty.link')

chmod('empty.py', 0o100)
utest_exc(TaskFileNotReadable('./empty.py'), run, './empty.py')
utest_exc(TaskFileNotReadable('./empty.link'), run, './empty.link')

# TODO: test effect of changing permissions on link.

chmod('empty.py', 0o700)
utest_exc(TaskFileHashbangMissing('./empty.py', b''), run, './empty.py')
utest_exc(TaskFileHashbangMissing('./empty.link', b''), run, './empty.link')

with open('hashbang-missing.py', 'w') as f:
  f.write('xyz\n')
make_link('hashbang-missing.py', 'hashbang-missing.link')
chmod('hashbang-missing.py', 0o700)

utest_exc(TaskFileHashbangMissing('./hashbang-missing.py', b'xyz'), run, './hashbang-missing.py')
utest_exc(TaskFileHashbangMissing('./hashbang-missing.link', b'xyz'), run, './hashbang-missing.link')

with open('./hashbang-ill-formed.py', 'w') as f:
  f.write('#!xyz\n')
chmod('./hashbang-ill-formed.py', 0o700)
make_link('hashbang-ill-formed.py', 'hashbang-ill-formed.link')

utest_exc(TaskFileHashbangIllFormed('./hashbang-ill-formed.py', b'#!xyz'), run, './hashbang-ill-formed.py')
utest_exc(TaskFileHashbangIllFormed('./hashbang-ill-formed.link', b'#!xyz'), run, './hashbang-ill-formed.link')

# Test interaction between parent process cwd and task cwd.
touch_path('dir/empty.py')
utest_exc(TaskFileNotExecutable('dir/empty.py'), run, 'dir/empty.py')
utest_exc(TaskFileInvokedAsInstalledCommand('dir/empty.py'), run, 'empty.py', cwd='dir')
