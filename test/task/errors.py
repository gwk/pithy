#!/usr/bin/env python3

from utest import *
from os import chmod
from pithy.task import *
from pithy.fs import *


utest_exc(TaskInstalledCommandNotFound('nonexistent'), run, 'nonexistent')

utest_exc(TaskFileNotFound('./nonexistent'), run, './nonexistent')

with open('empty.txt', 'w'): pass

utest_exc(TaskFileInvokedAsInstalledCommand('empty.txt'), run, 'empty.txt')

make_dir('dir')
utest_exc(TaskNotAFile('./dir'), run, './dir')

utest_exc(TaskFileNotExecutable('./empty.txt'), run, './empty.txt')

chmod('./empty.txt', 0o100)
utest_exc(TaskFileNotReadable('./empty.txt'), run, './empty.txt')

chmod('./empty.txt', 0o700)
utest_exc(TaskFileHashBangMissing('./empty.txt', b''), run, './empty.txt')

with open('./hashbang-missing.py', 'w') as f:
  f.write('xyz\n')
chmod('./hashbang-missing.py', 0o700)

utest_exc(TaskFileHashBangMissing('./hashbang-missing.py', b'xyz'), run, './hashbang-missing.py')

with open('./hashbang-ill-formed.py', 'w') as f:
  f.write('#!xyz\n')
chmod('./hashbang-ill-formed.py', 0o700)

assert is_file('./hashbang-ill-formed.py')
utest_exc(TaskFileHashBangIllFormed('./hashbang-ill-formed.py', b'#!xyz'), run, './hashbang-ill-formed.py')
