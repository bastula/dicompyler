#!/usr/bin/env python
# -*- coding: utf-8 -*-
# dicomgui.py
"""Class that imports and returns DICOM data via a wxPython GUI dialog."""
# Copyright (c) 2009-2017 Aditya Panchal
# Copyright (c) 2009 Roy Keyes
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/bastula/dicompyler/
#
# It's assumed that the reference (prescription) dose is in cGy.

import logging
logger = logging.getLogger('dicompyler.dicomgui')
import hashlib, os, threading
import wx
from wx.xrc import *
from pubsub import pub
import numpy as np
from dicompylercore import dicomparser
from dicompyler import guiutil, util

def ImportDicom(parent):
    """Prepare to show the dialog that will Import DICOM and DICOM RT files."""

    # Load the XRC file for our gui resources
    res = XmlResource(util.GetResourcePath('dicomgui.xrc'))

    dlgDicomImporter = res.LoadDialog(parent, "DicomImporterDialog")
    dlgDicomImporter.Init(res)

    # Show the dialog and return the result
    if (dlgDicomImporter.ShowModal() == wx.ID_OK):
        value = dlgDicomImporter.GetPatient()
        pub.sendMessage('patient.updated.raw_data', msg=value)
    else:
        value = {}
    # Block until the thread is done before destroying the dialog
    if dlgDicomImporter:
        dlgDicomImporter.t.join()
        dlgDicomImporter.Destroy()

    return value

class DicomImporterDialog(wx.Dialog):
    """Import DICOM RT files and return a dictionary of data."""

    def __init__(self):
        wx.Dialog.__init__(self)

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
        # wx.EVT_BUTTON(self, XRCID('btnDicomImport'), self.OnBrowseDicomImport)
        self.Bind(wx.EVT_BUTTON, self.OnBrowseDicomImport, id=XRCID('btnDicomImport'))
        # wx.EVT_CHECKBOX(self, XRCID('checkSearchSubfolders'),
        #                             self.OnCheckSearchSubfolders)
        self.Bind(wx.EVT_CHECKBOX, self.OnCheckSearchSubfolders, id=XRCID('checkSearchSubfolders'))
        # wx.EVT_TREE_SEL_CHANGED(self, XRCID('tcPatients'), self.OnSelectTreeItem)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnSelectTreeItem, id=XRCID('tcPatients'))
        # wx.EVT_TREE_ITEM_ACTIVATED(self, XRCID('tcPatients'), self.OnOK)
        self.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnOK, id=XRCID('tcPatients'))
        # wx.EVT_BUTTON(self, wx.ID_OK, self.OnOK)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)
        # wx.EVT_BUTTON(self, wx.ID_CANCEL, self.OnCancel)

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
        pub.sendMessage('preferences.requested.values', msg='general.dicom')

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

    def OnImportPrefsChange(self, topic, msg):
        """When the import preferences change, update the values."""
        topic = topic.split('.')
        if (topic[1] == 'import_location'):
            self.path = str(msg)
            self.txtDicomImport.SetValue(self.path)
        elif (topic[1] == 'import_location_setting'):
            self.import_location_setting = msg
        elif (topic[1] == 'import_search_subfolders'):
            self.import_search_subfolders = msg
            self.checkSearchSubfolders.SetValue(msg)

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

        # If a previous search thread exists, block until it is done before
        # starting a new thread
        if (hasattr(self, 't')):
            self.t.join()
            del self.t

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
                        logger.debug("Reading: %s", files[n])
                        dp = dicomparser.DicomParser(files[n])
                    except (AttributeError, EOFError, IOError, KeyError):
                        pass
                        logger.info("%s is not a valid DICOM file.", files[n])
                    else:
                        patient = dp.GetDemographics()
                        h = hashlib.sha1(patient['id'].encode('utf-8')).hexdigest()
                        if not h in patients:
                            patients[h] = {}
                            patients[h]['demographics'] = patient
                            if not 'studies' in patients[h]:
                                patients[h]['studies'] = {}
                                patients[h]['series'] = {}
                            wx.CallAfter(foundFunc, patient)
                        # Create each Study but don't create one for RT Dose
                        # since some vendors use incorrect StudyInstanceUIDs
                        if not (dp.GetSOPClassUID() == 'rtdose'):
                            stinfo = dp.GetStudyInfo()
                            if not stinfo['id'] in patients[h]['studies']:
                                patients[h]['studies'][stinfo['id']] = stinfo
                        # Create each Series of images
                        if (('ImageOrientationPatient' in dp.ds) and \
                            not (dp.GetSOPClassUID() == 'rtdose')):
                            seinfo = dp.GetSeriesInfo()
                            seinfo['numimages'] = 0
                            seinfo['modality'] = dp.ds.SOPClassUID.name
                            if not seinfo['id'] in patients[h]['series']:
                                patients[h]['series'][seinfo['id']] = seinfo
                            if not 'images' in patients[h]:
                                patients[h]['images'] = {}
                            image = {}
                            image['id'] = dp.GetSOPInstanceUID()
                            image['filename'] = files[n]
                            image['series'] = seinfo['id']
                            image['referenceframe'] = dp.GetFrameOfReferenceUID()
                            patients[h]['series'][seinfo['id']]['numimages'] = \
                                patients[h]['series'][seinfo['id']]['numimages'] + 1
                            patients[h]['images'][image['id']] = image
                        # Create each RT Structure Set
                        elif dp.ds.Modality in ['RTSTRUCT']:
                            if not 'structures' in patients[h]:
                                patients[h]['structures'] = {}
                            structure = dp.GetStructureInfo()
                            structure['id'] = dp.GetSOPInstanceUID()
                            structure['filename'] = files[n]
                            structure['series'] = dp.GetReferencedSeries()
                            structure['referenceframe'] = dp.GetFrameOfReferenceUID()
                            patients[h]['structures'][structure['id']] = structure
                        # Create each RT Plan
                        elif dp.ds.Modality in ['RTPLAN']:
                            if not 'plans' in patients[h]:
                                patients[h]['plans'] = {}
                            plan = dp.GetPlan()
                            plan['id'] = dp.GetSOPInstanceUID()
                            plan['filename'] = files[n]
                            plan['series'] = dp.ds.SeriesInstanceUID
                            plan['referenceframe'] = dp.GetFrameOfReferenceUID()
                            plan['beams'] = dp.GetReferencedBeamsInFraction()
                            plan['rtss'] = dp.GetReferencedStructureSet()
                            patients[h]['plans'][plan['id']] = plan
                        # Create each RT Dose
                        elif dp.ds.Modality in ['RTDOSE']:
                            if not 'doses' in patients[h]:
                                patients[h]['doses'] = {}
                            dose = {}
                            dose['id'] = dp.GetSOPInstanceUID()
                            dose['filename'] = files[n]
                            dose['referenceframe'] = dp.GetFrameOfReferenceUID()
                            dose['hasdvh'] = dp.HasDVHs()
                            dose['hasgrid'] = "PixelData" in dp.ds
                            dose['summationtype'] = dp.ds.DoseSummationType
                            dose['beam'] = dp.GetReferencedBeamNumber()
                            dose['rtss'] = dp.GetReferencedStructureSet()
                            dose['rtplan'] = dp.GetReferencedRTPlan()
                            patients[h]['doses'][dose['id']] = dose
                        # Otherwise it is a currently unsupported file
                        else:
                            logger.info("%s is a %s file and is not " + \
                                "currently supported.",
                                files[n], dp.ds.SOPClassUID.name)

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
        h = hashlib.sha1(patient['id'].encode('utf-8')).hexdigest()
        # Add the patient to the tree if they don't already exist
        if not h in self.patients:
            self.patients[h] = {}
            self.patients[h]['demographics'] = patient
            name = str(patient['name']) + ' (' + patient['id'] + ')'
            self.patients[h]['treeid'] = \
                self.tcPatients.AppendItem(self.root, name, 1)
            self.tcPatients.SortChildren(self.root)

        self.tcPatients.ExpandAll()

    def AddPatientDataTree(self, patients):
        """Add the patient data to the tree control."""

        # Now add the specific item to the tree
        for key, patient in self.patients.items():
            patient.update(patients[key])
            if 'studies' in patient:
                for studyid, study in patient['studies'].items():
                    name = 'Study: ' + study['description']
                    study['treeid'] = self.tcPatients.AppendItem(patient['treeid'], name, 2)
            # Search for series and images
            if 'series' in patient:
                for seriesid, series in patient['series'].items():
                    if 'studies' in patient:
                        for studyid, study in patient['studies'].items():
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
            if 'structures' in patient:
                for structureid, structure in patient['structures'].items():
                    if 'series' in patient:
                        foundseries = False
                        name = 'RT Structure Set: ' + structure['label']
                        for seriesid, series in patient['series'].items():
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
            if 'plans' in patient:
                for planid, plan in patient['plans'].items():
                    foundstructure = False
                    planname = ' (' + plan['name'] + ')' if len(plan['name']) else ""
                    rxdose = plan['rxdose'] if plan['rxdose'] > 0 else "Unknown"
                    name = 'RT Plan: ' + plan['label'] + planname + \
                        ' - Dose: ' + str(rxdose) + ' cGy'
                    if 'structures' in patient:
                        for structureid, structure in patient['structures'].items():
                            foundstructure = False
                            if (structureid == plan['rtss']):
                                plan['treeid'] = self.tcPatients.AppendItem(structure['treeid'], name, 5)
                                foundstructure = True
                    # If no structures were found, add the plan to the study/series instead
                    if not foundstructure:
                        # If there is an image series, add a fake rtss to it
                        foundseries = False
                        for seriesid, series in patient['series'].items():
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
            if 'doses' in patient:
                for doseid, dose in patient['doses'].items():
                    foundplan = False
                    if 'plans' in patient:
                        for planid, plan in patient['plans'].items():
                            foundplan = False
                            if (planid == dose['rtplan']):
                                foundplan = True
                                rxdose = None
                                if dose['hasgrid']:
                                    if dose['hasdvh']:
                                        name = 'RT Dose with DVH'
                                    else:
                                        name = 'RT Dose without DVH'
                                else:
                                    if dose['hasdvh']:
                                        name = 'RT Dose without Dose Grid (DVH only)'
                                    else:
                                        name = 'RT Dose without Dose Grid or DVH'
                                if (dose['summationtype'] == "BEAM"):
                                    name += " (Beam " + str(dose['beam']) + ": "
                                    if dose['beam'] in plan['beams']:
                                        b = plan['beams'][dose['beam']]
                                        name += b['name']
                                        if len(b['description']):
                                            name += " - " + b['description']
                                        name += ")"
                                        if "dose" in b:
                                            name += " - Dose: " + str(int(b['dose'])) + " cGy"
                                            rxdose = int(b['dose'])
                                dose['treeid'] = self.tcPatients.AppendItem(plan['treeid'], name, 6)
                                filearray = [dose['filename']]
                                self.EnableItemSelection(patient, dose, filearray, rxdose)
                    # If no plans were found, add the dose to the structure/study instead
                    if not foundplan:
                        if dose['hasgrid']:
                            if dose['hasdvh']:
                                name = 'RT Dose with DVH'
                            else:
                                name = 'RT Dose without DVH'
                        else:
                            if dose['hasdvh']:
                                name = 'RT Dose without Dose Grid (DVH only)'
                            else:
                                name = 'RT Dose without Dose Grid or DVH'
                        foundstructure = False
                        if 'structures' in patient:
                            for structureid, structure in patient['structures'].items():
                                foundstructure = False
                                if 'rtss' in dose:
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
                            for seriesid, series in patient['series'].items():
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
                if 'structures' in patient:
                    for structureid, structure in patient['structures'].items():
                        if 'plans' in patient:
                            for planid, plan in patient['plans'].items():
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
        if 'images' in patient:
            for imageid, image in patient['images'].items():
                appendImage = False
                # used for image series
                if 'id' in item:
                    if (item['id'] == image['series']):
                        appendImage = True
                # used for RT structure set
                if 'series' in item:
                    if (item['series'] == image['series']):
                        appendImage = True
                # used for RT plan / dose
                if 'referenceframe' in item:
                    if (item['referenceframe'] == image['referenceframe']):
                        if not 'numimages' in item:
                            appendImage = True
                if appendImage:
                    filearray.append(image['filename'])
        # Add the respective rtss files to the filearray if they exist
        if 'structures' in patient:
            for structureid, structure in patient['structures'].items():
                if 'rtss' in item:
                    if (structureid == item['rtss']):
                        filearray.append(structure['filename'])
                        break
                    elif (structure['referenceframe'] == item['referenceframe']):
                        filearray.append(structure['filename'])
                        break
                # If no referenced rtss, but ref'd rtplan, check rtplan->rtss
                if 'rtplan' in item:
                    if 'plans' in patient:
                        for planid, plan in patient['plans'].items():
                            if (planid == item['rtplan']):
                                if 'rtss' in plan:
                                    if (structureid == plan['rtss']):
                                        filearray.append(structure['filename'])
        # Add the respective rtplan files to the filearray if they exist
        if 'plans' in patient:
            for planid, plan in patient['plans'].items():
                if 'rtplan' in item:
                    if (planid == item['rtplan']):
                        filearray.append(plan['filename'])
        if not rxdose:
            self.tcPatients.SetItemData(item['treeid'], {'filearray':filearray})
        else:
            self.tcPatients.SetItemData(item['treeid'], {'filearray':filearray, 'rxdose':rxdose})
        self.tcPatients.SetItemBold(item['treeid'], True)
        self.tcPatients.SelectItem(item['treeid'])

    def OnSelectTreeItem(self, evt):
        """Update the interface when the selected item has changed."""

        item = evt.GetItem()
        # Disable the rx dose message and select button by default
        self.EnableRxDose(False)
        self.btnSelect.Enable(False)
        # If the item has data, check to see whether there is an rxdose
        if not (self.tcPatients.GetItemData(item) ==  None):
            data = self.tcPatients.GetItemData(item)
            self.btnSelect.Enable()
            rxdose = 0
            parent = self.tcPatients.GetItemParent(item)
            if 'rxdose' in data:
                rxdose = data['rxdose']
            else:
                parentdata = self.tcPatients.GetItemData(parent)
                if not (parentdata == None):
                    if 'rxdose' in parentdata:
                        rxdose = parentdata['rxdose']
            # Show the rxdose text box if no rxdose was found
            # and if it is an RT plan or RT dose file
            self.txtRxDose.SetValue(rxdose)
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
            dp = dicomparser.DicomParser(dcmfile)
            if (n == 0):
                self.patient = {}
                self.patient['rxdose'] = RxDose
            if (('ImageOrientationPatient' in dp.ds) and \
                not (dp.GetSOPClassUID() == 'rtdose')):
                if not 'images' in self.patient:
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
        if 'images' in self.patient:
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
        if self.tcPatients.GetItemData(item):
            # Since we have decided to use this location to import from,
            # update the location in the preferences for the next session
            # if the 'import_location_setting' is "Remember Last Used"
            if (self.import_location_setting == "Remember Last Used"):
                pub.sendMessage('preferences.updated.value',
                    msg={'general.dicom.import_location':self.path})

            # Since we have updated the search subfolders setting,
            # update the setting in preferences
            pub.sendMessage('preferences.updated.value',
                msg={'general.dicom.import_search_subfolders':
                 self.import_search_subfolders})

            filearray = self.tcPatients.GetItemData(item)['filearray']
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
        super().OnCancel(evt)
