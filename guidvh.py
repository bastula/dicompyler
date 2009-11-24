#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# guidvh.py
"""Class that displays the dose volume histogram via wxPython and matplotlib."""
# Copyright (c) 2009 Aditya Panchal
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

    def Replot(self, dvhs = None, structures = None, point = None):
        """Redraws the plot."""

        fig = self.panelDVH.get_figure()
        fig.set_edgecolor('white')

        # clear the axes and replot everything
        axes = fig.gca()
        axes.cla()
        if not (dvhs == None):
            for id, dvh in dvhs.iteritems():
                axes.set_xlim(0, len(dvh))
                # if the structure color is white, change it to black
                if np.size(np.nonzero(structures[id]['color']/255 - 1)):
                    color = structures[id]['color']/255
                else:
                    color = np.zeros(3)
                axes.plot(dvh,
                        label=structures[id]['name'],
                        color=color,
                        linewidth=2)
                if point:
                    axes.plot(point[0], point[1], 'o', color=color)
                else:
                    print point
            axes.legend()
        # set the volume
        axes.grid(True)
        axes.set_ylim(0, 100)
        axes.set_xlabel('Dose (cGy)')
        axes.set_ylabel('Volume (%)')
        axes.set_title('DVH')

        # redraw the display
        self.panelDVH.draw()
