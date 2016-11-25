# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from setuptools import setup

name = 'iotest'

setup(
  name=name,
  version='0.0.0',
  license='CC0',
  author='George King',
  author_email='george.w.king@gmail.com',
  url='https://github.com/gwk/' + name,
  description='iotest is a small tool for testing programs based on input and output.',
  long_description=open('readme.wu').read(),
  py_modules=[name],
  entry_points = {'console_scripts': [
    'iotest=iotest:main'
  ]},
  install_requires=[
    'pithy'
  ],
  keywords=[
    'testing'
  ],
  classifiers=[ # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
    'Programming Language :: Python :: 3 :: Only',
    'Topic :: Software Development :: Testing',
  ],
)
