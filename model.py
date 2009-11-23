#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

from elixir import *
import util

metadata.bind = "sqlite:///dicompyler.db"
if not util.main_is_frozen:
    metadata.bind.echo = True

class Preferences(Entity):
    name = Field(Unicode(50))
    value = Field(Unicode(200))
