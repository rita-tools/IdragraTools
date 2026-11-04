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
import numpy as np
from datetime import datetime
from qgis.core import QgsVectorLayer
import os

def queryDB(sql,dbname):
	msg = ''
	data = []
	try:
		# start connection
		conn = sqlite.connect(dbname, detect_types=sqlite.PARSE_DECLTYPES)
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
	
	return data,msg

def getWeatStatList(dbname):
	sql = 'SELECT fid FROM idr_weather_stations'
	data, msg = queryDB(sql, dbname)
	newData = [item for t in data for item in t]
	return newData, msg

def getWatSourceList(dbname):
	# get list of node with some discharge data
	sql = 'SELECT DISTINCT	wsid FROM node_act_disc'
	data, msg = queryDB(sql, dbname)
	nodeWithDataList = [item for t in data for item in t]

	# get list of irrigation nodes
	sql = 'SELECT node FROM idr_distrmap'
	data, msg = queryDB(sql, dbname)
	irrigationNodeList = [item for t in data for item in t]

	# for each irrigation node
	finalList = []
	for irrNode in irrigationNodeList:
		if irrNode in nodeWithDataList:
			if irrNode not in finalList:
				finalList.append(irrNode)
		else:
			# go upstream if it has no discharge data (i.e. not in nodeWithDataList)
			# if it has data, add to final list
			pass


def getTimeSeriesConsistency(dbname, fromTime, toTime, weatStatList=[],watSourceList=[], feedback=None,tr=None):
	uniqueY = []
	nOfAllDays = []
	nOfFilledDays = []
	msg = ''
	if not tr: tr = lambda x: x

	# make a big query
	sql = createQuery(fromTime,toTime,weatStatList, watSourceList)

	feedback.pushInfo(sql)

	# run the query
	data,msg = queryDB(sql, dbname)

	if msg != '':
		feedback.reportError(tr('SQL error: %s at %s'%(msg,sql)),True)
		return uniqueY,nOfAllDays,nOfFilledDays

	# make a list of years, expected number of days (365, 366) and number of filled days
	data = np.array(data)
	values = np.array(data[:,1:],dtype=float)
	years=np.array(data[:,0],np.datetime64).astype('datetime64[Y]').astype(int) + 1970
	uniqueY = np.unique(years).tolist()
	prodOfData = np.prod(values[:,1:], axis=1)
	#newData = np.column_stack((years,prodOfData))

	for y in uniqueY:
		nOfAllDays.append(int(np.sum(years == y)))
		nOfFilledDays.append(int(np.nansum(prodOfData[years == y])))

	return {'years':uniqueY,'numDays':nOfAllDays,'filledDays':nOfFilledDays}

def createQuery(sDate,eDate,weatStatList,watSourceList= []):
	sql = ''
	joinList = []
	fieldList = ['consday.timestamp AS timestamp']
	
	weatStatTableList = [
					'ws_tmax',
					'ws_tmin',
					'ws_Ptot',
					'ws_umax',
					'ws_umin',
					'ws_vmed',
					'ws_rgcorr'
					]					

	watSourceTableList = [
					'node_act_disc'
					]

	for wsId in weatStatList:
		for t in weatStatTableList:
			fieldList.append('%s_sel%s.recval as %s%s'%(t,wsId,t[3:],wsId))
			joinList.append(
				"LEFT JOIN (SELECT timestamp,recval*0+1 AS recval FROM %s WHERE %s.wsid = '%s') as %s_sel%s\nON consday.timestamp = %s_sel%s.timestamp"%
				(t,t,wsId,t,wsId,t,wsId))

	for wsId in watSourceList:
		for t in watSourceTableList:
			fieldList.append('%s_sel%s.recval as %s%s'%(t,wsId,t[3:],wsId))
			joinList.append(
				"LEFT JOIN (SELECT timestamp,recval*0+1 AS recval FROM %s WHERE %s.wsid = '%s') as %s_sel%s\nON consday.timestamp = %s_sel%s.timestamp" %
				(t, t, wsId, t, wsId, t, wsId))

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
			SELECT %s FROM (SELECT datetime(julianday('%s'), '+' || x || ' days') AS timestamp FROM cnt) as consday
			%s
			"""%(eDate, sDate, fieldSQL,sDate,joinSQL)
				
	return sql