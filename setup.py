# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from setup_utils import *
from setuptools import setup


setup(
  name='pithy',
  version='0.0.4',
  url='https://github.com/gwk/pithy',
  description='Pithy is a collection of libraries for Python 3.',

  packages=discover_packages(['craft', 'iotest', 'legs', 'pithy']),
  py_modules=['utest'],
  bin_dirs=['craft/bin', 'iotest/bin', 'pithy/bin', 'writeup/bin'],
  cmdclass=cmdclass,
)
