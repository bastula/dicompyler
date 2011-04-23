#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# anonymize.py
"""dicompyler plugin that anonymizes DICOM / DICOM RT data."""
# Copyright (c) 2010 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#

import wx
from wx.xrc import XmlResource, XRCCTRL, XRCID
from wx.lib.pubsub import Publisher as pub
import os, threading
import guiutil, util

def pluginProperties():
    """Properties of the plugin."""

    props = {}
    props['name'] = 'Anonymize'
    props['menuname'] = "as Anonymized DICOM"
    props['description'] = "Anonymizes DICOM / DICOM RT data"
    props['author'] = 'Aditya Panchal'
    props['version'] = 0.4
    props['plugin_type'] = 'export'
    props['plugin_version'] = 1
    props['min_dicom'] = []
    props['recommended_dicom'] = ['images', 'rtss', 'rtplan', 'rtdose']

    return props

class plugin:

    def __init__(self, parent):

        self.parent = parent

        # Set up pubsub
        pub.subscribe(self.OnUpdatePatient, 'patient.updated.raw_data')

        # Load the XRC file for our gui resources
        self.res = XmlResource(util.GetBasePluginsPath('anonymize.xrc'))

    def OnUpdatePatient(self, msg):
        """Update and load the patient data."""

        self.data = msg.data

    def pluginMenu(self, evt):
        """Anonymize DICOM / DICOM RT data."""

        dlgAnonymize = self.res.LoadDialog(self.parent, "AnonymizeDialog")
        dlgAnonymize.Init()

        if dlgAnonymize.ShowModal() == wx.ID_OK:
            path = dlgAnonymize.path
            name = str(dlgAnonymize.name)
            patientid = str(dlgAnonymize.patientid)
            privatetags = dlgAnonymize.privatetags

            # If the path doesn't exist, create it
            if not os.path.exists(path):
                os.mkdir(path)

            # Initialize the progress dialog
            dlgProgress = guiutil.get_progress_dialog(
                wx.GetApp().GetTopWindow(),
                "Anonymizing DICOM data...")
            # Initialize and start the anonymization thread
            self.t=threading.Thread(target=self.AnonymizeDataThread,
                args=(self.data, path, name, patientid, privatetags,
                dlgProgress.OnUpdateProgress))
            self.t.start()
            # Show the progress dialog
            dlgProgress.ShowModal()
            dlgProgress.Destroy()

        else:
            pass
        dlgAnonymize.Destroy()
        return

    def AnonymizeDataThread(self, data, path, name, patientid, privatetags,
            progressFunc):
        """Anonmyize and save each DICOM / DICOM RT file."""

        length = 0
        for key in ['rtss', 'rtplan', 'rtdose']:
            if data.has_key(key):
                length = length + 1
        if data.has_key('images'):
            length = length + len(data['images'])

        i = 1
        if data.has_key('rtss'):
            rtss = data['rtss']
            wx.CallAfter(progressFunc, i, length,
                'Anonymizing file ' + str(i) + ' of ' + str(length))
            self.updateCommonElements(rtss, name, patientid, privatetags)
            self.updateElement(rtss, 'SeriesDescription', 'RT Structure Set')
            self.updateElement(rtss, 'StructureSetDate', '19010101')
            self.updateElement(rtss, 'StructureSetTime', '000000')
            if rtss.has_key('RTROIObservations'):
                for item in rtss.RTROIObservations:
                    self.updateElement(item, 'ROIInterpreter', 'anonymous')
            rtss.save_as(os.path.join(path, 'rtss.dcm'))
            i = i + 1
        if data.has_key('rtplan'):
            rtplan = data['rtplan']
            wx.CallAfter(progressFunc, i, length,
                'Anonymizing file ' + str(i) + ' of ' + str(length))
            self.updateCommonElements(rtplan, name, patientid, privatetags)
            self.updateElement(rtplan, 'SeriesDescription', 'RT Plan')
            self.updateElement(rtplan, 'RTPlanName', 'plan')
            self.updateElement(rtplan, 'RTPlanDate', '19010101')
            self.updateElement(rtplan, 'RTPlanTime', '000000')
            if rtplan.has_key('Beams'):
                for item in rtplan.Beams:
                    self.updateElement(item, 'Manufacturer', 'manufacturer')
                    self.updateElement(item, 'ManufacturersModelName', 'model')
                    self.updateElement(item, 'TreatmentMachineName', 'txmachine')
            if rtplan.has_key('TreatmentMachines'):
                for item in rtplan.TreatmentMachines:
                    self.updateElement(item, 'Manufacturer', 'manufacturer')
                    self.updateElement(item, 'InstitutionName', 'vendor')
                    self.updateElement(item, 'InstitutionAddress', 'address')
                    self.updateElement(item, 'ManufacturersModelName', 'model')
                    self.updateElement(item, 'DeviceSerialNumber', '0')
                    self.updateElement(item, 'TreatmentMachineName', 'txmachine')
            if rtplan.has_key('Sources'):
                for item in rtplan.Sources:
                    self.updateElement(item, 'SourceManufacturer', 'manufacturer')
                    self.updateElement(item, 'SourceIsotopeName', 'isotope')
            rtplan.save_as(os.path.join(path, 'rtplan.dcm'))
            i = i + 1
        if data.has_key('rtdose'):
            rtdose = data['rtdose']
            wx.CallAfter(progressFunc, i, length,
                'Anonymizing file ' + str(i) + ' of ' + str(length))
            self.updateCommonElements(rtdose, name, patientid, privatetags)
            self.updateElement(rtdose, 'SeriesDescription', 'RT Dose')
            rtdose.save_as(os.path.join(path, 'rtdose.dcm'))
            i = i + 1
        if data.has_key('images'):
            images = data['images']
            for n, image in enumerate(images):
                wx.CallAfter(progressFunc, i, length,
                    'Anonymizing file ' + str(i) + ' of ' + str(length))
                self.updateCommonElements(image, name, patientid, privatetags)
                self.updateElement(image, 'SeriesDate', '19010101')
                self.updateElement(image, 'ContentDate', '19010101')
                self.updateElement(image, 'SeriesTime', '000000')
                self.updateElement(image, 'ContentTime', '000000')
                self.updateElement(image, 'InstitutionName', 'institution')
                self.updateElement(image, 'InstitutionalDepartmentName', '')
                modality = image.SOPClassUID.name.partition(' Image Storage')[0]
                image.save_as(
                    os.path.join(path, modality.lower() + '.' + str(n) + '.dcm'))
                i = i + 1

        wx.CallAfter(progressFunc, length-1, length, 'Done')

    def updateElement(self, data, element, value):
        """Updates the element only if it exists in the original DICOM data."""

        if element in data:
            data.update({element:value})

    def updateCommonElements(self, data, name, patientid, privatetags):
        """Updates the element only if it exists in the original DICOM data."""

        if len(name):
            self.updateElement(data, 'PatientsName', name)
        if len(patientid):
            self.updateElement(data, 'PatientID', patientid)
        if privatetags:
            data.remove_private_tags()
        self.updateElement(data, 'InstanceCreationDate', '19010101')
        self.updateElement(data, 'InstanceCreationTime', '000000')
        self.updateElement(data, 'StudyDate', '19010101')
        self.updateElement(data, 'StudyTime', '000000')
        self.updateElement(data, 'AccessionNumber', '')
        self.updateElement(data, 'Manufacturer', 'manufacturer')
        self.updateElement(data, 'ReferringPhysiciansName', 'physician')
        self.updateElement(data, 'StationName', 'station')
        self.updateElement(data, 'OperatorsName', 'operator')
        self.updateElement(data, 'ManufacturersModelName', 'model')
        self.updateElement(data, 'PatientsBirthDate', '')
        self.updateElement(data, 'PatientsSex', 'O')
        self.updateElement(data, 'StudyID', '1')
        self.updateElement(data, 'DeviceSerialNumber', '0')
        self.updateElement(data, 'SoftwareVersions', '1.0')
        self.updateElement(data, 'ReviewDate', '19010101')
        self.updateElement(data, 'ReviewTime', '000000')
        self.updateElement(data, 'ReviewerName', 'anonymous')

class AnonymizeDialog(wx.Dialog):
    """Dialog that shows the options to anonymize DICOM / DICOM RT data."""

    def __init__(self):
        pre = wx.PreDialog()
        # the Create step is done by XRC.
        self.PostCreate(pre)

    def Init(self):
        """Method called after the dialog has been initialized."""

        # Set window icon
        if not guiutil.IsMac():
            self.SetIcon(guiutil.get_icon())

        # Initialize controls
        self.txtDICOMFolder = XRCCTRL(self, 'txtDICOMFolder')
        self.checkPatientName = XRCCTRL(self, 'checkPatientName')
        self.txtFirstName = XRCCTRL(self, 'txtFirstName')
        self.txtLastName = XRCCTRL(self, 'txtLastName')
        self.checkPatientID = XRCCTRL(self, 'checkPatientID')
        self.txtPatientID = XRCCTRL(self, 'txtPatientID')
        self.checkPrivateTags = XRCCTRL(self, 'checkPrivateTags')
        self.bmpError = XRCCTRL(self, 'bmpError')
        self.lblDescription = XRCCTRL(self, 'lblDescription')

        # Bind interface events to the proper methods
        wx.EVT_BUTTON(self, XRCID('btnFolderBrowse'), self.OnFolderBrowse)
        wx.EVT_CHECKBOX(self, XRCID('checkPatientName'), self.OnCheckPatientName)
        wx.EVT_CHECKBOX(self, XRCID('checkPatientID'), self.OnCheckPatientID)
        wx.EVT_BUTTON(self, wx.ID_OK, self.OnOK)

        # Set and bold the font of the description label
        if guiutil.IsMac():
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            self.lblDescription.SetFont(font)

        # Initialize the import location via pubsub
        pub.subscribe(self.OnImportPrefsChange, 'general.dicom.import_location')
        pub.sendMessage('preferences.requested.value', 'general.dicom.import_location')

        # Pre-select the text on the text controls due to a Mac OS X bug
        self.txtFirstName.SetSelection(-1, -1)
        self.txtLastName.SetSelection(-1, -1)
        self.txtPatientID.SetSelection(-1, -1)

        # Load the error bitmap
        self.bmpError.SetBitmap(wx.Bitmap(util.GetResourcePath('error.png')))

        # Initialize variables
        self.name = self.txtLastName.GetValue() + '^' + self.txtFirstName.GetValue()
        self.patientid = self.txtPatientID.GetValue()
        self.privatetags = True

    def OnImportPrefsChange(self, msg):
        """When the import preferences change, update the values."""

        self.path = unicode(msg.data)
        self.txtDICOMFolder.SetValue(self.path)

    def OnFolderBrowse(self, evt):
        """Get the directory selected by the user."""

        dlg = wx.DirDialog(
            self, defaultPath = self.path,
            message="Choose a folder to save the anonymized DICOM data...")

        if dlg.ShowModal() == wx.ID_OK:
            self.path = dlg.GetPath()
            self.txtDICOMFolder.SetValue(self.path)

        dlg.Destroy()

    def OnCheckPatientName(self, evt):
        """Enable or disable whether the patient's name is anonymized."""

        self.txtFirstName.Enable(evt.IsChecked())
        self.txtLastName.Enable(evt.IsChecked())
        if not evt.IsChecked():
            self.txtDICOMFolder.SetFocus()
        else:
            self.txtFirstName.SetFocus()
            self.txtFirstName.SetSelection(-1, -1)

    def OnCheckPatientID(self, evt):
        """Enable or disable whether the patient's ID is anonymized."""

        self.txtPatientID.Enable(evt.IsChecked())
        if not evt.IsChecked():
            self.txtDICOMFolder.SetFocus()
        else:
            self.txtPatientID.SetFocus()
            self.txtPatientID.SetSelection(-1, -1)

    def OnOK(self, evt):
        """Return the options from the anonymize data dialog."""

        # Patient name
        if self.checkPatientName.IsChecked():
            self.name = self.txtLastName.GetValue()
            if len(self.txtFirstName.GetValue()):
                self.name = self.name + '^' + self.txtFirstName.GetValue()
        else:
            self.name = ''

        # Patient ID
        if self.checkPatientID.IsChecked():
            self.patientid = self.txtPatientID.GetValue()
        else:
            self.patientid = ''

        # Private tags
        if self.checkPrivateTags.IsChecked():
            self.privatetags = True
        else:
            self.privatetags = False

        self.EndModal(wx.ID_OK)