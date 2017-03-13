#!/usr/bin/env python
# -*- coding: utf-8 -*-
# setup.py
"""Setup script for dicompyler."""
# Copyright (c) 2012-2014 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

from setuptools import setup, find_packages

requires = [
    'matplotlib>=1.3, <=1.5.1',
    'numpy>=1.2.1',
    'pillow>=1.0',
    'dicompyler-core>=0.5.2',
    'pydicom>=0.9.9']

setup(
    name="dicompyler",
    version = "0.5.0",
    include_package_data = True,
    packages = find_packages(),
    package_data = {'dicompyler':
        ['*.txt', 'resources/*.png', 'resources/*.xrc', 'resources/*.ico',
        'baseplugins/*.py', 'baseplugins/*.xrc']},
    zip_safe = False,
    install_requires = requires,
    dependency_links = [
        'git+https://github.com/darcymason/pydicom.git#egg=pydicom-1.0.0'],
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
    
    - Python 2.7 or higher (not tested on Python 3)
    - wxPython 3.0.2.0 (not tested on wxPython Phoenix)
    - matplotlib 1.3 to 1.5.1
    - numpy 1.2 or higher
    - Pillow 1.0 or higher
    - dicompyler-core 0.5.2 or higher
    - pydicom 0.9.9 or higher""",
)