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
from datetime import datetime

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import QtSql
from qgis.PyQt import uic

from .chart_dialog import ChartDialog
from .utils import toDo

import qgis

class WeatherManagerDialog(QDialog):
	def __init__(self, parent, dbPath,wsId,title=''):
		QDialog.__init__(self, parent)
		
		#setup form
		uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'weather_manager_dialog.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle(title)
		
		self.wsId = wsId
		self.dbPath = dbPath
		
		# connect to db
		db = QtSql.QSqlDatabase.addDatabase('QSQLITE')
		db.setDatabaseName(dbPath)
		
		model = QtSql.QSqlTableModel() # <--- NECESSARY TO RUN QUERY WITH  QSqlQueryModel?!?!
		self.dataModel = QtSql.QSqlQueryModel() # <-- USED BY TABLE VIEW ...
	
		# setup chart
		#self.CHART = ChartWidget()
		self.ADD_BTN.clicked.connect(self.addMeteoData)
		self.DEL_BTN.clicked.connect(toDo)
		self.PLOT_BTN.clicked.connect(self.plotData)
		#self.DUPL_BTN.clicked.connect(self.duplicateRecord)
		#self.TABS.addTab(self.CHART,self.tr('Plot'))
		
		# set table view and plot
		self.setTimeSeries(wsId)
		
		#print('model: %s'%self.dataModel)
		
		self.CHART = None
		
		self.METEONAME = qgis.utils.plugins['QWaDiS'].METEONAME
		
		#self.DATA_TV.verticalScrollBar().sliderReleased.connect(self.updateChart)
		#self.TABS.currentChanged[int].connect(self.checkTab)
		
	def setTimeSeries(self,sensorId):
		self.initDataModel(sensorId)
		self.DATA_TV.setModel(self.dataModel)
		#self.updateChart(self.dataModel)
		
	def initDataModel(self,sensorId):
		sql = """
				SELECT
					ws_tmax.timestamp as ts,
					ws_tmax.recval as tmax,
					ws_tmin_sel.recval as tmin,
					ws_ptot_sel.recval as ptot,
					ws_umin_sel.recval as umin,
					ws_umax_sel.recval as umax,
					ws_vmed_sel.recval as vmed,
					ws_rgcorr_sel.recval as rgcorr
				FROM ws_tmax
				LEFT JOIN (SELECT * FROM ws_tmin WHERE ws_tmin.wsid = '[%id%]') as ws_tmin_sel
				USING(timestamp)
				LEFT JOIN (SELECT * FROM ws_Ptot WHERE ws_Ptot.wsid = '[%id%]') as ws_ptot_sel
				USING(timestamp)
				LEFT JOIN (SELECT * FROM ws_umin WHERE ws_umin.wsid = '[%id%]') as ws_umin_sel
				USING(timestamp)
				LEFT JOIN (SELECT * FROM ws_umax WHERE ws_umax.wsid = '[%id%]') as ws_umax_sel
				USING(timestamp)
				LEFT JOIN (SELECT * FROM ws_vmed WHERE ws_vmed.wsid = '[%id%]') as ws_vmed_sel
				USING(timestamp)
				LEFT JOIN (SELECT * FROM ws_rgcorr WHERE ws_rgcorr.wsid = '[%id%]') as ws_rgcorr_sel
				USING(timestamp)
				WHERE ws_tmax.wsid = '[%id%]'
				"""
		
		self.dataModel.setQuery(sql.replace('[%id%]',str(sensorId)))
		
		self.dataModel.setHeaderData(0, Qt.Horizontal, self.tr("Date-time"))
		self.dataModel.setHeaderData(1, Qt.Horizontal, self.tr("T max (C)"))
		self.dataModel.setHeaderData(2, Qt.Horizontal, self.tr("T min (C)"))
		self.dataModel.setHeaderData(3, Qt.Horizontal, self.tr("Precipitation (mm)"))
		self.dataModel.setHeaderData(4, Qt.Horizontal, self.tr("U min (-)"))
		self.dataModel.setHeaderData(5, Qt.Horizontal, self.tr("U max (-)"))
		self.dataModel.setHeaderData(6, Qt.Horizontal, self.tr("V mean (m/s)"))
		self.dataModel.setHeaderData(7, Qt.Horizontal, self.tr("RG corr (MJ/m^2/d)"))
		
	def plotData(self,model=None):
		if not model: model=self.dataModel
		
		ts = []
		tmax = []
		tmin = []
		p = []
		for row in range(model.rowCount()):
			index = model.index(row, 0)
			ts.append(datetime.strptime(str(model.data(index)),'%Y-%m-%d'))
			index = model.index(row, 1)
			tmax.append(model.data(index))
			index = model.index(row, 2)
			tmin.append(model.data(index))
			index = model.index(row, 3)
			p.append(model.data(index))
		

		self.CHART = ChartDialog(self, self.tr('Meteo data'))
		self.CHART.resize(0.9*self.geometry().width(),self.geometry().height())
		self.CHART.setAxis(211)
		self.CHART.setTitles(xlabs = None, ylabs = None, xTitle = None, yTitle = self.tr('Temperature (C)'), y2Title = None, mainTitle = None)
		if len(ts)>0: self.CHART.addTimeSerie(dateTimeList = ts,values=tmax,lineType='-',color='r',name = self.tr('T max (C)'),yaxis = 1)
		if len(ts)>0: self.CHART.addTimeSerie(dateTimeList = ts,values=tmin,lineType='-',color='b',name = self.tr('T min (C)'),yaxis = 1)
		self.CHART.setAxis(212)
		self.CHART.setTitles(xlabs = None, ylabs = None, xTitle = None, yTitle = self.tr('Precipitation (C)'), y2Title = None, mainTitle = None)
		if len(ts)>0: self.CHART.addBarPlot(x = ts,y=p,width=1,color='b',name = 'Precipitation (mm)')
		
		self.CHART.show()
		
	def addMeteoData(self):
		from .import_data import ImportData
		dlg = ImportData(self,self.METEONAME)
		dlg.show()
		result = dlg.exec_() 
		# See if OK was pressed
		res = []
		if result == 1: 
			res = dlg.getData()
			#import data from csv
			qgis.utils.plugins['QWaDiS'].runAsThread(qgis.utils.plugins['QWaDiS'].importDataFromCSV,
																				filename =res['selFile'], tablename=res['varName'], timeFldIdx=res['timeFldIdx'],
																				valueFldIdx=res['valueFldIdx'], sensorId=self.wsId, skip=res['skipLines'],
																				timeFormat=res['timeFormat'], column_sep=res['sep'],progress=None)
																			
	def removeMeteoData(self):
		from .remove_data import RemoveData
		wsid = self.DBM.getDataFromTable(tableName = 'idr_weather_stations',fieldList = ['fid'])
		wsid = [str(*x) for x in wsid]
		wsname = self.DBM.getDataFromTable(tableName = 'idr_weather_stations',fieldList = ['name'])
		wsname = [str(*x) for x in wsname]
		wsDict = dict(zip(wsid, wsname))
		
		dlg = RemoveData(self.iface.mainWindow(),self.METEONAME,wsDict)
		dlg.show()
		result = dlg.exec_() 
		# See if OK was pressed
		res = []
		if result == 1: 
			res = dlg.getData()
			#delete meteo data from database
			# select * from idr_tmin where (date(timestamp) > date('2020-01-01')) and (date(timestamp) < date('2020-02-01')) and wsname = '100'
			delCondition =  "((date(timestamp) >= date('%s')) and (date(timestamp) <= date('%s')) and (wsname = '%s'))"%(res['fromDate'],res['toDate'],res['sensorId'])
			self.DBM.deleteRow(tableName=res['varName'],wCond=delCondition)


	def insertRecord(self):
		newName, ok = QInputDialog.getText(self,self.tr('Define the name of the soil type'),self.tr('soil type name:'))
		if ok and (newName!=''):
			newRecord = self.model.record()
			#newRecord.setValue("id", null)
			newRecord.setValue("name", newName)
			ret = self.model.insertRecord(-1, newRecord)
			self.model.submitAll()
			
	def duplicateRecord(self):
		newName, ok = QInputDialog.getText(self,self.tr('Define the name of the soil type'),self.tr('soil type name:'))
		if ok and (newName!=''):
			newRecord = self.model.record(self.NAME_LST.currentIndex().row())
			newRecord.setValue("id", None)
			newRecord.setValue("name", newName)
			ret = self.model.insertRecord(-1, newRecord)
			self.NAME_LST.repaint()
			
	def deleteRecord(self):
		msgBox = QMessageBox()
		msgBox.setText(self.tr("The database will be permanently modified. All modifications will be saved!"))
		msgBox.setInformativeText(self.tr("Do you want to delete the selected record?"))
		msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
		msgBox.setDefaultButton(QMessageBox.Cancel)
		ret = msgBox.exec_()
		
		if ret ==QMessageBox.Ok:
			i = self.NAME_LST.currentIndex().row()
			print('record to be deleted: %s'%i)
			self.model.removeRow(i)
			self.NAME_LST.repaint()
			self.model.submitAll()
			
	def findrow(self,i):
		self.mapper.setCurrentModelIndex(i)
		
	def updateDB(self):
		print("updating DB")
		self.model.submitAll()
		#~ erreur = self.model.lastError().text()
		#~ print(erreur)
		self.accept()

if __name__ == '__console__':

	dlg = SoilTypeDialog(dbPath='C:/idragra_code/dataset/test.gpkg',wsId=1,title = 'test')
	dlg.show()
	