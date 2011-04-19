#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# 2dview.py
"""dicompyler plugin that displays images, structures and dose in 2D planes."""
# Copyright (c) 2009-2011 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#

import wx
from wx.xrc import XmlResource, XRCCTRL, XRCID
from wx.lib.pubsub import Publisher as pub
from matplotlib import _cntr as cntr
from matplotlib import __version__ as mplversion
import numpy as np
import guiutil, util

def pluginProperties():
    """Properties of the plugin."""

    props = {}
    props['name'] = '2D View'
    props['description'] = "Display image, structure and dose data in 2D"
    props['author'] = 'Aditya Panchal'
    props['version'] = 0.3
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
        self.pan = [0, 0]
        self.bwidth = 0
        self.bheight = 0
        self.mousepos = (-10000, -10000)
        self.mouse_in_window = False
        self.isodose_line_style = 'Solid'
        self.isodose_fill_opacity = 25
        self.structure_line_style = 'Solid'
        self.structure_fill_opacity = 50

        # Setup toolbar controls
        if guiutil.IsGtk():
            import gtk
            zoominbmp = wx.ArtProvider_GetBitmap(gtk.STOCK_ZOOM_IN, wx.ART_OTHER, (24, 24))
            zoomoutbmp = wx.ArtProvider_GetBitmap(gtk.STOCK_ZOOM_OUT, wx.ART_OTHER, (24, 24))
            drawingstyles = ['Solid', 'Transparent', 'Dot']
        else:
            zoominbmp = wx.Bitmap(util.GetResourcePath('magnifier_zoom_in.png'))
            zoomoutbmp = wx.Bitmap(util.GetResourcePath('magnifier_zoom_out.png'))
            drawingstyles = ['Solid', 'Transparent', 'Dot', 'Dash', 'Dot Dash']
        self.tools = []
        self.tools.append({'label':"Zoom In", 'bmp':zoominbmp, 'shortHelp':"Zoom In", 'eventhandler':self.OnZoomIn})
        self.tools.append({'label':"Zoom Out", 'bmp':zoomoutbmp, 'shortHelp':"Zoom Out", 'eventhandler':self.OnZoomOut})

        # Set up preferences
        self.preferences = [
            {'Drawing Settings':
                [{'name':'Isodose Line Style',
                 'type':'choice',
               'values':drawingstyles,
              'default':'Solid',
             'callback':'2dview.drawingprefs.isodose_line_style'},
                {'name':'Isodose Fill Opacity',
                 'type':'range',
               'values':[0, 100],
              'default':25,
                'units':'%',
             'callback':'2dview.drawingprefs.isodose_fill_opacity'},
                {'name':'Structure Line Style',
                 'type':'choice',
               'values':drawingstyles,
              'default':'Solid',
             'callback':'2dview.drawingprefs.structure_line_style'},
                {'name':'Structure Fill Opacity',
                 'type':'range',
               'values':[0, 100],
              'default':50,
                'units':'%',
             'callback':'2dview.drawingprefs.structure_fill_opacity'}]
            }]

        # Set up pubsub
        pub.subscribe(self.OnUpdatePatient, 'patient.updated.parsed_data')
        pub.subscribe(self.OnStructureCheck, 'structures.checked')
        pub.subscribe(self.OnIsodoseCheck, 'isodoses.checked')
        pub.subscribe(self.OnDrawingPrefsChange, '2dview.drawingprefs')
        pub.sendMessage('preferences.requested.values', '2dview.drawingprefs')

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
                if isinstance(image.ds.WindowWidth, float):
                    self.window = image.ds.WindowWidth
                elif isinstance(image.ds.WindowWidth, list):
                    if (len(image.ds.WindowWidth) > 1):
                        self.window = image.ds.WindowWidth[1]
                if isinstance(image.ds.WindowCenter, float):
                    self.level = image.ds.WindowCenter
                elif isinstance(image.ds.WindowCenter, list):
                    if (len(image.ds.WindowCenter) > 1):
                        self.level = image.ds.WindowCenter[1]
            # If no default window and level, determine via min/max of data
            else:
                wmax = 0
                wmin = 0
                # Rescale the slope and intercept of the image if present
                if (image.ds.has_key('RescaleIntercept') and
                    image.ds.has_key('RescaleSlope')):
                    pixel_array = image.ds.pixel_array*image.ds.RescaleSlope + \
                                  image.ds.RescaleIntercept
                else:
                    pixel_array = image.ds.pixel_array
                if (pixel_array.max() > wmax):
                    wmax = pixel_array.max()
                if (pixel_array.min() < wmin):
                    wmin = pixel_array.min()
                # Default window is the range of the data array
                self.window = int(abs(wmax) + abs(wmin))
                # Default level is the range midpoint minus the window minimum
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
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_RIGHT_UP, self.OnMouseUp)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseEnter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)
        self.Bind(wx.EVT_MOTION, self.OnMouseMotion)
        pub.subscribe(self.OnKeyDown, 'main.key_down')
        pub.subscribe(self.OnMouseWheel, 'main.mousewheel')

    def OnUnfocus(self):
        """Unbind to certain events when the plugin is unfocused."""

        # Unbind keyboard and mouse events
        self.Unbind(wx.EVT_KEY_DOWN)
        self.Unbind(wx.EVT_MOUSEWHEEL)
        self.Unbind(wx.EVT_LEFT_DOWN)
        self.Unbind(wx.EVT_LEFT_UP)
        self.Unbind(wx.EVT_RIGHT_DOWN)
        self.Unbind(wx.EVT_RIGHT_UP)
        self.Unbind(wx.EVT_MOTION)
        pub.unsubscribe(self.OnKeyDown)
        pub.unsubscribe(self.OnMouseWheel)

    def OnDestroy(self, evt):
        """Unbind to all events before the plugin is destroyed."""

        pub.unsubscribe(self.OnUpdatePatient)
        pub.unsubscribe(self.OnStructureCheck)
        pub.unsubscribe(self.OnIsodoseCheck)
        pub.unsubscribe(self.OnDrawingPrefsChange)
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

    def OnDrawingPrefsChange(self, msg):
        """When the drawing preferences change, update the drawing styles."""

        if (msg.topic[2] == 'isodose_line_style'):
            self.isodose_line_style = msg.data
        elif (msg.topic[2] == 'isodose_fill_opacity'):
            self.isodose_fill_opacity = msg.data
        elif (msg.topic[2] == 'structure_line_style'):
            self.structure_line_style = msg.data
        elif (msg.topic[2] == 'structure_fill_opacity'):
            self.structure_fill_opacity = msg.data
        self.Refresh()

    def DrawStructure(self, structure, gc, position, prone, feetfirst):
        """Draw the given structure on the panel."""

        # Draw the structure only if the structure has contours
        # on the current image position
        if structure['planes'].has_key(position):
            # Set the color of the contour
            color = wx.Colour(structure['color'][0], structure['color'][1],
                structure['color'][2], int(self.structure_fill_opacity*255/100))
            # Set fill (brush) color, transparent for external contour
            if (('RTROIType' in structure) and (structure['RTROIType'].lower() == 'external')):
                gc.SetBrush(wx.Brush(color, style=wx.TRANSPARENT))
            else:
                gc.SetBrush(wx.Brush(color))
            gc.SetPen(wx.Pen(tuple(structure['color']),
                style=self.GetLineDrawingStyle(self.structure_line_style)))
            # Create the path for the contour
            path = gc.CreatePath()
            for contour in structure['planes'][position]:
                if (contour['geometricType'] == u"CLOSED_PLANAR"):
                    # Convert the structure data to pixel data
                    pixeldata = self.GetContourPixelData(
                        self.structurepixlut, contour['contourData'], prone, feetfirst)

                    # Move the origin to the last point of the contour
                    point = pixeldata[-1]
                    path.MoveToPoint(point[0], point[1])

                    # Add each contour point to the path
                    for point in pixeldata:
                        path.AddLineToPoint(point[0], point[1])
                    # Close the subpath in preparation for the next contour
                    path.CloseSubpath()
            # Draw the path
            gc.DrawPath(path)

    def DrawIsodose(self, isodose, gc, isodosegen):
        """Draw the given structure on the panel."""

        # Calculate the isodose level according to rx dose and dose grid scaling
        level = isodose['data']['level'] * self.rxdose / (self.dosedata['dosegridscaling'] * 10000)
        contours = isodosegen.trace(level)
        # matplotlib 1.0.0 and above returns vertices and segments, but we only need vertices
        if (mplversion >= "1.0.0"):
            contours = contours[:len(contours)//2]
        if len(contours):

            # Set the color of the isodose line
            color = wx.Colour(isodose['color'][0], isodose['color'][1],
                isodose['color'][2], int(self.isodose_fill_opacity*255/100))
            gc.SetBrush(wx.Brush(color))
            gc.SetPen(wx.Pen(tuple(isodose['color']),
                style=self.GetLineDrawingStyle(self.isodose_line_style)))

            # Create the drawing path for the isodose line
            path = gc.CreatePath()
            # Draw each contour for the isodose line
            for c in contours:
                # Move the origin to the last point of the contour
                path.MoveToPoint(
                    self.dosepixlut[0][int(c[-1][0])], self.dosepixlut[1][int(c[-1][1])])
                # Add a line to the rest of the points
                # Note: draw every other point since there are too many points
                for p in c[::2]:
                    path.AddLineToPoint(
                        self.dosepixlut[0][int(p[0])], self.dosepixlut[1][int(p[1])])
                # Close the subpath in preparation for the next contour
                path.CloseSubpath()
            # Draw the final isodose path
            gc.DrawPath(path)

    def GetLineDrawingStyle(self, style):
        """Convert the stored line drawing style into wxWidgets pen drawing format."""

        styledict = {'Solid':wx.SOLID,
                    'Transparent':wx.TRANSPARENT,
                    'Dot':wx.DOT,
                    'Dash':wx.SHORT_DASH,
                    'Dot Dash':wx.DOT_DASH}
        return styledict[style]

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
            self.bwidth, self.bheight = image.GetSize()

            # Center the image
            gc.Translate(self.pan[0]+(width-self.bwidth*self.zoom)/(2*self.zoom),
                         self.pan[1]+(height-self.bheight*self.zoom)/(2*self.zoom))
            gc.DrawBitmap(bmp, 0, 0, self.bwidth, self.bheight)

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
                self.DrawStructure(structure, gc, z, prone, feetfirst)

            # Draw the isodoses if present
            if len(self.isodoses):
                grid = self.dose.GetDoseGrid(float(z))
                x, y = np.meshgrid(
                    np.arange(grid.shape[1]), np.arange(grid.shape[0]))
                # Instantiate the isodose generator for this slice
                isodosegen = cntr.Cntr(x, y, grid)
                for id, isodose in iter(sorted(self.isodoses.iteritems())):
                    self.DrawIsodose(isodose, gc, isodosegen)

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
            imsize = "Image Size: " + str(self.bheight) + "x" + str(self.bheight) + " px"
            gc.DrawText(imsize, 10, height-17-te[1]*1.1)
            imwinlevel = "W/L: " + str(self.window) + ' / ' + str(self.level)
            te = gc.GetFullTextExtent(imwinlevel)
            gc.DrawText(imwinlevel, width-te[0]-7, 7)
            impatpos = "Patient Position: " + imdata['patientposition']
            te = gc.GetFullTextExtent(impatpos)
            gc.DrawText(impatpos, width-te[0]-7, height-17)

            # Update the mouse cursor position display if the display refreshes
            self.OnUpdatePositionValues(None)

    def OnSize(self, evt):
        """Refresh the view when the size of the panel changes."""

        self.Refresh()
        evt.Skip()

    def OnUpdatePositionValues(self, evt=None):
        """Update the current position and value(s) of the mouse cursor."""

        if (evt == None):
            pos = np.array(self.mousepos)
        else:
            pos = np.array(evt.GetPosition())

        # On the Mac, the cursor position is shifted by 1 pixel to the left
        if guiutil.IsMac():
            pos = pos - 1

        # Determine the coordinates with respect to the current zoom and pan
        w, h = self.GetClientSize()
        xpos = int(pos[0]/self.zoom-self.pan[0]-(w-self.bwidth*self.zoom)/
                (2*self.zoom))
        ypos = int(pos[1]/self.zoom-self.pan[1]-(h-self.bheight*self.zoom)/
                (2*self.zoom))

        # Set an empty text placeholder if the coordinates are not within range
        text = ""
        # Only display if the mouse coordinates are in the image size range
        if ((0 <= xpos < len(self.structurepixlut[0])) and
            (0 <= ypos < len(self.structurepixlut[1])) and self.mouse_in_window):
            text = "X: " + unicode('%.2f' % self.structurepixlut[0][xpos]) + \
                " mm Y: " + unicode('%.2f' % self.structurepixlut[1][ypos]) + \
                " mm / X: " + unicode(xpos) + \
                " px Y:" + unicode(ypos) + " px"
        # Send a message with the coordinate text to the 3rd statusbar section
        pub.sendMessage('main.update_statusbar', {2:text})

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

    def OnMouseDown(self, evt):
        """Get the initial position of the mouse when dragging."""

        self.mousepos = evt.GetPosition()

    def OnMouseUp(self, evt):
        """Reset the cursor when the mouse is released."""

        self.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))

    def OnMouseEnter(self, evt):
        """Set a flag when the cursor enters the window."""

        self.mouse_in_window = True
        self.OnUpdatePositionValues(None)

    def OnMouseLeave(self, evt):
        """Set a flag when the cursor leaves the window."""

        self.mouse_in_window = False
        self.OnUpdatePositionValues(None)

    def OnMouseMotion(self, evt):
        """Process mouse motion events and pass to the appropriate handler."""

        if evt.LeftIsDown():
            self.OnLeftIsDown(evt)
            self.SetCursor(wx.StockCursor(wx.CURSOR_SIZING))
        elif evt.RightIsDown():
            self.OnRightIsDown(evt)
            # Custom cursors with > 2 colors only works on Windows currently
            if guiutil.IsMSWindows():
                image = wx.Image(util.GetResourcePath('contrast_high.png'))
                self.SetCursor(wx.CursorFromImage(image))
        # Update the positon and values of the mouse cursor
        self.mousepos = evt.GetPosition()
        self.OnUpdatePositionValues(evt)

    def OnLeftIsDown(self, evt):
        """Change the image pan when the left mouse button is dragged."""

        delta = self.mousepos - evt.GetPosition()
        self.mousepos = evt.GetPosition()
        self.pan[0] -= (delta[0]/self.zoom)
        self.pan[1] -= (delta[1]/self.zoom)
        self.Refresh()

    def OnRightIsDown(self, evt):
        """Change the window/level when the right mouse button is dragged."""

        delta = self.mousepos - evt.GetPosition()
        self.mousepos = evt.GetPosition()
        self.window -= delta[0]
        self.level -= delta[1]
        self.Refresh()
