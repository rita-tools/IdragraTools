# -*- coding: utf-8 -*-

"""
/***************************************************************************
 IdrAgraTools
 A QGIS plugin to manage water demand simulation with IdrAgra model
 The plugin shares user interfaces and tools to manage water in irrigation districts
-------------------
		begin				: 2020-12-01
		copyright			: (C) 2020 by Enrico A. Chiaradia
		email				    : enrico.chiaradia@unimi.it
 ***************************************************************************/

/***************************************************************************
 *																		   *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or	   *
 *   (at your option) any later version.								   *
 *																		   *
 ***************************************************************************/
"""
__author__ = 'Enrico A. Chiaradia'
__date__ = '2020-12-01'
__copyright__ = '(C) 2020 by Enrico A. Chiaradia'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'


from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *

from qgis.PyQt import uic

from qgis.PyQt.QtWidgets import QDialog, QToolBox, QWidget, QVBoxLayout, QFileDialog, QListWidgetItem, QDialogButtonBox, \
    QTableWidgetItem, QRadioButton, QMessageBox

# qgis import
from qgis.core import *
from qgis.gui import *
# other
import os
import sys
import glob
from datetime import datetime


# ~ uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'project_dialog.ui'))
# ~ print('uiFilePath: %s'%uiFilePath)
# ~ FormClass = uic.loadUiType(uiFilePath)[0]
from forms.custom_input import FieldInput, CheckInput, DateInput, FileInput, FileOutput, CRSInput


class NewDbDialog(QDialog):
    closed = pyqtSignal()

    def __init__(self, parent=None, settings=None,fileext = 'gpkg'):
        QDialog.__init__(self, parent)
        self.fileext = fileext.lstrip('.')
        # add file browser
        self.layout = QVBoxLayout()
        self.GPKG_FILE = FileOutput('GPKG_FILE', self.tr('Create database file'), settings['DBFILE'], type='*.'+fileext,
                                   descr = self.tr('Set database name'))
        self.layout.addWidget(self.GPKG_FILE)

        # add crs dialog
        self.CRS = CRSInput('CRS', self.tr('Select CRS'), settings['CRS'], self.tr('Set database name'))
        self.layout.addWidget(self.CRS)

        # add qradiobutton
        self.USEDEMO_RB = QRadioButton(self.tr('Use demo parameters'))
        self.USEDEMO_RB.clicked.connect(self.switchImportMode)
        self.USEDEMO_RB.setChecked(True)
        self.layout.addWidget(self.USEDEMO_RB)

        # add checkbox
        self.LOADPAR_CB = CheckInput('LOADPAR_CB', self.tr('Load demo parameters'), settings['LOAD_SAMPLE_PAR'],
                                      descr = self.tr('Load default parameters'))
        self.layout.addWidget(self.LOADPAR_CB)

        self.LOADDATA_CB = CheckInput('LOADDATA_CB', self.tr('Load demo data'), settings['LOAD_SAMPLE_DATA'],
                                      descr = self.tr('Load sample data other than default parameters'))
        self.layout.addWidget(self.LOADDATA_CB)

        self.USESOURCE_RB = QRadioButton(self.tr('Use data from existing database'))
        self.USESOURCE_RB.clicked.connect(self.switchImportMode)
        self.layout.addWidget(self.USESOURCE_RB)

        self.SOURCEFOLDER_FW = FileInput('SOURCE_FILE', self.tr('Source file'), settings['SOURCE_DB'],
                                    type='*.' + fileext,
                                    descr=self.tr('Set source database name'))
        self.SOURCEFOLDER_FW.setEnabled(False)
        self.layout.addWidget(self.SOURCEFOLDER_FW)

        # add button box
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setGeometry(QtCore.QRect(30, 240, 341, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.layout.addWidget(self.buttonBox)

        self.setLayout(self.layout)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        # QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
        # QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
        QMetaObject.connectSlotsByName(self)

    def closeEvent(self, event):
        self.closed.emit()

    def accept(self):
        if not self.GPKG_FILE.getValue().strip():
            QMessageBox.warning(
                self,
                self.tr('Missing database filename'),
                self.tr('Select a filename for the new GeoPackage database.')
            )
            self.GPKG_FILE.setFocus()
            return

        super().accept()

    def switchImportMode(self):
        useSource = self.USESOURCE_RB.isChecked()
        self.SOURCEFOLDER_FW.setEnabled(useSource)
        self.LOADPAR_CB.setEnabled(not useSource)
        self.LOADDATA_CB.setEnabled(not useSource)

    def getData(self):
        # get output file
        dbFile = self.GPKG_FILE.getValue().strip()
        expectedSuffix = '.' + self.fileext
        if not dbFile.lower().endswith(expectedSuffix.lower()):
            dbFile += expectedSuffix
        crs = self.CRS.getValue()
        loadSamplePar = self.LOADPAR_CB.getValue()
        loadSampleData = self.LOADDATA_CB.getValue()
        sourceFile = ''
        if self.SOURCEFOLDER_FW.isEnabled():
            sourceFile = self.SOURCEFOLDER_FW.getValue()

        return {'dbFile': dbFile, 'crs':crs,
                'loadSamplePar': loadSamplePar, 'loadSampleData': loadSampleData,
				'sourceFile':sourceFile}
