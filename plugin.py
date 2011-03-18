#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# plugin.py
"""Plugin manager for dicompyler."""
# Copyright (c) 2010 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

import imp, os
import wx
from wx.xrc import *
from model import *
import guiutil, util

def import_plugins():
    """Find and import available plugins."""

    # Get the base plugin path
    basepath = util.GetBasePluginsPath('')
    # Get the user plugin path
    datapath = guiutil.get_data_dir()
    userpath = os.path.join(datapath, 'plugins')
    # Get the list of possible plugins from both paths
    possibleplugins = []
    for i in os.listdir(userpath):
        possibleplugins.append(i)
    for i in os.listdir(basepath):
        possibleplugins.append(i)

    modules = []
    plugins = []
    for file in possibleplugins:
        module = file.split('.')[0]
        if module not in modules:
            if not ((module == "__init__") or (module == "")):
                # only try to import the module once
                modules.append(module)
                try:
                    f, filename, description = imp.find_module(module, [userpath, basepath])
                except (ImportError):
                    # Not able to find module so pass
                    pass
                else:
                    # Import the module if no exception occurred
                    plugins.append(imp.load_module(module, f, filename, description))
                    print 'Plugin:', module, 'loaded'
                    f.close()
    return plugins

def PluginManager(parent, plugins):
    """Prepare to show the plugin manager dialog."""

    # Load the XRC file for our gui resources
    res = XmlResource(util.GetResourcePath('plugin.xrc'))

    dlgPluginManager = res.LoadDialog(parent, "PluginManagerDialog")
    dlgPluginManager.Init(plugins)

    # Show the dialog
    dlgPluginManager.ShowModal()

class PluginManagerDialog(wx.Dialog):
    """Manage the available plugins."""

    def __init__(self):
        pre = wx.PreDialog()
        # the Create step is done by XRC.
        self.PostCreate(pre)

    def Init(self, plugins):
        """Method called after the panel has been initialized."""

        # Set window icon
        if not guiutil.IsMac():
            self.SetIcon(guiutil.get_icon())

        # Initialize controls
        self.lcPlugins = XRCCTRL(self, 'lcPlugins')
        self.btnGetMorePlugins = XRCCTRL(self, 'btnGetMorePlugins')
        self.btnDeletePlugin = XRCCTRL(self, 'btnDeletePlugin')

        self.plugins = plugins

        # Bind interface events to the proper methods
#        wx.EVT_BUTTON(self, XRCID('btnDeletePlugin'), self.DeletePlugin)
        self.InitPluginList()
        self.LoadPlugins()

    def InitPluginList(self):
        """Initialize the plugin list control."""
        
        info = wx.ListItem()
        info.m_mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_IMAGE | wx.LIST_MASK_FORMAT
        info.m_image = -1
        info.m_format = 0
        
        info.m_text = 'Name'
        self.lcPlugins.InsertColumnInfo(0, info)
        self.lcPlugins.SetColumn(0, info)
        self.lcPlugins.SetColumnWidth(0, 120)
        
        info.m_text = 'Description'
        self.lcPlugins.InsertColumnInfo(1, info)
        self.lcPlugins.SetColumn(1, info)
        self.lcPlugins.SetColumnWidth(1, 300)
        
        info.m_text = 'Author'
        self.lcPlugins.InsertColumnInfo(2, info)
        self.lcPlugins.SetColumn(2, info)
        self.lcPlugins.SetColumnWidth(2, 150)
        
        info.m_text = 'Version'
        self.lcPlugins.InsertColumnInfo(3, info)
        self.lcPlugins.SetColumn(3, info)
        self.lcPlugins.SetColumnWidth(3, 75)

        info.m_text = 'Enabled'
        self.lcPlugins.InsertColumnInfo(4, info)
        self.lcPlugins.SetColumn(4, info)
        self.lcPlugins.SetColumnWidth(4, 75)

    def LoadPlugins(self):
        """Update and load the data for the plugin list control."""

        # Set up the plugins for each plugin entry point of dicompyler
        for n, p in enumerate(self.plugins):
            props = p.pluginProperties()
            self.lcPlugins.InsertStringItem(n, props['name'])
            self.lcPlugins.SetStringItem(n, 1, props['description'])
            self.lcPlugins.SetStringItem(n, 2, props['author'])
            self.lcPlugins.SetStringItem(n, 3, str(props['version']))
            self.lcPlugins.SetStringItem(n, 4, 'Yes')
