dicompyler Readme
-----------------

dicompyler is a Python application to view and modify DICOM and DICOM-RT files.

dicompyler is released under a BSD license. See the included license.txt file,
or available online at: http://code.google.com/p/dicompyler/

Full documentation and source code for dicompyler is available online at:
http://code.google.com/p/dicompyler/

Features
-----------------

- Import DICOM RT structure set, RT dose and RT plan files
- Display and evaluate DVH data from DICOM RT dose files

Getting Started
-----------------

dicompyler will read properly formatted DICOM and DICOM-RT files. To get
started, run dicompyler and click "Open Patient" to bring up a dialog box that
will show the DICOM files in the last selected directory. You may click
"Browse..." to navigate to other folders that contain DICOM data.

In the current version of dicompyler, you can only import a RT dose file that
has a linked plan and structure set. dicompyler should automatically highlight
the RT plan for the patient. You may choose a different plan just by clicking on
it. If your plan does not have contain a specified prescription dose, enter one
in the box first. To import the data, click "Select" and dicompyler will process
the information.

Once the DICOM data has been loaded, the main window will show the patient and
plan information. Additionally it will show a list of structures that are
associated with the plan. Click on a structure and the corresponding DVH will be
displayed. Additional DVH constraints can be analyzed by manipulating the
constraint type and the slider. This can be used to look at parameters such as
V100, D90, D1cc, etc.

Example DICOM-RT data is provided within the testdata folder of the dicompyler
installation.

Bugs and Feedback
-----------------

Please report any bugs or feedback on the dicompyler discussion group found at:
http://groups.google.com/group/dicompyler/

Credits
-----------------

A number of individuals have contributed to dicompyler and can be found in the
included credits.txt.
