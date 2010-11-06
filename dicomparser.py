#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# dicomparser.py
"""Class that parses and returns formatted DICOM RT data."""
# Copyright (c) 2009-2010 Aditya Panchal
# Copyright (c) 2009 Roy Keyes
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/

from decimal import Decimal
import numpy as np
import dicom
from PIL import Image

class DicomParser:
    """Parses DICOM / DICOM RT files."""

    def __init__(self, dataset=None, filename=None):

        if dataset:
            self.ds = dataset
        elif filename:
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
        else:
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
        elif (self.ds.SOPClassUID == '1.2.840.10008.5.1.4.1.1.2'):
            return 'ct'
        else:
            return None

    def GetSOPInstanceUID(self):
        """Determine the SOP Class UID of the current file."""

        return self.ds.SOPInstanceUID

    def GetStudyInfo(self):
        """Return the study information of the current file."""

        study = {}
        if 'StudyDescription' in self.ds:
            desc=self.ds.StudyDescription
        else:
            desc='No description'
        study['description'] = desc
        study['id'] = self.ds.StudyInstanceUID
        
        return study

    def GetSeriesInfo(self):
        """Return the series information of the current file."""

        series = {}
        if 'SeriesDescription' in self.ds:
            desc=self.ds.SeriesDescription
        else:
            desc='No description'
        series['description'] = desc
        series['id'] = self.ds.SeriesInstanceUID
        series['study'] = self.ds.StudyInstanceUID
        series['referenceframe'] = self.ds.FrameofReferenceUID
        
        return series
    
    def GetReferencedSeries(self):
        """Return the SOP Class UID of the referenced series."""

        if "ReferencedFrameofReferences" in self.ds:
            if "RTReferencedStudies" in self.ds.ReferencedFrameofReferences[0]:
                if "RTReferencedSeries" in self.ds.ReferencedFrameofReferences[0].RTReferencedStudies[0]:
                    if "SeriesInstanceUID" in self.ds.ReferencedFrameofReferences[0].RTReferencedStudies[0].RTReferencedSeries[0]:
                        return self.ds.ReferencedFrameofReferences[0].RTReferencedStudies[0].RTReferencedSeries[0].SeriesInstanceUID
        else:
            return ''

    def GetFrameofReferenceUID(self):
        """Determine the Frame of Reference UID of the current file."""

        if 'FrameofReferenceUID' in self.ds:
            return self.ds.FrameofReferenceUID
        else:
            return ''

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

################################ Image Methods #################################

    def GetImageData(self, window = None, level = None):
        """Return the image data from a DICOM file."""

        data = {}

        data['position'] = self.ds.ImagePositionPatient
        data['orientation'] = self.ds.ImageOrientationPatient
        data['pixelspacing'] = self.ds.PixelSpacing
        data['rows'] = self.ds.Rows
        data['columns'] = self.ds.Columns
        if 'PatientPosition' in self.ds:
            data['patientposition'] = self.ds.PatientPosition

        return data

    def GetImage(self, window = None, level = None):
        """Return the image from a DICOM image storage file."""

        if ((window == None) and (level == None)):
            window = self.ds.WindowWidth
            level = self.ds.WindowCenter
        image = self.GetLUTValue(self.ds.pixel_array, window, level)

        return Image.fromarray(image).convert('L')

    def GetLUTValue(self, data, window, level):
        """Apply the RGB Look-Up Table for the given data and window/level value."""

        return np.piecewise(data,
            [data <= (level - 0.5 - (window-1)/2),
                data > (level - 0.5 + (window-1)/2)],
                [0, 255, lambda data: ((data - (level - 0.5))/(window-1) + 0.5)*(255-0)])

    def GetPatientToPixelLUT(self):
        """Get the image transformation matrix from the DICOM standard Part 3
            Section C.7.6.2.1.1"""

        di = self.ds.PixelSpacing[0]
        dj = self.ds.PixelSpacing[1]
        orientation = self.ds.ImageOrientationPatient
        position = self.ds.ImagePositionPatient

        m = np.matrix(
            [[orientation[0]*di, orientation[3]*dj, 0, position[0]],
            [orientation[1]*di, orientation[4]*dj, 0, position[1]],
            [orientation[2]*di, orientation[5]*dj, 0, position[2]],
            [0, 0, 0, 1]])

        x = []
        y = []
        for i in range(0, self.ds.Columns):
            imat = m * np.matrix([[i], [0], [0], [1]])
            x.append(float(imat[0]))
        for j in range(0, self.ds.Rows):
            jmat = m * np.matrix([[0], [j], [0], [1]])
            y.append(float(jmat[1]))

        return (x, y)

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
            return structures

        # Locate the name and number of each ROI
        if self.ds.has_key('StructureSetROIs'):
            for item in self.ds.StructureSetROIs:
                data = {}
                number = item.ROINumber
                data['id'] = number
                data['name'] = item.ROIName
                print 'Found ROI #' + str(number) + ': '  + data['name']
                structures[number] = data

        # Determine the type of each structure (PTV, organ, external, etc)
        if self.ds.has_key('RTROIObservations'):
            for item in self.ds.RTROIObservations:
                number = item.ReferencedROINumber
                structures[number]['RTROIType'] = item.RTROIInterpretedType

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
                        if plane.has_key('geometricType'):
                            z = Decimal(str(plane['contourData'][0][2]))
                            if not planes.has_key(z):
                                planes[z] = []
                            planes[z].append(plane)

                # Calculate the plane thickness for the current ROI
                structures[number]['thickness'] = self.CalculatePlaneThickness(planes)

                # Add the planes dictionary to the current ROI
                structures[number]['planes'] = planes

        return structures

    def GetContourPoints(self, array):
        """Parses an array of xyz points and returns a array of point dictionaries."""

        return zip(*[iter(array)]*3)

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

        if not "DVHs" in self.ds:
            return False
        else:
            return True

    def GetDVHs(self):
        """Returns the dose-volume histograms (DVHs)."""

        self.dvhs = {}

        if "DVHs" in self.ds:
            for item in self.ds.DVHs:
                dvhitem = {}
                # If the DVH is differential, convert it to a cumulative DVH
                if (self.ds.DVHs[0].DVHType == 'DIFFERENTIAL'):
                    dvhitem['data'] = self.GenerateCDVH(item.DVHData)
                    dvhitem['bins'] = len(dvhitem['data'])
                # Otherwise the DVH is cumulative
                # Remove "filler" values from DVH data array (even values are DVH values)
                else:
                    dvhitem['data'] = np.array(item.DVHData[1::2])
                    dvhitem['bins'] = int(item.DVHNumberofBins)
                dvhitem['type'] = 'CUMULATIVE'
                dvhitem['doseunits'] = item.DoseUnits
                dvhitem['volumeunits'] = item.DVHVolumeUnits
                dvhitem['scaling'] = item.DVHDoseScaling
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

    def GenerateCDVH(self, data):
        """Generate a cumulative DVH (cDVH) from a differential DVH (dDVH)"""

        dDVH = np.array(data)
        # Separate the dose and volume values into distinct arrays 
        dose = data[0::2]
        volume = data[1::2]

        # Get the min and max dose and volume values
        mindose = int(dose[0]*100)
        maxdose = int(sum(dose)*100)
        maxvol = sum(volume)

        # Determine the dose values that are missing from the original data
        missingdose = np.ones(mindose) * maxvol

        # Generate the cumulative dose and cumulative volume data
        k = 0
        cumvol = []
        cumdose = []
        while k < len(dose):
            cumvol += [sum(volume[k:])]
            cumdose += [sum(dose[:k])]
            k += 1
        cumvol = np.array(cumvol)
        cumdose = np.array(cumdose)*100

        # Interpolate the dDVH data for 1 cGy bins
        interpdose = np.arange(mindose, maxdose+1)
        interpcumvol = np.interp(interpdose, cumdose, cumvol)

        # Append the interpolated values to the missing dose values
        cumDVH = np.append(missingdose, interpcumvol)

        return cumDVH

    def GetDoseGrid(self, slicenumber = 0):
        """Return the dose grid for the given slice number."""

        sn = len(self.ds.pixel_array) - slicenumber
        return self.ds.pixel_array[sn].tolist()

    def GetIsodoseGrid(self, slicenumber = 0, level = 100):
        """Return the dose grid for the given slice number and isodose level."""

        sn = len(self.ds.pixel_array) - slicenumber
        isodose = (self.ds.pixel_array[sn] >= level).nonzero()
        return zip(isodose[1].tolist(), isodose[0].tolist())

    def GetDoseData(self):
        """Return the dose data from a DICOM RT Dose file."""

        data = self.GetImageData()
        data['doseunits'] = self.ds.DoseUnits
        data['dosetype'] = self.ds.DoseType
        data['dosesummationtype'] = self.ds.DoseSummationType
        data['dosegridscaling'] = self.ds.DoseGridScaling
        data['dosemax'] = float(self.ds.pixel_array.max())

        return data

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
                elif item.DoseReferenceStructureType == 'VOLUME':
                    if 'TargetPrescriptionDose' in item:
                        self.plan['rxdose'] = item.TargetPrescriptionDose * 100

        return self.plan
