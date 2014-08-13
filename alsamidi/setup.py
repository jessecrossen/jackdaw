has_setuptools = False
try:
	from setuptools import setup, Extension
	has_setuptools = True
except ImportError:
	from distutils.core import setup, Extension

import sys
import os
import string
import time

version = '0.1.0'

kwargs = dict()
if has_setuptools:
	kwargs = dict(
			include_package_data = True,
			install_requires = ['setuptools'],
			zip_safe = False)

setup(
	name = 'alsamidi',
	version = version,
	description = 'ALSA MIDI bindings for Python',
	author = 'Jesse Crossen',
	author_email = 'jesse.crossen@gmail.com',
	url = 'http://github.com/jessecrossen/impulse/alsamidi',
	license = 'WTFPL',
	ext_modules = [
		Extension('alsamidi', 
		  [ 'alsamidi.c' ],
		  libraries=['asound'])
	],
	data_files = [ ( 'share/alsamidi-'+version, [ ] ) ],
	platforms = ['linux'],
	long_description='''alsamidi provides Python bindings for the ALSA RawMidi module on Linux.''',
	classifiers=[ "Development Status :: 3 - Alpha",
            "Topic :: Multimedia :: Sound/Audio :: MIDI" ],
	package_dir = {'': '.',},
	**kwargs
)
