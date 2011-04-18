#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# guidvh.py
"""Class that displays the dose volume histogram via wxPython and matplotlib."""
# Copyright (c) 2009-2011 Aditya Panchal
# This file is part of dicompyler, relased under a BSD license.
#    See the file license.txt included with this distribution, also
#    available at http://code.google.com/p/dicompyler/
#
# It's assumed that the reference (prescription) dose is in cGy.

import wxmpl
import numpy as np

class guiDVH:
    """Displays and updates the dose volume histogram using WxMpl."""
    def __init__(self, parent):

        self.panelDVH = wxmpl.PlotPanel(parent, -1,
                    size=(6, 4.50), dpi=68, crosshairs=False)
        self.Replot()

    def Replot(self, dvhs=None, scaling=None, structures=None, point=None, pointid=None):
        """Redraws the plot."""

        fig = self.panelDVH.get_figure()
        fig.set_edgecolor('white')

        # clear the axes and replot everything
        axes = fig.gca()
        axes.cla()
        maxlen = 1
        if not (dvhs == None):
            for id, dvh in dvhs.iteritems():
                if structures.has_key(id):
                    # Determine the maximum DVH length for the x axis limit
                    if len(dvh) > maxlen:
                        maxlen = len(dvh)
                    # if the structure color is white, change it to black
                    colorarray = np.array(structures[id]['color'], dtype=float)
                    if np.size(np.nonzero(colorarray/255 - 1)):
                        color = colorarray/255
                    else:
                        color = np.zeros(3)
                    dose = np.arange(len(dvh))
                    if not (scaling == None):
                        dose = dose * scaling[id]
                    axes.plot(dose, dvh,
                            label=structures[id]['name'],
                            color=color,
                            linewidth=2)
                    if (point and (pointid == id)):
                        axes.plot(point[0], point[1], 'o', color=color)
                    axes.legend(fancybox=True, shadow=True)
        # set the volume
        axes.grid(True)
        axes.set_xlim(0, maxlen)
        axes.set_ylim(0, 100)
        axes.set_xlabel('Dose (cGy)')
        axes.set_ylabel('Volume (%)')
        axes.set_title('DVH')

        # redraw the display
        self.panelDVH.draw()
