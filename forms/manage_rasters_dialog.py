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

import processing
from qgis.PyQt.QtCore import *

from qgis.PyQt import uic

from qgis.PyQt.QtWidgets import QDialog, QToolBox, QWidget, QVBoxLayout, QFileDialog, QListWidgetItem, QDialogButtonBox, \
	QAbstractItemView, QMainWindow

import os

from ..tools.delete_raster_from_DB import deleteRasterFromDB
from ..tools.import_raster_in_db import importRasterInDB
from ..tools.array_table_model import ArrayTableModel
from forms.import_raster_dialog import ImportRasterDialog


class ManageRastersDialog(QMainWindow):
	closed = pyqtSignal()
	rasterAdded = pyqtSignal(str, str)
	rasterDeleted = pyqtSignal(str, str)
	accepted = pyqtSignal()
	rejected = pyqtSignal()

	def __init__(self, iface=None, assignTime = True,rasterDict = {},tableName='',DBM = None):
		QMainWindow.__init__(self, iface.mainWindow())
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'manage_rasters_dialog.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle('IdragraTools')

		# set global variables
		self.assignTime = assignTime
		self.rasterDict = rasterDict
		self.tableName = tableName
		self.gpkgFile = DBM.DBName
		self.iface = iface
		self.DBM = DBM
		# update the table widget with name, path columns
		self.updateTable()

		# connect buttons
		self.ADDBTN.clicked.connect(self.addRaster)
		self.DELETEBTN.clicked.connect(self.deleteRaster)

		self.CLOSEBTN.clicked.connect(self.reject)
		QMetaObject.connectSlotsByName(self)

	def closeEvent(self, event):
		self.closed.emit()

	def accept(self):
		self.close()
		self.accepted.emit()
		return 1

	def reject(self):
		self.close()
		return 0

	def getData(self):
		aModel = self.TV.model()
		#print('model data:',aModel.datatable)
		kList = aModel.getColumnValue(columnIndex=0)
		vList = aModel.getColumnValue(columnIndex=1)
		newDict = {}
		#print('kList',kList,'vList',vList)
		for k,v in zip(kList,vList):
			if k:
				newDict[k]=v

		return newDict

	def updateTable(self):
		data = []
		header =[self.tr('Name'),self.tr('Source')]
		for k,v in self.rasterDict.items():
			data.append([k,v])

		aModel = ArrayTableModel(self, data, header)
		aModel.setEditableColumn([])

		self.TV.setModel(aModel)
		self.TV.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.TV.horizontalHeader().setStretchLastSection(True)
		self.TV.setColumnHidden(1, True) # hide column with path because actually no more used

	def addRaster(self):
		# open file
		dlg = ImportRasterDialog(self.iface, self.assignTime)
		# See if OK was pressed
		def insertRaster():
			res = dlg.getData()
			filePath = res['rasterFile']
			outputExt = res['extent']
			outputCrs = res['crs']
			importRasterFlag = res['importRaster']
			startDate = res['date']
			tableName = self.tableName
			if (self.assignTime and (startDate !='')):
				tableName += '_' + startDate

			if importRasterFlag and self.DBM:
				filePath = importRasterInDB(DBM=self.DBM,
							  rasterFileName=filePath, tableName=tableName,
							  crs=outputCrs,
							  extension=outputExt)

			aModel = self.TV.model()
			self.TV.clearSelection()

			# replace existing
			notReplaced = True
			rowCount = aModel.rowCount()
			for row in range(rowCount):
				index = aModel.index(row, 0)
				if aModel.data(index)== '':
					# TODO: fix with a better management of new empy table
					# replace empty row with tablename and source
					aModel.setData(index, tableName)
					index = aModel.index(row, 1)
					aModel.setData(index, filePath)
					notReplaced = False
					break

				if aModel.data(index)== tableName:
					index = aModel.index(row, 1)
					# update source
					aModel.setData(index, '')
					notReplaced = False
					break

			if notReplaced:
				# add at the end
				aModel.addRow(rowCount, [tableName,''],False)

			self.rasterAdded.emit(filePath,tableName)

		dlg.accepted.connect(insertRaster)
		dlg.show()

	def deleteRaster(self):
		# get selection
		aModel = self.TV.model()
		aSelection = self.TV.selectionModel().selectedRows()
		indexList = []
		tableName =''
		filePath = ''
		for i, sel in enumerate(aSelection):
			tableName = aModel.datatable[sel.row()][0]
			filePath = aModel.datatable[sel.row()][1]
			deleteRasterFromDB(tableName,self.DBM)
			indexList.append(sel.row())

		for index in indexList:
			aModel.deleteRow(index)

		self.rasterDeleted.emit(filePath,tableName)


