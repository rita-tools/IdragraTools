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

from qgis.PyQt.QtWidgets import QMessageBox
from qgis.gui import *

def toSpecialInt(n):
	try:
		return str(int(float(n)))
	except:
		return '*'

def toSpecialFloat(n):
	try:
		return str(float(n))
	except:
		return '*'

def toFloat(n):
	try:
		return float(n)
	except:
		return 0.0

def toInt(n):
	try:
		return int(n)
	except:
		print('unable to parse',n)
		return 0

def toStr(n):
	try:
		return str(n)
	except:
		return ''



def parseString(dataString,sep=' ',cast = toSpecialFloat):
	valList = []
	if (dataString and dataString!='NULL'):
		tempValList = dataString.split(sep)
		if tempValList:
			valList = list(map(cast, tempValList))
			
	return valList

def updateListItems(listBox,allItems):
	# update only if it is empty
	if listBox is not None:
		listBox.clear()
		listBox.addItems(allItems)
		
def updateComboItems(comboBox,allItems):
	# update only if it is empty
	if comboBox.count()==0:
		comboBox.addItems(allItems.keys())
	
def updateSelectedOLD(comboBox, lineEdit, allItems):
	val = lineEdit.text()
	if val != '':
		try:
			index = int(val)
			if index >= 0:
				comboBox.setCurrentIndex(index)
		except Exception as e:
			print('error: %s'%str(e))

def updateSelected(comboBox, lineEdit, allItems):
	val = lineEdit.text()
	if val in ['','NULL']:
		comboBox.setCurrentIndex(0)
	else:
		try:
			val = int(val)
			if val >= 0:
				index = 0
				for key, itemVal in allItems.items():
					if itemVal == val:
						comboBox.setCurrentIndex(index)
						break
					index+=1
					
		except Exception as e:
			print('error: %s'%str(e))
		

def updateLineEdit(txt, allItems,lineEdit):
	if txt in allItems.keys():
		id = allItems[txt]
		lineEdit.setText(str(id))
		
def toDo():
	msg = QMessageBox()
	msg.setIcon(QMessageBox.Information)
	msg.setText('This function is not implemented')
	msg.setInformativeText('This function will be deleted or developed in the next release ...')
	msg.setWindowTitle('QWaDiS')
	msg.setStandardButtons(QMessageBox.Ok)
	msg.exec_()