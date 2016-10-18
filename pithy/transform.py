from collections import Counter
from enum import Enum

from .fs import path_ext, path_join, path_stem
from .io import errFL, err_progress, writeFL
from .meta import main_file_path


class Transformer:
  '''
  A data transformation pipeline.
  '''

  class DropItem(Exception):
    'Exception signals the Transformer to immediately drop the current item and continue to the next one.'


  def __init__(self, seq, log_stem='_build/', log_index_width=2, progress_frequency=0.1):

    self.seq = seq
    self.log_stem = log_stem
    self.log_index_width = log_index_width
    self.progress_frequency = progress_frequency

    self.stages = []
    self.stage_names = []
    self.counts = []
    self.log_files = []


  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    if exc_type: return None
    self.run()


  def _add_stage(self, name, fn):
    if name in self.stage_names: # makes adding all stages quadratic time, but len(stages) is low.
      raise KeyError('Transformer: stage name is a duplicate: {}'.format(name))
    self.stage_names.append(name)
    self.stages.append(fn)
    if len(self.counts) != len(self.stages): # this stage has no logger.
      assert len(self.counts) == len(self.stages) - 1
      self.counts.append(-1)


  def _mk_log_fn(self, mode, name, ext):
    'create a dedicated log file and logging function for use by a particular stage.'
    index = len(self.stages)
    path = '{}{:0{width}}-{}-{}{}'.format(self.log_stem, index, mode, name, ext,
      width=self.log_index_width)
    f = open(path, 'w')
    self.log_files.append(f)

    counts = self.counts
    assert len(counts) == index
    counts.append(0)

    def log_fn(fmt, *items):
      counts[index] += 1
      writeFL(f, fmt, *items)

    return log_fn


  def flag(self, fn):
    '''
    add a flag stage.
    the decorated function function should take an input item,
    and return a truth value indicating whether the item should be logged.
    '''
    name = fn.__name__
    log_fn = self._mk_log_fn('flag', name, '.txt')

    def flag_fn(item):
      if fn(item):
        log_fn('{!r}\n', item)
      return item

    self._add_stage(name, edit_fn)


  def drop(self, fn):
    '''
    add a drop stage.
    the decorated function should be a predicate that takes an input item,
    and returns a truth value indicating whether the item should be dropped from the pipeline.
    drops are logged as deltas.
    '''
    name = fn.__name__
    log_fn = self._mk_log_fn('drop', name, '.diff')
    DropItem = self.DropItem

    def drop_fn(item):
      if fn(item):
        log_fn('- {!r}\n', item)
        raise DropItem
      return item

    self._add_stage(name, drop_fn)


  def keep(self, fn):
    '''
    add a keep stage.
    the decorated function should be a predicate that takes an input item,
    and returns a truth value indicating whether the item should continue in the pipeline.
    no logging is performed.
    '''

    def keep_fn(item):
      if fn(item):
        return item
      raise DropItem

    self.add_stage(fn.__name__, keep_fn)


  def edit(self, fn):
    '''
    add an edit stage.
    the decorated function should return either the original item or an edited item.
    if the input is not equal to the output then the edit is logged as a delta.
    '''
    name = fn.__name__
    log_fn = self._mk_log_fn('edit', name, '.diff')

    def edit_fn(item):
      edited = fn(item)
      if edited != item:
        log_fn('- {!r}\n+ {!r}\n', item, edited)
      return edited

    self._add_stage(name, edit_fn)


  def convert(self, fn):
    '''
    add a conversion stage.
    the decorated function should convert the input item to an output item.
    no logging is performed.'
    '''
    self._add_stage(fn.__name__, fn)


  def put(self, fn):
    '''
    add an output stage.
    the decorated function should output the item, either to stdout or to a file.
    The decorated function does not need to return the item;
    this is handled by the decorator wrapper.
    no logging is performed.
    '''
    def put_fn(item):
      fn(item)
      return item

    self._add_stage(fn.__name__, put_fn)


  def run(self):

    if not self.stages:
      errFL('Transformer: WARNING: no transform functions found; '
        "transformation stage functions must be decorated with the transformer's convert/drop/edit/flag properties.")

    # create local bindings to avoid attribute lookups in the loop.
    stages = self.stages
    DropItem = self.DropItem

    errFL('◊ transform stages: {}.', ', '.join(self.stage_names))

    for item in err_progress(self.seq, 'transform', 'items', frequency=self.progress_frequency):
      try:
        for fn in stages:
          item = fn(item)
      except DropItem:
        continue

    for f in self.log_files:
      f.close()

    for i, (name, count) in enumerate(zip(self.stage_names, self.counts)):
      if count == -1: count = '-'
      errFL('◊   {:0{width}}-{}: {}', i, name, count, width=self.log_index_width)

