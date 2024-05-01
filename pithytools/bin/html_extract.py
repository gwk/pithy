# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from html.parser import HTMLParser
from sys import stdin


def main() -> None:
  arg_parser = ArgumentParser('Extract a portion of an HTML document.')
  arg_parser.add_argument('-id',help='The `id` of the DOM element to extract.')
  arg_parser.add_argument('path', nargs='?', help='path to the HTML document (defaults to stdin).')
  args = arg_parser.parse_args()
  path = args.path

  try: file = open(path) if path is not None else stdin
  except FileNotFoundError as e: exit(f'file not found: {e.filename}')
  parser = HtmlExtractParser(path=file.name, id=args.id, lines=list(file))
  parser.extract()


Pos = tuple[int, int]


class HtmlExtractParser(HTMLParser):

  def __init__(self, path: str, id=str, lines=list[str]):
    super().__init__(convert_charrefs=True)
    self.path = path
    self.id = id
    self.lines = lines
    self.stack: list[tuple[Pos, str]] = []
    self.extract_start_pos: Pos|None = None

  def extract(self) -> None:
    for line in self.lines:
      self.feed(line)
    self.close()
    if self.extract_start_pos: exit('specified element was found but unterminated.')
    else: exit('specified element was not found.')

  def handle_starttag(self, tag: str, attrs: list[tuple[str,str|None]]):
    self.stack.append((self.pos, tag))
    d = dict(attrs)
    if d.get('id') == self.id:
      self.extract_start_pos = self.pos

  def handle_endtag(self, tag: str) -> None:
    if self.stack and self.stack[-1][1] == tag:
      p, t = self.stack.pop()
      if p == self.extract_start_pos:
        self.print_range(p, self.pos)
        exit(0)
      return
    self.msg(f'unmatched closing tag: {tag}')
    self.msg(f'in: {" ".join(t for _, t in self.stack)}')
    for i in reversed(range(len(self.stack))):
      pi, ti = self.stack[i]
      if ti == tag: # found match.
        for p, t in self.stack[i+1:]:
          self.msg(f'note: ignoring open `{t}` here', pos=p)
        self.msg('note: could match here', pos=pi)
        return

  def print_range(self, start_pos: Pos, end_pos: Pos) -> None:
    sl, sc = start_pos
    el, ec = end_pos
    if sl == el:
      l = self.lines[sl]
      print(l[sc:ec], end='')
    else:
      print(self.lines[sl][sc:], end='')
      for line in self.lines[sl+1:el]: print(line, end='')
      print(self.lines[el][:ec], end='')
    # Need to print end tag, which comes after `ec`.
    last = self.lines[el]
    close_pos = last.index('>', ec)
    print(last[ec:close_pos+1])

  @property
  def pos(self) -> Pos:
    line1, col0 = self.getpos()
    return (line1-1, col0)

  def msg(self, msg: str, pos:Pos|None=None) -> None:
    if pos is None: pos = self.pos
    print(f'{self.path}:{pos[0]+1}:{pos[1]+1}: {msg}')


if __name__ == '__main__': main()
