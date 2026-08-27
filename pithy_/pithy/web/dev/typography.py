# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page showing the baseline styling of ordinary document elements.'

from ...html import (A, Blockquote, Code, Dd, Details, Dl, Dt, Em, H1, H2, H3, H4, H5, H6, Hr, Li, Main, Ol, P, Pre, Section,
  Small, Strong, Summary, Ul)
from ..endpoint import Endpoint, NoFields
from ..request import Request
from ..response import HtmlResponse
from .pages import dev_page


lorem = ('Endpoints declare an inner Fields class; the router fills a fresh instance from the path, query and body'
  ' parameters, rejecting requests that carry the wrong ones. The intent is that a handler receives values it can'
  ' use directly, rather than a bag of strings it must validate itself.')


class DevTypography(Endpoint):
  'Baseline styling of headings, text, lists and code.'

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmlResponse:
    main = Main(
      H1('Typography'),
      P('Every element on this page is unstyled by the application: this is what ', Code('pithy.css'),
        ' gives a document on its own.'),

      Section(
        _=[
          H1('First level'),
          P('Paragraph text between first-level headings.'),
          H1('First level'),
          H2('Second level'),
          P('Paragraph text between second-level headings.'),
          H2('Second level'),
          H3('Third level'),
          P('Paragraph text between third-level headings.'),
          H3('Third level'),
          H4('Fourth level'),
          P('Paragraph text between fourth-level headings.'),
          H4('Fourth level'),
          H5('Fifth level'),
          P('Paragraph text between fifth-level headings.'),
          H5('Fifth level'),
          H6('Sixth level'),
          P('Paragraph text between sixth-level headings.'),
          H6('Sixth level'),
        ]),

      Section(
        _=[
          H2('Text'),
          P(lorem),
          P('Inline elements: ', Strong('strong'), ', ', Em('emphasis'), ', ', Code('code'), ', ',
            A(href='/', _='a link'), ', and ', Small('small text'), '.'),
          Blockquote('A block quotation is indented and marked with a rule, so that it reads as an aside'
            ' without needing a class.'),
        ]),

      Section(
        _=[
          H2('Lists'),
          Ul(Li('Unordered items sit on the default marker.'), Li('Nested lists indent one step:',
            Ul(Li('First nested item.'), Li('Second nested item.')))),
          Ol(Li('Ordered items are numbered.'), Li('The second item.')),
          Dl(Dt('Definition list'), Dd('The term is bold; the description is indented beneath it.'),
            Dt('Second term'), Dd('A second description.')),
        ]),

      Section(
        _=[
          H2('Code'),
          P('A ', Code('code'), ' span is monospaced.'),
          Pre(Code("class Hello(Endpoint):\n"
            "  'Say hello.'\n\n"
            "  class Fields:\n"
            "    name: str\n\n"
            "  def handle_endpoint(self, request, fields):\n"
            "    return HtmlResponse(body=P(f'Hello, {fields.name}.'))\n")),
        ]),

      Section(
        _=[
          H2('Details'),
          Details(Summary('A closed disclosure'), P('The disclosure marker is drawn by the stylesheet,'
            ' because Chrome and Safari style the native one differently.')),
          Details(open='', _=[Summary('An open disclosure'), P('This one starts open.')]),
          Hr(),
          P(cl='muted', _='An addendum consisting of a horizontal rule and muted text.'),
        ]),
    )
    return dev_page(title='Typography', main=main,
      breadcrumbs=[('/', 'Home'), ('/typography', 'Typography')])
