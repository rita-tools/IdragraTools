# -*- coding: utf-8 -*-

"""
/***************************************************************************
 Data Manager
 A tool to manage time series from database
-------------------
		begin				: 2020-12-01
		copyright			: (C) 2020 by Enrico A. Chiaradia
		email				    : enrico.chiaradia@unimi.it
 ***************************************************************************/

/***************************************************************************
 *																		                                                               *
 *   This program is free software; you can redistribute it and/or modify                                *
 *   it under the terms of the GNU General Public License as published by                              *
 *   the Free Software Foundation; either version 2 of the License, or	                                   *
 *   (at your option) any later version.								                                                   *
 *																		                                                               *
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
	QTableWidgetItem

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

class ImportData(QDialog):
    closed = pyqtSignal()
    VARLIST = {}
    WSLIST = {}

    def __init__(self, parent=None, varName='',settings = None):
        QDialog.__init__(self, parent)
        # Set up the user interface from Designer.
        uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'import_data.ui'))
        uic.loadUi(uiFilePath, self)
        self.setWindowTitle(self.tr('Import data in %s' % varName))

        self.TABLE_PREVIEW.setHorizontalHeaderLabels([self.tr('Timestamp'), self.tr('Value')])

        # connect file browser
        self.SELFILE_BTN.clicked.connect(self.setInputFile)
        # connect
        self.SELFILE_TXT.textChanged.connect(self.setPreview)
        self.TC_SB.valueChanged.connect(self.setPreview)
        self.VC_SB.valueChanged.connect(self.setPreview)
        self.SKIPLINES_SB.valueChanged.connect(self.setPreview)
        self.FORMAT_TXT.textChanged.connect(self.setPreview)
        self.SEP_TXT.textChanged.connect(self.setPreview)
        # set data:
        self.s = settings

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        # QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
        # QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
        QMetaObject.connectSlotsByName(self)

        self.previewError = False
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

    def closeEvent(self, event):
        self.closed.emit()

    def setInputFile(self):
        res = QFileDialog.getOpenFileName(self, caption=self.tr('Import from:'), directory=self.s.value('lastPath'),
                                          filter='Comma Separated file (*.csv)')
        print(res)
        filePath = res[0]
        res = None
        if filePath != '':
            self.SELFILE_TXT.setText(filePath)

    def setPreview(self, dummy):
        # get all settings
        filePath = self.SELFILE_TXT.text()
        timeFldIdx = self.TC_SB.value() - 1
        valueFldIdx = self.VC_SB.value() - 1
        skip = self.SKIPLINES_SB.value()
        timeFormat = self.FORMAT_TXT.text()
        column_sep = self.SEP_TXT.text()

        while self.TABLE_PREVIEW.rowCount() > 0:
            self.TABLE_PREVIEW.removeRow(self.TABLE_PREVIEW.rowCount() - 1)

        self.previewError = False

        # open file
        try:
            in_file = open(filePath, "r")
            i = 0
            v = 0
            while v <= 15:
                in_line = in_file.readline()
                if i >= skip:
                    # process the line
                    in_line = in_line[:-1]
                    data = in_line.split(column_sep)
                    timestamp = '?!#'
                    value = '?!#'
                    try:
                        timestamp = datetime.strptime(data[timeFldIdx], timeFormat)
                    except Exception as e:
                        self.previewError = True
                        if len(data) > timeFldIdx:
                            timestamp += data[timeFldIdx]
                    try:
                        value = float(data[valueFldIdx])
                    except:
                        self.previewError = True
                        if len(data) > valueFldIdx:
                            value += data[valueFldIdx]
                    # add to table
                    self.TABLE_PREVIEW.insertRow(self.TABLE_PREVIEW.rowCount())
                    self.TABLE_PREVIEW.setItem(self.TABLE_PREVIEW.rowCount() - 1, 0, QTableWidgetItem(timestamp.strftime('%Y-%m-%d')))
                    self.TABLE_PREVIEW.setItem(self.TABLE_PREVIEW.rowCount() - 1, 1, QTableWidgetItem(str(value)))
                    v += 1

                i += 1
        except Exception as e:
            self.previewError = True
            print('exception',str(e))

        if self.previewError:
            self.MSG_LBL.setText(self.tr('Unable to correctly parse text file into table'))
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        else:
            self.MSG_LBL.setText(self.tr('Text file is ready to be imported'))
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)

    def setVariableList(self):
        pass

    def setWsList(self):
        pass

    def getData(self):
        # get output file
        selFile = self.SELFILE_TXT.text()

        # get file format
        timeFldIdx = self.TC_SB.value() - 1  # zero based
        valueFldIdx = self.VC_SB.value() - 1  # zero based
        sep = self.SEP_TXT.text()
        timeFormat = self.FORMAT_TXT.text()
        skipLines = self.SKIPLINES_SB.value()

        return {'selFile': selFile, 'timeFldIdx': timeFldIdx, 'valueFldIdx': valueFldIdx, 'sep': sep,
                'timeFormat': timeFormat, 'skipLines': skipLines}
