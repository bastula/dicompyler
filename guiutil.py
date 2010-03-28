#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# guiutil.py
"""Several GUI utility functions that don't really belong anywhere."""
# Copyright (c) 2009 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

import util
import wx
from wx.xrc import *

def IsMSWindows():
    """Are we running on Windows?

    @rtype: Bool"""
    return wx.Platform=='__WXMSW__'

def IsGtk():
    """Are we running on GTK (Linux)

    @rtype: Bool"""
    return wx.Platform=='__WXGTK__'

def IsMac():
    """Are we running on Mac

    @rtype: Bool"""
    return wx.Platform=='__WXMAC__'

def GetItemsList(wxCtrl):
    # Return the list of values stored in a wxCtrlWithItems
    list = []
    if not (wxCtrl.IsEmpty()):
        for i in range(wxCtrl.GetCount()):
            list.append(wxCtrl.GetString(i))
    return list

def SetItemsList(wxCtrl, list = [], data = []):
    # Set the wxCtrlWithItems to the given list and store the data in the item
    wxCtrl.Clear()
    i = 0
    for item in list:
        wxCtrl.Append(item)
        # if no data has been given, no need to set the client data
        if not (data == []):
            wxCtrl.SetClientData(i, data[i])
        i = i + 1
    if not (wxCtrl.IsEmpty()):
            wxCtrl.SetSelection(0)

def get_data_dir():
    """Returns the data location for the application."""

    sp = wx.StandardPaths.Get()
    return wx.StandardPaths.GetUserLocalDataDir(sp)

def get_icon():
    """Returns the icon for the application."""

    icon = None
    if IsMSWindows():
        if util.main_is_frozen():
            import sys
            exeName = sys.executable
            icon = wx.Icon(exeName, wx.BITMAP_TYPE_ICO)
        else:
            icon = wx.Icon(util.GetResourcePath('dicompyler.ico'), wx.BITMAP_TYPE_ICO)
    elif IsGtk():
        icon = wx.Icon(util.GetResourcePath('dicompyler_icon11_16.png'), wx.BITMAP_TYPE_PNG)

    return icon

def get_progress_dialog(parent):
    """Function to load the progress dialog."""

    # Load the XRC file for our gui resources
    res = XmlResource(util.GetResourcePath('guiutil.xrc'))

    dialogProgress = res.LoadDialog(parent, 'ProgressDialog')
    dialogProgress.Init(res)

    return dialogProgress

class ProgressDialog(wx.Dialog):
    """Dialog to show progress for certain long-running events."""

    def __init__(self):
        pre = wx.PreDialog()
        # the Create step is done by XRC.
        self.PostCreate(pre)
    
    def Init(self, res, title=None):
        """Method called after the dialog has been initialized."""

        # Initialize controls
        self.lblProgressLabel = XRCCTRL(self, 'lblProgressLabel')
        self.lblProgress = XRCCTRL(self, 'lblProgress')
        self.gaugeProgress = XRCCTRL(self, 'gaugeProgress')
        self.lblProgressPercent = XRCCTRL(self, 'lblProgressPercent')

    def OnUpdateProgress(self, num, length, message):
        """Update the process interface elements."""

        if not length:
            percentDone = 0
        else:
            percentDone = int(100 * (num+1) / length)

        self.gaugeProgress.SetValue(percentDone)
        self.lblProgressPercent.SetLabel(str(percentDone))
        self.lblProgress.SetLabel(message)

        # End the dialog since we are done with the import process
        if (message == 'Importing patient complete.'):
            self.EndModal(wx.ID_OK)