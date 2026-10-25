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

import sys
from qgis.PyQt import QtGui
from qgis.PyQt.QtWidgets import QDialog,QMenu,QMessageBox,QPushButton,QVBoxLayout,QWidget,Qlabel

from matplotlib.backends.backend_qt5agg  import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdt
from matplotlib.patches import Polygon


import numpy as np

import random
from datetime import datetime


class TextWidget(QWidget):
	def __init__(self, parent=None):
		QWidget.__init__(self,parent)

		self.myLabel = Qlabel()
		layout = QVBoxLayout()
		layout.addWidget(self.myLabel)
		self.setLayout(layout)
	
	def setText(self,value):
		myLabel.setText(value)
		
	def getText(self):
		return myLabel.text()
		
	text = pyqtProperty(str, fget=getText, fset=setText)
