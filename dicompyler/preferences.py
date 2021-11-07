#!/usr/bin/env python
# -*- coding: utf-8 -*-
# preferences.py
"""Preferences manager for dicompyler."""
# Copyright (c) 2011-2017 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/bastula/dicompyler/

import os
import wx
from wx.xrc import XRCCTRL, XmlResource
from pubsub import pub
from dicompyler import guiutil, util

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
        #self.dlgPreferences = PreferencesDialog(parent,name=name)
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
        if self.dlgPreferences:
            
            self.dlgPreferences.Destroy()

    def Show(self):
        """Show the preferences dialog with the given preferences."""

        # If the pref dialog has never been shown, load the values and show it
        if not self.dlgPreferences.IsShown():
            self.dlgPreferences.LoadPreferences(self.preftemplate, self.values)
            self.dlgPreferences.Hide()
        # Otherwise, hide the dialog and redisplay it to bring it to the front
        else:
            self.dlgPreferences.Hide()
        self.dlgPreferences.Show()

    def SetPreferenceTemplate(self, msg):
        """Set the template that the preferences will be shown in the dialog."""

        self.preftemplate = msg
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

        self.values = msg
        with open(self.filename, mode='w') as f:
            json.dump(self.values, f, sort_keys=True, indent=4)

    def GetPreferenceValue(self, msg):
        """Publish the requested value for a single preference setting."""

        query = msg.split('.')
        v = self.values
        if query[0] in v and query[1] in v[query[0]] and query[2] in v[query[0]][query[1]]:
            pub.sendMessage(msg, topic=msg, msg=v[query[0]][query[1]][query[2]])

    def GetPreferenceValues(self, msg):
        """Publish the requested values for preference setting group."""

        query = msg.split('.')
        v = self.values
        if query[0] in v and query[1] in v[query[0]]:
            for setting, value in list(v[query[0]][query[1]].items()):
                message = msg + '.' + setting
                pub.sendMessage(message, topic='.'.join(['general',setting]), msg=value)

    def SetPreferenceValue(self, msg):
        """Set the preference value for the given preference setting."""

        #Using list() may break threading.  
        #See https://blog.labix.org/2008/06/27/watch-out-for-listdictkeys-in-python-3
        SetValue(self.values, list(msg.keys())[0], list(msg.values())[0])
        pub.sendMessage('preferences.updated.values', msg=self.values)
        pub.sendMessage(list(msg.keys())[0], topic=list(msg.keys())[0], msg=list(msg.values())[0]) 

############################## Preferences Dialog ##############################

class PreferencesDialog(wx.Dialog):
    """Dialog to display and change preferences."""

    def __init__(self):      
        wx.Dialog.__init__(self)

    def Init(self, name = None, appname = ""):
        """Method called after the panel has been initialized."""

        # Hide the close button on Mac
        if guiutil.IsMac():
            XRCCTRL(self, 'wxID_OK').Hide()
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
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnClose)
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_OK)

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
            panel = self.CreatePreferencePanel(list(template.values())[0])
            self.notebook.AddPage(panel, list(template.keys())[0])

    def CreatePreferencePanel(self, prefpaneldata):
        """Create a preference panel for the given data."""

        panel = wx.Panel(self.notebook, -1)
        border = wx.BoxSizer(wx.VERTICAL)
        show_restart = False

        for group in prefpaneldata:
            # Create a header for each group of settings
            bsizer = wx.BoxSizer(wx.VERTICAL)
            bsizer.Add((0,5))
            hsizer = wx.BoxSizer(wx.HORIZONTAL)
            hsizer.Add((12, 0))
            h = wx.StaticText(panel, -1, list(group.keys())[0])
            font = h.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            h.SetFont(font)
            hsizer.Add(h)
            bsizer.Add(hsizer)
            bsizer.Add((0,7))
            # Create a FlexGridSizer to contain the group of settings
            fgsizer = wx.FlexGridSizer(len(list(group.values())[0]), 4, 10, 4)
            fgsizer.AddGrowableCol(2, 1)
            # Create controls for each setting
            for setting in list(group.values())[0]:
                fgsizer.Add((24, 0))
                # Show the restart asterisk for this setting if required
                restart = str('*' if 'restart' in setting else '')
                if ('restart' in setting) and (setting['restart'] == True):
                    show_restart = True
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
                # If this is a checkbox setting
                elif (setting['type'] == 'checkbox'):
                    c = wx.CheckBox(panel, -1, setting['name']+restart)
                    c.SetValue(value)
                    sizer.Add(c, 0, wx.ALIGN_CENTER)
                    # Remove the label preceding the checkbox
                    t = c.GetPrevSibling()
                    t.SetLabel('')
                    # Adjust the sizer preceding the label
                    fgsizer.GetItem(0).AssignSpacer((20,0))
                    # Add control to the callback dict
                    self.callbackdict[c] = setting['callback']
                    self.Bind(wx.EVT_CHECKBOX, self.OnUpdateCheckbox, c)
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
        pub.sendMessage(self.callbackdict[c], topic=self.callbackdict[c], msg=evt.GetString())
        SetValue(self.values, self.callbackdict[c], evt.GetString())

    def OnUpdateCheckbox(self, evt):
        """Publish the updated checkbox when the value changes."""

        c = evt.GetEventObject()
        pub.sendMessage(self.callbackdict[c], topic=self.callbackdict[c], msg=evt.IsChecked())
        SetValue(self.values, self.callbackdict[c], evt.IsChecked())

    def OnUpdateSlider(self, evt):
        """Publish the updated number when the slider value changes."""

        s = evt.GetEventObject()
        # Update the associated label with the new number
        t = self.FindWindowById(s.NextControlId(s.GetId()))
        t.SetLabel(str(s.GetValue()))
        pub.sendMessage(self.callbackdict[s], topic=self.callbackdict[s], msg=s.GetValue())
        SetValue(self.values, self.callbackdict[s], s.GetValue())

    def OnUpdateDirectory(self, evt):
        """Publish the updated directory when the value changes."""

        b = evt.GetEventObject()
        # Get the the label associated with the browse button
        t = b.GetPrevSibling()
        dlg = wx.DirDialog(self, defaultPath = t.GetValue())

        if dlg.ShowModal() == wx.ID_OK:
            # Update the associated label with the new directory
            d = str(dlg.GetPath())
            t.SetValue(d)
            pub.sendMessage(self.callbackdict[b], topic=self.callbackdict[b], msg=d)
            SetValue(self.values, self.callbackdict[b], d)
        dlg.Destroy()

    def OnClose(self, evt):
        """Publish the updated preference values when closing the dialog."""

        pub.sendMessage('preferences.updated.values', msg=self.values)
        if self:
            self.Hide()

############################ Get/Set Value Functions ###########################

def GetValue(values, setting):
    """Get the saved setting value."""

    # Look for the saved value and return it if it exists
    query = setting['callback'].split('.')
    value = setting['default']
    if query[0] in values and query[1] in values[query[0]] and query[2] in values[query[0]][query[1]]:
        value = values[query[0]][query[1]][query[2]]
    # Otherwise return the default value
    return value

def SetValue(values, setting, value):
    """Save the new setting value."""

    # Look if a prior value exists and replace it
    query = setting.split('.')
    if query[0] in values:
        if query[1] in values[query[0]]:
            values[query[0]][query[1]][query[2]] = value
        else:
            values[query[0]].update({query[1]:{query[2]:value}})
    else:
        values[query[0]] = {query[1]:{query[2]:value}}

############################### Test Preferences ###############################

def main():

    import tempfile, os
    import wx
    from pubsub import pub

    app = wx.App(False)

    t = tempfile.NamedTemporaryFile(delete=False)
    sp = wx.StandardPaths.Get()

    # Create a frame as a parent for the preferences dialog
    frame = wx.Frame(None, wx.ID_ANY, "Preferences Test")
    frame.Centre()
    frame.Show(True)
    app.SetTopWindow(frame)

    filename = t.name
    frame.prefmgr = PreferencesManager(parent = frame, appname = 'preftest',
                                       filename=filename)

    # Set up the preferences template
    grp1template = [
        {'Panel 1 Preference Group 1':
            [{'name':'Choice Setting',
             'type':'choice',
           'values':['Choice 1', 'Choice 2', 'Choice 3'],
          'default':'Choice 2',
         'callback':'panel1.prefgrp1.choice_setting'},
            {'name':'Directory setting',
             'type':'directory',
          'default':str(sp.GetDocumentsDir()),
         'callback':'panel1.prefgrp1.directory_setting'}]
        },
        {'Panel 1 Preference Group 2':
            [{'name':'Range Setting',
             'type':'range',
           'values':[0, 100],
          'default':50,
            'units':'%',
         'callback':'panel1.prefgrp2.range_setting'}]
        }]
    grp2template = [
        {'Panel 2 Preference Group 1':
           [{'name':'Range Setting',
             'type':'range',
           'values':[0, 100],
          'default':50,
            'units':'%',
         'callback':'panel2.prefgrp1.range_setting',
          'restart':True}]
        },
        {'Panel 2 Preference Group 2':
           [{'name':'Directory setting',
             'type':'directory',
          'default':str(sp.GetUserDataDir()),
         'callback':'panel2.prefgrp2.directory_setting'},
            {'name':'Choice Setting',
             'type':'choice',
           'values':['Choice 1', 'Choice 2', 'Choice 3'],
          'default':'Choice 2',
         'callback':'panel2.prefgrp2.choice_setting'}]
        }]
    preftemplate = [{'Panel 1':grp1template}, {'Panel 2':grp2template}]

    def print_template_value(msg):
        """Print the received template message."""
        print(msg.topic, msg)

    # Subscribe the template value printer to each set of preferences
    pub.subscribe(print_template_value, 'panel1')
    pub.subscribe(print_template_value, 'panel2')

    # Notify the preferences manager that a pref template is available
    pub.sendMessage('preferences.updated.template', msg=preftemplate)

    frame.prefmgr.Show()
    app.MainLoop()

    # Print the results of the preferences
    with open(filename, mode='r') as f:
        for line in f:
            print(line)

    try:
        os.remove(filename)
    except WindowsError:
        print('\nCould not delete: '+filename+'. Please delete it manually.')

if __name__ == '__main__':
    main()
