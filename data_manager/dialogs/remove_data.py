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

from qgis.PyQt.QtWidgets import QDialog,QToolBox,QWidget,QVBoxLayout,QFileDialog,QListWidgetItem,QMessageBox
	
#qgis import
from qgis.core import *
from qgis.gui import *
#other
import os
import sys
import glob


class RemoveData(QDialog):
	closed = pyqtSignal()
	VARLIST = {}
	WSLIST = {}
	
	def __init__(self, parent=None, varName= '',settings = None):
		QDialog.__init__(self, parent)
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'remove_data.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle(self.tr('Delete data'))
		self.varName = varName
		
		# set data:
		self.s = settings
		
		self.buttonBox.accepted.connect(self.validate)
		self.buttonBox.rejected.connect(self.reject)
		#QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
		#QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
		QMetaObject.connectSlotsByName(self)
		
	def closeEvent(self, event):
		self.closed.emit()
		
	def getData(self):
		# get date limits
		fromDate = self.FROMDATE.date().toPyDate()
		toDate = self.TODATE.date().toPyDate()
		
		return {'fromDate':str(fromDate), 'toDate':str(toDate)}

	def validate(self):
		if (self.FROMDATE.date().toPyDate() > self.TODATE.date().toPyDate()):
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Critical)
			msg.setText('Error')
			msg.setInformativeText('To-date must forward from-date')
			msg.setWindowTitle('Data Manager')
			msg.setDetailedText('Fix time')
			msg.setStandardButtons(QMessageBox.Ok)
			msg.exec_()
		else:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Question)
			msg.setText('Confirm action!')
			msg.setInformativeText('Would you like to delete data of <%s> from %s to %s'%
								   (self.varName,
									str(self.FROMDATE.date().toPyDate()),
									str(self.TODATE.date().toPyDate())
									)
								   )
			msg.setWindowTitle('Data Manager')
			msg.setStandardButtons(QMessageBox.Yes|QMessageBox.No)
			ret = msg.exec_()
			if ret == QMessageBox.Yes:
				self.accept()