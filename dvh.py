#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# dvh.py
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

if __name__=='__main__':

    import os, sys
    import dicomparser, dvh

    usage = "usage: dvh -d [directory] \
                \n       dicomparser -f [file ...]"

    if (len(sys.argv) > 1):
        if (len(sys.argv) == 2):
            print usage
        # if only one argument is provided, assume it is a directory
        elif (sys.argv[1] == '-d'):
            if os.path.isdir(sys.argv[2]):
                for item in os.listdir(sys.argv[2]):
                    dcmfile = os.path.join(sys.argv[2], item)
                    if os.path.isfile(dcmfile):
                        try:
                            dp = dicomparser.DicomParser(dcmfile)
                        except (KeyError, IOError):
                            pass
                            print item + " is not a valid DICOM file."
                        else:
                            if (dp.GetSOPClassUID() == 'rtss'):
                                structures = dp.GetStructures()
                            elif (dp.GetSOPClassUID() == 'rtdose'):
                                dvhs = dp.GetDVHs()
                                advh = dvh.DVH(dvhs[4])
                                print advh.GetVolumeConstraint(30.03)
                                print advh.GetVolumeConstraint(31.1)
                                print advh.GetVolumeConstraint(30.05)
                                for item in dvhs[4]['data']:
                                    print item
                            else:
                                print item + " is a " \
                                + dp.ds.MediaStorageSOPClassUID.name + " file."
                    else:
                        print item + " is a directory."
            else:
                print "Not a valid directory."
        # if more than one argument is provided, assume it a file
        elif (sys.argv[1] == '-f'):
            if os.path.isfile(sys.argv[2]):
                dp = dicomparser.DicomParser(os.path.abspath(sys.argv[2]))
                if (dp.GetSOPClassUID() == 'rtss'):
                    structures = dp.GetStructures()
                elif (dp.GetSOPClassUID() == 'rtdose'):
                    dvhs = dp.GetDVHs()
                    advh = dvh.DVH(dvhs[4])
                    print advh
                    print advh.GetVolumeConstraint(1300)
                else:
                    print item + " is a " \
                    + dp.ds.MediaStorageSOPClassUID.name + " file."
            else:
                print "Not a valid file."
    else:
         print usage
