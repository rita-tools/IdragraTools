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

from qgis.PyQt.QtWidgets import QDialog, QToolBox, QWidget, QVBoxLayout, QFileDialog, QListWidgetItem, QSpinBox, \
	QCalendarWidget, QToolButton, QLabel, QCheckBox, QMainWindow

import os

from qgis import processing
from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle, QgsProject, QgsPoint, QgsGeometry, QgsPointXY, \
	QgsWkbTypes
from qgis.gui import QgsDateTimeEdit, QgsRubberBand, QgsVertexMarker

from ..tools.utils import returnExtent

class NoYearCalendar(QCalendarWidget):
	def __init__(self,parent):
		QCalendarWidget.__init__(self,parent)
		self.findChild(QToolButton,'qt_calendar_yearbutton').setHidden(True)

class NoYearDate(QgsDateTimeEdit):
	def __init__(self,parent):
		QgsDateTimeEdit.__init__(self,parent)
		newCal = NoYearCalendar(self)
		self.setCalendarWidget(newCal)
		self.setMinimumDate(QDate(2000, 1, 1))
		self.setMaximumDate(QDate(2000,12,31))
		self.setDisplayFormat('MMMM, dd')

	def value(self):
		# get date
		aTime = self.date()
		# transform to dayOfYear
		return aTime.dayOfYear()

	def setValue(self,dayOfYear):
		selDate = QDate(2000, 1, 1).addDays(dayOfYear-1)
		self.setDate(selDate)


class SetSimulationDialog(QMainWindow):
	closed = pyqtSignal()
	accepted = pyqtSignal()
	
	FILELIST = {}
	VARLIST = {}
	FUNLIST = {}
	
	def __init__(self, parent=None, yearList=[],modeList = [], simSettings = {}, defLuDict = {},defImDict={}):
		QMainWindow.__init__(self, parent.mainWindow())
		# Set up the user interface from Designer.
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'set_simulation_dialog.ui'))
		uic.loadUi(uiFilePath, self)

		# init overall list
		self.rbList = []
		self.canvas = parent.mapCanvas()
		#self.allCaseYearList = allCaseYearList
		#self.consumeYearList = consumeYearList
		self.yearList = yearList
		self.defLuDict = defLuDict
		self.defImDict = defImDict

		# init irrigation page
		self.IRRSTART_LB = QLabel(self.tr('Irrigation season starts at'), self)
		self.IRREND_LB = QLabel(self.tr('Irrigation season ends at'), self)
		self.IRRSTART_TE = NoYearDate(self)
		self.IRREND_TE = NoYearDate(self)
		layout = self.IRRIGATION_PG.layout()
		layout.addRow(self.IRRSTART_LB, self.IRRSTART_TE)
		layout.addRow(self.IRREND_LB, self.IRREND_TE)

		# init output page
		self.USEMONTHS_CB = QCheckBox(self.tr('Output each month'),self)
		self.STARTDATE_LB = QLabel(self.tr('From day'),self)
		self.ENDDATE_LB = QLabel(self.tr('To day'),self)
		self.STEPDATE_LB = QLabel(self.tr('Time step (number of day)'),self)
		self.STARTDATE_TE = NoYearDate(self)
		self.ENDDATE_TE = NoYearDate(self)
		self.STEPDATE_SB = QSpinBox()
		self.STEPDATE_SB.setMinimum(1)
		self.STEPDATE_SB.setMaximum(366)
		self.STEPDATE_SB.setValue(10)
		layout = self.OUTPUT_PG.layout()
		layout.addRow(self.USEMONTHS_CB)
		layout.addRow(self.STARTDATE_LB,self.STARTDATE_TE)
		layout.addRow(self.ENDDATE_LB, self.ENDDATE_TE)
		layout.addRow(self.STEPDATE_LB, self.STEPDATE_SB)

		self.setWindowTitle('Idragra Tools')

		# simulation mode
		self.MODE_CB.addItems(modeList)  # populate list of simulation mode
		self.MODE_CB.currentIndexChanged.connect(self.enableIrrPeriod)
		if simSettings['MODE'] in range(0, len(modeList)):
			self.MODE_CB.setCurrentText(modeList[simSettings['MODE']])
			self.MODE_CB.currentIndexChanged.emit(simSettings['MODE'])

		self.DEF_LU_CB.addItems(list(self.defLuDict.values()))
		#print('self.defLuDict.keys:',list(self.defLuDict.keys()),'selected:',simSettings['DEFAULT_LU'])
		if simSettings['DEFAULT_LU'] in list(self.defLuDict.keys()):
			self.DEF_LU_CB.setCurrentText(self.defLuDict[simSettings['DEFAULT_LU']])

		self.DEF_IM_CB.addItems(list(self.defImDict.values()))
		if simSettings['DEFAULT_IM'] in list(self.defImDict.keys()):
			self.DEF_IM_CB.setCurrentText(self.defImDict[simSettings['DEFAULT_IM']])

		# sowing window
		self.RANDWIND_SB.setValue(simSettings['RANDWIND'])

		# yearly maps
		if simSettings['SOILUSEVARFLAG'] == 'T':
			self.SOILUSEVARFLAG_CB.setChecked(True)
		else:
			self.SOILUSEVARFLAG_CB.setChecked(False)

		### set output path
		self.OUTFOLDER_FW.setFilePath(simSettings['OUTPUTPATH'])

		### set simulation period
		#yearList = self.allCaseYearList
		#if simSettings['MODE']==1: yearList=self.consumeYearList

		# self.PERIOD_CB.addItems(yearList)
		# if str(simSettings['PERIOD']) in yearList:
		# 	self.FROM_CB.setCurrentText(str(simSettings['PERIOD']))

		self.FROM_CB.addItems(yearList)
		if str(simSettings['STARTYEAR']) in yearList:
			self.FROM_CB.setCurrentText(str(simSettings['STARTYEAR']))

		self.TO_CB.addItems(yearList)
		if str(simSettings['ENDYEAR']) in yearList:
			self.TO_CB.setCurrentText(str(simSettings['ENDYEAR']))

		# update based on selection
		self.updateLastYear()

		### set spatial resolution
		print('simSettings:',simSettings)
		if simSettings['VECTOR_MODE']:
			#print('vector mode is selected')
			self.VECTOR_MODE.setChecked(True)
			self.enableGridDomain()
		else:
			#print('grid mode is selected')
			self.GRID_MODE.setChecked(True)
			self.enableGridDomain()


		self.DOMAINEXT.setMapCanvas(self.canvas)
		#print('Set_simulation, CRS', simSettings['CRS'])
		try:
			crsCode = float(simSettings['CRS'])
			crs = QgsCoordinateReferenceSystem()
			# crs.createFromSrid(self.SIMDIC['CRS']) deprecated since 3.10
			crs.createFromSrsId(crsCode)
		except:
			crsCode = simSettings['CRS']
			crs = QgsCoordinateReferenceSystem(crsCode)

		#crs = QgsCoordinateReferenceSystem()
		#crs.createFromSrsId(crsCode)

		# xmin,ymin : xmax,ymax
		extStr = simSettings['EXTENT']
		ext = returnExtent(extStr)
		if ext is None:
			ext = self.canvas.extent()

		self.DOMAINEXT.setOriginalExtent(ext, crs)
		self.DOMAINEXT.setCurrentExtent(ext, crs)
		self.DOMAINEXT.setOutputCrs(crs)

		self.DOMAINEXT.setOutputExtentFromUser(ext, crs)
		self.CELLSIZE_SB.setValue(simSettings['CELLSIZE'])

		### set hydrological model
		self.EVALAY_SB.setValue(simSettings['ZEVALAY'])
		self.TRANSLAY_SB.setValue(simSettings['ZTRANSLAY'])
		# capillary rise
		if simSettings['CAPILLARYFLAG']=='T':
			self.CAPRISE_CB.setChecked(True)
		else:
			self.CAPRISE_CB.setChecked(False)

		# slope limits
		self.MINSLOPE_SB.setValue(simSettings['MINSLOPE'])
		self.MAXSLOPE_SB.setValue(simSettings['MAXSLOPE'])

		### set irrigation variable
		self.IRRSTART_TE.setValue(simSettings['STARTIRRSEASON'])
		self.IRREND_TE.setValue(simSettings['ENDIRRSEASON'])

		if simSettings['MODE']==0:
		 	self.IRRSTART_TE.setEnabled(False)
		 	self.IRREND_TE.setEnabled(False)

		### set output settings
		self.USEMONTHS_CB.stateChanged.connect(self.enableOutTime)
		if simSettings['MONTHOUTPUT']=='T':
			self.USEMONTHS_CB.setChecked(True)
			self.USEMONTHS_CB.stateChanged.emit(2)
		else:
			self.USEMONTHS_CB.setChecked(False)
			self.USEMONTHS_CB.stateChanged.emit(0)

		self.STARTDATE_TE.setValue(simSettings['STARTOUTPUT'])
		self.ENDDATE_TE.setValue(simSettings['ENDOUTPUT'])
		self.STEPDATE_SB.setValue(simSettings['STEPOUTPUT'])

		self.FROM_CB.currentTextChanged.connect(self.updateLastYear)

		# connect gridded domain options
		self.GRID_MODE.toggled.connect(self.enableGridDomain)

		# connect preview function
		self.conn_canvas = self.canvas.extentsChanged.connect(self.drawGrid)
		self.DOMAINEXT.extentChanged.connect(self.drawGrid)
		self.CELLSIZE_SB.valueChanged.connect(self.drawGrid)
		self.DRAW_GRID_CB.toggled.connect(self.drawGrid)


		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		#QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
		#QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
		QMetaObject.connectSlotsByName(self)

	def close(self):
		try:
			self.disconnect(self.conn_canvas)
		except:
			self.canvas.extentsChanged.disconnect(self.drawGrid)

		self.deleteGrid()
		super().close()


	def accept(self):
		self.close()
		self.accepted.emit()
		return 1

	def reject(self):
		self.close()
		return 0

	def updateLastYear(self):
		fromYear = int(self.FROM_CB.currentText())
		selYear = int(self.TO_CB.currentText())

		self.updateYearList(self.TO_CB, self.yearList, fromYear, selYear)

	def updateYearList(self,yearCB,yearList,minYear,selYear):
		minYearIdx = yearList.index(str(minYear))
		yearList=yearList[minYearIdx:]
		yearCB.clear()
		yearCB.addItems(yearList)
		if str(selYear) in yearList:
			yearCB.setCurrentText(str(selYear))

	def enableIrrPeriod(self,index):
		flag = True
		if index == 0:
			flag = False

		self.IRRSTART_TE.setEnabled(flag)
		self.IRREND_TE.setEnabled(flag)

	def enableOutTime(self,state):
		flag = True
		if state == 2:
			flag = False

		self.STARTDATE_TE.setEnabled(flag)
		self.ENDDATE_TE.setEnabled(flag)
		self.STEPDATE_SB.setEnabled(flag)

	def closeEvent(self, event):
		# self.disconnect(self.conn_canvas)
		# self.deleteGrid()
		self.closed.emit()

	def enableGridDomain(self):
		if self.GRID_MODE.isChecked():
			self.SETDOMAIN_GB.setEnabled(True)
		else:
			self.SETDOMAIN_GB.setEnabled(False)
			self.DRAW_GRID_CB.setChecked(False)

	def drawGrid(self,val=None):
		self.deleteGrid()
		if not self.DRAW_GRID_CB.isChecked():
			#print('Update preview not checked',self.DRAW_GRID_CB.isChecked(),val)
			return

		col = QColor(153,153,153) # gray color

		rasterExt = self.DOMAINEXT.outputExtent()
		cellDim = self.CELLSIZE_SB.value()

		xllcorner = rasterExt.xMinimum()
		# yllcorner = extension.yMinimum()
		yurcorner = rasterExt.yMaximum()
		h = rasterExt.height()
		w = rasterExt.width()

		nrows = round(h / cellDim)
		ncols = round(w / cellDim)

		xurcorner = xllcorner + ncols * cellDim
		# yurcorner = yllcorner+nrows*outputCellSize
		yllcorner = yurcorner - nrows * cellDim


		viewExt = self.canvas.extent()
		nOfCells = viewExt.area()/(cellDim*cellDim)

		if nOfCells>1000:
			# draw only the edge
			xList = [xllcorner,xurcorner]
			yList = [yllcorner, yurcorner]
			# draw polygon
			r = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
			r.setStrokeColor(col)
			r.setFillColor(QColor(153,153,153,60))
			r.setWidth(3)
			geom = QgsGeometry().fromRect(rasterExt)  # QgsGeometry object
			# set rubber band to geometry
			r.setToGeometry(geom)
			self.rbList.append(r)
		else:
			xList = [xllcorner+i*cellDim for i in range(0,ncols+1)]
			yList = [yllcorner+i*cellDim for i in range(0,nrows+1)]
			# filter coordinates
			view_xmin = viewExt.xMinimum() - cellDim
			view_xmax = viewExt.xMaximum() + cellDim
			view_ymin = viewExt.yMinimum() - cellDim
			view_ymax = viewExt.yMaximum() + cellDim
			xList = list(filter(lambda x: (x >= view_xmin) and (x<=view_xmax), xList))
			yList = list(filter(lambda y: (y >= view_ymin) and (y <= view_ymax), yList))

			# draw vertical lines
			for x in xList:
				r = QgsRubberBand(self.canvas, False)  # False = not a polygon
				r.setColor(col)
				r.setWidth(3)
				points = [QgsPoint(x, yllcorner), QgsPoint(x, yurcorner), QgsPoint(x, yllcorner)]
				r.setToGeometry(QgsGeometry.fromPolyline(points), None)
				self.rbList.append(r)
			# draw horizontal lines
			for y in yList:
				r = QgsRubberBand(self.canvas, False)  # False = not a polygon
				r.setColor(col)
				r.setWidth(3)
				points = [QgsPoint(xllcorner, y), QgsPoint(xurcorner, y), QgsPoint(xllcorner, y)]
				r.setToGeometry(QgsGeometry.fromPolyline(points), None)
				self.rbList.append(r)

			for x in xList[:-1]:
				for y in yList[:-1]:
					m = QgsVertexMarker(self.canvas)
					m.setCenter(QgsPointXY(x+0.5*cellDim, y+0.5*cellDim))
					m.setColor(col)
					m.setIconSize(5)
					m.setIconType(QgsVertexMarker.ICON_CROSS)  # or ICON_CROSS, ICON_X, ICON_BOX
					m.setPenWidth(3)
					self.rbList.append(m)

	def deleteGrid(self):
		#print('deleteGrid')
		for r in self.rbList:
			self.canvas.scene().removeItem(r)

	def getData(self):
		### get output path
		outfolder = self.OUTFOLDER_FW.filePath()
		useYearlyMaps = ['F', 'T'][int(self.SOILUSEVARFLAG_CB.isChecked())]
		### get options
		randWind = self.RANDWIND_SB.value()
		### get simulation period
		fromYear = int(self.FROM_CB.currentText())
		toYear = int(self.TO_CB.currentText())
		### get spatial resolution
		vector_mode = 0
		if self.VECTOR_MODE.isChecked(): vector_mode = 1
		dtmExtent = self.DOMAINEXT.outputExtent()
		crs = self.DOMAINEXT.outputCrs()
		#print('crs_from get',crs)
		cellsize = self.CELLSIZE_SB.value()
		### get hydrological model
		zevalay = self.EVALAY_SB.value()
		ztranslay = self.TRANSLAY_SB.value()
		capRise = ['F','T'][int(self.CAPRISE_CB.isChecked())]
		minSlope = self.MINSLOPE_SB.value()
		maxSlope = self.MAXSLOPE_SB.value()
		### get irrigation variable
		simMode = self.MODE_CB.currentIndex()
		irrStart = self.IRRSTART_TE.value()
		irrEnd = self.IRREND_TE.value()
		### get output settings
		outMonth = ['F', 'T'][int(self.USEMONTHS_CB.isChecked())]
		outStartDate = self.STARTDATE_TE.value()
		outEndDate = self.ENDDATE_TE.value()
		outStep = self.STEPDATE_SB.value()

		defLU = list(self.defLuDict.keys())[self.DEF_LU_CB.currentIndex()]
		defIM = list(self.defImDict.keys())[self.DEF_IM_CB.currentIndex()]

		return {'outfolder':outfolder,'simMode':simMode,'randWind':randWind,
				'defLU': defLU, 'defIM':defIM,
				'useyearlymaps':useYearlyMaps, 'from':fromYear, 'to':toYear,
				'vectorMode':vector_mode,'extent':dtmExtent, 'crs':crs, 'cellsize':cellsize,
				'zevalay':zevalay,'ztranslay':ztranslay,'capRise':capRise,'minSlope':minSlope, 'maxSlope':maxSlope,
				'irrStart':irrStart, 'irrEnd':irrEnd,
				'outMonth':outMonth, 'outStartDate': outStartDate, 'outEndDate': outEndDate, 'outStep': outStep
				}
