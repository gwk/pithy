# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Developer demo page for `pithy.web.dbview.DbView`, browsing an in-memory library catalog of authors and books.

Each request builds a fresh in-memory database, so the page needs no setup and no request can affect another.
DbView interpolates the `where` and `order_by` params into SQL; here the connection is query-only and private to the request.
'''

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from starlette.exceptions import HTTPException
from starlette.requests import Request as StarletteRequest

from ...html import A, Code, H1, Li, Main, P, Ul
from ...sqlite import Conn, Row
from ...sqlite.schema import Column, Schema, Table
from ..dbview import DbView
from ..dbview.vis import dt_split_wrap, Vis
from ..errors import BadRequestError
from ..handler import RoutableHandler
from ..request import Request
from ..response import Response
from .pages import dev_page


_context_keywords_ = ['database browser', 'demo', 'foreign keys', 'in-memory database', 'sqlite']


authors_table = Table('authors', desc='Writers in the demo catalog.', is_strict=True, columns=(
  Column('id', int, is_primary=True, is_unique=True),
  Column('name', str),
  Column('country', str),
  Column('born', int),
  Column('died', int, is_opt=True),
  Column('website', str),
))

books_table = Table('books', desc='Titles in the demo catalog.', is_strict=True, columns=(
  Column('id', int, is_primary=True, is_unique=True),
  Column('title', str),
  Column('author_id', int, is_opt=True, desc='References authors.id; NULL for anonymous works.'),
  Column('year', int, desc='Year of first publication.'),
  Column('pages', int),
  Column('price_cents', int),
  Column('rating', float, is_opt=True),
  Column('isbn', str),
  Column('added_at', str, desc='Catalog timestamp, formatted as "YYYY-MM-DD HH:MM:SS".'),
))

library_schema = Schema(name='', desc='Demo library catalog.', structures=[authors_table, books_table])


def fmt_price(cents:int) -> str:
  'Render an integer number of cents as dollars.'
  return f'${cents / 100:,.2f}'


def fmt_died(row:Row) -> str:
  'Render the year of death with the age at death, when the `born` column is also selected.'
  born = row.get('born')
  return f'{row.died} (age {row.died - born})' if born is not None else str(row.died)


library_dbview = DbView(
  schemas=[library_schema],
  vis={
    '': {
      'authors': {
        'id': Vis(cl='num'),
        'died': Vis(render=fmt_died, renders_row=True),
        'website': False, # Hidden by default; the bool is shorthand for `Vis(show=False)`.
      },
      'books': {
        'id': Vis(cl='num'),
        'author_id': Vis(key='authors.id', col='name'),
        'pages': Vis(cl='num'),
        'price_cents': Vis(cl='num', render=fmt_price),
        'rating': Vis(cl='num'),
        'isbn': Vis(show=False),
        'added_at': Vis(render=dt_split_wrap),
      },
    },
  },
  order_by={'': {'books': 'year, title'}},
)


class DevDbView(RoutableHandler):
  '''
  The DbView demo page.

  DbView reads arbitrary query parameters (one `c-{column}` checkbox per column),
  so this is a plain RoutableHandler rather than an Endpoint, which rejects undeclared params.
  '''

  _methods = frozenset({'GET', 'HEAD'})


  def __init__(self, request:Request, path_params:Mapping[str,object]) -> None: pass


  def handle_request(self, request:Request) -> Response:
    with open_library_db().closing() as conn:
      try: dbview_div = library_dbview.render(starlette_request(request), conn)
      except HTTPException as e: raise BadRequestError(e.detail) from e

    main = Main(
      H1('DbView'),
      P(Code('pithy.web.dbview.DbView'), ' browses an in-memory SQLite library catalog of authors and books.'
        ' Each book has an ', Code('author_id'), ' column that refers to ', Code('authors.id'), '.'),
      Ul(
        Li(A(href='/dbview?table=books&limit=20', _='Books, 20 per page'),
          ': author names come from a foreign key subquery and link to the author row.'),
        Li(A(href='/dbview?table=authors&limit=10', _='Authors, 10 per page'),
          ': the default order is by descending primary key.'),
        Li(A(href='/dbview?table=books&where=author_id+IS+NULL+OR+author_id+NOT+IN+(SELECT+id+FROM+authors)',
          _='Books without a known author'), ': NULL and dangling references.'),
      ),
      dbview_div,
    )
    return dev_page(title='DbView', main=main, css_paths=['/static/pithy/dbview.css'],
      breadcrumbs=[('/', 'Home'), ('/dbview', 'DbView')])


def starlette_request(request:Request) -> StarletteRequest:
  'Adapt a pithy.web Request to the Starlette Request that DbView expects; DbView reads only the path and query params.'
  return StarletteRequest(scope={
    'type': 'http',
    'method': request.method,
    'scheme': request.scheme,
    'server': (request.host, request.port),
    'path': request.path,
    'query_string': request.query_str.encode(),
    'headers': [],
  })


def open_library_db() -> Conn:
  'Create, populate and return a query-only in-memory library database.'
  conn = Conn('library', mode='memory')
  conn.executescript(''.join(library_schema.sql()))
  insert_rows(conn, authors_table, author_rows())
  insert_rows(conn, books_table, book_rows())
  conn.run_effect('PRAGMA query_only = 1')
  return conn


def insert_rows(conn:Conn, table:Table, rows:list[tuple[Any,...]]) -> None:
  placeholders = ', '.join('?' * len(table.columns))
  conn.executemany(f'INSERT INTO {table.name} ({table.quoted_columns_str}) VALUES ({placeholders})', rows)


def author_rows() -> list[tuple[Any,...]]:
  return [(id_, name, country, born, died, f'https://en.wikipedia.org/wiki/{name.replace(" ", "_")}')
    for id_, (name, country, born, died) in enumerate(authors, start=1)]


def book_rows() -> list[tuple[Any,...]]:
  '''
  Expand the compact `books` data with deterministic but varied prices, ratings, ISBNs and catalog timestamps.
  Every seventh book is unrated.
  '''
  rows = []
  catalog_start = datetime(2025, 1, 6, 9, 0)
  for id_, (title, author_id, year, pages) in enumerate(books, start=1):
    price_cents = 499 + (pages * 7) % 1600 // 100 * 100
    rating = None if id_ % 7 == 0 else round(3 + (id_ * 37) % 21 / 10, 1)
    added_at = catalog_start + timedelta(days=id_ * 3, minutes=(id_ * 97) % 600)
    rows.append((id_, title, author_id, year, pages, price_cents, rating, isbn13(id_), f'{added_at:%Y-%m-%d %H:%M:%S}'))
  return rows


def isbn13(n:int) -> str:
  'Return a fictitious ISBN-13 with a valid check digit.'
  digits = f'978{(n * 7919) % 10**9:09d}'
  check = (10 - sum(int(d) * (3 if idx % 2 else 1) for idx, d in enumerate(digits)) % 10) % 10
  return f'{digits[:3]}-{digits[3:5]}-{digits[5:9]}-{digits[9:]}-{check}'


# (name, country, born, died) rows; ids are assigned in order starting from 1.
# The countries and years were recited from LLM memory and have not been verified.
authors:list[tuple[str,str,int,int|None]] = [
  ('Jane Austen', 'United Kingdom', 1775, 1817),
  ('Charles Dickens', 'United Kingdom', 1812, 1870),
  ('Mark Twain', 'United States', 1835, 1910),
  ('Leo Tolstoy', 'Russia', 1828, 1910),
  ('Fyodor Dostoevsky', 'Russia', 1821, 1881),
  ('Herman Melville', 'United States', 1819, 1891),
  ('Mary Shelley', 'United Kingdom', 1797, 1851),
  ('Charlotte Brontë', 'United Kingdom', 1816, 1855),
  ('Emily Brontë', 'United Kingdom', 1818, 1848),
  ('George Eliot', 'United Kingdom', 1819, 1880),
  ('Thomas Hardy', 'United Kingdom', 1840, 1928),
  ('Victor Hugo', 'France', 1802, 1885),
  ('Alexandre Dumas', 'France', 1802, 1870),
  ('Gustave Flaubert', 'France', 1821, 1880),
  ('Jules Verne', 'France', 1828, 1905),
  ('Nathaniel Hawthorne', 'United States', 1804, 1864),
  ('Edgar Allan Poe', 'United States', 1809, 1849),
  ('Henry James', 'United States', 1843, 1916),
  ('Joseph Conrad', 'United Kingdom', 1857, 1924),
  ('Oscar Wilde', 'Ireland', 1854, 1900),
  ('Arthur Conan Doyle', 'United Kingdom', 1859, 1930),
  ('H. G. Wells', 'United Kingdom', 1866, 1946),
  ('Virginia Woolf', 'United Kingdom', 1882, 1941),
  ('Franz Kafka', 'Austria-Hungary', 1883, 1924),
  ('Edith Wharton', 'United States', 1862, 1937),
  ('Ursula K. Le Guin', 'United States', 1929, 2018),
  ('Toni Morrison', 'United States', 1931, 2019),
  ('Kazuo Ishiguro', 'United Kingdom', 1954, None),
  ('Chimamanda Ngozi Adichie', 'Nigeria', 1977, None),
  ('Haruki Murakami', 'Japan', 1949, None),
]


# (title, author_id, year, pages) rows; ids are assigned in order starting from 1.
# The titles, attributions, years and page counts were recited from LLM memory and have not been verified.
# Author id 31 does not exist: it demonstrates a dangling reference, which the schema cannot prevent.
books:list[tuple[str,int|None,int,int]] = [
  ('Pride and Prejudice', 1, 1813, 432),
  ('Sense and Sensibility', 1, 1811, 409),
  ('Emma', 1, 1815, 474),
  ('Persuasion', 1, 1817, 249),
  ('Mansfield Park', 1, 1814, 507),
  ('Great Expectations', 2, 1861, 505),
  ('A Tale of Two Cities', 2, 1859, 489),
  ('Bleak House', 2, 1853, 1017),
  ('Oliver Twist', 2, 1838, 608),
  ('David Copperfield', 2, 1850, 882),
  ('Adventures of Huckleberry Finn', 3, 1884, 366),
  ('The Adventures of Tom Sawyer', 3, 1876, 274),
  ("A Connecticut Yankee in King Arthur's Court", 3, 1889, 448),
  ('War and Peace', 4, 1869, 1225),
  ('Anna Karenina', 4, 1878, 864),
  ('The Death of Ivan Ilyich', 4, 1886, 114),
  ('Crime and Punishment', 5, 1866, 671),
  ('The Brothers Karamazov', 5, 1880, 796),
  ('The Idiot', 5, 1869, 667),
  ('Notes from Underground', 5, 1864, 136),
  ('Moby-Dick', 6, 1851, 635),
  ('Bartleby, the Scrivener', 6, 1853, 64),
  ('Billy Budd', 6, 1924, 192),
  ('Frankenstein', 7, 1818, 280),
  ('The Last Man', 7, 1826, 479),
  ('Jane Eyre', 8, 1847, 507),
  ('Villette', 8, 1853, 573),
  ('Wuthering Heights', 9, 1847, 416),
  ('Middlemarch', 10, 1871, 880),
  ('Silas Marner', 10, 1861, 256),
  ('The Mill on the Floss', 10, 1860, 576),
  ("Tess of the d'Urbervilles", 11, 1891, 518),
  ('Far from the Madding Crowd', 11, 1874, 464),
  ('Jude the Obscure', 11, 1895, 496),
  ('Les Misérables', 12, 1862, 1463),
  ('The Hunchback of Notre-Dame', 12, 1831, 940),
  ('The Count of Monte Cristo', 13, 1844, 1276),
  ('The Three Musketeers', 13, 1844, 700),
  ('Madame Bovary', 14, 1857, 329),
  ('Sentimental Education', 14, 1869, 464),
  ('Twenty Thousand Leagues Under the Seas', 15, 1870, 426),
  ('Around the World in Eighty Days', 15, 1872, 256),
  ('Journey to the Center of the Earth', 15, 1864, 240),
  ('The Scarlet Letter', 16, 1850, 272),
  ('The House of the Seven Gables', 16, 1851, 344),
  ('The Narrative of Arthur Gordon Pym of Nantucket', 17, 1838, 217),
  ('Tales of the Grotesque and Arabesque', 17, 1840, 528),
  ('The Portrait of a Lady', 18, 1881, 656),
  ('The Turn of the Screw', 18, 1898, 121),
  ('The Wings of the Dove', 18, 1902, 608),
  ('Heart of Darkness', 19, 1899, 96),
  ('Lord Jim', 19, 1900, 368),
  ('Nostromo', 19, 1904, 480),
  ('The Picture of Dorian Gray', 20, 1890, 254),
  ('The Importance of Being Earnest', 20, 1895, 76),
  ('A Study in Scarlet', 21, 1887, 108),
  ('The Sign of the Four', 21, 1890, 122),
  ('The Hound of the Baskervilles', 21, 1902, 256),
  ('The Time Machine', 22, 1895, 118),
  ('The Invisible Man', 22, 1897, 149),
  ('The War of the Worlds', 22, 1898, 192),
  ('Mrs Dalloway', 23, 1925, 194),
  ('To the Lighthouse', 23, 1927, 209),
  ('Orlando', 23, 1928, 333),
  ('The Metamorphosis', 24, 1915, 70),
  ('The Trial', 24, 1925, 255),
  ('The Castle', 24, 1926, 352),
  ('The House of Mirth', 25, 1905, 329),
  ('Ethan Frome', 25, 1911, 195),
  ('The Age of Innocence', 25, 1920, 365),
  ('A Wizard of Earthsea', 26, 1968, 183),
  ('The Left Hand of Darkness', 26, 1969, 304),
  ('The Dispossessed', 26, 1974, 387),
  ('The Bluest Eye', 27, 1970, 206),
  ('Song of Solomon', 27, 1977, 337),
  ('Beloved', 27, 1987, 324),
  ('The Remains of the Day', 28, 1989, 245),
  ('Never Let Me Go', 28, 2005, 288),
  ('Klara and the Sun', 28, 2021, 303),
  ('Purple Hibiscus', 29, 2003, 307),
  ('Half of a Yellow Sun', 29, 2006, 433),
  ('Americanah', 29, 2013, 588),
  ('Norwegian Wood', 30, 1987, 296),
  ('The Wind-Up Bird Chronicle', 30, 1994, 607),
  ('Kafka on the Shore', 30, 2002, 467),
  ('The Epic of Gilgamesh', None, -1200, 120),
  ('One Thousand and One Nights', None, 900, 1008),
  ('Beowulf', None, 1000, 213),
  ('The Moonstone', 31, 1868, 528),
]
