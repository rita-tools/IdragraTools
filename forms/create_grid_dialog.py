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

from qgis.PyQt import uic

from qgis.PyQt.QtWidgets import QDialog,QToolBox,QWidget,QVBoxLayout,QFileDialog,QListWidgetItem

import os

class CreateGridDialog(QDialog):
	closed = pyqtSignal()
	
	FILELIST = {}
	VARLIST = {}
	FUNLIST = {}
	
	def __init__(self, parent=None, title = 'IdragraTools'):
		QDialog.__init__(self, parent.mainWindow())
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'create_grid_dialog.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle(title)
		self.canvas = parent.mapCanvas()
		self.EXTENT_GRP.setMapCanvas(self.canvas)

		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		#QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
		#QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
		QMetaObject.connectSlotsByName(self)
		
	def closeEvent(self, event):
		self.closed.emit()
		
	
	def getData(self):
		# get selected vars
		cell_size = self.CELLSIZE_SB.value()

		grid_extent = self.EXTENT_GRP.outputExtent()
		grid_crs = self.EXTENT_GRP.outputCrs()

		use_integer = self.USEINT_CB.isChecked()
		save_edits = self.SAVEEDITS_CB.isChecked()

		return {'cell_size':cell_size, 'grid_extent':grid_extent,'grid_crs':grid_crs,
				'save_edits':save_edits,'use_integer':use_integer}
