# dvhdoses.py

# Functions to calculate minimum, maximum, and mean dose to ROI from a cDVH.

# Roy Keyes (roy.coding)
# Start - 20 Nov. 2009

# It's assumed that the reference (prescription) dose is in cGy and the bin width
#   of the cDVH is in cGy and fixed at 1 cGy.

def getdvhmin(dvh,doseref):
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

def getdvhmax(dvh,doseref):
    '''Return maximum dose to ROI derived from cDVH.'''

    # Calulate dDVH
    ddvh = getddvh(dvh)

    j = len(ddvh) - 1
    while j >= 0:
        if ddvh[j] > 0.0:
            maxdose = j+1
            break
        else:
            j -= 1

    maxdose = 100.0*maxdose/doseref

    return maxdose

def getdvhmedian(dvh,doseref):
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

def getdvhmean(dvh,doseref):
    '''Return mean dose to ROI derived from cDVH.'''

    # Mean dose = total dose / ROI volume

    # Volume of ROI
    v1 = dvh[0]

    # Calculate dDVH
    ddvh = getddvh(dvh)

    # Calculate total dose
    j = 1
    dose = 0
    for d in ddvh[1:]:
        dose += d*j
        j += 1

    meandose = dose/v1
    meandose = 100*meandose/doseref

    return meandose

def getddvh(cdvh):
    '''Retrun dDVH from cDVH array.'''

    # dDVH is the negative "slope" of the cDVH    
    j = 0
    jmax = len(cdvh) - 1
    ddvh = []
    while j < jmax:
        ddvh += [cdvh[j] - cdvh[j+1]]
        j += 1

    return ddvh
