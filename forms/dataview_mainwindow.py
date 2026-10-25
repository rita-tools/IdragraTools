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

import os
import os.path as osp
from os.path import dirname, join, exists, abspath, isfile, basename
import sys
import inspect
from shutil import copyfile
import numpy as np
import glob
import operator

from datetime import datetime

from qgis.core import QgsVectorLayerCache,QgsVectorLayer
from qgis.gui import (QgsAttributeTableModel,
									QgsAttributeTableView,
									QgsAttributeTableFilterModel)

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import QtSql
from qgis.PyQt import uic

from ..qt_compat import QAction

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from .chart_widget import ChartWidget

#def __init__(self,plugin_dir, dbPath, canvas,layer):
class DataViewMainwindow(QMainWindow):#(QDialog):
	
	def __init__(self,parent=None, title = ''):
		QMainWindow.__init__(self, parent)
		
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'dataview_mainwindow.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle(title)
		self.initUI()
		
	def closeEvent(self,event):
		print('ok')
		
		
	def _addmenuitem(self,parent, name, text, function):
		action = QAction(parent)
		action.setObjectName(name)
		action.setIcon(QIcon(self.plugin_dir+'/icons/'+name+'.svg'))
		action.setText(text)
		action.triggered.connect(function)
		parent.addAction(action)
		
	def _addAction(self,parent,name,text,function, checkable=False):
		action = QAction(parent)
		action.setObjectName(name)
		action.setIcon(QIcon(self.plugin_dir+'/icons/'+name+'.svg'))
		action.setText(text)
		#action.setWhatsThis(self.tr("Select upstream network"))
		action.setCheckable(checkable)
		action.triggered.connect(function)
		parent.addAction(action)
	
	def _addmenu(self,parent,name,text):
		menu = QMenu(parent)
		menu.setObjectName(name)
		menu.setTitle(text)
		return menu

	def initUI(self):
		menubar = self.menuBar()
		self.manMenu = self._addmenu(menubar,'MainMenu',self.tr('File'))
		#self._addmenuitem(self.manMenu, 'ZoomToSelected', self.tr('Zoom to selected'), self.ZoomToSelected)
		
		
		menubar.addMenu(self.manMenu)
		
		self.toolBar = self.addToolBar('MainToolBar')
		#self._addAction(self.toolBar, 'ZoomToSelected', self.tr('Zoom to selected'), self.ZoomToSelected,False)
		
		self.statusBar()
		#self.setWindowTitle(self.tr('Crop fields'))    
		
		# add chartWidget
		# a figure instance to plot on
		self.CHART = ChartWidget()

		
		# set the layout
		layout = QVBoxLayout()
		layout.addWidget(self.CHART)
		self.PLOT_SA.setLayout(layout)
		self.sb = self.DATA_TW.verticalScrollBar()
		print('slider: %s'%self.sb)
		self.sb.sliderReleased.connect(self.updateChart)
		
	def setModel(self, aModel):
		self.DATA_TW.setModel(aModel)
		self.updateChart()
		
	def printValue(self):
		print('aval: %s'%'release')
	
	def updateChart(self):
		model = self.DATA_TW.model()
		ts = []
		vals = []
		for row in range(model.rowCount()):
			index = model.index(row, 0)
			ts.append(datetime.strptime(str(model.data(index)),'%Y-%m-%d'))
			index = model.index(row, 1)
			vals.append(model.data(index))
		
		self.CHART.addTimeSerie(ts,vals)
		self.CHART.setAxes()
			

