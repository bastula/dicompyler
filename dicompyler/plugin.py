#!/usr/bin/env python
# -*- coding: utf-8 -*-
# plugin.py
"""Plugin manager for dicompyler."""
# Copyright (c) 2010-2017 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/bastula/dicompyler/

import logging
logger = logging.getLogger('dicompyler.plugin')
import imp, os
import wx
from wx.xrc import *
from pubsub import pub
from dicompyler import guiutil, util

def import_plugins(userpath=None):
    """Find and import available plugins."""

    # Get the base plugin path
    basepath = util.GetBasePluginsPath('')
    # Get the user plugin path if it has not been set
    if (userpath == None):
        datapath = guiutil.get_data_dir()
        userpath = os.path.join(datapath, 'plugins')
    # Get the list of possible plugins from both paths
    possibleplugins = []
    for i in os.listdir(userpath):
        possibleplugins.append({'plugin': i, 'location': 'user'})
    for i in os.listdir(basepath):
        possibleplugins.append({'plugin': i, 'location': 'base'})

    modules = []
    plugins = []
    for p in possibleplugins:
        module = p['plugin'].split('.')[0]
        if module not in modules and not ((module == "__init__") or (module == "")):
            # only try to import the module once
            modules.append(module)
            try:
                f, filename, description = \
                        imp.find_module(module, [userpath, basepath])
            except ImportError:
                # Not able to find module so pass
                pass
            else:
                # Try to import the module if no exception occurred
                try:
                    m = imp.load_module(module, f, filename, description)
                except ImportError:
                    logger.exception("%s could not be loaded", module)
                else:
                    plugins.append({'plugin': m,
                                    'location': p['location']})
                    logger.debug("%s loaded", module)
                # If the module is a single file, close it
                if not (description[2] == imp.PKG_DIRECTORY):
                    f.close()
    return plugins

def PluginManager(parent, plugins, pluginsDisabled):
    """Prepare to show the plugin manager dialog."""

    # Load the XRC file for our gui resources
    res = XmlResource(util.GetResourcePath('plugin.xrc'))

    dlgPluginManager = res.LoadDialog(parent, "PluginManagerDialog")
    dlgPluginManager.Init(plugins, pluginsDisabled)

    # Show the dialog
    dlgPluginManager.ShowModal()

class PluginManagerDialog(wx.Dialog):
    """Manage the available plugins."""

    def __init__(self):
        wx.Dialog.__init__(self)

    def Init(self, plugins, pluginsDisabled):
        """Method called after the panel has been initialized."""

        # Set window icon
        if not guiutil.IsMac():
            self.SetIcon(guiutil.get_icon())

        # Initialize controls
        self.tcPlugins = XRCCTRL(self, 'tcPlugins')
        self.panelTreeView = XRCCTRL(self, 'panelTreeView')
        self.panelProperties = XRCCTRL(self, 'panelProperties')
        self.lblName = XRCCTRL(self, 'lblName')
        self.lblAuthor = XRCCTRL(self, 'lblAuthor')
        self.lblPluginType = XRCCTRL(self, 'lblPluginType')
        self.lblVersion = XRCCTRL(self, 'lblVersion')
        self.lblVersionNumber = XRCCTRL(self, 'lblVersionNumber')
        self.lblDescription = XRCCTRL(self, 'lblDescription')
        self.checkEnabled = XRCCTRL(self, 'checkEnabled')
        self.lblMessage = XRCCTRL(self, 'lblMessage')
        self.btnGetMorePlugins = XRCCTRL(self, 'btnGetMorePlugins')
        self.btnDeletePlugin = XRCCTRL(self, 'btnDeletePlugin')

        self.plugins = plugins
        self.pluginsDisabled = set(pluginsDisabled)

        # Bind interface events to the proper methods
#        wx.EVT_BUTTON(self, XRCID('btnDeletePlugin'), self.DeletePlugin)
        # wx.EVT_CHECKBOX(self, XRCID('checkEnabled'), self.OnEnablePlugin)
        self.Bind(wx.EVT_CHECKBOX, self.OnEnablePlugin, id=XRCID('checkEnabled'))
        # wx.EVT_TREE_ITEM_ACTIVATED(self, XRCID('tcPlugins'), self.OnEnablePlugin)
        self.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnEnablePlugin, id=XRCID('tcPlugins'))
        # wx.EVT_TREE_SEL_CHANGED(self, XRCID('tcPlugins'), self.OnSelectTreeItem)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnSelectTreeItem, id=XRCID('tcPlugins'))
        # wx.EVT_TREE_SEL_CHANGING(self, XRCID('tcPlugins'), self.OnSelectRootItem)
        self.Bind(wx.EVT_TREE_SEL_CHANGING, self.OnSelectRootItem, id=XRCID('tcPlugins'))

        # Modify the control and font size as needed
        font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        if guiutil.IsMac():
            children = list(self.Children) + \
                        list(self.panelTreeView.Children) + \
                        list(self.panelProperties.Children)
            for control in children:
                control.SetFont(font)
                control.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)
            XRCCTRL(self, 'wxID_OK').SetWindowVariant(wx.WINDOW_VARIANT_NORMAL)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        if guiutil.IsMSWindows():
            self.tcPlugins.SetPosition((0, 3))
            self.panelTreeView.SetWindowStyle(wx.STATIC_BORDER)
        if (guiutil.IsMac() or guiutil.IsGtk()):
            self.tcPlugins.SetPosition((-30, 0))
            self.panelTreeView.SetWindowStyle(wx.SUNKEN_BORDER)
        self.lblName.SetFont(font)
        self.lblMessage.SetFont(font)

        self.Layout()
        self.InitPluginList()
        self.LoadPlugins()

    def InitPluginList(self):
        """Initialize the plugin list control."""

        iSize = (16, 16)
        iList = wx.ImageList(iSize[0], iSize[1])
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('bricks.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('plugin.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('plugin_disabled.png'),
                wx.BITMAP_TYPE_PNG))
        self.tcPlugins.AssignImageList(iList)
        self.root = self.tcPlugins.AddRoot('Plugins')
        self.baseroot = self.tcPlugins.AppendItem(
                        self.root, "Built-In Plugins", 0)
        self.userroot = self.tcPlugins.AppendItem(
                        self.root, "User Plugins", 0)

        font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.tcPlugins.SetItemFont(self.baseroot, font)
        self.tcPlugins.SetItemFont(self.userroot, font)

    def LoadPlugins(self):
        """Update and load the data for the plugin list control."""

        # Set up the plugins for each plugin entry point of dicompyler
        for n, plugin in enumerate(self.plugins):
            # Skip plugin if it doesn't contain the required dictionary
            # or actually is a proper Python module
            p = plugin['plugin']
            if not hasattr(p, 'pluginProperties'):
                continue
            props = p.pluginProperties()
            if (plugin['location'] == 'base'):
                root = self.baseroot
            else:
                root = self.userroot
            i = self.tcPlugins.AppendItem(root, props['name'], 1)

            if (p.__name__ in self.pluginsDisabled):
                self.tcPlugins.SetItemImage(i, 2)
                self.tcPlugins.SetItemTextColour(i, wx.Colour(169, 169, 169))

            self.tcPlugins.SetItemData(i, n)
            self.tcPlugins.SelectItem(i)
        self.tcPlugins.ExpandAll()
        self.Bind(
            wx.EVT_TREE_ITEM_COLLAPSING,
            self.OnExpandCollapseTree,
            id=XRCID('tcPlugins'))
        self.Bind(
            wx.EVT_TREE_ITEM_EXPANDING,
            self.OnExpandCollapseTree,
            id=XRCID('tcPlugins'))

    def OnSelectTreeItem(self, evt):
        """Update the interface when the selected item has changed."""

        item = evt.GetItem()
        n = self.tcPlugins.GetItemData(item)
        if (n == None):
            self.panelProperties.Hide()
            return
        self.panelProperties.Show()
        plugin = self.plugins[n]
        p = plugin['plugin']
        props = p.pluginProperties()
        self.lblName.SetLabel(props['name'])
        self.lblAuthor.SetLabel(props['author'].replace('&', '&&'))
        self.lblVersionNumber.SetLabel(str(props['version']))
        ptype = props['plugin_type']
        self.lblPluginType.SetLabel(ptype[0].capitalize() + ptype[1:])
        self.lblDescription.SetLabel(props['description'].replace('&', '&&'))

        self.checkEnabled.SetValue(not (p.__name__ in self.pluginsDisabled))

        self.Layout()
        self.panelProperties.Layout()

    def OnSelectRootItem(self, evt):
        """Block the root items from being selected."""

        item = evt.GetItem()
        n = self.tcPlugins.GetItemData(item)
        if (n == None):
            evt.Veto()

    def OnExpandCollapseTree(self, evt):
        """Block the tree from expanding or collapsing."""

        evt.Veto()

    def OnEnablePlugin(self, evt=None):
        """Publish the enabled/disabled state of the plugin."""

        item = self.tcPlugins.GetSelection()
        n = self.tcPlugins.GetItemData(item)
        plugin = self.plugins[n]
        p = plugin['plugin']

        # Set the checkbox to the appropriate state if the event
        # comes from the treeview
        if (evt.EventType == wx.EVT_TREE_ITEM_ACTIVATED.typeId):
            self.checkEnabled.SetValue(not self.checkEnabled.IsChecked())

        if self.checkEnabled.IsChecked():
            self.tcPlugins.SetItemImage(item, 1)
            self.tcPlugins.SetItemTextColour(item, wx.BLACK)
            self.pluginsDisabled.remove(p.__name__)
            logger.debug("%s enabled", p.__name__)
        else:
            self.tcPlugins.SetItemImage(item, 2)
            self.tcPlugins.SetItemTextColour(item, wx.Colour(169, 169, 169))
            self.pluginsDisabled.add(p.__name__)
            logger.debug("%s disabled", p.__name__)

        pub.sendMessage('preferences.updated.value',
                msg={'general.plugins.disabled_list': list(self.pluginsDisabled)})
