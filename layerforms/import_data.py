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
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog,QFileDialog
import os


class ImportData(QDialog):
	closed = pyqtSignal()
	VARLIST = {}
	WSLIST = {}
	
	def __init__(self, parent=None, varNames={}):
		QDialog.__init__(self, parent)
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'import_data.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle('Idragra4QGIS')
		
		# populate list of variables
		self.VARLIST = varNames
		for value in self.VARLIST.values():
			self.METEOVAR_CB.addItem(value)
		
		# connect file browser
		self.SELFILE_BTN.clicked.connect(self.setInputFile)		
		
		# set data:
		s = QSettings('UNIMI-DISAA', 'Idragra4QGIS')
		
		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		#QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
		#QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
		QMetaObject.connectSlotsByName(self)
		
	def closeEvent(self, event):
		self.closed.emit()
		
	def setInputFile(self):
		s = QSettings('UNIMI-DISAA', 'Idragra4QGIS')
		res = QFileDialog.getOpenFileName(self, caption = self.tr('Import from:'), directory = s.value('lastPath'), filter = 'Comma Separated file (*.csv)')
		filePath = res[0]
		if filePath != '':
			self.SELFILE_TXT.setText(res[0])
	
	def setVariableList(self):
		pass
		
	def setWsList(self):
		pass
		
	def getData(self):
		# get variable
		selVarName = self.METEOVAR_CB.currentText()
		for key, value in self.VARLIST.items():
			if value == selVarName:
				selVarName = key
			
		# get output file
		selFile = self.SELFILE_TXT.text()
		
		# get file format
		timeFldIdx = self.TC_SB.value()-1 # zero based
		valueFldIdx =self.VC_SB.value() -1 # zero based
		sep = self.SEP_TXT.text()
		timeFormat = self.FORMAT_TXT.text()
		skipLines = self.SKIPLINES_SB.value()
		
		return {'varName':selVarName, 'selFile':selFile, 'timeFldIdx':timeFldIdx, 'valueFldIdx':valueFldIdx, 'sep':sep, 'timeFormat':timeFormat, 'skipLines':skipLines}
