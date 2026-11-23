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

from processing.gui.wrappers import WidgetWrapper
from qgis.PyQt.QtWidgets import QDateTimeEdit
from qgis.PyQt.QtCore import QDate

class DateTimeWidget(WidgetWrapper):
	"""
	QDateTimeEdit widget with calendar pop up
	"""
	# https://www.faunalia.eu/fr/blog/2019-07-02-custom-processing-widget

	def createWidget(self):
		self._combo = QDateTimeEdit()
		self._combo.setDisplayFormat('yyyy-MM-dd')
		self._combo.setCalendarPopup(True)

		today = QDate.currentDate()
		self._combo.setDate(today)

		return self._combo

	def value(self):
		date_chosen = self._combo.dateTime()
		#Qt.ISODate
		return date_chosen.toString('yyyy-MM-dd')
		
	def setValue(self,dateString):
		self._combo.setDate(QDate.fromString(dateString, 'yyyy-MM-dd'))