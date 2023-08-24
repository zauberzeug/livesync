#!/usr/bin/env python
import os
from pathlib import Path

from setuptools import setup

long_description = (Path(__file__).parent / 'README.md').read_text()
requirements = (Path(__file__).parent / 'requirements.txt').read_text()
VERSION = os.getenv('VERSION', '0.0.1')

setup(
    name='LiveSync',
    version=VERSION,
    description='Repeatedly synchronize local workspace with a (slow) remote machine',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='MIT',
    author='Zauberzeug GmbH',
    author_email='info@zauberzeug.com',
    url='https://github.com/zauberzeug/livesync',
    keywords='sync remote watch filesystem development deploy live hot reload',
    python_requires='>=3.7',
    packages=['livesync'],
    install_requires=requirements.splitlines(),
    entry_points={
        'console_scripts': [
            'livesync=livesync.livesync:main',
        ],
    },
)
