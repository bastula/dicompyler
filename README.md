dicompyler
============

<img src='https://raw.githubusercontent.com/wiki/bastula/dicompyler/images/0.3/2dview_mac_thumb.png' align='right' height='240' width='287' alt="dicompyler screenshot">
dicompyler is an extensible open source radiation therapy research platform based on the DICOM standard. It also functions as a cross-platform DICOM RT viewer.

dicompyler is written in Python and is built on a number of technologies including:  [pydicom](https://github.com/pydicom/pydicom), [wxPython](http://www.wxpython.org), [Pillow](http://python-pillow.org/), and [matplotlib](http://matplotlib.org) and runs on Windows, Mac OS X and Linux.

dicompyler is released under a BSD [license](dicompyler/license.txt).

Take a tour of dicompyler by checking out some [screenshots](https://github.com/bastula/dicompyler/wiki/Screenshots) or download a copy today.

![alt text](https://img.shields.io/pypi/v/dicompyler.svg "pypi version") ![alt text](https://img.shields.io/pypi/dm/dicompyler.svg "pypi version")
---

Downloads:
----------
Downloads are available through Google Drive:<br>
<br>
Version 0.4.2: [Windows](https://bit.ly/dicompylerwindows) | [Mac](https://bit.ly/dicompylermac) | [Source](https://pypi.python.org/packages/source/d/dicompyler/dicompyler-0.4.2.tar.gz#md5=adbfa47b07f983f17fdba26a1442fce0) | [Test Data](https://bit.ly/dicompylertestdata) - Released July 15th, 2014 - [Release Notes](https://github.com/bastula/dicompyler/wiki/ReleaseNotes) 

Features:
---------
* Import CT/MR/PET Images, DICOM RT structure set, RT dose and RT plan files
* Extensible plugin system with included plugins:
  * 2D image viewer with dose and structure overlay
  * Dose volume histogram viewer with the ability to analyze DVH parameters
  * DICOM data tree viewer
  * Patient anonymizer
  * 3rd-party plugins can be found at [https://github.com/dicompyler/dicompyler-plugins](https://github.com/dicompyler/dicompyler-plugins)
  * Custom plugins can be written by following the [Plugin development guide](https://github.com/bastula/dicompyler/wiki/PluginDevelopmentGuide)

For upcoming features, see the [project roadmap](https://github.com/bastula/dicompyler/wiki/Roadmap).

System Requirements:
--------------------
* Windows XP/Vista/7/8/10
* Mac OS X 10.5 - 10.13 (Intel) - Must bypass [Gatekeeper](https://support.apple.com/en-us/HT202491)
* Linux - via a package from [PyPI](https://pypi.python.org/pypi/dicompyler) or a [Debian package](https://packages.debian.org/sid/dicompyler) (courtesy of debian-med)

If you are interested in building from source, please check out the [build instructions](https://github.com/bastula/dicompyler/wiki/BuildRequirements).

Getting Started:
----------------

* How to run dicompyler:
  * If you have downloaded dicompyler as an application for Windows or Mac, please
follow the normal process for running any other application on your system.

  * If you are running from a Python package, a script called "dicompyler" will now
be present on your path, which you can run from your command line or terminal.

  * If you are running from a source checkout, there is a script in the main folder
called "dicompyler_app.py" which can be executed via your Python interpreter.

dicompyler will read properly formatted DICOM and DICOM-RT files. To get
started, run dicompyler and click "Open Patient" to bring up a dialog box that
will show the DICOM files in the last selected directory. You may click
"Browse..." to navigate to other folders that contain DICOM data.

In the current version of dicompyler, you can import any DICOM CT, PET,
or MRI image series, DICOM RT structure set, RT dose and RT plan files.
dicompyler will automatically highlight the most dependent item for the patient.
All related items (up the tree) will be automatically imported as well.

Alternatively, you can selectively import data. For example, If you only want
to import CT images and an RT structure set just highlight the RT structure set.
If you are importing an RT dose file and the corresponding plan does not
contain a prescription dose, enter one in the box first. To import the data,
click "Select" and dicompyler will process the information.

Once the DICOM data has been loaded, the main window will show the patient and
plan information. Additionally it will show a list of structures and isodoses
that are associated with the plan.

Getting Help:
-------------
* As a starting point, please read the [FAQ](https://github.com/bastula/dicompyler/wiki/FAQ) as it answers the most commonly asked questions about dicompyler.
* If you are unable to find the answer in the FAQ or in the [wiki](https://github.com/bastula/dicompyler/wiki), dicompyler has a [discussion forum](https://groups.google.com/group/dicompyler) hosted on Google Groups.

Citing dicompyler:
------------------
* If you need to cite dicompyler as a reference in your publication, please use the following citation:
  * **A Panchal and R Keyes**. "SU-GG-T-260: dicompyler: An Open Source Radiation Therapy Research Platform with a Plugin Architecture" Med. Phys. 37, 3245, 2010
  * The reference in Medical Physics can be accessed via [http://dx.doi.org/10.1118/1.3468652](http://dx.doi.org/10.1118/1.3468652)
