# g4dose.py
# G4 RT-Dose plugin for dicompyler.
# Copyright (c) 2011-2012 Derek M. Tishler, Brian P. Tonner, and dicompyler contributors.
"""
Create RT Dose file from a GEANT4 or GAMOS DICOM phantom RT simulation utilizing
dose scoring with the GmPSPrinter3ddose or GmPSPrinterG4cout printers.
"""
# All rights reserved, released under a BSD license.
#    See the file license.txt included with this distribution, available at:
#    http://code.google.com/p/dicompyler-plugins/source/browse/plugins/g4dose/license.txt

#Requires wxPython, pyDicom, numpy, PIL, dicompyler.
import wx
from   wx.lib.pubsub import Publisher as pub
import dicom
from   dicom.dataset import Dataset, FileDataset
import os
import numpy as np
from   PIL import Image
from dicompyler import guiutil, util
import fnmatch
import logging
logger = logging.getLogger('dicompyler.g4dose')

def pluginProperties():

    props = {}
    props['name'] = 'G4 RT-Dose'
    props['description'] = "View RT-Dose from a Geant4/Gamos DICOM simulation"
    props['author'] = 'D.M. Tishler & B.P. Tonner'
    props['version'] = 0.5
    props['documentation'] = 'http://code.google.com/p/dicompyler-plugins/wiki/g4dose'
    props['license'] = 'license.txt'
    props['plugin_type'] = 'menu'
    props['plugin_version'] = 1
    props['min_dicom'] = ['images']
    props['recommended_dicom'] =  ['images','rtdose','rtplan']

    return props

class plugin():

    def __init__(self, parent):
        
        #Set subscriptions
        self.parent = parent
        pub.subscribe(self.OnUpdatePatient, 'patient.updated.raw_data')

    def OnUpdatePatient(self, msg):
        
        #Update data from pubsub.
        self.data = msg.data

    def addElement(self, tup):
        
        #Publish/broadcast the RT-Dose and rxdose.
        if tup:
            self.data.update({'rtdose':tup[0]})
            self.data.update({'rtplan':tup[1]})
            self.data.update({'rxdose':tup[2]})
        pub.sendMessage('patient.updated.raw_data', self.data)

    def pluginMenu(self, evt):

        #Input and main driver for creating RT Dose file from simulation output.
        msg        = "Select Dose File."
        loop       = True
        runG4cout  = False
        g4CoutType = 0
        while loop:
            loop   = False
            #Select Dose file & Data.dat
            dirdlg = wx.FileDialog(self.parent, msg, defaultFile='')
            if dirdlg.ShowModal() == wx.ID_OK:
                #Get path to file and file's directory
                pathDose   = dirdlg.GetPath()
                patientDir = os.path.dirname(pathDose)

                #Open dose file to determine the printer for parsing.
                checkG4Output = 0
                lCount = 0
                for i in open(pathDose,'r'):
                    lCount+=1
                    #Count the columns, it will be 2xN if it is a plain geant4 dicom output file.
                    if len(i.strip('\n').split()) == 2:
                        checkG4Output += 1
                    else:
                        checkG4Output = 0
                    
                    #Check for array size tuple on line 2
                    if len(i.strip('\n').split()) == 3 and lCount == 2: 
                        #Dose file from printer: GmPSPrinter3ddose
                        #Parse dose file, create RT-Dose DICOM object, broadcast RT-Dose.
                        self.addElement(self.loadGamos3ddose(patientDir, pathDose, self.data['images']))
                        loop = False
                        break
                    #Check for string on line 3, otherwise is it g4 output?
                    elif fnmatch.fnmatch(i, '*Number of entries*'):
                        runG4cout  = True
                        g4CoutType = 1
                        break
                    #Exit if g4 table seems obvious
                    elif checkG4Output >= 10:
                        runG4cout = True
                        break
                    else: 
                        msg  = "3ddose or g4cout dose file required!"
                        loop = True
                
                #Parse dose file from GmPSPrinterG4cout printer
                if runG4cout:
                    #Check if Data.dat is located with dose file.
                    if os.path.isfile(patientDir + '//Data.dat'):
                        #Parse dose file, create RT-Dose DICOM object, broadcast RT-Dose.
                        #Note patientDir is modified and passed here as pathData.
                        self.addElement(self.loadG4DoseGraph(g4CoutType, patientDir, patientDir+'//Data.dat', pathDose, self.data['images']))
                        break
                    #Loop for dialogue for Data.dat file if not found with dose file.
                    msg  = "Please select Data.dat" 
                    loop2 = True
                    while loop2:
                        loop2  = False
                        #Select Data.dat
                        dirdlg = wx.FileDialog(self.parent,msg)
                        if dirdlg.ShowModal() == wx.ID_OK:
                            pathData   = dirdlg.GetPath()
                            patientDir = os.path.dirname(pathData) 
                            #Confirm G4 simulation input and output files are found.
                            if fnmatch.fnmatch(pathData, '*Data.dat'):
                                #Parse dose file, create RT-Dose DICOM object, broadcast RT-Dose.
                                self.addElement(self.loadG4DoseGraph(g4CoutType, patientDir, pathData, pathDose, self.data['images']))
                                loop2 = False
                                break
                            else:
                                msg  = "Data.dat required!"
                                loop2 = True
                        dirdlg.Destroy()
                    #Exit file handeling loop.
                    loop = False
                    break
            dirdlg.Destroy()

    #Handle GmPSPrinter3ddose printer output
    def loadGamos3ddose(self, ptPath, doseFile, ds):
        
        #Open DOSXYZ dose file for phantom w/ slices in z dir.
        DoseFile = open(doseFile,'r')
        
        #First line is the number of events.
        NumEvents = float(DoseFile.readline())
        #Voxels is list [NX, NY, NZ]
        temp  = DoseFile.readline()  #Get Voxel dimensions
        temp  = temp.strip('\n')     #Strip linefeed
        [NX,NY,NZ] = [int(x) for x in temp.split()]
        #Get the coordinates of the x positions.
        temp  = DoseFile.readline()
        temp  = temp.strip('\n')
        XVals =[float(x) for x in temp.split()]
        #Get the coordinates of the y positions.
        temp  = DoseFile.readline()
        temp  = temp.strip('\n')
        YVals = [float(x) for x in temp.split()]
        #Get the coordinates of the z positions.
        temp  = DoseFile.readline()
        temp  = temp.strip('\n')
        ZVals = [float(x) for x in temp.split()]

        #Create and fill 3d dose array.
        DoseData = np.zeros((NX,NY,NZ),float)
        for iz in range(0,NZ,1):
            for iy in range (0,NY,1):
                #Read in one line of x values
                temp = DoseFile.readline()
                temp = temp.strip('\n')
                row  = temp.split()
                DoseData[:,iy,iz] = row

        #Image dimensions(Pixels). NY,NX represent voxel image dimensions.
        imageCol = ds[0].pixel_array.shape[0]
        imageRow = ds[0].pixel_array.shape[1]

        #Max dose value in Gy
        Max = np.max(DoseData)
        
        #Ask for RxDose and normalze.
        N = Max
        dlg = wx.TextEntryDialog(self.parent, 'RxDose will be 95% of Max Dose({0:g})\nPlease enter new Max Dose in Gy:'.format(Max),'Set Max Dose:')
        dlg.SetValue("%s" % str(1.))
        if dlg.ShowModal() == wx.ID_OK:
            N  = float(dlg.GetValue())
        dlg.Destroy()

        #Set rx dose.
        rxDose = 95.*N
        doseGridScale = float(N/65535.)


        #Copy DoseData array for uncompressing and masking.
        DDVoxDimImage = np.uint32(DoseData/Max*65535.)*np.ones(np.shape(DoseData),np.uint32)
        DDImgDimImage = np.ones((NZ,imageRow,imageCol),np.uint32)
        
        #Uncompress dose image and position in FFS or HFS. Add more support!
        for i in range(NZ):
            DDImgDimImage[i,:,:] = np.array(Image.frombuffer('I',(NY,NX),DDVoxDimImage[:,:,i].tostring(),'raw','I',0,1)
                                        .resize((imageCol, imageRow), Image.NEAREST)
                                        .rotate(-90)
                                        .transpose(Image.FLIP_LEFT_RIGHT),np.uint32)
        
        #Create RT-Dose File and copy info from CT
        rtDose, rtPlan = self.copyCTtoRTDose(ptPath, ds[0], DDImgDimImage, imageRow, imageCol, NZ, doseGridScale)

        #Add RXDose to RTPlan
        rtPlan.rxdose = rxDose
        
        return rtDose, rtPlan, rxDose

    #Handle GmPSPrinterG4cout printer output
    def loadG4DoseGraph(self, fileType, ptPath, dataFile, doseFile, ds):

        #Load number of slices and compression value from data.dat.
        file = open(dataFile)
        compression = int(file.readline())
        sliceCount  = len(ds)

        if fileType == 0:
            #Load dosegraph from dicom.out
            doseTable = np.loadtxt(doseFile)
        else:
            #Parse GmPSPrinterG4cout
            Go = False
            doseTable = []
            for i in open(doseFile,'r'):
                #Data begins after this line
                if fnmatch.fnmatch(i, '*Number of entries*'):
                    numEnt = i.strip('\n').split()[3]
                    Go = True
                #Ends on return of Sum All.
                elif fnmatch.fnmatch(i, '*SUM ALL*'):
                    sumAll = [3]
                    break
                #Save 2xN table from dose file.
                elif Go:
                    tempRow = i.strip('\n').split()
                    doseTable.append([float(tempRow[1]),float(tempRow[3])])
            doseTable = np.array(doseTable)
                    
        #Exit if simulator had null output.
        if len(doseTable) == 0:
            msgE = 'dicom.out is empty!\nCheck simulation for errors.\nExiting'
            dial = wx.MessageDialog(None, msgE, 'Error', wx.OK | wx.ICON_ERROR)
            dial.ShowModal()
            return

        #Temp, progress bar.
        guageCount = 0
        prog = [True,False]
        guage = wx.ProgressDialog("G4 RT-Dose","Building RT-Dose from GAMOS simulation\n",
                                  len(doseTable)+sliceCount+1,style=wx.PD_REMAINING_TIME |
                                  wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT)

        #image dimensions from images(DICOM dosegraph object)
        imageCol = ds[0].pixel_array.shape[0]
        imageRow = ds[0].pixel_array.shape[1]
        #voxel dimensions.
        voxelCol = imageCol/compression
        voxelRow = imageRow/compression
        #Repeated values.
        voxelDim = voxelCol*voxelRow*sliceCount
        area     = voxelCol*voxelRow
        
        #G4 compression value error. See documentation.
        if doseTable[-1][0] > voxelDim:
            msgE = 'Compression value error in data.dat!\nPlease delete binary files and re-run GEANT4.'
            dial = wx.MessageDialog(None, msgE, 'Error', wx.OK | wx.ICON_ERROR)
            dial.ShowModal()
            guage.Destroy()
            return

        #Store images for resizing.
        imageList = list()
        for i in range(sliceCount):
            imageList.append([])
            imageList[i] = np.zeros((voxelCol,voxelRow),np.uint32)

        #Create a new rescaled dose table.
        Max = max(doseTable[:, 1])
        #Normalize dose data and prepare for LUT in dicompyler.
        scaleTable = np.ones((len(doseTable),2),np.float32)
        #4294967295,65535,255;2147483647,32767,127.
        scaleTable[:, 1] = np.round((doseTable[:, 1]/Max)*65535.)
        doseTableInt = np.ones((len(doseTable), 2), np.uint32)*np.uint32(scaleTable)
        del scaleTable

        #Ask for RxDose and normalze.
        N = Max
        dlg = wx.TextEntryDialog(self.parent, 'RxDose will be 95% of Max Dose({0:g})\nPlease enter new Max Dose in Gy:'.format(Max),'Set Max Dose:')
        dlg.SetValue("%s" % str(1.))
        if dlg.ShowModal() == wx.ID_OK:
            N  = float(dlg.GetValue())
        dlg.Destroy()

        #Set RX Dose And Dose Grid Scale for RT Dose.
        doseGridScale = N/65535.
        rxDose        = 95.*N
       
        #Unravel dose table into 3d dose array.
        for index, vID in enumerate(doseTable[:, 0]):
            #Unravel the index instead of search. GO NUMPY!
            newIndex = np.unravel_index(int(vID), (sliceCount, voxelCol, voxelRow))
            imageList[newIndex[0]][newIndex[1]][newIndex[2]] = doseTableInt[index][1]
            #Update progress bar & check for abort.
            if prog[0]:
                guageCount += 1
                prog = guage.Update(guageCount,"Building RT-Dose from GEANT4 simulation")
            else:
                guage.Destroy()
                return
     
        #Convert to array and uncompress the dose image.
        pD3D = np.zeros((sliceCount,imageRow,imageCol),np.uint32)
        for i in range(sliceCount):
            #Use PIL to resize, Voxel to Pixel conversion.
            pD3D[i] = np.array(Image.frombuffer('I', (voxelCol, voxelRow), imageList[i], 'raw', 'I', 0, 1)
                                               .resize((imageCol, imageRow), Image.NEAREST), np.uint32)
            #Update progress bar & check for abort.
            if prog[0]:
                guageCount += 1
                prog = guage.Update(guageCount,"Building RT-Dose from GEANT4 simulation\nRe-sizing image: {0:n}".format(i+1))
            else:
                guage.Destroy()
                return

        #Create RT-Dose File and copy info from CT.
        rtDose, rtPlan = self.copyCTtoRTDose(ptPath, ds[0], pD3D, imageRow, imageCol, sliceCount, doseGridScale)

        #Add RXDose to RTPlan
        rtPlan.rxdose = rxDose

        #Close progress bar.
        guageCount += 1
        prog = guage.Update(guageCount,"Building RT-Dose from GEANT4 simulation\n")
        guage.Destroy()
        
        return rtDose, rtPlan, rxDose

    def copyCTtoRTDose(self, path, ds, doseData, imageRow, imageCol, sliceCount, dgs):
        
        # Create a RTDose file for broadcasting.
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.481.2' # CT Image Storage
        # Needs valid UID
        file_meta.MediaStorageSOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
        file_meta.ImplementationClassUID = ds.file_meta.ImplementationClassUID

        #create DICOM RT-Dose object.
        rtdose = FileDataset(path + '/rtdose.dcm', {}, file_meta=file_meta, preamble="\0"*128)
        
        #No DICOM object standard. Use only required to avoid errors with viewers.
        rtdose.SOPInstanceUID = ds.SOPInstanceUID
        rtdose.SOPClassUID = '1.2.840.10008.5.1.4.1.1.481.2'
        rtdose.file_meta.TransferSyntaxUID = ds.file_meta.TransferSyntaxUID
        rtdose.PatientsName = ds.PatientsName
        rtdose.PatientID = ds.PatientID
        rtdose.PatientsBirthDate = ds.PatientsBirthDate
        #Crashed caused if no sex.
        try:
            rtdose.PatientsSex = ds.PatientsSex
        except:
            rtdose.PatientsSex, ds.PatientsSex = 'O', 'O'
            self.data.update({'images':ds})
            
        rtdose.StudyDate                  = ds.StudyDate
        rtdose.StudyTime                  = ds.StudyTime
        rtdose.StudyInstanceUID           = ds.StudyInstanceUID
        rtdose.SeriesInstanceUID          = ds.SeriesInstanceUID
        rtdose.StudyID                    = ds.StudyID
        rtdose.SeriesNumber               = ds.SeriesNumber
        rtdose.Modality                   = 'RTDOSE'
        rtdose.ImagePositionPatient       = ds.ImagePositionPatient
        rtdose.ImageOrientationPatient    = ds.ImageOrientationPatient
        rtdose.FrameofReferenceUID        = ds.FrameofReferenceUID
        rtdose.PositionReferenceIndicator = ds.PositionReferenceIndicator
        rtdose.PixelSpacing               = ds.PixelSpacing
        rtdose.SamplesperPixel            = 1
        rtdose.PhotometricInterpretation  = 'MONOCHROME2'
        rtdose.NumberofFrames             = sliceCount
        rtdose.Rows                       =  imageRow
        rtdose.Columns                    = imageCol
        rtdose.BitsAllocated              = 32
        rtdose.BitsStored                 = 32
        rtdose.HighBit                    = 31
        rtdose.PixelRepresentation        = 0
        rtdose.DoseUnits                  = 'GY'
        rtdose.DoseType                   = 'PHYSICAL'
        rtdose.DoseSummationType          = 'FRACTION'
        #In case spaceing tag is missing.
        if not ds.has_key('SpacingBetweenSlices'):
            ds.SpacingBetweenSlices = ds.SliceThickness
        #Ensure patient pos is on "Last slice".
        if fnmatch.fnmatch(ds.PatientPosition, 'FF*'):
            #For compliance with dicompyler update r57d9155cc415 which uses a reverssed slice ordering.
            doseData = doseData[::-1]
            rtdose.ImagePositionPatient[2] = ds.ImagePositionPatient[2]
        elif fnmatch.fnmatch(ds.PatientPosition, 'HF*'):
            rtdose.ImagePositionPatient[2] = ds.ImagePositionPatient[2] - (sliceCount-1)*ds.SpacingBetweenSlices
        #Create Type A(Relative) GFOV.
        rtdose.GridFrameOffsetVector = list(np.arange(0., sliceCount*ds.SpacingBetweenSlices,ds.SpacingBetweenSlices))
        #Scaling from int to physical dose
        rtdose.DoseGridScaling = dgs

        #Store images in pixel_array(int) & Pixel Data(raw).  
        rtdose.pixel_array = doseData
        rtdose.PixelData   = doseData.tostring()

        #Tag required by dicompyler.
        plan_meta = Dataset()
        rtdose.ReferencedRTPlans = []
        rtdose.ReferencedRTPlans.append([])
        rtdose.ReferencedRTPlans[0] = plan_meta
        rtdose.ReferencedRTPlans[0].ReferencedSOPClassUID = 'RT Plan Storage'
        rtdose.ReferencedRTPlans[0].ReferencedSOPInstanceUID = ds.SOPInstanceUID


        #Create RTPlan to acticate DVH
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.481.5' # RT Plan Storage
        file_meta.MediaStorageSOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
        file_meta.ImplementationClassUID = ds.file_meta.ImplementationClassUID

        #create DICOM RT-Plan object.
        rtPlan = FileDataset(path + '/rtplan.dcm', {}, file_meta=file_meta, preamble="\0"*128)
        
        #No DICOM object standard. Use only required to avoid errora with viewers.
        rtPlan.SOPInstanceUID              = ds.SOPInstanceUID
        rtPlan.SOPClassUID                 = '1.2.840.10008.5.1.4.1.1.481.5'
        rtPlan.ReferencedSOPInstanceUID    = ds.SOPInstanceUID #Need to change
        rtPlan.file_meta.TransferSyntaxUID = ds.file_meta.TransferSyntaxUID
        rtPlan.PatientsName                = ds.PatientsName
        rtPlan.PatientID                   = ds.PatientID
        rtPlan.PatientsSex                 = ds.PatientsSex
        rtPlan.PatientsBirthDate           = ds.PatientsBirthDate
        rtPlan.RTPlanLabel                 = 'Simulation'
        rtPlan.RTPlanDate                  = ds.StudyDate
        rtPlan.RTPlanTime                  = ds.StudyTime
        rtPlan.Modality                    = 'RTPLAN'
        rtPlan.StudyInstanceUID            = ds.StudyInstanceUID
        rtPlan.SeriesInstanceUID           = ds.SeriesInstanceUID
        rtPlan.StudyID                     = ds.StudyID
        rtPlan.SeriesNumber                = ds.SeriesNumber
        
        return rtdose, rtPlan
