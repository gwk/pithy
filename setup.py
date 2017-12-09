# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from setuptools import setup


name = 'craft'

setup(
  name='craft-tools',
  version='0.0.0',
  license='CC0',
  author='George King',
  author_email='george.w.king@gmail.com',
  url='https://github.com/gwk/' + name,
  description='Craft is a build system.',
  long_description=open('readme.wu').read(),
  packages=[name],
  entry_points = {'console_scripts': [
    'craft-docs=craft.docs:main',
    'craft-mac-app=craft.mac_app:main',
    'craft-py-check=craft.py_check:main',
    'craft-swift=craft.swift:main',
    'craft-swift-utest=craft.swift_utest:main',
    'craft-tsc=craft.tsc:main',
  ]},
  install_requires=[
    'pithy'
  ],
  keywords=[
    'build',
    'build system',
    'mypy',
    'swift',
    'typescript',
  ],
  classifiers=[ # See https://pypi.python.org/pypi?%3Aaction=list_classifiers.
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
    'Programming Language :: Python :: 3 :: Only',
  ],
)
