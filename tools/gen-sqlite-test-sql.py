#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import ArgumentParser, Namespace
from sys import stderr
from typing import Iterator

from pithy.fs import abbreviate_user, list_dir, make_dirs
from pithy.iterable import fan_items
from pithy.path import path_join, path_name
from pithy.sqlite.keywords import sqlite_leading_keywords


def main() -> None:
  parser = ArgumentParser()
  parser.add_argument('-input-sqlite-dir', required=True)
  parser.add_argument('-out-dir', required=True)
  parser.add_argument('-verbose', action='store_true')

  args = parser.parse_args()

  make_dirs(args.out_dir)

  in_dir = path_join(args.input_sqlite_dir, 'test')

  all_paths = [path_join(in_dir, name) for name in list_dir(in_dir) if name.endswith('.test')]

  stmt_examples = fan_items(parse_all_paths(all_paths))

  unique_stmts:set[str] = set()
  seen_ignored_locs:set[str] = set()
  for keyword, examples in stmt_examples.items():
    write_examples(keyword, examples, args, unique_stmts, seen_ignored_locs)

  if unused_ignores := sorted(seen_ignored_locs - ignored_locs):
    print('\nUnused ignores:', *unused_ignores, sep='\n  ', file=stderr)



def parse_all_paths(all_paths:list[str]) -> Iterator[tuple[str,tuple[str,str]]]:
  '''
  Generate a stream of (keyword, (loc_str, stmt)) tuples.
  '''
  for path in all_paths:
    abbr_path = abbreviate_user(path)

    #print(f'\n{abbr_path}:')
    with open(path) as f: lines = list(f)

    stmt_loc = 0
    stmt_lines:list[str] = []

    def flush() -> tuple[str,tuple[str,str]]:
      assert stmt_lines
      keyword = first_word(stmt_lines[0]).upper()
      assert keyword.isalpha(), f'invalid keyword: {keyword!r}'
      loc_str = f'{abbr_path}:{stmt_loc}'
      stmt = '\n  '.join(stmt_lines)
      stmt_lines.clear()
      return keyword.lower(), (loc_str, stmt)

    for ln, line in enumerate(lines, 1):
      line = re.sub(r'/\*.*?\*/', '', line) # Remove TCL comments.
      line = line.strip()

      if not stmt_lines and first_word(line).upper() not in sqlite_leading_keywords: continue

      if line.startswith('}'): # Occasionally a statement is not terminated by a semicolon. Find the closing TCL brace instead.
        assert stmt_lines
        stmt_lines[-1] += ';'

      else:
        if line.endswith('}'):
          # Occasionally a statement looks like `COMMIT;}}`, `END}}`, etc. We want to strip the closing braces.
          # However we must be careful because others look like `SELECT * FROM ${::tbl_name}`.
          if not re.search(r'\$\{[^}]+\}$', line): line = line.rstrip('}')
          if not has_term_semicolon(line): line += ';' # Note: this might be adding the semicolon after the sql comment.

        if not stmt_lines: stmt_loc = ln # Save the first line number.
        stmt_lines.append(line)

      if has_term_semicolon(stmt_lines[-1]): yield flush()

    if stmt_lines: yield flush()


def first_word(s:str) -> str:
  if m := re.match(r'\w+\b(?!\.)', s): return m[0]
  return ''


def has_term_semicolon(line:str) -> bool:
  # We are obliged to do fake tokenization here.
  # Replace all string literals, then clip comment.
  line = sql_str_re.sub('', line)
  sql, _, _ = line.partition('--')
  return sql.rstrip().endswith(';')


sql_str_re = re.compile(r'''(?x)
  ' ( [^'] | '' )* '
| " ( [^"] | "" )* "
''')


def write_examples(keyword:str, examples:list[tuple[str,str]], args:Namespace, unique_stmts:set[str], seen_ignored_locs:set[str]) -> None:
  name = f'{keyword}.sql'
  out_path = path_join(args.out_dir, name)

  with open(out_path, 'w') as f:

    print(
      '-- Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.',
      f'-- Extracted from sqlite3/test/{name}.\n', sep='\n', file=f)

    for loc, stmt in examples:
      loc_name_num = path_name(loc)

      if stmt in unique_stmts: continue
      unique_stmts.add(stmt)

      ignore_reason = ''
      if loc_name_num in ignored_locs:
        ignore_reason = f'ignored location: {loc_name_num}'
        seen_ignored_locs.add(loc_name_num)
      elif re.search(r'\$\{\w+\}', stmt):
        ignore_reason = 'contains `${...}`'
      elif re.search(r'#\d;$', stmt):
        ignore_reason = 'contains `#n;` (Usually an intentional syntax error)'
      if ignore_reason:
        if args.verbose: print(f'\n{loc}: skipping: {ignore_reason}.\n{stmt}', file=stderr)
        continue
      print(f'\n-- {loc}\n{stmt}', file=f)


# NOTE: these are fragile, subject to breakage.
ignored_locs = {
  'alter.test:605',
  'alter.test:618',
  'alter.test:618',
  'alter.test:646',
  'alter3.test:383',
  'alterdropcol.test:152',
  'alterdropcol.test:175',
  'altertab.test:934',
  'altertab3.test:236',
  'altertrig.test:149',
  'analyze9.test:1054',
  'autovacuum.test:97',
  'bestindex8.test:379',
  'bind.test:444',
  'bind.test:453',
  'bind.test:462',
  'carray01.test:55',
  'distinct.test:122',
  'e_createtable.test:1604',
  'e_createtable.test:1626',
  'e_expr.test:1525',
  'e_expr.test:228',
  'e_expr.test:341',
  'e_expr.test:497',
  'e_expr.test:555',
  'e_fts3.test:677',
  'e_fts3.test:691',
  'fts1porter.test:655',
  'fts3auto.test:93',
  'fts3cov.test:134',
  'fts3defer.test:500',
  'fts3defer2.test:148',
  'fts3near.test:170',
  'fts3sort.test:146',
  'fts3tok1.test:38',
  'hook.test:185',
  'hook.test:250',
  'hook.test:280',
  'hook.test:306',
  'hook.test:544',
  'hook.test:551',
  'hook.test:561',
  'hook.test:566',
  'hook.test:602',
  'hook.test:609',
  'hook.test:621',
  'hook.test:638',
  'hook.test:640',
  'hook.test:649',
  'hook.test:651',
  'hook.test:667',
  'hook.test:692',
  'hook.test:804',
  'hook.test:847',
  'hook.test:875',
  'hook.test:883',
  'hook.test:888',
  'hook.test:893',
  'hook.test:898',
  'hook.test:909',
  'hook2.test:100',
  'hook2.test:112',
  'hook2.test:118',
  'hook2.test:133',
  'hook2.test:139',
  'hook2.test:145',
  'hook2.test:161',
  'hook2.test:166',
  'hook2.test:198',
  'hook2.test:205',
  'hook2.test:212',
  'hook2.test:60',
  'indexexpr2.test:367',
  'indexexpr2.test:371',
  'insert5.test:83',
  'json101.test:134',
  'json102.test:212',
  'json102.test:223',
  'json104.test:20',
  'json104.test:37',
  'keyword1.test:30',
  'keyword1.test:88',
  'main.test:232',
  'main.test:237',
  'main.test:249',
  'main.test:258',
  'main.test:266',
  'main.test:449',
  'normalize.test:48',
  'nulls1.test:30',
  'nulls1.test:34',
  'nulls1.test:38',
  'nulls1.test:42',
  'rowvalue.test:96',
  'rowvalue3.test:198',
  'rowvalueA.test:47',
  'savepoint6.test:211',
  'savepoint6.test:256',
  'shell1.test:594',
  'shell1.test:937',
  'shell1.test:959',
  'shell2.test:189',
  'shell2.test:214',
  'shell5.test:93',
  'shell5.test:121',
  'shell5.test:201',
  'shell5.test:227',
  'shell5.test:248',
  'shell5.test:262',
  'speed4.test:154',
  'sqllimits1.test:732',
  'sqllimits1.test:911',
  'sqllog.test:103',
  'sqllog.test:63',
  'sqllog.test:65',
  'substr.test:48',
  'tkt-f67b41381a.test:41',
  'tkt-f67b41381a.test:43',
  'tkt-80ba201079.test:60',
  'tpch01.test:130',
  'trigger2.test:309',
  'triggerE.test:62',
  'triggerE.test:79',
  'unhex.test:83',
  'unhex.test:86',
  'unhex.test:89',
  'unionvtab.test:194',
  'unionvtab.test:209',
  'upsert4.test:123',
  'upsert4.test:194',
  'upsert4.test:209',
  'vacuum-into.test:175',
  'whereJ.test:401',
  'window1.test:967',
  'window6.test:297',
  'window6.test:311',
  'windowB.test:44',
  'windowB.test:77',
  'windowC.test:53',
  'with2.test:242',
  'without_rowid4.test:72',
  'without_rowid4.test:77',
  'hook.test:698',
  'hook.test:722',
  'hook.test:796',
  'hook.test:839',
  'hook2.test:65',
  'hook2.test:184',
  'hook2.test:191',
  'icu.test:31',
  'autoindex4.test:113',
  'autoindex4.test:129',
  'autoindex4.test:145',
  'autoindex4.test:153',
  'autoindex4.test:161',
  'window1.test:976',
  'with1.test:1174', # Unicode operator that is apparently legal but we do not correctly lex.
  'alter.test:610',
  'alter.test:627',
  'alter.test:638',
  'json101.test:726',
  'json101.test:159',
  'json101.test:186',
  'sqllog.test:64',
  'savepoint6.test:216',
}

if __name__ == '__main__': main()
