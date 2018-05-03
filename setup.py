# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# distutils setup script.
# users should install with: `$ pip3 install pat`
# developers can make a local install with: `$ pip3 install -e .`
# upload to pypi test server with: `$ py3 setup.py sdist upload -r pypitest`
# upload to pypi prod server with: `$ py3 setup.py sdist upload`

from setuptools import setup


long_description = '''\
Pat is a tool for patching text files, similar to the traditional unix `diff` and `patch`. It is designed to make patching text data (not just source code) more convenient than the older tools, in particular within the Muck build system envirnoment (see http://github.com/gwk/muck).
'''

setup(
  name='pat-tool',
  license='CC0',
  version='0.0.0',
  author='George King',
  author_email='george.w.king@gmail.com',
  url='https://github.com/gwk/pat',
  description='Pat is a tool for patching text files.',
  long_description=long_description,
  install_requires=[],
  packages=['pat'],
  entry_points = { 'console_scripts': [
    'pat=pat.__main__:main',
  ]},
  keywords=['pat', 'diff', 'patch'],
  classifiers=[ # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: Education',
    'Intended Audience :: Information Technology',
    'Intended Audience :: Science/Research',
    'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
    'Programming Language :: Python :: 3 :: Only',
    'Topic :: Documentation',
    'Topic :: Education',
    'Topic :: Internet',
    'Topic :: Multimedia',
    'Topic :: Scientific/Engineering',
    'Topic :: Software Development',
    'Topic :: Software Development :: Build Tools',
    'Topic :: Text Processing',
    'Topic :: Utilities',
  ],
)
