# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from copy import deepcopy

from uvicorn.config import LOGGING_CONFIG


log_config = deepcopy(LOGGING_CONFIG)
log_config['formatters']['default'] = {'()': 'pithy.logs.PithyLogFormatter'}
log_config['formatters']['access'] = {'()': 'pithy.logs.PithyLogFormatter'}
