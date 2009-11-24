#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# dicomparser.py
"""Class that parses and returns formatted DICOM RT data."""
# Copyright (c) 2009 Aditya Panchal
# Copyright (c) 2009 Roy Keyes
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

from decimal import Decimal
import numpy as np
import dicom

class DicomParser:
    """Parses DICOM RT Structure Set or Dose files."""

    def __init__(self, filename):

        try:
            self.ds = dicom.read_file(filename, defer_size=100)
        except (EOFError, IOError):
            # Raise the error for the calling method to handle
            raise
        else:
            # Sometimes DICOM files may not have headers, but they should always
            # have a SOPClassUID to declare what type of file it is. If the
            # file doesn't have a SOPClassUID, then it probably isn't DICOM.
            if not "SOPClassUID" in self.ds:
                raise AttributeError

######################## SOP Class and Instance Methods ########################

    def GetSOPClassUID(self):
        """Determine the SOP Class UID of the current file."""

        if (self.ds.SOPClassUID == '1.2.840.10008.5.1.4.1.1.481.2'):
            return 'rtdose'
        elif (self.ds.SOPClassUID == '1.2.840.10008.5.1.4.1.1.481.3'):
            return 'rtss'
        elif (self.ds.SOPClassUID == '1.2.840.10008.5.1.4.1.1.481.5'):
            return 'rtplan'
        else:
            return None

    def GetSOPInstanceUID(self):
        """Determine the SOP Class UID of the current file."""

        return self.ds.SOPInstanceUID

    def GetReferencedStructureSet(self):
        """Return the SOP Class UID of the referenced structure set."""

        if "ReferencedStructureSets" in self.ds:
            return self.ds.ReferencedStructureSets[0].ReferencedSOPInstanceUID
        else:
            return ''

    def GetReferencedRTPlan(self):
        """Return the SOP Class UID of the referenced RT plan."""

        return self.ds.ReferencedRTPlans[0].ReferencedSOPInstanceUID

    def GetDemographics(self):
        """Return the patient demographics from a DICOM file."""

        patient = {}
        patient['name'] = str(self.ds.PatientsName).replace('^', ', ')
        patient['id'] = self.ds.PatientID
        if (self.ds.PatientsSex == 'M'):
            patient['gender'] = 'Male'
        elif (self.ds.PatientsSex == 'F'):
            patient['gender'] = 'Female'
        else:
            patient['gender'] = 'Other'
        if len(self.ds.PatientsBirthDate):
            patient['dob'] = str(self.ds.PatientsBirthDate)
        else:
            patient['dob'] = 'None found'

        return patient

########################### RT Structure Set Methods ###########################

    def GetStructureInfo(self):
        """Return the patient demographics from a DICOM file."""

        structure = {}
        structure['label'] = self.ds.StructureSetLabel
        structure['date'] = self.ds.StructureSetDate
        structure['time'] = self.ds.StructureSetTime
        structure['numcontours'] = len(self.ds.ROIContours)

        return structure

    def GetStructures(self):
        """Returns the structures (ROIs) with their coordinates."""

        structures = {}

        # Determine whether this is RT Structure Set file
        if not (self.GetSOPClassUID() == 'rtss'):
            print "Given file is not a valid RT Structure Set."
            return structures

        # Locate the name and number of each ROI
        if self.ds.has_key('StructureSetROIs'):
            for item in self.ds.StructureSetROIs:
                data = {}
                number = item.ROINumber
                data['name'] = item.ROIName
                print 'Found ROI #' + str(number) + ': '  + data['name']
                structures[number] = data

        # The coordinate data of each ROI is stored within ROIContourSequence
        if self.ds.has_key('ROIContours'):
            for roi in self.ds.ROIContours:
                number = roi.ReferencedROINumber

                # Get the RGB color triplet for the current ROI
                structures[number]['color'] = np.array(roi.ROIDisplayColor, dtype=float)

                planes = {}
                if roi.has_key('Contours'):
                    # Locate the contour sequence for each referenced ROI
                    for contour in roi.Contours:
                        # For each plane, initialize a new plane dictionary
                        plane = {}

                        # Determine all the plane properties
                        plane['geometricType'] = contour.ContourGeometricType
                        plane['numContourPoints'] = contour.NumberofContourPoints
                        plane['contourData'] = self.GetContourPoints(contour.ContourData)

                        # Each plane which coincides with a image slice will have a unique ID
                        if contour.has_key('ContourImages'):
                            plane['UID'] = contour.ContourImages[0].ReferencedSOPInstanceUID

                        # Add each plane to the planes dictionary of the current ROI
                        # only if the geometric type is closed planar
                        if plane.has_key('geometricType'):
                            if (plane['geometricType'] == u"CLOSED_PLANAR"):
                                z = Decimal(str(plane['contourData'][0]['z']))
                                planes[z] = plane
                            else:
                                print 'ROI # ' + str(number) + \
                                ': CLOSED_PLANAR contour type expected, but found ' + \
                                                plane['geometricType'] + ' instead.'

                # Calculate the plane thickness for the current ROI
                structures[number]['thickness'] = self.CalculatePlaneThickness(planes)

                # Add the planes dictionary to the current ROI
                structures[number]['planes'] = planes

        return structures

    def GetContourPoints(self, array):
        """Parses an array of xyz points and returns a array of point dictionaries."""

        contourData = []
        point = {}

        for n in range(0, len(array)):
            x = y = z = 0
            if (n % 3 == 0):
                point['x'] = float(array[n])
            if (n % 3 == 1):
                point['y'] = float(array[n])
            if (n % 3 == 2):
                point['z'] = float(array[n])
                contourData.append(point.copy())
                point = {}

        return contourData

    def CalculatePlaneThickness(self, planesDict):
        """Calculates the plane thickness for each structure."""

        planes = []

        # Iterate over each plane in the structure
        for z in planesDict.iterkeys():
            planes.append(z)
        planes.sort()

        # Determine the thickness
        thickness = 10000
        for n in range(0, len(planes)):
            if (n > 0):
                newThickness = planes[n] - planes[n-1]
                if (newThickness < thickness):
                    thickness = newThickness

        # If the thickness was not detected, set it to 0
        if (thickness == 10000):
            thickness = 0

        return thickness

############################### RT Dose Methods ###############################

    def HasDVHs(self):
        """Returns whether dose-volume histograms (DVHs) exist."""

        return "DVHs" in self.ds

    def GetDVHs(self):
        """Returns the dose-volume histograms (DVHs)."""

        self.dvhs = {}

        if "DVHs" in self.ds:
            for item in self.ds.DVHs:
                dvhitem = {}
                # Remove "filler" values from DVH data array (even values are DVH values)
                dvhitem['data'] = np.array(item.DVHData[1::2])
                dvhitem['type'] = item.DVHType
                dvhitem['doseunits'] = item.DoseUnits
                dvhitem['volumeunits'] = item.DVHVolumeUnits
                dvhitem['scaling'] = item.DVHDoseScaling
                dvhitem['bins'] = int(item.DVHNumberofBins)
                if "DVHMinimumDose" in item:
                    dvhitem['min'] = item.DVHMinimumDose
                else:
                    # save the min dose as -1 so we can calculate it later
                    dvhitem['min'] = -1
                if "DVHMaximumDose" in item:
                    dvhitem['max'] = item.DVHMaximumDose
                else:
                    # save the max dose as -1 so we can calculate it later
                    dvhitem['max'] = -1
                if "DVHMeanDose" in item:
                    dvhitem['mean'] = item.DVHMeanDose
                else:
                    # save the mean dose as -1 so we can calculate it later
                    dvhitem['mean'] = -1
                self.dvhs[item.DVHReferencedROIs[0].ReferencedROINumber] = dvhitem

        return self.dvhs

############################### RT Plan Methods ###############################

    def GetPlan(self):
        """Returns the plan information."""

        self.plan = {}

        self.plan['label'] = self.ds.RTPlanLabel
        self.plan['date'] = self.ds.RTPlanDate
        self.plan['time'] = self.ds.RTPlanTime
        self.plan['name'] = ''
        self.plan['rxdose'] = 0
        if "DoseReferences" in self.ds:
            for item in self.ds.DoseReferences:
                if item.DoseReferenceStructureType == 'SITE':
                    self.plan['name'] = item.DoseReferenceDescription
                    self.plan['rxdose'] = item.TargetPrescriptionDose * 100

        return self.plan
