# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from collections import defaultdict
from html import escape as html_escape
from os import environ
from typing import Any, Callable, cast, Iterable, Iterator, Match, NoReturn, TextIO, Union

import pygments
import pygments.lexers
import pygments.token
from pithy.html.semantics import phrasing_tags
from pithy.io import errSL, errSN
from pithy.json import load_json
from pithy.path import norm_path, path_dir, path_ext, path_join, path_name_stem, rel_path
from pithy.url import url_path
from pygments.token import Token


__all__ = ['writeup', 'writeup_dependencies', 'default_css', 'minify_css', 'minify_js', 'default_js']


SrcLine = tuple[int, str]


def writeup(src_path: str, src_lines: Iterable[SrcLine], description: str, author: str,
  css_lines:Iterator[str]|None, js: str|None, emit_doc: bool, target_section: str|None, emit_dbg: bool) -> Iterable[str]:
  'generate a complete html document from a writeup file (or stream of lines).'

  ctx = Ctx(src_path=src_path, should_embed=True, emit_dbg=emit_dbg)
  parse(ctx=ctx, src_lines=src_lines)

  if emit_doc:
    yield from [
      '<!DOCTYPE html>',
      '<html>',
      '<head>',
      '<meta charset="utf-8" />',
      f'<title>{ctx.title}</title>',
      f'<meta name="description" content="{description}" />',
      f'<meta name="author" content="{author}" />',
      '<link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgo=" />', # empty icon.
    ]
    if css_lines is not None:
      yield '<style type="text/css">'
      yield from css_lines
      yield from ctx.render_css()
      yield '</style>'
    if js:
      yield f'<script type="text/javascript"> "use strict";\n{js}</script>'

    yield from ctx.emit_head()
    yield '</head>'
    yield '<body id="body">'

  yield from ctx.emit_body(depth=0, target_section=target_section)
  if target_section is not None and not ctx.found_target_section: exit(f'target section not found: {target_section!r}')

  if bool(js):
    # Generate tables.
    yield '<script type="text/javascript"> "use strict";'
    section_ids = ','.join(f"'s{sid}'" for sid in ctx.section_ids)
    yield f'section_ids = [{section_ids}];'
    paging_ids = ','.join(f"'s{pid}'" for pid in ctx.paging_ids)
    yield f"paging_ids = ['body', {paging_ids}];"
    yield '</script>'
  if emit_doc:
    if ctx.license_lines:
      yield '<footer id="footer">'
      yield '<br />\n'.join(ctx.license_lines)
      yield '</footer>'
    yield '</body>\n</html>'


def writeup_dependencies(src_path:str, text_lines: Iterable[str], emit_dbg=False) -> list[str]:
  '''
  Return a list of dependencies from the writeup in `src_lines`.
  '''
  ctx = Ctx(src_path=src_path, should_embed=False, emit_dbg=emit_dbg)
  parse(ctx=ctx, src_lines=enumerate(text_lines))
  return sorted(ctx.dependencies)


class Span:
  'A tree node of inline HTML content.'
  def __init__(self, text: str):
    self.text = text

  def html(self, depth: int) -> str:
    return html_esc(self.text)

  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.text!r})'

Spans = tuple[Span, ...]


class CodeSpan(Span):
  def html(self, depth: int) -> str:
    'convert backtick code span to html.'
    span_char_esc_fn = lambda m: m.group(0)[1:] # strip leading '\' escape.
    text_escaped = span_backtick_esc_re.sub(span_char_esc_fn, self.text)
    text_escaped_html = html_esc(text_escaped)
    text_spaced = text_escaped_html.replace(' ', '&nbsp;') # TODO: should this be breaking space for long strings?
    return f'<code class="inline">{text_spaced}</code>'


class AttrSpan(Span):
  def __init__(self, text: str, attrs: dict[str, str]):
    super().__init__(text=text)
    self.attrs = attrs

  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.text!r}, attrs={self.attrs})'


class BoldSpan(AttrSpan):
  def html(self, depth: int) -> str:
    return f'<b{fmt_attrs(self.attrs)}>{html_esc(self.text)}</b>'


class EmbedSpan(AttrSpan):
  def __init__(self, text: str, attrs: dict[str, str], path: str, contents: tuple[str, ...]):
    super().__init__(text=text, attrs=attrs)
    self.path = path
    self.contents = contents

  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.text!r}, attrs={self.attrs}, path={self.path!r}, contents={self.contents})'


  def html(self, depth: int) -> str:
    if attrs_bool(self.attrs, 'titled'):
      label = f'<div class="embed-label">{html_esc(self.path)}</div>\n'
    else:
      label= ''

    j = '\n' + '  ' * (depth + 1)
    # TODO: migrate various embed html details up to here?
    return label + j.join(self.contents)


class GenericSpan(AttrSpan):

  def __init__(self, text:str, attrs:dict[str,str], tag:str):
    super().__init__(text=text, attrs=attrs)
    self.tag = tag

  def html(self, depth: int) -> str:
    return f'<{self.tag}{fmt_attrs(self.attrs)}>{html_esc(self.text)}</span>'


class ImgSpan(AttrSpan):
  def html(self, depth: int) -> str:
    return f'<img src="{html_esc_attr(self.text)}"{fmt_attrs(self.attrs)}/>'


class LinkSpan(AttrSpan):
  def __init__(self, text: str, attrs: dict[str, str], tag: str, words: list[str], ctx: 'Ctx', src: SrcLine):
    super().__init__(text=text, attrs=attrs)
    self.tag = tag
    if not words:
      ctx.error(src, f'link is empty: {self.tag!r}')
    if tag == 'link':
      self.link = words[0]
    else:
      self.link = f'{self.tag}:{words[0]}'
    if len(words) == 1:
      self.visible = self.link
    else:
      self.visible = ' '.join(words[1:])

  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.text!r}, attrs={self.attrs}, tag={self.tag!r}, link={self.link!r}, visible={self.visible!r})'

  def html(self, depth: int) -> str:
    return f'<a href="{html_esc_attr(self.link)}"{fmt_attrs(self.attrs)}>{html_esc(self.visible)}</a>'


class Block:
  'A tree node of block-level HTML content.'
  def finish(self, ctx: 'Ctx') -> None: pass
  def html(self, ctx: 'Ctx', depth: int) -> Iterable[str]: raise NotImplementedError


class Section(Block):
  def __init__(self, section_depth: int, quote_depth: int, index_path: tuple[int, ...], title: Spans):
    self.section_depth = section_depth
    self.quote_depth = quote_depth
    self.index_path = index_path
    self.title = title
    self.blocks: list[Block] = []

  def __repr__(self) -> str: return f'Section({self.sid}, {self.title}, {len(self.blocks)} blocks)'

  @property
  def sid(self) -> str: return '.'.join(str(i) for i in self.index_path)

  def html(self, ctx: 'Ctx', depth: int) -> Iterable[str]:
    sid = self.sid
    ctx.section_ids.append(sid)
    if self.section_depth <= 2: ctx.paging_ids.append(sid)
    quote_prefix = f'q{self.quote_depth}' if self.quote_depth else ''
    yield indent(depth, f'<section class="S{self.section_depth}" id="{quote_prefix}s{sid}">')
    h_num = min(6, self.section_depth)
    yield indent(depth + 1, f'<h{h_num} id="h{sid}">{html_for_spans(self.title, depth=depth)}</h{h_num}>')
    for block in self.blocks:
      yield from block.html(ctx, depth + 1)
    yield indent(depth, '</section>')


class UList(Block):
  def __init__(self, list_level: int):
    super().__init__()
    self.list_level = list_level # 1-indexed (top-level list is 1; no lists is 0).
    self.items: list[ListItem] = []

  def __repr__(self) -> str: return f'UList({self.list_level}, {len(self.items)} items)'

  def html(self, ctx: 'Ctx', depth: int) -> Iterable[str]:
    yield indent(depth, f'<ul class="L{self.list_level}">')
    for item in self.items:
      yield from item.html(ctx, depth + 1)
    yield indent(depth, '</ul>')


class ListItem(Block):
  def __init__(self, list_level: int):
    self.list_level = list_level # 1-indexed (top-level list is 1; no lists is 0).
    self.blocks: list[Block] = []

  def __repr__(self) -> str: return f'ListItem({self.list_level}, {len(self.blocks)} blocks)'

  def html(self, ctx: 'Ctx', depth: int) -> Iterable[str]:
    if len(self.blocks) == 1 and isinstance(self.blocks[0], Text):
      if len(self.blocks[0].lines) == 1:
        yield indent(depth, f'<li>{html_for_spans(self.blocks[0].lines[0], depth=depth)}</li>')
      else:
        yield indent(depth, '<li>')
        for i, line in enumerate(self.blocks[0].lines):
          if i: yield indent(depth, '<br />')
          yield indent(depth + 1, html_for_spans(line, depth=depth))
        yield indent(depth, '</li>')
    else:
      yield indent(depth, '<li>')
      for block in self.blocks:
        yield from block.html(ctx, depth + 1)
      yield indent(depth, '</li>')


BranchBlock = Union[Section, UList, ListItem]


class LeafBlock(Block):
  def __init__(self) -> None:
    self.src_lines: list[SrcLine] = []
    self.content_lines: list[str] = []

  def __repr__(self) -> str:
    head = f'{self.src_lines[0][1][0:64]!r}… {len(self.src_lines)} lines' if self.src_lines else ''
    return f'{type(self).__name__}({head})'


class Quote(LeafBlock):
  def __init__(self) -> None:
    super().__init__()
    self.blocks: list[Block] = []

  def finish(self, ctx: 'Ctx') -> None:
    quote_ctx = Ctx(
      src_path=ctx.src_path,
      project_dir=ctx.project_dir,
      quote_depth=ctx.quote_depth + 1,
      is_versioned=False,
      warn_missing_final_newline=False,
      should_embed=ctx.should_embed,
      emit_dbg=ctx.emit_dbg)
    unquoted_src_lines = list(enumerate(self.content_lines, self.src_lines[0][0]))
    parse(ctx=quote_ctx, src_lines=unquoted_src_lines)
    self.blocks = quote_ctx.blocks

  def html(self, ctx: 'Ctx', depth: int) -> Iterable[str]:
    yield indent(depth, '<blockquote>')
    for block in self.blocks:
      yield from block.html(ctx, depth=depth + 1)
    yield indent(depth, '</blockquote>')


class Code(LeafBlock):

  def html(self, ctx: 'Ctx', depth: int) -> Iterable[str]:
    yield '<div class="code-block">'
    for line in self.content_lines:
      content = html_esc(line)
      yield f'<code class="line">{content}</code>'
    yield '</div>'


class LangBlock(LeafBlock):

  def __init__(self) -> None:
    super().__init__()
    self.lang = ''
    self.lines:list[str] = []
    self.attrs:dict[str,str] = {}

  def finish(self, ctx: 'Ctx') -> None:
    lang_src = self.src_lines[0]
    lang_text = lang_src[1]
    assert lang_text.startswith('%')
    lang_text = lang_text[1:]
    lang, attrs, words = parse_tag_attrs_body(ctx, lang_src, lang_text)
    self.lang = lang
    self.attrs = attrs
    if not lang in langs:
      ctx.error(self.src_lines[0], f'invalid language block: {lang!r}.')
    if words:
      self.lines.append(' '.join(words))
    self.lines.extend(strip_lang_line(l[1]) for l in self.src_lines[1:])

    num_lines = len(self.lines)
    is_multiline = (num_lines > 1)

    def check_oneline() -> None:
      if is_multiline: ctx.error(self.src_lines[0], f'{lang} block must be a single line; found {num_lines}.')

    if lang == 'css':
      for line in self.lines:
        for word in line.split():
          ctx.head_text.append(f'<link rel="stylesheet" href="{word}">')
    elif lang == 'div':
      check_oneline()
    elif lang == 'head':
      ctx.head_text.extend(l.strip() for l in self.lines)
    elif lang == 'img':
      if 'src' in self.attrs: ctx.error(self.src_lines[0], 'img cannot have `src` specified as attribute.')
    elif lang == 'style':
      ctx.head_text.extend(minify_css(self.lines))
    elif lang == 'title':
      check_oneline()
      ctx.title = self.lines[0].strip()


  def html(self, ctx: 'Ctx', depth: int) -> Iterable[str]:
    if self.lang in ('css', 'head', 'style', 'title'):
      return # Already emitted in head_text.
    if self.lang == 'div':
      if ctx.open_div:
        yield '</div>'
      yield f'<div{fmt_attrs(self.attrs)}>'
      ctx.open_div = True
    elif self.lang == 'html':
      assert not self.attrs
      yield from self.lines
    elif self.lang == 'img':
      for line in self.lines:
        for word in line.split():
          yield f'<img{fmt_attrs(self.attrs)} src="{html_esc_attr(word)}"/>'
    else:
      raise NotImplementedError(self.lang)


langs = frozenset({'css', 'div', 'head', 'html', 'img', 'style', 'title'})


def strip_lang_line(line:str) -> str:
  assert line.startswith('% ') and line.endswith('\n'), repr(line)
  return line[2:-1]


class Text(LeafBlock):
  def __init__(self) -> None:
    super().__init__()
    self.lines: list[Spans] = []

  def finish(self, ctx: 'Ctx') -> None:
    self.lines = [parse_spans(ctx, src=src, text=text) for (src, text) in zip(self.src_lines, self.content_lines)]

  def html(self, ctx: 'Ctx', depth: int) -> Iterable[str]:
    assert self.lines
    yield indent(depth, '<p>')
    for i, line in enumerate(self.lines):
      if i: yield indent(depth, '<br />')
      yield indent(depth + 1, html_for_spans(line, depth=depth))
    yield indent(depth, '</p>')



class Ctx:
  '''
  Parser context.
  Converts input writeup source text to output html lines and dependencies.
  '''

  def __init__(self, *, src_path:str, should_embed:bool, project_dir:str='', is_versioned=True,
   warn_missing_final_newline=True, quote_depth=0, line_offset=0, emit_dbg=False) -> None:
    self.src_path = src_path
    self.title = path_name_stem(src_path)
    self.should_embed = should_embed
    self.is_versioned = is_versioned
    self.warn_missing_final_newline = warn_missing_final_newline
    self.quote_depth = quote_depth
    self.line_offset = line_offset
    self.emit_dbg = emit_dbg

    self.project_dir = norm_path(project_dir or environ.get('PROJECT_DIR', '.'))
    self.src_dir = path_dir(src_path)
    self.license_lines: list[str] = []
    self.head_text: list[str] = []
    self.stack: list[Block] = [] # stack of currently open content blocks.
    self.blocks: list[Block] = [] # top level blocks.
    self.dependencies: list[str] = []
    self.section_ids: list[str] = [] # accumulated list of all section ids.
    self.paging_ids: list[str] = [] # accumulated list of all paging (level 1 & 2) section ids.
    self.css = defaultdict[str, list[str]](list)
    self.found_target_section = False
    self.title = ''
    self.open_div = False


  @property
  def depth(self) -> int:
    return len(self.stack)

  @property
  def list_level(self) -> int:
    for block in reversed(self.stack):
      if isinstance(block, (UList, ListItem)):
        return block.list_level
    return 0

  @property
  def top(self) -> Block:
    return self.stack[-1]

  def push(self, block: Block) -> None:
    if self.stack:
      section = self.top
      assert isinstance(section, (Section, ListItem))
      section.blocks.append(block)
    else:
      self.blocks.append(block)
    self.stack.append(block)

  def pop(self) -> Block:
    popped = self.stack.pop()
    popped.finish(self)
    return popped

  def pop_to_section_depth(self, section_depth: int) -> int:
    prev_index = 0
    while self.depth > section_depth:
      prev = self.pop()
      assert isinstance(prev, Section)
      prev_index = prev.index_path[section_depth]
    return prev_index

  def pop_to_list(self, list_level: int) -> None:
    while self.stack:
      top = self.top
      if isinstance(top, Section): return
      if isinstance(top, UList) and top.list_level <= list_level: return
      if isinstance(top, ListItem) and top.list_level < list_level: return
      self.pop()

  def append_to_leaf_block(self, src: SrcLine, list_level: int, block_type: type, content: str) -> None:
    self.dbg(src, "APPEND", list_level, block_type.__name__)
    while self.stack:
      top = self.top
      if isinstance(top, Section): break
      if isinstance(top, ListItem) and top.list_level <= list_level: break
      if isinstance(top, block_type) and self.list_level == list_level: break
      self.pop()
    if self.stack and isinstance(self.top, block_type):
      leaf = self.top
    else:
      leaf = block_type()
      self.push(leaf)
    assert isinstance(leaf, LeafBlock)
    leaf.src_lines.append(src)
    leaf.content_lines.append(content)
    self.dbg(src, '-', self.stack)

  def close_leaf_block(self) -> None:
    if self.stack and isinstance(self.top, LeafBlock):
      self.pop()
      assert not self.stack or isinstance(self.top, (Section, ListItem))

  def emit_head(self) -> Iterator[str]:
    yield from self.head_text

  def emit_body(self, depth: int, target_section: str|None=None) -> Iterator[str]:
    for block in self.blocks:
      if target_section is not None:
        if not isinstance(block, Section): continue
        title = text_for_spans(block.title)
        # TODO: this only works for top level section ids; fixing it requires a recursive approach.
        if title != target_section and block.sid != target_section: continue
        self.found_target_section = True
      yield from block.html(ctx=self, depth=depth)
    if self.open_div: # See LangBlock.html 'div' case.
      yield '</div>'

  def add_dependency(self, dependency:str) -> None:
    assert dependency
    if '#' in dependency: raise ValueError(dependency)
    if '?' in dependency: raise ValueError(dependency)
    self.dependencies.append(dependency)

  def add_css(self, class_, style) -> None:
    l = self.css[class_] # get list from default dict.
    if style not in l: l.append(style) # deduplicate but preserve order.

  def render_css(self) -> Iterator[str]:
    for selector, styles in self.css.items():
      style_string = ''.join(f'{style};' for style in styles)
      yield f'{selector}{{{style_string}}}'

  def msg(self, src: SrcLine, label: str, items: tuple[Any, ...], col: int|None) -> None:
    line, txt = src
    if col is None: col = 0
    errSL(f'{self.src_path}:{line+1}:{col+1}: {label}:', *items)
    errSN(txt)

  def warn(self, src: SrcLine, *items: Any, col:int|None=None) -> None:
    self.msg(src, 'warning', items, col)

  def error(self, src: SrcLine, *items: Any, col:int|None=None) -> NoReturn:
    self.msg(src, 'error', items, col)
    exit(1)

  def dbg(self, src: SrcLine, *items: Any, col:int|None=None) -> None:
    if self.emit_dbg: self.msg(src, 'debug', items, col)


version_re = re.compile(r'writeup v(\d+)\n')
# version pattern is applied to the first line of documents;
# programs processing input strings may or may not check for a version as appropriate.

license_re = re.compile(r'(©|Copyright|Dedicated to the public domain).*')
# license pattern is is only applied to the first line (following the version line, if any).

# line states.
s_start, s_license, s_section, s_quote, s_code, s_lang, s_text, s_blank = range(8)

state_letters = '^©SQCLTB' # for debug output only.

line_re = re.compile(r'''(?x)
(?P<section_indents> \s* ) (?P<section_hashes>\#+) (?P<section_spaces> \s* ) (?P<section_title> .* )
|
(?P<indents> \s* )
( (?P<list_star> \* ) (?P<list_spaces> \s* ) )?
(?:
    >  \s? (?P<quote> .* )
  | \| \s? (?P<code> .* )
  | %  \s? (?P<lang> .* )
  | (?P<blank> \s*)
  | (?P<text> .* )
)
''')

line_groups_to_states = {
  'section_title' : s_section,
  'quote' : s_quote,
  'code': s_code,
  'lang': s_lang,
  'text': s_text,
  'blank': s_blank,
}


def parse(ctx: Ctx, src_lines: Iterable[SrcLine]) -> None:
  iter_src_lines = iter(src_lines)

  # Handle version line.
  if ctx.is_versioned:
    try: src = next(iter_src_lines)
    except StopIteration: src = (0, '')
    line_idx, version_line = src
    m = version_re.fullmatch(version_line)
    if m is None:
      ctx.error(src, f'first line must specify writeup version matching pattern: `{version_re.pattern}`\n'
        '  (The only currently supported version number is 0.)')
    version = int(m.group(1))
    if version != 0:
      ctx.error(src, f'unsupported version number: {version}\n'
        '  (The only currently supported version number is 0.)')
    ctx.line_offset += 1

  # Iterate over lines.
  prev_state = s_start
  for src in iter_src_lines:
    line_idx, raw_line = src
    line = raw_line.rstrip('\n')
    if ctx.warn_missing_final_newline and not raw_line.endswith('\n'):
      ctx.warn(src, 'missing final newline.')

    # any license notice at top gets moved to a footer at the bottom of the html.
    if prev_state == s_start and license_re.fullmatch(line):
      ctx.license_lines.append(line.strip())
      prev_state = s_license
      continue
    if prev_state == s_license: # consume remaining license lines.
      if line.strip(): # not blank.
        ctx.license_lines.append(line)
        continue # remain in s_license.

    # normal line.
    m = line_re.fullmatch(line)
    if m is None: ctx.error(src, 'invalid line (unknown reason; please report)')
    #errSL('L', repr(line))
    #errSL('M', m)
    g = m.lastgroup
    assert g is not None
    state = line_groups_to_states[g]
    writeup_line(ctx=ctx, src=src, state=state, m=m)
    prev_state = state

  # Finish.
  while ctx.stack:
    ctx.pop()


def writeup_line(ctx: Ctx, src: SrcLine, state: int, m: Match) -> None:
  'Process a source line.'

  ctx.dbg(src, state_letters[state])

  if state == s_section:
    ctx.pop_to_list(0)
    if m['section_indents']: ctx.error(src, 'section header cannot be indented.')
    check_whitespace(ctx, src, len_exp=1, m=m, key='section_spaces', msg_suffix=' following `#`')
    section_depth = len(m['section_hashes'])
    index_path: tuple[int, ...]
    if not ctx.stack: # first/intro case only.
      index_path = (0,) # intro section is 0-indexed (`s0`); everything else is 1-indexed.
    elif section_depth > ctx.depth + 1:
        ctx.error(src, f'missing parent section of depth {ctx.depth + 1}')
    else: # normal case.
      prev_index = ctx.pop_to_section_depth(section_depth - 1)
      if ctx.stack:
        index_path = cast(Section, ctx.top).index_path + (prev_index+1,)
      else:
        index_path = (prev_index+1,)
    title = parse_spans(ctx, src=src, text=m['section_title'])
    section = Section(section_depth=section_depth, quote_depth=ctx.quote_depth, index_path=index_path, title=title)
    ctx.push(section)
    return

  check_whitespace(ctx, src, len_exp=None, m=m, key='indents', msg_suffix=' in indentation')
  indents = m['indents']
  l = len(indents)
  if l % 2: ctx.error(src, f'odd indentation length: {l}.', col=l)
  list_level = l // 2
  if ctx.list_level < list_level:
    errSL(ctx.stack)
    ctx.error(src, f'indent implies missing parent list at indent depth {ctx.list_level+1}.')

  if m['list_star']:
    check_whitespace(ctx, src, len_exp=1, m=m, key='list_spaces', msg_suffix=' following `*`')
    goal_level = list_level + 1
    ctx.pop_to_list(goal_level)
    if ctx.list_level < goal_level:
      assert ctx.list_level + 1 == goal_level
      ulist = UList(list_level=goal_level)
      ctx.push(ulist)
    else:
      ulist = cast(UList, ctx.top)
      assert isinstance(ulist, UList)
    item = ListItem(list_level=goal_level)
    ulist.items.append(item)
    ctx.stack.append(item)
    list_level = goal_level

  if state == s_code:
    ctx.append_to_leaf_block(src, list_level, Code, content=m['code'])

  elif state == s_quote:
    ctx.append_to_leaf_block(src, list_level, Quote, content=m['quote'])

  elif state == s_lang:
    ctx.append_to_leaf_block(src, list_level, LangBlock, content=m['lang'])

  elif state == s_text:
    ctx.append_to_leaf_block(src, list_level, Text, content=m['text'])

  elif state == s_blank:
    if len(indents): ctx.warn(src, 'blank line is not empty.')
    ctx.close_leaf_block()

  else: ctx.error(src, f'bad state: {state}')


def check_whitespace(ctx: Ctx, src: SrcLine, len_exp: int|None, m: Match, key: str, msg_suffix='') -> bool:
  col = m.start(key)
  string = m[key]
  i = 0
  for i, c in enumerate(string):
    if c != ' ':
      ctx.warn(src, f'invalid whitespace character{msg_suffix}: {c!r}', col=col+i+1)
      return False
  if len_exp is not None and len(string) != len_exp:
    s = '' if len_exp == 1 else 's'
    ctx.warn(src, f'expected exactly {len_exp} space{s}{msg_suffix}; found: {len(string)}', col=col+i+1)
    return False
  return True


def parse_spans(ctx: Ctx, src: SrcLine, text: str) -> Spans:
  spans: list[Span] = []
  prev_idx = 0
  def flush(curr_idx: int) -> None:
    if prev_idx < curr_idx:
      spans.append(Span(text=text[prev_idx:curr_idx]))
  for m in span_re.finditer(text):
    start_idx = m.start()
    flush(start_idx)
    prev_idx = m.end()
    i = m.lastindex
    assert i is not None
    span_fn = span_fns[i-1] # Groups are 1-indexed, but function array is 0-indexed.
    group_text = m.group(i)
    spans.append(span_fn(ctx, src, group_text))
  flush(len(text))
  return tuple(spans)


def parse_tag_attrs_body(ctx:Ctx, src:SrcLine, text:str) -> tuple[str, dict[str,str], list[str]]:
  tag, colon, post_tag_text = text.lstrip().partition(':')
  if colon is None: ctx.error(src, f'missing colon after tag: {text!r}')

  attrs_list = []
  body_words = []
  in_body = False
  # TODO: better escaping syntax for equals.
  for i, word in enumerate(post_tag_text.split(' ')):
    if word == '': continue
    if in_body or (i == 0 and tag in span_link_tags):
      # hack: for URLs; do not partition first word because URL might contain '='.
      body_words.append(word); continue
    if word == ';': in_body = True; continue
    key, eq, val = word.partition('=')
    if not eq:
      body_words.append(word)
      continue
    if val.endswith(';'):
      in_body = True
      val = val[:-1]
    val = val.strip()
    if not sym_re.fullmatch(key): ctx.error(src, f'attribute name is invalid: {word!r}')
    if not val: ctx.error(src, f'attribute value is empty; word: {word!r}')
    if val[0] in ('"', "'") and (len(val) < 2 or val[0] != val[-1]):
      ctx.error(src, 'span attribute value has mismatched quotes (possibly due to writeup doing naive splitting on whitespace);' \
        f'word: {word!r}; val: {val!r}')
    attrs_list.append((key, val))
  return tag.strip(), dict(attrs_list), body_words


def span_angle_conv(ctx: Ctx, src: SrcLine, text: str) -> Span:
  'convert angle bracket span to html.'
  tag, attrs, body_words = parse_tag_attrs_body(ctx, src, text)
  if not body_words: ctx.error(src, 'span has no body (missing colon after the tag?)')
  body_text = ' '.join(body_words)
  if tag == 'b':
    return BoldSpan(text=body_text, attrs=attrs)
  if tag == 'embed':
    return embed(ctx, src, text=body_text, attrs=attrs)
  if tag == 'img':
    return ImgSpan(text=body_text, attrs=attrs)
  if tag in span_link_tags:
    span = LinkSpan(text=body_text, attrs=attrs, tag=tag, words=body_words, ctx=ctx, src=src)
    if tag == 'link':
      path = url_path(span.link)
      if path: # If the url is just an anchor, then there is no dependency.
        if not path_ext(path): # A link to a directory needs `index.html`.
          path = path_join(path, 'index.html')
        ctx.add_dependency(path)
    return span
  if tag in phrasing_tags:
    return GenericSpan(text=body_text, attrs=attrs, tag=tag)
  ctx.error(src, f'span has invalid tag: {tag!r}')
  raise Exception # TODO: remove. This is a hack around mypy type checker.


span_link_tags = { 'http', 'https', 'link', 'mailto' }


def span_backtick_conv(ctx: Ctx, src: SrcLine, text: str) -> Span:
  return CodeSpan(text=text)


# span regexes.
# general pattern for quoting with escapes is Q([^EQ]|EQ|EE)*Q.
# it is crucial that the escape character E is excluded in the '[^EQ]' clause,
# or else when matching against 'QEQQ', the pattern greedily matches 'QEQ'.
# to allow a trailing escape character, the 'EE' clause is also required.

# backtick code span.
span_backtick_pat = r'`((?:[^\\`]|\\`|\\\\)*)`' # Backtick code spans.
span_backtick_esc_re = re.compile(r'\\`|\\\\') # escapes code strings.

# generic angle bracket span.
span_angle_pat = r'<((?:[^\\>]|\\>|\\\\)*)>'
span_angle_esc_re = re.compile(r'\\>|\\\\') # escapes span strings.

# span patterns and associated handlers.
span_pairs = (
  (span_backtick_pat, span_backtick_conv),
  (span_angle_pat, span_angle_conv),
)

span_fns = tuple(f for _, f in span_pairs)

span_re = re.compile('|'.join(p for p, _ in span_pairs))


# Embed.


def embed(ctx: Ctx, src: SrcLine, text: str, attrs: dict[str, str]) -> Span:
  'convert an `embed` span into html.'
  words = text.split()
  dep = words[0]
  ctx.add_dependency(dep)
  if dep.startswith('/'):
    assert not ctx.project_dir.endswith('/')
    path = ctx.project_dir + dep # Using path_join would omit everything before the absolute path.
  else:
    path = path_join(ctx.src_dir, dep)
  args = words[1:]
  if ctx.should_embed:
    try: f = open(path)
    except FileNotFoundError:
      ctx.error(src, f'embedded file not found: {path!r}')
    ext = attrs.get('ext')
    if not ext:
      ext = path_ext(path)
    try: embed_fn = embed_dispatch.get(ext, embed_code)
    except KeyError:
      ctx.error(src, f'embedded file has unknown extension type: {path!r}')
    contents = tuple(embed_fn(ctx, src, f, args, attrs))
  else:
    contents = ()
  return EmbedSpan(text=text, attrs=attrs, path=path, contents=contents)


def embed_css(ctx: Ctx, src:SrcLine, f: TextIO, args:list[str], attrs:dict[str,str]) -> list[str]:
  css = f.read()
  return [f'<style type="text/css">{html_esc(css)}</style>']


def embed_csv(ctx: Ctx, src:SrcLine, f: TextIO, args:list[str], attrs:dict[str,str]) -> list[str]:
  from csv import reader
  csv_reader = reader(f)
  it = iter(csv_reader)
  lines = ['<table>']

  def append(*els:str) -> None: lines.append(''.join(els))

  try: header = next(it)
  except StopIteration: pass
  else:
    append('<thead>', '<tr>')
    append('  ', *[f'<th>{html_esc(col)}</th>' for col in header])
    append('</tr>', '</thead>', '<tbody>')
    for row in it:
      append('  <tr>', *[f'<td>{html_esc(cell)}</td>' for cell in row], '</tr>')
    append('</tbody>')
  append('</table>')
  return lines


def embed_code(ctx: Ctx, src:SrcLine, f: TextIO, args:list[str], attrs:dict[str,str]) -> Iterator[str]:
  lines = list(f)
  first = lines[0] if lines else ''
  lexer = pygments.lexers.guess_lexer_for_filename(f.name, first)
  yield '<div class="code-block">'
  for line in lines:
    content = ''.join(render_token(ctx, *t) for t in pygments.lex(line, lexer)) # type: ignore[no-untyped-call]
    yield f'<code class="line">{content}</code>'
  yield '</div>'

def render_token(ctx: Ctx, kind: pygments.token._TokenType, text: str) -> str:
  class_, color = token_class_colors.get(kind, ('t', None))
  if color is None: return text
  ctx.add_css(f'code.line span.{class_}', style=f'color: {color}')
  return f'<span class="{class_}">{html_esc(text)}</span>'


def embed_direct(ctx: Ctx, src:SrcLine, f: TextIO, args:list[str], attrs:dict[str,str]) -> list[str]:
  return list(filter(None, (xml_processing_instruction_re.sub('', line.rstrip()) for line in f)))

xml_processing_instruction_re = re.compile(r'<\?[^>]*>')


def embed_html(ctx: Ctx, src:SrcLine, f: TextIO, args:list[str], attrs:dict[str,str]) -> list[str]:
  lines = list(f)
  head = ''
  for head in lines:
    if head.strip(): break
  if html_doc_re.match(head): # looks like a complete html doc.
    # TODO: we shouldn't just leave a cryptic error message here.
    # Use an iframe? Or does object tag work for this purpose?
    path = rel_path(f.name, start=ctx.src_dir)
    msg = f'<error: missing object: {path!r}>'
    return [f'<object data="{html_esc_attr(path)}" type="text/html">{html_esc(msg)}</object>']
  else:
    return list(line.rstrip() for line in lines)

html_doc_re = re.compile(r'''(?xi)
\s* < \s* (!doctype \s+)? html
''')


def embed_img(ctx: Ctx, src:SrcLine, f: TextIO, args:list[str], attrs:dict[str,str]) -> list[str]:
  return [f'<img src={html_esc(f.name)}>']


def embed_json(ctx:Ctx, src:SrcLine, f:TextIO, args:list[str], attrs:dict[str,str]) -> list[str]:
  data = load_json(f)
  for i, arg in enumerate(args):
    acc = '.'.join(args[:i+1])
    if isinstance(data, dict):
      try: data = data[arg]
      except KeyError: ctx.error(src, f'{f.name}:{acc}: no such key.')
    elif isinstance(data, list):
      try: index = int(arg)
      except ValueError: ctx.error(src, f'{f.name}:{acc}: data is a list; key is not an index.')
      try: data = data[index]
      except IndexError: ctx.error(src, f'{f.name}:{acc}: data has {len(data)} items; index is out of bounds.')
    else:
      ctx.error(src, f'{f.name}:{acc}: data is not a collection.')
  return [str(data)]


def embed_wu(ctx: Ctx, src:SrcLine, f: TextIO, args:list[str], attrs:dict[str,str]) -> list[str]:
  embed_ctx = Ctx(
    src_path=f.name,
    project_dir=ctx.project_dir,
    quote_depth=ctx.quote_depth,
    line_offset=0,
    is_versioned=True,
    should_embed=ctx.should_embed)
  parse(embed_ctx, src_lines=enumerate(f))
  return list(embed_ctx.emit_body(depth=0))


_EmbedFn = Callable[[Ctx, SrcLine, TextIO, list[str], dict[str,str]], Iterable[str]]

embed_dispatch: dict[str, _EmbedFn] = {
  '.css'  : embed_css,
  '.csv'  : embed_csv,
  '.json' : embed_json,
  '.wu'   : embed_wu,
}

def _add_embed(fn:_EmbedFn, *exts: str) -> None:
  embed_dispatch.update((ext, fn) for ext in exts)

_add_embed(embed_direct, '.svg')
_add_embed(embed_html, '.htm', '.html')
_add_embed(embed_img, '.gif', '.jpeg', '.jpg', '.png')


sym_re = re.compile(r'[-_\w]+')


def attrs_bool(attrs: dict[str, str], key: str) -> bool:
  return attrs.get(key) in {'true', 'yes'}


# HTML output.

def fmt_attrs(attrs:dict[str,str]) -> str:
  return ''.join(f' {html_esc_attr(attr_subs.get(k, k))}="{html_esc_attr(v)}"' for k, v in attrs.items())

attr_subs = {
  'class_' : 'class'
}


def html_esc(text: str) -> str:
  # TODO: check for strange characters that html will ignore.
  return html_escape(text, quote=False)


def html_esc_attr(text: str) -> str:
  return html_escape(text, quote=True)


def html_for_spans(spans: Spans, depth: int) -> str:
  return ''.join(span.html(depth=depth) for span in spans).strip()


def text_for_spans(spans: Spans) -> str:
  return ''.join(span.text for span in spans).strip()


def indent(depth: int, *items: str) -> str:
  return '  ' * depth + ''.join(items)


# CSS.

minify_css_re = re.compile(r'''(?x)
  ([\{\}])    # tokenize braces, so that we can distinguish selectors from styles, and emit lines on close brace.
| \n          # discard newlines.
| \s+         # discard spaces.
| /\*.*?\*/   # discard comments.
| //[^\n]*\n? # discard comments.
''')
# We could do more agressive minification but this is good enough for now.

def minify_css(css_blocks: Iterable[str]) -> Iterator[str]:
  'Given blocks of CSS code, yield minified lines without final `\\n`.'
  for block in css_blocks:
    min_chunks = []
    for chunk in minify_css_re.split(block):
      if chunk: # discard empty chunks and splits that are None (not captured).
        min_chunks.append(chunk)
        if chunk == '}' and min_chunks:
          yield ' '.join(min_chunks)
          del min_chunks[:]
    if min_chunks: # shouldn't happen, assuming final token is closing brace.
      yield ' '.join(min_chunks)


# Javascript.

minify_js_re = re.compile(r'''(?x)
  (\s)\s+    # Keep only the first space.
| /\*.*?\*/ # discard comments.
| //[^\n]*  # discard comments.
''')

def minify_js(js:str) -> str:
  lines = (minify_js_line(l) for l in js.split('\n'))
  return '\n'.join(l for l in lines if l)

def minify_js_line(line:str) -> str:
  line = line.strip()
  chunks = minify_js_re.split(line)
  return ''.join(c for c in chunks if c).strip()


# Default assets.

_src_dir = path_dir(__file__)

default_css = open(path_join(_src_dir, 'writeup.css')).read()
default_js = open(path_join(_src_dir, 'writeup.js')).read()


# Syntax highlighting.

black   = '#000000'
blue    = '#0000E0'
gray    = '#606060'
magenta = '#800080'
orange  = '#60400'
red     = '#800000'
yellow  = '#806000'
green   = '#008000'

token_class_colors = {
  Token.Text                        : ('t',   None),
  Token.Escape                      : ('esc', yellow),
  Token.Error                       : ('err', red),
  Token.Other                       : ('x',   black),
  Token.Keyword                     : ('k',   magenta),
  Token.Keyword.Constant            : ('kc',  black),
  Token.Keyword.Declaration         : ('kd',  black),
  Token.Keyword.Namespace           : ('kn',  magenta),
  Token.Keyword.Pseudo              : ('kp',  black),
  Token.Keyword.Reserved            : ('kr',  black),
  Token.Keyword.Type                : ('kt',  black),
  Token.Name                        : ('n',   black),
  Token.Name.Attribute              : ('na',  black),
  Token.Name.Builtin                : ('nb',  black),
  Token.Name.Builtin.Pseudo         : ('bp',  black),
  Token.Name.Class                  : ('nc',  black),
  Token.Name.Constant               : ('no',  black),
  Token.Name.Decorator              : ('nd',  black),
  Token.Name.Entity                 : ('ni',  black),
  Token.Name.Exception              : ('ne',  black),
  Token.Name.Function               : ('nf',  black),
  Token.Name.Function.Magic         : ('fm',  black),
  Token.Name.Property               : ('py',  black),
  Token.Name.Label                  : ('nl',  black),
  Token.Name.Namespace              : ('nn',  black),
  Token.Name.Other                  : ('nx',  black),
  Token.Name.Tag                    : ('nt',  black),
  Token.Name.Variable               : ('nv',  black),
  Token.Name.Variable.Class         : ('vc',  black),
  Token.Name.Variable.Global        : ('vg',  black),
  Token.Name.Variable.Instance      : ('vi',  black),
  Token.Name.Variable.Magic         : ('vm',  black),
  Token.Literal                     : ('l',   black),
  Token.Literal.Date                : ('ld',  green),
  Token.Literal.String              : ('s',   green),
  Token.Literal.String.Affix        : ('sa',  green),
  Token.Literal.String.Backtick     : ('sb',  green),
  Token.Literal.String.Char         : ('sc',  green),
  Token.Literal.String.Delimiter    : ('dl',  green),
  Token.Literal.String.Doc          : ('sd',  green),
  Token.Literal.String.Double       : ('s2',  green),
  Token.Literal.String.Escape       : ('se',  green),
  Token.Literal.String.Heredoc      : ('sh',  green),
  Token.Literal.String.Interpol     : ('si',  green),
  Token.Literal.String.Other        : ('sx',  green),
  Token.Literal.String.Regex        : ('sr',  green),
  Token.Literal.String.Single       : ('s1',  green),
  Token.Literal.String.Symbol       : ('ss',  green),
  Token.Literal.Number              : ('m',   blue),
  Token.Literal.Number.Bin          : ('mb',  blue),
  Token.Literal.Number.Float        : ('mf',  blue),
  Token.Literal.Number.Hex          : ('mh',  blue),
  Token.Literal.Number.Integer      : ('mi',  blue),
  Token.Literal.Number.Integer.Long : ('il',  blue),
  Token.Literal.Number.Oct          : ('mo',  blue),
  Token.Operator                    : ('o',   black),
  Token.Operator.Word               : ('ow',  black),
  Token.Punctuation                 : ('p',   black),
  Token.Comment                     : ('c',   gray),
  Token.Comment.Hashbang            : ('ch',  gray),
  Token.Comment.Multiline           : ('cm',  gray),
  Token.Comment.Preproc             : ('cp',  gray),
  Token.Comment.PreprocFile         : ('cpf', gray),
  Token.Comment.Single              : ('c1',  gray),
  Token.Comment.Special             : ('cs',  gray),
  Token.Generic                     : ('g',   black),
  Token.Generic.Deleted             : ('gd',  black),
  Token.Generic.Emph                : ('ge',  black),
  Token.Generic.Error               : ('gr',  black),
  Token.Generic.Heading             : ('gh',  black),
  Token.Generic.Inserted            : ('gi',  black),
  Token.Generic.Output              : ('go',  black),
  Token.Generic.Prompt              : ('gp',  black),
  Token.Generic.Strong              : ('gs',  black),
  Token.Generic.Subheading          : ('gu',  black),
  Token.Generic.Traceback           : ('gt',  orange),
}
