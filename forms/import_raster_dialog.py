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

from qgis.PyQt.QtWidgets import QDialog, QToolBox, QWidget, QVBoxLayout, QFileDialog, QListWidgetItem, QToolButton, \
	QSpinBox, QCalendarWidget, QMainWindow

import os

from qgis._core import QgsProviderRegistry



class ImportRasterDialog(QMainWindow):
	closed = pyqtSignal()
	accepted = pyqtSignal()
	rejected = pyqtSignal()

	def __init__(self, iface=None, setDate = False):
		QMainWindow.__init__(self, iface.mainWindow())
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'import_raster_dialog.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle('IdragraTools')

		self.RASTERPATH_TE.setFilter(QgsProviderRegistry.instance().fileRasterFilters())

		self.OUTPUTEXT.setMapCanvas(iface.mapCanvas())

		self.DATE_LB.setVisible(setDate)
		self.DATE_DT.setVisible(setDate)

		self.IMPORT_CB.stateChanged.connect(self.enableOptions)

		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		#QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
		#QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
		QMetaObject.connectSlotsByName(self)
		
	def closeEvent(self, event):
		self.closed.emit()

	def accept(self):
		self.close()
		self.accepted.emit()
		return 1

	def reject(self):
		self.close()
		return 0

	def enableOptions(self,state):
		if state==0:
			self.OUTPUTEXT.setEnabled(False)
		else:
			self.OUTPUTEXT.setEnabled(True)
	
	def getData(self):
		# get selected vars
		dtmFile = self.RASTERPATH_TE.filePath()
		dtmExtent = self.OUTPUTEXT.outputExtent()
		crs = self.OUTPUTEXT.outputCrs().postgisSrid()
		#print('dtmExtent',dtmExtent)
		dt = self.DATE_DT.date().toString('yyyyMMdd')
		importRaster = False
		if self.IMPORT_CB.isChecked():
			importRaster = True
		
		return {'rasterFile':dtmFile, 'extent':dtmExtent, 'crs':crs,'importRaster':importRaster,'date':dt}
