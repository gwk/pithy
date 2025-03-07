# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-web` is a build tool wrapper around the TypeScript compiler. It is a work in progress.
'''


import re
from sys import argv
from typing import Dict

from crafts import load_craft_config
from pithy.ansi import RST, TXT_D, TXT_L, TXT_M, TXT_R, TXT_Y
from pithy.fs import copy_path, file_mtime, file_mtime_or_zero, make_dirs, make_link, path_exists, walk_files
from pithy.io import outL, outSL
from pithy.path import norm_path, path_dir, path_dir_or_dot, path_join
from pithy.string import replace_prefix
from pithy.task import runCO


def main() -> None:
  conf = load_craft_config()
  build_dir = conf.build_dir
  tsc_build_dir = f'{build_dir}/_ts'
  c, o = runCO(['tsc', '-outDir', tsc_build_dir, *argv[1:]])
  for line in o.split('\n'):
    m = tsc_regex.match(line)
    if not m:
      outL(TXT_M, line, RST)
      continue
    path, line, col, kind, code, msg = m.groups()
    kind_color = TXT_Y if kind == 'warning' else TXT_R
    outL(f'{TXT_L}{path}:{line}:{col}: {kind_color}{kind}: {RST}{msg} {TXT_D}({code}){RST}')
  if c: exit(c)

  # HACK: add link to source dir so that browser can see sources as described in source map.
  build_dir_src = f'{build_dir}/src'
  if not path_exists(build_dir_src, follow=False):
    make_link(orig='src', link=build_dir_src, create_dirs=True)

  manifest: list[str] = []

  for ts_path in walk_files(tsc_build_dir, file_exts=['.js', '.map']):
    dst_path = norm_path(replace_prefix(ts_path, prefix=tsc_build_dir, replacement=build_dir))
    manifest.append(dst_path)
    #if file_time_mod(ts_path) == file_time_mod_or_zero(dst_path): continue # never works.
    if ts_path.endswith('.js'):
      transpile_js(ts_path=ts_path, dst_path=dst_path, modules_map=conf.ts_modules)
    else:
      outSL(ts_path, '->', dst_path)
      copy_path(src=ts_path, dst=dst_path)

  for res_root, dst_root in conf.resources.items():
    build_dst_root = path_join(build_dir, dst_root)
    for res_path in walk_files(res_root, file_exts=web_res_exts):
      dst_path = norm_path(replace_prefix(res_path, prefix=res_root, replacement=build_dst_root))
      res_mtime = file_mtime(res_path, follow=True)
      dst_mtime = file_mtime_or_zero(dst_path, follow=True)
      if res_mtime == dst_mtime: continue
      outSL(res_path, '->', dst_path)
      if res_mtime < dst_mtime: exit(f'resource build copy was subsequently modified: {dst_path}')
      make_dirs(path_dir(dst_path))
      copy_path(res_path, dst_path)

def transpile_js(ts_path:str, dst_path:str, modules_map:Dict[str,str]) -> None:
  lines = list(open(ts_path))
  for line_idx, line in enumerate(lines):
    m = import_regex.fullmatch(line)
    if m:
      prefix, orig_module, suffix = m.groups()
      line_num = line_idx + 1
      col = m.start(2) # want 1-indexed column offset; since the start excludes the leading quote, it is fine as is.
      try: web_module = modules_map[orig_module]
      except KeyError: # not in ts_modules.
        if orig_module.startswith('.'): # local path.
          web_module = orig_module + '.js'
        else:
          exit(f'{TXT_L}{ts_path}:{line_num}:{col}: error: external module is not mapped in craft.eon ts-modules: {orig_module}{RST}')
      outL(f'{TXT_L}{ts_path}:{line_num}:{col}: note: fixing import: {orig_module} -> {web_module}{RST}')
      lines[line_idx] = f"{prefix}'{web_module}'{suffix}"
  make_dirs(path_dir_or_dot(dst_path))
  outSL(ts_path, '->', dst_path)
  with open(dst_path, 'w') as f:
    for line in lines: f.write(line)


tsc_regex = re.compile(r'([^\(]+)\((\d+),(\d+)\): (error|warning) (\w+): (.+)')

import_regex = re.compile(r'''(?x) \s* (import \s+ .+ \s+ from \s+) ["']([^'"]+)["'] (.*\n?)''')

web_res_exts = {
  '.css',
  '.jpg',
  '.png',
  '.html',
}


if __name__ == '__main__': main()
