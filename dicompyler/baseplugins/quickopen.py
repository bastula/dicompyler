#!/usr/bin/env python
# -*- coding: utf-8 -*-
# quickopen.py
"""dicompyler plugin that allows quick import of DICOM data."""
# Copyright (c) 2012-2017 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/bastula/dicompyler/
#

import logging
logger = logging.getLogger('dicompyler.quickimport')
import wx
from pubsub import pub
from dicompylercore import dicomparser
from dicompyler import util

def pluginProperties():
    """Properties of the plugin."""

    props = {}
    props['name'] = 'DICOM Quick Import'
    props['menuname'] = "&DICOM File Quickly...\tCtrl-Shift-O"
    props['description'] = "Import DICOM data quickly"
    props['author'] = 'Aditya Panchal'
    props['version'] = "0.5.0"
    props['plugin_type'] = 'import'
    props['plugin_version'] = 1
    props['min_dicom'] = []

    return props

class plugin:

    def __init__(self, parent):

        # Initialize the import location via pubsub
        pub.subscribe(self.OnImportPrefsChange, 'general.dicom')
        pub.sendMessage('preferences.requested.values', msg='general.dicom')

        self.parent = parent

        # Setup toolbar controls
        openbmp = wx.Bitmap(util.GetResourcePath('folder_image.png'))
        self.tools = [{'label':"Open Quickly", 'bmp':openbmp,
                            'shortHelp':"Open DICOM File Quickly...",
                            'eventhandler':self.pluginMenu}]

    def OnImportPrefsChange(self, topic, msg):
        """When the import preferences change, update the values."""
        topic = topic.split('.')
        if (topic[1] == 'import_location'):
            self.path = str(msg)
        elif (topic[1] == 'import_location_setting'):
            self.import_location_setting = msg

    def pluginMenu(self, evt):
        """Import DICOM data quickly."""

        dlg = wx.FileDialog(
            self.parent, defaultDir = self.path,
            wildcard="All Files (*.*)|*.*|DICOM File (*.dcm)|*.dcm",
            message="Choose a DICOM File")

        patient = {}
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
            # Try to parse the file if is a DICOM file
            try:
                logger.debug("Reading: %s", filename)
                dp = dicomparser.DicomParser(filename)
            # Otherwise show an error dialog
            except (AttributeError, EOFError, IOError, KeyError):
                logger.info("%s is not a valid DICOM file.", filename)
                dlg = wx.MessageDialog(
                    self.parent, filename + " is not a valid DICOM file.",
                    "Invalid DICOM File", wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            # If this is really a DICOM file, place it in the appropriate bin
            else:
                if (('ImageOrientationPatient' in dp.ds) and not (dp.ds.Modality in ['RTDOSE'])):
                    patient['images'] = []
                    patient['images'].append(dp.ds)
                elif (dp.ds.Modality in ['RTSTRUCT']):
                    patient['rtss'] = dp.ds
                elif (dp.ds.Modality in ['RTPLAN']):
                    patient['rtplan'] = dp.ds
                elif (dp.ds.Modality in ['RTDOSE']):
                    patient['rtdose'] = dp.ds
                else:
                    patient[dp.ds.Modality] = dp.ds
                # Since we have decided to use this location to import from,
                # update the location in the preferences for the next session
                # if the 'import_location_setting' is "Remember Last Used"
                if (self.import_location_setting == "Remember Last Used"):
                    pub.sendMessage('preferences.updated.value',
                        msg={'general.dicom.import_location':dlg.GetDirectory()})
                    pub.sendMessage('preferences.requested.values', msg='general.dicom')
        pub.sendMessage('patient.updated.raw_data', msg=patient)
        dlg.Destroy()
        return
