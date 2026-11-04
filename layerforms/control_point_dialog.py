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

from qgis.PyQt.QtWidgets import QPushButton, QLineEdit, QDialog, QMainWindow, QLabel

from data_manager.chart_widget import ChartWidget

from tools.show_message import showInfoMessageBox,showCriticalMessageBox


def formOpen(dialog,layerid,featureid):
	global myDialog
	myDialog = dialog
	global layer
	layer = layerid
	global feature
	feature = featureid

	PLOT_EVA_WC = myDialog.findChild(QPushButton,'PLOT_EVA_WC')
	# for some reason, forms are initialized twice ...
	if PLOT_EVA_WC.receivers(PLOT_EVA_WC.clicked)==0:
		PLOT_EVA_WC.clicked.connect(lambda: plotEvaWC(
			int(myDialog.findChild(QLineEdit,'id').text()),
			myDialog.findChild(QLineEdit,'name').text()))

	PLOT_TRANS_WC = myDialog.findChild(QPushButton, 'PLOT_TRANS_WC')
	# for some reason, forms are initialized twice ...
	if PLOT_TRANS_WC.receivers(PLOT_TRANS_WC.clicked) == 0:
		PLOT_TRANS_WC.clicked.connect(lambda: plotTransWC(
			int(myDialog.findChild(QLineEdit, 'id').text()),
			myDialog.findChild(QLineEdit, 'name').text()))

	PLOT_EVA_VARS = myDialog.findChild(QPushButton, 'PLOT_EVA_VARS')
	# for some reason, forms are initialized twice ...
	if PLOT_EVA_VARS.receivers(PLOT_EVA_VARS.clicked) == 0:
		PLOT_EVA_VARS.clicked.connect(lambda: plotEvaVars(
			int(myDialog.findChild(QLineEdit, 'id').text()),
			myDialog.findChild(QLineEdit, 'name').text()))

	PLOT_TRANS_VARS = myDialog.findChild(QPushButton, 'PLOT_TRANS_VARS')
	# for some reason, forms are initialized twice ...
	if PLOT_TRANS_VARS.receivers(PLOT_TRANS_VARS.clicked) == 0:
		PLOT_TRANS_VARS.clicked.connect(lambda: plotTransVars(
			int(myDialog.findChild(QLineEdit, 'id').text()),
			myDialog.findChild(QLineEdit, 'name').text()))

	PLOT_IRR_EVS = myDialog.findChild(QPushButton, 'PLOT_IRR_EVS')
	# for some reason, forms are initialized twice ...
	if PLOT_IRR_EVS.receivers(PLOT_IRR_EVS.clicked) == 0:
		PLOT_IRR_EVS.clicked.connect(lambda: plotIrrEvents(
			int(myDialog.findChild(QLineEdit, 'id').text()),
			myDialog.findChild(QLineEdit, 'name').text()))

	PLOT_CROP_VARS = myDialog.findChild(QPushButton, 'PLOT_CROP_VARS')
	# for some reason, forms are initialized twice ...
	if PLOT_CROP_VARS.receivers(PLOT_CROP_VARS.clicked) == 0:
		PLOT_CROP_VARS.clicked.connect(lambda: plotCropVars(
			int(myDialog.findChild(QLineEdit, 'id').text()),
			myDialog.findChild(QLineEdit, 'name').text()))

	#setInfoLabel()
	INFO_LBL = myDialog.findChild(QLabel, 'INFO_LBL')
	tr = qgis.utils.plugins['IdragraTools'].tr

	# hide plot buttons if feature is
	if not feature.geometry():
		PLOT_EVA_WC.setHidden(True)
		PLOT_EVA_VARS.setHidden(True)
		PLOT_TRANS_WC.setHidden(True)
		PLOT_TRANS_VARS.setHidden(True)
		PLOT_CROP_VARS.setHidden(True)
		INFO_LBL.setHidden(True)
	else:
		r, c = qgis.utils.plugins['IdragraTools'].getRowCol(feature)
		INFO_LBL.setText(tr('Cell coordinates (row,column): %s,%s') % (r, c))

def plotEvaWC(wsId,name):
	tr = qgis.utils.plugins['IdragraTools'].tr

	# get data
	simdic = qgis.utils.plugins['IdragraTools'].SIMDIC
	r,c = qgis.utils.plugins['IdragraTools'].getRowCol(feature)
	df, msg =  qgis.utils.plugins['IdragraTools'].readControlPointsResults(r,c,None,['Giulian_day','theta1_mm'])

	if df is None:
		showCriticalMessageBox(tr('It\'s like there is no data to plot'),tr('Please, check if file exist'),msg)
		return

	pars, msgPars =  qgis.utils.plugins['IdragraTools'].readControlPointsParams(r, c, [],['ThetaI_fc','ThetaI_wp'])

	cw = ChartWidget(myDialog, '', False, False)
	cw.setAxis(pos=111, secondAxis=False, label=['main plot'])

	if df is not None:
		df['theta1_mm'] = df['theta1_mm']/(simdic['ZEVALAY'] * 1000)
		#dlg = ChartDialog(myDialog, tr('Water content from %s' % name))
		cw.addTimeSerie(df['Giulian_day'].values, df['theta1_mm'].values,
						 lineType='-', color='#4A7EBB', name=tr('Soil water content (-)'),
						 yaxis=1,
						 shadow=False)
	if pars is not None:
		cw.addTimeSerie(pars['timestamp'].values, pars['ThetaI_wp'].values, lineType='-', color='#BE4B48',
						 name=tr('Wilting point (-)'), yaxis=1, shadow=False)
		cw.addTimeSerie(pars['timestamp'].values, pars['ThetaI_fc'].values,lineType='-',color='#98B954',
						name = tr('Field capacity (-)'), yaxis = 1,shadow= False)

	dlg = QMainWindow(myDialog)
	dlg.setWindowTitle(tr('1st layer WC'))
	dlg.setCentralWidget(cw)
	dlg.show()


def plotTransWC(wsId,name):
	tr = qgis.utils.plugins['IdragraTools'].tr

	# get data
	simdic = qgis.utils.plugins['IdragraTools'].SIMDIC
	r, c = qgis.utils.plugins['IdragraTools'].getRowCol(feature)
	df, msg = qgis.utils.plugins['IdragraTools'].readControlPointsResults(r, c, None, ['Giulian_day', 'pday','theta2_mm','thickness_II_m'])
	pars, msgPars = qgis.utils.plugins['IdragraTools'].readControlPointsParams(r, c, [], ['ThetaII_fc', 'ThetaII_wp'])

	if df is None:
		showCriticalMessageBox(tr('It\'s like there is no data to plot'),tr('Please, check if file exists'),msg)
		return

	cw = ChartWidget(myDialog, '', False, False)
	cw.setAxis(pos=111, secondAxis=False, label=['main plot'])

	print('cp:',type(df['Giulian_day'].values[0]))

	if df is not None:
		df['theta2'] = df['theta2_mm'] / (df['thickness_II_m'] * 1000)
		# dlg = ChartDialog(myDialog, tr('Water content from %s' % name))
		cw.addTimeSerie(df['Giulian_day'].values, df['theta2'].values,
						lineType='-', color='#4A7EBB', name=tr('Soil water content (-)'),
						yaxis=1,
						shadow=False)

	if pars is not None:
		cw.addTimeSerie(pars['timestamp'].values, pars['ThetaII_wp'].values, lineType='-', color='#BE4B48',
						name=tr('Wilting point (-)'), yaxis=1, shadow=False)
		cw.addTimeSerie(pars['timestamp'].values, pars['ThetaII_fc'].values, lineType='-', color='#98B954',
						name=tr('Field capacity (-)'), yaxis=1, shadow=False)

	if ((df is not None) and (pars is not None)):
		#df['RAWlim']
		df['RAWlim'] = (pars['ThetaII_fc'] - df['pday'] * (pars['ThetaII_fc'] - pars['ThetaII_wp']))

		cw.addTimeSerie(df['Giulian_day'].values, df['RAWlim'].values,
						lineType='-', color='#7d60a0', name=tr('RAW limit (-)'),
						yaxis=1,
						shadow=False)

	dlg = QMainWindow(myDialog)
	dlg.setWindowTitle(tr('2nd layer WC'))
	dlg.setCentralWidget(cw)
	dlg.show()


def plotEvaVars(wsId,name):
	tr = qgis.utils.plugins['IdragraTools'].tr

	r, c = qgis.utils.plugins['IdragraTools'].getRowCol(feature)
	df, msg = qgis.utils.plugins['IdragraTools'].readControlPointsResults(r, c,
																		  None, ['Giulian_day', 'rain_mm','irrig_mm','theta1_mm','interception_mm',
																				 'runoff_mm','eva_mm','perc1_mm'])

	if df is None:
		showCriticalMessageBox(tr('It\'s like there is no data to plot'),tr('Please, check if file exist'),msg)
		return

	# make a dialog
	cw = ChartWidget(myDialog, '', False, False)
	cw.setAxis(pos=211, secondAxis=False,label = ['External vars'])

	# add timeseries
	plotList =  [
						{'name':qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_rain_mm'],'plot':'True','color':'#416FA6','style': '-','axes':'y','table':'rain_mm','id':wsId},
						{'name':qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_irrig_mm'],'plot':'True','color':'#A8423F','style': '-','axes':'y','table':'irrig_mm','id':wsId},
						]

	y1Title = []
	if df is not None:
		for p in plotList:
			shadow = False
			if p['table']=='theta1_mm':
				shadow = p['color']+'29'
				p['color'] = p['color']+'00'
			# get data
			dateTimeList = df['Giulian_day'].values
			values = df[p['table']].values
			cw.addTimeSerie(dateTimeList,values,lineType='-',color=p['color'],name = p['name'],yaxis = p['axes'],shadow= shadow)
			if p['axes']=='y': y1Title.append(p['name'])

	# set title
	cw.setTitles(xlabs = None, ylabs = None, xTitle = None, yTitle = ',\n'.join(y1Title), y2Title = None, mainTitle = None)

	# flip y axes
	cw.flipAxes(x1 = None, y1 = True, x2 = None, y2 = None)

	cw.setAxis(pos=212, secondAxis=False,label = ['Internal vars'])

	# add timeseries
	plotList = [
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_theta1_mm'], 'plot': 'True', 'color': '#4198AF',
		 'style': '-', 'axes': 'y', 'table': 'theta1_mm', 'id': wsId},
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_interception_mm'], 'plot': 'True', 'color': '#86A44A',
		 'style': '-', 'axes': 'y', 'table': 'interception_mm', 'id': wsId},
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_runoff_mm'], 'plot': 'True', 'color': '#6E548D',
		 'style': '-', 'axes': 'y', 'table': 'runoff_mm', 'id': wsId},
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_eva_mm'], 'plot': 'True', 'color': '#DA8137',
		 'style': '-', 'axes': 'y', 'table': 'eva_mm', 'id': wsId},
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_perc1_mm'], 'plot': 'True', 'color': '#8EA5CB',
		 'style': '-', 'axes': 'y', 'table': 'perc1_mm', 'id': wsId}
	]

	y1Title = []
	if df is not None:
		for p in plotList:
			shadow = False
			if p['table'] == 'theta1_mm':
				shadow = p['color'] + '29'
				p['color'] = p['color'] + '00'
			# get data
			dateTimeList = df['Giulian_day'].values
			values = df[p['table']].values
			cw.addTimeSerie(dateTimeList, values, lineType='-', color=p['color'], name=p['name'], yaxis=p['axes'],
							shadow=shadow)
			if p['axes'] == 'y': y1Title.append(p['name'])

	# set title
	cw.setTitles(xlabs=None, ylabs=None, xTitle=None, yTitle=',\n'.join(y1Title), y2Title=None,
				 mainTitle=None)

	# add chart to dialog
	dlg = QMainWindow(myDialog)
	dlg.setWindowTitle(tr('1st layer vars.'))
	dlg.setCentralWidget(cw)
	dlg.show()

def plotTransVars(wsId,name):
	tr = qgis.utils.plugins['IdragraTools'].tr

	r, c = qgis.utils.plugins['IdragraTools'].getRowCol(feature)
	# try:
	# 	df, msg = qgis.utils.plugins['IdragraTools'].readControlPointsResults(r, c,
	# 																		  None, ['Giulian_day', 'perc1_mm', 'capflux_mm',
	# 																				 'theta2_mm', 'trasp_act_mm',
	# 																				 'perc2_mm'])
	# except:
	df, msg = qgis.utils.plugins['IdragraTools'].readControlPointsResults(r, c,
																		  None,
																		  ['Giulian_day', 'perc1_mm', 'capflux_mm',
																		   'theta2_mm',  'trasp_act1_mm', 'trasp_act2_mm',
																		   'perc2_mm'])
	version = 2.

	if df is None:
		showCriticalMessageBox(tr('It\'s like there is no data to plot'),tr('Please, check if file exist'),msg)
		return

	# TODO: manage also older version with df['trasp_act_mm']
	df['trasp_act_mm']= df['trasp_act1_mm']+df['trasp_act2_mm']

	# make a dialog
	tr = qgis.utils.plugins['IdragraTools'].tr
	cw = ChartWidget(myDialog, '', False, False)
	cw.setAxis(pos=211, secondAxis=False, label=['External vars'])

	# add timeseries
	plotList = [
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_perc1_mm'], 'plot': 'True', 'color': '#416FA6',
		 'style': '-', 'axes': 'y', 'table': 'perc1_mm', 'id': wsId},
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_capflux_mm'], 'plot': 'True', 'color': '#A8423F',
		 'style': '-', 'axes': 'y', 'table': 'capflux_mm', 'id': wsId},
	]

	y1Title = []
	if df is not None:
		for p in plotList:
			shadow = False
			if p['table'] == 'theta1_mm':
				shadow = p['color'] + '29'
				p['color'] = p['color'] + '00'
			# get data
			dateTimeList = df['Giulian_day'].values
			values = df[p['table']].values
			cw.addTimeSerie(dateTimeList, values, lineType='-', color=p['color'], name=p['name'], yaxis=p['axes'],
							shadow=shadow)
			if p['axes'] == 'y': y1Title.append(p['name'])

	# set title
	cw.setTitles(xlabs=None, ylabs=None, xTitle=None, yTitle=',\n'.join(y1Title), y2Title=None, mainTitle=None)

	# flip y axes
	cw.flipAxes(x1=None, y1=True, x2=None, y2=None)

	cw.setAxis(pos=212, secondAxis=False, label=['Internal vars'])

	# add timeseries
	plotList = [
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_theta2_mm'], 'plot': 'True', 'color': '#4198AF',
		 'style': '-', 'axes': 'y', 'table': 'theta2_mm', 'id': wsId},
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_trasp_act_mm'], 'plot': 'True', 'color': '#86A44A',
		 'style': '-', 'axes': 'y', 'table': 'trasp_act_mm', 'id': wsId},
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_perc2_mm'], 'plot': 'True', 'color': '#6E548D',
		 'style': '-', 'axes': 'y', 'table': 'perc2_mm', 'id': wsId}
	]


	y1Title = []
	if df is not None:
		for p in plotList:
			shadow = False
			if p['table'] == 'theta2_mm':
				shadow = p['color'] + '29'
				p['color'] = p['color'] + '00'
			# get data
			dateTimeList = df['Giulian_day'].values
			values = df[p['table']].values
			cw.addTimeSerie(dateTimeList, values, lineType='-', color=p['color'], name=p['name'], yaxis=p['axes'],
							shadow=shadow)
			if p['axes'] == 'y': y1Title.append(p['name'])

	# set title
	cw.setTitles(xlabs=None, ylabs=None, xTitle=None, yTitle=',\n'.join(y1Title), y2Title=None,
				 mainTitle=None)

	# add chart to dialog
	dlg = QMainWindow(myDialog)
	dlg.setWindowTitle(tr('2nd layer vars.'))
	dlg.setCentralWidget(cw)
	dlg.show()


def plotIrrEvents(wsId,name):
	tr = qgis.utils.plugins['IdragraTools'].tr

	settings = qgis.utils.plugins['IdragraTools'].SIMDIC

	r, c = qgis.utils.plugins['IdragraTools'].getRowCol(feature)
	# try:
	# 	df, msg = qgis.utils.plugins['IdragraTools'].readControlPointsResults(r, c,
	# 																		  None, ['Giulian_day', 'perc1_mm', 'capflux_mm',
	# 																				 'theta2_mm', 'trasp_act_mm',
	# 																				 'perc2_mm'])
	# except:
	df, msg = qgis.utils.plugins['IdragraTools'].readControlPointsResults(r, c,
																		  None,
																		  ['Giulian_day','rain_mm','pday','rawbig',
																		   'rawinf','theta1_mm','theta_old_mm',
																		   'irrig_mm','thickness_II_m'])

	if df is None:
		showCriticalMessageBox(tr('It\'s like there is no data to plot'),tr('Please, check if file exist'),msg)
		return

	version = 2.
	df['theta1_mm']=df['theta1_mm'].shift(1)
	df['theta_mm'] = df['theta1_mm'] + df['theta_old_mm']
	# make a shift
	#df['theta_mm']=df['theta_mm'].shift(1)
	pars, msgPars = qgis.utils.plugins['IdragraTools'].readControlPointsParams(r, c, [],
																			   ['ThetaI_fc', 'ThetaI_wp',
																				'ThetaII_fc', 'ThetaII_wp'])

	# calculate RAW
	# wat%layer(1)%fc + wat%layer(2)%fc - (wat%layer(1)%fc - wat%layer(1)%wp +
	# wat%layer(2)%fc-wat%layer(2)%wp)*pheno%pday
	df['fc1'] = pars['ThetaI_fc'] * settings['ZEVALAY'] * 1000.
	df['wp1'] = pars['ThetaI_wp'] * settings['ZEVALAY'] * 1000.
	df['fc2'] = pars['ThetaII_fc'] * df['thickness_II_m'] * 1000.
	df['wp2'] = pars['ThetaII_wp'] * df['thickness_II_m'] * 1000.

	# TODO: control points results should be updated in order to include also RAW
	# the solution proposed above is prone to error if current ZEVALAY is not the same as the project
	# alternatively, the read_idragra_parameters function should be used
	df['RAW'] = df['fc1']+df['fc2'] - (df['fc1']-df['wp1']+df['fc2']-df['wp2'])*df['pday']
	df['fc_tot'] = df['fc1']+df['fc2']
	df['wp_tot'] = df['wp1'] + df['wp2']

	# make a dialog
	cw = ChartWidget(myDialog, '', False, False)
	cw.setAxis(pos=211, secondAxis=False,label = ['External vars'])

	# add timeseries
	plotList =  [
						{'name':qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_rain_mm'],'plot':'True','color':'#416FA6','style': '-','axes':'y','table':'rain_mm','id':wsId},
						{'name':qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_irrig_mm'],'plot':'True','color':'#A8423F','style': '-','axes':'y','table':'irrig_mm','id':wsId},
						]

	y1Title = []
	if df is not None:
		for p in plotList:
			shadow = False
			if p['table']=='theta1_mm':
				shadow = p['color']+'29'
				p['color'] = p['color']+'00'
			# get data
			dateTimeList = df['Giulian_day'].values
			values = df[p['table']].values
			cw.addTimeSerie(dateTimeList,values,lineType='-',color=p['color'],name = p['name'],yaxis = p['axes'],shadow= shadow)
			if p['axes']=='y': y1Title.append(p['name'])

	# set title
	cw.setTitles(xlabs = None, ylabs = None, xTitle = None,
				 yTitle = None, y2Title = None, mainTitle = None)

	# flip y axes
	cw.flipAxes(x1 = None, y1 = True, x2 = None, y2 = None)

	cw.setAxis(pos=212, secondAxis=False,label = ['Internal vars'])

	# add timeseries
	plotList = [
		{'name': tr('SWC (mm)'), 'plot': 'True', 'color': '#4198AF',
		 'style': '-', 'axes': 'y', 'table': 'theta_mm', 'id': wsId},
		{'name': tr('SWC at RAW limit (mm)'), 'plot': 'True', 'color': '#7d60a0',
		 'style': '-', 'axes': 'y', 'table': 'RAW', 'id': wsId},
		{'name': tr('SWC at FC (mm)'), 'plot': 'True', 'color': '#98B954',
		 'style': '--', 'axes': 'y', 'table': 'fc_tot', 'id': wsId},
		{'name': tr('SWC at WP (mm)'), 'plot': 'True', 'color': '#BE4B48',
		 'style': '--', 'axes': 'y', 'table': 'wp_tot', 'id': wsId},
		{'name': tr('Irrigation threshold (mm)'), 'plot': 'True', 'color': '#416FA6',
		 'style': '-', 'axes': 'y', 'table': 'rawbig', 'id': wsId}
	]

	y1Title = []
	y2Title = []

	if df is not None:
		for p in plotList:
			shadow = False
			if p['table'] == 'theta_mm':
				shadow = p['color'] + '29'
				p['color'] = p['color'] + '00'
			# get data
			dateTimeList = df['Giulian_day'].values
			values = df[p['table']].values
			cw.addTimeSerie(dateTimeList, values, lineType=p['style'], color=p['color'], name=p['name'], yaxis=p['axes'],
							shadow=shadow)
			if p['axes'] == 'y': y1Title.append(p['name'])
			else: y2Title.append(p['name'])

	# set title
	cw.setTitles(xlabs=None, ylabs=None, xTitle=None,
				 yTitle=None, y2Title=None, mainTitle=None)

	# flip y axes
	cw.flipAxes(x1=None, y1=None, x2=None, y2=None)

	# add chart to dialog
	dlg = QMainWindow(myDialog)
	dlg.setWindowTitle(tr('Irrigation events'))
	dlg.setCentralWidget(cw)
	dlg.show()


def plotCropVars(wsId,name):
	tr = qgis.utils.plugins['IdragraTools'].tr

	r, c = qgis.utils.plugins['IdragraTools'].getRowCol(feature)
	df, msg = qgis.utils.plugins['IdragraTools'].readControlPointsResults(r, c,
																		  None, ['Giulian_day', 'kcb', 'lai'])
	if df is None:
		showCriticalMessageBox(tr('It\'s like there is no data to plot'),tr('Please, check if file exist'),msg)
		return

	# make a dialog
	tr = qgis.utils.plugins['IdragraTools'].tr
	cw = ChartWidget(myDialog, '', False, False)
	cw.setAxis(pos=211, secondAxis=False, label=['External vars'])

	# add timeseries
	plotList = [
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_kcb'], 'plot': 'True', 'color': '#c87137ff',
		 'style': '-', 'axes': 'y', 'table': 'kcb', 'id': wsId},
	]

	y1Title = []
	if df is not None:
		for p in plotList:
			shadow = False
			if p['table'] == 'theta1_mm':
				shadow = p['color'] + '29'
				p['color'] = p['color'] + '00'
			# get data
			dateTimeList = df['Giulian_day'].values
			values = df[p['table']].values
			cw.addTimeSerie(dateTimeList, values, lineType='-', color=p['color'], name=p['name'], yaxis=p['axes'],
							shadow=shadow)
			if p['axes'] == 'y': y1Title.append(p['name'])

	# set title
	cw.setTitles(xlabs=None, ylabs=None, xTitle=None, yTitle=',\n'.join(y1Title), y2Title=None, mainTitle=None)

	cw.setAxis(pos=212, secondAxis=False, label=['Internal vars'])

	# add timeseries
	plotList = [
		{'name': qgis.utils.plugins['IdragraTools'].CPVARNAME['cp_lai'], 'plot': 'True', 'color': '#71c837ff',
		 'style': '-', 'axes': 'y', 'table': 'lai', 'id': wsId}
	]

	y1Title = []
	if df is not None:
		for p in plotList:
			shadow = False
			if p['table'] == 'theta2_mm':
				shadow = p['color'] + '29'
				p['color'] = p['color'] + '00'
			# get data
			dateTimeList = df['Giulian_day'].values
			values = df[p['table']].values
			cw.addTimeSerie(dateTimeList, values, lineType='-', color=p['color'], name=p['name'], yaxis=p['axes'],
							shadow=shadow)
			if p['axes'] == 'y': y1Title.append(p['name'])

	# set title
	cw.setTitles(xlabs=None, ylabs=None, xTitle=None, yTitle=',\n'.join(y1Title), y2Title=None,
				 mainTitle=None)

	# add chart to dialog
	dlg = QMainWindow(myDialog)
	dlg.setWindowTitle(tr('Crop vars.'))
	dlg.setCentralWidget(cw)
	dlg.show()
