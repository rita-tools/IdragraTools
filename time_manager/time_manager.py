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

import os
import os.path as osp
from os.path import dirname, join, exists, abspath, isfile, basename
import sys
import inspect
from shutil import copyfile
import numpy as np
import glob
import operator
import sqlite3 as sqlite
from datetime import datetime

from qgis.core import QgsVectorLayerCache,QgsVectorLayer

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import QtSql
from qgis.PyQt import uic

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

class TimeManager(QMainWindow):#(QDialog)QMainWindow:

	def __init__(self,parent=None, title = '',varDict= {},callBack = None, dateList=[]):
		QMainWindow.__init__(self, parent)
		self.installation_dir = os.path.dirname(__file__)
		self.iface = parent
		self.callBack = callBack
		# init gui
		uiFilePath = os.path.abspath(os.path.join(self.installation_dir, 'time_manager.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle(title)

		self.VARDICT = varDict
		# populate list of variable
		self.VAR_CB.addItems(list(self.VARDICT.values()))

		# setup scrollbar
		self.DATELIST = dateList
		nOfDays = len(self.DATELIST)
		print('nOfDays:',nOfDays)
		self.LOWLIM = 0
		self.UPLIM = nOfDays-1
		self.TIME_SB.setMinimum(self.LOWLIM)
		self.TIME_SB.setMaximum(self.UPLIM)

		# init
		self.count = -1
		self.fps = 5
		self.timer = QTimer(self.iface)
		self.timer.timeout.connect(self.execute)
		self.timer.setInterval(1000/self.fps)

        # connect buttons
		self.BACKWARD_BTN.clicked.connect(self.goBackward)
		self.FORWARD_BTN.clicked.connect(self.goForward)
		self.PLAY_BTN.clicked.connect(self.play)

        # connect windows closeEvent
		self.TIME_SB.valueChanged.connect(self.updateCounter)
		self.TIME_SB.valueChanged.connect(self.updateStepLabel)

	def play(self):
		if self.PLAY_BTN.isChecked():
			self.PLAY_BTN.setChecked(True)
			self.PLAY_BTN.setText('||')
			self.start()
		else:
			self.PLAY_BTN.setChecked(False)
			self.PLAY_BTN.setText('>')
			self.stop()

	def start(self):
		self.timer.start()

	def stop(self):
		self.timer.stop()

	def goForward(self):
		self.PLAY_BTN.setChecked(False)
		self.stop()
		if self.count<self.UPLIM:
			self.count+=1
			self.updateProgressBar(self.count)
			self.execute(False)

	def goBackward(self):
		self.PLAY_BTN.setChecked(False)
		self.stop()
		if self.count>self.LOWLIM:
			self.count-=1
			self.updateProgressBar(self.count)
			self.execute(False)

	def updateProgressBar(self,step):
		self.TIME_SB.setValue(step)

	def updateCounter(self,step):
		self.count = step
		if self.count>self.UPLIM:
			self.stop()
		if self.count<self.LOWLIM:
			self.stop()
			
		self.execute(False)


	def updateStepLabel(self,step):
		self.DATE_LBL.setText('day %s'%self.DATELIST[self.count])

	def execute(self,goNext = True):
		if goNext: self.count+=1
		if (self.count > self.UPLIM) or (self.count < self.LOWLIM):
			return

		# get current variables
		selVarName = self.VAR_CB.currentText()
		selVarIdx = list(self.VARDICT.values()).index(selVarName)
		selVar = list(self.VARDICT.keys())[selVarIdx]

		# get current limits
		minmax = None
		try:
			minmax = (float(self.MINSCALE_LE.text()),float(self.MAXSCALE_LE.text()))
		except:
			pass

		self.callBack(selVar,self.DATELIST[self.count],minmax)
		#print('do something:',self.count)
		self.updateProgressBar(self.count)

	def closeEvent(self,event):
		self.timer.stop()
		#print('ok')

if __name__ == '__console__':
	#layer = iface.activeLayer()
	dialog = TimeManager(None,'timer',{'a':'aaaa','b':'bbbb'})
	dialog.show()
