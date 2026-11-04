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

from IdragraTools.layerforms.utils import *

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
	
	setupCombo('inlet_node',getIdNameDict('idr_nodes',filterName='node_type',filterValues=[3,'3']))
	setupCombo('outlet_node', getIdNameDict('idr_nodes',filterName='node_type',filterValues=[12,'12']))

	# enable/disable edit mode
	setEditMode(layer.isEditable())
		
	# connect start edit button to setEditMode to get edit tool pressed	
	#qgis.utils.plugins['IdragraTools'].iface.actionToggleEditing().toggled[bool].connect(setEditMode)
	try:
		parentForm = myDialog.window() 
		act = parentForm.findChild(QAction,'mActionToggleEditing')
		if act: act.toggled[bool].connect(setEditMode)
	except Exception as e:
		print('error: %s'%str(e))


def setupCombo(attrName,allItems):
	CB = myDialog.findChild(QComboBox,attrName+'_CB')
	objToBeEnabledList.append(CB)
	updateComboItems(CB,allItems)
	LE = myDialog.findChild(QLineEdit,attrName)
	LE.setHidden(True)
	CB.currentIndexChanged[str].connect(lambda txt: updateLineEdit(txt,allItems,LE))
	updateSelected(CB, LE,allItems)
	
def setEditMode(mode):
	try:
		for obj in objToBeEnabledList:
			obj.setEnabled(mode)
	except Exception as e:
		print('error: %s'%str(e))
		
def validate():
	# Make sure that the name field isn't empty.
	myDialog.accept()

