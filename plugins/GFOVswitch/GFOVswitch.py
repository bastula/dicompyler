# GFOVswitch.py
# GridFrameOffsetVector Switch plugin for dicompyler.
# Copyright (c) 2012 Derek M. Tishler and dicompyler contributors.
"""
Switch the Grid Frame Offset Vector between Type A/B(Relative/Absolute).
"""
# All rights reserved, released under a BSD license.
#    See the file license.txt included with this distribution, available at:
#    http://code.google.com/p/dicompyler-plugins/source/browse/plugins/gfovswitch/license.txt

#Requires wxPython, pyDicom, numpy, dicompyler.
import wx
from   wx.lib.pubsub import Publisher as pub
import dicom
import os
import numpy as np
from dicompyler import guiutil, util
import logging
logger = logging.getLogger('dicompyler.gfovswitch')

def pluginProperties():

    props = {}
    props['name'] = 'GFOV Switch'
    props['description'] = "Switch the GFOV between Type A/B(Relative/Absolute)"
    props['author'] = 'D. M. Tishler'
    props['version'] = 0.1
    props['documentation'] = 'http://code.google.com/p/dicompyler-plugins/wiki/gfovswitch'
    props['license'] = 'license.txt'
    props['plugin_type'] = 'menu'
    props['plugin_version'] = 1
    #Use 'rtdose' here once Issue 72 is fixed.
    props['min_dicom'] = ['images']
    props['recommended_dicom'] =  ['images','rtdose']

    return props

class plugin():

    def __init__(self, parent):
        
        #Set subscriptions
        self.parent = parent
        pub.subscribe(self.OnUpdatePatient, 'patient.updated.raw_data')

    def OnUpdatePatient(self, msg):
        
        #Update data from pubsub.
        self.data = msg.data

    def pluginMenu(self, evt):

        #Wont need this check once Issue 72 is fixed.
        if self.data.has_key('rtdose'):

            #Load RTPlan and first DICOM slice.
            rtd = self.data['rtdose']
            ct1 = self.data['images'][0]
            #Number of slices.
            N = len(self.data['images'])

            #Get slice spacing t, use difference instead of tags to get direction.
            t = self.data['images'][1].ImagePositionPatient[2]-self.data['images'][0].ImagePositionPatient[2]
            zpos = ct1.ImagePositionPatient[2]
            #Check current type of GFOV and switch.
            if rtd.has_key('GridFrameOffsetVector'):
                if rtd.GridFrameOffsetVector[0] == 0.:
                    logger.info("Found Type A - Relative Coordinates\nConverting to Type B - Absolute")
                    #Convert to Type B (Absolute)
                    rtd.GridFrameOffsetVector = list(np.arange(zpos, zpos + t*N, t))
                elif rtd.GridFrameOffsetVector[0] == zpos:
                    logger.info("Found Type B - Absolute Coordinates\nConverting to Type A - Relative")
                    #Convert to Type A (Relative)
                    rtd.GridFrameOffsetVector = list(np.arange(0., abs(t)*N,abs(t)))
            else:
                logger.info("GridFrameOffsetVector key not found in RT-Dose!")

            #Print results.
            np.set_printoptions(precision=2)
            logger.info(np.array(rtd.GridFrameOffsetVector))
            #Publish new rtdose.
            pub.sendMessage('patient.updated.raw_data', self.data)

        else:
            logger.info("Please load a RT-Dose file!")

