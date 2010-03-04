#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# dvhdata.py
"""Class and functions related to dose volume histogram (DVH) data."""
# Copyright (c) 2009 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#
# It's assumed that the reference (prescription) dose is in cGy.

import numpy as np

class DVH:
    """Processes the dose volume histogram from DICOM DVH data."""

    def __init__(self, dvh):
        """Take a dvh numpy array and convert it to cGy."""
        self.dvh = dvh['data'] * 100 / dvh['data'][0]

        # Instruct numpy to print the full extent of the array
        np.set_printoptions(threshold=2147483647, suppress=True)

    def GetVolumeConstraint(self, dose):
        """ Return the volume (in percent) of the structure that receives at
            least a specific dose in cGy. i.e. V100, V150."""

        return self.dvh[dose]

    def GetVolumeConstraintCC(self, dose, volumecc):
        """ Return the volume (in cc) of the structure that receives at least a
            specific dose in cGy. i.e. V100, V150."""

        volumepercent = self.GetVolumeConstraint(dose)

        return volumepercent * volumecc / 100

    def GetDoseConstraint(self, volume):
        """ Return the maximum dose (in cGy) that a specific volume (in percent)
            receives. i.e. D90, D20."""

        return np.argmin(np.fabs(self.dvh - volume))

def CalculateVolume(structure):
    """Calculates the volume for the given structure."""

    sPlanes = structure['planes']

    # Store the total volume of the structure
    sVolume = 0

    # Store the total number of planes to be used later
    sLen = len(sPlanes)
    n = 0
    # Iterate over each plane in the structure
    for sPlane in sPlanes.itervalues():

        # Store the total area for each plane
        sArea = 0

        # Create arrays for the x,y coordinate pair for the triangulation
        x = []
        y = []

        for point in sPlane['contourData']:
            x.append(point['x'])
            y.append(point['y'])

        # Calculate the area based on the Surveyor's formula
        for i in range(0, len(sPlane['contourData'])-1):
            sArea = sArea + x[i]*y[i+1] - x[i+1]*y[i]
        sArea = abs(sArea / 2)

        # If the plane is the first or last slice
        # only add half of the volume, otherwise add the full slice thickness
        if ((n == 0) or (n == sLen)):
            sVolume = float(sVolume) + float(sArea) * float(structure['thickness']) * 0.5
        else:
            sVolume = float(sVolume) + float(sArea) * float(structure['thickness'])

        # Increment the current plane number
        n = n + 1

    # Since DICOM uses millimeters, convert from mm^3 to cm^3
    volume = sVolume/1000

    return volume
