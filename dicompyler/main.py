#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py
"""Main file for dicompyler."""
# Copyright (c) 2009-2017 Aditya Panchal
# Copyright (c) 2009 Roy Keyes
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/bastula/dicompyler/

# Configure logging for dicompyler
import logging, logging.handlers
logger = logging.getLogger('dicompyler')
logger.setLevel(logging.DEBUG)

import os, threading
import sys, traceback
import wx
from wx.xrc import *
import wx.adv
import wx.lib.dialogs, webbrowser
import pydicom
from pubsub import pub
from dicompylercore import dvhcalc
from dicompyler import __version__
from dicompyler import guiutil, util
from dicompyler import dicomgui, dvhdata
from dicompylercore.dicomparser import DicomParser as dp
from dicompyler import plugin, preferences
import pandas as pd

class MainFrame(wx.Frame):
    def __init__(self, parent, id, title, res):

        # Initialize logging
        logger = logging.getLogger('dicompyler')

        # Configure the exception hook to process threads as well
        self.InstallThreadExcepthook()

        # Remap the exception hook so that we can log and display exceptions
        def LogExcepthook(*exc_info):
            # Log the exception
            text = "".join(traceback.format_exception(*exc_info))
            logger.error("Unhandled exception: %s", text)
            pub.sendMessage('logging.exception', msg=text)

        sys.excepthook = LogExcepthook

        # Modify the logging system from pydicom to capture important messages
        pydicom_logger = logging.getLogger('pydicom')
        for l in pydicom_logger.handlers:
            pydicom_logger.removeHandler(l)

        # Add file logger
        logpath = os.path.join(guiutil.get_data_dir(), 'logs')
        if not os.path.exists(logpath):
            os.makedirs(logpath)
        self.fh = logging.handlers.RotatingFileHandler(
                os.path.join(logpath, 'dicompyler.log'),
                maxBytes=524288, backupCount=7)
        self.fh.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.fh.setLevel(logging.WARNING)
        logger.addHandler(self.fh)
        pydicom_logger.addHandler(self.fh)

        # Add console logger if not frozen
        if not util.main_is_frozen():
            self.ch = logging.StreamHandler()
            self.ch.setFormatter(logging.Formatter(
                '%(levelname)s: %(message)s'))
            self.ch.setLevel(logging.WARNING)
            logger.addHandler(self.ch)
            pydicom_logger.addHandler(self.ch)
        # Otherwise if frozen, send stdout/stderror to /dev/null since
        # logging the messages seems to cause instability due to recursion
        else:
            devnull = open(os.devnull, 'w')
            sys.stdout = devnull
            sys.stderr = devnull
        
        # Set the window size
        if guiutil.IsMac():
            size=(900, 700)
        else:
            size=(850, 625)

        wx.Frame.__init__(self, parent, id, title, pos=wx.DefaultPosition,
            size=size, style=wx.DEFAULT_FRAME_STYLE)

        # Set up the status bar
        self.sb = self.CreateStatusBar(3)

        # set up resource file and config file
        self.res = res

        # Set window icon
        if not guiutil.IsMac():
            self.SetIcon(guiutil.get_icon())

        # Load the main panel for the program
        self.panelGeneral = self.res.LoadPanel(self, 'panelGeneral')

        # Initialize the General panel controls
        self.notebook = XRCCTRL(self, 'notebook')
        self.notebookTools = XRCCTRL(self, 'notebookTools')
        self.lblPlanName = XRCCTRL(self, 'lblPlanName')
        self.lblRxDose = XRCCTRL(self, 'lblRxDose')
        self.lblPatientName = XRCCTRL(self, 'lblPatientName')
        self.lblPatientID = XRCCTRL(self, 'lblPatientID')
        self.lblPatientGender = XRCCTRL(self, 'lblPatientGender')
        self.lblPatientDOB = XRCCTRL(self, 'lblPatientDOB')
        self.choiceStructure = XRCCTRL(self, 'choiceStructure')
        self.lblStructureVolume = XRCCTRL(self, 'lblStructureVolume')
        self.lblStructureMinDose = XRCCTRL(self, 'lblStructureMinDose')
        self.lblStructureMaxDose = XRCCTRL(self, 'lblStructureMaxDose')
        self.lblStructureMeanDose = XRCCTRL(self, 'lblStructureMeanDose')
        self.cclbStructures = guiutil.ColorCheckListBox(self.notebookTools, 'structure')
        self.cclbIsodoses = guiutil.ColorCheckListBox(self.notebookTools, 'isodose')

        # Modify the control size on Mac
        controls = [self.notebookTools, self.choiceStructure]

        if guiutil.IsMac():
            for control in controls:
                control.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)

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

        # If we are running on Mac OS X, alter the menu location
        if guiutil.IsMac():
            wx.PyApp.SetMacAboutMenuItemId(XRCID('menuAbout'))
            wx.PyApp.SetMacPreferencesMenuItemId(XRCID('menuPreferences'))
            wx.PyApp.SetMacExitMenuItemId(XRCID('menuExit'))

        # Set the menu as the default menu for this frame
        self.SetMenuBar(menuMain)

        # Setup Tools menu
        self.menuShowLogs = menuMain.FindItemById(XRCID('menuShowLogs')).GetMenu()
        self.menuPlugins = menuMain.FindItemById(XRCID('menuPluginManager')).GetMenu()

        # Setup Import menu
        self.menuImport = menuMain.FindItemById(XRCID('menuImportPlaceholder')).GetMenu()
        self.menuImport.Delete(menuMain.FindItemById(XRCID('menuImportPlaceholder')).GetId())
        self.menuImportItem = menuMain.FindItemById(XRCID('menuImport'))
        self.menuImportItem.Enable(False)

        # Setup Export menu
        self.menuExport = menuMain.FindItemById(XRCID('menuExportPlaceholder')).GetMenu()
        self.menuExport.Delete(menuMain.FindItemById(XRCID('menuExportPlaceholder')).GetId())
        self.menuExportItem = menuMain.FindItemById(XRCID('menuExport'))
        self.menuExportItem.Enable(False)

        # Bind menu events to the proper methods
        self.Bind(wx.EVT_MENU, self.OnOpenPatient, id=XRCID('menuOpen'))
        self.Bind(wx.EVT_MENU, self.OnClose, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.OnPreferences, id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, self.OnShowLogs, id=XRCID('menuShowLogs'))
        self.Bind(
            wx.EVT_MENU, self.OnPluginManager, id=XRCID('menuPluginManager'))
        self.Bind(wx.EVT_MENU, self.OnAbout, id=wx.ID_ABOUT)
        self.Bind(wx.EVT_MENU, self.OnHomepage, id=XRCID('menuHomepage'))
        self.Bind(wx.EVT_MENU, self.OnLicense, id=XRCID('menuLicense'))

        # Load the toolbar for the frame
        toolbarMain = self.res.LoadToolBar(self, 'toolbarMain')
        self.SetToolBar(toolbarMain)
        self.toolbar = self.GetToolBar()

        # Setup main toolbar controls
        folderbmp = wx.Bitmap(util.GetResourcePath('folder_user.png'))
        self.maintools = [{'label':"Open Patient", 'bmp':folderbmp,
                            'shortHelp':"Open Patient...",
                            'eventhandler':self.OnOpenPatient}]
        for m, tool in enumerate(self.maintools):
            self.toolbar.AddTool(m+1, tool['label'], tool['bmp'],
                                 shortHelp=tool['shortHelp'])
            self.Bind(wx.EVT_TOOL, tool['eventhandler'], id=m+1)
        self.toolbar.Realize()

        # Bind interface events to the proper methods
        self.Bind(
            wx.EVT_CHOICE, self.OnStructureSelect, id=XRCID('choiceStructure'))
        self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPageChanged)
        # Events to work around a focus bug in Windows
        self.notebook.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.notebook.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.notebookTools.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.notebookTools.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)

        self.SetSizer(mainGrid)
        self.Layout()

        #Set the Minumum size
        self.SetMinSize(size)
        self.Centre(wx.BOTH)

        # Initialize the welcome notebook tab
        panelWelcome = self.res.LoadPanel(self.notebook, 'panelWelcome')
        self.notebook.AddPage(panelWelcome, 'Welcome')
        # Set the version on the welcome notebook tab
        XRCCTRL(self, 'lblVersion').SetLabel('Version ' + __version__)

        # Initialize the tools notebook
        self.notebookTools.AddPage(self.cclbStructures, 'Structures')
        self.notebookTools.AddPage(self.cclbIsodoses, 'Isodoses')

        # Create the data folder
        datapath = guiutil.get_data_dir()
        if not os.path.exists(datapath):
            os.mkdir(datapath)

        # Initialize the preferences
        if guiutil.IsMac():
            self.prefmgr = preferences.PreferencesManager(
                parent = self, appname = 'dicompyler')
        else:
            self.prefmgr = preferences.PreferencesManager(
                parent = self, appname = 'dicompyler', name = 'Options')
        sp = wx.StandardPaths.Get()
        self.generalpreftemplate = [
            {'DICOM Import Settings':
                [{'name':'Import Location',
                 'type':'choice',
               'values':['Remember Last Used', 'Always Use Default'],
              'default':'Remember Last Used',
             'callback':'general.dicom.import_location_setting'},
                {'name':'Default Location',
                 'type':'directory',
              'default':sp.GetDocumentsDir(),
             'callback':'general.dicom.import_location'}]
            },
            {'Plugin Settings':
                [{'name':'User Plugins Location',
                 'type':'directory',
              'default':os.path.join(datapath, 'plugins'),
             'callback':'general.plugins.user_plugins_location',
             'restart':True}]
            },
            {'Calculation Settings':
                [{'name':'DVH Calculation',
                 'type':'choice',
               'values':['Use RT Dose DVH if Present', 'Always Recalculate DVH'],
              'default':'Use RT Dose DVH if Present',
             'callback':'general.calculation.dvh_recalc'}]
            },
            {'Advanced Settings':
                [{'name':'Enable Detailed Logging',
                 'type':'checkbox',
              'default':False,
             'callback':'general.advanced.detailed_logging'}]
            }]
        self.preftemplate = [{'General':self.generalpreftemplate}]
        pub.sendMessage('preferences.updated.template', msg=self.preftemplate)

        # Initialize variables
        self.ptdata = {}

        # Set up pubsub
        pub.subscribe(self.OnLoadPatientData, 'patient.updated.raw_data')
        pub.subscribe(self.OnStructureCheck, 'colorcheckbox.checked.structure')
        pub.subscribe(self.OnStructureUncheck, 'colorcheckbox.unchecked.structure')
        pub.subscribe(self.OnIsodoseCheck, 'colorcheckbox.checked.isodose')
        pub.subscribe(self.OnIsodoseUncheck, 'colorcheckbox.unchecked.isodose')
        pub.subscribe(self.OnUpdatePlugins, 'general.plugins.user_plugins_location')
        pub.subscribe(self.OnUpdatePreferences, 'general')
        pub.subscribe(self.OnUpdateStatusBar, 'main.update_statusbar')
        pub.subscribe(self.OnOpenPatient, 'dicomgui.show')

        # Send a message to the logging system to turn on/off detailed logging
        pub.sendMessage('preferences.requested.value',
                        msg='general.advanced.detailed_logging')

        # Create the default user plugin path
        self.userpluginpath = os.path.join(datapath, 'plugins')
        if not os.path.exists(self.userpluginpath):
            os.mkdir(self.userpluginpath)

        # Load and initialize plugins
        self.plugins = []
        self.pluginsDisabled = []
        pub.sendMessage('preferences.requested.value', 
                        msg='general.plugins.user_plugins_location')
        pub.sendMessage('preferences.requested.value',
                        msg='general.calculation.dvh_recalc')
        pub.sendMessage('preferences.requested.value',
                        msg='general.plugins.disabled_list')
        pub.sendMessage('preferences.requested.values',
                        msg='general.window')

########################### Patient Loading Functions ##########################

    def OnOpenPatient(self, evt):
        """Load and show the Dicom RT Importer dialog box."""

        dicomgui.ImportDicom(self)

    def OnLoadPatientData(self, msg):
        """Update and load the patient data."""

        # Skip loading if the dataset is empty or if the dataset is the same
        if (not len(msg)) or (self.ptdata == msg):
            return
        else:
            # Unsubscribe all listeners to the raw data updated while
            # it is re-processed
            pub.unsubAll('patient.updated.raw_data')
            pub.subscribe(self.OnLoadPatientData, 'patient.updated.raw_data')
            self.ptdata = msg
            # Delete the previous notebook pages
            self.notebook.DeleteAllPages()
            # Delete the previous toolbar items
            for t in range(0, self.toolbar.GetToolsCount()):
                # Only delete the plugin toolbar items
                if (t >= len(self.maintools)):
                    self.toolbar.DeleteToolByPos(len(self.maintools))
            # Delete the previous plugin menus
            if len(self.menuDict):
                self.menuPlugins.Delete(wx.ID_SEPARATOR)
                for menuid, menu in self.menuDict.items():
                    self.menuPlugins.Delete(menuid)
                    # Remove the menu object from memory
                    del(menu)
                self.menuDict = {}
            # Delete the previous export menus
            if len(self.menuExportDict):
                self.menuExportItem.Enable(False)
                for menuid, menu in self.menuExportDict.items():
                    self.menuExport.Delete(menuid)
                    del(menu)
                self.menuExportDict = {}
            # Reset the preferences template
            self.preftemplate = [{'General':self.generalpreftemplate}]
            # Initialize the list of subplugins
            subplugins = []
            # Set up the plugins for each plugin entry point of dicompyler
            for i, plugin in enumerate(self.plugins):
                # Skip plugin if it doesn't contain the required dictionary
                # or actually is a proper Python module
                p = plugin['plugin']
                if not hasattr(p, 'pluginProperties') or \
                    (p.__name__ in self.pluginsDisabled):
                    continue
                props = p.pluginProperties()
                # Only load plugin versions that are qualified
                if (props['plugin_version'] == 1):
                    # Check whether the plugin can view the loaded DICOM data
                    add = False
                    if len(props['min_dicom']):
                        for key in props['min_dicom']:
                            if (key == 'rxdose'):
                                pass
                            elif key in self.ptdata.keys():
                                add = True
                            else:
                                add = False
                                break
                    # Plugin can view all DICOM data so always load it
                    else:
                        add = True
                    # Initialize the plugin
                    if add:
                        # Load the main panel plugins
                        if (props['plugin_type'] == 'main'):
                            plugin = p.pluginLoader(self.notebook)
                            self.notebook.AddPage(plugin, props['name'])
                        # Load the menu plugins
                        elif (props['plugin_type'] == 'menu'):
                            if not len(self.menuDict):
                                self.menuPlugins.AppendSeparator()
                            self.menuPlugins.Append(100+i, props['name']+'...')
                            plugin = p.plugin(self)
                            self.menuDict[100+i] = plugin
                            self.Bind(wx.EVT_MENU, plugin.pluginMenu, id=100+i)
                        # Load the export menu plugins
                        elif (props['plugin_type'] == 'export'):
                            if not len(self.menuExportDict):
                                self.menuExportItem.Enable(True)
                            self.menuExport.Append(200+i, props['menuname'])
                            plugin = p.plugin(self)
                            self.menuExportDict[200+i] = plugin
                            self.Bind(wx.EVT_MENU, plugin.pluginMenu, id=200+i)
                        # If a sub-plugin, mark it to be initialized later
                        else:
                            subplugins.append(p)
                            continue
                        # Add the plugin preferences if they exist
                        if hasattr(plugin, 'preferences'):
                            self.preftemplate.append({props['name']:plugin.preferences})
            pub.sendMessage('preferences.updated.template', msg=self.preftemplate)

            # Load the subplugins and notify the parent plugins
            for s in subplugins:
                props = s.pluginProperties()
                msg = 'plugin.loaded.' + props['plugin_type'] + '.' +s.__name__
                pub.sendMessage(msg, msg=s)

        dlgProgress = guiutil.get_progress_dialog(self, "Loading Patient Data...")
        self.t=threading.Thread(target=self.LoadPatientDataThread,
            args=(self, self.ptdata, dlgProgress.OnUpdateProgress,
            self.OnUpdatePatientData))
        self.t.start()
        dlgProgress.ShowModal()
        if dlgProgress:
            dlgProgress.Destroy()

    def LoadPatientDataThread(self, parent, ptdata, progressFunc, updateFunc):
        """Thread to load the patient data."""

        # Call the progress function to update the gui
        wx.CallAfter(progressFunc, 0, 0, 'Processing patient data...')
        patient = {}

        if not 'images' in ptdata:
            #Look for DICOM data in the ptdata dictionary
            for rtdatatype in ptdata.keys():
                if isinstance(ptdata[rtdatatype], pydicom.dataset.FileDataset):
                    patient.update(dp(ptdata[rtdatatype]).GetDemographics())
                    break
        if 'rtss' in ptdata:
            wx.CallAfter(progressFunc, 20, 100, 'Processing RT Structure Set...')
            d = dp(ptdata['rtss'])
            s = d.GetStructures()
            for k in s.keys():
                s[k]['planes'] = d.GetStructureCoordinates(k)
                s[k]['thickness'] = d.CalculatePlaneThickness(s[k]['planes'])
            patient['structures'] = s
        if 'rtplan' in ptdata:
            wx.CallAfter(progressFunc, 40, 100, 'Processing RT Plan...')
            patient['plan'] = dp(ptdata['rtplan']).GetPlan()
        if 'rtdose' in ptdata:
            wx.CallAfter(progressFunc, 60, 100, 'Processing RT Dose...')
            patient['dvhs'] = dp(ptdata['rtdose']).GetDVHs()
            patient['dose'] = dp(ptdata['rtdose'])
        if 'images' in ptdata:
            wx.CallAfter(progressFunc, 80, 100, 'Processing Images...')
            if not 'id' in patient:
                patient.update(dp(ptdata['images'][0]).GetDemographics())
            patient['images'] = []
            for image in ptdata['images']:
                patient['images'].append(dp(image))
        if 'rxdose' in ptdata:
            if not 'plan' in patient:
                patient['plan'] = {}
            patient['plan']['rxdose'] = ptdata['rxdose']
        # if the min/max/mean dose was not present, calculate it and save it for each structure
        wx.CallAfter(progressFunc, 90, 100, 'Processing DVH data...')
        if ('dvhs' in patient) and ('structures' in patient):
            # If the DVHs are not present, calculate them
            i = 0
            # Grabbing patient ID
            dvh_patientID = ptdata['rtdose'].PatientID
            csv_filename = str(dvh_patientID) + '.csv'

            dvh_csv_list = [] 
            # maximum dose of all ROIs
            max_roi_dose = 0
            # csv Header
            csv_header = []

            for key, structure in patient['structures'].items():
                # Initialize a list for dvh exporting to csv
                dvh_roi_list = []
                
                # Only calculate DVHs if they are not present for the structure
                # or recalc all DVHs if the preference is set
                if ((not (key in patient['dvhs'].keys())) or
                    (self.dvhRecalc == 'Always Recalculate DVH')):
                    # Only calculate DVHs for structures, not applicators
                    # and only if the dose grid is present
                    if ((structure['name'].startswith('Applicator')) or
                        (not "PixelData" in patient['dose'].ds)):
                        continue
                    wx.CallAfter(progressFunc,
                                 10*i/len(patient['structures'])+90, 100,
                                 'Calculating DVH for ' + structure['name'] +
                                 '...')
                    # Limit DVH bins to 500 Gy due to high doses in brachy
                    dvh = dvhcalc.get_dvh(ptdata['rtss'], patient['dose'].ds, key, 50000)
                    # Retrieve roi name
                    dvh_roiName = dvh.name
                    # Retrieve roi dvh volume
                    dvh_roiVolume = dvh.volume
                    # Append info
                    dvh_roi_list.append(dvh_patientID)
                    dvh_roi_list.append(dvh_roiName)
                    dvh_roi_list.append(dvh_roiVolume)
                    # 
                    dvh_roiDose = dvh.relative_volume.counts

                    for i in range(0, len(dvh_roiDose)+1, 10):
                        dvh_roi_list.append(dvh_roiDose[i])
                        if i > max_roi_dose:
                            max_roi_dose = i

                    dvh_csv_list.append(dvh_roi_list)

                    if len(dvh.counts):
                        patient['dvhs'][key] = dvh
                    i += 1

            csv_header.append('Hash ID')
            csv_header.append('ROI')
            csv_header.append('Volume (mL)')

            print(max_roi_dose)

            for i in range(0, max_roi_dose+1, 10):
                csv_header.append(str(i)+'cGy')
            
            pddf_csv = pd.DataFrame(dvh_csv_list, columns=csv_header).round(2)
            pddf_csv.fillna(0.0, inplace=True)

            pddf_csv.to_csv(csv_filename)
                
            for key, dvh in patient['dvhs'].items():
                dvh.rx_dose = patient['plan']['rxdose'] / 100

        wx.CallAfter(progressFunc, 100, 100, 'Done')
        wx.CallAfter(updateFunc, patient)

    def OnUpdatePatientData(self, patient):
        """Update the patient data in the main program interface."""

        self.PopulateDemographics(patient)

        self.structures = {}
        if 'structures' in patient:
            self.structures = patient['structures']
        self.PopulateStructures()

        if 'plan' in patient:
            self.PopulatePlan(patient['plan'])
        else:
            self.PopulatePlan({})

        if ('dose' in patient and 'plan' in patient):
            self.PopulateIsodoses('images' in patient, patient['plan'], patient['dose'])
        else:
            self.PopulateIsodoses('images' in patient, {}, {})

        if 'dvhs' in patient:
            self.dvhs = patient['dvhs']
        else:
            self.dvhs = {}

        # Re-publish the raw data
        pub.sendMessage('patient.updated.raw_data', msg=self.ptdata)
        # Publish the parsed data
        pub.sendMessage('patient.updated.parsed_data', msg=patient)

    def PopulateStructures(self):
        """Populate the structure list."""

        self.cclbStructures.Clear()

        self.structureList = {}
        for id, structure in iter(sorted(self.structures.items())):
            # Only append structures, don't include applicators
            if not(structure['name'].startswith('Applicator')):
                self.cclbStructures.Append(structure['name'], structure, structure['color'],
                    refresh=False)
        # Refresh the structure list manually since we didn't want it to refresh
        # after adding each structure
        self.cclbStructures.Layout()
        self.choiceStructure.Clear()
        self.choiceStructure.Enable(False)
        self.OnStructureUnselect()

    def PopulateIsodoses(self, has_images, plan, dose):
        """Populate the isodose list."""

        self.cclbIsodoses.Clear()

        self.isodoseList={}
        if (has_images and len(plan) and "PixelData" in dose.ds):
            dosedata = dose.GetDoseData()
            dosemax = int(dosedata['dosemax'] * dosedata['dosegridscaling'] * 10000 / plan['rxdose'])
            self.isodoses = [{'level':dosemax, 'color':wx.Colour(120, 0, 0), 'name':'Max'},
                {'level':102, 'color':wx.Colour(170, 0, 0)},
                {'level':100, 'color':wx.Colour(238, 69, 0)}, {'level':98, 'color':wx.Colour(255, 165, 0)},
                {'level':95, 'color':wx.Colour(255, 255, 0)}, {'level':90, 'color':wx.Colour(0, 255, 0)},
                {'level':80, 'color':wx.Colour(0, 139, 0)}, {'level':70, 'color':wx.Colour(0, 255, 255)},
                {'level':50, 'color':wx.Colour(0, 0, 255)}, {'level':30, 'color':wx.Colour(0, 0, 128)}]
            for isodose in self.isodoses:
                # Calculate the absolute dose value
                name = ' / ' + str("%.6g" %
                (float(isodose['level']) * float(plan['rxdose']) / 100)) + \
                ' cGy'
                if 'name' in isodose:
                    name = name + ' [' + isodose['name'] + ']'
                self.cclbIsodoses.Append(str(isodose['level'])+' %'+name, isodose, isodose['color'],
                    refresh=False)
        # Refresh the isodose list manually since we didn't want it to refresh
        # after adding each isodose
        self.cclbIsodoses.Layout()

    def PopulateDemographics(self, demographics):
        """Populate the patient demographics."""

        self.lblPatientName.SetLabel(str(demographics['name']))
        self.lblPatientID.SetLabel(demographics['id'])
        self.lblPatientGender.SetLabel(demographics['gender'])
        self.lblPatientDOB.SetLabel(str(demographics['birth_date']))

    def PopulatePlan(self, plan):
        """Populate the patient's plan information."""

        if (len(plan) and not plan['rxdose'] == 1):
            if 'name' in plan:
                if len(plan['name']):
                    self.lblPlanName.SetLabel(plan['name'])
                elif len(plan['label']):
                    self.lblPlanName.SetLabel(plan['label'])
            self.lblRxDose.SetLabel(str("%.6g" % plan['rxdose']))
        else:
            self.lblPlanName.SetLabel('-')
            self.lblRxDose.SetLabel('-')

############################## Structure Functions #############################

    def OnStructureCheck(self, msg):
        """Load the properties of the currently checked structures."""

        structure = msg

        # Get the structure number
        id = structure['data']['id']
        structure['data']['color'] = structure['color'].Get()

        # Make sure that the volume has been calculated for each structure
        # before setting it
        if not 'volume' in self.structures[id]:
            # Use the volume units from the DVH if they are absolute volume
            if id in self.dvhs and (self.dvhs[id].volume_units == 'cm3'):
                self.structures[id]['volume'] = self.dvhs[id].volume
            # Otherwise calculate the volume from the structure data
            else:
                self.structures[id]['volume'] = dvhdata.CalculateVolume(
                                                    self.structures[id])
            structure['data']['volume'] = self.structures[id]['volume']
        self.structureList[id] = structure['data']

        # Populate the structure choice box with the checked structures
        self.choiceStructure.Enable()
        i = self.choiceStructure.Append(structure['data']['name'])
        self.choiceStructure.SetClientData(i, id)
        # Select the first structure
        self.OnStructureSelect()

        pub.sendMessage('structures.checked', msg=self.structureList)

    def OnStructureUncheck(self, msg):
        """Remove the unchecked structures."""

        structure = msg

        # Get the structure number
        id = structure['data']['id']

        # Remove the structure from the structure list
        if id in self.structureList:
            del self.structureList[id]

        # Remove the structure from the structure choice box
        for n in range(self.choiceStructure.GetCount()):
            if (id == self.choiceStructure.GetClientData(n)):
                # Save if the currently selected item's position
                currSelection = self.choiceStructure.GetSelection()
                self.choiceStructure.Delete(n)
                break

        # If the currently selected item will be deleted,
        # select the last item instead
        if (n == currSelection):
            if (self.choiceStructure.GetCount() >= 1):
                self.OnStructureSelect()
        # Disable the control if it is the last item
        if (self.choiceStructure.GetCount() == 0):
            self.choiceStructure.Enable(False)
            self.OnStructureUnselect()

        pub.sendMessage('structures.checked', msg=self.structureList)

    def OnStructureSelect(self, evt=None):
        """Load the properties of the currently selected structure."""

        if (evt == None):
            self.choiceStructure.SetSelection(0)
            choiceItem = 0
        else:
            choiceItem = evt.GetInt()
        # Load the structure id chosen from the choice control
        id = self.choiceStructure.GetClientData(choiceItem)

        pub.sendMessage('structure.selected', msg={'id':id})

        self.lblStructureVolume.SetLabel(str(self.structures[id]['volume'])[0:7])
        # make sure that the dvh has been calculated for each structure
        # before setting it
        if id in self.dvhs:
            self.lblStructureMinDose.SetLabel("%.3f" % self.dvhs[id].min)
            self.lblStructureMaxDose.SetLabel("%.3f" % self.dvhs[id].max)
            self.lblStructureMeanDose.SetLabel("%.3f" % self.dvhs[id].mean)
        else:
            self.lblStructureMinDose.SetLabel('-')
            self.lblStructureMaxDose.SetLabel('-')
            self.lblStructureMeanDose.SetLabel('-')

    def OnStructureUnselect(self):
        """Clear the properties of the selected structure."""

        pub.sendMessage('structures.selected', msg={'id':None})

        self.lblStructureVolume.SetLabel('-')
        self.lblStructureMinDose.SetLabel('-')
        self.lblStructureMaxDose.SetLabel('-')
        self.lblStructureMeanDose.SetLabel('-')

############################### Isodose Functions ##############################

    def OnIsodoseCheck(self, msg):
        """Load the properties of the currently checked isodoses."""

        isodose = msg
        self.isodoseList[isodose['data']['level']] = isodose

        pub.sendMessage('isodoses.checked', msg=self.isodoseList)

    def OnIsodoseUncheck(self, msg):
        """Remove the unchecked isodoses."""

        isodose = msg
        id = isodose['data']['level']

        # Remove the isodose from the isodose list
        if id in self.isodoseList:
            del self.isodoseList[id]

        pub.sendMessage('isodoses.checked', msg=self.isodoseList)

################################ Other Functions ###############################

    def InstallThreadExcepthook(self):
        """Workaround for sys.excepthook thread bug from Jonathan Ellis
            (http://bugs.python.org/issue1230540).
            Call once from __main__ before creating any threads.
            If using psyco, call psyco.cannotcompile(threading.Thread.run)
            since this replaces a new-style class method."""

        run_old = threading.Thread.run
        def Run(*args, **kwargs):
            try:
                run_old(*args, **kwargs)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                sys.excepthook(*sys.exc_info())
        threading.Thread.run = Run

    def OnUpdatePreferences(self, topic, msg):
        """When the preferences change, update the values."""
        topic = topic.split('.')
        if (topic[1] == 'calculation') and (topic[2] == 'dvh_recalc'):
            self.dvhRecalc = msg
        elif (topic[1] == 'advanced') and \
                (topic[2] == 'detailed_logging'):
                    # Enable logging at the debug level if the value is set
                    if msg:
                        self.fh.setLevel(logging.DEBUG)
                        if not util.main_is_frozen():
                            self.ch.setLevel(logging.DEBUG)
                    else:
                        self.fh.setLevel(logging.WARNING)
                        if not util.main_is_frozen():
                            self.ch.setLevel(logging.WARNING)
        elif (topic[1] == 'plugins') and (topic[2] == 'disabled_list'):
            self.pluginsDisabled = msg
        elif (topic[1] == 'window'):
            if topic[2] == 'maximized':
                self.Maximize(msg)
            elif topic[2] == 'size':
                if not self.IsMaximized():
                    self.SetSize(tuple(msg))
            elif topic[2] == 'position':
                if not self.IsMaximized():
                    self.SetPosition(tuple(msg))

    def OnUpdatePlugins(self, topic, msg):
        """Update the location of the user plugins and load all plugins."""

        self.userpluginpath = msg
        # Load the plugins only if they haven't been loaded previously
        if not len(self.plugins):
            self.plugins = plugin.import_plugins(self.userpluginpath)
            self.menuDict = {}
            self.menuImportDict = {}
            self.menuExportDict = {}
            # Set up the import plugins for dicompyler
            for i, pg in enumerate(self.plugins):
                # Skip plugin if it doesn't contain the required dictionary
                # or actually is a proper Python module or is disabled
                p = pg['plugin']
                if not hasattr(p, 'pluginProperties') or \
                    (p.__name__ in self.pluginsDisabled):
                    continue
                props = p.pluginProperties()
                # Only load plugin versions that are qualified
                if ((props['plugin_version'] == 1) and
                    (props['plugin_type'] == 'import')):
                    self.menuImportItem.Enable(True)
                    # Load the import menu plugins
                    if not len(self.menuImportDict):
                        self.menuImportItem.Enable(True)
                    self.menuImportDict[300+i] = self.menuImport.Append(
                                        300+i, props['menuname'])
                    pi = p.plugin(self)
                    self.Bind(wx.EVT_MENU, pi.pluginMenu, id=300+i)
                    # If the import plugin has toolbar items, display them
                    if hasattr(pi, 'tools'):
                        for t, tool in enumerate(pi.tools):
                            self.maintools.append(tool)
                            self.toolbar.AddTool(
                                        (300+i)*10+t, tool['label'],
                                        tool['bmp'], shortHelp=tool['shortHelp'])
                            self.Bind(wx.EVT_TOOL, tool['eventhandler'], id=(300+i)*10+t)
                        self.toolbar.Realize()
    def OnUpdateStatusBar(self, msg):
        """Update the status bar text."""

        for k, v in msg.items():
            self.sb.SetStatusText(str(v), k)

    def OnPageChanged(self, evt):
        """Notify each notebook tab whether it has the focus or not."""

        # Determine the new tab
        new = evt.GetSelection()
        page = self.notebook.GetPage(new)
        # Notify the new tab that it has focus
        if hasattr(page, 'OnFocus'):
            page.OnFocus()
        # If the tab has toolbar items, display them
        if hasattr(page, 'tools'):
            for t, tool in enumerate(page.tools):
                self.toolbar.AddTool(
                            (new+1)*10+t, tool['label'],
                            tool['bmp'], shortHelp=tool['shortHelp'])
                self.Bind(wx.EVT_TOOL, tool['eventhandler'], id=(new+1)*10+t)
            self.toolbar.Realize()
        # For all other tabs, notify that they don't have focus anymore
        for i in range(self.notebook.GetPageCount()):
            if not (new == i):
                page = self.notebook.GetPage(i)
                if hasattr(page, 'OnUnfocus'):
                    page.OnUnfocus()
                # Delete all other toolbar items
                if hasattr(page, 'tools'):
                    for t, tool in enumerate(page.tools):
                        self.toolbar.DeleteTool((i+1)*10+t)
        evt.Skip()

    def OnKeyDown(self, evt):
        """Capture the keypress when the notebook tab is focused.
            Currently this is used to workaround a bug in Windows since the
            notebook tab instead of the panel receives focus."""

        if guiutil.IsMSWindows():
            pub.sendMessage('main.key_down', evt=evt)

    def OnMouseWheel(self, evt):
        """Capture the mousewheel event when the notebook tab is focused.
            Currently this is used to workaround a bug in Windows since the
            notebook tab instead of the panel receives focus."""

        if guiutil.IsMSWindows():
            pub.sendMessage('main.mousewheel', evt=evt)

    def OnPreferences(self, evt):
        """Load and show the Preferences dialog box."""

        self.prefmgr.Show()

    def OnShowLogs(self, evt):
        """Open and display the logs folder."""

        util.open_path(os.path.join(guiutil.get_data_dir(), 'logs'))

    def OnPluginManager(self, evt):
        """Load and show the Plugin Manager dialog box."""

        self.pm = plugin.PluginManager(self, self.plugins, self.pluginsDisabled)

    def OnAbout(self, evt):
        # First we create and fill the info object
        info = wx.adv.AboutDialogInfo()
        info.Name = "dicompyler"
        info.Version = __version__
        info.Copyright = "(c) 2009-2017 Aditya Panchal"
        credits = util.get_credits()
        info.Developers = credits['developers']
        info.Artists = credits['artists']
        desc =  "Extensible radiation therapy research platform and viewer for DICOM and DICOM RT." + \
                "\n\ndicompyler is released under a BSD license.\n" + \
                "See the Help menu for license information."
        info.Description = desc
        if guiutil.IsGtk():
            info.WebSite = "https://github.com/bastula/dicompyler/"

        # Then we call wx.AboutBox giving it that info object
        wx.adv.AboutBox(info)

    def OnHomepage(self, evt):
        """Show the homepage for dicompyler."""

        webbrowser.open_new_tab("https://github.com/bastula/dicompyler/")
        
    def OnLicense(self, evt):
        """Show the license document in a new dialog."""
        
        f = open(util.get_text_resources("license.txt"), "rU")
        msg = f.read()
        f.close()

        if guiutil.IsMSWindows():
            dlg = wx.lib.dialogs.ScrolledMessageDialog(self, msg,
                "dicompyler License")
        else:
            dlg = wx.lib.dialogs.ScrolledMessageDialog(self, msg,
                "dicompyler License", size=(650, 550))

        dlg.ShowModal()
        dlg.Destroy()

    def OnActivate(self, evt):
        """Show the import dialog if command-line arguments have been passed."""

        # Check if a folder is provided via command-line arguments
        if (len(sys.argv) == 2):
            path = sys.argv[1]
            if not os.path.isdir(path):
                path = os.path.split(path)[0]
            pub.sendMessage('preferences.updated.value',
                        msg={'general.dicom.import_location':path})
            sys.argv.pop()
            self.OnOpenPatient(None)
        evt.Skip()

    def OnClose(self, _):
        pub.sendMessage('preferences.updated.value',
                msg={'general.window.maximized':self.IsMaximized()})
        if not self.IsMaximized():
            pub.sendMessage('preferences.updated.value',
                    msg={'general.window.size':tuple(self.GetSize())})
            pub.sendMessage('preferences.updated.value',
                    msg={'general.window.position':tuple(self.GetPosition())})
        self.Destroy()
        sys.exit(0)

class dicompyler(wx.App):
    def OnInit(self):
        wx.GetApp().SetAppName("dicompyler")

        # Load the XRC file for our gui resources
        self.res = XmlResource(util.GetResourcePath('main.xrc'))

        dicompylerFrame = MainFrame(None, -1, "dicompyler", self.res)
        self.SetTopWindow(dicompylerFrame)
        dicompylerFrame.Show()
        return 1

# end of class dicompyler

def start():
    app = dicompyler(0)
    app.MainLoop()

if __name__ == '__main__':
    start()
