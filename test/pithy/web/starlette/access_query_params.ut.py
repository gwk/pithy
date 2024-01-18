# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.date import Date
from pithy.web.starlette import (get_query_bool, get_query_date, get_query_int, req_query_bool, req_query_date, req_query_int,
  req_query_str)
from starlette.datastructures import QueryParams
from starlette.exceptions import HTTPException
from utest import utest, utest_exc


qp = QueryParams({'k': '1', 'j': '0', 'z': ''})

utest('1', req_query_str, qp, 'k')
utest_exc(HTTPException, req_query_str, qp, 'x')

utest(True, get_query_bool, qp, 'k')
utest(False, get_query_bool, qp, 'j')
utest(None, get_query_bool, qp, 'x')
utest(None, get_query_bool, qp, 'z')
utest(True, get_query_bool, qp, 'x', default=True)
utest(False, get_query_bool, qp, 'x', default=False)
utest(True, get_query_bool, qp, 'z', default=True)
utest(False, get_query_bool, qp, 'z', default=False)

utest(True, req_query_bool, qp, 'k')
utest(False, req_query_bool, qp, 'j')
utest_exc(HTTPException, req_query_bool, qp, 'x')
utest_exc(HTTPException, req_query_bool, qp, 'z')

utest(1, get_query_int, qp, 'k')
utest(None, get_query_int, qp, 'x')
utest(None, get_query_int, qp, 'z')
utest(1, get_query_int, qp, 'x', default=1)
utest(1, get_query_int, qp, 'z', default=1)

utest(1, req_query_int, qp, 'k')
utest_exc(HTTPException, req_query_int, qp, 'x')
utest_exc(HTTPException, req_query_int, qp, 'z')

utest(Date(2000, 1, 1), get_query_date, QueryParams({'d': '2000-01-01'}), 'd')
utest(Date(2000, 1, 1), get_query_date, QueryParams(), 'x', default=Date(2000, 1, 1))
utest(None, get_query_date, QueryParams(), 'x')
utest_exc(HTTPException, get_query_date, QueryParams({'d': '!2000-01-01'}), 'd')

utest(Date(2000, 1, 1), req_query_date, QueryParams({'d': '2000-01-01'}), 'd')
utest_exc(HTTPException, req_query_date, QueryParams(), 'x')
utest_exc(HTTPException, req_query_date, QueryParams({'d': '!2000-01-01'}), 'd')
