#!/usr/bin/env python
# -*- coding: utf-8 -*-
# dvh.py
"""dicompyler plugin that displays a dose volume histogram (DVH)
    with adjustable constraints via wxPython and matplotlib."""
# Copyright (c) 2009-2017 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/bastula/dicompyler/
#
# It is assumed that the reference (prescription) dose is in cGy.

import wx
from wx.xrc import XmlResource, XRCCTRL, XRCID
from wx.lib.pubsub import pub
from dicompyler import guiutil, util
from dicompyler import guidvh
import numpy as np

def pluginProperties():
    """Properties of the plugin."""

    props = {}
    props['name'] = 'DVH'
    props['description'] = "Display and evaluate dose volume histogram (DVH) data"
    props['author'] = 'Aditya Panchal'
    props['version'] = "0.5.0"
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
        wx.Panel.__init__(self)
        
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
            for control in controls:
                control.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)

        # Adjust the control size for the result value labels
        te = self.lblType.GetTextExtent('0')
        self.lblConstraintUnits.SetMinSize((te[0]*10, te[1]))
        self.lblConstraintPercent.SetMinSize((te[0]*6, te[1]))
        self.Layout()

        # Bind ui events to the proper methods
        self.Bind(
            wx.EVT_CHOICE, self.OnToggleConstraints, id=XRCID('choiceConstraint'))
        self.Bind(
            wx.EVT_SPINCTRL, self.OnChangeConstraint, id=XRCID('txtConstraint'))
        self.Bind(
            wx.EVT_COMMAND_SCROLL_THUMBTRACK,
            self.OnChangeConstraint, id=XRCID('sliderConstraint'))
        self.Bind(
            wx.EVT_COMMAND_SCROLL_CHANGED,
            self.OnChangeConstraint, id=XRCID('sliderConstraint'))
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

        # Initialize variables
        self.structures = {} # structures from initial DICOM data
        self.checkedstructures = {} # structures that need to be shown
        self.dvhs = {} # raw dvhs from initial DICOM data
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

        self.structures = msg['structures']
        self.dvhs = msg['dvhs']
        self.plan = msg['plan']
        # show an empty plot when (re)loading a patient
        self.guiDVH.Replot()
        self.EnableConstraints(False)

    def OnDestroy(self, evt):
        """Unbind to all events before the plugin is destroyed."""

        pub.unsubscribe(self.OnUpdatePatient, 'patient.updated.parsed_data')
        pub.unsubscribe(self.OnStructureCheck, 'structures.checked')
        pub.unsubscribe(self.OnStructureSelect, 'structure.selected')

    def OnStructureCheck(self, msg):
        """When a structure changes, update the interface and plot."""

        # Make sure that the volume has been calculated for each structure
        # before setting it
        self.checkedstructures = msg
        for id, structure in self.checkedstructures.items():
            if not 'volume' in self.structures[id]:
                self.structures[id]['volume'] = structure['volume']

            # make sure that the dvh has been calculated for each structure
            # before setting it
            if id in self.dvhs:
                self.EnableConstraints(True)
                self.dvharray[id] = self.dvhs[id].relative_volume.counts
                # Create an instance of the dvh scaling data for guidvh
                self.dvhscaling[id] = 1  # self.dvhs[id]['scaling']
                # 'Toggle' the choice box to refresh the dose data
                self.OnToggleConstraints(None)
        if not len(self.checkedstructures):
            self.EnableConstraints(False)
            # Make an empty plot on the DVH
            self.guiDVH.Replot()

    def OnStructureSelect(self, msg):
        """Load the constraints for the currently selected structure."""

        if (msg['id'] == None):
            self.EnableConstraints(False)
        else:
            self.structureid = msg['id']
            if self.structureid in self.dvhs:
                # Create an instance of the dvh scaling data for guidvh
                self.dvhscaling[self.structureid] = 1  # self.dvhs[self.structureid]['scaling']
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
        if not self.structureid in self.dvhs:
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
            constraintrange = dvh.relative_dose().max
        # Volume constraint in Gy
        elif (constrainttype == 1):
            self.lblConstraintType.SetLabel('   Dose:')
            self.lblConstraintTypeUnits.SetLabel('Gy ')
            self.lblResultType.SetLabel('Volume:')
            constraintrange = round(dvh.max)
        # Dose constraint
        elif (constrainttype == 2):
            self.lblConstraintType.SetLabel('Volume:')
            self.lblConstraintTypeUnits.SetLabel('%  ')
            self.lblResultType.SetLabel('   Dose:')
            constraintrange = 100
        # Dose constraint in cc
        elif (constrainttype == 3):
            self.lblConstraintType.SetLabel('Volume:')
            self.lblConstraintTypeUnits.SetLabel('cm\u00B3')
            self.lblResultType.SetLabel('   Dose:')
            constraintrange = dvh.volume

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
        id = self.structureid
        dvh = self.dvhs[self.structureid]

        constrainttype = self.choiceConstraint.GetSelection()
        # Volume constraint
        if (constrainttype == 0):
            absDose = dvh.rx_dose * slidervalue
            cc = dvh.volume_constraint(slidervalue)
            constraint = dvh.relative_volume.volume_constraint(slidervalue)

            self.lblConstraintUnits.SetLabel(str(cc))
            self.lblConstraintPercent.SetLabel(str(constraint))
            self.guiDVH.Replot([self.dvharray], [self.dvhscaling],
                self.checkedstructures, ([absDose], [constraint.value]), id)
        # Volume constraint in Gy
        elif (constrainttype == 1):
            absDose = slidervalue*100
            cc = dvh.volume_constraint(slidervalue, dvh.dose_units)
            constraint = dvh.relative_volume.volume_constraint(
                slidervalue, dvh.dose_units)

            self.lblConstraintUnits.SetLabel(str(cc))
            self.lblConstraintPercent.SetLabel(str(constraint))
            self.guiDVH.Replot([self.dvharray], [self.dvhscaling],
                self.checkedstructures, ([absDose], [constraint.value]), id)
        # Dose constraint
        elif (constrainttype == 2):
            dose = dvh.dose_constraint(slidervalue)
            relative_dose = dvh.relative_dose().dose_constraint(slidervalue)

            self.lblConstraintUnits.SetLabel(str(dose))
            self.lblConstraintPercent.SetLabel(str(relative_dose))
            self.guiDVH.Replot([self.dvharray], [self.dvhscaling],
                self.checkedstructures,
                ([dose.value * 100], [slidervalue]), id)
        # Dose constraint in cc
        elif (constrainttype == 3):
            volumepercent = slidervalue*100/self.structures[id]['volume']
            dose = dvh.dose_constraint(slidervalue, dvh.volume_units)
            relative_dose = dvh.relative_dose().dose_constraint(
                slidervalue, dvh.volume_units)

            self.lblConstraintUnits.SetLabel(str(dose))
            self.lblConstraintPercent.SetLabel(str(relative_dose))
            self.guiDVH.Replot([self.dvharray], [self.dvhscaling],
                self.checkedstructures,
                ([dose.value * 100], [volumepercent]), id)
