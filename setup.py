# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# distutils setup script.
# users should install with: `$ pip3 install pithy`
# developers can make a local install with: `$ pip3 install -e .`
# upload to pypi test server with: `$ python3 setup.py sdist upload -r pypitest`
# upload to pypi prod server with: `$ python3 setup.py sdist upload`

from setuptools import setup

long_description = '''
Pithy is a small library of python utilities. Many of the functions are simple wrappers around standard library functions, but named to make scripts read more concisely. There are several families of functions with abbreviation conventions, e.g. errZ, errL, errSL, errLL all print to stderr, but with different `sep` and `end` values. Similarly, there is a family of 'run' functions for spawning subprocesses and then checking or returning various combinations of exit status code, stdout, and stderr.

The result is that code may look a bit more cryptic or less traditional, but is made more correct and concise by handling boring details like stdout versus stderr and error checking/reporting minutiae correctly.

The project is hosted at 'https://github.com/gwk/pithy'.
'''

setup(
  name='pithy',
  license='CC0',
  version='0.0.0',
  author='George King',
  author_email='george.w.king@gmail.com',
  url='https://github.com/gwk/pithy',
  description='Pithy is a collection of utilities for scripting in Python 3.',
  long_description=long_description,
  packages=['pithy'],
  keywords=['scripting', 'testing', 'utilities'],
  classifiers=[ # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
    'Programming Language :: Python :: 3 :: Only',
    'Topic :: Software Development',
    'Topic :: Software Development :: Build Tools',
    'Topic :: Software Development :: Testing',
    'Topic :: Utilities',
  ],
)
