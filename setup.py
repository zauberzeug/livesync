#!/usr/bin/env python
import os
from distutils.core import setup

VERSION = os.getenv('VERSION', '0.0.1')
setup(
    name='LiveSync',
    version=VERSION,
    description='Repeatedly synchronize local workspace with a (slow) remote machine',
    license='MIT',
    author='Zauberzeug GmbH',
    author_email='info@zauberzeug.com',
    url='https://github.com/zauberzeug/livesync',
    keywords='snyc remote watch filesystem development deploy live hot reload',
    python_requires='>=3.7',
    packages=['livesync'],
    entry_points={
        'console_scripts': [
            'livesync=livesync.livesync:main',
        ],
    },
)
