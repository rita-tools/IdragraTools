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

import io
import os
from .write_pars_to_template import writeParsToTemplate
import sqlite3 as sqlite
from datetime import date, timedelta
import numpy as np
import pandas as pd

def exportWaterSources(DBM,outPath, startY,endY,feedback = None,tr=None):
	# get node layers
	nodeLay = DBM.getTableAsLayer(name = 'idr_nodes')
	linkLay = DBM.getTableAsLayer(name='idr_links')
	irrunitLay = DBM.getTableAsLayer(name='idr_distrmap')

	# set time
	fromTime = '%s-01-01' % startY
	toTime = '%s-12-31' % endY

	# 1: [1] Generic water source
	# 11: [11] Monitored water source
	# 12: [12] Constant water source
	# 13: [13] Threshold rules water source
	# 14: [14] On demand unlimited water source
	# 2: [2] Junctions
	# 3: [3] Water distributor

	divList = []
	divDischList = []
	publicWellList = []
	privWellList = []

	twoStageFlow = {}
	for feat in nodeLay.getFeatures():
		nodeId = feat['id']
		if feat['node_type'] == 1:
			# it is a water source!
			nodeDisch = feat['q_sum']
			res = DBM.getRecord('node_act_disc', '', 'wsid', nodeId)
			if len(res)>0:
				# if it has a time serie of discharge --> use as diversion
				divList.append(nodeId)
				divDischList.append(nodeDisch)
			elif nodeDisch>0:
				# it has the summer discharge --> use as public well
				table = []
				trs = feat['act_trshold'].split(' ')
				trs = [float(x) for x in trs]
				misTrs = min(trs)
				rt = feat['act_ratio'].split(' ')
				aZip = zip(trs, rt )
				for i,z in enumerate(aZip):
					table.append('%s\t%s\t%s' % (i+1,z[0],z[1]))

				table = '\n'.join(table)

				pubWellDict = {'WELLNAME': nodeId,
						   'WELLID': nodeId,
						   'QMAX': feat['q_sum'],
						   'QNOM': feat['q_sum'],
						   'MINTRESHOLD': misTrs,
						   'TRESHOLDTABLE': table
						   }

				# save to file
				writeParsToTemplate(outfile=os.path.join(outPath, '%s.txt' % nodeId),
									parsDict=pubWellDict,
									templateName='single_CR.txt')

				publicWellList.append(nodeId)
			else:
				# else: no complete informations except the type --> use as private well
				# add to private wells list
				privWellList.append(nodeId)
		elif feat['node_type'] == 11:
			# monitored diversion
			nodeDisch = feat['q_sum']
			res = DBM.getRecord('node_act_disc', '', 'wsid', nodeId)
			# if it has a time serie of discharge --> use as diversion
			if len(res) > 0:
				divList.append(nodeId)
				divDischList.append(nodeDisch)
			else:
				feedback.reportError(tr('Source has no time-discharge data. Node %s will be skipped.' % nodeId), False)
		elif feat['node_type'] == 12:
			# runoff collector
			nodeDisch = feat['q_sum']
			res = DBM.getRecord('node_act_disc', '', 'wsid', nodeId)
			# if it has a time serie of discharge --> use as diversion
			if len(res) > 0:
				divList.append(nodeId)
				divDischList.append(nodeDisch)
			else:
				feedback.reportError(tr('Source has no time-discharge data. Node %s will be skipped.' % nodeId), False)
		elif feat['node_type'] == 13:
			# public well
			table = []
			trs = feat['act_trshold'].split(' ')
			trs = [float(x) for x in trs]
			misTrs = min(trs)
			rt = feat['act_ratio'].split(' ')
			aZip = zip(trs, rt)
			for i, z in enumerate(aZip):
				table.append('%s\t%s\t%s' % (i + 1, z[0], z[1]))

			table = '\n'.join(table)

			pubWellDict = {'WELLNAME': nodeId,
						   'WELLID': nodeId,
						   'QMAX': feat['q_sum'],
						   'QNOM': feat['q_sum'],
						   'MINTRESHOLD': misTrs,
						   'TRESHOLDTABLE': table
						   }

			# save to file
			writeParsToTemplate(outfile=os.path.join(outPath, '%s.txt' % nodeId),
								parsDict=pubWellDict,
								templateName='single_CR.txt')

			publicWellList.append(nodeId)
		elif feat['node_type'] == 14:
			# private well
			privWellList.append(nodeId)
		elif feat['node_type'] == 15:
			# TODO: not tested yet
			# winter/summer discharges
			# add to the dictionary
			# twoStageFlow[nodeId] = [feat['q_sum'], feat['sum_start'], feat['sum_end'], feat['q_win'], feat['win_start'],
			# 						feat['win_end']]
			pass
		else:
			pass


	# save cr_sources.txt
	# #SourceWellTotNum: number of public wells
	# SourceWellTotNum = 2
	# # List: Wells parameters' files
	# # List starts with the label "List =" and ends with the label "EndList ="
	# List =
	# q_iant.txt
	# q_ibon.txt
	# EndList =

	nOfFile = len(publicWellList)
	fileList = ''
	if nOfFile>0:
		# add newline symbols as caps
		fileList ='\n'+ '\n'.join(['%s.txt' % x for x in publicWellList])

	writeParsToTemplate(outfile=os.path.join(outPath, 'cr_sources.txt'),
						parsDict={'NUMOFWELL': nOfFile, 'WELLLIST': fileList},
						templateName='cr_sources.txt')

	# Make the diversion file "XXX_diversion.txt"
	# c_cal	  c_maroc	  c_vac --> SOURCE_CODE
	# 2.500 	 4.173 	 38.500  --> NOMINAL_DISCHARGE
	# 01/01/2020 -> 31/12/2029 --> PERIOD
	# 0.300 	  2.310 	  19.830
	# 0.300 	  2.310 	  19.830
	# 0.300 	  2.310 	  19.830
	# ...

	sourceList = '\t'.join(str(x) for x in divList)
	# dischList = '\t'.join(str(x) for x in divDischList) moved down..
	#print('divList:',divList)
	# make a big discharge query
	data_df = None
	step_div = list(range(0,len(divList),10))
	if max(step_div)<len(divList): step_div+=[len(divList)] # add the last index

	for i in range(0,len(step_div)-1):
		feedback.setPercentage(100.0*i/10)
		sql = createDischQuery(sDate = fromTime, eDate= toTime, wsIdList = divList[step_div[i]:step_div[i+1]])
		#print('sql createDischQuery',sql)

		msg = ''
		data = None
		nOfRec = 0
		try:
			# start connection
			conn = sqlite.connect(DBM.DBName, detect_types=sqlite.PARSE_DECLTYPES)
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
			feedback.reportError(tr('SQL error: %s at %s' % (msg, sql)), True)
			return -1

		temp_data_df = pd.DataFrame(data, columns = ['date']+divList[step_div[i]:step_div[i+1]])
		#print(temp_data_df)
		if data_df is None:
			data_df = temp_data_df
		else:
			#temp_data_df.drop(columns=['date'], inplace=True)
			#data_df = data_df.join(temp_data_df,'date')
			data_df = data_df.merge(temp_data_df,on=['date'], how='left')

	#print(data_df)

	data_df.drop(columns = ['date'],inplace=True)
	mean_disch = data_df.mean(axis=0,skipna=True).to_list()

	data_df.fillna(0, inplace=True)


	#dischList = '\t'.join(str(x) for x in divDischList)
	dischList = []
	for q,q_mean in zip(divDischList,mean_disch):
		if not q: q = round(q_mean,3)

		dischList.append(str(q))

	dischList = '\t'.join(dischList)

	dischTable = data_df.to_string(header=False,index=False, float_format=lambda x: "{:9.3f}".format(x))
	# parse data
	# dischTable = ''
	# for d in data:
	# 	valList = []
	# 	for v in d[1:]:
	# 		if v is None: valList.append(0.0)
	# 		else: valList.append(v)
	#
	# 	dischTable += ''.join(format(x, "9.3f") for x in valList) + '\n'

	#print(dischTable)
	# Right date format is dd/mm/yyyy
	writeParsToTemplate(outfile=os.path.join(outPath, 'monit_sources_i.txt'),
						parsDict={'SOURCELIST': sourceList, 'DISCHLIST': dischList,
								  'FROMDATE':'01/01/%s'%startY,'TODATE':'31/12/%s'%endY, 'DISCHTABLE': dischTable},
						templateName='monit_sources_i.txt')

	# Save two stage discharges
	twoStageList = list(twoStageFlow.keys())
	nOfTwoStage = len(twoStageList)
	twoStageListString = '\t'.join([str(x) for x in twoStageList])

	twoStageDischList,twoStageDischTable = makeDischSerie(twoStageFlow,startY, endY)
	if len(twoStageDischList)>0:
		twoStageDischList = '\t'.join([str(x) for x in twoStageDischList])

		s = io.BytesIO()
		np.savetxt(s, twoStageDischTable, '%.3f','\t')
		twoStageDischTable = s.getvalue().decode()

		writeParsToTemplate(outfile=os.path.join(outPath, 'int_reuse.txt'),
							parsDict={'SOURCELIST': twoStageListString, 'DISCHLIST': twoStageDischList,
									  'FROMDATE': '01/01/%s' % startY, 'TODATE': '31/12/%s' % endY,
									  'DISCHTABLE': twoStageDischTable},
							templateName='int_reuse.txt')

	# add empty file
	# writeParsToTemplate(outfile=os.path.join(outPath, 'monit_sources_ii.txt'),
	# 					parsDict={},
	# 					templateName='monit_sources_ii.txt')

	# build water district tables "irrdistricts.txt", "watsources.txt"
	# need loop to the upstream node
	irrDistr = []
	watSources = []

	for feat in irrunitLay.getFeatures():
		distrId = feat['id']
		nodeId = feat['inlet_node']
		expFact = feat['expl_factor']
		watShift = feat['wat_shift']

		res = DBM.getAllSourceNode(nodeId)

		isPrivateWell = 0
		for i, f in zip(res['nodeList'], res['ratioList']):
			if i in privWellList:
				# check if it is a private wells
				isPrivateWell = 1
			else:
				# check is there are private wells
				sourceType = 1  # all water sources with discharge time series
				if i in twoStageList: sourceType = 3
				if i in publicWellList: sourceType = 4  # all water sources with automatic delivery

				watSources.append([distrId, i, sourceType, f])

		irrDistr.append([distrId, expFact, isPrivateWell])

	# save water sources file
	table = []
	for ws in watSources:
		if ws[1] in (divList+publicWellList): table.append('\t'.join([str(x) for x in ws])) # append anly water sources in the list

	table = '\n'.join(table)
	writeParsToTemplate(outfile=os.path.join(outPath, 'watsources.txt'),
						parsDict={'WSTABLE': table},
						templateName='watsources.txt')

	# save irrigation district file
	table = []
	for ir in irrDistr:
		table.append('\t'.join([str(x) for x in ir]))

	table = '\n'.join(table)
	writeParsToTemplate(outfile=os.path.join(outPath, 'irr_districts.txt'),
						parsDict={'DISTRTABLE': table},
						templateName='irr_districts.txt')


	return {'nbasins':len(irrDistr),'nsource':len(watSources),'nsourceder':len(divList),'noftwostage':nOfTwoStage,'npubwell':len(publicWellList) }


def createDischQuery(sDate, eDate, wsIdList):
	sql = ''
	joinList = []
	fieldList = ['consday.timestamp AS timestamp']

	for t in wsIdList:
		fieldList.append('x%s_sel.recval as x%s' % (t,t))
		joinList.append(
			"LEFT JOIN (SELECT timestamp,recval FROM node_act_disc WHERE node_act_disc.wsid = '%s') as x%s_sel\nON consday.timestamp = x%s_sel.timestamp" %
			(t, t, t))
	# build a super query
	joinSQL = '\n'.join(joinList)
	fieldSQL = ', '.join(fieldList)

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
			""" % (eDate, sDate, fieldSQL, sDate, joinSQL)

	return sql

def makeDischSerie(twoStageDict, startYear, endYear):
	# make a list of julian date

	d1 = date(startYear, 1, 1)
	d2 = date(endYear, 12, 31)

	# this will give you a list containing all of the dates as "julian" dates
	dd = [(d1 + timedelta(days=x)).timetuple().tm_yday for x in range((d2 - d1).days + 1)]
	nRows = len(dd)
	nCols = len(list(twoStageDict.keys()))
	dd = np.array(dd)

	dischList = []
	dischArray = np.zeros((nRows,nCols))
	# for each twoStageDict, make a list
	#print('twoStageDict:',twoStageDict)
	i=-1
	for k,v in twoStageDict.items():
		i+=1
		q1 = v[0]
		start1 = v[1]
		end1 = v[2]
		q2 = v[3]
		start2 = v[4]
		end2 = v[5]
		# assign q1
		if start1<end1:
			dischArray[np.logical_and(dd>=start1,dd<= end1),i] = q1
		else:
			dischArray[np.logical_and(dd >= start1,dd <= 366), i] = q1
			dischArray[np.logical_and(dd >= 1,dd <= end1), i] = q1
		# assign q2
		if start2<end2:
			dischArray[np.logical_and(dd>=start2,dd<= end2),i] = q2
		else:
			dischArray[np.logical_and(dd >= start2,dd <= 366), i] = q2
			dischArray[np.logical_and(dd >= 1,dd <= end2), i] = q2

		dischList.append(q1)
	return dischList,dischArray

