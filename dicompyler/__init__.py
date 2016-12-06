#!/usr/bin/env python
# -*- coding: utf-8 -*-
# __init__.py
"""Package initialization for dicompyler."""
# Copyright (c) 2009-2011 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
from __future__ import print_function, division, absolute_import
from dicompyler.main import start, __version__

if __name__ == '__main__':
    import dicompyler.main
    dicompyler.main.start()