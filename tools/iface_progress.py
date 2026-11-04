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

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QProgressBar
from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgsMessageBar

# TODO: manage error message


class IfaceProgress(QObject):
	def __init__(self,iface):
		QObject.__init__(self,iface)
		self.iface = iface
		# setup progress bar
		# clear the message bar
		self.iface.messageBar().clearWidgets()
		# set a new message bar
		progressMessageBar = self.iface.messageBar()

		# Init progress bar
		self.progressBar = QProgressBar()
		self.progressBar.setMaximum(100)
		# pass the progress bar to the message Bar
		progressMessageBar.pushWidget(self.progressBar)

	def setConsoleInfo(self, text):
		QgsMessageLog.logMessage(text, 'IdrAgra', level=Qgis.Info)

	def error(self, text):
		self.iface.messageBar().pushMessage("Error", text, level=Qgis.Critical)

	def setProgress(self,val):
		self.progressBar.setValue(int(val))
		if val >=100:
			self.iface.messageBar().clearWidgets()

	def setPercentage(self,val,printPerc = False):
		progressValue = int(val)
		if printPerc:
			nblock = int(progressValue/10)
			blocks = ['#']*nblock
			lines = ['_']*(10-nblock)
			bar = 'PROGRESS: '+blocks+lines
			print(bar, end="\r")
			self.progressBar.setValue(progressValue)
		else:
			print('PERC: %s' % progressValue)
			self.progressBar.setValue(progressValue)

		if val >=100:
			self.iface.messageBar().clearWidgets()

	def setText(self, text):
		QgsMessageLog.logMessage(text, 'IdrAgra', level=Qgis.Info)

	def setInfo(self, text, error=False):
		self.pushInfo(text,error)

	def pushInfo(self, text, error=False):
		if error:
			self.iface.messageBar().pushMessage("Error", text, level=Qgis.Critical)
		else:
			self.iface.messageBar().pushMessage("Info", text, level=Qgis.Info)

	def setCommand(self, text):
		QgsMessageLog.logMessage(text, 'IdrAgra', level=Qgis.Info)

	def reportError(self, text, error=False):
		if error:
			self.iface.messageBar().pushMessage("Error", text, level=Qgis.Critical)

		else:
			self.iface.messageBar().pushMessage("Warning", text, level=Qgis.Warning)
