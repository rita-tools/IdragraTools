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

from qgis.PyQt.QtWidgets import *

from IdragraTools.qt_compat import QAction

from IdragraTools.layerforms.utils import *
from IdragraTools.tools.array_table_model import ArrayTableModel

def formOpen(dialog,layerid,featureid):
	global myDialog
	myDialog = dialog
	global layer
	layer = layerid
	global feature
	feature = featureid
	
	# option list to update
	tr = qgis.utils.plugins['IdragraTools'].tr
	#global allItems
	ph_rItems = {tr('Day-neutral plants'):0,
				 tr('Long-day plants'):1,
				 tr('Short-day plants'):2}

	cl_cnItems = {tr('Fallow'):1,
				  tr('Row crops'):2,
				  tr('Small grains'):3,
				  tr('Close-seeded or broadcast legumes or rotation'):4,
				  tr('Meadow - continuous grass, protected from grazing and generally mowed for hay'):5,
				  tr('Woods - grass combination (orchard or tree farm)'):6}
	
	# elements to hide
	ph_rLE = myDialog.findChild(QLineEdit,'ph_r')
	cl_cnLE = myDialog.findChild(QLineEdit, 'cl_cn')

	gddLE = myDialog.findChild(QLineEdit,'gdd')
	kcbLE = myDialog.findChild(QLineEdit,'kcb')
	laiLE = myDialog.findChild(QLineEdit,'lai')
	hcLE = myDialog.findChild(QLineEdit,'hc')
	srLE = myDialog.findChild(QLineEdit,'sr')

	ph_rLE.setHidden(True)
	cl_cnLE.setHidden(True)

	gddLE.setHidden(True)
	kcbLE.setHidden(True)
	laiLE.setHidden(True)
	hcLE.setHidden(True)
	srLE.setHidden(True)

	global objToBeEnabledList
	objToBeEnabledList = []

	# combo to populate
	ph_rCB = myDialog.findChild(QComboBox,'ph_r_CB')
	objToBeEnabledList.append(ph_rCB)
	
	updateComboItems(ph_rCB,ph_rItems)
	ph_rCB.currentIndexChanged[str].connect(lambda txt: updateLineEdit(txt,ph_rItems,ph_rLE))
	updateSelected(ph_rCB, ph_rLE,ph_rItems)

	cl_cnCB = myDialog.findChild(QComboBox, 'cl_cn_CB')
	objToBeEnabledList.append(cl_cnCB)

	updateComboItems(cl_cnCB, cl_cnItems)
	cl_cnCB.currentIndexChanged[str].connect(lambda txt: updateLineEdit(txt, cl_cnItems, cl_cnLE))
	updateSelected(cl_cnCB, cl_cnLE, cl_cnItems)
	
	setEditMode(layer.isEditable())
		
	# connect start edit button to setEditMode to get edit tool pressed	
	#qgis.utils.plugins['QWaDiS'].iface.actionToggleEditing().toggled[bool].connect(setEditMode)
	try:
		parentForm = myDialog.window() 
		act = parentForm.findChild(QAction,'mActionToggleEditing')
		if act: act.toggled[bool].connect(setEditMode)
	except Exception as e:
		print('error: %s'%str(e))
	
	
	# button to activate
	EDIT_BTN = myDialog.findChild(QPushButton,'EDIT_BTN')
	# for some reason, forms are initialized twice ...
	if EDIT_BTN.receivers(EDIT_BTN.clicked)==0:
		EDIT_BTN.clicked.connect(showEditDialog)
		
def setEditMode(mode):
	try:
		for obj in objToBeEnabledList:
			obj.setEnabled(mode)
	except Exception as e:
		print('error: %s'%str(e))
		
def showEditDialog():
	tr = qgis.utils.plugins['IdragraTools'].tr
	# extract data
	gdd = parseString(myDialog.findChild(QLineEdit,'gdd').text(),' ',toSpecialInt)
	kcb = parseString(myDialog.findChild(QLineEdit,'kcb').text())
	lai = parseString(myDialog.findChild(QLineEdit,'lai').text())
	hc = parseString(myDialog.findChild(QLineEdit,'hc').text())
	sr = parseString(myDialog.findChild(QLineEdit, 'sr').text())
	
	data = list(zip(gdd, kcb,lai,hc,sr))
	data = list(map(list, data))
	if len(data)==0:
		data = [['','','','','']]

	header = [tr('Growing degree days'),tr('Crop coefficient'),tr('Leaf area index'),tr('Crop heigth'),tr('Root depth')]
	# make a dialog
	from IdragraTools.layerforms.table_dialog import TableDialog
	dlg = TableDialog(parent=myDialog,title = 'View/edit table')
	dlg.setEditMode(layer.isEditable())
	# make the model with data
	global aModel
	aModel = ArrayTableModel(dlg,data,header)
	
	if not layer.isEditable():
		aModel.setEditableColumn([])
		
	dlg.TV.setModel(aModel)
	# set size from qgis habits
	dlg.resize(0.8*myDialog.geometry().width(),0.5*myDialog.geometry().height())
	#dlg.finished.connect(updateTableValues)

	dlg.show()
	result = dlg.exec()
	# See if OK was pressed
	res = []
	if result == 1:
		updateTableValues()

def updateTableValues():
	if layer.isEditable():
		myDialog.changeAttribute('gdd',' '.join(list(map(toSpecialInt,aModel.getColumnValue(0)))))
		myDialog.changeAttribute('kcb', ' '.join(list(map(toSpecialFloat, aModel.getColumnValue(1)))))
		myDialog.changeAttribute('lai', ' '.join(list(map(toSpecialFloat, aModel.getColumnValue(2)))))
		myDialog.changeAttribute('hc', ' '.join(list(map(toSpecialFloat, aModel.getColumnValue(3)))))
		myDialog.changeAttribute('sr', ' '.join(list(map(toSpecialFloat, aModel.getColumnValue(4)))))

if __name__ == '__console__': 
	pass
