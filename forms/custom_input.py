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

from qgis.PyQt import QtCore, QtGui
from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtWidgets import QWidget, QLabel, QLineEdit, QGridLayout, QComboBox, QListWidget, QPushButton, QCheckBox, \
	QFileDialog, QSpacerItem, QToolButton, QDateTimeEdit, QPlainTextEdit
import os.path as osp
from os import sep as oss

from qgis.core import *
from qgis.gui import *

from ast import literal_eval


class CRSInput(QWidget):

	def __init__(self, objName, labelString, defaultValue, descr=''):
		super(CRSInput, self).__init__()
		self.setObjectName(objName)
		self.setWhatsThis(descr + ' [key: ' + objName + ']')
		self.label = QLabel(labelString)
		self.input = QgsProjectionSelectionWidget()
		self.setValue(defaultValue)

		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.label, 0, 0)
		grid.addWidget(self.input, 0, 1)

		self.setLayout(grid)

	def getValue(self):
		return self.input.crs().postgisSrid()

	def setValue(self, crsCode):
		crs = QgsCoordinateReferenceSystem("POSTGIS:%s"%crsCode)
		self.input.setCrs(crs)

class StringInput(QWidget):
	
	def __init__(self, objName, labelString, defaultValue,descr = '', singleLine = True):
		super(StringInput, self).__init__()
		self.setObjectName(objName)
		self.setWhatsThis(descr+' [key: '+objName+']')
		self.label = QLabel(labelString)
		self.singleLine = singleLine
		if singleLine:
			self.input = QLineEdit()
			self.input.setText(str(defaultValue))
		else:
			self.input = QPlainTextEdit()
			self.input.setPlainText(str(defaultValue))
		
		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.label, 0, 0)
		grid.addWidget(self.input, 0, 1)
		
		self.setLayout(grid)
	
	def getValue(self):
		if self.singleLine:
			return self.input.text()
		else:
			return self.input.toPlainText()

class NumericInput(QWidget):
	def __init__(self, objName, labelString, defaultValue,descr = '', convertTo = 'float'):
		super(NumericInput, self).__init__()
		self.setObjectName(objName)
		self.convertTo = convertTo
		self.setWhatsThis(descr+' [key: '+objName+']')
		self.label = QLabel(labelString)
		self.input = QLineEdit()
		#self.input.setMaxLength(10)
		#validator = QDoubleValidator(1,10,2,self);
		#input.setValidator(validator);
		self.input.setText(str(defaultValue))
		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.label, 0, 0)
		grid.addWidget(self.input, 0, 1)
		
		self.setLayout(grid)
	
	def getValue(self):
		if self.convertTo == 'float':
			return float(self.input.text())
		else:
			return int(self.input.text())
	
	def setTitle(self,newTitle):
		self.label.setText(newTitle)


class DateInput(QWidget):
	def __init__(self, objName, labelString, defaultValue, descr='',timeformat = 'yyyy-MM-dd'):
		super(DateInput, self).__init__()
		self.setObjectName(objName)
		self.defaultValue = defaultValue
		self.setWhatsThis(descr + ' [key: ' + objName + ']')
		#self.label = QLabel(labelString)
		self.timeformat = timeformat

		self.dateField = QDateTimeEdit()
		self.dateField.setDisplayFormat(self.timeformat)
		self.dateField.setCalendarPopup(True)

		today = QDate.currentDate()
		self.dateField.setDate(today)

		# add check box
		self.useDate = QCheckBox()
		self.useDate.setText(labelString)

		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.useDate, 1, 0)
		grid.addWidget(self.dateField, 1, 1)

		self.setLayout(grid)

		# connect checkbox with datetime combo
		self.useDate.stateChanged.connect(self.dateField.setEnabled)
		self.useDate.stateChanged.emit(0)

	def getValue(self):
		date_chosen = ''
		if self.useDate.isChecked():
			date_chosen = self.dateField.dateTime().toString(self.timeformat)

		return date_chosen

	def setValue(self, dateString):
		self.dateField.setDate(QDate.fromString(dateString, self.timeformat))

	def setTitle(self, newTitle):
		self.label.setText(newTitle)



class FieldInput(QWidget):
	def __init__(self, objName, labelString, defaultValue,descr = '',unit = None):
		super(FieldInput, self).__init__()
		self.setObjectName(objName)
		self.defaultValue = defaultValue
		if unit == '': unit = None
		self.unit = unit
		self.setWhatsThis(descr+' [key: '+objName+']')
		self.label = QLabel(labelString)
		self.comboField = QComboBox()
		self.comboUnit = QComboBox()
		self.comboUnit.setMaximumWidth(40)
		self.updateUnitList(unit)
		#validator = QDoubleValidator(1,10,2,self);
		#input.setValidator(validator);
		self.updateFieldList(None,defaultValue)
		self.updateUnitList(unit)
		
		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.label, 1, 0)
		grid.addWidget(self.comboField, 1, 1)
		grid.addWidget(self.comboUnit, 1, 2)
		
		self.setLayout(grid)
	
	def getValue(self):
		value = self.comboField.currentText()
		unit = self.comboUnit.currentText()
		if unit == '-':
			unit = None
			
		if unit == '':
			unit = None
		
		return (value,unit)
		
	def setValue(self,layerPath = None):
		#print 'setValue',layerPath, self.defaultValue,self.unit
		self.updateFieldList(layerPath, self.defaultValue)
		self.updateUnitList(self.unit)
	
	def setTitle(self,newTitle):
		self.label.setText(newTitle)
		
	def updateFieldList(self,layerPath = None, selectedItem= None):
		print('in updateFieldList,',layerPath, selectedItem)
		self.comboField.clear()
		if layerPath is not None:
			# get layer from registry
			vlayer = None
			for l in QgsProject.instance().mapLayers().values():
				if l.source() == layerPath:
					vlayer = l
					break

			if vlayer is None:
				vlayer = QgsVectorLayer(layerPath, "new", "ogr")
			# get layer fields
			self.comboField.addItem('')
			for field in vlayer.dataProvider().fields():
				self.comboField.addItem(field.name())
		
		if selectedItem is not None:
			index = self.comboField.findText(selectedItem)
			#print index
			if index != -1:
				self.comboField.setCurrentIndex(index)
	
	def updateUnitList(self,selectedItem= None):
		self.comboUnit.clear()
		self.comboUnit.addItems(['-','km','m','cm','mm'])
		
		if selectedItem is None:
			self.comboUnit.setEnabled(False)
			selectedItem = '-'
		
		index = self.comboUnit.findText(selectedItem)
		self.comboUnit.setCurrentIndex(index)
			
class MultiListInput(QWidget):
	def __init__(self, objName, labelString, itemArray,descr = ''):
		super(MultiListInput, self).__init__()
		self.setObjectName(objName)
		self.label = QLabel(labelString)
		self.list = QListWidget(self)
		# populate items
		self.list.addItems(itemArray)
		self.list.setSelectionMode(3) # set multiple selection
		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.label, 1, 0)
		grid.addWidget(self.list, 1, 1)
		
		self.setLayout(grid)
		
	def getValue(self):
		res = [ i.text() for i in self.list.selectedItems()]
		return res
	
	def setTitle(self,newTitle):
		self.label.setText(newTitle)
	
	def clearList(self):
		self.list.clear
	
	def addItem(self,item):
		self.list.addItem(item)

	
class ListInput(QWidget):
	def __init__(self, objName, labelString, defaultValue, itemArray,descr = ''):
		super(ListInput, self).__init__()
		self.setObjectName(objName)
		self.setWhatsThis(descr+' [key: '+objName+']')
		self.label = QLabel(labelString)
		self.list = QComboBox(self)
		# populate items
		self.itemDict = literal_eval(itemArray)
			
		toLowerList = []
		for key, item in self.itemDict.items():
			self.list.addItem(key)
			toLowerList.append(item.lower())
		
		# select current value
		defaultText = list(self.itemDict.keys())[toLowerList.index(defaultValue.lower())]
		index = self.list.findText(defaultText)
		
		self.list.setCurrentIndex(index)
			
		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.label, 1, 0)
		grid.addWidget(self.list, 1, 1)
		
		self.setLayout(grid)
		
	def getValue(self):
		# return the key of the dictionary
		selKey = self.list.currentText()
		return list(self.itemDict.values())[list(self.itemDict.keys()).index(selKey)]
		
	def setTitle(self,newTitle):
		self.label.setText(newTitle)
	
	def clearList(self):
		self.list.clear
	
	def addItem(self,item):
		self.list.addItem(item)
	
class CheckInput(QWidget):
	def __init__(self,objName, labelString, defaultValue,descr = ''):
		super(CheckInput, self).__init__()
		self.setObjectName(objName)
		self.setWhatsThis(descr+' [key: '+objName+']')
		self.input = QCheckBox(labelString)
		val = True if defaultValue in ['True',True,1,'1'] else False
		self.input.setChecked(val)
		#self.label = QtGui.QLabel(labelString)
		
		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.input, 1, 0)
		#grid.addWidget(self.label, 1, 1)
		
		self.setLayout(grid)
		
	def getValue(self):
		return self.input.isChecked()
	
	def setTitle(self,newTitle):
		#self.label.setText(newTitle)
		self.input.setText(newTitle)
		
class FileOutput(QWidget):
	def __init__(self, objName, labelString, defaultValue, type,descr = ''):
		super(FileOutput, self).__init__()
		self.setObjectName(objName)
		self.setWhatsThis(descr+' [key: '+objName+']')
		self.label = QLabel(labelString)
		self.input = QLineEdit()
		self.button = QToolButton()
		self.button.setToolButtonStyle(1)
		self.button.setText('...')
		self.input.setText(str(defaultValue))
		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.label, 1, 0)
		grid.addWidget(self.input, 1, 1)
		grid.addWidget(self.button, 1, 3)
		
		self.setLayout(grid)
		
		# link action
		if (type == '*.mat'): self.button.clicked.connect(lambda: self.saveFile(filter='Matlab (*.mat)'))
		if (type == '*.gpkg'): self.button.clicked.connect(lambda: self.saveFile(filter='Geopackage (*.gpkg)'))
		if (type == '*.idb'): self.button.clicked.connect(lambda: self.saveFile(filter='IdrAgra DB (*.idb)'))

	def getValue(self):
		return self.input.text()
	
	def setTitle(self,newTitle):
		self.label.setText(newTitle)
		
	def saveFile(self, filter='All (*.*)'):
		outputFile = QFileDialog.getSaveFileName(None, self.label.text(), '', filter)
		if not outputFile:
			return
		else:
			# update input box
			self.input.setText(outputFile[0])

class FileInput(QWidget):
	
	def __init__(self, objName, labelString, defaultValue, type,descr = '',sourceList = {}):
		super(FileInput, self).__init__()
		self.setObjectName(objName)
		self.setWhatsThis(descr+' [key: '+objName+']')
		self.label = QLabel(labelString)
		self.input = QComboBox()
		self.input.setEditable(True) # enable user to edit the text
		self.button = QToolButton()
		self.button.setToolButtonStyle(1)
		self.button.setText('...')
		#~ self.input.setText(str(defaultValue))
		grid = QGridLayout()
		grid.setSpacing(10)
		grid.addWidget(self.label, 1, 0)
		grid.addWidget(self.input, 1, 1)
		grid.addWidget(self.button, 1, 3)
		
		self.setLayout(grid)
	
		self.SOURCELIST = {} # keys= layersource, values = layername
		
		listType = type[1:]
		listType2 = None
		if listType == '.dbf':
			listType2 = '.shp' # special case for dbf file connected with shapefile
		
		for source,name in sourceList.items():
			#print('source:',source,'target type:',type[1:])
			
			if source.endswith(listType):
				#print('--> ok')
				self.SOURCELIST[source[:-4]+listType] = name
			
			if listType2:
				if source.endswith(listType2):
					self.SOURCELIST[source[:-4]+listType] = name
				
			
		self.updateLayerList()
		
		# set default value
		self.input.lineEdit().setText(str(defaultValue))
		
		# link action
		if (type == '*.tif'): self.button.clicked.connect(lambda: self.openFile(filter='Geotiff (*.tif)'))
		if (type == '*.shp'): self.button.clicked.connect(lambda: self.openFile(filter='ESRI shapefile (*.shp)'))
		if (type == '*.dbf'): self.button.clicked.connect(lambda: self.openFile(filter='database (*.dbf)'))
		if (type == '*.mat'): self.button.clicked.connect(lambda: self.openFile(filter='Matlab (*.mat)'))
		if (type == '*.txt'): self.button.clicked.connect(lambda: self.openFile(filter='Text file (*.txt)'))
		if (type == '*.gpkg'): self.button.clicked.connect(lambda: self.openFile(filter='Geopackage file (*.gpkg)'))
		if (type == '*.idb'): self.button.clicked.connect(lambda: self.openFile(filter='IdrAgra DB (*.idb)'))
		if (type == 'None'): self.button.clicked.connect(lambda: self.openFile(filter=None))
		
	def updateLayerList(self):
		self.input.clear()
		layNames = list(self.SOURCELIST.values())
		for name in layNames:
			self.input.addItem(name)
		
	def getValue(self):
		layName = self.input.currentText()
		#print 'in LayerInput::getValue',layName
		value = None
		# if it is in SOURCELIST
		layNames = list(self.SOURCELIST.values())
		if layName in layNames:
			value = list(self.SOURCELIST.keys())[layNames.index(layName)]
		else:
			# it doesn't make other control to set process adaptable
			value = layName
				
		return value
	
	def setTitle(self,newTitle):
		self.label.setText(newTitle)
		
	def openFile(self, filter='All (*.*)'):
		if filter == None:
			# open directory
			inputFile = QFileDialog.getExistingDirectory(None, self.label.text(), '')
			if inputFile =='': inputFile = None
			if not inputFile:
				return
			else:
				# update input box
				self.input.lineEdit().setText(inputFile+oss)
		else:
			inputFile = QFileDialog.getOpenFileName(None, self.label.text(), '', filter)
			inputFile = inputFile[0]
			if inputFile =='': inputFile = None
			if not inputFile:
				return
			else:
				# update input box
				self.input.lineEdit().setText(inputFile)