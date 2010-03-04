#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# dvh.py
"""dicompyler plugin that displays a dose volume histogram (DVH)
    with adjustable constraints via wxPython and matplotlib."""
# Copyright (c) 2009-2010 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#
# It is assumed that the reference (prescription) dose is in cGy.

import wx
from wx.xrc import XmlResource, XRCCTRL, XRCID
from wx.lib.pubsub import Publisher as pub
import util
import wxmpl
import numpy as np
import dvhdata, guidvh

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

        # Bind ui events to the proper methods
        wx.EVT_RADIOBUTTON(self, XRCID('radioVolume'), self.OnToggleConstraints)
        wx.EVT_RADIOBUTTON(self, XRCID('radioDose'), self.OnToggleConstraints)
        wx.EVT_RADIOBUTTON(self, XRCID('radioDosecc'), self.OnToggleConstraints)
        wx.EVT_SPINCTRL(self, XRCID('txtConstraint'), self.OnChangeConstraint)
        wx.EVT_COMMAND_SCROLL_THUMBTRACK(self, XRCID('sliderConstraint'), self.OnChangeConstraint)
        wx.EVT_COMMAND_SCROLL_CHANGED(self, XRCID('sliderConstraint'), self.OnChangeConstraint)

        # Initialize variables
        self.structures = {}
        self.dvhs = {}
        self.plan = {}
        self.structureid = 1

        self.EnableConstraints(False)

        # Set up pubsub
        pub.subscribe(self.OnUpdatePatient, 'patient.updated')
        pub.subscribe(self.OnStructureSelect, 'structures.selected')

    def OnUpdatePatient(self, msg):
        """Update and load the patient data."""

        self.structures = msg.data['structures']
        self.dvhs = msg.data['dvhs']
        self.plan = msg.data['plan']
        # show an empty plot when (re)loading a patient
        self.guiDVH.Replot()

    def OnStructureSelect(self, msg):
        """When the structure changes, update the interface and plot."""

        self.structureid = msg.data['id']
        # id is shorthand for structure id so we don't have long lines of code
        id = self.structureid

        # make sure that the volume has been calculated for each structure
        # before setting it
        if not self.structures[id].has_key('volume'):
            self.structures[id]['volume'] = msg.data['volume']

        # make sure that the dvh has been calculated for each structure
        # before setting it
        if self.dvhs.has_key(id):
            self.EnableConstraints(True)
            # Create an instance of the dvhdata class to can access its functions
            self.dvh = dvhdata.DVH(self.dvhs[id])
            # 'Toggle' the radio box to refresh the dose data
            self.OnToggleConstraints(None)
        else:
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
            rxDose = float(self.plan['rxdose'])
            dvhdata = len(self.dvhs[self.structureid]['data'])
            constraintrange = int(dvhdata*100/rxDose)
            # never go over the max dose as data does not exist
            if (constraintrange > int(self.dvhs[self.structureid]['max'])):
                constraintrange = int(self.dvhs[self.structureid]['max'])
        elif (label == 'Dose Constraint (D__)'):
            self.lblConstraintType.SetLabel('Volume:')
            self.lblConstraintTypeUnits.SetLabel(u'%  ')
            self.lblConstraintResultUnits.SetLabel(u'cGy')
            constraintrange = 100
        elif (label == 'Dose Constraint (D__cc)'):
            self.lblConstraintType.SetLabel('Volume:')
            self.lblConstraintTypeUnits.SetLabel(u'cm³')
            self.lblConstraintResultUnits.SetLabel(u'cGy')
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

        if self.radioVolume.GetValue():
            absDose = rxDose * slidervalue / 100
            volume = self.structures[self.structureid]['volume']
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
            volumepercent = slidervalue*100/self.structures[self.structureid]['volume']

            dose = self.dvh.GetDoseConstraint(volumepercent)

            self.lblConstraintUnits.SetLabel("%.3f" % dose)
            self.lblConstraintPercent.SetLabel("%.3f" % (dose*100/rxDose))
            self.guiDVH.Replot({id:self.dvh.dvh}, {id:self.structures[id]},
                ([dose], [volumepercent]))
