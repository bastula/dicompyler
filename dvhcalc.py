#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# dvhcalc.py
"""Calculate dose volume histogram (DVH) from DICOM RT Structure / Dose data."""
# Copyright (c) 2011 Aditya Panchal
# Copyright (c) 2010 Roy Keyes
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

import logging
logger = logging.getLogger('dicompyler.dvhcalc')
import numpy as np
import numpy.ma as ma
import matplotlib.nxutils as nx

def get_dvh(structure, dose, limit=None, callback=None):
    """Get a calculated cumulative DVH along with the associated parameters."""

    # Get the differential DVH
    hist = calculate_dvh(structure, dose, limit, callback)
    # Convert the differential DVH into a cumulative DVH
    dvh = get_cdvh(hist)

    dvhdata = {}
    dvhdata['data'] = dvh
    dvhdata['bins'] = len(dvh)
    dvhdata['type'] = 'CUMULATIVE'
    dvhdata['doseunits'] = 'GY'
    dvhdata['volumeunits'] = 'CM3'
    dvhdata['scaling'] = 1
    # save the min dose as -1 so we can calculate it later
    dvhdata['min'] = -1
    # save the max dose as -1 so we can calculate it later
    dvhdata['max'] = -1
    # save the mean dose as -1 so we can calculate it later
    dvhdata['mean'] = -1
    return dvhdata

def calculate_dvh(structure, dose, limit=None, callback=None):
    """Calculate the differential DVH for the given structure and dose grid."""

    sPlanes = structure['planes']
    logger.debug("Calculating DVH of %s %s", structure['id'], structure['name'])

    # Get the dose to pixel LUT
    doselut = dose.GetPatientToPixelLUT()

    # Generate a 2d mesh grid to create a polygon mask in dose coordinates
    # Code taken from Stack Overflow Answer from Joe Kington:
    # http://stackoverflow.com/questions/3654289/scipy-create-2d-polygon-mask/3655582
    # Create vertex coordinates for each grid cell
    x, y = np.meshgrid(np.array(doselut[0]), np.array(doselut[1]))
    x, y = x.flatten(), y.flatten()
    dosegridpoints = np.vstack((x,y)).T

    # Get the dose and image data information
    dd = dose.GetDoseData()
    id = dose.GetImageData()

    # Create an empty array of bins to store the histogram in cGy
    # only if the structure has contour data
    if len(sPlanes):
        maxdose = int(dd['dosemax'] * dd['dosegridscaling'] * 100)
        # Remove values above the limit (cGy) if specified
        if not (limit == None):
            if (limit < maxdose):
                maxdose = limit
        hist = np.zeros(maxdose)
    else:
        hist = np.array([0])
    volume = 0

    plane = 0
    # Iterate over each plane in the structure
    for z, sPlane in sPlanes.iteritems():

        # Get the contours with calculated areas and the largest contour index
        contours, largestIndex = calculate_contour_areas(sPlane)

        # Get the dose plane for the current structure plane
        doseplane = dose.GetDoseGrid(z)

        # If there is no dose for the current plane, go to the next plane
        if not len(doseplane):
            break

        # Calculate the histogram for each contour
        for i, contour in enumerate(contours):
            m = get_contour_mask(doselut, dosegridpoints, contour['data'])
            h, vol = calculate_contour_dvh(m, doseplane, maxdose,
                                           dd, id, structure)
            # If this is the largest contour, just add to the total histogram
            if (i == largestIndex):
                hist += h
                volume += vol
            # Otherwise, determine whether to add or subtract histogram
            # depending if the contour is within the largest contour or not
            else:
                contour['inside'] = False
                for point in contour['data']:
                    if nx.pnpoly(point[0], point[1],
                                 np.array(contours[largestIndex]['data'])):
                        contour['inside'] = True
                        # Assume if one point is inside, all will be inside
                        break
                # If the contour is inside, subtract it from the total histogram
                if contour['inside']:
                    hist -= h
                    volume -= vol
                # Otherwise it is outside, so add it to the total histogram
                else:
                    hist += h
                    volume += vol
        plane += 1
        if not (callback == None):
            callback(plane, len(sPlanes))
    # Volume units are given in cm^3
    volume = volume/1000
    # Rescale the histogram to reflect the total volume
    hist = hist*volume/sum(hist)
    # Remove the bins above the max dose for the structure
    hist = np.trim_zeros(hist, trim='b')

    return hist

def calculate_contour_areas(plane):
    """Calculate the area of each contour for the given plane.
       Additionally calculate and return the largest contour index."""

    # Calculate the area for each contour in the current plane
    contours = []
    largest = 0
    largestIndex = 0
    for c, contour in enumerate(plane):
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
        # Remove the z coordinate from the xyz point tuple
        data = map(lambda x: x[0:2], contour['contourData'])
        # Add the contour area and points to the list of contours
        contours.append({'area':cArea, 'data':data})

        # Determine which contour is the largest
        if (cArea > largest):
            largest = cArea
            largestIndex = c

    return contours, largestIndex

def get_contour_mask(doselut, dosegridpoints, contour):
    """Get the mask for the contour with respect to the dose plane."""

    grid = nx.points_inside_poly(dosegridpoints, contour)
    grid = grid.reshape((len(doselut[1]), len(doselut[0])))

    return grid

def calculate_contour_dvh(mask, doseplane, maxdose, dd, id, structure):
    """Calculate the differential DVH for the given contour and dose plane."""

    # Multiply the structure mask by the dose plane to get the dose mask
    mask = ma.array(doseplane * dd['dosegridscaling'] * 100, mask=~mask)
    # Calculate the differential dvh
    hist, edges = np.histogram(mask.compressed(),
                               bins=maxdose,
                               range=(0,maxdose))

    # Calculate the volume for the contour for the given dose plane
    vol = sum(hist) * ((id['pixelspacing'][0]) *
                      (id['pixelspacing'][1]) *
                      (structure['thickness']))
    return hist, vol

def get_cdvh(ddvh):
    """Calculate the cumulative DVH from a differential DVH array."""

    # cDVH(x) is Sum (Integral) of dDVH with x as lower limit
    cdvh = []
    j = 0
    jmax = len(ddvh)
    while j < jmax:
        cdvh += [np.sum(ddvh[j:])]
        j += 1
    cdvh = np.array(cdvh)
    return cdvh

############################# Test DVH Calculation #############################

def main():

    import dicomparser
    import string

    has_pylab = True
    try:
        import pylab as pl
    except ImportError:
        has_pylab = False

    # Read the example RT structure and RT dose files
    # The testdata was downloaded from the dicompyler website as testdata.zip
    rtss = dicomparser.DicomParser(filename="testdata/rtss.dcm")
    rtdose = dicomparser.DicomParser(filename="testdata/rtdose.dcm")

    # Obtain the structures and DVHs from the DICOM data
    structures = rtss.GetStructures()
    dvhs = rtdose.GetDVHs()

    # Generate the calculated DVHs
    calcdvhs = {}
    for key, structure in structures.iteritems():
        calcdvhs[key] = get_dvh(structure, rtdose)

    # Compare the calculated and original DVH volume for each structure
    print '\nStructure Name\t\t' + 'Original Volume\t\t' + \
          'Calculated Volume\t' + 'Percent Difference'
    print '--------------\t\t' + '---------------\t\t' + \
          '-----------------\t' + '------------------'
    for key, structure in structures.iteritems():
        if (key in calcdvhs) and (len(calcdvhs[key]['data'])):
            if key in dvhs:
                ovol = dvhs[key]['data'][0]
                cvol = calcdvhs[key]['data'][0]
                print string.ljust(structure['name'], 18) + '\t' + \
                      string.ljust(str(ovol), 18) + '\t' + \
                      string.ljust(str(cvol), 18) + '\t' + \
                      "%.3f" % float((100)*(cvol-ovol)/(ovol))

    # Plot the DVHs if pylab is available
    if has_pylab:
        for key, structure in structures.iteritems():
            if (key in calcdvhs) and (len(calcdvhs[key]['data'])):
                if key in dvhs:
                    pl.plot(calcdvhs[key]['data']*100/calcdvhs[key]['data'][0],
                            color=np.array(structure['color'], dtype=float)/255,
                            label=structure['name'], linestyle='dashed')
                    pl.plot(dvhs[key]['data']*100/dvhs[key]['data'][0],
                            color=np.array(structure['color'], dtype=float)/255,
                            label='Original '+structure['name'])
        pl.legend(loc=7, borderaxespad=-5)
        pl.setp(pl.gca().get_legend().get_texts(), fontsize='x-small')
        pl.show()

if __name__ == '__main__':
    main()
