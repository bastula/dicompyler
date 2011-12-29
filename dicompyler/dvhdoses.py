# dvhdoses.py
"""Functions to calculate minimum, maximum, and mean dose to ROI from a cDVH."""
# Copyright (c) 2009 Roy Keyes (roy.coding)
# Copyright (c) 2011 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#
# Start - 20 Nov. 2009
# It is assumed that the bin width of the cDVH is fixed at 1 cGy.

def get_dvh_min(dvh):
    '''Return minimum dose to ROI derived from cDVH.'''

    # ROI volume (always receives at least 0% dose)
    v1 = dvh[0]

    j = 1
    jmax = len(dvh) - 1
    mindose = 0
    while j < jmax:
        if dvh[j] < v1:
            mindose = (2*j - 1)/2.0
            break
        else:
            j += 1

    return mindose

def get_dvh_max(dvh):
    '''Return maximum dose to ROI derived from cDVH.'''

    # Calulate dDVH
    ddvh = get_ddvh(dvh)

    maxdose = 0
    j = len(ddvh) - 1
    while j >= 0:
        if ddvh[j] > 0.0:
            maxdose = j+1
            break
        else:
            j -= 1

    return maxdose

def get_dvh_median(dvh):
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

    return mediandose

def get_dvh_mean(dvh):
    '''Return mean dose to ROI derived from cDVH.'''

    # Mean dose = total dose / ROI volume

    # Volume of ROI
    v1 = dvh[0]

    # Calculate dDVH
    ddvh = get_ddvh(dvh)

    # Calculate total dose
    j = 1
    dose = 0
    for d in ddvh[1:]:
        dose += d*j
        j += 1

    meandose = dose/v1

    return meandose

def get_ddvh(cdvh):
    '''Return dDVH from cDVH array.'''

    # dDVH is the negative "slope" of the cDVH
    j = 0
    jmax = len(cdvh) - 1
    ddvh = []
    while j < jmax:
        ddvh += [cdvh[j] - cdvh[j+1]]
        j += 1
    ddvh += [cdvh[j]]

    return ddvh
