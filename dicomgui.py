#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

import fnmatch, hashlib, os, threading
import wx
from wx.xrc import *
from model import *
import dicomparser, guiutil

def ImportDicom(parent):
    """Prepare to show the dialog that will Import DICOM RT files."""

    # Load the XRC file for our gui resources
    res = XmlResource("resources/dicomgui.xrc")

    dlgDicomImporter = res.LoadDialog(parent, "DicomImporterDialog")
    dlgDicomImporter.Init(res)

    # Show the dialog and return the result
    if (dlgDicomImporter.ShowModal() == wx.ID_OK):
        return dlgDicomImporter.GetPatient()
    else:
        return None

class DicomImporterDialog(wx.Dialog):
    """Import DICOM RT files and return a dictionary of data."""

    def __init__(self):
        pre = wx.PreDialog()
        # the Create step is done by XRC.
        self.PostCreate(pre)

    def Init(self, res):
        """Method called after the panel has been initialized."""

        # Initialize controls
        self.txtDicomImport = XRCCTRL(self, 'txtDicomImport')
        self.btnDicomImport = XRCCTRL(self, 'btnDicomImport')
        self.lblDirections = XRCCTRL(self, 'lblDirections')
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
        wx.EVT_TREE_SEL_CHANGED(self, XRCID('tcPatients'), self.OnSelectTreeItem)
        wx.EVT_TREE_ITEM_ACTIVATED(self, XRCID('tcPatients'), self.OnOK)
        wx.EVT_BUTTON(self, wx.ID_OK, self.OnOK)
        wx.EVT_BUTTON(self, wx.ID_CANCEL, self.OnCancel)

        # Set the dialog font and bold the font of the directions label
        font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        if guiutil.IsMac():
            self.txtDicomImport.SetFont(font)
            self.btnDicomImport.SetFont(font)
            self.lblDirections.SetFont(font)
            self.lblProgressLabel.SetFont(font)
            self.lblProgress.SetFont(font)
            self.lblProgressPercent.SetFont(font)
            self.lblProgressPercentSym.SetFont(font)
            self.tcPatients.SetFont(font)
            self.txtRxDose.SetFont(font)
            self.lblRxDoseUnits.SetFont(font)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.lblDirections.SetFont(font)
        self.lblRxDose.SetFont(font)

        # Initialize the patients tree control
        self.root = self.InitTree()

        # Initialize the patients dictionary
        self.patients = {}

        # Initialize the import location

        # Get the location from the preferences if it hasn't been set,
        # otherwise set it
        sp = wx.StandardPaths.Get()
        self.path = unicode(sp.GetDocumentsDir())
        if not len(Preferences.query.all()):
            Preferences(name='dicom_import_location', value=self.path)
            session.commit()
        else:
            path = Preferences.get_by(name=u'dicom_import_location').value
            if os.path.isdir(path):
                self.path = path
        self.txtDicomImport.SetValue(self.path)

        # Set the threading termination status to false intially
        self.terminate = False

        # Hide the progress bar until it needs to be shown
        self.gaugeProgress.Show(False)
        self.lblProgressPercent.Show(False)
        self.lblProgressPercentSym.Show(False)

        # Start the directory search as soon as the panel loads
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
        self.EnableRxDose(False)

        self.t=threading.Thread(target=self.DirectorySearchThread,
            args=(self, self.path, self.SetThreadStatus, self.OnUpdateProgress,
            self.AddPatientTree, self.AddItemTree))
        self.t.start()

    def SetThreadStatus(self):
        """Tell the directory search thread whether to terminate or not."""

        if self.terminate:
            return True
        else:
            return False

    def DirectorySearchThread(self, parent, path, terminate, progressFunc, foundFunc, resultFunc):
        """Thread to start the directory search."""

        # Call the progress function to update the gui
        wx.CallAfter(progressFunc, 0, 0, 'Searching for patients...')

        patients = {}

        # Check if the path is valid
        if os.path.isdir(path):
            for n in range(0, len(os.listdir(path))):

                # terminate the thread if the value has changed
                # during the loop duration
                if terminate():
                    wx.CallAfter(progressFunc, 0, 0, 'Search terminated.')
                    return

                files = os.listdir(path)
                dcmfile = str(os.path.join(path, files[n]))
                if (os.path.isfile(dcmfile) and fnmatch.fnmatch(dcmfile, '*.dcm')):
                    try:
                        print 'Reading:', files[n]
                        dp = dicomparser.DicomParser(dcmfile)
                    except (KeyError, IOError):
                        pass
                        print files[n] + " is not a valid DICOM file."
                    else:
                        patient = dp.GetDemographics()
                        h = hashlib.sha1(patient['id']).hexdigest()
                        if not patients.has_key(h):
                            patients[h] = {}
                            patients[h]['demographics'] = patient
                            wx.CallAfter(foundFunc, patient)
                        if (dp.GetSOPClassUID() == 'rtss'):
                            if not patients[h].has_key('structures'):
                                patients[h]['structures'] = []
                            structure = dp.GetStructureInfo()
                            structure['id'] = dp.GetSOPInstanceUID()
                            structure['filename'] = files[n]
                            patients[h]['structures'].append(structure)
                        elif (dp.GetSOPClassUID() == 'rtplan'):
                            if not patients[h].has_key('plans'):
                                patients[h]['plans'] = []
                            plan = dp.GetPlan()
                            plan['id'] = dp.GetSOPInstanceUID()
                            plan['filename'] = files[n]
                            plan['rtss'] = dp.GetReferencedStructureSet()
                            patients[h]['plans'].append(plan)
                        elif (dp.GetSOPClassUID() == 'rtdose'):
                            if not patients[h].has_key('doses'):
                                patients[h]['doses'] = []
                            dose = {}
                            dose['id'] = dp.GetSOPInstanceUID()
                            dose['filename'] = files[n]
                            dose['hasdvh'] = dp.HasDVHs()
                            dose['rtss'] = dp.GetReferencedStructureSet()
                            dose['rtplan'] = dp.GetReferencedRTPlan()
                            patients[h]['doses'].append(dose)
                        else:
                            print files[n] + " is a " \
                            + dp.ds.MediaStorageSOPClassUID.name \
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
                guiutil.GetResourcePath('group.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                guiutil.GetResourcePath('user.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                guiutil.GetResourcePath('pencil.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                guiutil.GetResourcePath('chart_bar.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                guiutil.GetResourcePath('chart_curve.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                guiutil.GetResourcePath('chart_bar_error.png'),
                wx.BITMAP_TYPE_PNG))
        iList.Add(
            wx.Bitmap(
                guiutil.GetResourcePath('chart_curve_error.png'),
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

    def AddItemTree(self, patients):
        """Add a new item to the tree control."""

        # Now add the specific item to the tree
        for key, patient in self.patients.iteritems():
            patient.update(patients[key])
            if patient.has_key('structures'):
                for structure in patient['structures']:
                    name = 'RT Structure Set: ' + structure['label']
                    structure['treeid'] = self.tcPatients.AppendItem(patient['treeid'], name, 2)
            if patient.has_key('plans'):
                for plan in patient['plans']:
                    for structure in patient['structures']:
                        if (structure['id'] == plan['rtss']):
                            name = 'RT Plan: ' + plan['label'] + ' (' + plan['name'] + ')'
                            plan['treeid'] = self.tcPatients.AppendItem(structure['treeid'], name, 3)
                            self.tcPatients.SetPyData(plan['treeid'], [plan['rxdose']])
            if patient.has_key('doses'):
                for dose in patient['doses']:
                    for structure in patient['structures']:
                        for plan in patient['plans']:
                            if (plan['id'] == dose['rtplan']):
                                if dose['hasdvh']:
                                    name = 'RT Dose with DVH'
                                    dose['treeid'] = self.tcPatients.AppendItem(plan['treeid'], name, 4)
                                    self.tcPatients.SetItemBold(dose['treeid'], True)
                                    filearray = [structure['filename'], plan['filename'], dose['filename']]
                                    self.tcPatients.SetPyData(dose['treeid'], filearray)
                                    self.tcPatients.SelectItem(dose['treeid'])
                                else:
                                    name = 'RT Dose without DVH (Not usable)'
                                    dose['treeid'] = self.tcPatients.AppendItem(plan['treeid'], name, 6)
                                    self.tcPatients.SetItemTextColour(dose['treeid'], wx.RED)
            else:
                for structure in patient['structures']:
                    if patient.has_key('plans'):
                        for plan in patient['plans']:
                            name = 'RT Dose not found'
                            baddose = self.tcPatients.AppendItem(plan['treeid'], name, 6)
                            self.tcPatients.SetItemTextColour(baddose, wx.RED)
                    else:
                        name = 'RT Plan not found'
                        badplan = self.tcPatients.AppendItem(structure['treeid'], name, 5)
                        self.tcPatients.SetItemTextColour(badplan, wx.RED)
                        name = 'RT Dose not found'
                        baddose = self.tcPatients.AppendItem(badplan, name, 6)
                        self.tcPatients.SetItemTextColour(baddose, wx.RED)

            self.btnSelect.SetFocus()
            self.tcPatients.ExpandAll()
            self.lblProgress.SetLabel(
                str(self.lblProgress.GetLabel()).replace(' Reading DICOM data...', ''))

    def OnSelectTreeItem(self, evt):
        """Update the interface when the selected item has changed."""

        item = evt.GetItem()
        self.EnableRxDose(False)
        self.btnSelect.Enable(False)
        if not (self.tcPatients.GetPyData(item) ==  None):
            if (len(self.tcPatients.GetPyData(item)) > 1):
                self.btnSelect.Enable()
                parent = self.tcPatients.GetItemParent(item)
                self.txtRxDose.SetValue(self.tcPatients.GetPyData(parent)[0])
                if (self.tcPatients.GetPyData(parent) == [0]):
                    self.EnableRxDose(True)

    def EnableRxDose(self, value):
        """Show or hide the prescription dose message."""

        self.bmpRxDose.Show(value)
        self.lblRxDose.Show(value)
        self.txtRxDose.Show(value)
        self.lblRxDoseUnits.Show(value)

        # if set to hide, reset the rx dose
        if not value:
            self.txtRxDose.SetValue(0.1)

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
                self.patient = dp.GetDemographics()
            if (dp.GetSOPClassUID() == 'rtss'):
                self.patient['structures'] = dp.GetStructures()
            elif (dp.GetSOPClassUID() == 'rtplan'):
                self.patient['plan'] = dp.GetPlan()
                self.patient['plan']['rxdose'] = RxDose
            elif (dp.GetSOPClassUID() == 'rtdose'):
                self.patient['dvh'] = dp.GetDVHs()
            wx.CallAfter(progressFunc, n, len(filearray), 'Importing patient. Please wait...')
        wx.CallAfter(progressFunc, 98, 100, 'Importing patient complete.')

    def GetPatient(self):
        """Return the patient data from the DICOM importer dialog."""

        return self.patient

    def OnOK(self, evt):
        """Return the patient data if the patient is selected or the button
            is pressed."""
        item = self.tcPatients.GetSelection()
        if (threading.activeCount() == 1):
            if self.tcPatients.GetPyData(item) :
                # Since we have decided to use this location to import from,
                # save the location back to the db for the next session,
                # only if the path has not changed from the previous session
                path = Preferences.get_by(name=u'dicom_import_location')
                if not (self.path == path.value):
                    path.value=self.path
                    session.commit()

                filearray = self.tcPatients.GetPyData(item)
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
