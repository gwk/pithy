# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.date import Date
from starlette.convertors import Convertor, register_url_convertor
from starlette.exceptions import HTTPException


class DateConverter(Convertor):
  '''
  A simple converter to get ISO dates out out of URL paths in a Starlette Router.
  To register with Starlette: `DateConverter.register()`.
  To use in a route: `Route('/calendar/{date:date}', calendar_endpoint)`
  '''

  regex = '[0-9]{4}-[0-9]{2}-[0-9]{2}'

  def convert(self, value:str) -> Date:
    try: return Date.fromisoformat(value)
    except ValueError as e: raise HTTPException(404) from e


  def to_string(self, value:Date) -> str: return value.isoformat()


  @classmethod
  def  register(cls, name='date') -> None:
    register_url_convertor(name, cls())
