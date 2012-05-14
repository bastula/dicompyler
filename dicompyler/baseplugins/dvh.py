#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# dvh.py
"""dicompyler plugin that displays a dose volume histogram (DVH)
    with adjustable constraints via wxPython and matplotlib."""
# Copyright (c) 2009-2012 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#
# It is assumed that the reference (prescription) dose is in cGy.

import wx
from wx.xrc import XmlResource, XRCCTRL, XRCID
from wx.lib.pubsub import Publisher as pub
from dicompyler import guiutil, util
from dicompyler import dvhdata, guidvh
from dicompyler import wxmpl
import numpy as np

def pluginProperties():
    """Properties of the plugin."""

    props = {}
    props['name'] = 'DVH'
    props['description'] = "Display and evaluate dose volume histogram (DVH) data"
    props['author'] = 'Aditya Panchal'
    props['version'] = "0.4.2"
    props['plugin_type'] = 'main'
    props['plugin_version'] = 1
    props['min_dicom'] = ['rtss', 'rtdose']
    props['recommended_dicom'] = ['rtss', 'rtdose', 'rtplan']

    return props

def pluginLoader(parent):
    """Function to load the plugin."""

    # Load the XRC file for our gui resources
    res = XmlResource(util.GetBasePluginsPath('dvh.xrc'))

    panelDVH = res.LoadPanel(parent, 'pluginDVH')
    panelDVH.Init(res)

    return panelDVH

class pluginDVH(wx.Panel):
    """Plugin to display DVH data with adjustable constraints."""

    def __init__(self):
        pre = wx.PrePanel()
        # the Create step is done by XRC.
        self.PostCreate(pre)

    def Init(self, res):
        """Method called after the panel has been initialized."""

        self.guiDVH = guidvh.guiDVH(self)
        res.AttachUnknownControl('panelDVH', self.guiDVH.panelDVH, self)

        # Initialize the Constraint selector controls
        self.lblType = XRCCTRL(self, 'lblType')
        self.choiceConstraint = XRCCTRL(self, 'choiceConstraint')
        self.txtConstraint = XRCCTRL(self, 'txtConstraint')
        self.sliderConstraint = XRCCTRL(self, 'sliderConstraint')
        self.lblResultType = XRCCTRL(self, 'lblResultType')
        self.lblConstraintUnits = XRCCTRL(self, 'lblConstraintUnits')
        self.lblConstraintTypeUnits = XRCCTRL(self, 'lblConstraintTypeUnits')

        # Initialize the result labels
        self.lblConstraintType = XRCCTRL(self, 'lblConstraintType')
        self.lblResultDivider = XRCCTRL(self, 'lblResultDivider')
        self.lblConstraintPercent = XRCCTRL(self, 'lblConstraintPercent')

        # Modify the control and font size on Mac
        controls = [self.lblType, self.choiceConstraint, self.sliderConstraint,
            self.lblResultType, self.lblConstraintUnits, self.lblConstraintPercent,
            self.lblConstraintType, self.lblConstraintTypeUnits, self.lblResultDivider]
        # Add children of composite controls to modification list
        compositecontrols = [self.txtConstraint]
        for control in compositecontrols:
            for child in control.GetChildren():
                controls.append(child)
        # Add the constraint static box to the modification list
        controls.append(self.lblType.GetContainingSizer().GetStaticBox())

        if guiutil.IsMac():
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
            font.SetPointSize(10)
            for control in controls:
                control.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)
                control.SetFont(font)

        # Adjust the control size for the result value labels
        te = self.lblType.GetTextExtent('0')
        self.lblConstraintUnits.SetMinSize((te[0]*10, te[1]))
        self.lblConstraintPercent.SetMinSize((te[0]*6, te[1]))
        self.Layout()

        # Bind ui events to the proper methods
        wx.EVT_CHOICE(self, XRCID('choiceConstraint'), self.OnToggleConstraints)
        wx.EVT_SPINCTRL(self, XRCID('txtConstraint'), self.OnChangeConstraint)
        wx.EVT_COMMAND_SCROLL_THUMBTRACK(self, XRCID('sliderConstraint'), self.OnChangeConstraint)
        wx.EVT_COMMAND_SCROLL_CHANGED(self, XRCID('sliderConstraint'), self.OnChangeConstraint)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

        # Initialize variables
        self.structures = {} # structures from initial DICOM data
        self.checkedstructures = {} # structures that need to be shown
        self.dvhs = {} # raw dvhs from initial DICOM data
        self.dvhdata = {} # dict of dvh constraint functions
        self.dvharray = {} # dict of dvh data processed from dvhdata
        self.dvhscaling = {} # dict of dvh scaling data
        self.plan = {} # used for rx dose
        self.structureid = 1 # used to indicate current constraint structure

        # Set up pubsub
        pub.subscribe(self.OnUpdatePatient, 'patient.updated.parsed_data')
        pub.subscribe(self.OnStructureCheck, 'structures.checked')
        pub.subscribe(self.OnStructureSelect, 'structure.selected')

    def OnUpdatePatient(self, msg):
        """Update and load the patient data."""

        self.structures = msg.data['structures']
        self.dvhs = msg.data['dvhs']
        self.plan = msg.data['plan']
        # show an empty plot when (re)loading a patient
        self.guiDVH.Replot()
        self.EnableConstraints(False)

    def OnDestroy(self, evt):
        """Unbind to all events before the plugin is destroyed."""

        pub.unsubscribe(self.OnUpdatePatient)
        pub.unsubscribe(self.OnStructureCheck)
        pub.unsubscribe(self.OnStructureSelect)

    def OnStructureCheck(self, msg):
        """When a structure changes, update the interface and plot."""

        # Make sure that the volume has been calculated for each structure
        # before setting it
        self.checkedstructures = msg.data
        for id, structure in self.checkedstructures.iteritems():
            if not self.structures[id].has_key('volume'):
                self.structures[id]['volume'] = structure['volume']

            # make sure that the dvh has been calculated for each structure
            # before setting it
            if self.dvhs.has_key(id):
                self.EnableConstraints(True)
                # Create an instance of the dvhdata class to can access its functions
                self.dvhdata[id] = dvhdata.DVH(self.dvhs[id])
                # Create an instance of the dvh arrays so that guidvh can plot it
                self.dvharray[id] = dvhdata.DVH(self.dvhs[id]).dvh
                # Create an instance of the dvh scaling data for guidvh
                self.dvhscaling[id] = self.dvhs[id]['scaling']
                # 'Toggle' the choice box to refresh the dose data
                self.OnToggleConstraints(None)
        if not len(self.checkedstructures):
            self.EnableConstraints(False)
            # Make an empty plot on the DVH
            self.guiDVH.Replot()

    def OnStructureSelect(self, msg):
        """Load the constraints for the currently selected structure."""

        if (msg.data['id'] == None):
            self.EnableConstraints(False)
        else:
            self.structureid = msg.data['id']
            if self.dvhs.has_key(self.structureid):
                # Create an instance of the dvhdata class to can access its functions
                self.dvhdata[self.structureid] = dvhdata.DVH(self.dvhs[self.structureid])
                # Create an instance of the dvh scaling data for guidvh
                self.dvhscaling[self.structureid] = self.dvhs[self.structureid]['scaling']
                # 'Toggle' the choice box to refresh the dose data
                self.OnToggleConstraints(None)
            else:
                self.EnableConstraints(False)
                self.guiDVH.Replot([self.dvharray], [self.dvhscaling], self.checkedstructures)

    def EnableConstraints(self, value):
        """Enable or disable the constraint selector."""

        self.choiceConstraint.Enable(value)
        self.txtConstraint.Enable(value)
        self.sliderConstraint.Enable(value)
        if not value:
            self.lblConstraintUnits.SetLabel('- ')
            self.lblConstraintPercent.SetLabel('- ')
            self.txtConstraint.SetValue(0)
            self.sliderConstraint.SetValue(0)

    def OnToggleConstraints(self, evt):
        """Switch between different constraint modes."""

        # Replot the remaining structures and disable the constraints
        # if a structure that has no DVH calculated is selected
        if not self.dvhs.has_key(self.structureid):
            self.guiDVH.Replot([self.dvharray], [self.dvhscaling], self.checkedstructures)
            self.EnableConstraints(False)
            return
        else:
            self.EnableConstraints(True)
            dvh = self.dvhs[self.structureid]

        # Check if the function was called via an event or not
        if not (evt == None):
            constrainttype = evt.GetInt()
        else:
            constrainttype = self.choiceConstraint.GetSelection()

        constraintrange = 0
        # Volume constraint
        if (constrainttype == 0):
            self.lblConstraintType.SetLabel('   Dose:')
            self.lblConstraintTypeUnits.SetLabel('%  ')
            self.lblResultType.SetLabel('Volume:')
            rxDose = float(self.plan['rxdose'])
            dvhdata = (len(dvh['data'])-1)*dvh['scaling']
            constraintrange = int(dvhdata*100/rxDose)
            # never go over the max dose as data does not exist
            if (constraintrange > int(dvh['max'])):
                constraintrange = int(dvh['max'])
        # Volume constraint in Gy
        elif (constrainttype == 1):
            self.lblConstraintType.SetLabel('   Dose:')
            self.lblConstraintTypeUnits.SetLabel('Gy ')
            self.lblResultType.SetLabel('Volume:')
            constraintrange = self.plan['rxdose']/100
            maxdose = int(dvh['max']*self.plan['rxdose']/10000)
            # never go over the max dose as data does not exist
            if (constraintrange*100 > maxdose):
                constraintrange = maxdose
        # Dose constraint
        elif (constrainttype == 2):
            self.lblConstraintType.SetLabel('Volume:')
            self.lblConstraintTypeUnits.SetLabel(u'%  ')
            self.lblResultType.SetLabel('   Dose:')
            constraintrange = 100
        # Dose constraint in cc
        elif (constrainttype == 3):
            self.lblConstraintType.SetLabel('Volume:')
            self.lblConstraintTypeUnits.SetLabel(u'cm³')
            self.lblResultType.SetLabel('   Dose:')
            constraintrange = int(self.structures[self.structureid]['volume'])

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
        rxDose = self.plan['rxdose']
        id = self.structureid

        constrainttype = self.choiceConstraint.GetSelection()
        # Volume constraint
        if (constrainttype == 0):
            absDose = rxDose * slidervalue / 100
            volume = self.structures[id]['volume']
            cc = self.dvhdata[id].GetVolumeConstraintCC(absDose, volume)
            constraint = self.dvhdata[id].GetVolumeConstraint(absDose)

            self.lblConstraintUnits.SetLabel("%.1f" % cc + u' cm³')
            self.lblConstraintPercent.SetLabel("%.1f" % constraint + " %")
            self.guiDVH.Replot([self.dvharray], [self.dvhscaling],
                self.checkedstructures, ([absDose], [constraint]), id)
        # Volume constraint in Gy
        elif (constrainttype == 1):
            absDose = slidervalue*100
            volume = self.structures[id]['volume']
            cc = self.dvhdata[id].GetVolumeConstraintCC(absDose, volume)
            constraint = self.dvhdata[id].GetVolumeConstraint(absDose)

            self.lblConstraintUnits.SetLabel("%.1f" % cc + u' cm³')
            self.lblConstraintPercent.SetLabel("%.1f" % constraint + " %")
            self.guiDVH.Replot([self.dvharray], [self.dvhscaling],
                self.checkedstructures, ([absDose], [constraint]), id)
        # Dose constraint
        elif (constrainttype == 2):
            dose = self.dvhdata[id].GetDoseConstraint(slidervalue)

            self.lblConstraintUnits.SetLabel("%.1f" % dose + u' cGy')
            self.lblConstraintPercent.SetLabel("%.1f" % (dose*100/rxDose) + " %")
            self.guiDVH.Replot([self.dvharray], [self.dvhscaling],
                self.checkedstructures, ([dose], [slidervalue]), id)
        # Dose constraint in cc
        elif (constrainttype == 3):
            volumepercent = slidervalue*100/self.structures[id]['volume']

            dose = self.dvhdata[id].GetDoseConstraint(volumepercent)

            self.lblConstraintUnits.SetLabel("%.1f" % dose + u' cGy')
            self.lblConstraintPercent.SetLabel("%.1f" % (dose*100/rxDose) + " %")
            self.guiDVH.Replot([self.dvharray], [self.dvhscaling],
                self.checkedstructures, ([dose], [volumepercent]), id)
