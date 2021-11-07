#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 2dview.py
"""dicompyler plugin that displays images, structures and dose in 2D planes."""
# Copyright (c) 2009-2017 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/bastula/dicompyler/
#

import wx
from wx.xrc import XmlResource, XRCCTRL, XRCID
from pubsub import pub
from matplotlib import _cntr as cntr
from matplotlib import __version__ as mplversion
import numpy as np
from dicompyler import guiutil, util

def pluginProperties():
    """Properties of the plugin."""

    props = {}
    props['name'] = '2D View'
    props['description'] = "Display image, structure and dose data in 2D"
    props['author'] = 'Aditya Panchal'
    props['version'] = "0.5.0"
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
        wx.Panel.__init__(self)

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
        self.xpos = 0
        self.ypos = 0
        self.mousepos = wx.Point(-10000, -10000)
        self.mouse_in_window = False
        self.isodose_line_style = 'Solid'
        self.isodose_fill_opacity = 25
        self.structure_line_style = 'Solid'
        self.structure_fill_opacity = 50
        self.plugins = {}

        # Setup toolbar controls
        if guiutil.IsGtk():
            drawingstyles = ['Solid', 'Transparent', 'Dot']
        else:
            drawingstyles = ['Solid', 'Transparent', 'Dot', 'Dash', 'Dot Dash']
        zoominbmp = wx.Bitmap(util.GetResourcePath('magnifier_zoom_in.png'))
        zoomoutbmp = wx.Bitmap(util.GetResourcePath('magnifier_zoom_out.png'))
        toolsbmp = wx.Bitmap(util.GetResourcePath('cog.png'))
        self.tools = []
        self.tools.append({'label':"Zoom In", 'bmp':zoominbmp, 'shortHelp':"Zoom In", 'eventhandler':self.OnZoomIn})
        self.tools.append({'label':"Zoom Out", 'bmp':zoomoutbmp, 'shortHelp':"Zoom Out", 'eventhandler':self.OnZoomOut})
        self.tools.append({'label':"Tools", 'bmp':toolsbmp, 'shortHelp':"Tools", 'eventhandler':self.OnToolsMenu})

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
        pub.subscribe(self.OnRefresh, '2dview.refresh')
        pub.subscribe(self.OnDrawingPrefsChange, '2dview.drawingprefs')
        pub.subscribe(self.OnPluginLoaded, 'plugin.loaded.2dview')
        pub.sendMessage('preferences.requested.values', msg='2dview.drawingprefs')

    def OnUpdatePatient(self, msg):
        """Update and load the patient data."""

        self.z = 0
        self.structurepixlut = ([], [])
        self.dosepixlut = ([], [])
        if 'images' in msg:
            self.images = msg['images']
            self.imagenum = 1
            # If more than one image, set first image to middle of the series
            if (len(self.images) > 1):
                self.imagenum = int(len(self.images)/2)
            image = self.images[self.imagenum-1]
            self.structurepixlut = image.GetPatientToPixelLUT()
            # Determine the default window and level of the series
            self.window, self.level = image.GetDefaultImageWindowLevel()
            # Dose display depends on whether we have images loaded or not
            self.isodoses = {}
            if ('dose' in msg and \
                ("PixelData" in msg['dose'].ds)):
                self.dose = msg['dose']
                self.dosedata = self.dose.GetDoseData()
                # First get the dose grid LUT
                doselut = self.dose.GetPatientToPixelLUT()
                # Then convert dose grid LUT into an image pixel LUT
                self.dosepixlut = self.GetDoseGridPixelData(self.structurepixlut, doselut)
            else:
                self.dose = []
            if 'plan' in msg:
                self.rxdose = msg['plan']['rxdose']
            else:
                self.rxdose = 0
        else:
            self.images = []

        self.SetBackgroundColour(wx.Colour(0, 0, 0))
        # Set the focus to this panel so we can capture key events
        self.SetFocus()
        self.OnFocus() #Workaround on Windows. ST
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
        if guiutil.IsMSWindows():
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
        if guiutil.IsMSWindows():
            pub.unsubscribe(self.OnKeyDown, 'main.key_down')
            pub.unsubscribe(self.OnMouseWheel, 'main.mousewheel')
        pub.unsubscribe(self.OnRefresh, '2dview.refresh')

    def OnDestroy(self, evt):
        """Unbind to all events before the plugin is destroyed."""

        pub.unsubscribe(self.OnUpdatePatient, 'patient.updated.parsed_data')
        pub.unsubscribe(self.OnStructureCheck, 'structures.checked')
        pub.unsubscribe(self.OnIsodoseCheck, 'isodoses.checked')
        pub.unsubscribe(self.OnDrawingPrefsChange, '2dview.drawingprefs')
        pub.unsubscribe(self.OnPluginLoaded, 'plugin.loaded.2dview')
        # self.OnUnfocus()

    def OnStructureCheck(self, msg):
        """When the structure list changes, update the panel."""

        self.structures = msg
        self.SetFocus()
        self.Refresh()

    def OnIsodoseCheck(self, msg):
        """When the isodose list changes, update the panel."""

        self.isodoses = msg
        self.SetFocus()
        self.Refresh()

    def OnDrawingPrefsChange(self, topic, msg):
        """When the drawing preferences change, update the drawing styles."""
        topic = topic.split('.')
        if (topic[1] == 'isodose_line_style'):
            self.isodose_line_style = msg
        elif (topic[1] == 'isodose_fill_opacity'):
            self.isodose_fill_opacity = msg
        elif (topic[1] == 'structure_line_style'):
            self.structure_line_style = msg
        elif (topic[1] == 'structure_fill_opacity'):
            self.structure_fill_opacity = msg
        self.Refresh()

    def OnPluginLoaded(self, msg):
        """When a 2D View-dependent plugin is loaded, initialize the plugin."""

        name = msg.pluginProperties()['name']
        self.plugins[name] = msg.plugin(self)

    def DrawStructure(self, structure, gc, position, prone, feetfirst):
        """Draw the given structure on the panel."""

        # Create an indexing array of z positions of the structure data
        # to compare with the image z position
        if not "zarray" in structure:
            structure['zarray'] = np.array(
                    list(structure['planes'].keys()), dtype=np.float32)
            structure['zkeys'] = structure['planes'].keys()

        # Return if there are no z positions in the structure data
        if not len(structure['zarray']):
            return

        # Determine the closest z plane to the given position
        zmin = np.amin(np.abs(structure['zarray'] - float(position)))
        index = np.argmin(np.abs(structure['zarray'] - float(position)))

        # Draw the structure only if the structure has contours
        # on the closest plane, within a threshold
        if (zmin < 0.5):
            # Set the color of the contour
            color = wx.Colour(structure['color'][0], structure['color'][1],
                structure['color'][2], int(self.structure_fill_opacity*255/100))
            # Set fill (brush) color, transparent for external contour
            if (('type' in structure) and (structure['type'].lower() == 'external')):
                gc.SetBrush(wx.Brush(color, style=wx.TRANSPARENT))
            else:
                gc.SetBrush(wx.Brush(color))
            gc.SetPen(wx.Pen(tuple(structure['color']),
                style=self.GetLineDrawingStyle(self.structure_line_style)))
            # Create the path for the contour
            path = gc.CreatePath()
            for contour in structure['planes'][list(structure['zkeys'])[index]]:
                if (contour['type'] == u"CLOSED_PLANAR"):
                    # Convert the structure data to pixel data
                    pixeldata = self.GetContourPixelData(
                        self.structurepixlut, contour['data'], prone, feetfirst)

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
                    self.dosepixlut[0][int(c[-1][0])]+1, self.dosepixlut[1][int(c[-1][1])]+1)
                # Add a line to the rest of the points
                # Note: draw every other point since there are too many points
                for p in c[::2]:
                    path.AddLineToPoint(
                        self.dosepixlut[0][int(p[0])]+1, self.dosepixlut[1][int(p[1])]+1)
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
                if (xval > point[0] and not prone and not feetfirst) or (xval < point[0]) and feetfirst or prone:
                    break
            for yv, yval in enumerate(pixlut[1]):
                if (yval > point[1] and not prone) or (yval < point[1] and prone):
                    break
            pixeldata.append((xv, yv))

        return pixeldata

    def GetDoseGridPixelData(self, pixlut, doselut):
        """Convert dosegrid data into pixel data using the dose to pixel LUT."""

        dosedata = []
        x = []
        y = []
        # Determine if the patient is prone or supine
        imdata = self.images[self.imagenum-1].GetImageData()
        prone = -1 if 'p' in imdata['patientposition'].lower() else 1
        feetfirst = -1 if 'ff' in imdata['patientposition'].lower() else 1
        # Get the pixel spacing
        spacing = imdata['pixelspacing']

        # Transpose the dose grid LUT onto the image grid LUT
        x = (np.array(doselut[0]) - pixlut[0][0]) * prone * feetfirst / spacing[0]
        y = (np.array(doselut[1]) - pixlut[1][0]) * prone / spacing[1]
        return (x, y)

    def OnPaint(self, evt):
        """Update the panel when it needs to be refreshed."""

        # Bind motion event when the panel has been painted to avoid a blank
        # image on Windows if a file is loaded too quickly before the plugin
        # is initialized
        self.Bind(wx.EVT_MOTION, self.OnMouseMotion)

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
            bmp = wx.Bitmap(image)
            self.bwidth, self.bheight = image.GetSize()

            # Center the image
            transx = self.pan[0]+(width-self.bwidth*self.zoom)/(2*self.zoom)
            transy = self.pan[1]+(height-self.bheight*self.zoom)/(2*self.zoom)
            gc.Translate(transx, transy)
            gc.DrawBitmap(bmp, 0, 0, self.bwidth, self.bheight)
            gc.SetBrush(wx.Brush(wx.Colour(0, 0, 255, 30)))
            gc.SetPen(wx.Pen(wx.Colour(0, 0, 255, 30)))

            # Draw the structures if present
            imdata = self.images[self.imagenum-1].GetImageData()
            self.z = '%.2f' % imdata['position'][2]

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
            for id, structure in self.structures.items():
                self.DrawStructure(structure, gc, self.z, prone, feetfirst)

            # Draw the isodoses if present
            if len(self.isodoses):
                grid = self.dose.GetDoseGrid(float(self.z))
                if not (grid == []):
                    x, y = np.meshgrid(
                        np.arange(grid.shape[1]), np.arange(grid.shape[0]))
                    # Instantiate the isodose generator for this slice
                    isodosegen = cntr.Cntr(x, y, grid)
                    for id, isodose in iter(sorted(self.isodoses.items())):
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
            impos = "Position: " + str(self.z) + " mm"
            gc.DrawText(impos, 10, 7+te[1]*1.1)
            if ("%.3f" % self.zoom == "1.000"):
                zoom = "1"
            else:
                zoom = "%.3f" % self.zoom
            imzoom = "Zoom: " + zoom + ":1"
            gc.DrawText(imzoom, 10, height-17)
            imsize = "Image Size: " + str(self.bheight) + "x" + str(self.bwidth) + " px"
            gc.DrawText(imsize, 10, height-17-te[1]*1.1)
            imwinlevel = "W/L: " + str(self.window) + ' / ' + str(self.level)
            te = gc.GetFullTextExtent(imwinlevel)
            gc.DrawText(imwinlevel, width-te[0]-7, 7)
            impatpos = "Patient Position: " + imdata['patientposition']
            te = gc.GetFullTextExtent(impatpos)
            gc.DrawText(impatpos, width-te[0]-7, height-17)

            # Send message with the current image number and various properties
            pub.sendMessage('2dview.updated.image',
                            msg={'number':self.imagenum,    # slice number
                             'z':self.z,                # slice location
                             'window':self.window,      # current window value
                             'level':self.level,        # curent level value
                             'gc':gc,                   # wx.GraphicsContext
                             'scale':self.zoom,         # current zoom level
                             'transx':transx,           # current x translation
                             'transy':transy,           # current y translation
                             'imdata':imdata,           # image data dictionary
                             'patientpixlut':self.structurepixlut})
                                                        # pat to pixel coord LUT

    def OnSize(self, evt):
        """Refresh the view when the size of the panel changes."""

        self.Refresh()
        evt.Skip()

    def OnRefresh(self, msg):
        """Refresh the view when it is requested by a plugin."""

        self.Refresh()

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

        # Save the coordinates so they can be used by the 2dview plugins
        self.xpos = xpos
        self.ypos = ypos

        # Set an empty text placeholder if the coordinates are not within range
        text = ""
        value = ""
        # Skip processing if images are not loaded
        if not len(self.images):
            pub.sendMessage('main.update_statusbar', msg={1:text, 2:value})
        # Only display if the mouse coordinates are within the image size range
        if ((0 <= xpos < len(self.structurepixlut[0])) and
            (0 <= ypos < len(self.structurepixlut[1])) and self.mouse_in_window):
            text = "X: " + str('%.2f' % self.structurepixlut[0][xpos]) + \
                " mm Y: " + str('%.2f' % self.structurepixlut[1][ypos]) + \
                " mm / X: " + str(xpos) + \
                " px Y:" + str(ypos) + " px"

            # Lookup the current image and find the value of the current pixel
            image = self.images[self.imagenum-1]
            # Rescale the slope and intercept of the image if present
            if ('RescaleIntercept' in image.ds and
                'RescaleSlope' in image.ds):
                pixel_array = image.ds.pixel_array*image.ds.RescaleSlope + \
                              image.ds.RescaleIntercept
            else:
                pixel_array = image.ds.pixel_array
            value = "Value: " + str(pixel_array[ypos, xpos])

            # Lookup the current dose plane and find the value of the current
            # pixel, if the dose has been loaded
            if not (self.dose == []):
                xdpos = np.argmin(np.fabs(np.array(self.dosepixlut[0]) - xpos))
                ydpos = np.argmin(np.fabs(np.array(self.dosepixlut[1]) - ypos))
                dosegrid = self.dose.GetDoseGrid(float(self.z))
                if not (dosegrid == []):
                    dose = dosegrid[ydpos, xdpos] * \
                           self.dosedata['dosegridscaling']
                    value = value + " / Dose: " + \
                            str('%.4g' % dose) + " Gy / " + \
                            str('%.4g' % float(dose*10000/self.rxdose)) + " %"
        # Send a message with the text to the 2nd and 3rd statusbar sections
        pub.sendMessage('main.update_statusbar', msg={1:text, 2:value})

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

        if len(self.images):
            keyname = evt.GetKeyCode()
            prevkey = [wx.WXK_UP, wx.WXK_PAGEUP]
            nextkey = [wx.WXK_DOWN, wx.WXK_PAGEDOWN]
            zoominkey = [43, 61, 388] # Keys: +, =, Numpad add
            zoomoutkey = [45, 95, 390] # Keys: -, _, Numpad subtract
            if (keyname in prevkey) and (self.imagenum > 1):
                self.imagenum -= 1
                self.Refresh()
            if (keyname in nextkey) and (self.imagenum < len(self.images)):
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

        if len(self.images):
            delta = evt.GetWheelDelta()
            rot = evt.GetWheelRotation()
            rot = rot/delta
            if (rot >= 1):
                if (self.imagenum > 1):
                    self.imagenum -= 1
                    self.Refresh()
            if (rot <= -1) and (self.imagenum < len(self.images)):
                self.imagenum += 1
                self.Refresh()

    def OnMouseDown(self, evt):
        """Get the initial position of the mouse when dragging."""

        self.mousepos = evt.GetPosition()
        # Publish the coordinates of the cursor position based
        # on the scaled image size range
        if ((0 <= self.xpos < len(self.structurepixlut[0])) and
            (0 <= self.ypos < len(self.structurepixlut[1])) and
            (self.mouse_in_window) and
            (evt.LeftDown())):
            pub.sendMessage('2dview.mousedown',
                        msg={'x':self.xpos,
                         'y':self.ypos,
                         'xmm':self.structurepixlut[0][self.xpos],
                         'ymm':self.structurepixlut[1][self.ypos]})

    def OnMouseUp(self, evt):
        """Reset the cursor when the mouse is released."""

        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))

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
            self.SetCursor(wx.Cursor(wx.CURSOR_SIZING))
        elif evt.RightIsDown():
            self.OnRightIsDown(evt)
            # Custom cursors with > 2 colors only works on Windows currently
            if guiutil.IsMSWindows():
                image = wx.Image(util.GetResourcePath('contrast_high.png'))
                self.SetCursor(wx.Cursor(image))
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

    def OnToolsMenu(self, evt):
        """Show a context menu for the loaded 2D View plugins when the
            'Tools' toolbar item is selected."""

        menu = wx.Menu()
        if len(self.plugins):
            for name, p in self.plugins.items():
                identifier = wx.NewId()
                self.Bind(wx.EVT_MENU, p.pluginMenu, id=identifier)
                menu.Append(identifier, name)
        else:
            identifier = wx.NewId()
            menu.Append(identifier, "No tools found")
            menu.Enable(identifier, False)
        self.PopupMenu(menu)
        menu.Destroy()