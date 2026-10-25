# -*- coding: utf-8 -*-

"""
/***************************************************************************
 Data Manager
 A tool to manage time series from database
-------------------
		begin				: 2020-12-01
		copyright			: (C) 2020 by Enrico A. Chiaradia
		email				    : enrico.chiaradia@unimi.it
 ***************************************************************************/

/***************************************************************************
 *																		                                                               *
 *   This program is free software; you can redistribute it and/or modify                                *
 *   it under the terms of the GNU General Public License as published by                              *
 *   the Free Software Foundation; either version 2 of the License, or	                                   *
 *   (at your option) any later version.								                                                   *
 *																		                                                               *
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

from ..qt_compat import QAction

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from .data_window import DataWindow
from .time_filter import TimeFilter

class DataManagerMainwindow(QMainWindow):#(QDialog)QMainWindow:
	
	def __init__(self,parent=None, title = '',confDict= None,
				 dbFile = 'C:/idragra_code/dataset/test.gpkg',
				 initStartDate = '2000-01-01', initEndDate='2005-12-31',
				 settings = None):
		QMainWindow.__init__(self, parent)
		self.installation_dir = os.path.dirname(__file__)
		#self.installation_dir = 'C:/Users/enrico/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/IdragraTools/data_manager'
		#~ self.model = QStandardItemModel(parent)
		
		self.dbFile = dbFile

		self.s = settings
		
		uiFilePath = os.path.abspath(os.path.join(self.installation_dir, 'data_manager_mainwindow.ui'))
		uic.loadUi(uiFilePath, self)
		self.setWindowTitle(title)
		self.initUI()
		self.setupTreeWidget(self.TS_EXPLORER,confDict)
		
		self.TF = TimeFilter(initStartDate,initEndDate)
		layout = QVBoxLayout()
		layout.addWidget(self.TF)
		widget = QWidget(self)
		widget.setLayout(layout)
		self.FILTER_DOCK.setWidget(widget)
		
		
		self.CONF = confDict
		self.nSubs=0
		
		
	def closeEvent(self,event):
		print('ok')
		
		
	def _addmenuitem(self,parent, name, text, function):
		action = QAction(parent)
		action.setObjectName(name)
		action.setIcon(QIcon(self.installation_dir+'/icons/'+name+'.svg'))
		action.setText(text)
		action.triggered.connect(function)
		parent.addAction(action)
		
	def _addAction(self,parent,name,text,function, checkable=False):
		action = QAction(parent)
		action.setObjectName(name)
		action.setIcon(QIcon(self.installation_dir+'/icons/'+name+'.svg'))
		action.setText(text)
		#action.setWhatsThis(self.tr("Select upstream network"))
		action.setCheckable(checkable)
		con = action.triggered.connect(function)
		parent.addAction(action)
	
	def _addmenu(self,parent,name,text):
		menu = QMenu(parent)
		menu.setObjectName(name)
		menu.setTitle(text)
		return menu

	def initUI(self):
		menubar = self.menuBar()
		self.manMenu = self._addmenu(menubar,'MainMenu',self.tr('File'))
		self._addmenuitem(self.manMenu, 'ExportData', self.tr('Export data'), self.exportAsCSV)
		self.editMenu = self._addmenu(menubar,'EditMenu',self.tr('Edit'))
		self._addmenuitem(self.editMenu, 'AddData', self.tr('Add/update data'), self.addData)
		self._addmenuitem(self.editMenu, 'RemoveData', self.tr('Delete data'), self.removeData)
		
		self.viewMenu = self._addmenu(menubar,'ViewMenu',self.tr('View'))
		self._addmenuitem(self.viewMenu, 'VTileSubwindows', self.tr('Vertical tile'), self.verticalTile)
		self._addmenuitem(self.viewMenu, 'HTileSubwindows', self.tr('Horizontal tile'), self.MDI_AREA.tileSubWindows)
		self._addmenuitem(self.viewMenu, 'CascadeSubwindows', self.tr('Cascade'), self.MDI_AREA.cascadeSubWindows)
		
		menubar.addMenu(self.manMenu)
		menubar.addMenu(self.editMenu)
		menubar.addMenu(self.viewMenu)
		
		self.toolBar = self.addToolBar('MainToolBar')
		self._addAction(self.toolBar, 'AddPlot', self.tr('Add plot'), self.addPlot,False)
		self._addAction(self.toolBar, 'AddTable', self.tr('Add table'), self.addTable,False)
		self.toolBar.addSeparator()
		self._addAction(self.toolBar, 'AddData', self.tr('Add/update data'), self.addData,False)
		self._addAction(self.toolBar, 'RemoveData', self.tr('Delete data'), self.removeData,False)		
		self._addAction(self.toolBar, 'ExportData', self.tr('Export data'), self.exportAsCSV,False)		
		self.toolBar.addSeparator()
		self._addAction(self.toolBar, 'VTileSubwindows', self.tr('Vertical tile'), self.verticalTile,False)
		self._addAction(self.toolBar, 'HTileSubwindows', self.tr('Horizontal tile'), self.MDI_AREA.tileSubWindows,False)
		self._addAction(self.toolBar, 'CascadeSubwindows', self.tr('Cascade'), self.MDI_AREA.cascadeSubWindows,False)
		self.statusBar()
		
		self.MDI_AREA.subWindowActivated.connect(self.updateSubList)
		#self.setWindowTitle(self.tr('Crop fields'))    
		
		# add chartWidget
		# a figure instance to plot on
		#self.CHART = ChartWidget()

		
		# set the layout
		#~ layout = QVBoxLayout()
		#~ layout.addWidget(self.CHART)
		#~ self.PLOT_SA.setLayout(layout)
		#~ self.sb = self.DATA_TW.verticalScrollBar()
		#~ print('slider: %s'%self.sb)
		#~ self.sb.sliderReleased.connect(self.updateChart)
		
	def updateSubList(self,subWindow):
		winList = ['']
		if subWindow:
			# get list of subwindows
			for window in self.MDI_AREA.subWindowList():
				if (window.isVisible() and (subWindow.windowTitle()!=window.windowTitle())):
					winList.append(window.windowTitle())
			
			# call subwindow to update list
			subWindow.updateWinList(winList)
			
	
	def manageSubConnection(self,subTitle):
		slaveSub = self.MDI_AREA.currentSubWindow()
		
		# disconnect ...
		masterSub = None
		for window in self.MDI_AREA.subWindowList():
			if window.windowTitle()==slaveSub.CHART.cname:
				masterSub = window
		
		if masterSub:
			if slaveSub.CHART.cid is not None:
				masterSub.CHART.ax.callbacks.disconnect(slaveSub.CHART.cid)
				slaveSub.CHART.cid = None
				
		# connect
		masterSub = None
		for window in self.MDI_AREA.subWindowList():
			if window.windowTitle()==subTitle:
				masterSub = window

		if masterSub:
			slaveSub.CHART.cid = masterSub.CHART.ax.callbacks.connect('xlim_changed', slaveSub.CHART.updateXLimits)
			slaveSub.CHART.cname = subTitle
		else:
			# restore oldAxis
			slaveSub.CHART.ax.set_xlim(slaveSub.home_xlim)
			slaveSub.CHART.ax.set_ylim(slaveSub.home_ylim)
			slaveSub.CHART.figure.canvas.draw()

	def verticalTile(self,event = None):
		winList = []
		xpos = 0
		ypos = 0
		for window in self.MDI_AREA.subWindowList():
			if window.isVisible():
				winList.append(window)
		
		nOfWin = len(winList)
		
		hWin = self.MDI_AREA.height() / nOfWin
		wWin = self.MDI_AREA.width() 
		for window in winList:
			window.setGeometry(0,0,wWin,hWin)
			window.move(xpos,ypos)
			ypos+= hWin
			
	def addPlot(self):
		self.nSubs+=1
		sql = self.createQuery()
		#print('copy sql',sql)
		# make the model
		# make the view
		sub = DataWindow(self,self.tr('View %s: plot')%self.nSubs,self.dbFile,sql)
		sub.resize(self.MDI_AREA.width(),self.MDI_AREA.height())
		indexList = self.find_checked(self.TS_EXPLORER)
		conf = self.getConf(indexList,self.CONF)
		sub.createPlot(conf)
		self.MDI_AREA.addSubWindow(sub)
		swList = self.MDI_AREA.subWindowList()
		# connect to the first
		#~ if len(swList)>1:
			#~ firstSW = swList[0]
			#~ sub.CHART.ax.callbacks.connect('xlim_changed', firstSW.CHART.updateXLimits)
			#~ #firstSW.CHART.ax.callbacks.connect('ylim_changed', sub.CHART.updateYLimits)
			
		#~ self.ax.callbacks.connect('ylim_changed', self.on_ylims_change)
		sub.show()
		
		
	def addTable(self):
		self.nSubs+=1
		sql = self.createQuery()
		# make the model
		# make the view
		sub = DataWindow(self,self.tr('View %s: table')%self.nSubs,self.dbFile,sql)
		sub.resize(self.MDI_AREA.width(),self.MDI_AREA.height())
		sub.createTable()
		self.MDI_AREA.addSubWindow(sub)
		sub.show()
		
	def createQuery(self):
		sDate,eDate =  self.TF.getTimeLimits()
		indexList = self.find_checked(self.TS_EXPLORER)
		self.updateConf(self.CONF,indexList,'plot','True','False')
		
		sql = ''
		joinList = []
		fieldList = ['consday.timestamp AS timestamp']
		
		for layName,featList in self.CONF.items():
			for featName, featVal in featList.items():
				for c in featVal:
					if c['plot']=='True':
						# something like this
						# LEFT JOIN (SELECT * FROM idr_tmin WHERE idr_tmin.wsid = '1') as idr_tmin_sel	on consday.timestamp = idr_tmin_sel.timestamp
						newTable = '%s_%s'%(c['table'],c['id']) # make an unique table identifier in the query
						fieldList.append(newTable+"_sel.recval AS '"+c['name']+"'")
						
						joinList.append( "LEFT JOIN (SELECT timestamp,recval FROM %s WHERE %s.wsid = '%s') as %s_sel\nON consday.timestamp = %s_sel.timestamp"%(c['table'],c['table'],c['id'],newTable,newTable))
		
		if len(joinList)>0:
			# build a super query
			joinSQL = '\n'.join(joinList)
			fieldSQL =', '.join(fieldList)
			
			sql = """
					WITH RECURSIVE
					cnt(x) AS (
						 SELECT 0
						 UNION ALL
						 SELECT x+1 FROM cnt
						  LIMIT (SELECT ((julianday('%s') - julianday('%s'))) + 1)
					)
					SELECT %s FROM (SELECT date(julianday('%s'), '+' || x || ' days') AS timestamp FROM cnt) as consday
					%s
					"""%(eDate, sDate, fieldSQL,sDate,joinSQL)
					
		return sql
			
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
		
	def setupTreeWidget(self,tree,db = None):
		# populate data
		header=QTreeWidgetItem(['name'])
		tree.setHeaderItem(header)   #Another alternative is setHeaderLabels(["Tree","First",...])

		i=0
		for layName,featList in db.items():
			layParent = QTreeWidgetItem(tree)
			layParent.setText(0,layName)
			layParent.setFlags(layParent.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
			for featName, featVal in featList.items():
				featParent = QTreeWidgetItem(layParent)
				featParent.setText(0, featName)
				featParent.setFlags(featParent.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
				for v in featVal:
					item1 = QTreeWidgetItem(featParent,[v['name']])
					item1.setFlags(item1.flags() | Qt.ItemIsUserCheckable)
					item1.setCheckState(0, Qt.Unchecked)
					if (v['plot']=='True'): item1.setCheckState(0, Qt.Checked)
					
	def updateConf(self,db,indexList,attrName,newValue,altValue = None):
		l=-1
		for layName,featList in db.items():
			l+=1
			f =-1
			for featName, featVal in featList.items():
				f+=1
				v=-1
				for val in featVal:
					v+=1
					if [l,f,v] in indexList:
						db[layName][featName][v][attrName] = newValue
					else:
						if altValue:
							db[layName][featName][v][attrName] = altValue				
	
	def getConf(self, indexList,db = None,rowK= ['name','plot','color','style','axes','query']):
		# loop in each root
		res=[]
		for index in indexList:
			# 0 = layer, 1 = station, 2 = parameter
			lay = list(db.items())[index[0]]
			stationList = lay[1]
			station = list(stationList.items())[index[1]]
			parList = station[1]
			res.append(parList[index[2]])
			
		return res

					
	def find_checked(self,tree):
		# return the index of the selected items
		checked = []
		root = tree.invisibleRootItem()
		for l in range(root.childCount()):
			lay = root.child(l)
			for s in range(lay.childCount()):
				station = lay.child(s)
				for p in range(station.childCount()):
					par = station.child(p)
					if par.checkState(0) == Qt.Checked:
						checked.append([l,s,p])

		return checked

	def find_selected(self,tree):
		# return the index of the selected item (only one)
		selected = []
		selectedName = ''
		selectedItem = tree.selectedItems()
		if len(selectedItem)==1:
			selectedItem = selectedItem[0]
		else:
			print('None or more than one selected items',selectedItem)
			return selected
		
		if selectedItem.childCount() == 0:
			selectedName = selectedItem.text(0)
		
		root = tree.invisibleRootItem()
		for l in range(root.childCount()):
			lay = root.child(l)
			for s in range(lay.childCount()):
				station = lay.child(s)
				for p in range(station.childCount()):
					par = station.child(p)
					if par.text(0) == selectedName:
						selected.append([l,s,p])

		return selected

		
	def addData(self):
		# get current selected variable from treewidget
		selectIndex = self.find_selected(self.TS_EXPLORER)
		if len(selectIndex)==0:
			return
			
		conf = self.getConf(selectIndex,self.CONF)
		varName = conf[0]['name']
		tableName = conf[0]['table']
		sensId = conf[0]['id']
		
		# show dialog to set time interval
		from .dialogs.import_data import ImportData
		dlg = ImportData(self,varName,self.s)
		dlg.show()
		result = dlg.exec()
		# See if OK was pressed
		res = []
		if result == 1: 
			res = dlg.getData()
			self.importDataFromCSV(filename=res['selFile'], tablename=tableName, timeFldIdx = res['timeFldIdx'], valueFldIdx=res['valueFldIdx'], sensorId=sensId,
												skip=res['skipLines'], timeFormat =res['timeFormat'], column_sep= res['sep'], progress=None)

	def addConstantValue(self):
		# get current selected variable from treewidget
		selectIndex = self.find_selected(self.TS_EXPLORER)
		if len(selectIndex) == 0:
			return

		conf = self.getConf(selectIndex, self.CONF)
		varName = conf[0]['name']
		tableName = conf[0]['table']
		sensId = conf[0]['id']

		# show dialog to set time interval
		from .dialogs.import_data import ImportData
		dlg = ImportData(self, varName, self.s)
		dlg.show()
		result = dlg.exec()
		# See if OK was pressed
		res = []
		if result == 1:
			res = dlg.getData()
			self.importDataFromCSV(filename=res['selFile'], tablename=tableName, timeFldIdx=res['timeFldIdx'],
								   valueFldIdx=res['valueFldIdx'], sensorId=sensId,
								   skip=res['skipLines'], timeFormat=res['timeFormat'], column_sep=res['sep'],
								   progress=None)

	def removeData(self):
		# get current selected variable from treewidget
		selectIndex = self.find_selected(self.TS_EXPLORER)
		if len(selectIndex)==0:
			return
			
		conf = self.getConf(selectIndex,self.CONF)
		varName = conf[0]['name']
		tableName = conf[0]['table']
		sensId = conf[0]['id']
		
		# show dialog to set time interval
		from .dialogs.remove_data import RemoveData
		dlg = RemoveData(self,varName,self.s)
		dlg.show()
		result = dlg.exec()
		# See if OK was pressed
		res = []
		if result == 1: 
			res = dlg.getData()
			#delete meteo data from database
			# select * from idr_tmin where (date(timestamp) > date('2020-01-01')) and (date(timestamp) < date('2020-02-01')) and wsname = '100'
			#self.dbFile
			sql =  "DELETE FROM %s WHERE ((date(timestamp) >= date('%s')) and (date(timestamp) <= date('%s')) and (wsid = %s))"%(tableName, res['fromDate'],res['toDate'],sensId)
			msg = self.executeSQL(sql)
			if msg != '':
				print('Error:',msg)
			
	def executeSQL(self,sql):
		msg=''
		try:
			# start connection
			self.conn = sqlite.connect(self.dbFile)
			# creating a Cursor
			self.cur = self.conn.cursor()
			self.cur.executescript(sql)
		except Exception as e:
			msg = str(e)
		finally:
			# run VACUUM to reduce the size
			self.conn.rollback()
			#self.cur.execute('VACUUM')
			self.conn.close()
		
		return msg
		
	def importDataFromCSV(self,filename, tablename, timeFldIdx, valueFldIdx, sensorId, skip,timeFormat,column_sep, progress=None):
		msg = ''
		if progress: progress.setText(self.tr('INFO: loading %s'%filename))
		concatValues = []
		# oper CSV file
		in_file = open(filename,"r")
		i = 0
		while 1:
			in_line = in_file.readline()
			if i>=skip:
				if len(in_line) == 0:
					break
				
				# process the line
				in_line = in_line[:-1]
				#print 'LN %d: %s'%(i,in_line)
				data = in_line.split(column_sep)
				timestamp = datetime.strptime(data[timeFldIdx], timeFormat)
				value = float(data[valueFldIdx])
				
				concatValues.append("('"+ timestamp.strftime('%Y-%m-%d')+"', '"+str(sensorId)+"', '"+str(value)+"')")
			
			i+=1
		
		print('n. of imported record: %s'%len(concatValues))
		
		concatValues = ', '.join(concatValues)
		# create a temporary table to store uploaded data
		if progress: progress.setText(self.tr('INFO: creating temporary table'))
		sql = 'DROP TABLE IF EXISTS dummy;'
		sql += 'CREATE TABLE dummy (timestamp2 text, wsid2 integer, recval2 double);'
		
		msg = self.executeSQL(sql)
		if msg != '':
			print(self.tr('SQL error: %s' % msg))
			if progress:
				progress.setText(self.tr('SQL error: %s'%msg))
				progress.setText(self.tr('at: %s'%sql))
		else:
			if progress: progress.setText(self.tr('--> OK'))
			
		if progress: progress.setPercentage(30)
		
		if progress: progress.setText(self.tr('INFO: populating temporary table'))
		
		sql = 'BEGIN; '
		sql += 'REPLACE INTO dummy (timestamp2,wsid2,recval2) VALUES %s; ' %(concatValues)
		sql += 'COMMIT;'

		#print(sql)
		
		msg = self.executeSQL(sql)
		if msg != '':
			print(self.tr('SQL error: %s' % msg))
			if progress:
				progress.setText(self.tr('SQL error: %s'%msg))
				progress.setText(self.tr('at: %s'%sql))
		else:
			if progress: progress.setText(self.tr('--> OK'))
			
		if progress: progress.setPercentage(50)

		if progress: progress.setText(self.tr('INFO: updating existing values in %s'%tablename))
		# update value if they already exist
		sql ='UPDATE %s SET recval = (SELECT d.recval2 FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid)	WHERE EXISTS (SELECT * FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid);'%(tablename)
		print(sql)
		msg = self.executeSQL(sql)
		if msg != '':
			print(self.tr('SQL error: %s' % msg))
			if progress:
				progress.setText(self.tr('SQL error: %s'%msg))
				progress.setText(self.tr('at: %s'%sql))
		else:
			if progress: progress.setText(self.tr('--> OK'))
			
		if progress: progress.setPercentage(75)
		
		# copy value to tablename id they aren't
		if progress: progress.setText(self.tr('INFO: appending new values in %s'%tablename))
		sql = 'INSERT INTO %s (timestamp,wsid,recval) SELECT timestamp2,wsid2,recval2 FROM dummy d WHERE NOT EXISTS (SELECT * FROM %s WHERE timestamp = d.timestamp2 AND wsid = d.wsid2);'%(tablename,tablename)
		msg = self.executeSQL(sql)
		if msg != '':
			print(self.tr('SQL error: %s' % msg))
			if progress:
				progress.setText(self.tr('SQL error: %s'%msg))
				progress.setText(self.tr('at: %s'%sql))
		else:
			if progress: progress.setText(self.tr('--> OK'))
			
		if progress: progress.setPercentage(80)
		
		if progress: progress.setText(self.tr('INFO: removing temporary table'))
		sql = 'DROP TABLE IF EXISTS dummy;'
		msg = self.executeSQL(sql)
		if msg != '':
			print(self.tr('SQL error: %s' % msg))
			if progress:
				progress.setText(self.tr('SQL error: %s'%msg))
				progress.setText(self.tr('at: %s'%sql))
		else:
			if progress: progress.setText(self.tr('--> OK'))
			
		if progress: progress.setPercentage(90)

		if msg =='':
			if progress: progress.setText(self.tr('Importation finished! Variable %s updated for station %s'%(tablename,sensorId)))
		else:
			if progress: progress.setText(self.tr('Error: unable to import data'))
			
		if progress: progress.setPercentage(100)
	
	def exportAsCSV(self):
		# check if there is an active plot/table view
		currSub = self.MDI_AREA.currentSubWindow()
		if not currSub:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Information)
			msg.setText('Please add a table or plot to the view')
			msg.setWindowTitle('IdragraTools')
			msg.setStandardButtons(QMessageBox.Ok)
			ret = msg.exec()
			return
			
		# ask for file name
		s = QSettings('UNIMI-DISAA', 'IdragraTools')
		res = QFileDialog.getSaveFileName(self, caption = self.tr('Save to:'), directory = s.value('lastPath'), filter = 'Comma Separated file (*.csv)')
		filePath = res[0]
		if filePath == '':
			return
			
		# export data
		res = currSub.exportData(filePath)
		
		if res !='':
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Critical)
			msg.setText(self.tr('An error occured while exporting data: %s')%res)
			msg.setWindowTitle('IdragraTools')
			msg.setStandardButtons(QMessageBox.Ok)
			ret = msg.exec()
		else:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Information)
			msg.setText(self.tr('Data are exported to: %s')%filePath)
			msg.setWindowTitle('IdragraTools')
			msg.setStandardButtons(QMessageBox.Ok)
			ret = msg.exec()
			


	
if __name__ == '__console__':
	#layer = iface.activeLayer()
	dialog = DataManagerMainwindow(None,'Data manager')
	dialog.show()
