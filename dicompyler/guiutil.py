#!/usr/bin/env python
# -*- coding: utf-8 -*-
# guiutil.py
"""Several GUI utility functions that don't really belong anywhere."""
# Copyright (c) 2009-2017 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/bastula/dicompyler/

from dicompyler import util
import wx
from wx.xrc import XmlResource, XRCCTRL, XRCID
from wx.lib.pubsub import pub

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

def convert_pil_to_wx(pil, alpha=True):
    """ Convert a PIL Image into a wx.Image.
        Code taken from Dave Witten's imViewer-Simple.py in pydicom contrib."""
    if alpha:
        image = wx.Image(pil.size[0], pil.size[1], clear=True)
        image.SetData(pil.convert("RGB").tobytes())
        image.SetAlpha(pil.convert("RGBA").tobytes()[3::4])
    else:
        image = wx.Image(pil.size[0], pil.size[1], clear=True)
        new_image = pil.convert('RGB')
        data = new_image.tostring()
        image.SetData(data)
    return image

def get_progress_dialog(parent, title="Loading..."):
    """Function to load the progress dialog."""

    # Load the XRC file for our gui resources
    res = XmlResource(util.GetResourcePath('guiutil.xrc'))

    dialogProgress = res.LoadDialog(parent, 'ProgressDialog')
    dialogProgress.Init(res, title)

    return dialogProgress

def adjust_control(control):
    """Adjust the control and font size on the Mac."""

    if IsMac():
        font = control.GetFont()
        font.SetPointSize(11)
        control.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)
        control.SetFont(font)

class ProgressDialog(wx.Dialog):
    """Dialog to show progress for certain long-running events."""

    def __init__(self):
        wx.Dialog.__init__(self)
    
    def Init(self, res, title=None):
        """Method called after the dialog has been initialized."""

        # Initialize controls
        self.SetTitle(title)
        self.lblProgressLabel = XRCCTRL(self, 'lblProgressLabel')
        self.lblProgress = XRCCTRL(self, 'lblProgress')
        self.gaugeProgress = XRCCTRL(self, 'gaugeProgress')
        self.lblProgressPercent = XRCCTRL(self, 'lblProgressPercent')

    def OnUpdateProgress(self, num, length, message=''):
        """Update the process interface elements."""

        if not length:
            percentDone = 0
        else:
            percentDone = int(100 * (num) / length)

        self.gaugeProgress.SetValue(percentDone)
        self.lblProgressPercent.SetLabel(str(percentDone))
        self.lblProgress.SetLabel(message)

        # End the dialog since we are done with the import process
        if (message == 'Done'):
            self.EndModal(wx.ID_OK)

class ColorCheckListBox(wx.ScrolledWindow):
    """Control similar to a wx.CheckListBox with additional color indication."""

    def __init__(self, parent, pubsubname=''):
        wx.ScrolledWindow.__init__(self, parent, -1, style=wx.SUNKEN_BORDER)

        # Initialize variables
        self.pubsubname = pubsubname

        # Setup the layout for the frame
        self.grid = wx.BoxSizer(wx.VERTICAL)

        # Setup the panel background color and layout the controls
        self.SetBackgroundColour(wx.WHITE)
        self.SetSizer(self.grid)
        self.Layout()

        self.Clear()

    def Layout(self):
        self.SetScrollbars(20,20,50,50)
        super(ColorCheckListBox,self).Layout()

    def Append(self, item, data=None, color=None, refresh=True):
        """Add an item to the control."""

        ccb = ColorCheckBox(self, item, data, color, self.pubsubname)
        self.items.append(ccb)
        self.grid.Add(ccb, 0, flag=wx.ALIGN_LEFT, border=4)
        self.grid.Add((0,3), 0)
        if refresh:
            self.Layout()

    def Clear(self):
        """Removes all items from the control."""

        self.items = []
        self.grid.Clear(True)
        self.grid.Add((0,3), 0)
        self.Layout()

class ColorCheckBox(wx.Panel):
    """Control with a checkbox and a color indicator."""

    def __init__(self, parent, item, data=None, color=None, pubsubname=''):
        wx.Panel.__init__(self, parent, -1)

        # Initialize variables
        self.item = item
        self.data = data
        self.pubsubname = pubsubname

        # Initialize the controls
        self.colorbox = ColorBox(self, color)
        self.checkbox = wx.CheckBox(self, -1, item)

        # Setup the layout for the frame
        grid = wx.BoxSizer(wx.HORIZONTAL)
        grid.Add((3,0), 0)
        grid.Add(self.colorbox, 0, flag=wx.ALIGN_CENTRE)
        grid.Add((5,0), 0)
        grid.Add(self.checkbox, 1, flag=wx.EXPAND|wx.ALL|wx.ALIGN_CENTRE)

        # Decrease the font size on Mac
        if IsMac():
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
            font.SetPointSize(10)
            self.checkbox.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)
            self.checkbox.SetFont(font)

        # Setup the panel background color and layout the controls
        self.SetBackgroundColour(wx.WHITE)
        self.SetSizer(grid)
        self.Layout()

        # Bind ui events to the proper methods
        self.Bind(wx.EVT_CHECKBOX, self.OnCheck)

    def OnCheck(self, evt):
        """Send a message via pubsub if the checkbox has been checked."""

        message = {'item':self.item, 'data':self.data,
                'color':self.colorbox.GetBackgroundColour()}
        if evt.IsChecked():
            pub.sendMessage('colorcheckbox.checked.' + self.pubsubname, msg=message)
        else:
            pub.sendMessage('colorcheckbox.unchecked.' + self.pubsubname, msg=message)

class ColorBox(wx.Window):
    """Control that shows and stores a color."""

    def __init__(self, parent, color=[]):
        wx.Window.__init__(self, parent, -1)
        self.SetMinSize((16,16))
        col = []
        for val in color:
            col.append(int(val))
        self.SetBackgroundColour(tuple(col))

        # Bind ui events to the proper methods
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)

    def OnFocus(self, evt):
        """Ignore the focus event via keyboard."""

        self.Navigate()
