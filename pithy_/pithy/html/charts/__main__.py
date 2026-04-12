# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stderr

import uvicorn
import watchfiles  # This is an optional import for uvicorn but we want to make sure it is installed.


_ = watchfiles

def main() -> None:
  print('Serving chart _webtest', file=stderr)
  uvicorn.run("pithy.html.charts._webtest:app", host='localhost', port=8000, log_level="info", factory=True, reload=True)


if __name__ == '__main__': main()
