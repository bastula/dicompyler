#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# main.py
"""Main file for dicompyler."""
# Copyright (c) 2009 Aditya Panchal
# Copyright (c) 2009 Roy Keyes
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

import os, threading
import wx
from wx.xrc import *
import wx.lib.dialogs, webbrowser
from wx.lib.pubsub import Publisher as pub
from model import *
import guiutil, util
import dicomgui, dvhdata, dvhdoses
from dicomparser import DicomParser as dp
import plugin

class MainFrame(wx.Frame):
    def __init__(self, parent, id, title, res):

        # Set the window size
        if guiutil.IsMac():
            size=(900, 700)
        else:
            size=(850, 625)

        wx.Frame.__init__(self, parent, id, title, pos=wx.DefaultPosition,
            size=size, style=wx.DEFAULT_FRAME_STYLE)

        # set up resource file and config file
        self.res = res

        # Set window icon
        if not guiutil.IsMac():
            self.SetIcon(guiutil.get_icon())

        # Load the main panel for the program
        self.panelGeneral = self.res.LoadPanel(self, 'panelGeneral')

        # Initialize the General panel controls
        self.notebook = XRCCTRL(self, 'notebook')
        self.lblPlanName = XRCCTRL(self, 'lblPlanName')
        self.lblRxDose = XRCCTRL(self, 'lblRxDose')
        self.lblPatientName = XRCCTRL(self, 'lblPatientName')
        self.lblPatientID = XRCCTRL(self, 'lblPatientID')
        self.lblPatientGender = XRCCTRL(self, 'lblPatientGender')
        self.lblPatientDOB = XRCCTRL(self, 'lblPatientDOB')
        self.lblStructureVolume = XRCCTRL(self, 'lblStructureVolume')
        self.lblStructureMinDose = XRCCTRL(self, 'lblStructureMinDose')
        self.lblStructureMaxDose = XRCCTRL(self, 'lblStructureMaxDose')
        self.lblStructureMeanDose = XRCCTRL(self, 'lblStructureMeanDose')
        self.lbStructures = XRCCTRL(self, 'lbStructures')
        self.lbStructures.SetFocus()

        # Setup the layout for the frame
        mainGrid = wx.BoxSizer(wx.VERTICAL)
        hGrid = wx.BoxSizer(wx.HORIZONTAL)
        if guiutil.IsMac():
            hGrid.Add(self.panelGeneral, 1, flag=wx.EXPAND|wx.ALL|wx.ALIGN_CENTRE, border=4)
        else:
            hGrid.Add(self.panelGeneral, 1, flag=wx.EXPAND|wx.ALL|wx.ALIGN_CENTRE)

        mainGrid.Add(hGrid, 1, flag=wx.EXPAND|wx.ALL|wx.ALIGN_CENTRE)

        # Load the menu for the frame
        menuMain = self.res.LoadMenuBar('menuMain')

        # Setup Help menu
        menuAbout = XRCCTRL(self, 'menuAbout')
        menuHomepage = XRCCTRL(self, 'menuHomepage')
        menuLicense = XRCCTRL(self, 'menuLicense')

        # If we are running on Mac OS X, alter the menu location
        if guiutil.IsMac():
            wx.App_SetMacAboutMenuItemId(XRCID('menuAbout'))
            wx.App_SetMacExitMenuItemId(XRCID('menuExit'))

        # Set the menu as the default menu for this frame
        self.SetMenuBar(menuMain)

        # Bind menu events to the proper methods
        wx.EVT_MENU(self, XRCID('menuOpen'), self.OnOpenPatient)
        wx.EVT_MENU(self, XRCID('menuExit'), self.OnClose)
        wx.EVT_MENU(self, XRCID('menuPluginManager'), self.OnPluginManager)
        wx.EVT_MENU(self, XRCID('menuAbout'), self.OnAbout)
        wx.EVT_MENU(self, XRCID('menuHomepage'), self.OnHomepage)
        wx.EVT_MENU(self, XRCID('menuLicense'), self.OnLicense)

        # Load the toolbar for the frame
        toolbarMain = self.res.LoadToolBar(self, 'toolbarMain')
        self.SetToolBar(toolbarMain)

        # Bind interface events to the proper methods
        wx.EVT_TOOL(self, XRCID('toolOpen'), self.OnOpenPatient)

        # Bind ui events to the proper methods
        wx.EVT_LISTBOX(self, XRCID('lbStructures'), self.OnStructureSelect)

        # Initialize variables
        self.structures = {}

        self.SetSizer(mainGrid)
        self.Layout()

        #Set the Minumum size
        self.SetMinSize(size)
        self.Centre(wx.BOTH)

        # Initalize the database
        datapath = guiutil.get_data_dir()
        dbpath = os.path.join(datapath, 'dicompyler.db')
        # Set the database path to the data path before writing to disk
        metadata.bind = "sqlite:///" + dbpath
        setup_all()
        if not os.path.exists(datapath):
            os.mkdir(datapath)
        if not os.path.isfile(dbpath):
            create_all()

        # Load plugins
        self.plugins = plugin.import_plugins()

        # Set up the plugins for each plugin entry point of dicompyler
        for p in self.plugins:
            props = p.pluginProperties()
            # Only load plugin versions that are qualified
            if (props['plugin_version'] == 1):
                # Load the main panel plugins
                if (props['plugin_type'] == 'main'):
                    # Initialize the notebook tabs
                    self.notebook.AddPage(
                        p.pluginLoader(self.notebook), 
                        props['name'])

        # Set up pubsub
        pub.subscribe(self.OnLoadPatientData, 'patient.updated.raw_data')

    def OnOpenPatient(self, evt):
        """Load and show the Dicom RT Importer dialog box."""

        self.ptdata = dicomgui.ImportDicom(self)
        if not (self.ptdata == None):
            pub.sendMessage('patient.updated.raw_data', self.ptdata)

    def OnLoadPatientData(self, msg):
        """Update and load the patient data."""

        ptdata = msg.data
        dlgProgress = guiutil.get_progress_dialog(self)
        self.t=threading.Thread(target=self.LoadPatientDataThread,
            args=(self, ptdata, dlgProgress.OnUpdateProgress,
            self.OnUpdatePatientData))
        self.t.start()
        dlgProgress.ShowModal()

    def LoadPatientDataThread(self, parent, ptdata, progressFunc, updateFunc):
        """Thread to load the patient data."""

        # Call the progress function to update the gui
        wx.CallAfter(progressFunc, 0, 0, 'Importing patient data...')
        if ptdata.has_key('rtplan'):
            wx.CallAfter(progressFunc, 0, 4, 'Importing RT Structure Set...')
            patient = dp(ptdata['rtplan']).GetDemographics()
            patient['structures'] = dp(ptdata['rtss']).GetStructures()
        if ptdata.has_key('rtplan'):
            patient['plan'] = dp(ptdata['rtplan']).GetPlan()
            patient['plan']['rxdose'] = ptdata['rxdose']
        if ptdata.has_key('rtdose'):
            wx.CallAfter(progressFunc, 1, 4, 'Importing RT Dose...')
            patient['dvhs'] = dp(ptdata['rtdose']).GetDVHs()
        # if the min/max/mean dose was not present, calculate it and save it for each structure
        wx.CallAfter(progressFunc, 2, 4, 'Processing DVH data...')
        for key, dvh in patient['dvhs'].iteritems():
            if (dvh['min'] == -1):
                dvh['min'] = dvhdoses.get_dvh_min(dvh['data'], ptdata['rxdose'])
            if (dvh['max'] == -1):
                dvh['max'] = dvhdoses.get_dvh_max(dvh['data'], ptdata['rxdose'])
            if (dvh['mean'] == -1):
                dvh['mean'] = dvhdoses.get_dvh_mean(dvh['data'], ptdata['rxdose'])
        wx.CallAfter(progressFunc, 98, 100, 'Done')
        wx.CallAfter(updateFunc, patient)

    def OnUpdatePatientData(self, patient):
        """Update the patient data in the main program interface."""
        
        self.structures = patient['structures']
        self.dvhs = patient['dvhs']
        self.PopulateDemographics(patient)
        self.PopulatePlan(patient['plan'])
        self.PopulateStructures()
        self.currConstraintId = None
        
        # publish the parsed data
        pub.sendMessage('patient.updated.parsed_data', patient)

    def PopulateStructures(self):
        """Populate the structure list."""

        self.lbStructures.Clear()

        structureList = []
        structureIDList = []
        for id, structure in self.structures.iteritems():
            # Only append structures, don't include applicators
            if not(structure['name'].startswith('Applicator')):
                structureList.append(structure['name'])
                structureIDList.append(id)

        guiutil.SetItemsList(self.lbStructures, structureList, structureIDList)

        # Select the first item in the list (if it exists)
        if len(structureList):
            self.lbStructures.SetSelection(wx.NOT_FOUND)

    def PopulateDemographics(self, demographics):
        """Populate the patient demographics."""

        self.lblPatientName.SetLabel(demographics['name'])
        self.lblPatientID.SetLabel(demographics['id'])
        self.lblPatientGender.SetLabel(demographics['gender'])
        self.lblPatientDOB.SetLabel(demographics['dob'])

    def PopulatePlan(self, plan):
        """Populate the patient's plan information."""

        if len(plan['name']):
            self.lblPlanName.SetLabel(plan['name'])
        elif len(plan['label']):
            self.lblPlanName.SetLabel(plan['label'])
        self.lblRxDose.SetLabel(str(plan['rxdose']))

    def OnStructureSelect(self, evt):
        """Load the properties of the currently selected structure."""

        id = evt.GetClientData()
        self.dvhid = id

        # make sure that the volume has been calculated for each structure
        # before setting it
        if not self.structures[id].has_key('volume'):
            self.structures[id]['volume'] = dvhdata.CalculateVolume(self.structures[id])
        self.lblStructureVolume.SetLabel(str(self.structures[id]['volume'])[0:7])
        pub.sendMessage('structures.selected',
            {'id':id, 'volume':self.structures[id]['volume']})

        # make sure that the dvh has been calculated for each structure
        # before setting it
        if self.dvhs.has_key(id):
            self.lblStructureMinDose.SetLabel("%.3f" % self.dvhs[id]['min'])
            self.lblStructureMaxDose.SetLabel("%.3f" % self.dvhs[id]['max'])
            self.lblStructureMeanDose.SetLabel("%.3f" % self.dvhs[id]['mean'])
        else:
            self.lblStructureMinDose.SetLabel('-')
            self.lblStructureMaxDose.SetLabel('-')
            self.lblStructureMeanDose.SetLabel('-')

    def OnPluginManager(self, evt):
        """Load and show the Dicom RT Importer dialog box."""

        self.pm = plugin.PluginManager(self, self.plugins)

    def OnAbout(self, evt):
        # First we create and fill the info object
        info = wx.AboutDialogInfo()
        info.Name = "dicompyler"
        info.Version = "0.1"
        info.Copyright = u"© 2009-2010 Aditya Panchal"
        credits = util.get_credits()
        info.Developers = credits['developers']
        info.Artists = credits['artists']
        desc =  "Python application to view and modify DICOM and DICOM-RT files." + \
                "\n\ndicompyler is released under a BSD license.\n" + \
                "See the Help menu for license information."
        info.Description = desc
        if guiutil.IsGtk():
            info.WebSite = "http://code.google.com/p/dicompyler/"

        # Then we call wx.AboutBox giving it that info object
        wx.AboutBox(info)

    def OnHomepage(self, evt):
        """Show the homepage for dicompyler."""

        webbrowser.open_new_tab("http://code.google.com/p/dicompyler/")
        
    def OnLicense(self, evt):
        """Show the license document in a new dialog."""
        
        f = open("license.txt", "rU")
        msg = f.read()
        f.close()

        if guiutil.IsMSWindows():
            dlg = wx.lib.dialogs.ScrolledMessageDialog(self, msg,
                "dicompyler License")
        else:
            dlg = wx.lib.dialogs.ScrolledMessageDialog(self, msg,
                "dicompyler License", size=(650, 550))
        dlg.ShowModal()

    def OnClose(self, _):
        self.Close()

class dicompyler(wx.App):
    def OnInit(self):
        wx.InitAllImageHandlers()
        wx.GetApp().SetAppName("dicompyler")

        # Load the XRC file for our gui resources
        self.res = XmlResource(util.GetResourcePath('main.xrc'))

        # Use the native listctrl on Mac OS X
        if guiutil.IsMac():
            wx.SystemOptions.SetOptionInt("mac.listctrl.always_use_generic", 0)

        dicompylerFrame = MainFrame(None, -1, "dicompyler", self.res)
        self.SetTopWindow(dicompylerFrame)
        dicompylerFrame.Centre()
        dicompylerFrame.Show()
        return 1

# end of class dicompyler

if __name__ == '__main__':
    app = dicompyler(0)
    app.MainLoop()
