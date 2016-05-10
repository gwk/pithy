# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# setuptools setup script.
# users should install with: `$ pip3 install iotest`
# developers can make a local install with: `$ pip3 install -e .`
# upload to pypi test server with: `$ py3 setup.py sdist upload -r pypitest`
# upload to pypi prod server with: `$ py3 setup.py sdist upload`

from setuptools import setup


long_description = '''\
iotest is a small tool for testing programs based on input and output.
'''

setup(
  name='iotest',
  license='CC0',
  version='0.0.0',
  author='George King',
  author_email='george.w.king@gmail.com',
  url='https://github.com/gwk/iotest',
  description='iotest is a small tool for testing programs based on input and output.',
  long_description=long_description,
  py_modules=['iotest'],
  entry_points = {'console_scripts': ['iotest=iotest:main']},
  keywords=['testing'],
  classifiers=[ # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
    'Programming Language :: Python :: 3 :: Only',
    'Topic :: Software Development :: Testing',
  ],
)
