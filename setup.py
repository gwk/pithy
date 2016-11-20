# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from setuptools import setup


name = 'pithy'

setup(
  name=name,
  version='0.0.0',
  license='CC0',
  author='George King',
  author_email='george.w.king@gmail.com',
  url='https://github.com/gwk/' + name,
  description='Pithy is a collection of utilities for scripting in Python 3.',
  long_description=open('readme.wu').read(),
  packages=['pithy'],
  keywords=[
    'scripting', 'testing', 'utilities'
  ],
  classifiers=[ # See https://pypi.python.org/pypi?%3Aaction=list_classifiers.
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
