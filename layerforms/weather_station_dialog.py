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

import datetime
import numpy as np
import os

from qgis.PyQt.QtWidgets import *
from qgis.core import *


from IdragraTools.layerforms.utils import *

from IdragraTools.data_manager.chart_widget import ChartWidget

from tools.show_message import showCriticalMessageBox


def formOpen(dialog,layerid,featureid):
	global myDialog
	myDialog = dialog
	global layer
	layer = layerid
	global feature
	feature = featureid

	global objToBeEnabledList
	objToBeEnabledList = []

	# setup button
	calcLatBtn = myDialog.findChild(QToolButton,'LAT_BTN')
	calcLatBtn.clicked.connect(calcLat)
	objToBeEnabledList.append(calcLatBtn)

	calcAltBtn = myDialog.findChild(QToolButton, 'ALT_BTN')
	calcAltBtn.clicked.connect(getElevation)
	objToBeEnabledList.append(calcAltBtn)

	# enable/disable edit mode
	setEditMode(layer.isEditable())

	wsid = myDialog.findChild(QLineEdit,'id').text()

	res = {}
	if wsid not in ['','Autogenerate']:
		res = qgis.utils.plugins['IdragraTools'].getData(
			list(qgis.utils.plugins['IdragraTools'].METEONAME.keys()),
			int(wsid))
	else:
		return

	#populate table
	table = myDialog.findChild(QTableWidget,'stat_TB')

	# Row count
	table.setRowCount(len(res['varName']))

	varList = list(qgis.utils.plugins['IdragraTools'].STATS.keys())
	varList.remove('varName')
	# Column count
	table.setColumnCount(len(varList))

	for c,statKey in enumerate(varList):
		# set cell value
		valueList = res[statKey]
		for r,val in enumerate(valueList):
			if isinstance(val,datetime.datetime):
				val = val.strftime('%Y-%m-%d')

			table.setItem(r, c, QTableWidgetItem(str(val)))

	table.setHorizontalHeaderLabels(list(qgis.utils.plugins['IdragraTools'].STATS.values())[1:])
	table.setVerticalHeaderLabels(res['varName'])
	table.horizontalHeader().setStretchLastSection(True)
	table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

	msg = qgis.utils.plugins['IdragraTools'].checkData(res)
	myDialog.findChild(QTextBrowser,'MSG_TE').setText(msg)

	PLOT_METEO_VARS_BTN = myDialog.findChild(QPushButton,'PLOT_METEO_VARS_BTN')
	# for some reason, forms are initialized twice ...
	if PLOT_METEO_VARS_BTN.receivers(PLOT_METEO_VARS_BTN.clicked)==0:
		PLOT_METEO_VARS_BTN.clicked.connect(lambda: plotMeteoVars(int(myDialog.findChild(QLineEdit,'id').text()),
																					myDialog.findChild(QLineEdit,'name').text()))

	global PLOT_HEATMAP_CB
	PLOT_HEATMAP_CB = myDialog.findChild(QComboBox, 'PLOT_HEATMAP_CB')
	# add items
	inv_map = {qgis.utils.plugins['IdragraTools'].tr('Heat map from...'):'no_sel'}
	for k, v in qgis.utils.plugins['IdragraTools'].METEONAME.items():
		inv_map[v]=k

	updateComboItems(PLOT_HEATMAP_CB,inv_map)
	# for some reason, forms are initialized twice ...
	if PLOT_HEATMAP_CB.receivers(PLOT_HEATMAP_CB.currentIndexChanged) == 0:
		PLOT_HEATMAP_CB.currentIndexChanged.connect(lambda x: plotSingleMeteoDistro(int(myDialog.findChild(QLineEdit, 'id').text()),
																  myDialog.findChild(QLineEdit, 'name').text(),
																				  int(x)))

	global PLOT_PHENO_VARS_CB
	PLOT_PHENO_VARS_CB = myDialog.findChild(QComboBox, 'PLOT_PHENO_VARS_CB')
	# add items
	inv_map = {qgis.utils.plugins['IdragraTools'].tr('Plot pheno vars...'): 'no_sel'}
	for k, v in qgis.utils.plugins['IdragraTools'].PHENOVARS.items():
		inv_map[v] = k

	updateComboItems(PLOT_PHENO_VARS_CB, inv_map)
	# for some reason, forms are initialized twice ...
	if PLOT_PHENO_VARS_CB.receivers(PLOT_PHENO_VARS_CB.currentIndexChanged) == 0:
		PLOT_PHENO_VARS_CB.currentIndexChanged.connect(
			lambda x: plotPheno(int(myDialog.findChild(QLineEdit, 'id').text()),
											int(x)))

	# connect start edit button to setEditMode to get edit tool pressed
	#qgis.utils.plugins['IdragraTools'].iface.actionToggleEditing().toggled[bool].connect(setEditMode)
	try:
		parentForm = myDialog.window()
		act = parentForm.findChild(QAction,'mActionToggleEditing')
		if act: act.toggled[bool].connect(setEditMode)
	except Exception as e:
		print('error: %s'%str(e))

def calcLat():
	tr = qgis.utils.plugins['IdragraTools'].tr
	latTE = myDialog.findChild(QLineEdit,'lat')
	fromCRS = QgsProject.instance().crs()
	toCRS = QgsCoordinateReferenceSystem('EPSG:4326')
	coordtr = QgsCoordinateTransform(fromCRS, toCRS, QgsProject.instance())
	try:
		geom = feature.geometry()
		geom.transform(coordtr)
		latTE.setText(str(geom.asMultiPoint()[0].y()))
	except Exception as e:
		showCriticalMessageBox(text=tr('Not supported'),
							   infoText=tr('This function is not supported in table view'),
							   detailText=str(e))

def showEditDialog(wsId,name):
	# make a dialog
	from IdragraTools.layerforms.weather_manager_dialog import WeatherManagerDialog
	tr = qgis.utils.plugins['IdragraTools'].tr
	dlg = WeatherManagerDialog(myDialog, qgis.utils.plugins['IdragraTools'].DBM.DBName,wsId,tr('Data of %s'%name))
	dlg.resize(0.9*myDialog.geometry().width(),myDialog.geometry().height())
	# make the model with data
	dlg.show()


def plotMeteoVars(wsId,name):
	# make a dialog
	tr = qgis.utils.plugins['IdragraTools'].tr
	cw = ChartWidget(myDialog, '', False, False)

	cw.setAxis(pos=311 , secondAxis=True, label = ['Temp','Prec'])
	# add timeseries
	plotList =  [
						{'name':qgis.utils.plugins['IdragraTools'].METEONAME['ws_ptot'],'plot':'True','color':'#416FA6','style': '-','axes':'y','table':'ws_ptot','id':wsId},
						{'name':qgis.utils.plugins['IdragraTools'].METEONAME['ws_tmax'],'plot':'True','color':'#A8423F','style': '-','axes':'y2','table':'ws_tmax','id':wsId},
						{'name':qgis.utils.plugins['IdragraTools'].METEONAME['ws_tmin'],'plot':'True','color':'#4198AF','style': '-','axes':'y2','table':'ws_tmin','id':wsId}
						]

	y1Title = []
	y2Title = []
	for p in plotList:
		shadow = False
		if p['table']=='ws_ptot':
			shadow = p['color']+'29'
		# get data
		dateTimeList, values = qgis.utils.plugins['IdragraTools'].DBM.getTimeSeries(p['table'],p['id'])
		print('ws:',type(dateTimeList[0]))
		#dateTimeList = [np.datetime64(dt) for dt in dateTimeList]
		print('ws:', type(dateTimeList[0]))
		cw.addTimeSerie(dateTimeList,values,lineType='-',color=p['color'],name = p['name'],yaxis = p['axes'],shadow= shadow)
		if p['axes']=='y': y1Title.append(p['name'])
		if p['axes']=='y2': y2Title.append(p['name'])

	# flip y axes
	cw.flipAxes(x1 = None, y1 = True, x2 = None, y2 = None)

	# set title
	cw.setTitles(xlabs=None, ylabs=None, xTitle=None, yTitle=', '.join(y1Title), y2Title=', '.join(y2Title),
				 mainTitle=None)

	# second plot
	cw.setAxis(pos=312 , secondAxis=False,label = ['Humidity'])
	# add timeseries
	plotList =  [
						{'name':qgis.utils.plugins['IdragraTools'].METEONAME['ws_umax'],'plot':'True','color':'#86A44A','style': '-','axes':'y','table':'ws_umax','id':wsId},
						{'name':qgis.utils.plugins['IdragraTools'].METEONAME['ws_umin'],'plot':'True','color':'#6E548D','style': '-','axes':'y','table':'ws_umin','id':wsId}
					]

	y1Title = []
	y2Title = []
	for p in plotList:
		shadow = False
		if p['table']=='ws_ptot':
			shadow = p['color']+'29'
		# get data
		dateTimeList, values = qgis.utils.plugins['IdragraTools'].DBM.getTimeSeries(p['table'],p['id'])
		cw.addTimeSerie(dateTimeList,values,lineType='-',color=p['color'],name = p['name'],yaxis = p['axes'],shadow= shadow)
		if p['axes']=='y': y1Title.append(p['name'])
		if p['axes']=='y2': y2Title.append(p['name'])

	# set title
	cw.setTitles(xlabs = None, ylabs = None, xTitle = None, yTitle = ', '.join(y1Title), y2Title = ', '.join(y2Title), mainTitle = None)

	# flip y axes
	#dlg.flipAxes(x1 = None, y1 = True, x2 = None, y2 = None)

	# third plot
	cw.setAxis(pos=313 , secondAxis=True, label = ['Wind','Radiation'])
	# add timeseries
	plotList =  [
						{'name':qgis.utils.plugins['IdragraTools'].METEONAME['ws_vmed'],'plot':'True','color':'#DA8137','style': '-','axes':'y','table':'ws_vmed','id':wsId},
						{'name':qgis.utils.plugins['IdragraTools'].METEONAME['ws_rgcorr'],'plot':'True','color':'#8EA5CB','style': '-','axes':'y2','table':'ws_rgcorr','id':wsId}
					]

	y1Title = []
	y2Title = []
	for p in plotList:
		shadow = False
		if p['table']=='ws_ptot':
			shadow = p['color']+'29'
		# get data
		dateTimeList, values = qgis.utils.plugins['IdragraTools'].DBM.getTimeSeries(p['table'],p['id'])
		cw.addTimeSerie(dateTimeList,values,lineType='-',color=p['color'],name = p['name'],yaxis = p['axes'],shadow= shadow)
		if p['axes']=='y': y1Title.append(p['name'])
		if p['axes']=='y2': y2Title.append(p['name'])

	# set title
	cw.setTitles(xlabs = None, ylabs = None, xTitle = None, yTitle = ', '.join(y1Title), y2Title = ', '.join(y2Title), mainTitle = None)

	# add chart to dialog
	dlg = QMainWindow(myDialog)
	dlg.setCentralWidget(cw)
	dlg.show()


def plotSingleMeteoDistro(wsId,name,varIdx):
	PLOT_HEATMAP_CB.setCurrentIndex(0)
	# make a dialog
	tr = qgis.utils.plugins['IdragraTools'].tr
	dict = qgis.utils.plugins['IdragraTools'].METEONAME
	varIdx = varIdx-1 # delete first
	if varIdx<0:
		# no var case
		return

	cRamps = {'ws_tmin': 'winter', 'ws_tmax': 'summer',
			 'ws_ptot': 'Blues',
			 'ws_umin': 'PuBuGn', 'ws_umax':'YlOrRd',
			 'ws_vmed': 'Oranges', 'ws_rgcorr': 'Purples_r',
			 'ws_co2':'Greys'}

	cw = ChartWidget(myDialog, '', False, False)

	k = list(dict.keys())[varIdx]
	cw.setAxis(pos=111, secondAxis=False,label = [dict[k]])
	data2D, startYear, endYear = createArray(wsId,k)
	yList = []
	if (startYear and endYear):
		yList = list(range(startYear, endYear + 1))

	cw.addHeadMap(data2D, list(range(1, 367)), yList,True,cRamps[k])
	cw.setTitles(mainTitle=dict[k])

	cw.fixLayout()

	# add chart to dialog
	dlg = QMainWindow(myDialog)
	dlg.setCentralWidget(cw)
	dlg.show()

def plotPheno(wsId,varIdx):
	tr = qgis.utils.plugins['IdragraTools'].tr
	PLOT_PHENO_VARS_CB.setCurrentIndex(0)
	# make a dialog
	varIdx = varIdx-1 # delete first
	if varIdx<0:
		# no var case
		return

	import matplotlib.pyplot as plt
	phenovars = qgis.utils.plugins['IdragraTools'].PHENOVARS
	# get var id to plot, is the same name of the output file of cropcoef
	varId = list(phenovars.keys())[varIdx]
	phenos,msg = qgis.utils.plugins['IdragraTools'].readCropCoefReasults(varId,wsId)
	if phenos is None:
		showCriticalMessageBox(tr('It\'s like there is no data to plot'),tr('Please, check if the file exists and it is correctly formatted'),msg)
		return

	# make a plot
	cw = ChartWidget(myDialog, '', False, False)
	cw.setAxis(pos=111, secondAxis=False, label=['main chart'])
	timestamp = phenos['timestamp'].values
	nOfSeries = len(list(phenos.keys()))
	colList = plt.cm.get_cmap('tab20', nOfSeries)
	for i,landuse in enumerate(list(phenos.keys())):
		if landuse != 'timestamp':
			cw.addTimeSerie(timestamp, phenos[landuse].values,'-',colList(i/nOfSeries),landuse,1,False)

	cw.setTitles(yTitle=list(phenovars.values())[varIdx])

	cw.fixLayout()

	# add chart to dialog
	dlg = QMainWindow(myDialog)
	dlg.setCentralWidget(cw)
	dlg.show()

def createArray(wsId,tableName = 'ws_ptot'):

	# create the 2d matrix
	dateTimeList, values = qgis.utils.plugins['IdragraTools'].DBM.getTimeSeries(tableName, wsId)
	if len(dateTimeList)==0:
		return None,None, None

	# get first and last year of the serie
	startYear = dateTimeList[0].year
	endYear = dateTimeList[-1].year
	nOfYear = endYear-startYear+1

	# make a fake list of day of the years values
	dayOfYears = list(range(1,367))*nOfYear

	# make a new list of value
	newListOfValues = [np.NAN]*366*nOfYear

	#replace value
	for i,ts in enumerate(dateTimeList):
		currentYear = ts.year
		# fake day of the year, always 366 days/years
		dayOfYear = (datetime.datetime(2000,ts.month,ts.day) - datetime.datetime(2000,1,1)).days
		# if currentYear == startYear: print(ts,dayOfYear)
		offset = (currentYear - startYear)*366
		idx = offset+dayOfYear
		newListOfValues[idx]= values[i]

	# make a 2d array
	data2D = np.array(newListOfValues,np.float32)
	data2D = np.reshape(data2D,(nOfYear,366))

	return data2D,startYear,endYear

def setEditMode(mode):
	if feature:
		try:
			for obj in objToBeEnabledList:
				obj.setEnabled(mode)
		except Exception as e:
			print('error: %s'%str(e))

def getElevation():
	tr = qgis.utils.plugins['IdragraTools'].tr
	# get raster layer
	try:
		rasteName = qgis.utils.plugins['IdragraTools'].SIMDIC['RASTER']['elevation']
		rasterLay = QgsRasterLayer(rasteName,'dtm')
	except Exception as e:
		rasterLay = None
		showCriticalMessageBox(text=tr('DTM map not found'),
							   infoText=tr('This function needs a valid DTM map loaded in the IdrAgraTools project'),
							   detailText=str(e))

	if rasterLay:
		# if exists ok
		try:
			pointGeom = feature.geometry()
			pointGeom.convertToSingleType()
			pointPoint = pointGeom.asPoint()
			res = rasterLay.dataProvider().identify(pointPoint, QgsRaster.IdentifyFormatValue).results()
			if len(res)>0:
				altTE = myDialog.findChild(QLineEdit, 'alt')
				altTE.setText(str(res[1]))
		except Exception as e:
			showCriticalMessageBox(text=tr('Not supported'),
								   infoText=tr('This function is not supported in table view'),
								   detailText=str(e))
if __name__ == '__console__':
	pass
