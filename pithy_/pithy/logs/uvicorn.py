# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from copy import deepcopy

from uvicorn.config import LOGGING_CONFIG


_context_keywords_ = ['access log', 'logging configuration', 'structured logging']


log_config = deepcopy(LOGGING_CONFIG)
log_config['formatters']['default'] = {'()': 'pithy.logs.PithyLogFormatter'}
log_config['formatters']['access'] = {'()': 'pithy.logs.PithyLogFormatter'}
