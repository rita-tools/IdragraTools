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

from IdragraTools.layerforms.utils import *
from IdragraTools.tools.array_table_model import ArrayTableModel

def formOpen(dialog,layerid,featureid):
	global myDialog
	myDialog = dialog
	global layer
	layer = layerid
	global feature
	feature = featureid
	
	global irrTimeLE
	global irrFractLE
	
	#global irrTimeLE
	irrTimeLE = myDialog.findChild(QLineEdit,'irr_time')
	irrFractLE = myDialog.findChild(QLineEdit,'irr_fraction')
	
	irrTimeLE.setHidden(True)
	irrFractLE.setHidden(True)
	
	global EDIT_BTN
	EDIT_BTN = myDialog.findChild(QPushButton,'EDIT_BTN')
	# for some reason, forms are initialized twice ...
	if EDIT_BTN.receivers(EDIT_BTN.clicked)==0:
		EDIT_BTN.clicked.connect(showEditDialog)
	

	
def showEditDialog():
	tr = qgis.utils.plugins['IdragraTools'].tr
	# extract data
	t = parseString(irrTimeLE.text(),' ',toSpecialInt)
	if len(t) ==0: t = list(range(1,25))
		
	v = parseString(irrFractLE.text(),' ',toSpecialFloat)
	if len(v) ==0: v = [0]*24
	
	data = list(zip(t, v))
	data = list(map(list, data))
	header = [tr('Hour'),tr('Fraction')]
	# make a dialog
	from IdragraTools.layerforms.table_dialog import TableDialog
	dlg = TableDialog(parent=myDialog,title = 'View/edit table')
	# make the model with data
	global aModel
	aModel = ArrayTableModel(dlg,data,header)

	dlg.hideControls()
	
	if not layer.isEditable():
		aModel.setEditableColumn([])
		
	dlg.TV.setModel(aModel)
	# set size from qgis habits
	dlg.resize(0.5*myDialog.geometry().width(),myDialog.geometry().height())
	dlg.show()
	result = dlg.exec_()
	# See if OK was pressed
	res = []
	if result == 1:
		updateTableValues()


def updateTableValues():
	if layer.isEditable():
		myDialog.changeAttribute('irr_time',' '.join(list(map(toSpecialInt,aModel.getColumnValue(0)))))
		myDialog.changeAttribute('irr_fraction', ' '.join(list(map(toSpecialFloat, aModel.getColumnValue(1)))))

if __name__ == '__console__': 
	pass