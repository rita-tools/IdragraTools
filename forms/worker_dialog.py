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

import time

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *

from qgis.PyQt import uic

from qgis.PyQt.QtWidgets import QDialog,QToolBox,QWidget,QVBoxLayout,QApplication
	
#qgis import
from qgis.core import *
from qgis.gui import *
#other
import os
import sys

from .custom_input import *

class WorkerDialog(QDialog):
	closed = pyqtSignal()
	
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'worker_dialog.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle('IdrAgraTools')
		
		self.PROGBAR.destroyed.connect(self.closeEvent)
		self.OK_BTN.clicked.connect(self.close)
		
	def closeEvent(self,event):
		#~ print('closeEvent')
		self.closed.emit()
	
	@QtCore.pyqtSlot(object)
	def setPercentage(self,val):
		self.PROGBAR.setValue(int(val))
	
	@QtCore.pyqtSlot(str,str)
	def setText(self, text,col= None):
		if text != '':
			if col is None:
				text = '%s<br>'%text
			else:
				execTime = time.strftime("%H:%M:%S")
				text = '<font color="%s">%s - %s</font><br>' %(col,execTime,text)
			#~ htmlText = self._console.toHtml()
			#~ htmlText += text
			#~ self._console.setHtml(htmlText)
			textCursor = self.REP_TB.textCursor()
			textCursor.movePosition(QTextCursor.End)
			self.REP_TB.setTextCursor(textCursor)
			self.REP_TB.insertHtml(text)
			# scroll to the end
			sb = self.REP_TB.verticalScrollBar()
			sb.setValue(sb.maximum())
	
	@QtCore.pyqtSlot()
	def enableOK(self):
		self.OK_BTN.setEnabled(True)
		
	def keyPressEvent(self,event):
		itemList = []
		if (event==QKeySequence.Copy):
			repText = self.REP_TB.toHtml()
			QApplication.clipboard().setText(repText)
		
		