# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from typing import Any, Callable, cast, Dict, get_type_hints, List, Type

from pithy.type_utils import is_a
from tolkien import Token


class PBX:
  'Abstract root class.'
  isa:str

  def __init__(self, token:Token, **kwargs:Any) -> None:
    anns = get_type_hints(cast(Callable, self))
    for k, v in kwargs.items():
      if k == 'isa': continue
      try: t = anns[k]
      except KeyError as e:
        raise DefError(token, kwargs, f'{type(self).__name__}: unknown PBX key: {k!r}') from e
      if not is_a(v, t):
        raise DefError(token, kwargs, f'key: {k!r}: expected {t.__name__}; received: {v!r}')
    vars(self).update(kwargs)

  @property
  def is_inline(self) -> bool: return False

  @property
  def label(self) -> str: return type(self).__name__

  @property
  def type_name(self) -> str: return type(self).__name__

  def sort_key(self, key:str, objects:Dict[str,'PBX']) -> Callable|None:
    return None


@dataclass
class PlistRoot:
  '''
  Independent Class for the root of the tree. This class name never appears as an "isa" value in project files.
  '''
  archiveVersion:str
  classes:Dict[str,Any]
  objectVersion:str
  objects:Dict[str,PBX] # Flat list of all objects.
  rootObject:str # Id of an object, typically a PBXProject.


class _BuildPhase(PBX):
  'Abstract intermediate class.'
  files:List[str]


class PBXCopyFilesBuildPhase(_BuildPhase):
  buildActionMask: str
  dstPath: str
  dstSubfolderSpec: str
  files: List[str]
  name: str
  runOnlyForDeploymentPostprocessing: str

  @property
  def label(self) -> str: return 'Copy Files'


class PBXBuildFile(PBX):
  fileRef:str|None = None
  productRef:str|None = None
  settings:Dict[str,object]

  @property
  def is_inline(self) -> bool: return True


class PBXContainerItemProxy(PBX):
  containerPortal:str
  proxyType:str
  remoteGlobalIDString:str
  remoteInfo:str


class PBXFileReference(PBX):
  explicitFileType:str|None = None
  fileEncoding:str
  includeInIndex:str
  lastKnownFileType:str
  name:str|None = None
  path:str
  sourceTree:str

  @property
  def is_inline(self) -> bool: return True


class PBXFrameworksBuildPhase(_BuildPhase):
  buildActionMask:str
  files:List[str]
  runOnlyForDeploymentPostprocessing:str

  @property
  def label(self) -> str: return 'Frameworks'


class PBXGroup(PBX):
  children:List[str]
  indentWidth:str
  isa:str
  name:str|None = None
  path:str|None = None
  sourceTree:str
  tabWidth:str

  def sort_key(self, key:str, objects:Dict[str,PBX]) -> Callable|None:
    if key == 'children':
      def sort_by_path(ref:str) -> str:
        obj = objects[ref]
        assert isinstance(obj, (PBXFileReference, PBXGroup)), obj
        return obj.path or obj.name or ''
      return sort_by_path
    return None


class PBXHeadersBuildPhase(_BuildPhase):
  buildActionMask:str
  files:list
  runOnlyForDeploymentPostprocessing:str

  @property
  def label(self) -> str: return 'Headers'


class PBXNativeTarget(PBX):
  buildConfigurationList:str
  buildPhases:list
  buildRules:list
  dependencies:list
  name:str
  packageProductDependencies:list
  productName:str
  productReference:str
  productType:str


class PBXProject(PBX):
  attributes:dict
  buildConfigurationList:str
  compatibilityVersion:str
  developmentRegion:str
  hasScannedForEncodings:str
  knownRegions:list
  mainGroup:str
  packageReferences:list
  productRefGroup:str
  projectDirPath:str
  projectRoot:str
  targets:list


class PBXResourcesBuildPhase(_BuildPhase):
  buildActionMask:str
  files:list
  runOnlyForDeploymentPostprocessing:str

  @property
  def label(self) -> str: return 'Resources'


class PBXShellScriptBuildPhase(_BuildPhase):
  buildActionMask:str
  files:list
  inputPaths:list
  inputFileListPaths:list
  name:str
  outputPaths:list
  outputFileListPaths:list
  runOnlyForDeploymentPostprocessing:str
  shellPath:str
  shellScript:str
  showEnvVarsInLog:str

  @property
  def label(self) -> str: return self.name


class PBXSourcesBuildPhase(_BuildPhase):
  buildActionMask:str
  files:list
  runOnlyForDeploymentPostprocessing:str

  @property
  def label(self) -> str: return 'Sources'


class PBXTargetDependency(PBX):
  target:str
  targetProxy:str


class XCBuildConfiguration(PBX):
  baseConfigurationReference:str
  buildSettings:dict
  name:str


class XCConfigurationList(PBX):
  buildConfigurations:list
  defaultConfigurationIsVisible:str
  defaultConfigurationName:str


class XCLocalSwiftPackageReference(PBX):
  relativePath: str


class XCSwiftPackageProductDependency(PBX):
  package: str
  productName: str


node_classes:Dict[str,Type[PBX]] = {
  name: c for (name, c) in locals().items() if (name.startswith('PBX') or name.startswith('XC')) }


class DefError(Exception):
  def __init__(self, token:Token, dictionary:Dict[str,Any], msg:str) -> None:
    super().__init__(msg)
    self.token = token
    self.dictionary = dictionary
