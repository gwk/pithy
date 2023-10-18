# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from itertools import groupby
from typing import Any, Callable, Dict, Iterator, List

from pithy.fs import path_name
from pithy.io import errL

from .pbx import (_BuildPhase, PBX, PBXBuildFile, PBXFileReference, PBXGroup, PBXNativeTarget, PBXProject, PlistRoot,
  XCBuildConfiguration, XCConfigurationList, XCLocalSwiftPackageReference, XCSwiftPackageProductDependency)
from .util import is_ref, quote_string


class Renderer:

  def __init__(self, proj_name:str, root:PlistRoot) -> None:
    self.proj_name = proj_name
    self.root = root
    self.objects = root.objects

    list_owners = [(k, v) for (k, v) in self.objects.items() if hasattr(v, 'buildConfigurationList')]
    self.configurationList_owners = { v.buildConfigurationList : k for (k, v) in list_owners }

    phases = [v for v in  self.objects.values() if isinstance(v, _BuildPhase)]
    self.buildFile_phases = {file_id : phase for phase in phases for file_id in phase.files}


  def render(self) -> Iterator[str]:
    'Render top level PlistRoot object.'
    yield '// !$*UTF8*$!\n'
    yield '{\n'
    for k, v in vars(self.root).items():
      yield f'\t{k} = '
      if k == 'objects':
        yield from self.render_objects(v, depth=1)
      else:
        yield from self.render_el(v, depth=1, key=k)
      yield ';\n'
    yield '}\n'


  def render_objects(self, objects:Dict[str,Any], depth:int)-> Iterator[str]:
    'Special handling for the main objects list.'
    yield '{\n'
    groups = groupby(sorted(objects.items(), key=lambda kv:(kv[1].type_name, kv[0])),
       key= lambda kv: kv[1].type_name)
    for type_name, g in groups:
      yield f'\n/* Begin {type_name} section */\n'
      for k, v in g:
        yield from self.render_dict_item(k, v, depth=depth + 1, label_refs=True)
      yield f'/* End {type_name} section */\n'
    yield '\t}'


  def render_el(self, el:Any, depth:int, key:str|None=None, sort_key:Callable|None=None) -> Iterator[str]:
    if isinstance(el, str):
      return self.render_str(el, label_refs=(key not in unlabeled_keys))
    elif isinstance(el, PBX):
      return self.render_pbx(el, depth)
    elif isinstance(el, list):
      return self.render_list(el, depth, sort_key=sort_key)
    elif isinstance(el, dict):
      return self.render_dict(el, depth)
    else:
      raise ValueError(el)

  def render_str(self, s:str, label_refs:bool)-> Iterator[str]:
    yield quote_string(s)
    if label_refs and is_ref(s):
      desc = self.ref_desc(s)
      if desc:
        yield f' /* {desc} */'


  def render_pbx(self, pbx:PBX, depth:int)-> Iterator[str]:
    if pbx.is_inline:
      open_end = ''
      el_pre = ''
      el_end = ' '
      close_pre = ''
    else:
      open_end = '\n'
      el_pre = '\t' * (depth + 1)
      el_end = '\n'
      close_pre = '\t' * depth
    yield '{' + open_end
    for k, v in vars(pbx).items():
      yield el_pre
      yield from self.render_str(k, label_refs=True)
      yield ' = '
      yield from self.render_el(v, depth + 1, key=k, sort_key=pbx.sort_key(k, self.objects))
      yield ';' + el_end
    yield close_pre + '}'


  def render_dict(self, d:Dict, depth:int)-> Iterator[str]:
    yield '{\n'
    for k, v in d.items():
      yield from self.render_dict_item(k, v, depth=depth + 1, label_refs=False)
    yield '\t' * depth + '}'


  def render_dict_item(self, k:str, v:Any, depth:int, label_refs:bool)-> Iterator[str]:
    yield '\t' * depth
    yield from self.render_str(k, label_refs=label_refs)
    yield ' = '
    yield from self.render_el(v, depth)
    yield ';\n'


  def render_list(self, l:List, depth:int, sort_key:Callable|None=None)-> Iterator[str]:
    indent = '\t' * depth
    indent1 = indent + '\t'
    yield '(\n'
    if sort_key is not None:
      l = sorted(l, key=sort_key)
    for el in l:
      yield indent1
      yield from self.render_el(el, depth + 1)
      yield ',\n'
    yield indent + ')'


  def ref_desc(self, ref:str) -> str:
    pbx = self.objects[ref]
    assert isinstance(pbx, PBX)

    if isinstance(pbx, _BuildPhase):
      return pbx.label

    if isinstance(pbx, PBXBuildFile):
      if file_ref := pbx.fileRef:
        name = path_name(self.objects[file_ref].path) # type: ignore[attr-defined]
      elif product_ref := pbx.productRef:
        name = self.objects[product_ref].productName # type: ignore[attr-defined]
      else:
        name = '???'
      phase = self.buildFile_phases[ref]
      return f'{name} in {phase.label}'

    if isinstance(pbx, PBXFileReference):
      return path_name(pbx.path)

    if isinstance(pbx, PBXGroup):
      if pbx.name: return pbx.name
      if pbx.path: return path_name(pbx.path)
      return ''

    if isinstance(pbx, PBXNativeTarget):
      return pbx.name

    if isinstance(pbx, XCBuildConfiguration):
      return pbx.name

    if isinstance(pbx, XCConfigurationList):
      owner_key = self.configurationList_owners[ref]
      owner = self.objects[owner_key]
      name = self.proj_name if isinstance(owner, PBXProject) else owner.name # type: ignore[attr-defined]
      return f'Build configuration list for {owner.type_name} "{name}"'

    if isinstance(pbx, XCLocalSwiftPackageReference):
      return f'XCLocalSwiftPackageReference "{pbx.relativePath}"'

    if isinstance(pbx, XCSwiftPackageProductDependency):
      return pbx.productName

    if isinstance(pbx, PBXProject):
      return 'Project object'

    errL('warning: ref_desc: defaulted for type:', pbx.type_name)
    errL('  ', vars(pbx))
    return pbx.type_name


def render_to_str(proj_name:str, root:PlistRoot) -> str:
  r = Renderer(proj_name=proj_name, root=root)
  return ''.join(r.render())


unlabeled_keys = { 'remoteGlobalIDString' }
