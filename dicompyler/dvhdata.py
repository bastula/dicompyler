#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# dvhdata.py
"""Class and functions related to dose volume histogram (DVH) data."""
# Copyright (c) 2009-2012 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
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
        self.scaling = dvh['scaling']

        # Instruct numpy to print the full extent of the array
        np.set_printoptions(threshold=2147483647, suppress=True)

    def GetVolumeConstraint(self, dose):
        """ Return the volume (in percent) of the structure that receives at
            least a specific dose in cGy. i.e. V100, V150."""
        return self.dvh[int(dose/self.scaling)]

    def GetVolumeConstraintCC(self, dose, volumecc):
        """ Return the volume (in cc) of the structure that receives at least a
            specific dose in cGy. i.e. V100, V150."""

        volumepercent = self.GetVolumeConstraint(dose)

        return volumepercent * volumecc / 100

    def GetDoseConstraint(self, volume):
        """ Return the maximum dose (in cGy) that a specific volume (in percent)
            receives. i.e. D90, D20."""

        return np.argmin(np.fabs(self.dvh - volume))*self.scaling

def CalculateVolume(structure):
    """Calculates the volume for the given structure."""

    sPlanes = structure['planes']

    # Store the total volume of the structure
    sVolume = 0

    n = 0
    # Iterate over each plane in the structure
    for sPlane in sPlanes.itervalues():

        # Calculate the area for each contour in the current plane
        contours = []
        largest = 0
        largestIndex = 0
        for c, contour in enumerate(sPlane):
            # Create arrays for the x,y coordinate pair for the triangulation
            x = []
            y = []
            for point in contour['contourData']:
                x.append(point[0])
                y.append(point[1])

            cArea = 0
            # Calculate the area based on the Surveyor's formula
            for i in range(0, len(x)-1):
                cArea = cArea + x[i]*y[i+1] - x[i+1]*y[i]
            cArea = abs(cArea / 2)
            contours.append({'area':cArea, 'data':contour['contourData']})

            # Determine which contour is the largest
            if (cArea > largest):
                largest = cArea
                largestIndex = c

        # See if the rest of the contours are within the largest contour
        area = contours[largestIndex]['area']
        for i, contour in enumerate(contours):
            # Skip if this is the largest contour
            if not (i == largestIndex):
                contour['inside'] = False
                for point in contour['data']:
                    if PointInPolygon(point[0], point[1], contours[largestIndex]['data']):
                        contour['inside'] = True
                        # Assume if one point is inside, all will be inside
                        break
                # If the contour is inside, subtract it from the total area
                if contour['inside']:
                    area = area - contour['area']
                # Otherwise it is outside, so add it to the total area
                else:
                    area = area + contour['area']

        # If the plane is the first or last slice
        # only add half of the volume, otherwise add the full slice thickness
        if ((n == 0) or (n == len(sPlanes)-1)):
            sVolume = float(sVolume) + float(area) * float(structure['thickness']) * 0.5
        else:
            sVolume = float(sVolume) + float(area) * float(structure['thickness'])
        # Increment the current plane number
        n = n + 1

    # Since DICOM uses millimeters, convert from mm^3 to cm^3
    volume = sVolume/1000

    return volume

def PointInPolygon(x, y, poly):
    """Uses the Ray Casting method to determine whether a point is within
        the given polygon.
        Taken from: http://www.ariel.com.au/a/python-point-int-poly.html"""

    n = len(poly)
    inside = False
    p1x, p1y, p1z = poly[0]
    for i in range(n+1):
        p2x, p2y, p2z = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xinters = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x,p1y = p2x,p2y

    return inside
