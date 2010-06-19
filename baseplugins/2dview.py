#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# 2dview.py
"""dicompyler plugin that displays images, structures and dose in 2D planes."""
# Copyright (c) 2010 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#

import wx
from wx.xrc import XmlResource, XRCCTRL, XRCID
from wx.lib.pubsub import Publisher as pub
from decimal import Decimal
import guiutil, util

def pluginProperties():
    """Properties of the plugin."""

    props = {}
    props['name'] = '2D View'
    props['description'] = "Display image, structure and dose data in 2D"
    props['author'] = 'Aditya Panchal'
    props['version'] = 0.1
    props['plugin_type'] = 'main'
    props['plugin_version'] = 1
    props['min_dicom'] = []
    props['recommended_dicom'] = ['ct', 'rtss', 'rtdose']

    return props

def pluginLoader(parent):
    """Function to load the plugin."""

    # Load the XRC file for our gui resources
    res = XmlResource(util.GetBasePluginsPath('2dview.xrc'))

    panel2DView = res.LoadPanel(parent, 'plugin2DView')
    panel2DView.Init(res)

    return panel2DView

class plugin2DView(wx.Panel):
    """Plugin to display DICOM image, RT Structure, RT Dose in 2D."""

    def __init__(self):
        pre = wx.PrePanel()
        # the Create step is done by XRC.
        self.PostCreate(pre)

    def Init(self, res):
        """Method called after the panel has been initialized."""

        # Bind ui events to the proper methods
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

        # Initialize variables
        self.images = []
        self.structures = {}

        # Set up pubsub
        pub.subscribe(self.OnUpdatePatient, 'patient.updated.parsed_data')
        pub.subscribe(self.OnStructureCheck, 'structures.checked')
        pub.subscribe(self.OnKeyDown, 'main.key_down')

    def OnUpdatePatient(self, msg):
        """Update and load the patient data."""

        if msg.data.has_key('images'):
            self.images = msg.data['images']
        else:
            self.images = []
        self.SetBackgroundColour(wx.Colour(0, 0, 0))
        # Set the first image to the middle of the series
        self.imagenum = len(self.images)/2
        # Get the Patient to Pixel LUT
        self.patpixlut = self.images[self.imagenum-1].GetPatientToPixelLUT()
        # Set the focus to this panel so we can capture key events
        self.SetFocus()
        self.Refresh()

    def OnStructureCheck(self, msg):
        """When the structure list changes, update the panel."""

        self.structures = msg.data
        self.SetFocus()
        self.Refresh()

    def DrawStructure(self, structure, gc, position):
        """Draw the given structure on the panel."""

        # Draw the structure only if the structure has contours
        # on the current image position
        if structure['planes'].has_key(position):
            # Set the color of the contour
            color = wx.Colour(structure['color'][0], structure['color'][1],
                structure['color'][2], 128)
            gc.SetBrush(wx.Brush(color))
            gc.SetPen(wx.Pen(tuple(structure['color'])))
            for contour in structure['planes'][position]:
                if (contour['geometricType'] == u"CLOSED_PLANAR"):
                    # Create the path for the contour
                    path = gc.CreatePath()
                    # Convert the structure data to pixel data
                    pixeldata = self.GetContourPixelData(contour)

                    # Move the origin to the first point of the contour
                    point = pixeldata[0]
                    path.MoveToPoint(point['x'], point['y'])

                    # Add each contour point to the path
                    for point in pixeldata:
                        path.AddLineToPoint(point['x'], point['y'])
                # Draw the path
                gc.DrawPath(path)

    def GetContourPixelData(self, contour):
        """Convert structure data into pixel data using the patient to pixel LUT."""

        pixeldata = []
        # For each point in the structure data
        # look up the value in the LUT and find the corresponding pixel pair
        for p, point in enumerate(contour['contourData']):
            for xv, xval in enumerate(self.patpixlut[0]):
                if (xval > point['x']):
                    break
            for yv, yval in enumerate(self.patpixlut[1]):
                if (yval > point['y']):
                    break
            pixeldata.append({'x':xv, 'y':yv})

        return pixeldata

    def OnPaint(self, evt):
        """Update the panel when it needs to be refreshed."""

        # Special case for Windows to account for flickering
        # if and only if images are loaded
        if (guiutil.IsMSWindows() and len(self.images)):
            dc = wx.BufferedPaintDC(self)
            self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        else:
            dc = wx.PaintDC(self)

        width, height = self.GetClientSize()
        try:
            gc = wx.GraphicsContext.Create(dc)
        except NotImplementedError:
            dc.DrawText("This build of wxPython does not support the "
                        "wx.GraphicsContext family of classes.",
                        25, 25)
            return

        # If we have images loaded, process and show the image
        if len(self.images):
            # Redraw the background on Windows
            if guiutil.IsMSWindows():
                gc.SetBrush(wx.Brush(wx.Colour(0, 0, 0)))
                gc.SetPen(wx.Pen(wx.Colour(0, 0, 0)))
                gc.DrawRectangle(0, 0, width, height)

            image = guiutil.convert_pil_to_wx(
                self.images[self.imagenum-1].GetImage())
            bmp = wx.BitmapFromImage(image)
            bwidth, bheight = bmp.GetSize()

            # Center the image
            gc.Translate((width-bwidth)/2, (height-bheight)/2)
            gc.DrawBitmap(bmp,
                0, 0, bwidth, bheight)

            # Draw the structures if present
            imdata = self.images[self.imagenum-1].GetImageData()
            z = '%.2f' % imdata['position'][2]
            for id, structure in self.structures.iteritems():
                self.DrawStructure(structure, gc, Decimal(z))

            # Reset the origin for the text elements
            gc.Translate(-(width-bwidth)/2, -(height-bheight)/2)

            # Prepare the font for drawing the information text
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
            if guiutil.IsMac():
                font.SetPointSize(10)
            gc.SetFont(font, wx.WHITE)

            # Draw the information text
            imtext = "Image: " + str(self.imagenum) + "/" + str(len(self.images))
            gc.DrawText(imtext, 10, 7)
            impos = "Position: " + str(z) + " mm"
            gc.DrawText(impos, 10, height-17)

    def OnSize(self, evt):
        """Refresh the view when the size of the panel changes."""

        self.Refresh()
        evt.Skip()

    def OnKeyDown(self, evt):
        """Change the image when the user presses the appropriate keys."""

        # Needed to work around a bug in Windows. See main.py for more details.
        if guiutil.IsMSWindows():
            try:
                evt = evt.data
            except AttributeError:
                keyname = evt.GetKeyCode()

        if len(self.images):
            keyname = evt.GetKeyCode()
            prevkey = [wx.WXK_UP, wx.WXK_PAGEUP]
            nextkey = [wx.WXK_DOWN, wx.WXK_PAGEDOWN]
            if (keyname in prevkey):
                if (self.imagenum > 1):
                    self.imagenum -= 1
                    self.Refresh()
            if (keyname in nextkey):
                if (self.imagenum < len(self.images)):
                    self.imagenum += 1
                    self.Refresh()
            if (keyname == wx.WXK_HOME):
                self.imagenum = 1
                self.Refresh()
            if (keyname == wx.WXK_END):
                self.imagenum = len(self.images)
                self.Refresh()
