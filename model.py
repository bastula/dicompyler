#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# model.py
"""Data model file to store various settings and preferences."""
# Copyright (c) 2009 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

from elixir import *
from sqlalchemy.databases import sqlite
import util

metadata.bind = "sqlite:///dicompyler.db"
if not util.main_is_frozen:
    metadata.bind.echo = True

class Preferences(Entity):
    name = Field(Unicode(50))
    value = Field(Unicode(200))
