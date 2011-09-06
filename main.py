#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# main.py
"""Main file for dicompyler."""
# Copyright (c) 2009-2011 Aditya Panchal
# Copyright (c) 2009 Roy Keyes
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

import os, threading
import wx
from wx.xrc import *
import wx.lib.dialogs, webbrowser
# Uncomment line to setup pubsub for frozen targets on wxPython 2.8.11 and above
# from wx.lib.pubsub import setupv1
from wx.lib.pubsub import Publisher as pub
import guiutil, util
import dicomgui, dvhdata, dvhdoses, dvhcalc
from dicomparser import DicomParser as dp
import plugin, preferences

__version__ = "0.4a2"

class MainFrame(wx.Frame):
    def __init__(self, parent, id, title, res):

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

        # Modify the control and font size on Mac
        controls = [self.notebookTools, self.choiceStructure]

        if guiutil.IsMac():
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
            font.SetPointSize(10)
            for control in controls:
                control.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)
                control.SetFont(font)

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
            wx.App_SetMacAboutMenuItemId(XRCID('menuAbout'))
            wx.App_SetMacPreferencesMenuItemId(XRCID('menuPreferences'))
            wx.App_SetMacExitMenuItemId(XRCID('menuExit'))

        # Set the menu as the default menu for this frame
        self.SetMenuBar(menuMain)

        # Setup Plugins menu
        self.menuPlugins = menuMain.FindItemById(XRCID('menuPluginManager')).GetMenu()

        # Setup Export menu
        self.menuExport = menuMain.FindItemById(XRCID('menuExportPlaceholder')).GetMenu()
        self.menuExport.Delete(menuMain.FindItemById(XRCID('menuExportPlaceholder')).GetId())
        self.menuExportItem = menuMain.FindItemById(XRCID('menuExport'))
        self.menuExportItem.Enable(False)

        # Bind menu events to the proper methods
        wx.EVT_MENU(self, XRCID('menuOpen'), self.OnOpenPatient)
        wx.EVT_MENU(self, XRCID('menuExit'), self.OnClose)
        wx.EVT_MENU(self, XRCID('menuPreferences'), self.OnPreferences)
        wx.EVT_MENU(self, XRCID('menuPluginManager'), self.OnPluginManager)
        wx.EVT_MENU(self, XRCID('menuAbout'), self.OnAbout)
        wx.EVT_MENU(self, XRCID('menuHomepage'), self.OnHomepage)
        wx.EVT_MENU(self, XRCID('menuLicense'), self.OnLicense)

        # Load the toolbar for the frame
        toolbarMain = self.res.LoadToolBar(self, 'toolbarMain')
        self.SetToolBar(toolbarMain)
        self.toolbar = self.GetToolBar()

        # Setup main toolbar controls
        if guiutil.IsGtk():
            import gtk
            folderbmp = wx.ArtProvider_GetBitmap(gtk.STOCK_OPEN, wx.ART_OTHER, (24, 24))
        else:
            folderbmp = wx.Bitmap(util.GetResourcePath('folder_user.png'))
        self.maintools = [{'label':"Open Patient", 'bmp':folderbmp,
                            'shortHelp':"Open Patient...",
                            'eventhandler':self.OnOpenPatient}]
        for m, tool in enumerate(self.maintools):
            self.toolbar.AddLabelTool(
                                    m+1, tool['label'], tool['bmp'],
                                    shortHelp=tool['shortHelp'])
            self.Bind(wx.EVT_TOOL, tool['eventhandler'], id=m+1)
        self.toolbar.Realize()

        # Bind interface events to the proper methods
        wx.EVT_CHOICE(self, XRCID('choiceStructure'), self.OnStructureSelect)
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
                parent = None, appname = 'dicompyler')
        else:
            self.prefmgr = preferences.PreferencesManager(
                parent = None, appname = 'dicompyler', name = 'Options')
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
              'default':unicode(sp.GetDocumentsDir()),
             'callback':'general.dicom.import_location'}]
            },
            {'Plugin Settings':
                [{'name':'User Plugins Location',
                 'type':'directory',
              'default':unicode(os.path.join(datapath, 'plugins')),
             'callback':'general.plugins.user_plugins_location',
             'restart':True}]
            }]
        self.preftemplate = [{'General':self.generalpreftemplate}]
        pub.sendMessage('preferences.updated.template', self.preftemplate)

        # Set up pubsub
        pub.subscribe(self.OnLoadPatientData, 'patient.updated.raw_data')
        pub.subscribe(self.OnStructureCheck, 'colorcheckbox.checked.structure')
        pub.subscribe(self.OnStructureUncheck, 'colorcheckbox.unchecked.structure')
        pub.subscribe(self.OnIsodoseCheck, 'colorcheckbox.checked.isodose')
        pub.subscribe(self.OnIsodoseUncheck, 'colorcheckbox.unchecked.isodose')
        pub.subscribe(self.OnUpdatePlugins, 'general.plugins.user_plugins_location')
        pub.subscribe(self.OnUpdateStatusBar, 'main.update_statusbar')

        # Create the default user plugin path
        self.userpluginpath = os.path.join(datapath, 'plugins')
        if not os.path.exists(self.userpluginpath):
            os.mkdir(self.userpluginpath)

        # Load and initialize plugins
        self.plugins = []
        pub.sendMessage('preferences.requested.value',
                        'general.plugins.user_plugins_location')

########################### Patient Loading Functions ##########################

    def OnOpenPatient(self, evt):
        """Load and show the Dicom RT Importer dialog box."""

        self.ptdata = dicomgui.ImportDicom(self)
        if not (self.ptdata == None):
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
                for menuid, menu in self.menuDict.iteritems():
                    self.menuPlugins.Delete(menuid)
                self.menuDict = {}
            # Delete the previous export menus
            if len(self.menuExportDict):
                self.menuExportItem.Enable(False)
                for menuid, menu in self.menuExportDict.iteritems():
                    self.menuExport.Delete(menuid)
                self.menuExportDict = {}
            # Reset the preferences template
            self.preftemplate = [{'General':self.generalpreftemplate}]
            # Set up the plugins for each plugin entry point of dicompyler
            for i, p in enumerate(self.plugins):
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
                        if (props['plugin_type'] == 'menu'):
                            if not len(self.menuDict):
                                self.menuPlugins.AppendSeparator()
                            self.menuDict[100+i] = self.menuPlugins.Append(
                                                100+i, props['name']+'...')
                            plugin = p.plugin(self)
                            wx.EVT_MENU(self, 100+i, plugin.pluginMenu)
                        # Load the export menu plugins
                        if (props['plugin_type'] == 'export'):
                            if not len(self.menuExportDict):
                                self.menuExportItem.Enable(True)
                            self.menuExportDict[200+i] = self.menuExport.Append(
                                                200+i, props['menuname'])
                            plugin = p.plugin(self)
                            wx.EVT_MENU(self, 200+i, plugin.pluginMenu)
                        # Add the plugin preferences if they exist
                        if hasattr(plugin, 'preferences'):
                            self.preftemplate.append({props['name']:plugin.preferences})
            pub.sendMessage('preferences.updated.template', self.preftemplate)
            pub.sendMessage('patient.updated.raw_data', self.ptdata)

    def OnLoadPatientData(self, msg):
        """Update and load the patient data."""

        ptdata = msg.data
        dlgProgress = guiutil.get_progress_dialog(self, "Loading Patient Data...")
        self.t=threading.Thread(target=self.LoadPatientDataThread,
            args=(self, ptdata, dlgProgress.OnUpdateProgress,
            self.OnUpdatePatientData))
        self.t.start()
        dlgProgress.ShowModal()
        dlgProgress.Destroy()

    def LoadPatientDataThread(self, parent, ptdata, progressFunc, updateFunc):
        """Thread to load the patient data."""

        # Call the progress function to update the gui
        wx.CallAfter(progressFunc, 0, 0, 'Processing patient data...')
        patient = {}
        if ptdata.has_key('rtss'):
            wx.CallAfter(progressFunc, 20, 100, 'Processing RT Structure Set...')
            if not patient.has_key('id'):
                patient = dp(ptdata['rtss']).GetDemographics()
            patient['structures'] = dp(ptdata['rtss']).GetStructures()
        if ptdata.has_key('rtplan'):
            wx.CallAfter(progressFunc, 40, 100, 'Processing RT Plan...')
            if not patient.has_key('id'):
                patient = dp(ptdata['rtplan']).GetDemographics()
            patient['plan'] = dp(ptdata['rtplan']).GetPlan()
        if ptdata.has_key('rtdose'):
            wx.CallAfter(progressFunc, 60, 100, 'Processing RT Dose...')
            if not patient.has_key('id'):
                patient = dp(ptdata['rtdose']).GetDemographics()
            patient['dvhs'] = dp(ptdata['rtdose']).GetDVHs()
            patient['dose'] = dp(ptdata['rtdose'])
        if ptdata.has_key('images'):
            wx.CallAfter(progressFunc, 80, 100, 'Processing Images...')
            if not patient.has_key('id'):
                patient = dp(ptdata['images'][0]).GetDemographics()
            patient['images'] = []
            for image in ptdata['images']:
                patient['images'].append(dp(image))
        if ptdata.has_key('rxdose'):
            if not patient.has_key('plan'):
                patient['plan'] = {}
            patient['plan']['rxdose'] = ptdata['rxdose']
        # if the min/max/mean dose was not present, calculate it and save it for each structure
        wx.CallAfter(progressFunc, 90, 100, 'Processing DVH data...')
        if ('dvhs' in patient) and ('structures' in patient):
            # If the DVHs are not present, calculate them
            i = 0
            for key, structure in patient['structures'].iteritems():
                # Only calculate DVHs if they are not present for the structure
                if not (key in patient['dvhs'].keys()):
                    wx.CallAfter(progressFunc,
                                 10*i/len(patient['structures'])+90, 100,
                                 'Calculating DVH for ' + structure['name'] +
                                 '...')
                    # Limit DVH bins to 500 Gy due to high doses in brachy
                    dvh = dvhcalc.get_dvh(structure, patient['dose'], 50000)
                    if len(dvh['data']):
                        patient['dvhs'][key] = dvh
                    i += 1
            for key, dvh in patient['dvhs'].iteritems():
                self.CalculateDoseStatistics(dvh, ptdata['rxdose'])
        wx.CallAfter(progressFunc, 100, 100, 'Done')
        wx.CallAfter(updateFunc, patient)

    def CalculateDoseStatistics(self, dvh, rxdose):
        """Calculate the dose statistics for the given DVH and rx dose."""

        sfdict = {'min':dvhdoses.get_dvh_min,
                  'mean':dvhdoses.get_dvh_mean,
                  'max':dvhdoses.get_dvh_max}

        for stat, func in sfdict.iteritems():
            # Only calculate stat if the stat was not calculated previously (-1)
            if dvh[stat] == -1:
                dvh[stat] = 100*func(dvh['data']*dvh['scaling'])/rxdose

        return dvh

    def OnUpdatePatientData(self, patient):
        """Update the patient data in the main program interface."""

        self.PopulateDemographics(patient)

        self.structures = {}
        if patient.has_key('structures'):
            self.structures = patient['structures']
        self.PopulateStructures()

        if patient.has_key('plan'):
            self.PopulatePlan(patient['plan'])
        else:
            self.PopulatePlan({})

        if (patient.has_key('dose') and patient.has_key('plan')):
            self.PopulateIsodoses(patient.has_key('images'), patient['plan'], patient['dose'])
        else:
            self.PopulateIsodoses(patient.has_key('images'), {}, {})

        if patient.has_key('dvhs'):
            self.dvhs = patient['dvhs']
        else:
            self.dvhs = {}
        
        # publish the parsed data
        pub.sendMessage('patient.updated.parsed_data', patient)

    def PopulateStructures(self):
        """Populate the structure list."""

        self.cclbStructures.Clear()

        self.structureList = {}
        for id, structure in self.structures.iteritems():
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
        if (has_images and len(plan)):
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
                name = ' / ' + unicode("%.6g" %
                (float(isodose['level']) * float(plan['rxdose']) / 100)) + \
                ' cGy'
                if isodose.has_key('name'):
                    name = name + ' [' + isodose['name'] + ']'
                self.cclbIsodoses.Append(str(isodose['level'])+' %'+name, isodose, isodose['color'],
                    refresh=False)
        # Refresh the isodose list manually since we didn't want it to refresh
        # after adding each isodose
        self.cclbIsodoses.Layout()

    def PopulateDemographics(self, demographics):
        """Populate the patient demographics."""

        self.lblPatientName.SetLabel(demographics['name'])
        self.lblPatientID.SetLabel(demographics['id'])
        self.lblPatientGender.SetLabel(demographics['gender'])
        self.lblPatientDOB.SetLabel(demographics['dob'])

    def PopulatePlan(self, plan):
        """Populate the patient's plan information."""

        if (len(plan) and not plan['rxdose'] == 1):
            if plan.has_key('name'):
                if len(plan['name']):
                    self.lblPlanName.SetLabel(plan['name'])
                elif len(plan['label']):
                    self.lblPlanName.SetLabel(plan['label'])
            self.lblRxDose.SetLabel(unicode("%.6g" % plan['rxdose']))
        else:
            self.lblPlanName.SetLabel('-')
            self.lblRxDose.SetLabel('-')

############################## Structure Functions #############################

    def OnStructureCheck(self, msg):
        """Load the properties of the currently checked structures."""

        structure = msg.data

        # Get the structure number
        id = structure['data']['id']
        structure['data']['color'] = structure['color'].Get()

        # Make sure that the volume has been calculated for each structure
        # before setting it
        if not self.structures[id].has_key('volume'):
            # Use the volume units from the DVH if they are absolute volume
            if self.dvhs.has_key(id) and (self.dvhs[id]['volumeunits'] == 'CM3'):
                self.structures[id]['volume'] = self.dvhs[id]['data'][0]
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

        pub.sendMessage('structures.checked', self.structureList)

    def OnStructureUncheck(self, msg):
        """Remove the unchecked structures."""

        structure = msg.data

        # Get the structure number
        id = structure['data']['id']

        # Remove the structure from the structure list
        if self.structureList.has_key(id):
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

        pub.sendMessage('structures.checked', self.structureList)

    def OnStructureSelect(self, evt=None):
        """Load the properties of the currently selected structure."""

        if (evt == None):
            self.choiceStructure.SetSelection(0)
            choiceItem = 0
        else:
            choiceItem = evt.GetInt()
        # Load the structure id chosen from the choice control
        id = self.choiceStructure.GetClientData(choiceItem)

        pub.sendMessage('structure.selected', {'id':id})

        self.lblStructureVolume.SetLabel(str(self.structures[id]['volume'])[0:7])
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

    def OnStructureUnselect(self):
        """Clear the properties of the selected structure."""

        pub.sendMessage('structures.selected', {'id':None})

        self.lblStructureVolume.SetLabel('-')
        self.lblStructureMinDose.SetLabel('-')
        self.lblStructureMaxDose.SetLabel('-')
        self.lblStructureMeanDose.SetLabel('-')

############################### Isodose Functions ##############################

    def OnIsodoseCheck(self, msg):
        """Load the properties of the currently checked isodoses."""

        isodose = msg.data
        self.isodoseList[isodose['data']['level']] = isodose

        pub.sendMessage('isodoses.checked', self.isodoseList)

    def OnIsodoseUncheck(self, msg):
        """Remove the unchecked isodoses."""

        isodose = msg.data
        id = isodose['data']['level']

        # Remove the isodose from the isodose list
        if self.isodoseList.has_key(id):
            del self.isodoseList[id]

        pub.sendMessage('isodoses.checked', self.isodoseList)

################################ Other Functions ###############################

    def OnUpdatePlugins(self, msg):
        """Update the location of the user plugins and load all plugins."""

        self.userpluginpath = msg.data
        # Load the plugins only if they haven't been loaded previously
        if not len(self.plugins):
            self.plugins = plugin.import_plugins(self.userpluginpath)
            self.menuDict = {}
            self.menuExportDict = {}

    def OnUpdateStatusBar(self, msg):
        """Update the status bar text."""

        for k, v in msg.data.iteritems():
            self.sb.SetStatusText(unicode(v), k)

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
                self.toolbar.AddLabelTool(
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
            pub.sendMessage('main.key_down', evt)

    def OnMouseWheel(self, evt):
        """Capture the mousewheel event when the notebook tab is focused.
            Currently this is used to workaround a bug in Windows since the
            notebook tab instead of the panel receives focus."""

        if guiutil.IsMSWindows():
            pub.sendMessage('main.mousewheel', evt)

    def OnPreferences(self, evt):
        """Load and show the Preferences dialog box."""

        self.prefmgr.Show()

    def OnPluginManager(self, evt):
        """Load and show the Plugin Manager dialog box."""

        self.pm = plugin.PluginManager(self, self.plugins)

    def OnAbout(self, evt):
        # First we create and fill the info object
        info = wx.AboutDialogInfo()
        info.Name = "dicompyler"
        info.Version = __version__
        info.Copyright = u"© 2009-2011 Aditya Panchal"
        credits = util.get_credits()
        info.Developers = credits['developers']
        info.Artists = credits['artists']
        desc =  "Extensible radiation therapy research platform and viewer for DICOM and DICOM RT." + \
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

    def OnClose(self, _):
        self.Destroy()

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
