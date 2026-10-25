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

import traceback

from qgis.PyQt import QtGui, QtCore
from qgis.PyQt.QtCore import QThread
from time import sleep

from qgis.core import QgsProcessingFeedback, QgsFeedback


class Worker(QgsProcessingFeedback):#(QtCore.QObject):
	finished = QtCore.pyqtSignal()
	finishedBefore = QtCore.pyqtSignal()
	ready = QtCore.pyqtSignal()
	reportProgress = QtCore.pyqtSignal(object)
	reportMessage = QtCore.pyqtSignal(str,str)
	
	def __init__(self,parent,function,*args, **kwargs):
		#QtCore.QObject.__init__(self)
		#QgsProcessingFeedback.__init__(self)
		QgsProcessingFeedback.__init__(self)
		self.parent = parent
		self._flag = True
		self.function = function
		self.args = args
		self.kwargs = kwargs
		self.kwargs['progress']= self # make worker as progress output
		
	def stop(self):
		if self._flag:
			self._flag = False
			self.finishedBefore.emit()
		
	def getFlag(self):
		return self._flag
		
	def pushInfo(self, text,error = False):
		if error:
			self.error(text)
		else:
			self.setConsoleInfo(text)

	def pushCommandInfo(self, text):
		self.reportMessage.emit(self.decode(text), 'gray')

	def setConsoleInfo(self,text):
		self.reportMessage.emit(self.decode(text) ,'gray')
		
	def error(self,text):
		self.reportMessage.emit(self.decode(text) ,'red')
		
	def reportError(self,text,stopFlag =False):
		if stopFlag:
			self.reportMessage.emit(self.decode(text), 'red')
			self.stop()
		else:
			self.reportMessage.emit(self.decode(text), 'blue')
	
	def setText(self, text):
		self.reportMessage.emit(self.decode(text) ,'gray')
		
	def setInfo(self,text, error=False):
		if error:
			self.error(text)
		else:
			self.setConsoleInfo(text)
		
	def setCommand(self, text):
		self.reportMessage.emit(self.decode(text) ,'black')
		
	def setPercentage(self,val):
		try:
			val = int(val)
		except:
			val = 0
			
		self.reportProgress.emit(val)

	def setProgress(self,val):
		self.setPercentage(val)

	def process(self):
		#~ self.ready.emit()
		# add try to manage errors ...
		try:
			self._flag = self.function(*self.args, **self.kwargs)
		except Exception as e:
			self.setInfo('Unmanaged error %s'%str(e),True)
			# credits: https://stackoverflow.com/questions/11414894/extract-traceback-info-from-an-exception-object/14564261#14564261
			traceback_str = ''.join(traceback.format_tb(e.__traceback__))
			self.setInfo('Traceback %s' % traceback_str, True)

		finally:
			self.finished.emit()

	def decode(self,btext):
		try:
			btext = btext.decode('utf-8')
		except (UnicodeDecodeError, AttributeError):
			pass
		
		return btext