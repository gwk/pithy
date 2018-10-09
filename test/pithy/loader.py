#!/usr/bin/env python3

from utest import *
from pithy.loader import *
from pithy.loader import _path_cmpd_ext, _last_ext, _sub_ext
from pithy.json import write_json, write_jsonl
from pithy.csv import write_csv
from pithy.task import run


lines = ['0\n', '1\n']
lines_b = [s.encode() for s in lines]
with open('test.txt', 'w') as f:
  for line in lines:
    f.write(line)

utest_seq(lines, load, 'test.txt')
utest_seq(lines_b, load, 'test.txt', ext='') # Open with binary loader.

header = ('N', 'A')
rows = [['0', 'a'], ['1', 'b']]
with open('test.csv', 'w') as f:
  write_csv(f, header=header, rows=rows)

utest_seq(rows, load, 'test.csv', header=header)


d = {'0':0, '1':1}
with open('test.json', 'w') as f:
  write_json(f, d)

utest(d, load, 'test.json')


with open('test.jsonl', 'w') as f:
  write_jsonl(f, d)
  write_jsonl(f, d)

utest_seq([d, d], load, 'test.jsonl')


with open('test.jsons', 'w') as f:
  write_json(f, d)
  write_json(f, d)

utest_seq([d, d], load, 'test.jsons')


# Test each compression method.
compression_exts = ['.gz', '.xz', '.zst']
pack_flags = [e.replace('.', '-') for e in compression_exts]
run(['pack', '-quiet', *pack_flags, 'test.txt'])
for ext in compression_exts:
  path = 'test.txt' + ext
  utest_seq(lines, load, path)

# TODO:
# '.br'
# '.pyl'
# '.sqlite'
# '.sqlite3'
# '.tar'
# '.xls'
# '.zip'


utest('', _path_cmpd_ext, '')
utest('', _path_cmpd_ext, '.hidden')
utest('.ext', _path_cmpd_ext, 'stem.ext')
utest('.ext', _path_cmpd_ext, '.hidden.ext')
utest('.ext.ext', _path_cmpd_ext, 'stem.ext.ext')
utest('.ext.ext', _path_cmpd_ext, '.hidden.ext.ext')

utest('', _last_ext, '')
utest('', _sub_ext, '')

utest('.ext', _last_ext, '.ext')
utest('', _sub_ext, '.ext')

utest('.b', _last_ext, '.a.b')
utest('.a', _sub_ext, '.a.b')

