#!/usr/bin/env python
# -*- coding: utf-8 -*-
# util.py
"""Several utility functions that don't really belong anywhere."""
# Copyright (c) 2009-2017 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

from __future__ import with_statement
import imp, os, sys
import subprocess

def platform():
    if sys.platform.startswith('win'):
        return 'windows'
    elif sys.platform.startswith('darwin'):
        return 'mac'
    return 'linux'

def GetResourcePath(resource):
    """Return the specified item from the resources folder."""

    if main_is_frozen():
        if (platform() == 'mac'):
            return os.path.join((os.path.join(get_main_dir(), '../Resources')), resource)
    return os.path.join((os.path.join(get_main_dir(), 'resources')), resource)

def GetBasePluginsPath(resource):
    """Return the specified item from the base plugins folder."""

    if main_is_frozen():
        if (platform() == 'mac'):
            return os.path.join((os.path.join(get_main_dir(), '../PlugIns')), resource)
    return os.path.join((os.path.join(get_main_dir(), 'baseplugins')), resource)

# from http://www.py2exe.org/index.cgi/HowToDetermineIfRunningFromExe
def main_is_frozen():
   return (hasattr(sys, "frozen") or # new py2exe
           hasattr(sys, "importers") # old py2exe
           or imp.is_frozen("__main__")) # tools/freeze

def get_main_dir():
    if main_is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)

def get_text_resources(resource):
    """Return the resources that are located in the root folder of the
        distribution, except for the Mac py2app version, which is located
        in the Resources folder in the app bundle."""

    if (main_is_frozen() and (platform() == 'mac')):
        resource = GetResourcePath(resource)
    else:
        resource = (os.path.join(get_main_dir(), resource))

    return resource

def open_path(path):
    """Open the specified path in the system default folder viewer."""

    if sys.platform == 'darwin':
        subprocess.check_call(["open", path])
    elif sys.platform == 'linux2':
        subprocess.check_call(["gnome-open", path])
    elif sys.platform == 'win32':
        subprocess.Popen("explorer " + path)

def get_credits():
    """Read the credits file and return the data from it."""
    
    developers = []
    artists = []
    with open(get_text_resources('credits.txt'), 'rU') as cf:
        credits = cf.readlines()
        for i, v in enumerate(credits):
            if (v == "Lead Developer\n"):
                developers.append(credits[i+1].strip())
            if (v == "Developers\n"):
                for d in credits[i+1:len(credits)]:
                    if (d.strip() == ""):
                        break
                    developers.append(d.strip())
            if (v == "Artists\n"):
                for a in credits[i+1:len(credits)]:
                    if (a.strip() == ""):
                        break
                    artists.append(a.strip())
    return {'developers':developers, 'artists':artists}
