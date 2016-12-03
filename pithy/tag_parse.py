# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


'''
The tag_parse module provides a means for quickly constructing parsers for simple languages,
where each node of the syntax tree is either a lexical token
(as recognized by a regular expression)
or else a branch node delimited by distinct open and close tokens surrounding any child nodes.
Examples of such languages include HTML
(by treating the attributes in an opening tag as an opaque part of the token)
and Lisp-style S-Expressions.
The leaves of the syntax tree are simply strings;
the branches are TagTree instances, which are subclasses of tuple.
'''

import re

from itertools import chain, islice
from pithy.ansi import TXT_R, TXT_Y, RST_TXT
from .buffer import Buffer


class TagRule():
  def __init__(self, open_pattern, close_pattern, open_close_tokens_match_fn=None):
    self.open_pattern = open_pattern
    self.close_pattern = close_pattern
    self.open_close_tokens_match_fn = open_close_tokens_match_fn


class TagParser():

  def __init__(self, leaf_patterns, tag_rules):
    # parser works by wrapping each start and end pattern in a capture group.
    # the group itself is not used,
    # but the match group index indicates which open or close pattern matched.
    open_choices = ['({})'.format(r.open_pattern) for r in tag_rules]
    close_choices = ['({})'.format(r.close_pattern) for r in tag_rules]
    lexer_pattern = '|'.join(chain(open_choices, close_choices, leaf_patterns))
    self.lexer = re.compile(lexer_pattern)
    self.open_close_tokens_match_fns = [r.open_close_tokens_match_fn for r in tag_rules]
    self.last_open_index = len(tag_rules)


  def _parse(self, leaf_replacements, text, match_stream, pos, depth, subs, close_pred, parent_close_pred):

    def append_leaf(leaf):
      subs.append(leaf_replacements.get(leaf, leaf))

    def flush_leaf(pos, end_index):
      leaf_text = text[pos:end_index]
      if leaf_text:
        append_leaf(leaf_text)

    for match in match_stream:
      flush_leaf(pos, match.start())
      pos = match.end()
      token = match.group()
      match_index = match.lastindex # only start and end tokens have a group.
      if match_index is None: # leaf token.
        append_leaf(token)
      elif match_index <= self.last_open_index: # found a start token (groups are 1-indexed).
        open_close_tokens_match_fn = self.open_close_tokens_match_fns[match_index - 1]
        exp_index = match_index + self.last_open_index
        def child_close_pred(close_match_index, close_token):
          return (close_match_index == exp_index
           and (open_close_tokens_match_fn is None
             or open_close_tokens_match_fn(token, close_token)))
        sub, pos = self._parse(leaf_replacements, text, match_stream, pos, depth + 1,
          subs=[token], close_pred=child_close_pred, parent_close_pred=close_pred)
        subs.append(sub)
      elif close_pred(match_index, token):
        subs.append(token)
        return TagTree(*subs), pos
      elif parent_close_pred(match_index, token): # parent end; missing end token.
        match_stream.push(match) # put the parent end token back into the stream.
        return TagTreeUnterminated(*subs), pos
      else: # unexpected end token.
        subs.append(TagTreeUnexpected(token))
    # end.
    flush_leaf(pos, len(text))
    return TagTreeRoot(*subs) if depth == 0 else TagTreeUnterminated(*subs), len(text)


  def parse(self, text, leaf_replacements=None):
    match_stream = IterBuffer(self.lexer.finditer(text))
    res, pos = self._parse(leaf_replacements or {}, text, match_stream, pos=0, depth=0,
      subs=[], close_pred=lambda i, t: False, parent_close_pred=lambda i, t: False)
    return res



class TagTree(tuple):
  '''
  TagParser AST node.
  The str() value of the node is equal to the original text.
  '''

  def __new__(cls, *args):
    assert all(isinstance(el, (str, TagTree)) for el in args)
    return super().__new__(cls, args)

  def __repr__(self):
    return '{}({})'.format(type(self).__name__, ', '.join(repr(el) for el in self))

  def __str__(self):
    return ''.join(self.walk_all())

  def __getitem__(self, key):
    if isinstance(key, slice):
      return type(self)(super().__getitem__(key)) # create a TagTree as the slice.
    return super().__getitem__(key)

  class_label = 'Tag'
  ansi_color = ''
  ansi_reset = ''

  @property
  def is_flawed(self):
    return isinstance(self, TagTreeFlawed) or self.has_flawed_els

  @property
  def has_flawed_els(self):
    return any(isinstance(el, TagTree) and el.is_flawed for el in self)

  @property
  def contents(self):
    if len(self) < 2: raise ValueError('bad TagTree: {!r}'.format(self))
    return islice(self, 1, len(self) - 1) # omit start and end tag.


  def walk_all(self):
    for el in self:
      if isinstance(el, str):
        yield el
      else:
        yield from el.walk_all()


  def walk_contents(self):
    for el in self.contents:
      if isinstance(el, str):
        yield el
      else:
        yield from el.walk_contents()


  def walk_branches(self, should_enter_tag_fn=lambda tag: True):
    for el in self:
      if isinstance(el, TagTree):
        yield el
        if should_enter_tag_fn(el[0]):
          yield from el.walk_branches(should_enter_tag_fn=should_enter_tag_fn)


  def _structured_desc(self, res, depth):
    'multiline indented description helper.'
    if self.ansi_color: res.append(self.ansi_color)
    res.append(self.class_label)
    res.append(':')
    if self.ansi_reset: res.append(self.ansi_reset)
    d = depth + 1
    nest_spacer = '\n' + ('  ' * d)
    spacer = ' ' # the spacer to use for string tokens.
    for el in self:
      if isinstance(el, str):
        if spacer: res.append(spacer)
        res.append(repr(el))
        spacer = ''
      else:
        res.append(nest_spacer)
        el._structured_desc(res, d)
        spacer = nest_spacer

  def structured_desc(self, depth=0):
    res = []
    self._structured_desc(res, depth)
    return ''.join(res)


class TagTreeRoot(TagTree):
  class_label = 'Root'
  @property
  def contents(self):
    return self # no tags at root level.


class TagTreeFlawed(TagTree):
  'abstract parent of the various flaw types.'
  pass


class TagTreeUnexpected(TagTreeFlawed):
  'unexpected trees consist solely of an unpaired closing tag.'

  class_label = 'Unexpected'
  ansi_color = TXT_R
  ansi_reset = RST_TXT

  def __new__(cls, *args):
    assert len(args) == 1
    return super().__new__(cls, *args)

  @property
  def contents(self):
    assert len(self) == 1
    return ()


class TagTreeUnterminated(TagTreeFlawed):
  'unterminated trees are missing a closing tag.'

  class_label = 'Unterminated'
  ansi_color = TXT_Y
  ansi_reset = RST_TXT

  @property
  def contents(self):
    return islice(self, 1, len(self)) # omit the start tag only.
