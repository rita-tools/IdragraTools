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

from qgis.core import QgsProject, QgsVectorLayer, QgsExpression, QgsFeatureRequest, QgsFeature

from tools.my_progress import MyProgress


def previewImportFromCSV(filename, dbname, tablename, timeFldIdx, valueFldIdx, sensorId, skip,timeFormat,column_sep, feedback,tr=None):
	msg = ''
	
	if not tr: tr = lambda x: x 
	
	feedback.pushInfo(tr('Loading %s'%filename))
	concatValues = []
	# oper CSV file
	in_file = open(filename,"r")
	i = 0
	nOfRec = 0
	# process the first 10 lines
	feedback.pushInfo(tr('Only the first 10 lines will be processed'))
	feedback.pushInfo(tr('LN, date, sensorid, value'))
			
	while i<10:
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
			feedback.pushInfo('%s, %s, %s, %s'%(i,timestamp,sensorId,value))
			nOfRec +=1
		
		i+=1
		
	return nOfRec


def importFromCSV(filename, dbname, tablename, timeFldIdx, valueFldIdx, sensorId, skip,timeFormat,column_sep, feedback,tr=None):
	msg = ''
	
	if not tr: tr = lambda x: x 
	
	feedback.pushInfo(tr('Loading %s'%filename))
	concatValues = []
	# oper CSV file
	in_file = open(filename,"r")
	i = 0
	nOfRec = 0
	while 1:
		in_line = in_file.readline()
		if i>=skip:
			if len(in_line) == 0:
				break
			
			# process the line
			in_line = in_line.rstrip() # remove newline
			#print('LN %d: %s'%(i,in_line))
			data = in_line.split(column_sep)
			timestamp = datetime.strptime(data[timeFldIdx], timeFormat)
			value = float(data[valueFldIdx])
			
			concatValues.append("('"+ timestamp.strftime('%Y-%m-%d')+"', '"+str(sensorId)+"', '"+str(value)+"')")
			nOfRec +=1
			if feedback.isCanceled():
				return -1
		
		i+=1
	
	concatValues = ', '.join(concatValues)
	# create a temporary table to store uploaded data
	feedback.pushInfo(tr('Creating temporary table'))
	sql = 'DROP TABLE IF EXISTS dummy;'
	sql += 'CREATE TABLE dummy (timestamp2 text, wsid2 integer, recval2 double);'
	
	msg = executeSQL(dbname,sql)
	if msg != '':
		feedback.reportError(tr('SQL error: %s at %s'%(msg,sql)),True)
		return -1
	else:
		feedback.pushInfo(tr('--> OK'))
		
	feedback.setProgress(30)
	
	feedback.pushInfo(tr('Populating temporary table'))
	
	sql = 'BEGIN; '
	sql += 'REPLACE INTO dummy (timestamp2,wsid2,recval2) VALUES %s; ' %(concatValues)
	sql += 'COMMIT;'
	
	msg = executeSQL(dbname,sql)
	if msg != '':
		feedback.reportError(tr('SQL error: %s at %s'%(msg,sql)),True)
		return -1
	else:
		feedback.pushInfo(tr('--> OK'))
		
	feedback.setProgress(50)

	feedback.pushInfo(tr('INFO: updating existing values in %s'%tablename))
	# update value if they already exist
	sql ='UPDATE %s SET recval = (SELECT d.recval2 FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid)	WHERE EXISTS (SELECT * FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid);'%(tablename)
	msg = executeSQL(dbname,sql)
	if msg != '':
		feedback.reportError(tr('SQL error: %s at %s'%(msg,sql)),True)
		return -1
	else:
		feedback.pushInfo(tr('--> OK'))
		
	feedback.setProgress(75)
	
	# copy value to tablename id they aren't
	feedback.pushInfo(tr('INFO: appending new values in %s'%tablename))
	sql = 'INSERT INTO %s (timestamp,wsid,recval) SELECT timestamp2,wsid2,recval2 FROM dummy d WHERE NOT EXISTS (SELECT * FROM %s WHERE timestamp = d.timestamp2 AND wsid = d.wsid2);'%(tablename,tablename)
	msg = executeSQL(dbname,sql)
	if msg != '':
		feedback.reportError(tr('SQL error: %s at %s'%(msg,sql)),True)
		return -1
	else:
		feedback.pushInfo(tr('--> OK'))
		
	feedback.setProgress(80)
	
	feedback.pushInfo(tr('INFO: removing temporary table'))
	sql = 'DROP TABLE IF EXISTS dummy;'
	msg = executeSQL(dbname,sql)
	if msg != '':
		feedback.pushInfo(tr('SQL error: %s'%msg))
		feedback.pushInfo(tr('at: %s'%sql))
		return -1
	else:
		feedback.pushInfo(tr('--> OK'))
		
	feedback.setProgress(90)

	if msg !='':
		feedback.reportError(tr('Error: unable to import data'))
		return -1		
	else:
		feedback.pushInfo(tr('Importation finished! Variable %s updated for sensor %s'%(tablename,sensorId)))

		
	feedback.setProgress(100)
	
	return nOfRec
	
def executeSQL(dbname,sql):
	msg=''
	try:
		# start connection
		conn = sqlite.connect(dbname,detect_types=sqlite.PARSE_DECLTYPES)
		# creating a Cursor
		cur = conn.cursor()
		# execute query
		cur.executescript(sql)
	except Exception as e:
		msg = str(e)
	finally:
		conn.rollback()
		conn.close()
		
	return msg


def importDataFromCSVXXX(filename, vLayer, timeFldIdx, valueFldIdx, sensorId, skip, timeFormat, column_sep,
					  overWrite=True, saveEdit=False, year='',
					  progress=None,tr = None):

	if not tr: tr = lambda x: x
	if not progress: progress = MyProgress()

	msg = ''
	progress.setText(tr('INFO: loading %s' % filename))
	tsList = []
	valList = []
	# open CSV file
	try:
		in_file = open(filename, "r")
		i = 0
		while 1:
			in_line = in_file.readline()
			if i >= skip:
				if len(in_line) == 0:
					break

				# process the line
				in_line = in_line[:-1]
				if column_sep != ' ': in_line = in_line.replace(' ', '')
				# print 'LN %d: %s'%(i,in_line)
				data = in_line.split(column_sep)
				timestamp = datetime.strptime(str(year) + data[timeFldIdx], timeFormat)
				value = float(data[valueFldIdx])

				tsList.append(timestamp)
				valList.append(value)

			i += 1
	except Exception as e:
		progress.reportError(
			tr('Unable to parse input file %s: %s') % (filename, str(e)), True)
		return
	finally:
		in_file.close()

	nOfRecord = len(tsList)

	progress.setText(tr('n. of imported record: %s') % nOfRecord)

	# start ediding
	vLayer.startEditing()

	pr = vLayer.dataProvider()
	fieldNames = [field.name() for field in pr.fields()]
	nOfRec = 0

	idxTS = fieldNames.index('timestamp')
	idxSens = fieldNames.index('wsid')
	idxVal = fieldNames.index('recval')

	# populate data
	i = 0
	for t, v in zip(tsList, valList):
		# check if the record exist
		# check if attribute already exist
		expr = QgsExpression(
			"\"%s\" = '%s' and \"%s\" = '%s'" % ('timestamp', str(t), 'wsid', sensorId))
		featList = vLayer.getFeatures(QgsFeatureRequest(expr))
		updateFeat = 0
		for feat in featList:
			if feat['recval'] != value:
				if overWrite:
					progress.pushInfo(tr('Updating feature %s') % feat.id())
					vLayer.changeAttributeValues(feat.id(), {idxVal: value}, {idxVal: feat['recval']})
			updateFeat += 1

		if updateFeat > 1:
			progress.reportError(
				tr('Unexpected number of matches (%s) for timestamp "%s" and sensor "%s"') %
				(updateFeat, timestamp, sensorId), True)
			return

		# no feature to update --> add it
		if updateFeat == 0:
			# add new record to table
			newFeat = QgsFeature(pr.fields())
			newFeat.setAttribute(idxTS, str(t))
			newFeat.setAttribute(idxSens, sensorId)
			newFeat.setAttribute(idxVal, value)
			vLayer.addFeatures([newFeat])

		i += 1
		progress.setPercentage(100 * i / nOfRecord)

	if saveEdit:
		progress.pushInfo(tr('Save edits ...'))
		vLayer.commitChanges()