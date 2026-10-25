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

from qgis.PyQt.QtWidgets import QDialog,QToolBox,QWidget,QVBoxLayout,QFileDialog,QListWidgetItem,QMessageBox
	
#qgis import
from qgis.core import *
from qgis.gui import *
#other
import os
import sys
import glob

from .custom_input import *

#~ uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'project_dialog.ui'))
#~ print('uiFilePath: %s'%uiFilePath)
#~ FormClass = uic.loadUiType(uiFilePath)[0]

class RemoveData(QDialog):
	closed = pyqtSignal()
	VARLIST = {}
	WSLIST = {}
	
	def __init__(self, parent=None, varNames={}, wsNames={}):
		QDialog.__init__(self, parent)
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'remove_data.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle('Idragra4QGIS')
		
		# populate list of variables
		self.VARLIST = varNames
		for value in self.VARLIST.values():
			self.METEOVAR_CB.addItem(value)
		
		self.WSLIST = wsNames
		# populate list of weather stations
		for value in self.WSLIST.values():
			self.WS_CB.addItem(value)
		
		# set data:
		s = QSettings('UNIMI-DISAA', 'Idragra4QGIS')
		
		self.buttonBox.accepted.connect(self.validate)
		self.buttonBox.rejected.connect(self.reject)
		#QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
		#QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
		QMetaObject.connectSlotsByName(self)
		
	def closeEvent(self, event):
		self.closed.emit()
		
	def getData(self):
		# get variable
		selVarName = self.METEOVAR_CB.currentText()
		for key, value in self.VARLIST.items():
			if value == selVarName:
				selVarName = key
			
		# get ws name
		sensorId = self.WS_CB.currentText()
		for key, value in self.WSLIST.items():
			if value == selVarName:
				sensorId = key		
		
		# get date limits
		fromDate = self.FROMDATE.date().toPyDate()
		toDate = self.TODATE.date().toPyDate()
		
		return {'varName':selVarName, 'sensorId':sensorId, 'fromDate':str(fromDate), 'toDate':str(toDate)}

	def validate(self):
		if (self.FROMDATE.date().toPyDate() > self.TODATE.date().toPyDate()):
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Critical)
			msg.setText('Error')
			msg.setInformativeText('To-date must forward from-date')
			msg.setWindowTitle('Idragra4QGIS')
			msg.setDetailedText('Fix time')
			msg.setStandardButtons(QMessageBox.Ok)
			msg.exec()
		else:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Question)
			msg.setText('Confirm action!')
			msg.setInformativeText('Would you like to delete data from %s to %s'%(str(self.FROMDATE.date().toPyDate()),str(self.TODATE.date().toPyDate())))
			msg.setWindowTitle('Idragra4QGIS')
			msg.setStandardButtons(QMessageBox.Yes|QMessageBox.No)
			ret = msg.exec()
			if ret == QMessageBox.Yes:
				self.accept()