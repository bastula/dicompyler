#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# dicomgui.py
"""Class that imports and returns DICOM data via a wxPython GUI dialog."""
# Copyright (c) 2009-2011 Aditya Panchal
# Copyright (c) 2009 Roy Keyes
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#
# It's assumed that the reference (prescription) dose is in cGy.

import hashlib, os, threading
import wx
from wx.xrc import *
from wx.lib.pubsub import Publisher as pub
import numpy as np
import dicomparser, dvhdoses, guiutil, util

def ImportDicom(parent):
    """Prepare to show the dialog that will Import DICOM and DICOM RT files."""

    # Load the XRC file for our gui resources
    res = XmlResource(util.GetResourcePath('dicomgui.xrc'))

    dlgDicomImporter = res.LoadDialog(parent, "DicomImporterDialog")
    dlgDicomImporter.Init(res)

    # Show the dialog and return the result
    if (dlgDicomImporter.ShowModal() == wx.ID_OK):
        value = dlgDicomImporter.GetPatient()
    else:
        value = None
    # Block until the thread is done before destroying the dialog
    dlgDicomImporter.t.join()
    dlgDicomImporter.Destroy()

    return value

class DicomImporterDialog(wx.Dialog):
    """Import DICOM RT files and return a dictionary of data."""

    def __init__(self):
        pre = wx.PreDialog()
        # the Create step is done by XRC.
        self.PostCreate(pre)

    def Init(self, res):
        """Method called after the panel has been initialized."""

        # Set window icon
        if not guiutil.IsMac():
            self.SetIcon(guiutil.get_icon())

        # Initialize controls
        self.txtDicomImport = XRCCTRL(self, 'txtDicomImport')
        self.btnDicomImport = XRCCTRL(self, 'btnDicomImport')
        self.checkSearchSubfolders = XRCCTRL(self, 'checkSearchSubfolders')
        self.lblDirections = XRCCTRL(self, 'lblDirections')
        self.lblDirections2 = XRCCTRL(self, 'lblDirections2')
        self.lblProgressLabel = XRCCTRL(self, 'lblProgressLabel')
        self.lblProgress = XRCCTRL(self, 'lblProgress')
        self.gaugeProgress = XRCCTRL(self, 'gaugeProgress')
        self.lblProgressPercent = XRCCTRL(self, 'lblProgressPercent')
        self.lblProgressPercentSym = XRCCTRL(self, 'lblProgressPercentSym')
        self.tcPatients = XRCCTRL(self, 'tcPatients')
        self.bmpRxDose = XRCCTRL(self, 'bmpRxDose')
        self.lblRxDose = XRCCTRL(self, 'lblRxDose')
        self.txtRxDose = XRCCTRL(self, 'txtRxDose')
        self.lblRxDoseUnits = XRCCTRL(self, 'lblRxDoseUnits')
        self.btnSelect = XRCCTRL(self, 'wxID_OK')

        # Bind interface events to the proper methods
        wx.EVT_BUTTON(self, XRCID('btnDicomImport'), self.OnBrowseDicomImport)
        wx.EVT_CHECKBOX(self, XRCID('checkSearchSubfolders'),
                                    self.OnCheckSearchSubfolders)
        wx.EVT_TREE_SEL_CHANGED(self, XRCID('tcPatients'), self.OnSelectTreeItem)
        wx.EVT_TREE_ITEM_ACTIVATED(self, XRCID('tcPatients'), self.OnOK)
        wx.EVT_BUTTON(self, wx.ID_OK, self.OnOK)
        wx.EVT_BUTTON(self, wx.ID_CANCEL, self.OnCancel)

        # Set the dialog font and bold the font of the directions label
        font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        if guiutil.IsMac():
            self.txtDicomImport.SetFont(font)
            self.btnDicomImport.SetFont(font)
            self.checkSearchSubfolders.SetFont(font)
            self.lblDirections.SetFont(font)
            self.lblDirections2.SetFont(font)
            self.lblProgressLabel.SetFont(font)
            self.lblProgress.SetFont(font)
            self.lblProgressPercent.SetFont(font)
            self.lblProgressPercentSym.SetFont(font)
            self.tcPatients.SetFont(font)
            self.txtRxDose.SetFont(font)
            self.lblRxDoseUnits.SetFont(font)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.lblDirections2.SetFont(font)
        self.lblRxDose.SetFont(font)

        # Initialize the patients tree control
        self.root = self.InitTree()

        # Initialize the patients dictionary
        self.patients = {}

        # Initialize the import location via pubsub
        pub.subscribe(self.OnImportPrefsChange, 'general.dicom')
        pub.sendMessage('preferences.requested.values', 'general.dicom')

        # Search subfolders by default
        self.import_search_subfolders = True

        # Set the threading termination status to false intially
        self.terminate = False

        # Hide the progress bar until it needs to be shown
        self.gaugeProgress.Show(False)
        self.lblProgressPercent.Show(False)
        self.lblProgressPercentSym.Show(False)

        # Start the directory search as soon as the panel loads
        self.OnDirectorySearch()

    def OnImportPrefsChange(self, msg):
        """When the import preferences change, update the values."""

        if (msg.topic[2] == 'import_location'):
            self.path = unicode(msg.data)
            self.txtDicomImport.SetValue(self.path)
        elif (msg.topic[2] == 'import_location_setting'):
            self.import_location_setting = msg.data
        elif (msg.topic[2] == 'import_search_subfolders'):
            self.import_search_subfolders = msg.data
            self.checkSearchSubfolders.SetValue(msg.data)

    def OnCheckSearchSubfolders(self, evt):
        """Determine whether to search subfolders for DICOM data."""

        self.import_search_subfolders = evt.IsChecked()
        self.terminate = True
        self.OnDirectorySearch()

    def OnBrowseDicomImport(self, evt):
        """Get the directory selected by the user."""

        self.terminate = True

        dlg = wx.DirDialog(
            self, defaultPath = self.path,
            message="Choose a directory containing DICOM RT files...")

        if dlg.ShowModal() == wx.ID_OK:
            self.path = dlg.GetPath()
            self.txtDicomImport.SetValue(self.path)

        dlg.Destroy()
        self.OnDirectorySearch()

    def OnDirectorySearch(self):
        """Begin directory search."""

        self.patients = {}
        self.tcPatients.DeleteChildren(self.root)
        self.terminate = False

        self.gaugeProgress.Show(True)
        self.lblProgressPercent.Show(True)
        self.lblProgressPercentSym.Show(True)
        self.btnSelect.Enable(False)
        # Disable Rx dose controls except on GTK due to control placement oddities
        if not guiutil.IsGtk():
            self.EnableRxDose(False)

        self.t=threading.Thread(target=self.DirectorySearchThread,
            args=(self, self.path, self.import_search_subfolders,
            self.SetThreadStatus, self.OnUpdateProgress,
            self.AddPatientTree, self.AddPatientDataTree))
        self.t.start()

    def SetThreadStatus(self):
        """Tell the directory search thread whether to terminate or not."""

        if self.terminate:
            return True
        else:
            return False

    def DirectorySearchThread(self, parent, path, subfolders, terminate,
        progressFunc, foundFunc, resultFunc):
        """Thread to start the directory search."""

        # Call the progress function to update the gui
        wx.CallAfter(progressFunc, 0, 0, 'Searching for patients...')

        patients = {}

        # Check if the path is valid
        if os.path.isdir(path):

            files = []
            for root, dirs, filenames in os.walk(path):
                files += map(lambda f:os.path.join(root, f), filenames)
                if (self.import_search_subfolders == False):
                    break
            for n in range(len(files)):

                # terminate the thread if the value has changed
                # during the loop duration
                if terminate():
                    wx.CallAfter(progressFunc, 0, 0, 'Search terminated.')
                    return

                if (os.path.isfile(files[n])):
                    try:
                        print 'Reading:', files[n]
                        dp = dicomparser.DicomParser(filename=files[n])
                    except (AttributeError, EOFError, IOError, KeyError):
                        pass
                        print files[n] + " is not a valid DICOM file."
                    else:
                        patient = dp.GetDemographics()
                        h = hashlib.sha1(patient['id']).hexdigest()
                        if not patients.has_key(h):
                            patients[h] = {}
                            patients[h]['demographics'] = patient
                            if not patients[h].has_key('studies'):
                                patients[h]['studies'] = {}
                                patients[h]['series'] = {}
                            wx.CallAfter(foundFunc, patient)
                        # Create each Study but don't create one for RT Dose
                        # since some vendors use incorrect StudyInstanceUIDs
                        if not (dp.GetSOPClassUID() == 'rtdose'):
                            stinfo = dp.GetStudyInfo()
                            if not patients[h]['studies'].has_key(stinfo['id']):
                                patients[h]['studies'][stinfo['id']] = stinfo
                        # Create each Series of images
                        if (('ImageOrientationPatient' in dp.ds) and \
                            not (dp.GetSOPClassUID() == 'rtdose')):
                            seinfo = dp.GetSeriesInfo()
                            seinfo['numimages'] = 0
                            seinfo['modality'] = dp.ds.SOPClassUID.name
                            if not patients[h]['series'].has_key(seinfo['id']):
                                patients[h]['series'][seinfo['id']] = seinfo
                            if not patients[h].has_key('images'):
                                patients[h]['images'] = {}
                            image = {}
                            image['id'] = dp.GetSOPInstanceUID()
                            image['filename'] = files[n]
                            image['series'] = seinfo['id']
                            image['referenceframe'] = dp.GetFrameofReferenceUID()
                            patients[h]['series'][seinfo['id']]['numimages'] = \
                                patients[h]['series'][seinfo['id']]['numimages'] + 1 
                            patients[h]['images'][image['id']] = image
                        # Create each RT Structure Set
                        elif dp.ds.Modality in ['RTSTRUCT']:
                            if not patients[h].has_key('structures'):
                                patients[h]['structures'] = {}
                            structure = dp.GetStructureInfo()
                            structure['id'] = dp.GetSOPInstanceUID()
                            structure['filename'] = files[n]
                            structure['series'] = dp.GetReferencedSeries()
                            structure['referenceframe'] = dp.GetFrameofReferenceUID()
                            patients[h]['structures'][structure['id']] = structure
                        # Create each RT Plan
                        elif dp.ds.Modality in ['RTPLAN']:
                            if not patients[h].has_key('plans'):
                                patients[h]['plans'] = {}
                            plan = dp.GetPlan()
                            plan['id'] = dp.GetSOPInstanceUID()
                            plan['filename'] = files[n]
                            plan['series'] = dp.ds.SeriesInstanceUID
                            plan['referenceframe'] = dp.GetFrameofReferenceUID()
                            plan['rtss'] = dp.GetReferencedStructureSet()
                            patients[h]['plans'][plan['id']] = plan
                        # Create each RT Dose
                        elif dp.ds.Modality in ['RTDOSE']:
                            if not patients[h].has_key('doses'):
                                patients[h]['doses'] = {}
                            dose = {}
                            dose['id'] = dp.GetSOPInstanceUID()
                            dose['filename'] = files[n]
                            dose['referenceframe'] = dp.GetFrameofReferenceUID()
                            dose['hasdvh'] = dp.HasDVHs()
                            dose['rtss'] = dp.GetReferencedStructureSet()
                            dose['rtplan'] = dp.GetReferencedRTPlan()
                            patients[h]['doses'][dose['id']] = dose
                        # Otherwise it is a currently unsupported file
                        else:
                            print files[n] + " is a " \
                            + dp.ds.SOPClassUID.name \
                            + " file and is not currently supported."

                # Call the progress function to update the gui
                wx.CallAfter(progressFunc, n, len(files), 'Searching for patients...')

            if (len(patients) == 0):
                progressStr = 'Found 0 patients.'
            elif (len(patients) == 1):
                progressStr = 'Found 1 patient. Reading DICOM data...'
            elif (len(patients) > 1):
                progressStr = 'Found ' + str(len(patients)) + ' patients. Reading DICOM data...'
            wx.CallAfter(progressFunc, 0, 1, progressStr)
            wx.CallAfter(resultFunc, patients)

        # if the path is not valid, display an error message
        else:
            wx.CallAfter(progressFunc, 0, 0, 'Select a valid location.')
            dlg = wx.MessageDialog(
                parent,
                "The DICOM import location does not exist. Please select a valid location.",
                "Invalid DICOM Import Location", wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()

    def OnUpdateProgress(self, num, length, message):
        """Update the DICOM Import process interface elements."""

        if not length:
            percentDone = 0
        else:
            percentDone = int(100 * (num+1) / length)

        self.gaugeProgress.SetValue(percentDone)
        self.lblProgressPercent.SetLabel(str(percentDone))
        self.lblProgress.SetLabel(message)

        if not (percentDone == 100):
            self.gaugeProgress.Show(True)
            self.lblProgressPercent.Show(True)
            self.lblProgressPercentSym.Show(True)
        else:
            self.gaugeProgress.Show(False)
            self.lblProgressPercent.Show(False)
            self.lblProgressPercentSym.Show(False)

        # End the dialog since we are done with the import process
        if (message == 'Importing patient complete.'):
            self.EndModal(wx.ID_OK)
        elif (message == 'Importing patient cancelled.'):
            self.EndModal(wx.ID_CANCEL)

    def InitTree(self):
        """Initialize the tree control for use."""

        iSize = (16,16)
        iList = wx.ImageList(iSize[0], iSize[1])
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('group.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('user.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('book.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('table_multiple.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('pencil.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('chart_bar.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('chart_curve.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('pencil_error.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('chart_bar_error.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                util.GetResourcePath('chart_curve_error.png'),
                wx.BITMAP_TYPE_PNG))

        self.tcPatients.AssignImageList(iList)

        root = self.tcPatients.AddRoot('Patients', image=0)

        return root

    def AddPatientTree(self, patient):
        """Add a new patient to the tree control."""

        # Create a hash for each patient
        h = hashlib.sha1(patient['id']).hexdigest()
        # Add the patient to the tree if they don't already exist
        if not self.patients.has_key(h):
            self.patients[h] = {}
            self.patients[h]['demographics'] = patient
            name = patient['name'] + ' (' + patient['id'] + ')'
            self.patients[h]['treeid'] = \
                self.tcPatients.AppendItem(self.root, name, 1)
            self.tcPatients.SortChildren(self.root)

        self.tcPatients.ExpandAll()

    def AddPatientDataTree(self, patients):
        """Add the patient data to the tree control."""

        # Now add the specific item to the tree
        for key, patient in self.patients.iteritems():
            patient.update(patients[key])
            if patient.has_key('studies'):
                for studyid, study in patient['studies'].iteritems():
                    name = 'Study: ' + study['description']
                    study['treeid'] = self.tcPatients.AppendItem(patient['treeid'], name, 2)
            # Search for series and images
            if patient.has_key('series'):
                for seriesid, series in patient['series'].iteritems():
                    if patient.has_key('studies'):
                        for studyid, study in patient['studies'].iteritems():
                            if (studyid == series['study']):
                                modality = series['modality'].partition(' Image Storage')[0]
                                name = 'Series: ' + series['description'] + \
                                    ' (' + modality + ', '
                                if (series['numimages'] == 1):
                                    numimages = str(series['numimages']) + ' image)'
                                else:
                                    numimages = str(series['numimages']) + ' images)'
                                name = name + numimages
                                series['treeid'] = self.tcPatients.AppendItem(study['treeid'], name, 3)
                                self.EnableItemSelection(patient, series, [])
            # Search for RT Structure Sets
            if patient.has_key('structures'):
                for structureid, structure in patient['structures'].iteritems():
                    if patient.has_key('series'):
                        foundseries = False
                        name = 'RT Structure Set: ' + structure['label']
                        for seriesid, series in patient['series'].iteritems():
                            foundseries = False
                            if (seriesid == structure['series']):
                                structure['treeid'] = self.tcPatients.AppendItem(series['treeid'], name, 4)
                                foundseries = True
                        # If no series were found, add the rtss to the study
                        if not foundseries:
                            structure['treeid'] = self.tcPatients.AppendItem(study['treeid'], name, 4)
                        filearray = [structure['filename']]
                        self.EnableItemSelection(patient, structure, filearray)
            # Search for RT Plans
            if patient.has_key('plans'):
                for planid, plan in patient['plans'].iteritems():
                    foundstructure = False
                    name = 'RT Plan: ' + plan['label'] + ' (' + plan['name'] + ')'
                    if patient.has_key('structures'):
                        for structureid, structure in patient['structures'].iteritems():
                            foundstructure = False
                            if (structureid == plan['rtss']):
                                plan['treeid'] = self.tcPatients.AppendItem(structure['treeid'], name, 5)
                                foundstructure = True
                    # If no structures were found, add the plan to the study/series instead
                    if not foundstructure:
                        # If there is an image series, add a fake rtss to it
                        foundseries = False
                        for seriesid, series in patient['series'].iteritems():
                            foundseries = False
                            if (series['referenceframe'] == plan['referenceframe']):
                                badstructure = self.tcPatients.AppendItem(
                                    series['treeid'], "RT Structure Set not found", 7)
                                foundseries = True
                        # If no series were found, add the rtss to the study
                        if not foundseries:
                            badstructure = self.tcPatients.AppendItem(
                                patient['treeid'], "RT Structure Set not found", 7)
                        plan['treeid'] = self.tcPatients.AppendItem(badstructure, name, 5)
                        self.tcPatients.SetItemTextColour(badstructure, wx.RED)
                    filearray = [plan['filename']]
                    self.EnableItemSelection(patient, plan, filearray, plan['rxdose'])
            # Search for RT Doses
            if patient.has_key('doses'):
                for doseid, dose in patient['doses'].iteritems():
                    foundplan = False
                    if patient.has_key('plans'):
                        for planid, plan in patient['plans'].iteritems():
                            foundplan = False
                            if (planid == dose['rtplan']):
                                foundplan = True
                                if dose['hasdvh']:
                                    name = 'RT Dose with DVH'
                                else:
                                    name = 'RT Dose without DVH'
                                dose['treeid'] = self.tcPatients.AppendItem(plan['treeid'], name, 6)
                                filearray = [dose['filename']]
                                self.EnableItemSelection(patient, dose, filearray)
                    # If no plans were found, add the dose to the structure/study instead
                    if not foundplan:
                        if dose['hasdvh']:
                            name = 'RT Dose with DVH'
                        else:
                            name = 'RT Dose without DVH'
                        foundstructure = False
                        if patient.has_key('structures'):
                            for structureid, structure in patient['structures'].iteritems():
                                foundstructure = False
                                if dose.has_key('rtss'):
                                    if (structureid == dose['rtss']):
                                        foundstructure = True
                                if (structure['referenceframe'] == dose['referenceframe']):
                                    foundstructure = True
                                if foundstructure:
                                    badplan = self.tcPatients.AppendItem(
                                        structure['treeid'], "RT Plan not found", 8)
                                    dose['treeid'] = self.tcPatients.AppendItem(badplan, name, 6)
                                    self.tcPatients.SetItemTextColour(badplan, wx.RED)
                                    filearray = [dose['filename']]
                                    self.EnableItemSelection(patient, dose, filearray)
                        if not foundstructure:
                            # If there is an image series, add a fake rtss to it
                            foundseries = False
                            for seriesid, series in patient['series'].iteritems():
                                foundseries = False
                                if (series['referenceframe'] == dose['referenceframe']):
                                    badstructure = self.tcPatients.AppendItem(
                                        series['treeid'], "RT Structure Set not found", 7)
                                    foundseries = True
                            # If no series were found, add the rtss to the study
                            if not foundseries:
                                badstructure = self.tcPatients.AppendItem(
                                    patient['treeid'], "RT Structure Set not found", 7)
                            self.tcPatients.SetItemTextColour(badstructure, wx.RED)
                            badplan = self.tcPatients.AppendItem(
                                    badstructure, "RT Plan not found", 8)
                            dose['treeid'] = self.tcPatients.AppendItem(badplan, name, 5)
                            self.tcPatients.SetItemTextColour(badplan, wx.RED)
                            filearray = [dose['filename']]
                            self.EnableItemSelection(patient, dose, filearray)
            # No RT Dose files were found
            else:
                if patient.has_key('structures'):
                    for structureid, structure in patient['structures'].iteritems():
                        if patient.has_key('plans'):
                            for planid, plan in patient['plans'].iteritems():
                                name = 'RT Dose not found'
                                baddose = self.tcPatients.AppendItem(plan['treeid'], name, 9)
                                self.tcPatients.SetItemTextColour(baddose, wx.RED)
                        # No RT Plan nor RT Dose files were found
                        else:
                            name = 'RT Plan not found'
                            badplan = self.tcPatients.AppendItem(structure['treeid'], name, 8)
                            self.tcPatients.SetItemTextColour(badplan, wx.RED)
                            name = 'RT Dose not found'
                            baddose = self.tcPatients.AppendItem(badplan, name, 9)
                            self.tcPatients.SetItemTextColour(baddose, wx.RED)

            self.btnSelect.SetFocus()
            self.tcPatients.ExpandAll()
            self.lblProgress.SetLabel(
                str(self.lblProgress.GetLabel()).replace(' Reading DICOM data...', ''))

    def EnableItemSelection(self, patient, item, filearray = [], rxdose = None):
        """Enable an item to be selected in the tree control."""

        # Add the respective images to the filearray if they exist
        if patient.has_key('images'):
            for imageid, image in patient['images'].iteritems():
                appendImage = False
                # used for image series
                if item.has_key('id'):
                    if (item['id'] == image['series']):
                        appendImage = True
                # used for RT structure set
                if item.has_key('series'):
                    if (item['series'] == image['series']):
                        appendImage = True
                # used for RT plan / dose
                if item.has_key('referenceframe'):
                    if (item['referenceframe'] == image['referenceframe']):
                        if not 'numimages' in item:
                            appendImage = True
                if appendImage:
                    filearray.append(image['filename'])
        # Add the respective rtss files to the filearray if they exist
        if patient.has_key('structures'):
            for structureid, structure in patient['structures'].iteritems():
                if item.has_key('rtss'):
                    if (structureid == item['rtss']):
                        filearray.append(structure['filename'])
                        break
                    elif (structure['referenceframe'] == item['referenceframe']):
                        filearray.append(structure['filename'])
                        break
                # If no referenced rtss, but ref'd rtplan, check rtplan->rtss
                if item.has_key('rtplan'):
                    if patient.has_key('plans'):
                        for planid, plan in patient['plans'].iteritems():
                            if (planid == item['rtplan']):
                                if plan.has_key('rtss'):
                                    if (structureid == plan['rtss']):
                                        filearray.append(structure['filename'])
        # Add the respective rtplan files to the filearray if they exist
        if patient.has_key('plans'):
            for planid, plan in patient['plans'].iteritems():
                if item.has_key('rtplan'):
                    if (planid == item['rtplan']):
                        filearray.append(plan['filename'])
        if not rxdose:
            self.tcPatients.SetPyData(item['treeid'], {'filearray':filearray})
        else:
            self.tcPatients.SetPyData(item['treeid'], {'filearray':filearray, 'rxdose':rxdose})
        self.tcPatients.SetItemBold(item['treeid'], True)
        self.tcPatients.SelectItem(item['treeid'])

    def OnSelectTreeItem(self, evt):
        """Update the interface when the selected item has changed."""

        item = evt.GetItem()
        # Disable the rx dose message and select button by default
        self.EnableRxDose(False)
        self.btnSelect.Enable(False)
        # If the item has data, check to see whether there is an rxdose
        if not (self.tcPatients.GetPyData(item) ==  None):
            data = self.tcPatients.GetPyData(item)
            self.btnSelect.Enable()
            rxdose = 0
            if data.has_key('rxdose'):
                rxdose = data['rxdose']
            else:
                parent = self.tcPatients.GetItemParent(item)
                parentdata = self.tcPatients.GetPyData(parent)
                if not (parentdata == None):
                    if parentdata.has_key('rxdose'):
                        rxdose = parentdata['rxdose']
            # Show the rxdose text box if no rxdose was found
            # and if it is an RT plan or RT dose file
            self.txtRxDose.SetValue(rxdose)
            if (rxdose == 0):
                if (self.tcPatients.GetItemText(item).startswith('RT Plan') or
                    self.tcPatients.GetItemText(parent).startswith('RT Plan')):
                    self.EnableRxDose(True)

    def EnableRxDose(self, value):
        """Show or hide the prescription dose message."""

        self.bmpRxDose.Show(value)
        self.lblRxDose.Show(value)
        self.txtRxDose.Show(value)
        self.lblRxDoseUnits.Show(value)

        # if set to hide, reset the rx dose
        if not value:
            self.txtRxDose.SetValue(1)

    def GetPatientData(self, path, filearray, RxDose, terminate, progressFunc):
        """Get the data of the selected patient from the DICOM importer dialog."""

        wx.CallAfter(progressFunc, -1, 100, 'Importing patient. Please wait...')
        for n in range(0, len(filearray)):
            if terminate():
                wx.CallAfter(progressFunc, 98, 100, 'Importing patient cancelled.')
                return
            dcmfile = str(os.path.join(self.path, filearray[n]))
            dp = dicomparser.DicomParser(filename=dcmfile)
            if (n == 0):
                self.patient = {}
                self.patient['rxdose'] = RxDose
            if (('ImageOrientationPatient' in dp.ds) and \
                not (dp.GetSOPClassUID() == 'rtdose')):
                if not self.patient.has_key('images'):
                    self.patient['images'] = []
                self.patient['images'].append(dp.ds)
            elif (dp.ds.Modality in ['RTSTRUCT']):
                self.patient['rtss'] = dp.ds
            elif (dp.ds.Modality in ['RTPLAN']):
                self.patient['rtplan'] = dp.ds
            elif (dp.ds.Modality in ['RTDOSE']):
                self.patient['rtdose'] = dp.ds
            wx.CallAfter(progressFunc, n, len(filearray), 'Importing patient. Please wait...')
        # Sort the images based on a sort descriptor:
        # (ImagePositionPatient, InstanceNumber or AcquisitionNumber)
        if self.patient.has_key('images'):
            sortedimages = []
            unsortednums = []
            sortednums = []
            images = self.patient['images']
            sort = 'IPP'
            # Determine if all images in the series are parallel
            # by testing for differences in ImageOrientationPatient
            parallel = True
            for i, item in enumerate(images):
                if (i > 0):
                    iop0 = np.array(item.ImageOrientationPatient)
                    iop1 = np.array(images[i-1].ImageOrientationPatient)
                    if (np.any(np.array(np.round(iop0 - iop1),
                    dtype=np.int32))):
                        parallel = False
                        break
                    # Also test ImagePositionPatient, as some series
                    # use the same patient position for every slice
                    ipp0 = np.array(item.ImagePositionPatient)
                    ipp1 = np.array(images[i-1].ImagePositionPatient)
                    if not (np.any(np.array(np.round(ipp0 - ipp1),
                    dtype=np.int32))):
                        parallel = False
                        break
            # If the images are parallel, sort by ImagePositionPatient
            if parallel:
                sort = 'IPP'
            else:
                # Otherwise sort by Instance Number
                if not (images[0].InstanceNumber == \
                images[1].InstanceNumber):
                    sort = 'InstanceNumber'
                # Otherwise sort by Acquisition Number
                elif not (images[0].AcquisitionNumber == \
                images[1].AcquisitionNumber):
                    sort = 'AcquisitionNumber'

            # Add the sort descriptor to a list to be sorted
            for i, image in enumerate(images):
                if (sort == 'IPP'):
                    unsortednums.append(image.ImagePositionPatient[2])
                else:
                    unsortednums.append(image.data_element(sort).value)

            # Sort image numbers in descending order for head first patients
            if ('hf' in image.PatientPosition.lower()) and (sort == 'IPP'):
                sortednums = sorted(unsortednums, reverse=True)
            # Otherwise sort image numbers in ascending order
            else:
                sortednums = sorted(unsortednums)

            # Add the images to the array based on the sorted order
            for s, slice in enumerate(sortednums):
                for i, image in enumerate(images):
                    if (sort == 'IPP'):
                        if (slice == image.ImagePositionPatient[2]):
                            sortedimages.append(image)
                    elif (slice == image.data_element(sort).value):
                        sortedimages.append(image)

            # Save the images back to the patient dictionary
            self.patient['images'] = sortedimages
        wx.CallAfter(progressFunc, 98, 100, 'Importing patient complete.')

    def GetPatient(self):
        """Return the patient data from the DICOM importer dialog."""

        return self.patient

    def OnOK(self, evt):
        """Return the patient data if the patient is selected or the button
            is pressed."""
        item = self.tcPatients.GetSelection()
        if self.tcPatients.GetPyData(item):
            # Since we have decided to use this location to import from,
            # update the location in the preferences for the next session
            # if the 'import_location_setting' is "Remember Last Used"
            if (self.import_location_setting == "Remember Last Used"):
                pub.sendMessage('preferences.updated.value',
                    {'general.dicom.import_location':self.path})

            # Since we have updated the search subfolders setting,
            # update the setting in preferences
            pub.sendMessage('preferences.updated.value',
                {'general.dicom.import_search_subfolders':
                 self.import_search_subfolders})

            filearray = self.tcPatients.GetPyData(item)['filearray']
            self.btnSelect.Enable(False)
            self.txtRxDose.Enable(False)
            self.terminate = False
            self.importThread=threading.Thread(target=self.GetPatientData,
            args=(self.path, filearray, self.txtRxDose.GetValue(),
                self.SetThreadStatus, self.OnUpdateProgress))
            self.importThread.start()

    def OnCancel(self, evt):
        """Stop the directory search and close the dialog."""

        self.terminate = True
        self.Hide()
