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

from qgis.core import QgsMapLayerProxyModel


class GroupstatsDialog(QDialog):
	closed = pyqtSignal()
	
	FILELIST = {}
	VARLIST = {}
	FUNLIST = {}
	
	def __init__(self, parent=None, varDict ={}, funDict = {}):
		QDialog.__init__(self, parent)
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'groupstats_dialog.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle('IdragraTools')

		self.VARDICT = varDict
		self.FUNDICT = funDict

		# populate list of variable
		self.VAR_CB.addItems(list(self.VARDICT.values()))
		self.GROUPBY_FUN_CB.addItems(list(self.FUNDICT.values()))
		# populate list of layer
		self.GROUPBY_LAY_CB.setFilters(QgsMapLayerProxyModel.PolygonLayer)
		self.GROUPBY_LAY_CB.setCurrentIndex(-1)

		# connect combobox
		self.GROUPBY_LAY_CB.layerChanged.connect(self.GROUPBY_FLD_CB.setLayer)  # setLayer is a native slot function

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
		selVarIdx = list(self.VARDICT.values()).index(selVarName)
		selVar = list(self.VARDICT.keys())[selVarIdx]

		selFunName = self.GROUPBY_FUN_CB.currentText()
		selFunIdx = list(self.FUNDICT.values()).index(selFunName)
		selFun = list(self.FUNDICT.keys())[selFunIdx]


		selGroupLay = self.GROUPBY_LAY_CB.currentLayer().source()
		selGroupName = self.GROUPBY_LAY_CB.currentLayer().name()
		selGroupField = self.GROUPBY_FLD_CB.currentText()

		selMerge = self.MERGE_CB.isChecked()


		return {'selVarIdx':selVarIdx,
				'selGroupLay':selGroupLay,
				'selGroupField':selGroupField,
				'selGroupName':selGroupName,
				'selFunIdx':selFunIdx,
				'selMerge':selMerge}
