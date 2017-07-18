#!/usr/bin/env python
# -*- coding: utf-8 -*-
# __init__.py
"""Package initialization for dicompyler."""
# Copyright (c) 2009-2017 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/bastula/dicompyler/

__author__ = 'Aditya Panchal'
__email__ = 'apanchal@bastula.org'
__version__ = '0.5.0'
__version_info__ = (0, 5, 0)


from dicompyler.main import start

if __name__ == '__main__':
    import dicompyler.main
    dicompyler.main.start()