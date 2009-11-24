# dvhdoses.py
"""Functions to calculate minimum, maximum, and mean dose to ROI from a cDVH."""
# Copyright (c) 2009 Roy Keyes (roy.coding)
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#
# Start - 20 Nov. 2009
# It's assumed that the reference (prescription) dose is in cGy and the bin width
# of the cDVH is in cGy.

def get_dvh_min(dvh, doseref):
    '''Return minimum dose to ROI derived from cDVH.'''

    # ROI volume (always receives at least 0% dose)
    v1 = dvh[0]

    j = 1
    jmax = len(dvh) - 1
    while j < jmax:
        if dvh[j] < v1:
            mindose = (2*j - 1)/2.0
            break
        else:
            j += 1

    mindose = 100*mindose/doseref

    return mindose

def get_dvh_max(dvh, doseref):
    '''Return maximum dose to ROI derived from cDVH.'''

    maxdose = 100*len(dvh[:-2])/doseref

    return maxdose

def get_dvh_median(dvh, doseref):
    '''Return median dose to ROI derived from cDVH.'''

    # Half of ROI volume
    v1 = dvh[0]/2.

    j = 1
    jmax = len(dvh) - 1
    while j < jmax:
        if dvh[j] < v1:
            mediandose = (2*j - 1)/2.0
            break
        else:
            j += 1

    mediandose = 100*mediandose/doseref

    return mediandose

def get_dvh_mean(dvh, doseref):
    '''Return mean dose to ROI derived from cDVH.'''

    # Mean dose = total dose / ROI volume

    # Volume of ROI
    v1 = dvh[0]

    # Calculate dDVH
    j = 1
    jmax = len(dvh) - 1
    ddvh = []
    while j < jmax:
        ddvh += [dvh[j] - dvh[j+1]]
        j += 1

    # Calculate total dose
    j = 1
    dose = 0
    for d in ddvh:
        dose += d*j
        j += 1

    meandose = dose/v1
    meandose = 100*meandose/doseref

    return meandose
