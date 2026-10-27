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
from forms.custom_input import FieldInput, CheckInput, DateInput


class ImportVectorDialog(QDialog):
    closed = pyqtSignal()

    def __init__(self, parent=None, layList=[], fields=[], skipFields=[], dateFld=[], settings=None,
                 title='Import vector dialog', fieldLabels=None):
        QDialog.__init__(self, parent)
        # Set up the user interface from Designer.
        uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'import_vector_dialog.ui'))
        uic.loadUi(uiFilePath, self)

        self.setWindowTitle(title)

        self.FLDLIST = []
        self.LAYLIST = layList
        fieldLabels = fieldLabels or {}
        # populate station ids
        for l,v in layList.items():
            self.SOURCE_CB.addItem(l)

        # add as many filed as required
        for f in fields:
            fieldName = f.name()
            if fieldName not in skipFields:
                label = fieldLabels.get(fieldName, f.alias() or fieldName)

                if fieldName in dateFld:
                    newFI = DateInput(objName = fieldName, labelString = label, defaultValue ='',descr = '')
                else:
                    newFI = FieldInput(objName = fieldName, labelString = label, defaultValue ='',descr = '')

                self.layout().addWidget(newFI)
                self.FLDLIST.append(newFI)



        self.updateFieldWidgets(self.SOURCE_CB.currentText())

        # add check box
        self.SAVEEDIT_CB = CheckInput(objName='SAVEEDIT_CB', labelString =self.tr('Save edit'), defaultValue = False, descr = '')
        self.layout().addWidget(self.SAVEEDIT_CB)

        # add button box
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setGeometry(QtCore.QRect(30, 240, 341, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.layout().addWidget(self.buttonBox)

        # connect file browser
        self.SOURCE_BTN.clicked.connect(self.setInputFile)
        # connect source combobox
        self.SOURCE_CB.currentTextChanged.connect(self.updateFieldWidgets)
        # set data:
        self.s = settings

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        # QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
        # QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
        QMetaObject.connectSlotsByName(self)

    def closeEvent(self, event):
        self.closed.emit()

    def setInputFile(self):
        res = QFileDialog.getOpenFileName(self, caption=self.tr('Import from:'), directory=self.s.value('lastPath'),
                                          filter=QgsProviderRegistry.instance().fileVectorFilters())
        filePath = res[0]
        res = None
        if filePath != '':
            self.SOURCE_CB.lineEdit().setText(filePath)

    def updateFieldWidgets(self,lay):
        #print('laydict:',self.LAYLIST)
        if os.path.exists(lay):
            layPath = lay
        else:
            layPath = self.LAYLIST[lay].source()


        for fldWG in self.FLDLIST:
            if isinstance(fldWG, FieldInput):
                fldWG.updateFieldList(layerPath = layPath, selectedItem= fldWG.getValue()[0])

    def getData(self):
        # get output file
        selLay = self.SOURCE_CB.currentText()
        if os.path.exists(str(selLay)):
            lay = QgsVectorLayer(selLay, "new", "ogr")
        else:
            lay = self.LAYLIST[selLay]

        fieldDict = {}
        assignDate = None

        for fldWG in self.FLDLIST:
            if isinstance(fldWG, FieldInput):
                #print('-',fldWG.objectName(),'-',fldWG.getValue()[0] )
                if fldWG.getValue()[0] != '':
                    fieldDict[fldWG.objectName()] = fldWG.getValue()[0]
            elif isinstance(fldWG, DateInput):
                assignDate = fldWG.getValue()
            else:
                print('unmanaged input type')

        saveEdit = self.SAVEEDIT_CB.getValue()

        return {'lay': lay, 'fieldDict': fieldDict,'assignDate':assignDate, 'saveEdit':saveEdit}
