#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# guidvh.py
"""Class that displays the dose volume histogram via wxPython and matplotlib."""
# Copyright (c) 2009-2012 Aditya Panchal
# This file is part of dicompyler, released under a BSD license.
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
                    size=(6, 4.50), dpi=68, crosshairs=False,
                    autoscaleUnzoom=False)
        self.Replot()

    def Replot(self, dvhlist=None, scalinglist=None, structures=None,
               point=None, pointid=None, prefixes=None):
        """Redraws the plot."""

        fig = self.panelDVH.get_figure()
        fig.set_edgecolor('white')

        # clear the axes and replot everything
        axes = fig.gca()
        axes.cla()
        maxlen = 1
        if not (dvhlist == None):
            # Enumerate each set of DVHs
            for d, dvhs in enumerate(dvhlist):
                # Plot the DVH from each set
                for id, dvh in dvhs.iteritems():
                    if id in structures:
                        # Convert the color array to MPL formatted color
                        colorarray = np.array(structures[id]['color'],
                                              dtype=float)
                        # Plot white as black so it is visible on the plot
                        if np.size(np.nonzero(colorarray/255 - 1)):
                            color = colorarray/255
                        else:
                            color = np.zeros(3)
                        prefix = prefixes[d] if not (prefixes == None) else None
                        linestyle = '-' if not (d % 2) else '--'
                        maxlen = self.DrawDVH(dvh, structures[id], axes, color,
                                              maxlen, scalinglist[d],
                                              prefix, linestyle)
                        if (point and (pointid == id)):
                            self.DrawPoint(point, axes, color)
                        axes.legend(fancybox=True, shadow=True)
        # set the axes parameters
        axes.grid(True)
        axes.set_xlim(0, maxlen)
        axes.set_ylim(0, 100)
        axes.set_xlabel('Dose (cGy)')
        axes.set_ylabel('Volume (%)')
        axes.set_title('DVH')

        # redraw the display
        self.panelDVH.draw()

    def DrawDVH(self, dvh, structure, axes, color, maxlen,
                scaling=None, prefix=None, linestyle='-'):
        """Draw the given structure on the plot."""

        # Determine the maximum DVH length for the x axis limit
        if len(dvh) > maxlen:
            maxlen = len(dvh)
        # if the structure color is white, change it to black

        dose = np.arange(len(dvh))
        if not (scaling == None):
            dose = dose * scaling[structure['id']]
        name = prefix + ' ' + structure['name'] if prefix else structure['name']
        axes.plot(dose, dvh,
                label=name,
                color=color,
                linewidth=2,
                linestyle=linestyle)

        return maxlen

    def DrawPoint(self, point, axes, color):
        """Draw the point for the given structure on the plot."""

        axes.plot(point[0], point[1], 'o', color=color)
