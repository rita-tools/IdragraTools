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

import sqlite3 as sqlite
from datetime import datetime
from qgis.core import QgsVectorLayer
import os
import numpy as np

from tools.check_value import checkValue


def queryDB(sql,DBM,feedback,tr):
	data = []
	try:
		DBM.startConnection()
		res = DBM.cur.execute(sql)
		data = DBM.cur.fetchall()
	except Exception as e:
		feedback.pushInfo(tr('SQL error at %s: %s') %(sql,str(e)),True)
	finally:
		DBM.stopConnection()
	
	return list(zip(*data))


def exportMeteodataFromDB(DBM, outpath,startY,endY,feedback,tr=None):
	#~ fromTime = datetime(year, 1, 1)
	#~ toTime = datetime(year, 12, 31,23, 59, 59)
	fromTime = '%s-01-01'%startY
	toTime = '%s-12-31'%endY
	yearList = list(range(startY,endY+1))

	# # get the list of the used weather stations
	# sql = 'SELECT DISTINCT id_wstation FROM idr_crop_fields ORDER BY id_wstation ASC'
	# #print(sql)
	# dummy = list(queryDB(sql,DBM,feedback,tr))
	# listOfUsedWS = []
	# for d in dummy:
	# 	listOfUsedWS.append(int(d[0]))
		
	
	# get list of all weather stations
	# as we need also coordinates, it will open as QGIS layer
	sql = 'SELECT id,name,lat, alt FROM idr_weather_stations'
	wsData = queryDB(sql,DBM,feedback,tr)
	#print('wsData',wsData)

	listOfUsedWS = []
	for d in wsData[0]:
		listOfUsedWS.append(int(d))

	wsLay = DBM.getTableAsLayer('idr_weather_stations')
	
	i=0
	wsList = []

	CO2 = []
	for feat in wsLay.getFeatures():
		
		if feat['id'] in listOfUsedWS:
			i+=1
			filename = os.path.join(outpath,str(feat['id'])+'.dat')
			exportMeteodata(filename, DBM.DBName, feat['id'], feat['name'], feat['lat'], feat['alt'], fromTime, toTime, feedback,tr)
			x = feat.geometry().asMultiPoint()[0].x()
			y = feat.geometry().asMultiPoint()[0].y()
			# add to list of exported ws
			wsList.append('%s.dat %s %s'%(feat['id'],x,y))

			# calculate average CO2 concentration
			valueList = getAverageCO2(DBM, feat['id'], yearList)
			CO2.append(valueList)

	# calculate average sumCO2
	CO2 = np.array(CO2,dtype=float)
	meanCO2 = np.nanmean(CO2, axis=0)
	CO2List = meanCO2.tolist()
	for i,v in enumerate(CO2List):
		if np.isnan(v): CO2List[i]=None

	return wsList,yearList,CO2List

def getAverageCO2(DBManager, sensorId, yearList):
	valueList = []
	for y in yearList:
		fromDate = '%s-12-31' % str(y-1) # use the last day of the previous years (it's excluded by calculation)
		toDate = '%s-12-31' % str(y)
		res = DBManager.makeStatistics(tableName = 'ws_co2', sensorId = sensorId,
								 fromDate = fromDate, toDate = toDate)
		valueList.append(res['meanVal'])

	return valueList
	
def exportMeteodata(filename, dbname, sensorId, sensorName, sensorLat, sensorAlt, fromTime, toTime, feedback,tr=None):
	
	msg = ''
	if not tr: tr = lambda x: x
	
	sql = createQuery(fromTime,toTime,sensorId)
		
	feedback.pushInfo(tr('Processing weather station %s [%s]')%(sensorName,sensorId))
	
	msg = ''
	data = None
	nOfRec = 0
	try:
		# start connection
		conn = sqlite.connect(dbname,detect_types=sqlite.PARSE_DECLTYPES)
		# creating a Cursor
		cur = conn.cursor()
		# execute query
		cur.execute(sql)
		data = cur.fetchall()
	except Exception as e:
		msg = str(e)
	finally:
		conn.rollback()
		conn.close()
	
	if msg != '':
		feedback.reportError(tr('SQL error: %s at %s'%(msg,sql)),True)
		return -1
	
	# parse data
	textData = ''
	try:
		for d in data:
			check_flag = 1
			#'ws_tmax','ws_tmin','ws_Ptot','ws_umax','ws_umin','ws_vmed','ws_rgcorr'
			check_flag *= checkValue('[%s] ws_tmax >= ws_tmin'%str(d[0]), d[1], d[2], '>=', tr, feedback)
			check_flag *= checkValue('[%s] ws_Ptot'%str(d[0]), d[3], 0., '>=', tr, feedback)
			check_flag *= checkValue('[%s] ws_umax'%str(d[0]), d[4], [0., 100.], '>=<=', tr, feedback)
			check_flag *= checkValue('[%s] ws_umin'%str(d[0]), d[5], [0., 100.], '>=<=', tr, feedback)
			check_flag *= checkValue('[%s] ws_umax >= ws_umin'%str(d[0]), d[4],d[5], '>=', tr, feedback)
			check_flag *= checkValue('[%s] ws_vmed'%str(d[0]), d[6], [0.,10.], '>=<=', tr, feedback)
			check_flag *= checkValue('[%s] ws_rgcorr'%str(d[0]), d[7], [0., 50.], '>=<=', tr, feedback)

			if check_flag ==0: return -1

			textData += ''.join(format(x, "9.3f") for x in d[1:])+'\n'
	except Exception as e:
		#print(str(e))
		feedback.reportError(
			tr('Unable to prepare weather data for station %s [id = %s]. Dataset must be complete for the selected period')%
			(sensorName,sensorId),True)
		return -1
		
	# save to file
	
	s = """Id stazione: %s, località: %s
%s  %s
%s -> %s
T_max   T_min   P_tot   U_max   U_min   V_med   RG_CORR
%s"""
			
	s = s%(sensorId, sensorName, sensorLat, sensorAlt,
				datetime.strptime(fromTime,'%Y-%m-%d').strftime('%d/%m/%Y'),
				datetime.strptime(toTime,'%Y-%m-%d').strftime('%d/%m/%Y'),
				textData)
	
	try:
		f = open(filename,'w',encoding='utf-8')
		f.write(s)
	except IOError:
		feedback.reportError(tr('Cannot save to %s because %s')%(filename,str(IOError)),True)
		return -1
	finally:
		f.close()
	
	return nOfRec

def createQuery(sDate,eDate,wsId):
	sql = ''
	joinList = []
	fieldList = ['consday.timestamp AS timestamp']
	
	tableList = [
					'ws_tmax',
					'ws_tmin',
					'ws_Ptot',
					'ws_umax',
					'ws_umin',
					'ws_vmed',
					'ws_rgcorr'
					]					
	
	for t in tableList:
		fieldList.append('%s_sel.recval as %s'%(t,t[3:]))
		joinList.append( "LEFT JOIN (SELECT timestamp,recval FROM %s WHERE %s.wsid = '%s') as %s_sel\nON consday.timestamp = %s_sel.timestamp"%
								(t,t,wsId,t,t))
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