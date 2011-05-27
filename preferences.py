#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# preferences.py
"""Preferences manager for dicompyler."""
# Copyright (c) 2011 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

import os
import wx
from wx.xrc import *
from wx.lib.pubsub import Publisher as pub
import guiutil, util

try:
    # Only works on Python 2.6 and above
    import json
except ImportError:
    # Otherwise try simplejson: http://github.com/simplejson/simplejson
    import simplejson as json

class PreferencesManager():
    """Class to access preferences and set up the preferences dialog."""

    def __init__(self, parent, name = None, appname = "the application",
                 filename='preferences.txt'):

        # Load the XRC file for our gui resources
        res = XmlResource(util.GetResourcePath('preferences.xrc'))
        self.dlgPreferences = res.LoadDialog(None, "PreferencesDialog")
        self.dlgPreferences.Init(name, appname)

        # Setup internal pubsub methods
        pub.subscribe(self.SetPreferenceTemplate, 'preferences.updated.template')
        pub.subscribe(self.SavePreferenceValues, 'preferences.updated.values')

        # Setup user pubsub methods
        pub.subscribe(self.GetPreferenceValue, 'preferences.requested.value')
        pub.subscribe(self.GetPreferenceValues, 'preferences.requested.values')
        pub.subscribe(self.SetPreferenceValue, 'preferences.updated.value')

        # Initialize variables
        self.preftemplate = []
        self.values = {}
        self.filename = os.path.join(guiutil.get_data_dir(), filename)
        self.LoadPreferenceValues()

    def __del__(self):

        # Destroy the dialog when the preferences manager object is deleted
        self.dlgPreferences.Destroy()

    def Show(self):
        """Show the preferences dialog with the given preferences."""

        # If the pref dialog has never been shown, load the values and show it
        if not self.dlgPreferences.IsShown():
            self.dlgPreferences.LoadPreferences(self.preftemplate, self.values)
            self.dlgPreferences.Show()
        # Otherwise, hide the dialog and redisplay it to bring it to the front
        else:
            self.dlgPreferences.Hide()
            self.dlgPreferences.Show()

    def SetPreferenceTemplate(self, msg):
        """Set the template that the preferences will be shown in the dialog."""

        self.preftemplate = msg.data
        self.dlgPreferences.LoadPreferences(self.preftemplate, self.values)

    def LoadPreferenceValues(self):
        """Load the saved preference values from disk."""

        if os.path.isfile(self.filename):
            with open(self.filename, mode='r') as f:
                try:
                    self.values = json.load(f)
                except ValueError:
                    self.values = {}
        else:
            self.values = {}

    def SavePreferenceValues(self, msg):
        """Save the preference values to disk after the dialog is closed."""

        self.values = msg.data
        with open(self.filename, mode='w') as f:
            json.dump(self.values, f, sort_keys=True, indent=4)

    def GetPreferenceValue(self, msg):
        """Publish the requested value for a single preference setting."""

        query = msg.data.split('.')
        v = self.values
        if v.has_key(query[0]):
            if v[query[0]].has_key(query[1]):
                if v[query[0]][query[1]].has_key(query[2]):
                    pub.sendMessage(msg.data, v[query[0]][query[1]][query[2]])

    def GetPreferenceValues(self, msg):
        """Publish the requested values for preference setting group."""

        query = msg.data.split('.')
        v = self.values
        if v.has_key(query[0]):
            if v[query[0]].has_key(query[1]):
                for setting, value in v[query[0]][query[1]].iteritems():
                    message = msg.data + '.' + setting
                    pub.sendMessage(message, value)

    def SetPreferenceValue(self, msg):
        """Set the preference value for the given preference setting."""

        SetValue(self.values, msg.data.keys()[0], msg.data.values()[0])
        pub.sendMessage('preferences.updated.values', self.values)

############################## Preferences Dialog ##############################

class PreferencesDialog(wx.Dialog):
    """Dialog to display and change preferences."""

    def __init__(self):
        pre = wx.PreDialog()
        # the Create step is done by XRC.
        self.PostCreate(pre)

    def Init(self, name = None, appname = ""):
        """Method called after the panel has been initialized."""

        # Hide the close button on Mac
        if guiutil.IsMac():
            XRCCTRL(self, 'wxID_CANCEL').Hide()
        # Set window icon
        else:
            self.SetIcon(guiutil.get_icon())

        # Set the dialog title
        if name:
            self.SetTitle(name)

        # Initialize controls
        self.notebook = XRCCTRL(self, 'notebook')

        # Modify the control and font size on Mac
        for child in self.GetChildren():
            guiutil.adjust_control(child)

        # Bind ui events to the proper methods
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Initialize variables
        self.preftemplate = []
        self.values = {}
        self.appname = appname

    def LoadPreferences(self, preftemplate, values):
        """Update and load the data for the preferences notebook control."""

        self.preftemplate = preftemplate
        self.values = values

        # Delete and reset all the previous preference panels
        self.notebook.DeleteAllPages()
        self.callbackdict = {}

        # Add each preference panel to the notebook
        for template in self.preftemplate:
            panel = self.CreatePreferencePanel(template.values()[0])
            self.notebook.AddPage(panel, template.keys()[0])

    def CreatePreferencePanel(self, prefpaneldata):
        """Create a preference panel for the given data."""

        panel = wx.Panel(self.notebook, -1)
        border = wx.BoxSizer(wx.VERTICAL)

        for group in prefpaneldata:
            # Create a header for each group of settings
            bsizer = wx.BoxSizer(wx.VERTICAL)
            bsizer.Add((0,5))
            hsizer = wx.BoxSizer(wx.HORIZONTAL)
            hsizer.Add((12, 0))
            h = wx.StaticText(panel, -1, group.keys()[0])
            font = h.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            h.SetFont(font)
            hsizer.Add(h)
            bsizer.Add(hsizer)
            bsizer.Add((0,7))
            # Create a FlexGridSizer to contain the group of settings
            fgsizer = wx.FlexGridSizer(len(group.values()[0]), 4, 10, 4)
            fgsizer.AddGrowableCol(2, 1)
            show_restart = False
            # Create controls for each setting
            for setting in group.values()[0]:
                fgsizer.Add((24, 0))
                # Show the restart asterisk for this setting if required
                restart = str('*' if 'restart' in setting else '')
                if ('restart' in setting):
                    if (setting['restart'] == True):
                        restart = '*'
                        show_restart = True
                    else:
                        restart = ''
                t = wx.StaticText(panel, -1, setting['name']+restart+':',
                    style=wx.ALIGN_RIGHT)
                fgsizer.Add(t, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT)
                sizer = wx.BoxSizer(wx.HORIZONTAL)

                # Get the setting value
                value = GetValue(self.values, setting)
                # Save the setting value in case it hasn't been saved previously
                SetValue(self.values, setting['callback'], value)

                # If this is a choice setting
                if (setting['type'] == 'choice'):
                    c = wx.Choice(panel, -1, choices=setting['values'])
                    c.SetStringSelection(value)
                    sizer.Add(c, 0, wx.ALIGN_CENTER)
                    # Add control to the callback dict
                    self.callbackdict[c] = setting['callback']
                    self.Bind(wx.EVT_CHOICE, self.OnUpdateChoice, c)
                # If this is a range setting
                elif (setting['type'] == 'range'):
                    s = wx.Slider(panel, -1, value,
                        setting['values'][0], setting['values'][1],
                        size=(120, -1), style=wx.SL_HORIZONTAL)
                    sizer.Add(s, 0, wx.ALIGN_CENTER)
                    t = wx.StaticText(panel, -1, str(value))
                    sizer.Add((3, 0))
                    sizer.Add(t, 0, wx.ALIGN_CENTER)
                    sizer.Add((6, 0))
                    t = wx.StaticText(panel, -1, setting['units'])
                    sizer.Add(t, 0, wx.ALIGN_CENTER)
                    # Add control to the callback dict
                    self.callbackdict[s] = setting['callback']
                    self.Bind(wx.EVT_COMMAND_SCROLL_THUMBTRACK, self.OnUpdateSlider, s)
                    self.Bind(wx.EVT_COMMAND_SCROLL_CHANGED, self.OnUpdateSlider, s)
                # If this is a directory location setting
                elif (setting['type'] == 'directory'):
                    # Check if the value is a valid directory,
                    # otherwise set it to the default directory
                    if not os.path.isdir(value):
                        value = setting['default']
                        SetValue(self.values, setting['callback'], value)
                    t = wx.TextCtrl(panel, -1, value, style=wx.TE_READONLY)
                    sizer.Add(t, 1, wx.ALIGN_CENTER)
                    sizer.Add((5, 0))
                    b = wx.Button(panel, -1, "Browse...")
                    sizer.Add(b, 0, wx.ALIGN_CENTER)
                    # Add control to the callback dict
                    self.callbackdict[b] = setting['callback']
                    self.Bind(wx.EVT_BUTTON, self.OnUpdateDirectory, b)
                # Modify the control and font size on Mac
                for child in panel.GetChildren():
                    guiutil.adjust_control(child)
                fgsizer.Add(sizer, 1, wx.EXPAND|wx.ALL)
                fgsizer.Add((12, 0))
            bsizer.Add(fgsizer, 0, wx.EXPAND|wx.ALL)
            border.Add(bsizer, 0, wx.EXPAND|wx.ALL, 2)
        border.Add((60, 20), 0, wx.EXPAND|wx.ALL)
        # Show the restart text for this group if required for >= 1 setting
        if show_restart:
            r = wx.StaticText(panel, -1,
                              '* Restart ' + self.appname + \
                              ' for this setting to take effect.',
                              style=wx.ALIGN_CENTER)
            font = r.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            r.SetFont(font)
            border.Add((0,0), 1, wx.EXPAND|wx.ALL)
            rhsizer = wx.BoxSizer(wx.HORIZONTAL)
            rhsizer.Add((0,0), 1, wx.EXPAND|wx.ALL)
            rhsizer.Add(r)
            rhsizer.Add((0,0), 1, wx.EXPAND|wx.ALL)
            border.Add(rhsizer, 0, wx.EXPAND|wx.ALL)
            border.Add((0,5))
        panel.SetSizer(border)

        return panel

    def OnUpdateChoice(self, evt):
        """Publish the updated choice when the value changes."""

        c = evt.GetEventObject()
        pub.sendMessage(self.callbackdict[c], evt.GetString())
        SetValue(self.values, self.callbackdict[c], evt.GetString())

    def OnUpdateSlider(self, evt):
        """Publish the updated number when the slider value changes."""

        s = evt.GetEventObject()
        # Update the associated label with the new number
        t = self.FindWindowById(s.NextControlId(s.GetId()))
        t.SetLabel(str(s.GetValue()))
        pub.sendMessage(self.callbackdict[s], s.GetValue())
        SetValue(self.values, self.callbackdict[s], s.GetValue())

    def OnUpdateDirectory(self, evt):
        """Publish the updated directory when the value changes."""

        b = evt.GetEventObject()
        # Get the the label associated with the browse button
        t = self.FindWindowById(b.PrevControlId(b.GetId()))
        print t.GetValue()
        dlg = wx.DirDialog(self, defaultPath = t.GetValue())

        if dlg.ShowModal() == wx.ID_OK:
            # Update the associated label with the new directory
            d = unicode(dlg.GetPath())
            t.SetValue(d)
            pub.sendMessage(self.callbackdict[b], d)
            SetValue(self.values, self.callbackdict[b], d)
        dlg.Destroy()

    def OnClose(self, evt):
        """Publish the updated preference values when closing the dialog."""

        pub.sendMessage('preferences.updated.values', self.values)
        self.Hide()

############################ Get/Set Value Functions ###########################

def GetValue(values, setting):
    """Get the saved setting value."""

    # Look for the saved value and return it if it exists
    query = setting['callback'].split('.')
    value = setting['default']
    if values.has_key(query[0]):
        if values[query[0]].has_key(query[1]):
            if values[query[0]][query[1]].has_key(query[2]):
                value = values[query[0]][query[1]][query[2]]
    # Otherwise return the default value
    return value

def SetValue(values, setting, value):
    """Save the new setting value."""

    # Look if a prior value exists and replace it
    query = setting.split('.')
    if values.has_key(query[0]):
        if values[query[0]].has_key(query[1]):
            values[query[0]][query[1]][query[2]] = value
        else:
            values[query[0]].update({query[1]:{query[2]:value}})
    else:
        values[query[0]] = {query[1]:{query[2]:value}}
