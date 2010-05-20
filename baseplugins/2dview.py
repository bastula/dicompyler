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
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

        # Initialize variables
        self.images = []

        # Set up pubsub
        pub.subscribe(self.OnUpdatePatient, 'patient.updated.parsed_data')

    def OnUpdatePatient(self, msg):
        """Update and load the patient data."""

        self.images = msg.data['images']
        self.SetBackgroundColour(wx.Colour(0, 0, 0))
        # Set the first image to the middle of the series
        self.imagenum = len(self.images)/2
        # Set the focus to this panel so we can capture key events
        self.SetFocus()

    def OnPaint(self, evt):
        """Update the panel when it needs to be refreshed."""

        dc = wx.PaintDC(self)
        width, height = dc.GetSize()
        try:
            gc = wx.GraphicsContext.Create(dc)
        except NotImplementedError:
            dc.DrawText("This build of wxPython does not support the "
                        "wx.GraphicsContext family of classes.",
                        25, 25)
            return

        # If we have images loaded, process and show the image
        if len(self.images):
            image = guiutil.convert_pil_to_wx(
                self.images[self.imagenum-1].GetImage())
            bmp = wx.BitmapFromImage(image)
            bwidth, bheight = bmp.GetSize()
            # Center the image
            gc.Translate((width-bwidth)/2, (height-bheight)/2)
            gc.DrawBitmap(bmp,
                0, 0, bwidth, bheight)

            # Prepare the font for drawing the information text
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
            if guiutil.IsMac():
                font.SetPointSize(10)
            gc.SetFont(font, wx.WHITE)

            # Draw the information text
            imtext = "Image: " + str(self.imagenum) + "/" + str(len(self.images))
            gc.DrawText(imtext, 10+(bwidth-width)/2, -10)

            imdata = self.images[self.imagenum-1].GetImageData()
            z = '%.2f' % imdata['position'][2]
            impos = "Position: " + str(z) + " mm"
            gc.DrawText(impos, 10+(bwidth-width)/2, bheight)


    def OnKeyDown(self, evt):
        """Change the image when the user presses the appropriate keys."""

        keyname = evt.GetKeyCode()
        prevkey = [wx.WXK_UP, wx.WXK_PAGEUP]
        nextkey = [wx.WXK_DOWN, wx.WXK_PAGEDOWN]
        if (keyname in prevkey):
            if (self.imagenum > 1):
                self.imagenum -= 1
        if (keyname in nextkey):
            if (self.imagenum < len(self.images)):
                self.imagenum += 1
        if (keyname == wx.WXK_HOME):
            self.imagenum = 1
        if (keyname == wx.WXK_END):
            self.imagenum = len(self.images)
        self.Refresh()