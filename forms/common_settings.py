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
	
#qgis import
from qgis.core import *
from qgis.gui import *
#other
import os
import sys
import glob

from .custom_input import *

#~ uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'project_dialog.ui'))
#~ print('uiFilePath: %s'%uiFilePath)
#~ FormClass = uic.loadUiType(uiFilePath)[0]

class CommonSettings(QDialog):
	closed = pyqtSignal()

	def __init__(self, parent=None):
		QDialog.__init__(self, parent.mainWindow())
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'common_settings.ui'))
		uic.loadUi(uiFilePath, self)

		### set path to executable
		s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
		path2Idragra = s.value('idragraPath', '')
		path2CropCoeff = s.value('cropcoeffPath', '')
		MCRpath = s.value('MCRpath', '')
		MinGWPath = s.value('MinGWPath', '')

		self.IDRAGRA_EXE.setFilter('Executable (*.exe)')
		self.CROPCOEFF_EXE.setFilter('Executable (*.exe)')

		self.IDRAGRA_EXE.setFilePath(path2Idragra)
		self.CROPCOEFF_EXE.setFilePath(path2CropCoeff)

		self.MATLAB_FOLDER.setFilePath(MCRpath)
		self.MINGW_FOLDER.setFilePath(MinGWPath)

		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		#QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
		#QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
		QMetaObject.connectSlotsByName(self)
		
	def closeEvent(self, event):
		self.closed.emit()

	def getData(self):
		### get executable path
		idragraPath = self.IDRAGRA_EXE.filePath()
		cropcoeffPath = self.CROPCOEFF_EXE.filePath()
		MCRpath = self.MATLAB_FOLDER.filePath()
		MinGWPath = self.MINGW_FOLDER.filePath()

		return {'idragraPath':idragraPath,'cropcoeffPath':cropcoeffPath,
				'MCRpath':MCRpath, 'MinGWPath':MinGWPath
				}
