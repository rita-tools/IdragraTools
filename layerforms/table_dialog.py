# -*- coding: utf-8 -*-

"""
/***************************************************************************
 IdrAgraTools
 A QGIS plugin to manage water demand simulation with IdrAgra model
 The plugin shares user interfaces and tools to manage water in irrigation districts
-------------------
		begin				: 2020-12-01
		copyright			: (C) 2020 by Enrico A. Chiaradia
		email					: enrico.chiaradia@unimi.it
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

import os

from qgis.PyQt import QtGui, uic
from qgis.PyQt.QtCore import QMetaObject, Qt, QVariant
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QTableView, QPushButton, QAbstractItemView, QItemDelegate, QComboBox, \
	QApplication, QStyleOptionComboBox, QStyle, QHeaderView


# credits: https://stackoverflow.com/questions/18068439/pyqt-simplest-working-example-of-a-combobox-inside-qtableview/48055193
class ComboBoxDelegate(QItemDelegate):
	def __init__(self, parent, itemsDict):
		super().__init__(parent)
		self.itemsDict = itemsDict
		self.items = list(self.itemsDict.keys())
		self.codes =  list(self.itemsDict.values())

	def createEditor(self, parent, option, index):
		self.editor = QComboBox(parent)
		self.editor.addItems(self.items)
		return self.editor

	def paint(self, painter, option, index):
		value = index.data(Qt.DisplayRole)
		style = QApplication.style()
		opt = QStyleOptionComboBox()
		opt.text = str(value)
		opt.rect = option.rect
		style.drawComplexControl(QStyle.CC_ComboBox, opt, painter)
		QItemDelegate.paint(self, painter, option, index)

	def setEditorData(self, editor, index):
		value = index.data(Qt.DisplayRole)
		if value in self.items:
			num = self.items.index(value)
			editor.setCurrentIndex(num)

	def setModelData(self, editor, model, index):
		value = editor.currentText()
		model.setData(index, value,Qt.EditRole)

	def updateEditorGeometry(self, editor, option, index):
		editor.setGeometry(option.rect)

class TableDialog(QDialog):
	def __init__(self, parent=None, title = ''):
		QDialog.__init__(self,parent)

		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'table_dialog.ui'))
		uic.loadUi(uiFilePath, self)
		
		self.setWindowTitle(title)
		self.TV.setSelectionMode(QAbstractItemView.MultiSelection)
		self.TV.setSelectionBehavior(QAbstractItemView.SelectRows )
		self.TV.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)


		self.ADDBTN.clicked.connect(self.addRow)
		self.DELBTN.clicked.connect(self.delRow)
		self.UPBTN.clicked.connect(self.moveUp)
		self.DOWNBTN.clicked.connect(self.moveDown)

		self.cbDel = None

		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		QMetaObject.connectSlotsByName(self)

	def hideControls(self, flag = True):
		self.setEditMode(False)
		self.ADDBTN.setHidden(flag)
		self.DELBTN.setHidden(flag)
		self.UPBTN.setHidden(flag)
		self.DOWNBTN.setHidden(flag)

	def setEditMode(self, flag = False):
		self.ADDBTN.setEnabled(flag)
		self.DELBTN.setEnabled(flag)
		self.UPBTN.setEnabled(flag)
		self.DOWNBTN.setEnabled(flag)

	def addRow(self):
		# get selected row
		aSelection = self.TV.selectionModel().selectedRows()
		i=0
		nRecs =len(aSelection)
		indexList = []
		for i,sel in enumerate(aSelection):
			indexList.append(sel.row())

		if len(indexList)>0: index = min(indexList)
		else: index = 0

		aModel = self.TV.model()
		if index ==0: nRecs=1

		self.TV.clearSelection()

		for j in range(nRecs):
			print('add row at',index)
			aModel.addEmptyRow(index) # TODO check addRow
			#self.TV.selectRow(index)
			index+=1

		# update delegate
		if self.cbDel:
			self.TV.setItemDelegateForColumn(0, self.cbDel)

	def delRow(self):
		# get selected row
		aSelection = self.TV.selectionModel().selectedRows()
		indexList = []
		for i,sel in enumerate(aSelection):
			indexList.append(sel.row())

		# start from the lower in the table
		indexList.sort(reverse=True)

		aModel = self.TV.model()
		for index in indexList:
			aModel.deleteRow(index)

	def moveUp(self):
		# get selected row
		aSelection = self.TV.selectionModel().selectedRows()
		indexList = []
		for i, sel in enumerate(aSelection):
			indexList.append(sel.row())

		self.TV.clearSelection()
		# start from the lower in the table
		indexList.sort(reverse=False)

		aModel = self.TV.model()

		for index in indexList:
			aModel.moveRow(index,-1)
			# and select
			next_index = aModel.index(index - 1, 0)
			#self.TV.setCurrentIndex(next_index)
			self.TV.selectRow(index - 1)

	def moveDown(self):
		# get selected row
		aSelection = self.TV.selectionModel().selectedRows()
		indexList = []
		for i, sel in enumerate(aSelection):
			indexList.append(sel.row())

		self.TV.clearSelection()
		# start from the lower in the table
		indexList.sort(reverse=True)

		aModel = self.TV.model()
		for index in indexList:
			aModel.moveRow(index, 1)
			# and select
			next_index = aModel.index(index + 1, 0)
			#self.TV.setCurrentIndex(next_index)
			self.TV.selectRow(index + 1)


	def setModel(self, dataModel):
		pass

	def setDelegate(self,column,choices):
		self.cbDel = ComboBoxDelegate(self, choices)
		self.TV.setItemDelegateForColumn(0,self.cbDel)
		# TODO: seems not working
		# make combo boxes editable with a single-click:
		# for row in range(self.TV.model().rowCount()):
		# 	self.TV.openPersistentEditor(self.TV.model().index(row, column))
		
if __name__ == '__console__':
	pass