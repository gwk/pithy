# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import *


T = TypeVar('T')

DictType = TypeVar('DictType', bound=dict)
TupleType = TypeVar('TupleType', bound=tuple)

class _MISSING_TYPE: ...

class _InitVarMeta(type): ...

def asdict(obj: Any, *, dict_factory:DictType=...) -> DictType: ...

def astuple(obj: Any, *, tuple_factory:TupleType=...) -> TupleType: ...

def dataclass(_cls:Optional[Type[T]]=..., *, init:bool=..., repr:bool=...,
  eq:bool=..., order:bool=..., hash:Optional[bool]=..., frozen:bool=...) -> Type[T]: ...

class Field(Generic[T]):
  name: str
  type: Type[T]
  default: T
  default_factory: Callable[[], T]
  repr: bool
  hash: Optional[bool]
  init: bool
  compare: bool
  metadata: Optional[Mapping[str, Any]]


def field(*, default:Union[T, _MISSING_TYPE]=..., default_factory:Union[Callable[[], T], _MISSING_TYPE]=...,
  init:bool=..., repr:bool=..., hash:Optional[bool]=..., compare:bool=..., metadata:Optional[Mapping[str, Any]]=...) -> Field: ...

def fields(class_or_instance:Type) -> Tuple[Field, ...]: ...

def is_dataclass(obj:Any) -> bool: ...

class FrozenInstanceError(AttributeError): ...

class InitVar(metaclass=_InitVarMeta): ...

def make_dataclass(cls_name:str, fields:Iterable[Union[str, Tuple[str, type], Tuple[str, type, Field]]], *,
  bases:Tuple[type, ...]=..., namespace:Dict[str, Any]=...,
  init:bool=..., repr:bool=..., eq:bool=..., order:bool=..., hash:bool=..., frozen:bool=...): ...

def replace(obj:T, **changes:Any) -> T: ...
