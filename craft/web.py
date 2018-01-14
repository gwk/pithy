#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from time import time
from typing import *
from pithy.ansi import *
from pithy.fs import *
from pithy.io import *
from pithy.string import replace_prefix
from pithy.task import runCO
from craft import *


def main():
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
  if not path_exists(build_dir_src):
    make_link(src='src', dst=build_dir_src, make_dirs=True)

  manifest: List[str] = []

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
      res_mtime = file_time_mod(res_path)
      dst_mtime = file_time_mod_or_zero(dst_path)
      if res_mtime == dst_mtime: continue
      outSL(res_path, '->', dst_path)
      if res_mtime < dst_mtime: exit(f'resource build copy was subsequently modified: {dst_path}')
      make_dirs(path_dir(dst_path))
      copy_path(res_path, dst_path)

def transpile_js(ts_path, dst_path, modules_map):
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
          exit(f'{TXT_L}{ts_path}:{line_num}:{col}: error: external module is not mapped in yaml.conf ts-modules: {orig_module}{RST}')
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
