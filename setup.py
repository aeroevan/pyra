#!/usr/bin/env python
from setuptools import setup, find_packages
from codecs import open
from os import path
import re

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


def parse_requirements(file_name):
    '''Parse requirements from a pip ``requirements.txt`` style file

    :param str file_name: the file to parse

    :returns: a list of requirements
    :rtype: list
    '''
    requirements = []
    for line in open(file_name, 'r').read().split('\n'):
        if re.match(r'(\s*#)|(\s*$)', line) or line.startswith('-'):
            continue
        elif '://' in line or line.startswith('-e'):
            # TODO support version numbers
            if 'egg' in line:
                requirements.append(re.sub(r'.*#egg=(.*)$', r'\1', line))
            elif 'file' in line:
                requirements.append(line.strip().rsplit('/', 1)[1])
            else:
                pass
        elif re.match(r'\s*-f\s+', line):
            pass
        else:
            requirements.append(line)
    return requirements


def parse_dependency_links(file_name):
    '''Parse dependency links from a pip ``requirements.txt`` style file

    :param str file_name: the file to parse

    :returns: a list of dependency links
    :rtype: list
    '''
    dependency_links = []
    for line in open(file_name, 'r').read().split('\n'):
        if re.match(r'\s*-[ef]\s+', line):
            dependency_links.append(re.sub(r'\s*-[ef]\s+', '', line))
    return dependency_links


setup(
    name='pyra',
    version='0.0.1',
    description='Python Text Indexer and Qurery Scripts',
    long_description=long_description,
    author='Evan McClain',
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],

    packages=find_packages(),
    install_requires=parse_requirements('requirements.txt'),
    dependency_links=parse_dependency_links('requirements.txt'),

    entry_points={
        'console_scripts': [
            'pyra-index=pyra.index:main',
            'pyra-query=pyra.query:main'
        ],
    }
)
