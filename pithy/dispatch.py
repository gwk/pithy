# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
from typing import Any, Callable, Dict


class DispatchTypeError(TypeError): pass

class MethodDispatch:
  '''
  Create a single dispatch method family that dispatches on the type of the first argument.
  Note that the implementation currently dispatches on exact types only.
  TODO: MRO resolution as in singledispatch.

  Usage:
  | class C():
  |   class describe(MethodDispatch): pass
  |
  |  @describe
  |  def _(self, item:int) -> None: print(f'int: {item}')
  |
  |  @describe
  |  def _(self, item:str) -> None: print(f'str: {item}')


  References:
  * https://stackoverflow.com/questions/24601722/how-can-i-use-functools-singledispatch-with-instance-methods
  * https://medium.com/@vadimpushtaev/decorator-inside-python-class-1e74d23107f6.
  TODO: better typing.
  '''

  def __new__(cls, method: Callable):
    try: methods: Dict[type, Callable] = cls.methods # type: ignore
    except AttributeError:
      methods = {}
      cls.methods = methods
    sig = inspect.signature(method)
    pars = list(sig.parameters.values())
    par_self = pars[0]
    par_node = pars[1]
    assert par_self.name == 'self'
    methods[par_node.annotation] = method

  @classmethod
  def method(cls, arg):
    try: return cls.methods[type(arg)]
    except KeyError as e: raise DispatchTypeError(type(arg)) from e

  @classmethod
  def dispatch(cls, instance, arg, *args, **kwargs):
    method = cls.method(arg)
    return method(instance, arg, *args, **kwargs)
