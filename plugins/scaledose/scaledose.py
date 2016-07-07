#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# scaledose.py
"""dicompyler plugin that scales DICOM RT Dose data."""
# Copyright (c) 2010-2012 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#

import wx
from wx.xrc import XmlResource, XRCCTRL, XRCID
from wx.lib.pubsub import Publisher as pub
import os.path, threading
from dicompyler import guiutil, util

def pluginProperties():
    """Properties of the plugin."""

    props = {}
    props['name'] = 'Scale Dose'
    props['description'] = "Scales DICOM RT dose data"
    props['author'] = 'Aditya Panchal'
    props['version'] = 0.2
    props['plugin_type'] = 'menu'
    props['plugin_version'] = 1
    props['min_dicom'] = ['rtplan', 'rtdose']
    props['recommended_dicom'] = ['rtplan', 'rtdose']

    return props

class plugin:

    def __init__(self, parent):

        self.parent = parent

        # Set up pubsub
        pub.subscribe(self.OnUpdatePatient, 'patient.updated.raw_data')

        # Load the XRC file for our gui resources
        xrc = os.path.join(os.path.dirname(__file__), 'scaledose.xrc')
        self.res = XmlResource(xrc)

    def OnUpdatePatient(self, msg):
        """Update and load the patient data."""

        self.data = msg.data

    def pluginMenu(self, evt):
        """Scale DICOM RT dose data."""

        dlgScaleDose = self.res.LoadDialog(self.parent, "ScaleDoseDialog")
        dlgScaleDose.Init(self.data['rxdose'])

        if dlgScaleDose.ShowModal() == wx.ID_OK:
            oldRxDose = dlgScaleDose.oldRxDose
            newRxDose = dlgScaleDose.newRxDose

            # Initialize and start the scale dose thread
            self.t=threading.Thread(target=self.ScaleDoseDataThread,
                args=(self.data, oldRxDose, newRxDose, self.UpdateData))
            self.t.start()

        else:
            pass
        dlgScaleDose.Destroy()
        return

    def ScaleDoseDataThread(self, data, oldRxDose, newRxDose, finishedFunc):
        """Scale the DICOM RT dose data."""

        dosescale = float(newRxDose) / float(oldRxDose)
        # Scale the Rx dose
        data['rxdose'] = int(data['rxdose'] * dosescale)
        rtdose = data['rtdose']
        # Scale the Dose grid data
        rtdose.DoseGridScaling = rtdose.DoseGridScaling * dosescale
        # Scale the DVH data
        if "DVHs" in rtdose:
            for item in rtdose.DVHs:
                item.DVHDoseScaling = item.DVHDoseScaling * dosescale
        wx.CallAfter(finishedFunc, data)

    def UpdateData(self, data, ):
        """Publish the updated patient data."""

        pub.sendMessage('patient.updated.raw_data', data)

class ScaleDoseDialog(wx.Dialog):
    """Dialog that shows the options to scale the DICOM RT dose data."""

    def __init__(self):
        pre = wx.PreDialog()
        # the Create step is done by XRC.
        self.PostCreate(pre)

    def Init(self, rxdose):
        """Method called after the dialog has been initialized."""

        # Set window icon
        if not guiutil.IsMac():
            self.SetIcon(guiutil.get_icon())

        # Initialize controls
        self.txtOriginalRxDose = XRCCTRL(self, 'txtOriginalRxDose')
        self.txtNewRxDose = XRCCTRL(self, 'txtNewRxDose')

        # Bind interface events to the proper methods
        wx.EVT_BUTTON(self, wx.ID_OK, self.OnOK)

        # Pre-select the text on the text controls due to a Mac OS X bug
        self.txtOriginalRxDose.SetSelection(-1, -1)
        self.txtNewRxDose.SetSelection(-1, -1)

        # Initialize variables
        self.txtOriginalRxDose.SetValue(str(int(rxdose)))
        self.txtNewRxDose.SetValue(str(int(rxdose)/2))

    def OnOK(self, evt):
        """Return the options from the anonymize data dialog."""

        self.oldRxDose = int(self.txtOriginalRxDose.GetValue())
        self.newRxDose  = int(self.txtNewRxDose.GetValue())

        self.EndModal(wx.ID_OK)
