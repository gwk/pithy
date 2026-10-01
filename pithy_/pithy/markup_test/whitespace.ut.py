# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from textwrap import dedent

from pithy.html import Div, P, Span
from pithy.markup import Mu, TagMu
from utest import utest


# TagMu has a per-instance tag slot; Mu uses a class-level tag.
# TagMu has no inline_tags, void_tags, or ws_sensitive_tags set (inherits empty frozensets from Mu).

# Empty node is self-closing.
utest(dedent('''\
  <div/>
  '''), Mu.render_str, TagMu(tag='div'))

# Single text child: no extra newlines (child_newlines requires >1 children).
utest(dedent('''\
  <p>hello</p>
  '''), Mu.render_str, TagMu(tag='p', _='hello'))

# Single text child, newline=False.
utest(dedent('''\
  <p>hello</p>'''), Mu.render_str, TagMu(tag='p', _='hello'), False)

# Two text children: no block-level children, so this is an inline context and no newlines are manufactured.
utest(dedent('''\
  <div>ab</div>
  '''), Mu.render_str, TagMu(tag='div', _=['a', 'b']))

# HTML elements: Div is a block; P is a block; Span is inline (in phrasing_tags).

# Div with single P child: only 1 child so child_newlines=False.
utest(dedent('''\
  <div><p>text</p></div>
  '''), Mu.render_str, Div(_=[P('text')]))

# Div with two P children: child_newlines=True, newline between block elements.
utest(dedent('''\
  <div>
  <p>one</p>
  <p>two</p>
  </div>
  '''), Mu.render_str, Div(_=[P('one'), P('two')]))

# Div with two Span children: all children are inline, so this is an inline context and renders on one line.
utest(dedent('''\
  <div><span>a</span><span>b</span></div>
  '''), Mu.render_str, Div(_=[Span('a'), Span('b')]))

# Mixed: text then block child.
utest(dedent('''\
  <div>
  some text
  <p>para</p>
  </div>
  '''), Mu.render_str, Div(_=['some text', P('para')]))

# Mixed: block then text child.
utest(dedent('''\
  <div>
  <p>para</p>
  some text
  </div>
  '''), Mu.render_str, Div(_=[P('para'), 'some text']))

# Span (inline parent) with two children: child_newlines=False because span is in inline_tags.
utest(dedent('''\
  <span>ab</span>
  '''), Mu.render_str, Span(_=['a', 'b']))

# Block parent (P) whose children are all phrasing content: no block children, so it renders inline.
utest(dedent('''\
  <p>The <span>pre</span> module.</p>
  '''), Mu.render_str, P(_=['The ', Span('pre'), ' module.']))

# Nested blocks: outer Div with single inner Div → no extra newlines (1 child).
utest(dedent('''\
  <div><div>inner</div></div>
  '''), Mu.render_str, Div(_=[Div(_='inner')]))

# Nested blocks: outer Div with two inner Divs.
utest(dedent('''\
  <div>
  <div>a</div>
  <div>b</div>
  </div>
  '''), Mu.render_str, Div(_=[Div(_='a'), Div(_='b')]))

# render() is an iterator; joining it should match render_str().
node = Div(_=[P('x'), P('y')])
utest(Mu.render_str(node), ''.join, node.render())

# render_str(newline=False) omits the trailing newline.
utest(dedent('''\
  <div>
  <p>x</p>
  <p>y</p>
  </div>'''), Mu.render_str, Div(_=[P('x'), P('y')]), False)
