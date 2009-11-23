#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

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
