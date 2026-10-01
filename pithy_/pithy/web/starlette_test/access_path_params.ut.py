# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.web.starlette import req_path_nat, req_path_pos_int
from starlette.exceptions import HTTPException
from starlette.requests import Request
from utest import utest, utest_exc


def request(**path_params:object) -> Request:
  return Request({'type': 'http', 'path_params': path_params})


utest(0, req_path_nat, request(n=0), 'n')
utest(42, req_path_nat, request(n=42), 'n')
utest(42, req_path_nat, request(n='42'), 'n')
utest_exc(HTTPException, req_path_nat, request(n=-1), 'n')
utest_exc(HTTPException, req_path_nat, request(n='-1'), 'n')
utest_exc(HTTPException, req_path_nat, request(n='nope'), 'n')
utest_exc(HTTPException, req_path_nat, request(), 'n')

utest(1, req_path_pos_int, request(n=1), 'n')
utest(42, req_path_pos_int, request(n='42'), 'n')
utest_exc(HTTPException, req_path_pos_int, request(n=0), 'n')
utest_exc(HTTPException, req_path_pos_int, request(n=-1), 'n')
utest_exc(HTTPException, req_path_pos_int, request(n='nope'), 'n')
utest_exc(HTTPException, req_path_pos_int, request(), 'n')
