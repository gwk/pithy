# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from enum import Enum
from types import TracebackType
from typing import Any, Callable, ContextManager, Generic, Iterable, List, Optional, TextIO, Type, TypeVar

from .fs import path_ext, path_join, path_stem
from .io import errL, err_progress, writeL


_T = TypeVar('_T')
_I = TypeVar('_I')
_O = TypeVar('_O')
Stage = Callable[[_I], _O]
Pred = Callable[[_I], bool]
Put = Callable[[_I], None]


class _DropItem(Exception):
  'Exception signals the Transformer to immediately drop the current item and continue to the next one.'


class Transformer(Generic[_T], ContextManager):
  '''
  A data transformation pipeline.
  '''



  def __init__(self, iterable: Iterable[_T], log_stem='_build/', log_index_width=2, progress_frequency=0.1) -> None:

    self.iterable = iterable
    self.log_stem = log_stem
    self.log_index_width = log_index_width
    self.progress_frequency = progress_frequency

    self.stages: List[Callable] = []
    self.stage_names: List[str] = []
    self.counts: List[int] = []
    self.log_files: List[TextIO] = []


  def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException],
   traceback: Optional[TracebackType]) -> None:
    if exc_type: return
    self.run()


  def _add_stage(self, name: str, fn: Stage) -> None:
    if name in self.stage_names: # makes adding all stages quadratic time, but len(stages) is low.
      raise KeyError('Transformer: stage name is a duplicate: {}'.format(name))
    self.stage_names.append(name)
    self.stages.append(fn)
    if len(self.counts) != len(self.stages): # this stage has no logger.
      assert len(self.counts) == len(self.stages) - 1
      self.counts.append(-1)


  def _mk_log_fn(self, mode: str, name: str, ext: str) -> Callable[..., None]:
    'create a dedicated log file and logging function for use by a particular stage.'
    index = len(self.stages)
    path = f'{self.log_stem}{index:0{self.log_index_width}}-{mode}-{name}{ext}'
    f = open(path, 'w')
    self.log_files.append(f)

    counts = self.counts
    assert len(counts) == index
    counts.append(0)

    def log_fn(*items: Any) -> None:
      counts[index] += 1
      writeL(*items)

    return log_fn


  def flag(self, pred: Pred) -> None:
    '''
    add a flag stage.
    the decorated function function should take an input item,
    and return a truth value indicating whether the item should be logged.
    '''
    name = pred.__name__
    log_fn = self._mk_log_fn('flag', name, '.txt')

    def flag_fn(item: _I) -> _I:
      if pred(item):
        log_fn(f'{item!r}\n')
      return item

    self._add_stage(name, flag_fn)


  def drop(self, pred: Pred) -> None:
    '''
    add a drop stage.
    the decorated function should be a predicate that takes an input item,
    and returns a truth value indicating whether the item should be dropped from the pipeline.
    drops are logged as deltas.
    '''
    name = pred.__name__
    log_fn = self._mk_log_fn('drop', name, '.diff')

    def drop_fn(item: _I) -> _I:
      if pred(item):
        log_fn(f'- {item!r}\n')
        raise _DropItem
      return item

    self._add_stage(name, drop_fn)


  def keep(self, pred: Pred) -> None:
    '''
    add a keep stage.
    the decorated function should be a predicate that takes an input item,
    and returns a truth value indicating whether the item should continue in the pipeline.
    no logging is performed.
    '''

    def keep_fn(item: _I) -> _I:
      if pred(item):
        return item
      raise _DropItem

    self._add_stage(pred.__name__, keep_fn)


  def edit(self, fn: Stage) -> None:
    '''
    add an edit stage.
    the decorated function should return either the original item or an edited item.
    if the input is not equal to the output then the edit is logged as a delta.
    '''
    name = fn.__name__
    log_fn = self._mk_log_fn('edit', name, '.diff')

    def edit_fn(item: _I) -> _O:
      edited = fn(item)
      if edited != item:
        log_fn(f'- {item!r}\n+ {edited!r}\n')
      return edited # type: ignore

    self._add_stage(name, edit_fn)


  def convert(self, fn: Stage) -> None:
    '''
    add a conversion stage.
    the decorated function should convert the input item to an output item.
    no logging is performed.'
    '''
    self._add_stage(fn.__name__, fn)


  def put(self, fn: Put) -> None:
    '''
    add an output stage.
    the decorated function should output the item, either to stdout or to a file.
    The decorated function does not return the item;
    this is handled by the decorator wrapper.
    no logging is performed.
    '''
    def put_fn(item: _I) -> _I:
      fn(item)
      return item

    self._add_stage(fn.__name__, put_fn)


  def run(self) -> None:

    if not self.stages:
      errL('Transformer: WARNING: no transform functions found; '
        "transformation stage functions must be decorated with the transformer's convert/drop/edit/flag properties.")

    # create local bindings to avoid attribute lookups in the loop.
    stages = self.stages

    errL(f'◊ transform stages: {", ".join(self.stage_names)}.')

    for item in err_progress(self.iterable, 'transform', 'items', frequency=self.progress_frequency):
      try:
        for fn in stages:
          item = fn(item)
      except _DropItem:
        continue

    for f in self.log_files:
      f.close()

    for i, (name, count) in enumerate(zip(self.stage_names, self.counts)):
      c = '-' if count == -1 else count
      width = self.log_index_width
      errL('◊   {i:0{width}}-{name}: {c}')

