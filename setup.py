#!/usr/bin/env python
# -*- coding: utf-8 -*-
# dicompyler.py
"""Setup script for dicompyler."""
# Copyright (c) 2012 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages
import sys

requires = [
    'matplotlib>=0.99',
    'numpy>=1.2.1',
    'pil>=1.1.7',
    'pydicom>=0.9.5',]

if sys.version_info[0] == 2 and sys.version_info[1] < 6:
    requires.append('simplejson')

setup(
    name="dicompyler",
    version="0.4.2",
    include_package_data = True,
    packages = find_packages(),
    package_data = {'dicompyler':
        ['*.txt', 'resources/*.png', 'resources/*.xrc', 'resources/*.ico',
        'baseplugins/*.py', 'baseplugins/*.xrc']},
    zip_safe = False,
    install_requires = requires,
    entry_points={'console_scripts':['dicompyler = dicompyler.main:start']},

    # metadata for upload to PyPI
    author = "Aditya Panchal",
    author_email = "apanchal@bastula.org",
    description = "Extensible radiation therapy research platform and " + \
        "viewer for DICOM and DICOM RT.",
    license = "BSD License",
    keywords = "radiation therapy research python dicom dicom-rt",
    url = "http://code.google.com/p/dicompyler/",
    classifiers = [
        "License :: OSI Approved :: BSD License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Visualization"],
    long_description = """
    dicompyler
    ==========
    
    dicompyler is an extensible open source radiation therapy research 
    platform based on the DICOM standard. It also functions as a 
    cross-platform DICOM RT viewer.
    
    dicompyler runs on Windows, Mac and Linux systems and is available in 
    source and binary versions. Since dicompyler is based on modular 
    architecture, it is easy to extend it with 3rd party plugins.
    
    Visit the dicompyler _`home page`:
    http://code.google.com/p/dicompyler/ for how-to information and guides.

    Getting Help
    ============

    To get help with dicompyler, visit the _`mailing list`: 
    http://groups.google.com/group/dicompyler/ or follow us on _`twitter`: 
    http://twitter.com/dicompyler

    Requirements
    ============
    
    dicompyler requires the following packages to run from source:
    
    - Python 2.5 or higher (not tested on Python 3)
    - wxPython 2.8.8.1 or higher
    - matplotlib 0.99 or higher
    - numpy 1.2.1 or higher
    - PIL 1.1.7 or higher
    - pydicom 0.9.5 or higher
    - simplejson (only for Python 2.5, Python 2.6+ includes JSON support)""",
)