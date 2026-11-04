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
from qgis.gui import *

from IdragraTools.qt_compat import QAction

#from QWaDiS.layerforms.utils import *

from IdragraTools.layerforms.utils import toFloat, parseString, toInt,updateListItems

from tools.array_table_model import ArrayTableModel


def formOpen(dialog,layerid,featureid):
	global myDialog
	myDialog = dialog
	global layer
	layer = layerid
	global feature
	feature = featureid
		
	tr = qgis.utils.plugins['IdragraTools'].tr
	getIdNameDict = qgis.utils.plugins['IdragraTools'].getIdNameDict
	
	# prepare a list of widget to enable/disable
	global objToBeEnabledList
	objToBeEnabledList = []

	global imageLBL
	imageLBL = myDialog.findChild(QLabel, 'IMAGE_LABEL')

	global croplistLE
	croplistLE = myDialog.findChild(QLineEdit, 'croplist')
	croplistLE.setHidden(True)
	croplistLE.textChanged.connect(updatePlot)

	# set up label image

	# get vertex from geometry TODO
	#~ geom = feature.geometry()
	
	
	#~ if geom:
		#~ vertices = geom.asPolyline()
		#~ n = len(vertices)
		#~ x1 = vertices[0].x()
		#~ y1 = vertices[0].y()
		#~ x2 = vertices[n-1].x()
		#~ y2 = vertices[n-1].y()
		
		#~ # populate combos with values
		#~ setupCombo('inlet_node',getIdNameDictXY('idr_nodes',x1,y1))
		#~ setupCombo('outlet_node',getIdNameDictXY('idr_nodes',x2,y2))
	#~ else:
	global cropDict
	cropDict = getIdNameDict('idr_crop_types')
	# enable/disable edit mode
	setEditMode(layer.isEditable())
		
	# connect start edit button to setEditMode to get edit tool pressed
	global EDIT_BTN
	EDIT_BTN = myDialog.findChild(QPushButton, 'EDIT_BTN')
	# for some reason, forms are initialized twice ...
	if EDIT_BTN.receivers(EDIT_BTN.clicked) == 0:
		EDIT_BTN.clicked.connect(showEditDialog)

	#qgis.utils.plugins['idragra4qgis'].iface.actionToggleEditing().toggled[bool].connect(setEditMode)
	try:
		parentForm = myDialog.window() 
		act = parentForm.findChild(QAction,'mActionToggleEditing')
		if act: act.toggled[bool].connect(setEditMode)
	except Exception as e:
		print('error: %s'%str(e))

def updatePlot(cropIdsText):
	cropIds = cropIdsText.split(' ')
	cropIds = [str(x) for x in cropIds]
	w = imageLBL.width()
	h = imageLBL.height()
	screen = QApplication.primaryScreen()
	print('w', w)
	print('h', h)
	print('screen',screen.size())
	print('dpi',screen.logicalDotsPerInch())
	dpi = screen.logicalDotsPerInch()
	w=w/dpi
	h = 1+len(cropIds)
	pixmap = qgis.utils.plugins['IdragraTools'].makeDistroPlot(cropIds,w,h)

	# imageLBL.setPixmap(pixmap.scaled(w,h,Qt.IgnoreAspectRatio))
	imageLBL.setPixmap(pixmap.scaled(0.9*w*dpi,0.9*h*dpi,Qt.KeepAspectRatio,Qt.SmoothTransformation))


def showEditDialog():
	tr = qgis.utils.plugins['IdragraTools'].tr
	# extract data
	t = parseString(croplistLE.text(),' ',toInt)
	# replace data with names
	keys = list(cropDict.keys())
	values = list(cropDict.values())
	data = []
	for item in t:
		if item not in values:
			item = ''

		data.append(keys[values.index(item)])

	data = list(zip(data))
	data = list(map(list, data))
	header = [tr('Crop')]
	# make a dialog
	from IdragraTools.layerforms.table_dialog import TableDialog
	dlg = TableDialog(parent=myDialog, title='View/edit table')
	dlg.setEditMode(layer.isEditable())
	# make the model with data
	global aModel
	aModel = ArrayTableModel(dlg, data, header)

	if not layer.isEditable():
		aModel.setEditableColumn([])

	dlg.TV.setModel(aModel)

	dlg.setDelegate(column=1, choices=cropDict)

	# set size from qgis habits
	dlg.resize(0.5 * myDialog.geometry().width(), myDialog.geometry().height())
	dlg.finished.connect(updateTableValues)
	dlg.show()

def updateTableValues():
	if layer.isEditable():
		valueList = list(map(str,aModel.getColumnValue(0)))
		codeList = []
		for v in valueList:
			if v in list(cropDict.keys()):
				codeList.append(str(cropDict[v]))
			else:
				print('Cannot parse',v)

		croplistLE.setText(' '.join(codeList))


def setupListWidget(attrName,allItems):
	LE = myDialog.findChild(QLineEdit,attrName)
	cropList = LE.text().split(' ')
	cropNameList = []
	for c in cropList:
		for k,v in allItems.items():
			if str(v) == c:
				cropNameList.append(k)
			
	LW = myDialog.findChild(QListWidget,attrName+'_LW')
	objToBeEnabledList.append(LW)
	updateListItems(LW,cropNameList)
	
	LE.setHidden(True)
	#CB.currentIndexChanged[str].connect(lambda txt: updateLineEdit(txt,allItems,LE))
	#updateSelected(LW, LE,allItems)
	
def setEditMode(mode):
	try:
		for obj in objToBeEnabledList:
			obj.setEnabled(mode)
	except Exception as e:
		print('error: %s'%str(e))
		
def validate():
	# Make sure that the name field isn't empty.
	myDialog.accept()

