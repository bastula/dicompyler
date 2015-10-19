# dicompyler

<img src='http://wiki.dicompyler.googlecode.com/hg/images/0.3/2dview_mac_thumb.png' align='right' height='240' width='287' alt="dicompyler screenshot">
dicompyler is an extensible open source radiation therapy research platform based on the DICOM standard. It also functions as a cross-platform DICOM RT viewer.

dicompyler is written in Python and is built on a number of technologies including:  [pydicom](http://www.pydicom.org), [wxPython](http://www.wxpython.org), [PIL](http://www.pythonware.com/products/pil/), and [matplotlib](http://matplotlib.org) and runs on Windows, Mac OS X and Linux.

Take a tour of dicompyler by checking out some [screenshots](https://github.com/bastula/dicompyler/wiki/Screenshots) or download a copy today.

![alt text](https://img.shields.io/pypi/v/dicompyler.svg "pypi version") ![alt text](https://img.shields.io/pypi/dm/dicompyler.svg "pypi version")
---

## Downloads:
Downloads are available through Google Drive:<br>
<br>
Version 0.4.2: [Windows](https://bit.ly/dicompylerwindows) | [Mac](https://bit.ly/dicompylermac) | [Source](https://pypi.python.org/packages/source/d/dicompyler/dicompyler-0.4.2.tar.gz#md5=adbfa47b07f983f17fdba26a1442fce0) | [Test Data](https://bit.ly/dicompylertestdata) - Released July 15th, 2014 - [Release Notes](https://github.com/bastula/dicompyler/wiki/ReleaseNotes) 

## Features:
* Import CT/MR/PET Images, DICOM RT structure set, RT dose and RT plan files
* Extensible plugin system with included plugins:
  * 2D image viewer with dose and structure overlay
  * Dose volume histogram viewer with the ability to analyze DVH parameters
  * DICOM data tree viewer
  * Patient anonymizer
  * 3rd-party plugins can be found at [https://github.com/dicompyler/dicompyler-plugins](https://github.com/dicompyler/dicompyler-plugins)
  * Custom plugins can be written by following the [Plugin development guide](https://github.com/bastula/dicompyler/wiki/PluginDevelopmentGuide)

For upcoming features, see the [project roadmap](https://github.com/bastula/dicompyler/wiki/Roadmap).

## System Requirements:
* Windows 2000/XP/Vista/7
* Mac OS X 10.5 - 10.10 (Intel) - Must bypass [Gatekeeper](https://support.apple.com/en-us/HT202491)
* Linux - via a package from [PyPI](https://pypi.python.org/pypi/dicompyler) or a [Debian package](https://packages.debian.org/sid/dicompyler) (courtesy of debian-med)

If you are interested in building from source, please check out the [build instructions](https://github.com/bastula/dicompyler/wiki/BuildRequirements).

## Getting Help:
* As a starting point, please read the [FAQ](https://github.com/bastula/dicompyler/wiki/FAQ) as it answers the most commonly asked questions about dicompyler.
* If you are unable to find the answer in the FAQ or in the [wiki](https://github.com/bastula/dicompyler/wiki), dicompyler has a [discussion forum](https://groups.google.com/group/dicompyler) hosted on Google Groups.

## Citing dicompyler:
* If you need to cite dicompyler as a reference in your publication, please use the following citation:
  * **A Panchal and R Keyes**. "SU-GG-T-260: dicompyler: An Open Source Radiation Therapy Research Platform with a Plugin Architecture" Med. Phys. 37, 3245, 2010
  * The reference in Medical Physics can be accessed via [http://dx.doi.org/10.1118/1.3468652](http://dx.doi.org/10.1118/1.3468652)
