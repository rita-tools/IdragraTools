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
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic

class ArrayTableModel(QAbstractTableModel): 
	def __init__(self, parent=None, data = [], header = []): 
		super(ArrayTableModel, self).__init__()
		# list of tuple, each tuple is a record of the table

		self.dataheader = header
		if len(data) == 0: self.datatable = [['']*len(header)]  # add empty row
		else: self.datatable = data

		self.editableColumnList = list(range(0,len(header)))
		
	def update(self, dataIn,headerIn = None):
		self.datatable = dataIn
		self.dataheader = headerIn

	def rowCount(self, parent=QModelIndex()):
		#print 'rowCount',len(self.datatable) 
		return len(self.datatable) 

	def columnCount(self, parent=QModelIndex()):
		if self.rowCount()>0:
			#print 'colCount',self.datatable[0]
			return len(self.datatable[0]) 
		else:
			return 0

	def addEmptyRow(self, index = -1,silent = False):
		if index>0:
			self.datatable.insert(index, ['']*self.columnCount())
		else:
			self.datatable.append(['']*self.columnCount())

		if not silent: self.layoutChanged.emit()

	def addRow(self, index=-1, rowData = [], silent=False):
		numData = len(rowData)
		if numData<self.columnCount(): rowData += ['']* (self.columnCount()-numData)

		if index >= 0:
			self.datatable.insert(index, rowData)
		else:
			self.datatable.append( rowData)

		if not silent: self.layoutChanged.emit()

	def deleteRow(self,index = -1, silent = False):
		if index>=0:
			self.datatable.pop(index)
			if not silent: self.layoutChanged.emit()

	def moveRow(self,index, step, silent = False):
		if (index+step)<0: return
		if (index+step)>(len(self.datatable)-1): return

		# TODO: check position
		# get element
		dummy = self.datatable[index]
		self.deleteRow(index,True)
		self.addRow(index+step, dummy, True)

		if not silent: self.layoutChanged.emit()

	def getColumnValue(self, columnIndex):
		res = []
		
		if self.columnCount()==0:
			return res
			
		if ((columnIndex >=0) and (columnIndex < self.columnCount())):
			for val in self.datatable:
				res.append(val[columnIndex])
				
		return res
			

	def data(self, index, role=Qt.DisplayRole):
		i = index.row()
		j = index.column()
		if role == Qt.DisplayRole:
			return self.datatable[i][j]
	
	def setData(self, index, value, role=Qt.EditRole):
		i = index.row()
		j = index.column()
		if role == Qt.EditRole:
			self.datatable[i][j] = value
			self.dataChanged.emit(index, index)
			return True
		else:
			return False
			
	def setEditableColumn(self,colList):
		self.editableColumnList = colList
		
	def flags(self, index):  # Qt was imported from PyQt4.QtCore
		if index.column() in self.editableColumnList:
			return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
		else:
			return Qt.ItemIsEnabled | Qt.ItemIsSelectable
		
	def headerData(self, section, orientation, role=Qt.DisplayRole):
		if role == Qt.DisplayRole and orientation == Qt.Horizontal:
			return self.dataheader[section]
			
		return QAbstractTableModel.headerData(self, section, orientation, role)
