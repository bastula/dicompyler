#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
""" Several gui utility functions that don't really belong anywhere"""

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
