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

from qgis.PyQt.QtWidgets import QDialog,QToolBox,QWidget,QVBoxLayout,QFileDialog,QListWidgetItem

import os

class StatMaps(QDialog):
	closed = pyqtSignal()
	
	FILELIST = {}
	VARLIST = {}
	FUNLIST = {}
	
	def __init__(self, parent=None, varDict ={},funDict = {},startDate = None,endDate=None):
		QDialog.__init__(self, parent)
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'stat_maps.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle('Idragra4QGIS')
		
		self.VARDICT = varDict
		self.FUNDICT = funDict
		
		# populate list of variable
		self.VAR_CB.addItems(list(self.VARDICT.values()))
		self.FUN_CB.addItems(list(self.FUNDICT.values()))

		self.FROMDAY.setMinimumDate(startDate)
		self.TODAY.setMaximumDate(endDate)
		self.FROMDAY.setDate(startDate)
		self.TODAY.setDate(endDate)
		
		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		#QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
		#QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
		QMetaObject.connectSlotsByName(self)
		
	def closeEvent(self, event):
		self.closed.emit()
		
	
	def getData(self):
		# get selected vars
		selVarName = self.VAR_CB.currentText()
		selFunName = self.FUN_CB.currentText()
		
		selVarIdx = list(self.VARDICT.values()).index(selVarName)
		selFunIdx = list(self.FUNDICT.values()).index(selFunName)
		
		selVar = list(self.VARDICT.keys())[selVarIdx]
		selFun = list(self.FUNDICT.keys())[selFunIdx]
		
		startDate = self.FROMDAY.date().toString("yyyy-MM-dd")
		endDate = self.TODAY.date().toString("yyyy-MM-dd")
		
		return {'variable':selVar, 'function':selFun, 'fromdate':startDate, 'todate': endDate}
