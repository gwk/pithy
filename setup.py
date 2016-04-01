#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# distutils setup script.

# You can install the modules into your Python distribution with:
# $ python3 setup.py install

from os.path import abspath, dirname, join
from setuptools import setup, find_packages

with open(join(abspath(dirname(__file__)), 'readme.txt')) as f:
  readme = f.read()

setup(
  name='pithy',
  license='CC0',
  version='0.0.0',
  author='George King',
  author_email='george.w.king@gmail.com',
  url='https://github.com/gwk/pithy',
  description='Pithy is a collection of utilities for scripting in Python 3.',
  long_description=readme,
  packages=find_packages(exclude=['_misc']),
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
