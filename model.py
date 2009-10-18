#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

from elixir import *

metadata.bind = "sqlite:///dicompyler.db"
metadata.bind.echo = True

class Preferences(Entity):
    name = Field(Unicode(50))
    value = Field(Unicode(200))
