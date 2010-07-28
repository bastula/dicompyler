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
    props['min_dicom'] = ['images']
    props['recommended_dicom'] = ['images', 'rtss', 'rtdose']

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
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

        # Initialize variables
        self.images = []
        self.structures = {}
        self.window = 0
        self.level = 0
        self.zoom = 1

        # Setup toolbar controls
        if guiutil.IsGtk():
            import gtk
            zoominbmp = wx.ArtProvider_GetBitmap(gtk.STOCK_ZOOM_IN, wx.ART_OTHER, (24, 24))
            zoomoutbmp = wx.ArtProvider_GetBitmap(gtk.STOCK_ZOOM_OUT, wx.ART_OTHER, (24, 24))
        else:
            zoominbmp = wx.Bitmap(util.GetResourcePath('magnifier_zoom_in.png'))
            zoomoutbmp = wx.Bitmap(util.GetResourcePath('magnifier_zoom_out.png'))
        self.tools = []
        self.tools.append({'label':"Zoom In", 'bmp':zoominbmp, 'shortHelp':"Zoom In", 'eventhandler':self.OnZoomIn})
        self.tools.append({'label':"Zoom Out", 'bmp':zoomoutbmp, 'shortHelp':"Zoom Out", 'eventhandler':self.OnZoomOut})

        # Set up pubsub
        pub.subscribe(self.OnUpdatePatient, 'patient.updated.parsed_data')
        pub.subscribe(self.OnStructureCheck, 'structures.checked')
        pub.subscribe(self.OnIsodoseCheck, 'isodoses.checked')

    def OnUpdatePatient(self, msg):
        """Update and load the patient data."""

        if msg.data.has_key('images'):
            self.images = msg.data['images']
            # Set the first image to the middle of the series
            self.imagenum = len(self.images)/2
            image = self.images[self.imagenum-1]
            self.structurepixlut = image.GetPatientToPixelLUT()
            # Determine the default window and level of the series
            if ('WindowWidth' in image.ds) and ('WindowCenter' in image.ds):
                self.window = image.ds.WindowWidth
                self.level = image.ds.WindowCenter
            else:
                wmax = 0
                wmin = 0
                if (image.ds.pixel_array.max() > wmax):
                    wmax = image.ds.pixel_array.max()
                if (image.ds.pixel_array.min() < wmin):
                    wmin = image.ds.pixel_array.min()
                self.window = int(abs(wmax) + abs(wmin))
                self.level = int(self.window / 2 - abs(wmin))
            # Dose display depends on whether we have images loaded or not
            self.isodoses = {}
            if msg.data.has_key('dose'):
                self.dose = msg.data['dose']
                self.dosedata = self.dose.GetDoseData()
                # First get the dose grid LUT
                doselut = self.dose.GetPatientToPixelLUT()
                # Then convert dose grid LUT into an image pixel LUT
                self.dosepixlut = self.GetDoseGridPixelData(self.structurepixlut, doselut)
            else:
                self.dose = []
            if msg.data.has_key('plan'):
                self.rxdose = msg.data['plan']['rxdose']
            else:
                self.rxdose = 0
        else:
            self.images = []

        self.SetBackgroundColour(wx.Colour(0, 0, 0))
        # Set the focus to this panel so we can capture key events
        self.SetFocus()
        self.Refresh()

    def OnFocus(self):
        """Bind to certain events when the plugin is focused."""

        # Bind keyboard and mouse events
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        pub.subscribe(self.OnKeyDown, 'main.key_down')
        pub.subscribe(self.OnMouseWheel, 'main.mousewheel')

    def OnUnfocus(self):
        """Unbind to certain events when the plugin is unfocused."""

        # Unbind keyboard and mouse events
        self.Unbind(wx.EVT_KEY_DOWN)
        self.Unbind(wx.EVT_MOUSEWHEEL)
        pub.unsubscribe(self.OnKeyDown)
        pub.unsubscribe(self.OnMouseWheel)

    def OnDestroy(self, evt):
        """Unbind to all events before the plugin is destroyed."""

        pub.unsubscribe(self.OnUpdatePatient)
        pub.unsubscribe(self.OnStructureCheck)
        pub.unsubscribe(self.OnIsodoseCheck)
        self.OnUnfocus()

    def OnStructureCheck(self, msg):
        """When the structure list changes, update the panel."""

        self.structures = msg.data
        self.SetFocus()
        self.Refresh()

    def OnIsodoseCheck(self, msg):
        """When the isodose list changes, update the panel."""

        self.isodoses = msg.data
        self.SetFocus()
        self.Refresh()

    def DrawStructure(self, structure, gc, position, prone, feetfirst):
        """Draw the given structure on the panel."""

        # Draw the structure only if the structure has contours
        # on the current image position
        if structure['planes'].has_key(position):
            # Set the color of the contour
            color = wx.Colour(structure['color'][0], structure['color'][1],
                structure['color'][2], 128)
            # Set fill (brush) color, transparent for external contour
            if (('RTROIType' in structure) and (structure['RTROIType'].lower() == 'external')):
                gc.SetBrush(wx.Brush(color, style=wx.TRANSPARENT))
            else:
                gc.SetBrush(wx.Brush(color))
            gc.SetPen(wx.Pen(tuple(structure['color'])))
            for contour in structure['planes'][position]:
                if (contour['geometricType'] == u"CLOSED_PLANAR"):
                    # Create the path for the contour
                    path = gc.CreatePath()
                    # Convert the structure data to pixel data
                    pixeldata = self.GetContourPixelData(
                        self.structurepixlut, contour['contourData'], prone, feetfirst)

                    # Move the origin to the first point of the contour
                    point = pixeldata[0]
                    path.MoveToPoint(point[0], point[1])

                    # Add each contour point to the path
                    for point in pixeldata:
                        path.AddLineToPoint(point[0], point[1])
                # Draw the path
                gc.DrawPath(path)

    def DrawIsodose(self, isodose, gc, imagenum):
        """Draw the given structure on the panel."""

        # Calculate the isodose level according to rx dose and dose grid scaling
        level = isodose['data']['level'] * self.rxdose / (self.dosedata['dosegridscaling'] * 10000)
        # Get the isodose contour data for this slice and isodose level
        contour = self.dose.GetIsodoseGrid(imagenum, level)

        if len(contour):
            # Set the color of the isodose line
            color = wx.Colour(isodose['color'][0], isodose['color'][1],
                isodose['color'][2], 64)
            gc.SetBrush(wx.Brush(color))
            gc.SetPen(wx.Pen(tuple(isodose['color'])))

            # Create the path for the isodose line
            path = gc.CreatePath()

            # Move the origin to the first point of the isodose line
            point = contour[0]
            path.MoveToPoint(
                self.dosepixlut[0][point[0]], self.dosepixlut[1][point[1]])

            # Create two arrays of points: left side (down) and right side (up)
            prevpt = (self.dosepixlut[0][point[0]], self.dosepixlut[1][point[1]])
            down = [(self.dosepixlut[0][point[0]], self.dosepixlut[1][point[1]])]
            up = []
            for index, point in enumerate(contour):
                pt = (self.dosepixlut[0][point[0]], self.dosepixlut[1][point[1]])
                # If the point is on a new line,
                # add the point to down and add the prev point to up
                if (self.dosepixlut[1][point[1]] > prevpt[1]):
                    down.append(pt)
                    up.append(prevpt)
                # If this is the very last point, add it to up
                if ((index-1) == len(contour)):
                    up.append(pt)
                # Save the point for comparsion to the next point
                prevpt = pt

            # Add each contour point to the path, first drawing the left side,
            # going down, then drawing the right side going up
            for point in down:
                path.AddLineToPoint(point[0], point[1])
            for point in reversed(up):
                path.AddLineToPoint(point[0], point[1])
            # Draw a line back to the original starting point
            path.AddLineToPoint(
                self.dosepixlut[0][contour[0][0]], self.dosepixlut[1][contour[0][1]])
            # Draw the path
            gc.DrawPath(path)

    def GetContourPixelData(self, pixlut, contour, prone = False, feetfirst = False):
        """Convert structure data into pixel data using the patient to pixel LUT."""

        pixeldata = []
        # For each point in the structure data
        # look up the value in the LUT and find the corresponding pixel pair
        for p, point in enumerate(contour):
            for xv, xval in enumerate(pixlut[0]):
                if (xval > point[0] and not prone and not feetfirst):
                    break
                elif (xval < point[0]):
                    if feetfirst or prone:
                        break
            for yv, yval in enumerate(pixlut[1]):
                if (yval > point[1] and not prone):
                    break
                elif (yval < point[1] and prone):
                    break
            pixeldata.append((xv, yv))

        return pixeldata

    def GetDoseGridPixelData(self, pixlut, doselut):
        """Convert dosegrid data into pixel data using the dose to pixel LUT."""

        dosedata = []
        x = []
        y = []
        # For each point in the dose data
        # look up the value in the LUT and find the corresponding pixel pair
        for p, point in enumerate(doselut[0]):
            for xv, xval in enumerate(pixlut[0]):
                if (abs(xval - point) < 1):
                    x.append(xv)
                    break
        for p, point in enumerate(doselut[1]):
            for yv, yval in enumerate(pixlut[1]):
                if (abs(yval - point) < 1):
                    y.append(yv)
                    break
        return (x, y)

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
            # Save the original drawing state
            gc.PushState()
            # Scale the image by the zoom factor
            gc.Scale(self.zoom, self.zoom)

            # Redraw the background on Windows
            if guiutil.IsMSWindows():
                gc.SetBrush(wx.Brush(wx.Colour(0, 0, 0)))
                gc.SetPen(wx.Pen(wx.Colour(0, 0, 0)))
                gc.DrawRectangle(0, 0, width, height)

            image = guiutil.convert_pil_to_wx(
                self.images[self.imagenum-1].GetImage(self.window, self.level))
            bmp = wx.BitmapFromImage(image)
            bwidth, bheight = bmp.GetSize()

            # Center the image
            gc.Translate((width-bwidth*self.zoom)/(2*self.zoom),
                         (height-bheight*self.zoom)/(2*self.zoom))
            gc.DrawBitmap(bmp, 0, 0, bwidth, bheight)

            # Draw the structures if present
            imdata = self.images[self.imagenum-1].GetImageData()
            z = '%.2f' % imdata['position'][2]
            # Determine whether the patient is prone or supine
            if 'p' in imdata['patientposition'].lower():
                prone = True
            else:
                prone = False
            # Determine whether the patient is feet first or head first
            if 'ff' in imdata['patientposition'].lower():
                feetfirst = True
            else:
                feetfirst = False
            for id, structure in self.structures.iteritems():
                self.DrawStructure(structure, gc, Decimal(z), prone, feetfirst)

            # Draw the isodoses if present
            for id, isodose in iter(sorted(self.isodoses.iteritems())):
                self.DrawIsodose(isodose, gc, self.imagenum)

            # Restore the translation and scaling
            gc.PopState()

            # Prepare the font for drawing the information text
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
            if guiutil.IsMac():
                font.SetPointSize(10)
            gc.SetFont(font, wx.WHITE)

            # Draw the information text
            imtext = "Image: " + str(self.imagenum) + "/" + str(len(self.images))
            te = gc.GetFullTextExtent(imtext)
            gc.DrawText(imtext, 10, 7)
            impos = "Position: " + str(z) + " mm"
            gc.DrawText(impos, 10, 7+te[1]*1.1)
            if ("%.3f" % self.zoom == "1.000"):
                zoom = "1"
            else:
                zoom = "%.3f" % self.zoom
            imzoom = "Zoom: " + zoom + ":1"
            gc.DrawText(imzoom, 10, height-17)
            imzoom = "Image Size: " + str(bheight) + "x" + str(bheight) + " px"
            gc.DrawText(imzoom, 10, height-17-te[1]*1.1)

    def OnSize(self, evt):
        """Refresh the view when the size of the panel changes."""

        self.Refresh()
        evt.Skip()

    def OnZoomIn(self, evt):
        """Zoom the view in."""

        self.zoom = self.zoom * 1.1
        self.Refresh()

    def OnZoomOut(self, evt):
        """Zoom the view out."""

        if (self.zoom > 1):
            self.zoom = self.zoom / 1.1
            self.Refresh()

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
            zoominkey = [43, 61, 388] # Keys: +, =, Numpad add
            zoomoutkey = [45, 95, 390] # Keys: -, _, Numpad subtract
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
            if (keyname in zoominkey):
                self.OnZoomIn(None)
            if (keyname in zoomoutkey):
                self.OnZoomOut(None)

    def OnMouseWheel(self, evt):
        """Change the image when the user scrolls the mouse wheel."""

        # Needed to work around a bug in Windows. See main.py for more details.
        if guiutil.IsMSWindows():
            try:
                evt = evt.data
            except AttributeError:
                delta = evt.GetWheelDelta()
                rot = evt.GetWheelRotation()

        if len(self.images):
            delta = evt.GetWheelDelta()
            rot = evt.GetWheelRotation()
            rot = rot/delta
            if (rot >= 1):
                if (self.imagenum > 1):
                    self.imagenum -= 1
                    self.Refresh()
            if (rot <= -1):
                if (self.imagenum < len(self.images)):
                    self.imagenum += 1
                    self.Refresh()
