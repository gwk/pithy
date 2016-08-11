# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# setuptools setup script.
# users should install with: `$ pip3 install legs`
# developers can make a local install with: `$ pip3 install -e .`
# upload to pypi test server with: `$ python3 setup.py sdist upload -r pypitest`
# upload to pypi prod server with: `$ python3 setup.py sdist upload`

from setuptools import setup


long_description = '''\
Legs is a lexical analyzer generator.
'''

setup(
  name='legs',
  license='CC0',
  version='0.0.0',
  author='George King',
  author_email='george.w.king@gmail.com',
  url='https://github.com/gwk/iotest',
  description='A lexical analyzer generator.',
  long_description=long_description,
  install_requires=['pithy'],
  entry_points = {'console_scripts': ['legs=legs.__main__:main']},
  keywords=['testing'],
  classifiers=[ # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
    'Programming Language :: Python :: 3 :: Only',
  ],
)
