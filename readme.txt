dicompyler Readme
=================

dicompyler is an extensible radiation therapy research platform and viewer for
DICOM and DICOM RT.

dicompyler is released under a BSD license. See the included license.txt file,
or available online at: http://code.google.com/p/dicompyler/

Full documentation and source code for dicompyler is available online at:
http://code.google.com/p/dicompyler/

Features
========

- Import CT/PET/MRI Images, DICOM RT structure set, RT dose and RT plan files
- Extensible plugin system with included plugins:
    - 2D image viewer with dose and structure overlay
    - Dose volume histogram viewer with the ability to analyze DVH parameters
    - DICOM data tree viewer
    - Patient anonymizer

Quick Start
===========

If you have downloaded dicompyler as an application for Windows or Mac, please
follow the normal process for running any other application on your system.

If you are running from a Python package, a script called "dicompyler" is now
present on your path, which you can run from your command line or terminal.

If you are running from a source checkout, there is a script in the main folder
called "dicompyler_app.py" which can be executed via your Python interpreter.

Release Notes for dicompyler 0.4.1-1 - January 1st, 2012
========================================================

- Fixed a critical bug where the logging folder could not be created and dicompyler would not run.

Release Notes for dicompyler 0.4.1 - December 31st, 2011
========================================================

- General
    - Added an error reporter for Windows and Mac versions allowing easy error submission
    - Added support for volumetric image series (i.e. CT, MR, PET)
    - Added support for RT Ion Plan
    - Improved image sorting significantly which now allows for non-axial orientations and non-parallel image series
    - Implemented console and file logging, along with a menu item to display log files
    - Implemented an preference to enable detailed logging for debugging
    - Implemented searching of DICOM files within subfolders
    - Implemented the ability to specify the user plugins folder in the preferences
    - Added support for RT Dose files that don't reference RT Plans
    - Added support for unrelated RT Dose and RT Structure Sets that share the same frame of reference
- DVH calculation and viewer
    - Implemented a preference to force recalculation of DVH data regardless of the presence in RT Dose
    - Limited the number of bins in the DVH calculation to 500 Gy due to high doses in brachytherapy plans
    - Automatically calculate DVHs for a structure only if they are not present within the RT Dose file
- 2D image viewer
    - Improved support for very low/high doses in the main interface and 2D View
- Anonymization
    - Added support for more tags that can should be de-identified
- Bug fixes
    - Fixed a bug where multiple series were loaded when a single series was selected due to the same Frame of Reference
    - Fixed a bug if multiple Target Prescriptions exist in a RT Plan file.
    - Fixed overestimation of volume calculation when using the DVH to calculate volumes
    - Fixed a bug when calculating DVHs for structures that are empty
    - Fixed a bug if DVH data has less bins than actually expected
    - Fixed a bug if the structure data was located slice position with a negative value close to zero
    - Fixed a bug regarding dose display if the current image slice is outside of the dose grid range
    - Fixed a bug where the displayed image width does not correspond to the actual image width
    - Fixed a bug with isodose rendering by moving the origin by 1 px right and 1 px down
    - Fixed a bug if the dose grid boundaries were located outside of the image grid


This release also includes all the new features introduced in dicompyler 0.4a2:
-------------------------------------------------------------------------------

- General
    - Automatic conversion of Differential DVHs to Cumulative DVHs
    - Automatic import of TomoTherapy Prescription Dose
    - Preferences dialog for each plugin with data stored in JSON format
    - Support structures that don't have color information
    - Added scrollbars to isodose and structure lists
    - Added a status bar to the program to show additional information
    - Added Export plugin capability
    - Added independent DVH calculation from RT Dose / Structure Set data
- 2D image viewer
    - Support CT data that has multiple window / level presets
    - Support for non-coincident dose planes
    - New isodose generation using matplotlib backend
    - Holes in contours are now properly displayed
    - Support CT data that is missing the SliceLocation tag
    - More accurate panning when zoomed during mouse movement
    - Support RescaleIntercept & RescaleSlope tags for more accurate window / level values
    - Added DICOM / pixel coordinate display of the mouse cursor in the status bar
    - Added image / dose value display of the mouse cursor in the status bar
- Anonymization
    - Now an export plugin, found under the File->Export menu

Getting Started
===============

dicompyler will read properly formatted DICOM and DICOM-RT files. To get
started, run dicompyler and click "Open Patient" to bring up a dialog box that
will show the DICOM files in the last selected directory. You may click
"Browse..." to navigate to other folders that contain DICOM data.

In the current version of dicompyler, you can import any DICOM CT, PET,
or MRI image series, DICOM RT structure set, RT dose and RT plan files.
dicompyler will automatically highlight the deepest item for the patient.
All related items (up the tree) will be automatically imported as well.

Alternatively, you can selectively import data. For example, If you only want
to import CT images and an RT structure set just highlight the RT structure set.
If you are importing an RT dose file and the corresponding plan does not
contain a prescription dose, enter one in the box first. To import the data,
click "Select" and dicompyler will process the information.

Once the DICOM data has been loaded, the main window will show the patient and
plan information. Additionally it will show a list of structures and isodoses
that are associated with the plan.

Example DICOM-RT data is provided in the downloads tab on the project homepage:
http://code.google.com/p/dicompyler/downloads/list

Included Plugins
================

You can use the 2D View tab to navigate CT, PET or MRI data with corresponding
structures and isodoses. The DVH tab can be used to inspect and analyze DVH
curves. The DICOM tree view tab can be used to delve into the raw DICOM data of
the imported files. You can anonymize the loaded DICOM files via the anonymizer
found in the File --> Export menu.

Custom Plugins
==============

Since dicompyler is based on a plugin architecture, users can write their own
plugins with ease. For more information see the Plugin Development Guide on the
dicompyler wiki: http://code.google.com/p/dicompyler/wiki/PluginDevelopmentGuide

3rd-party plugins can be found at http://code.google.com/p/dicompyler-plugins/

Bugs and Feedback
=================

Please report any bugs or feedback on the dicompyler discussion group found at:
http://groups.google.com/group/dicompyler/

Credits
=======

A number of individuals have contributed to dicompyler and can be found in the
included credits.txt.
