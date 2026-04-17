# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.date import Date
from pithy.web.starlette import (get_query_bool, get_query_date, get_query_int, req_query_bool, req_query_date, req_query_int,
  req_query_str)
from starlette.datastructures import QueryParams
from starlette.exceptions import HTTPException
from utest import utest, utest_exc


qp = QueryParams({'one': '1', 'zero': '0', 'empty': ''})

utest('1', req_query_str, qp, 'one')
utest_exc(HTTPException, req_query_str, qp, 'missing')

utest(True, get_query_bool, qp, 'one')
utest(False, get_query_bool, qp, 'zero')
utest(False, get_query_bool, qp, 'missing')
utest(False, get_query_bool, qp, 'empty')
utest(True, get_query_bool, qp, 'missing', default=True)
utest(False, get_query_bool, qp, 'missing', default=False)
utest(True, get_query_bool, qp, 'empty', default=True)
utest(False, get_query_bool, qp, 'empty', default=False)

utest(True, req_query_bool, qp, 'one')
utest(False, req_query_bool, qp, 'zero')
utest_exc(HTTPException, req_query_bool, qp, 'missing')
utest_exc(HTTPException, req_query_bool, qp, 'empty')

utest(1, get_query_int, qp, 'one')
utest(None, get_query_int, qp, 'missing')
utest(None, get_query_int, qp, 'empty')
utest(1, get_query_int, qp, 'missing', default=1)
utest(1, get_query_int, qp, 'empty', default=1)

utest(1, req_query_int, qp, 'one')
utest_exc(HTTPException, req_query_int, qp, 'missing')
utest_exc(HTTPException, req_query_int, qp, 'empty')

utest(Date(2000, 1, 1), get_query_date, QueryParams({'d': '2000-01-01'}), 'd')
utest(Date(2000, 1, 1), get_query_date, QueryParams(), 'missing', default=Date(2000, 1, 1))
utest(None, get_query_date, QueryParams(), 'missing')
utest_exc(HTTPException, get_query_date, QueryParams({'d': '!2000-01-01'}), 'd')

utest(Date(2000, 1, 1), req_query_date, QueryParams({'d': '2000-01-01'}), 'd')
utest_exc(HTTPException, req_query_date, QueryParams(), 'missing')
utest_exc(HTTPException, req_query_date, QueryParams({'d': '!2000-01-01'}), 'd')
