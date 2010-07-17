dicompyler Readme
-----------------

dicompyler:
A Python based radiation therapy research platform using the DICOM standard

dicompyler is released under a BSD license. See the included license.txt file,
or available online at: http://code.google.com/p/dicompyler/

Full documentation and source code for dicompyler is available online at:
http://code.google.com/p/dicompyler/

Version 0.2 Features
-----------------

- Import CT Images, DICOM RT structure set, RT dose and RT plan files
- Extensible plugin system with included plugins:
  - 2D image viewer with dose and structure overlay
  - Dose volume histogram viewer with the ability to analyze DVH parameters
  - DICOM data tree viewer
  - Patient anonymizer

Getting Started
-----------------

dicompyler will read properly formatted DICOM and DICOM-RT files. To get
started, run dicompyler and click "Open Patient" to bring up a dialog box that
will show the DICOM files in the last selected directory. You may click
"Browse..." to navigate to other folders that contain DICOM data.

In the current version of dicompyler, you can import any DICOM CT image, DICOM
RT structure set, RT dose and RT plan files. dicompyler will automatically
highlight the deepest item for the patient. All related items (up the tree)
will be automatically imported as well. Alternatively, you can selectively
import data. For example, If you only want to import CT images and an RT
structure set just highlight the RT structure set. If you are importing an RT
dose file and the corresponding plan does not contain a prescription dose, enter
one in the box first. To import the data, click "Select" and dicompyler will
process the information.

Once the DICOM data has been loaded, the main window will show the patient and
plan information. Additionally it will show a list of structures and isodoses
that are associated with the plan.

Example DICOM-RT data is provided in the downloads tab on the project homepage:
http://code.google.com/p/dicompyler/downloads/list

Included Plugins
-----------------

You can use the 2D View tab to navigate CT data with corresponding structures
and isodoses. The DVH tab can be used to inspect and analyze DVH curves. The
DICOM tree view tab can be used to delve into the raw DICOM data of the imported
files.You can anonymize the loaded DICOM files via the anonymizer found in the
Tools menu.

Custom Plugins
-----------------

Since dicompyler is based on a plugin architecture, users can write their own
plugins with ease. For more information see the Plugin Development Guide on the
dicompyler wiki: http://code.google.com/p/dicompyler/wiki/PluginDevelopmentGuide

Bugs and Feedback
-----------------

Please report any bugs or feedback on the dicompyler discussion group found at:
http://groups.google.com/group/dicompyler/

Credits
-----------------

A number of individuals have contributed to dicompyler and can be found in the
included credits.txt.
