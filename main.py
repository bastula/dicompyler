#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

import os
import wx
from wx.xrc import *
from model import *
import guiutil, util
import dicomgui, dicomparser, dvh, guidvh

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
        if util.main_is_frozen():
            import sys
            exeName = sys.executable
            icon = wx.Icon(exeName, wx.BITMAP_TYPE_ICO)
        elif guiutil.IsGtk():
            icon = wx.Icon(util.GetResourcePath('dicompyler_icon11_16.png'), wx.BITMAP_TYPE_PNG)
        else:
            icon = wx.Icon(util.GetResourcePath('dicompyler.ico'), wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)

        # Load the main panel for the program
        self.panelGeneral = self.res.LoadPanel(self, 'panelGeneral')
        self.guiDVH = guidvh.guiDVH(self)
        self.res.AttachUnknownControl('panelDVH', self.guiDVH.panelDVH, self)

        # Initialize the General panel controls
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

        # Initialize the Constraint selector controls
        self.radioVolume = XRCCTRL(self, 'radioVolume')
        self.radioDose = XRCCTRL(self, 'radioDose')
        self.radioDosecc = XRCCTRL(self, 'radioDosecc')
        self.txtConstraint = XRCCTRL(self, 'txtConstraint')
        self.sliderConstraint = XRCCTRL(self, 'sliderConstraint')
        self.lblConstraintUnits = XRCCTRL(self, 'lblConstraintUnits')
        self.lblConstraintPercent = XRCCTRL(self, 'lblConstraintPercent')

        # Initialize the Constraint selector labels
        self.lblConstraintType = XRCCTRL(self, 'lblConstraintType')
        self.lblConstraintTypeUnits = XRCCTRL(self, 'lblConstraintTypeUnits')
        self.lblConstraintResultUnits = XRCCTRL(self, 'lblConstraintResultUnits')

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

        # If we are running on Mac OS X, alter the menu location
        if guiutil.IsMac():
            wx.App_SetMacAboutMenuItemId(XRCID('menuAbout'))
            wx.App_SetMacExitMenuItemId(XRCID('menuExit'))

        # Set the menu as the default menu for this frame
        self.SetMenuBar(menuMain)

        # Bind menu events to the proper methods
        wx.EVT_MENU(self, XRCID('menuOpen'), self.OnOpenPatient)
        wx.EVT_MENU(self, XRCID('menuExit'), self.OnClose)
        wx.EVT_MENU(self, XRCID('menuAbout'), self.OnAbout)

        # Load the toolbar for the frame
        toolbarMain = self.res.LoadToolBar(self, 'toolbarMain')
        self.SetToolBar(toolbarMain)

        # Bind interface events to the proper methods
        wx.EVT_TOOL(self, XRCID('toolOpen'), self.OnOpenPatient)

        # Bind ui events to the proper methods
        wx.EVT_LISTBOX(self, XRCID('lbStructures'), self.OnStructureSelect)
        wx.EVT_RADIOBUTTON(self, XRCID('radioVolume'), self.OnToggleConstraints)
        wx.EVT_RADIOBUTTON(self, XRCID('radioDose'), self.OnToggleConstraints)
        wx.EVT_RADIOBUTTON(self, XRCID('radioDosecc'), self.OnToggleConstraints)
        wx.EVT_SPINCTRL(self, XRCID('txtConstraint'), self.OnChangeConstraint)
        wx.EVT_COMMAND_SCROLL_THUMBTRACK(self, XRCID('sliderConstraint'), self.OnChangeConstraint)
        wx.EVT_COMMAND_SCROLL_CHANGED(self, XRCID('sliderConstraint'), self.OnChangeConstraint)

        # Initialize variables
        self.structures = {}
        self.dvhs = {}
        self.dvhid = 1

        self.SetSizer(mainGrid)
        self.Layout()

        #Set the Minumum size
        self.SetMinSize(size)
        self.Centre(wx.BOTH)

        # Initalize the database
        setup_all()
        if not os.path.isfile('dicompyler.db'):
            create_all()

        self.EnableConstraints(False)

    def OnOpenPatient(self, evt):
        """Load and show the Dicom RT Importer dialog box."""

        patient = dicomgui.ImportDicom(self)
        if not (patient == None):
            self.structures = patient['structures']
            self.dvhs = patient['dvh']
            self.PopulateDemographics(patient)
            self.PopulatePlan(patient['plan'])
            self.PopulateStructures()
            self.currConstraintId = None
            # show an empty plot when (re)loading a patient
            self.guiDVH.Replot()

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
            self.structures[id]['volume'] = dvh.CalculateVolume(self.structures[id])
        self.lblStructureVolume.SetLabel(str(self.structures[id]['volume'])[0:7])

        # make sure that the dvh has been calculated for each structure
        # before setting it
        if self.dvhs.has_key(id):
            self.lblStructureMinDose.SetLabel("%.3f" % self.dvhs[id]['min'])
            self.lblStructureMaxDose.SetLabel("%.3f" % self.dvhs[id]['max'])
            self.lblStructureMeanDose.SetLabel("%.3f" % self.dvhs[id]['mean'])
            self.EnableConstraints(True)
            # Create an instance of the dvh class so we can access the functions
            self.dvh = dvh.DVH(self.dvhs[id])
            # 'Toggle' the radio box to refresh the dose data
            self.OnToggleConstraints(None)
        else:
            self.lblStructureMinDose.SetLabel('-')
            self.lblStructureMaxDose.SetLabel('-')
            self.lblStructureMeanDose.SetLabel('-')
            self.EnableConstraints(False)
            # Make an empty plot on the DVH
            self.guiDVH.Replot(None, {id:self.structures[id]})

    def EnableConstraints(self, value):
        """Enable or disable the constraint selector."""

        self.radioVolume.Enable(value)
        self.radioDose.Enable(value)
        self.radioDosecc.Enable(value)
        self.txtConstraint.Enable(value)
        self.sliderConstraint.Enable(value)
        if not value:
            self.lblConstraintUnits.SetLabel('-            ')
            self.lblConstraintPercent.SetLabel('-            ')

    def OnToggleConstraints(self, evt):
        """Switch between different constraint modes."""

        # Check if the function was called via an event or not
        if not (evt == None):
            label = evt.GetEventObject().GetLabel()
        else:
            if self.radioVolume.GetValue():
                label = 'Volume Constraint (V__)'
            elif self.radioDose.GetValue():
                label = 'Dose Constraint (D__)'
            elif self.radioDosecc.GetValue():
                label = 'Dose Constraint (D__cc)'

        constraintrange = 0
        if (label == 'Volume Constraint (V__)'):
            self.lblConstraintType.SetLabel('   Dose:')
            self.lblConstraintTypeUnits.SetLabel('%  ')
            self.lblConstraintResultUnits.SetLabel(u'cm³')
            rxDose = float(self.lblRxDose.GetLabel())
            dvhdata = len(self.dvhs[self.dvhid]['data'])
            constraintrange = int(dvhdata*100/rxDose)
            # never go over the max dose as data does not exist
            if (constraintrange > int(self.dvhs[self.dvhid]['max'])):
                constraintrange = int(self.dvhs[self.dvhid]['max'])
        elif (label == 'Dose Constraint (D__)'):
            self.lblConstraintType.SetLabel('Volume:')
            self.lblConstraintTypeUnits.SetLabel(u'%  ')
            self.lblConstraintResultUnits.SetLabel(u'cGy')
            constraintrange = 100
        elif (label == 'Dose Constraint (D__cc)'):
            self.lblConstraintType.SetLabel('Volume:')
            self.lblConstraintTypeUnits.SetLabel(u'cm³')
            self.lblConstraintResultUnits.SetLabel(u'cGy')
            constraintrange = int(self.structures[self.dvhid]['volume'])

        self.sliderConstraint.SetRange(0, constraintrange)
        self.sliderConstraint.SetValue(constraintrange)
        self.txtConstraint.SetRange(0, constraintrange)
        self.txtConstraint.SetValue(constraintrange)

        self.OnChangeConstraint(None)

    def OnChangeConstraint(self, evt):
        """Update the results when the constraint value changes."""

        # Check if the function was called via an event or not
        if not (evt == None):
            slidervalue = evt.GetInt()
        else:
            slidervalue = self.sliderConstraint.GetValue()

        self.txtConstraint.SetValue(slidervalue)
        self.sliderConstraint.SetValue(slidervalue)
        rxDose = float(self.lblRxDose.GetLabel())
        id = self.dvhid

        if self.radioVolume.GetValue():
            absDose = rxDose * slidervalue / 100
            volume = self.structures[self.dvhid]['volume']
            cc = self.dvh.GetVolumeConstraintCC(absDose, volume)
            constraint = self.dvh.GetVolumeConstraint(absDose)

            self.lblConstraintUnits.SetLabel("%.3f" % cc)
            self.lblConstraintPercent.SetLabel("%.3f" % constraint)
            self.guiDVH.Replot({id:self.dvh.dvh}, {id:self.structures[id]},
                ([absDose], [constraint]))

        elif self.radioDose.GetValue():
            dose = self.dvh.GetDoseConstraint(slidervalue)

            self.lblConstraintUnits.SetLabel("%.3f" % dose)
            self.lblConstraintPercent.SetLabel("%.3f" % (dose*100/rxDose))
            self.guiDVH.Replot({id:self.dvh.dvh}, {id:self.structures[id]},
                ([dose], [slidervalue]))

        elif self.radioDosecc.GetValue():
            volumepercent = slidervalue*100/self.structures[self.dvhid]['volume']

            dose = self.dvh.GetDoseConstraint(volumepercent)

            self.lblConstraintUnits.SetLabel("%.3f" % dose)
            self.lblConstraintPercent.SetLabel("%.3f" % (dose*100/rxDose))
            self.guiDVH.Replot({id:self.dvh.dvh}, {id:self.structures[id]},
                ([dose], [volumepercent]))

    def OnAbout(self, evt):
        # First we create and fill the info object
        info = wx.AboutDialogInfo()
        info.Name = "dicompyler"
        info.Version = "0.1"
        info.Copyright = u"© 2009"
        info.Developers = ["Aditya Panchal (apanchal@bastula.org)"]

        # Then we call wx.AboutBox giving it that info object
        wx.AboutBox(info)

    def OnClose(self, _):
        self.Close()

class dicompyler(wx.App):
    def OnInit(self):
        wx.InitAllImageHandlers()

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
