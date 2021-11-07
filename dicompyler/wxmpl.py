# Purpose: painless matplotlib embedding for wxPython
# Author: Ken McIvor <mcivor@iit.edu>
# Portions modified by Aditya Panchal
#
# Copyright 2005-2009 Illinois Institute of Technology
#
# See the file "license.txt" for information on usage and redistribution
# of this file, and for a DISCLAIMER OF ALL WARRANTIES.

"""
Embedding matplotlib in wxPython applications is straightforward, but the
default plotting widget lacks the capabilities necessary for interactive use.
WxMpl (wxPython+matplotlib) is a library of components that provide these
missing features in the form of a better matplolib FigureCanvas.
"""


from matplotlib.transforms import Bbox
from matplotlib.font_manager import FontProperties
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.axes._base import _process_plot_var_args
import numpy as np
import wx
import os.path
import weakref

import matplotlib
matplotlib.use('WXAgg')

__version__ = '1.3.1'

__all__ = ['PlotPanel', 'PlotFrame', 'PlotApp', 'StripCharter', 'Channel',
           'FigurePrinter', 'PointEvent', 'EVT_POINT', 'SelectionEvent',
           'EVT_SELECTION']

# If you are using wxGtk without libgnomeprint and want to use something other
# than `lpr' to print you will have to specify that command here.
POSTSCRIPT_PRINTING_COMMAND = 'lpr'

# Between 0.98.1 and 0.98.3rc there were some significant API changes:
#   * FigureCanvasWx.draw(repaint=True) became draw(drawDC=None)
#   * The following events were added:
#       - figure_enter_event
#       - figure_leave_event
#       - axes_enter_event
#       - axes_leave_event
MATPLOTLIB_0_98_3 = '0.98.3' <= matplotlib.__version__


#
# Utility functions and classes
#

def invert_point(x, y, transform):
    """
    Returns a coordinate inverted by the specificed C{Transform}.
    """
    return transform.inverted().transform_point((x, y))


def find_axes(canvas, x, y):
    """
    Finds the C{Axes} within a matplotlib C{FigureCanvas} contains the canvas
    coordinates C{(x, y)} and returns that axes and the corresponding data
    coordinates C{xdata, ydata} as a 3-tuple.

    If no axes contains the specified point a 3-tuple of C{None} is returned.
    """
    evt = matplotlib.backend_bases.MouseEvent('', canvas, x, y)

    axes = None
    for a in canvas.get_figure().get_axes():
        if a.in_axes(evt):
            if axes is None:
                axes = a
            else:
                return None, None, None

    if axes is None:
        return None, None, None

    xdata, ydata = invert_point(x, y, axes.transData)
    return axes, xdata, ydata


def get_bbox_lims(bbox):
    """
    Returns the boundaries of the X and Y intervals of a C{Bbox}.
    """
    p0 = bbox.min
    p1 = bbox.max
    return (p0[0], p1[0]), (p0[1], p1[1])


def find_selected_axes(canvas, x1, y1, x2, y2):
    """
    Finds the C{Axes} within a matplotlib C{FigureCanvas} that overlaps with a
    canvas area from C{(x1, y1)} to C{(x1, y1)}.  That axes and the
    corresponding X and Y axes ranges are returned as a 3-tuple.

    If no axes overlaps with the specified area, or more than one axes
    overlaps, a 3-tuple of C{None}s is returned.
    """
    axes = None
    bbox = Bbox.from_extents(x1, y1, x2, y2)

    for a in canvas.get_figure().get_axes():
        if bbox.overlaps(a.bbox):
            if axes is None:
                axes = a
            else:
                return None, None, None

    if axes is None:
        return None, None, None

    x1, y1, x2, y2 = limit_selection(bbox, axes)
    xrange, yrange = get_bbox_lims(
        Bbox.from_extents(x1, y1, x2, y2).inverse_transformed(axes.transData))
    return axes, xrange, yrange


def limit_selection(bbox, axes):
    """
    Finds the region of a selection C{bbox} which overlaps with the supplied
    C{axes} and returns it as the 4-tuple C{(xmin, ymin, xmax, ymax)}.
    """
    bxr, byr = get_bbox_lims(bbox)
    axr, ayr = get_bbox_lims(axes.bbox)

    xmin = max(bxr[0], axr[0])
    xmax = min(bxr[1], axr[1])
    ymin = max(byr[0], ayr[0])
    ymax = min(byr[1], ayr[1])
    return xmin, ymin, xmax, ymax


def format_coord(axes, xdata, ydata):
    """
    A C{None}-safe version of {Axes.format_coord()}.
    """
    if xdata is None or ydata is None:
        return ''
    return axes.format_coord(xdata, ydata)


def toplevel_parent_of_window(window):
    """
    Returns the first top-level parent of a wx.Window
    """
    topwin = window
    while not isinstance(topwin, wx.TopLevelWindow):
        topwin = topwin.GetParent()
    return topwin


class AxesLimits:
    """
    Alters the X and Y limits of C{Axes} objects while maintaining a history of
    the changes.
    """

    def __init__(self, autoscaleUnzoom):
        self.autoscaleUnzoom = autoscaleUnzoom
        self.history = weakref.WeakKeyDictionary()

    def setAutoscaleUnzoom(self, state):
        """
        Enable or disable autoscaling the axes as a result of zooming all the
        way back out.
        """
        self.limits.setAutoscaleUnzoom(state)

    def _get_history(self, axes):
        """
        Returns the history list of X and Y limits associated with C{axes}.
        """
        return self.history.setdefault(axes, [])

    def zoomed(self, axes):
        """
        Returns a boolean indicating whether C{axes} has had its limits
        altered.
        """
        return not (not self._get_history(axes))

    def set(self, axes, xrange, yrange):
        """
        Changes the X and Y limits of C{axes} to C{xrange} and {yrange}
        respectively.  A boolean indicating whether or not the
        axes should be redraw is returned, because polar axes cannot have
        their limits changed sensibly.
        """
        if not axes.can_zoom():
            return False

        # The axes limits must be converted to tuples because MPL 0.98.1
        # returns the underlying array objects
        oldRange = tuple(axes.get_xlim()), tuple(axes.get_ylim())

        history = self._get_history(axes)
        history.append(oldRange)
        axes.set_xlim(xrange)
        axes.set_ylim(yrange)
        return True

    def restore(self, axes):
        """
        Changes the X and Y limits of C{axes} to their previous values.  A
        boolean indicating whether or not the axes should be redraw is
        returned.
        """
        history = self._get_history(axes)
        if not history:
            return False

        xrange, yrange = history.pop()
        if self.autoscaleUnzoom and not len(history):
            axes.autoscale_view()
        else:
            axes.set_xlim(xrange)
            axes.set_ylim(yrange)
        return True


#
# Director of the matplotlib canvas
#

class PlotPanelDirector:
    """
    Encapsulates all of the user-interaction logic required by the
    C{PlotPanel}, following the Humble Dialog Box pattern proposed by Michael
    Feathers:
    U{http://www.objectmentor.com/resources/articles/TheHumbleDialogBox.pdf}
    """

    # TODO: add a programmatic interface to zooming and user interactions
    # TODO: full support for MPL events

    def __init__(self, view, zoom=True, selection=True, rightClickUnzoom=True,
                 autoscaleUnzoom=True):
        """
        Create a new director for the C{PlotPanel} C{view}.  The keyword
        arguments C{zoom} and C{selection} have the same meanings as for
        C{PlotPanel}.
        """
        self.view = view
        self.zoomEnabled = zoom
        self.selectionEnabled = selection
        self.rightClickUnzoom = rightClickUnzoom
        self.limits = AxesLimits(autoscaleUnzoom)
        self.leftButtonPoint = None

    def setSelection(self, state):
        """
        Enable or disable left-click area selection.
        """
        self.selectionEnabled = state

    def setZoomEnabled(self, state):
        """
        Enable or disable zooming as a result of left-click area selection.
        """
        self.zoomEnabled = state

    def setAutoscaleUnzoom(self, state):
        """
        Enable or disable autoscaling the axes as a result of zooming all the
        way back out.
        """
        self.limits.setAutoscaleUnzoom(state)

    def setRightClickUnzoom(self, state):
        """
        Enable or disable unzooming as a result of right-clicking.
        """
        self.rightClickUnzoom = state

    def canDraw(self):
        """
        Indicates if plot may be not redrawn due to the presence of a selection
        box.
        """
        return self.leftButtonPoint is None

    def zoomed(self, axes):
        """
        Returns a boolean indicating whether or not the plot has been zoomed in
        as a result of a left-click area selection.
        """
        return self.limits.zoomed(axes)

    def keyDown(self, evt):
        """
        Handles wxPython key-press events.  These events are currently skipped.
        """
        evt.Skip()

    def keyUp(self, evt):
        """
        Handles wxPython key-release events.  These events are currently
        skipped.
        """
        evt.Skip()

    def leftButtonDown(self, evt, x, y):
        """
        Handles wxPython left-click events.
        """
        self.leftButtonPoint = (x, y)

        view = self.view
        axes, xdata, ydata = find_axes(view, x, y)

        if axes is not None and self.selectionEnabled and axes.can_zoom():
            view.cursor.setCross()
            view.crosshairs.clear()

    def leftButtonUp(self, evt, x, y):
        """
        Handles wxPython left-click-release events.
        """
        if self.leftButtonPoint is None:
            return

        view = self.view
        axes, xdata, ydata = find_axes(view, x, y)

        x0, y0 = self.leftButtonPoint
        self.leftButtonPoint = None
        view.rubberband.clear()

        if x0 == x:
            if y0 == y and axes is not None:
                view.notify_point(axes, x, y)
                view.crosshairs.set(x, y)
            return
        elif y0 == y:
            return

        xdata = ydata = None
        axes, xrange, yrange = find_selected_axes(view, x0, y0, x, y)

        if axes is not None:
            xdata, ydata = invert_point(x, y, axes.transData)
            if self.zoomEnabled:
                if self.limits.set(axes, xrange, yrange):
                    self.view.draw()
            else:
                bbox = Bbox.from_extents(x0, y0, x, y)
                x1, y1, x2, y2 = limit_selection(bbox, axes)
                self.view.notify_selection(axes, x1, y1, x2, y2)

        if axes is None:
            view.cursor.setNormal()
        elif not axes.can_zoom():
            view.cursor.setNormal()
            view.location.set(format_coord(axes, xdata, ydata))
        else:
            view.crosshairs.set(x, y)
            view.location.set(format_coord(axes, xdata, ydata))

    def rightButtonDown(self, evt, x, y):
        """
        Handles wxPython right-click events.  These events are currently
        skipped.
        """
        evt.Skip()

    def rightButtonUp(self, evt, x, y):
        """
        Handles wxPython right-click-release events.
        """
        view = self.view
        axes, xdata, ydata = find_axes(view, x, y)
        if (axes is not None and self.zoomEnabled and self.rightClickUnzoom
                and self.limits.restore(axes)):
            view.crosshairs.clear()
            view.draw()
            view.crosshairs.set(x, y)

    def mouseMotion(self, evt, x, y):
        """
        Handles wxPython mouse motion events, dispatching them based on whether
        or not a selection is in process and what the cursor is over.
        """
        view = self.view
        axes, xdata, ydata = find_axes(view, x, y)

        if self.leftButtonPoint is not None:
            self.selectionMouseMotion(evt, x, y, axes, xdata, ydata)
        else:
            if axes is None:
                self.canvasMouseMotion(evt, x, y)
            elif not axes.can_zoom():
                self.unzoomableAxesMouseMotion(evt, x, y, axes, xdata, ydata)
            else:
                self.axesMouseMotion(evt, x, y, axes, xdata, ydata)

    def selectionMouseMotion(self, evt, x, y, axes, xdata, ydata):
        """
        Handles wxPython mouse motion events that occur during a left-click
        area selection.
        """
        view = self.view
        x0, y0 = self.leftButtonPoint
        view.rubberband.set(x0, y0, x, y)
        if axes is None:
            view.location.clear()
        else:
            view.location.set(format_coord(axes, xdata, ydata))

    def canvasMouseMotion(self, evt, x, y):
        """
        Handles wxPython mouse motion events that occur over the canvas.
        """
        view = self.view
        view.cursor.setNormal()
        view.crosshairs.clear()
        view.location.clear()

    def axesMouseMotion(self, evt, x, y, axes, xdata, ydata):
        """
        Handles wxPython mouse motion events that occur over an axes.
        """
        view = self.view
        view.cursor.setCross()
        view.crosshairs.set(x, y)
        view.location.set(format_coord(axes, xdata, ydata))

    def unzoomableAxesMouseMotion(self, evt, x, y, axes, xdata, ydata):
        """
        Handles wxPython mouse motion events that occur over an axes that does
        not support zooming.
        """
        view = self.view
        view.cursor.setNormal()
        view.location.set(format_coord(axes, xdata, ydata))


#
# Components used by the PlotPanel
#

class Painter:
    """
    Painters encapsulate the mechanics of drawing some value in a wxPython
    window and erasing it.  Subclasses override template methods to process
    values and draw them.

    @cvar PEN: C{wx.Pen} to use (defaults to C{wx.BLACK_PEN})
    @cvar BRUSH: C{wx.Brush} to use (defaults to C{wx.TRANSPARENT_BRUSH})
    @cvar FUNCTION: Logical function to use (defaults to C{wx.COPY})
    @cvar FONT: C{wx.Font} to use (defaults to C{wx.NORMAL_FONT})
    @cvar TEXT_FOREGROUND: C{wx.Colour} to use (defaults to C{wx.BLACK})
    @cvar TEXT_BACKGROUND: C{wx.Colour} to use (defaults to C{wx.WHITE})
    """

    PEN = wx.BLACK_PEN
    BRUSH = wx.TRANSPARENT_BRUSH
    FUNCTION = wx.COPY
    FONT = wx.NORMAL_FONT
    TEXT_FOREGROUND = wx.BLACK
    TEXT_BACKGROUND = wx.WHITE

    def __init__(self, view, enabled=True):
        """
        Create a new painter attached to the wxPython window C{view}.  The
        keyword argument C{enabled} has the same meaning as the argument to the
        C{setEnabled()} method.
        """
        self.view = view
        self.lastValue = None
        self.enabled = enabled

    def setEnabled(self, state):
        """
        Enable or disable this painter.  Disabled painters do not draw their
        values and calls to C{set()} have no effect on them.
        """
        oldState, self.enabled = self.enabled, state
        if oldState and not self.enabled:
            self.clear()

    def set(self, *value):
        """
        Update this painter's value and then draw it.  Values may not be
        C{None}, which is used internally to represent the absence of a current
        value.
        """
        if self.enabled:
            value = self.formatValue(value)
            self._paint(value, None)

    def redraw(self, dc=None):
        """
        Redraw this painter's current value.
        """
        value = self.lastValue
        self.lastValue = None
        self._paint(value, dc)

    def clear(self, dc=None):
        """
        Clear the painter's current value from the screen and the painter
        itself.
        """
        if self.lastValue is not None:
            self._paint(None, dc)

    def _paint(self, value, dc):
        """
        Draws a previously processed C{value} on this painter's window.
        """
        if dc is None:
            dc = wx.ClientDC(self.view)

        dc.SetPen(self.PEN)
        dc.SetBrush(self.BRUSH)
        dc.SetFont(self.FONT)
        dc.SetTextForeground(self.TEXT_FOREGROUND)
        dc.SetTextBackground(self.TEXT_BACKGROUND)
        dc.SetLogicalFunction(self.FUNCTION)
        # dc.BeginDrawing()

        if self.lastValue is not None:
            self.clearValue(dc, self.lastValue)
            self.lastValue = None

        if value is not None:
            self.drawValue(dc, value)
            self.lastValue = value

        # dc.EndDrawing()

    def formatValue(self, value):
        """
        Template method that processes the C{value} tuple passed to the
        C{set()} method, returning the processed version.
        """
        return value

    def drawValue(self, dc, value):
        """
        Template method that draws a previously processed C{value} using the
        wxPython device context C{dc}.  This DC has already been configured, so
        calls to C{BeginDrawing()} and C{EndDrawing()} may not be made.
        """
        pass

    def clearValue(self, dc, value):
        """
        Template method that clears a previously processed C{value} that was
        previously drawn, using the wxPython device context C{dc}.  This DC has
        already been configured, so calls to C{BeginDrawing()} and
        C{EndDrawing()} may not be made.
        """
        pass


class LocationPainter(Painter):
    """
    Draws a text message containing the current position of the mouse in the
    lower left corner of the plot.
    """

    PADDING = 2
    PEN = wx.WHITE_PEN
    BRUSH = wx.WHITE_BRUSH

    def formatValue(self, value):
        """
        Extracts a string from the 1-tuple C{value}.
        """
        return value[0]

    def get_XYWH(self, dc, value):
        """
        Returns the upper-left coordinates C{(X, Y)} for the string C{value}
        its width and height C{(W, H)}.
        """
        height = dc.GetSize()[1]
        w, h = dc.GetTextExtent(value)
        x = self.PADDING
        y = int(height - (h + self.PADDING))
        return x, y, w, h

    def drawValue(self, dc, value):
        """
        Draws the string C{value} in the lower left corner of the plot.
        """
        x, y, w, h = self.get_XYWH(dc, value)
        dc.DrawText(value, x, y)

    def clearValue(self, dc, value):
        """
        Clears the string C{value} from the lower left corner of the plot by
        painting a white rectangle over it.
        """
        x, y, w, h = self.get_XYWH(dc, value)
        dc.DrawRectangle(x, y, w, h)


class CrosshairPainter(Painter):
    """
    Draws crosshairs through the current position of the mouse.
    """

    PEN = wx.WHITE_PEN
    FUNCTION = wx.XOR

    def formatValue(self, value):
        """
        Converts the C{(X, Y)} mouse coordinates from matplotlib to wxPython.
        """
        x, y = value
        return int(x), int(self.view.get_figure().bbox.height - y)

    def drawValue(self, dc, value):
        """
        Draws crosshairs through the C{(X, Y)} coordinates.
        """
        dc.CrossHair(*value)

    def clearValue(self, dc, value):
        """
        Clears the crosshairs drawn through the C{(X, Y)} coordinates.
        """
        dc.CrossHair(*value)


class RubberbandPainter(Painter):
    """
    Draws a selection rubberband from one point to another.
    """

    PEN = wx.WHITE_PEN
    FUNCTION = wx.XOR

    def formatValue(self, value):
        """
        Converts the C{(x1, y1, x2, y2)} mouse coordinates from matplotlib to
        wxPython.
        """
        x1, y1, x2, y2 = value
        height = self.view.get_figure().bbox.height
        y1 = height - y1
        y2 = height - y2
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        return [int(z) for z in (x1, y1, x2-x1, y2-y1)]

    def drawValue(self, dc, value):
        """
        Draws the selection rubberband around the rectangle
        C{(x1, y1, x2, y2)}.
        """
        dc.DrawRectangle(*value)

    def clearValue(self, dc, value):
        """
        Clears the selection rubberband around the rectangle
        C{(x1, y1, x2, y2)}.
        """
        dc.DrawRectangle(*value)


class CursorChanger:
    """
    Manages the current cursor of a wxPython window, allowing it to be switched
    between a normal arrow and a square cross.
    """

    def __init__(self, view, enabled=True):
        """
        Create a CursorChanger attached to the wxPython window C{view}.  The
        keyword argument C{enabled} has the same meaning as the argument to the
        C{setEnabled()} method.
        """
        self.view = view
        self.cursor = wx.CURSOR_DEFAULT
        self.enabled = enabled

    def setEnabled(self, state):
        """
        Enable or disable this cursor changer.  When disabled, the cursor is
        reset to the normal arrow and calls to the C{set()} methods have no
        effect.
        """
        oldState, self.enabled = self.enabled, state
        if oldState and not self.enabled and self.cursor != wx.CURSOR_DEFAULT:
            self.cursor = wx.CURSOR_DEFAULT
            self.view.SetCursor(wx.STANDARD_CURSOR)

    def setNormal(self):
        """
        Change the cursor of the associated window to a normal arrow.
        """
        if self.cursor != wx.CURSOR_DEFAULT and self.enabled:
            self.cursor = wx.CURSOR_DEFAULT
            self.view.SetCursor(wx.STANDARD_CURSOR)

    def setCross(self):
        """
        Change the cursor of the associated window to a square cross.
        """
        if self.cursor != wx.CURSOR_CROSS and self.enabled:
            self.cursor = wx.CURSOR_CROSS
            self.view.SetCursor(wx.CROSS_CURSOR)


#
# Printing Framework
#

# PostScript resolutions for the various WX print qualities
PS_DPI_HIGH_QUALITY = 600
PS_DPI_MEDIUM_QUALITY = 300
PS_DPI_LOW_QUALITY = 150
PS_DPI_DRAFT_QUALITY = 72


def update_postscript_resolution(printData):
    """
    Sets the default wx.PostScriptDC resolution from a wx.PrintData's quality
    setting.

    This is a workaround for WX ignoring the quality setting and defaulting to
    72 DPI.  Unfortunately wx.Printout.GetDC() returns a wx.DC object instead
    of the actual class, so it's impossible to set the resolution on the DC
    itself.

    Even more unforuntately, printing with libgnomeprint appears to always be
    stuck at 72 DPI.
    """
    if not callable(getattr(wx, 'PostScriptDC_SetResolution', None)):
        return

    quality = printData.GetQuality()
    if quality > 0:
        dpi = quality
    elif quality == wx.PRINT_QUALITY_HIGH:
        dpi = PS_DPI_HIGH_QUALITY
    elif quality == wx.PRINT_QUALITY_MEDIUM:
        dpi = PS_DPI_MEDIUM_QUALITY
    elif quality == wx.PRINT_QUALITY_LOW:
        dpi = PS_DPI_LOW_QUALITY
    elif quality == wx.PRINT_QUALITY_DRAFT:
        dpi = PS_DPI_DRAFT_QUALITY
    else:
        dpi = PS_DPI_HIGH_QUALITY

    wx.PostScriptDC_SetResolution(dpi)


class FigurePrinter:
    """
    Provides a simplified interface to the wxPython printing framework that's
    designed for printing matplotlib figures.
    """

    def __init__(self, view, printData=None):
        """
        Create a new C{FigurePrinter} associated with the wxPython widget
        C{view}.  The keyword argument C{printData} supplies a C{wx.PrintData}
        object containing the default printer settings.
        """
        self.view = view

        if printData is None:
            printData = wx.PrintData()

        self.setPrintData(printData)

    def getPrintData(self):
        """
        Return the current printer settings in their C{wx.PrintData} object.
        """
        return self.pData

    def setPrintData(self, printData):
        """
        Use the printer settings in C{printData}.
        """
        self.pData = printData
        update_postscript_resolution(self.pData)

    def pageSetup(self):
        dlg = wx.PrintDialog(self.view)
        pdData = dlg.GetPrintDialogData()
        pdData.SetPrintData(self.pData)

        if dlg.ShowModal() == wx.ID_OK:
            self.setPrintData(pdData.GetPrintData())
        dlg.Destroy()

    def previewFigure(self, figure, title=None):
        """
        Open a "Print Preview" window for the matplotlib chart C{figure}.  The
        keyword argument C{title} provides the printing framework with a title
        for the print job.
        """
        topwin = toplevel_parent_of_window(self.view)
        fpo = FigurePrintout(figure, title)
        fpo4p = FigurePrintout(figure, title)
        preview = wx.PrintPreview(fpo, fpo4p, self.pData)
        frame = wx.PreviewFrame(preview, topwin, 'Print Preview')
        if self.pData.GetOrientation() == wx.PORTRAIT:
            frame.SetSize(wx.Size(450, 625))
        else:
            frame.SetSize(wx.Size(600, 500))
        frame.Initialize()
        frame.Show(True)

    def printFigure(self, figure, title=None):
        """
        Open a "Print" dialog to print the matplotlib chart C{figure}.  The
        keyword argument C{title} provides the printing framework with a title
        for the print job.
        """
        pdData = wx.PrintDialogData()
        pdData.SetPrintData(self.pData)
        printer = wx.Printer(pdData)
        fpo = FigurePrintout(figure, title)
        if printer.Print(self.view, fpo, True):
            self.setPrintData(pdData.GetPrintData())


class FigurePrintout(wx.Printout):
    """
    Render a matplotlib C{Figure} to a page or file using wxPython's printing
    framework.
    """

    ASPECT_RECTANGULAR = 1
    ASPECT_SQUARE = 2

    def __init__(self, figure, title=None, size=None, aspectRatio=None):
        """
        Create a printout for the matplotlib chart C{figure}.  The
        keyword argument C{title} provides the printing framework with a title
        for the print job.  The keyword argument C{size} specifies how to scale
        the figure, from 1 to 100 percent.  The keyword argument C{aspectRatio}
        determines whether the printed figure will be rectangular or square.
        """
        self.figure = figure

        figTitle = figure.gca().title.get_text()
        if not figTitle:
            figTitle = title or 'Matplotlib Figure'

        if size is None:
            size = 100
        elif size < 1 or size > 100:
            raise ValueError('invalid figure size')
        self.size = size

        if aspectRatio is None:
            aspectRatio = self.ASPECT_RECTANGULAR
        elif (aspectRatio != self.ASPECT_RECTANGULAR
              and aspectRatio != self.ASPECT_SQUARE):
            raise ValueError('invalid aspect ratio')
        self.aspectRatio = aspectRatio

        wx.Printout.__init__(self, figTitle)

    def GetPageInfo(self):
        """
        Overrides wx.Printout.GetPageInfo() to provide the printing framework
        with the number of pages in this print job.
        """
        return (1, 1, 1, 1)

    def HasPage(self, pageNumber):
        """
        Overrides wx.Printout.GetPageInfo() to tell the printing framework
        of the specified page exists.
        """
        return pageNumber == 1

    def OnPrintPage(self, pageNumber):
        """
        Overrides wx.Printout.OnPrintPage() to render the matplotlib figure to
        a printing device context.
        """
        # % of printable area to use
        imgPercent = max(1, min(100, self.size)) / 100.0

        # ratio of the figure's width to its height
        if self.aspectRatio == self.ASPECT_RECTANGULAR:
            aspectRatio = 1.61803399
        elif self.aspectRatio == self.ASPECT_SQUARE:
            aspectRatio = 1.0
        else:
            raise ValueError('invalid aspect ratio')

        # PPI_P: Pixels Per Inch of the Printer
        wPPI_P, hPPI_P = [float(x) for x in self.GetPPIPrinter()]
        PPI_P = (wPPI_P + hPPI_P)/2.0

        # PPI: Pixels Per Inch of the DC
        if self.IsPreview():
            wPPI, hPPI = [float(x) for x in self.GetPPIScreen()]
        else:
            wPPI, hPPI = wPPI_P, hPPI_P
        PPI = (wPPI + hPPI)/2.0

        # Pg_Px: Size of the page (pixels)
        wPg_Px,  hPg_Px = [float(x) for x in self.GetPageSizePixels()]

        # Dev_Px: Size of the DC (pixels)
        wDev_Px, hDev_Px = [float(x) for x in self.GetDC().GetSize()]

        # Pg: Size of the page (inches)
        wPg = wPg_Px / PPI_P
        hPg = hPg_Px / PPI_P

        # minimum margins (inches)
        wM = 0.75
        hM = 0.75

        # Area: printable area within the margins (inches)
        wArea = wPg - 2*wM
        hArea = hPg - 2*hM

        # Fig: printing size of the figure
        # hFig is at a maximum when wFig == wArea
        max_hFig = wArea / aspectRatio
        hFig = min(imgPercent * hArea, max_hFig)
        wFig = aspectRatio * hFig

        # scale factor = device size / page size (equals 1.0 for real printing)
        S = ((wDev_Px/PPI)/wPg + (hDev_Px/PPI)/hPg)/2.0

        # Fig_Dx: scaled printing size of the figure (device pixels)
        # M_Dx: scaled minimum margins (device pixels)
        wFig_Dx = int(S * PPI * wFig)
        hFig_Dx = int(S * PPI * hFig)
        wM_Dx = int(S * PPI * wM)
        hM_Dx = int(S * PPI * hM)

        image = self.render_figure_as_image(wFig, hFig, PPI)

        if self.IsPreview():
            image = image.Scale(wFig_Dx, hFig_Dx)
        self.GetDC().DrawBitmap(image.ConvertToBitmap(), wM_Dx, hM_Dx, False)

        return True

    def render_figure_as_image(self, wFig, hFig, dpi):
        """
        Renders a matplotlib figure using the Agg backend and stores the result
        in a C{wx.Image}.  The arguments C{wFig} and {hFig} are the width and
        height of the figure, and C{dpi} is the dots-per-inch to render at.
        """
        figure = self.figure

        old_dpi = figure.dpi
        figure.dpi = dpi
        old_width = figure.get_figwidth()
        figure.set_figwidth(wFig)
        old_height = figure.get_figheight()
        figure.set_figheight(hFig)
        old_frameon = figure.frameon
        figure.frameon = False

        wFig_Px = int(figure.bbox.width)
        hFig_Px = int(figure.bbox.height)

        agg = RendererAgg(wFig_Px, hFig_Px, dpi)
        figure.draw(agg)

        figure.dpi = old_dpi
        figure.set_figwidth(old_width)
        figure.set_figheight(old_height)
        figure.frameon = old_frameon

        image = wx.EmptyImage(wFig_Px, hFig_Px)
        image.SetData(agg.tostring_rgb())
        return image


#
# wxPython event interface for the PlotPanel and PlotFrame
#

EVT_POINT_ID = wx.NewId()


def EVT_POINT(win, id, func):
    """
    Register to receive wxPython C{PointEvent}s from a C{PlotPanel} or
    C{PlotFrame}.
    """
    win.Connect(id, -1, EVT_POINT_ID, func)


class PointEvent(wx.PyCommandEvent):
    """
    wxPython event emitted when a left-click-release occurs in a matplotlib
    axes of a window without an area selection.

    @cvar axes: matplotlib C{Axes} which was left-clicked
    @cvar x: matplotlib X coordinate
    @cvar y: matplotlib Y coordinate
    @cvar xdata: axes X coordinate
    @cvar ydata: axes Y coordinate
    """

    def __init__(self, id, axes, x, y):
        """
        Create a new C{PointEvent} for the matplotlib coordinates C{(x, y)} of
        an C{axes}.
        """
        wx.PyCommandEvent.__init__(self, EVT_POINT_ID, id)
        self.axes = axes
        self.x = x
        self.y = y
        self.xdata, self.ydata = invert_point(x, y, axes.transData)

    def Clone(self):
        return PointEvent(self.GetId(), self.axes, self.x, self.y)


EVT_SELECTION_ID = wx.NewId()


def EVT_SELECTION(win, id, func):
    """
    Register to receive wxPython C{SelectionEvent}s from a C{PlotPanel} or
    C{PlotFrame}.
    """
    win.Connect(id, -1, EVT_SELECTION_ID, func)


class SelectionEvent(wx.PyCommandEvent):
    """
    wxPython event emitted when an area selection occurs in a matplotlib axes
    of a window for which zooming has been disabled.  The selection is
    described by a rectangle from C{(x1, y1)} to C{(x2, y2)}, of which only
    one point is required to be inside the axes.

    @cvar axes: matplotlib C{Axes} which was left-clicked
    @cvar x1: matplotlib x1 coordinate
    @cvar y1: matplotlib y1 coordinate
    @cvar x2: matplotlib x2 coordinate
    @cvar y2: matplotlib y2 coordinate
    @cvar x1data: axes x1 coordinate
    @cvar y1data: axes y1 coordinate
    @cvar x2data: axes x2 coordinate
    @cvar y2data: axes y2 coordinate
    """

    def __init__(self, id, axes, x1, y1, x2, y2):
        """
        Create a new C{SelectionEvent} for the area described by the rectangle
        from C{(x1, y1)} to C{(x2, y2)} in an C{axes}.
        """
        wx.PyCommandEvent.__init__(self, EVT_SELECTION_ID, id)
        self.axes = axes
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.x1data, self.y1data = invert_point(x1, y1, axes.transData)
        self.x2data, self.y2data = invert_point(x2, y2, axes.transData)

    def Clone(self):
        return SelectionEvent(self.GetId(), self.axes, self.x1, self.y1,
                              self.x2, self.y2)


#
# Matplotlib canvas in a wxPython window
#

class PlotPanel(FigureCanvasWxAgg):
    """
    A matplotlib canvas suitable for embedding in wxPython applications.
    """

    def __init__(self, parent, id, size=(6.0, 3.70), dpi=96, cursor=True,
                 location=True, crosshairs=True, selection=True, zoom=True,
                 autoscaleUnzoom=True):
        """
        Creates a new PlotPanel window that is the child of the wxPython window
        C{parent} with the wxPython identifier C{id}.

        The keyword arguments C{size} and {dpi} are used to create the
        matplotlib C{Figure} associated with this canvas.  C{size} is the
        desired width and height of the figure, in inches, as the 2-tuple
        C{(width, height)}.  C{dpi} is the dots-per-inch of the figure.

        The keyword arguments C{cursor}, C{location}, C{crosshairs},
        C{selection}, C{zoom}, and C{autoscaleUnzoom} enable or disable various
        user interaction features that are descibed in their associated
        C{set()} methods.
        """
        FigureCanvasWxAgg.__init__(self, parent, id, Figure(size, dpi))

        self.insideOnPaint = False
        self.cursor = CursorChanger(self, cursor)
        self.location = LocationPainter(self, location)
        self.crosshairs = CrosshairPainter(self, crosshairs)
        self.rubberband = RubberbandPainter(self, selection)
        rightClickUnzoom = True  # for now this is default behavior
        self.director = PlotPanelDirector(self, zoom, selection,
                                          rightClickUnzoom, autoscaleUnzoom)

        self.figure.set_edgecolor('black')
        self.figure.set_facecolor('white')
        self.SetBackgroundColour(wx.WHITE)

        # find the toplevel parent window and register an activation event
        # handler that is keyed to the id of this PlotPanel
        topwin = toplevel_parent_of_window(self)
        topwin.Connect(self.GetId(), wx.ID_ANY,
                       wx.wxEVT_ACTIVATE, self.OnActivate)

        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        # self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    def OnActivate(self, evt):
        """
        Handles the wxPython window activation event.
        """
        if not isinstance(self, FigureCanvasWxAgg):
            return
        if not evt.GetActive():
            self.cursor.setNormal()
            self.location.clear()
            self.crosshairs.clear()
            self.rubberband.clear()
        evt.Skip()

    def OnEraseBackground(self, evt):
        """
        Overrides the wxPython backround repainting event to reduce flicker.
        """
        pass

    def _onPaint(self, evt):
        """
        Overrides the C{FigureCanvasWxAgg} paint event to redraw the
        crosshairs, etc.
        """
        # avoid wxPyDeadObject errors
        if not isinstance(self, FigureCanvasWxAgg):
            return

        self.insideOnPaint = True
        FigureCanvasWxAgg._onPaint(self, evt)
        self.insideOnPaint = False

        dc = wx.PaintDC(self)
        self.location.redraw(dc)
        self.crosshairs.redraw(dc)
        self.rubberband.redraw(dc)

    def get_figure(self):
        """
        Returns the figure associated with this canvas.
        """
        return self.figure

    def set_cursor(self, state):
        """
        Enable or disable the changing mouse cursor.  When enabled, the cursor
        changes from the normal arrow to a square cross when the mouse enters a
        matplotlib axes on this canvas.
        """
        self.cursor.setEnabled(state)

    def set_location(self, state):
        """
        Enable or disable the display of the matplotlib axes coordinates of the
        mouse in the lower left corner of the canvas.
        """
        self.location.setEnabled(state)

    def set_crosshairs(self, state):
        """
        Enable or disable drawing crosshairs through the mouse cursor when it
        is inside a matplotlib axes.
        """
        self.crosshairs.setEnabled(state)

    def set_selection(self, state):
        """
        Enable or disable area selections, where user selects a rectangular
        area of the canvas by left-clicking and dragging the mouse.
        """
        self.rubberband.setEnabled(state)
        self.director.setSelection(state)

    def set_zoom(self, state):
        """
        Enable or disable zooming in when the user makes an area selection and
        zooming out again when the user right-clicks.
        """
        self.director.setZoomEnabled(state)

    def set_autoscale_unzoom(self, state):
        """
        Enable or disable automatic view rescaling when the user zooms out to
        the initial figure.
        """
        self.director.setAutoscaleUnzoom(state)

    def zoomed(self, axes):
        """
        Returns a boolean indicating whether or not the C{axes} is zoomed in.
        """
        return self.director.zoomed(axes)

    def draw(self, **kwds):
        """
        Draw the associated C{Figure} onto the screen.
        """
        # don't redraw if the left mouse button is down and avoid
        # wxPyDeadObject errors
        if (not self.director.canDraw()
                or not isinstance(self, FigureCanvasWxAgg)):
            return

        if MATPLOTLIB_0_98_3:
            FigureCanvasWxAgg.draw(self, kwds.get('drawDC', None))
        else:
            FigureCanvasWxAgg.draw(self, kwds.get('repaint', True))

        # Don't redraw the decorations when called by _onPaint()
        if not self.insideOnPaint:
            self.location.redraw()
            self.crosshairs.redraw()
            self.rubberband.redraw()

    def notify_point(self, axes, x, y):
        """
        Called by the associated C{PlotPanelDirector} to emit a C{PointEvent}.
        """
        wx.PostEvent(self, PointEvent(self.GetId(), axes, x, y))

    def notify_selection(self, axes, x1, y1, x2, y2):
        """
        Called by the associated C{PlotPanelDirector} to emit a
        C{SelectionEvent}.
        """
        wx.PostEvent(self, SelectionEvent(self.GetId(), axes, x1, y1, x2, y2))

    def _get_canvas_xy(self, evt):
        """
        Returns the X and Y coordinates of a wxPython event object converted to
        matplotlib canavas coordinates.
        """
        return evt.GetX(), int(self.figure.bbox.height - evt.GetY())

    def _onKeyDown(self, evt):
        """
        Overrides the C{FigureCanvasWxAgg} key-press event handler, dispatching
        the event to the associated C{PlotPanelDirector}.
        """
        self.director.keyDown(evt)

    def _onKeyUp(self, evt):
        """
        Overrides the C{FigureCanvasWxAgg} key-release event handler,
        dispatching the event to the associated C{PlotPanelDirector}.
        """
        self.director.keyUp(evt)

    def _onLeftButtonDown(self, evt):
        """
        Overrides the C{FigureCanvasWxAgg} left-click event handler,
        dispatching the event to the associated C{PlotPanelDirector}.
        """
        x, y = self._get_canvas_xy(evt)
        self.director.leftButtonDown(evt, x, y)

    def _onLeftButtonUp(self, evt):
        """
        Overrides the C{FigureCanvasWxAgg} left-click-release event handler,
        dispatching the event to the associated C{PlotPanelDirector}.
        """
        x, y = self._get_canvas_xy(evt)
        self.director.leftButtonUp(evt, x, y)

    def _onRightButtonDown(self, evt):
        """
        Overrides the C{FigureCanvasWxAgg} right-click event handler,
        dispatching the event to the associated C{PlotPanelDirector}.
        """
        x, y = self._get_canvas_xy(evt)
        self.director.rightButtonDown(evt, x, y)

    def _onRightButtonUp(self, evt):
        """
        Overrides the C{FigureCanvasWxAgg} right-click-release event handler,
        dispatching the event to the associated C{PlotPanelDirector}.
        """
        x, y = self._get_canvas_xy(evt)
        self.director.rightButtonUp(evt, x, y)

    def _onMotion(self, evt):
        """
        Overrides the C{FigureCanvasWxAgg} mouse motion event handler,
        dispatching the event to the associated C{PlotPanelDirector}.
        """
        x, y = self._get_canvas_xy(evt)
        self.director.mouseMotion(evt, x, y)


#
# Matplotlib canvas in a top-level wxPython window
#

class PlotFrame(wx.Frame):
    """
    A matplotlib canvas embedded in a wxPython top-level window.

    @cvar ABOUT_TITLE: Title of the "About" dialog.
    @cvar ABOUT_MESSAGE: Contents of the "About" dialog.
    """

    ABOUT_TITLE = 'About wxmpl.PlotFrame'
    ABOUT_MESSAGE = ('wxmpl.PlotFrame %s\n' % __version__
                     + 'Written by Ken McIvor <mcivor@iit.edu>\n'
                     + 'Copyright 2005-2009 Illinois Institute of Technology')

    def __init__(self, parent, id, title, size=(6.0, 3.7), dpi=96, cursor=True,
                 location=True, crosshairs=True, selection=True, zoom=True,
                 autoscaleUnzoom=True, **kwds):
        """
        Creates a new PlotFrame top-level window that is the child of the
        wxPython window C{parent} with the wxPython identifier C{id} and the
        title of C{title}.

        All of the named keyword arguments to this constructor have the same
        meaning as those arguments to the constructor of C{PlotPanel}.

        Any additional keyword arguments are passed to the constructor of
        C{wx.Frame}.
        """
        wx.Frame.__init__(self, parent, id, title, **kwds)
        self.panel = PlotPanel(self, -1, size, dpi, cursor, location,
                               crosshairs, selection, zoom)

        pData = wx.PrintData()
        pData.SetPaperId(wx.PAPER_LETTER)
        if callable(getattr(pData, 'SetPrinterCommand', None)):
            pData.SetPrinterCommand(POSTSCRIPT_PRINTING_COMMAND)
        self.printer = FigurePrinter(self, pData)

        self.create_menus()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, 1, wx.ALL | wx.EXPAND, 5)
        self.SetSizer(sizer)
        self.Fit()

    def create_menus(self):
        mainMenu = wx.MenuBar()
        menu = wx.Menu()

        entry_id = wx.NewId()
        menu.Append(entry_id, '&Save As...\tCtrl+S',
                    'Save a copy of the current plot')
        wx.EVT_MENU(self, entry_id, self.OnMenuFileSave)

        menu.AppendSeparator()

        if wx.Platform != '__WXMAC__':
            entry_id = wx.NewId()
            menu.Append(entry_id, 'Page Set&up...',
                        'Set the size and margins of the printed figure')
            wx.EVT_MENU(self, entry_id, self.OnMenuFilePageSetup)

            entry_id = wx.NewId()
            menu.Append(entry_id, 'Print Pre&view...',
                        'Preview the print version of the current plot')
            wx.EVT_MENU(self, entry_id, self.OnMenuFilePrintPreview)

        entry_id = wx.NewId()
        menu.Append(entry_id, '&Print...\tCtrl+P', 'Print the current plot')
        wx.EVT_MENU(self, entry_id, self.OnMenuFilePrint)

        menu.AppendSeparator()

        entry_id = wx.NewId()
        menu.Append(entry_id, '&Close Window\tCtrl+W',
                    'Close the current plot window')
        wx.EVT_MENU(self, entry_id, self.OnMenuFileClose)

        mainMenu.Append(menu, '&File')
        menu = wx.Menu()

        entry_id = wx.NewId()
        menu.Append(entry_id, '&About...', 'Display version information')
        wx.EVT_MENU(self, entry_id, self.OnMenuHelpAbout)

        mainMenu.Append(menu, '&Help')
        self.SetMenuBar(mainMenu)

    def OnMenuFileSave(self, evt):
        """
        Handles File->Save menu events.
        """
        fileName = wx.FileSelector('Save Plot', default_extension='png',
                                   wildcard=('Portable Network Graphics (*.png)|*.png|'
                                             + 'Encapsulated Postscript (*.eps)|*.eps|All files (*.*)|*.*'),
                                   parent=self, flags=wx.SAVE | wx.OVERWRITE_PROMPT)

        if not fileName:
            return

        path, ext = os.path.splitext(fileName)
        ext = ext[1:].lower()

        if ext != 'png' and ext != 'eps':
            error_message = (
                'Only the PNG and EPS image formats are supported.\n'
                'A file extension of `png\' or `eps\' must be used.')
            wx.MessageBox(error_message, 'Error - plotit',
                          parent=self, style=wx.OK | wx.ICON_ERROR)
            return

        try:
            self.panel.print_figure(fileName)
        except IOError as e:
            if e.strerror:
                err = e.strerror
            else:
                err = e

            wx.MessageBox('Could not save file: %s' % err, 'Error - plotit',
                          parent=self, style=wx.OK | wx.ICON_ERROR)

    def OnMenuFilePageSetup(self, evt):
        """
        Handles File->Page Setup menu events
        """
        self.printer.pageSetup()

    def OnMenuFilePrintPreview(self, evt):
        """
        Handles File->Print Preview menu events
        """
        self.printer.previewFigure(self.get_figure())

    def OnMenuFilePrint(self, evt):
        """
        Handles File->Print menu events
        """
        self.printer.printFigure(self.get_figure())

    def OnMenuFileClose(self, evt):
        """
        Handles File->Close menu events.
        """
        self.Close()

    def OnMenuHelpAbout(self, evt):
        """
        Handles Help->About menu events.
        """
        wx.MessageBox(self.ABOUT_MESSAGE, self.ABOUT_TITLE, parent=self,
                      style=wx.OK)

    def get_figure(self):
        """
        Returns the figure associated with this canvas.
        """
        return self.panel.figure

    def set_cursor(self, state):
        """
        Enable or disable the changing mouse cursor.  When enabled, the cursor
        changes from the normal arrow to a square cross when the mouse enters a
        matplotlib axes on this canvas.
        """
        self.panel.set_cursor(state)

    def set_location(self, state):
        """
        Enable or disable the display of the matplotlib axes coordinates of the
        mouse in the lower left corner of the canvas.
        """
        self.panel.set_location(state)

    def set_crosshairs(self, state):
        """
        Enable or disable drawing crosshairs through the mouse cursor when it
        is inside a matplotlib axes.
        """
        self.panel.set_crosshairs(state)

    def set_selection(self, state):
        """
        Enable or disable area selections, where user selects a rectangular
        area of the canvas by left-clicking and dragging the mouse.
        """
        self.panel.set_selection(state)

    def set_zoom(self, state):
        """
        Enable or disable zooming in when the user makes an area selection and
        zooming out again when the user right-clicks.
        """
        self.panel.set_zoom(state)

    def set_autoscale_unzoom(self, state):
        """
        Enable or disable automatic view rescaling when the user zooms out to
        the initial figure.
        """
        self.panel.set_autoscale_unzoom(state)

    def draw(self):
        """
        Draw the associated C{Figure} onto the screen.
        """
        self.panel.draw()


#
# wxApp providing a matplotlib canvas in a top-level wxPython window
#

class PlotApp(wx.App):
    """
    A wxApp that provides a matplotlib canvas embedded in a wxPython top-level
    window, encapsulating wxPython's nuts and bolts.

    @cvar ABOUT_TITLE: Title of the "About" dialog.
    @cvar ABOUT_MESSAGE: Contents of the "About" dialog.
    """

    ABOUT_TITLE = None
    ABOUT_MESSAGE = None

    def __init__(self, title="WxMpl", size=(6.0, 3.7), dpi=96, cursor=True,
                 location=True, crosshairs=True, selection=True, zoom=True, **kwds):
        """
        Creates a new PlotApp, which creates a PlotFrame top-level window.

        The keyword argument C{title} specifies the title of this top-level
        window.

        All of other the named keyword arguments to this constructor have the
        same meaning as those arguments to the constructor of C{PlotPanel}.

        Any additional keyword arguments are passed to the constructor of
        C{wx.App}.
        """
        self.title = title
        self.size = size
        self.dpi = dpi
        self.cursor = cursor
        self.location = location
        self.crosshairs = crosshairs
        self.selection = selection
        self.zoom = zoom
        wx.App.__init__(self, **kwds)

    def OnInit(self):
        self.frame = panel = PlotFrame(None, -1, self.title, self.size,
                                       self.dpi, self.cursor, self.location, self.crosshairs,
                                       self.selection, self.zoom)

        if self.ABOUT_TITLE is not None:
            panel.ABOUT_TITLE = self.ABOUT_TITLE

        if self.ABOUT_MESSAGE is not None:
            panel.ABOUT_MESSAGE = self.ABOUT_MESSAGE

        panel.Show(True)
        return True

    def get_figure(self):
        """
        Returns the figure associated with this canvas.
        """
        return self.frame.get_figure()

    def set_cursor(self, state):
        """
        Enable or disable the changing mouse cursor.  When enabled, the cursor
        changes from the normal arrow to a square cross when the mouse enters a
        matplotlib axes on this canvas.
        """
        self.frame.set_cursor(state)

    def set_location(self, state):
        """
        Enable or disable the display of the matplotlib axes coordinates of the
        mouse in the lower left corner of the canvas.
        """
        self.frame.set_location(state)

    def set_crosshairs(self, state):
        """
        Enable or disable drawing crosshairs through the mouse cursor when it
        is inside a matplotlib axes.
        """
        self.frame.set_crosshairs(state)

    def set_selection(self, state):
        """
        Enable or disable area selections, where user selects a rectangular
        area of the canvas by left-clicking and dragging the mouse.
        """
        self.frame.set_selection(state)

    def set_zoom(self, state):
        """
        Enable or disable zooming in when the user makes an area selection and
        zooming out again when the user right-clicks.
        """
        self.frame.set_zoom(state)

    def draw(self):
        """
        Draw the associated C{Figure} onto the screen.
        """
        self.frame.draw()


#
# Automatically resizing vectors and matrices
#

class VectorBuffer:
    """
    Manages a Numerical Python vector, automatically growing it as necessary to
    accomodate new entries.
    """

    def __init__(self):
        self.data = np.zeros((16,), np.Float)
        self.nextRow = 0

    def clear(self):
        """
        Zero and reset this buffer without releasing the underlying array.
        """
        self.data[:] = 0.0
        self.nextRow = 0

    def reset(self):
        """
        Zero and reset this buffer, releasing the underlying array.
        """
        self.data = np.zeros((16,), np.Float)
        self.nextRow = 0

    def append(self, point):
        """
        Append a new entry to the end of this buffer's vector.
        """
        nextRow = self.nextRow
        data = self.data

        resize = False
        if nextRow == data.shape[0]:
            nR = int(np.ceil(self.data.shape[0]*1.5))
            resize = True

        if resize:
            self.data = np.zeros((nR,), np.Float)
            self.data[0:data.shape[0]] = data

        self.data[nextRow] = point
        self.nextRow += 1

    def getData(self):
        """
        Returns the current vector or C{None} if the buffer contains no data.
        """
        if self.nextRow == 0:
            return None
        else:
            return self.data[0:self.nextRow]


class MatrixBuffer:
    """
    Manages a Numerical Python matrix, automatically growing it as necessary to
    accomodate new rows of entries.
    """

    def __init__(self):
        self.data = np.zeros((16, 1), np.Float)
        self.nextRow = 0

    def clear(self):
        """
        Zero and reset this buffer without releasing the underlying array.
        """
        self.data[:, :] = 0.0
        self.nextRow = 0

    def reset(self):
        """
        Zero and reset this buffer, releasing the underlying array.
        """
        self.data = np.zeros((16, 1), np.Float)
        self.nextRow = 0

    def append(self, row):
        """
        Append a new row of entries to the end of this buffer's matrix.
        """
        row = np.asarray(row, np.Float)
        nextRow = self.nextRow
        data = self.data
        nPts = row.shape[0]

        if nPts == 0:
            return

        resize = True
        if nextRow == data.shape[0]:
            nC = data.shape[1]
            nR = int(np.ceil(self.data.shape[0]*1.5))
            if nC < nPts:
                nC = nPts
        elif data.shape[1] < nPts:
            nR = data.shape[0]
            nC = nPts
        else:
            resize = False

        if resize:
            self.data = np.zeros((nR, nC), np.Float)
            rowEnd, colEnd = data.shape
            self.data[0:rowEnd, 0:colEnd] = data

        self.data[nextRow, 0:nPts] = row
        self.nextRow += 1

    def getData(self):
        """
        Returns the current matrix or C{None} if the buffer contains no data.
        """
        if self.nextRow == 0:
            return None
        else:
            return self.data[0:self.nextRow, :]


#
# Utility functions used by the StripCharter
#

def make_delta_bbox(X1, Y1, X2, Y2):
    """
    Returns a C{Bbox} describing the range of difference between two sets of X
    and Y coordinates.
    """
    return make_bbox(get_delta(X1, X2), get_delta(Y1, Y2))


def get_delta(X1, X2):
    """
    Returns the vector of contiguous, different points between two vectors.
    """
    n1 = X1.shape[0]
    n2 = X2.shape[0]

    if n1 < n2:
        return X2[n1:]
    elif n1 == n2:
        # shape is no longer a reliable indicator of change, so assume things
        # are different
        return X2
    else:
        return X2


def make_bbox(X, Y):
    """
    Returns a C{Bbox} that contains the supplied sets of X and Y coordinates.
    """
    if X is None or X.shape[0] == 0:
        x1 = x2 = 0.0
    else:
        x1 = min(X)
        x2 = max(X)

    if Y is None or Y.shape[0] == 0:
        y1 = y2 = 0.0
    else:
        y1 = min(Y)
        y2 = max(Y)

    return Bbox.from_extents(x1, y1, x2, y2)


#
# Strip-charts lines using a matplotlib axes
#

class StripCharter:
    """
    Plots and updates lines on a matplotlib C{Axes}.
    """

    def __init__(self, axes):
        """
        Create a new C{StripCharter} associated with a matplotlib C{axes}.
        """
        self.axes = axes
        self.channels = []
        self.lines = {}

    def setChannels(self, channels):
        """
        Specify the data-providers of the lines to be plotted and updated.
        """
        self.lines = None
        self.channels = channels[:]

        # minimal Axes.cla()
        self.axes.legend_ = None
        self.axes.lines = []

    def update(self):
        """
        Redraw the associated axes with updated lines if any of the channels'
        data has changed.
        """
        axes = self.axes
        figureCanvas = axes.figure.canvas

        zoomed = figureCanvas.zoomed(axes)

        redraw = False
        if self.lines is None:
            self._create_plot()
            redraw = True
        else:
            for channel in self.channels:
                redraw = self._update_channel(channel, zoomed) or redraw

        if redraw:
            if not zoomed:
                axes.autoscale_view()
            figureCanvas.draw()

    def _create_plot(self):
        """
        Initially plot the lines corresponding to the data-providers.
        """
        self.lines = {}
        axes = self.axes
        styleGen = _process_plot_var_args(axes)

        for channel in self.channels:
            self._plot_channel(channel, styleGen)

        if self.channels:
            lines = [self.lines[x] for x in self.channels]
            labels = [x.get_label() for x in lines]
            self.axes.legend(lines, labels, numpoints=2,
                             prop=FontProperties(size='x-small'))

    def _plot_channel(self, channel, styleGen):
        """
        Initially plot a line corresponding to one of the data-providers.
        """
        empty = False
        x = channel.getX()
        y = channel.getY()
        if x is None or y is None:
            x = y = []
            empty = True

        line = styleGen(x, y).next()
        line._wxmpl_empty_line = empty

        if channel.getColor() is not None:
            line.set_color(channel.getColor())
        if channel.getStyle() is not None:
            line.set_linestyle(channel.getStyle())
        if channel.getMarker() is not None:
            line.set_marker(channel.getMarker())
            line.set_markeredgecolor(line.get_color())
            line.set_markerfacecolor(line.get_color())

        line.set_label(channel.getLabel())
        self.lines[channel] = line
        if not empty:
            self.axes.add_line(line)

    def _update_channel(self, channel, zoomed):
        """
        Replot a line corresponding to one of the data-providers if the data
        has changed.
        """
        if channel.hasChanged():
            channel.setChanged(False)
        else:
            return False

        axes = self.axes
        line = self.lines[channel]
        newX = channel.getX()
        newY = channel.getY()

        if newX is None or newY is None:
            return False

        oldX = line._x
        oldY = line._y

        x, y = newX, newY
        line.set_data(x, y)

        if line._wxmpl_empty_line:
            axes.add_line(line)
            line._wxmpl_empty_line = False
        else:
            if line.get_transform() != axes.transData:
                xys = axes._get_verts_in_data_coords(
                    line.get_transform(), zip(x, y))
            else:
                xys = np.zeros((x.shape[0], 2), np.Float)
                xys[:, 0] = x
                xys[:, 1] = y
            axes.update_datalim(xys)

        if zoomed:
            return axes.viewLim.overlaps(
                make_delta_bbox(oldX, oldY, newX, newY))
        else:
            return True


#
# Data-providing interface to the StripCharter
#

class Channel:
    """
    Provides data for a C{StripCharter} to plot.  Subclasses of C{Channel}
    override the template methods C{getX()} and C{getY()} to provide plot data
    and call C{setChanged(True)} when that data has changed.
    """

    def __init__(self, name, color=None, style=None, marker=None):
        """
        Creates a new C{Channel} with the matplotlib label C{name}.  The
        keyword arguments specify the strings for the line color, style, and
        marker to use when the line is plotted.
        """
        self.name = name
        self.color = color
        self.style = style
        self.marker = marker
        self.changed = False

    def getLabel(self):
        """
        Returns the matplotlib label for this channel of data.
        """
        return self.name

    def getColor(self):
        """
        Returns the line color string to use when the line is plotted, or
        C{None} to use an automatically generated color.
        """
        return self.color

    def getStyle(self):
        """
        Returns the line style string to use when the line is plotted, or
        C{None} to use the default line style.
        """
        return self.style

    def getMarker(self):
        """
        Returns the line marker string to use when the line is plotted, or
        C{None} to use the default line marker.
        """
        return self.marker

    def hasChanged(self):
        """
        Returns a boolean indicating if the line data has changed.
        """
        return self.changed

    def setChanged(self, changed):
        """
        Sets the change indicator to the boolean value C{changed}.

        @note: C{StripCharter} instances call this method after detecting a
        change, so a C{Channel} cannot be shared among multiple charts.
        """
        self.changed = changed

    def getX(self):
        """
        Template method that returns the vector of X axis data or C{None} if
        there is no data available.
        """
        return None

    def getY(self):
        """
        Template method that returns the vector of Y axis data or C{None} if
        there is no data available.
        """
        return None
