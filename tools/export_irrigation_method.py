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

import os

from .check_value import checkValue
from .speaking_name import speakingName
from .write_pars_to_template import writeParsToTemplate

def checkIrrMethodPars(irrmeth,feedback,tr):
	# k_stress, k_stresswells, irr_eff [0-1]
	checkValue('k_stress', irrmeth['k_stress'], 0, '>=', tr, feedback)
	checkValue('k_stresswells', irrmeth['k_stresswells'], 0, '>=', tr, feedback)
	checkValue('irr_eff', irrmeth['irr_eff'], [0.,1.], '>=<=', tr, feedback)
	if 'fw' in list(irrmeth.keys()):
		# TODO: empty value are showed as 0 in QGIS print('fw =',irrmeth['fw'])
		checkValue('fw', irrmeth['fw'], [0.,1.], '>=<=', tr, feedback)

	# TODO: check comparison
	# min_a,max_a,min_b,max_b ?
	#checkValue('min_a <= max_a', irrmeth['min_a'], irrmeth['max_a'], '<=', tr, feedback)
	#checkValue('min_b <= max_b', irrmeth['min_b'], irrmeth['max_b'], '<=', tr, feedback)

	# losses_a,losses_b,losses_c ?
	# f_interception [0,1]
	checkValue('f_interception', irrmeth['f_interception'], [0,1], 'in', tr, feedback)

	irr_time = [int(x) for x in irrmeth['irr_time'].split(' ')]
	checkValue('n of irr_time', len(irr_time), [24], 'in', tr, feedback)
	if irr_time != list(range(1,25)):
		feedback.reportError(tr('Not admissible value error: irr_time is not a list of ordered values from 1 to 24'),True)

def exportIrrigationMethod(DBM,outPath, feedback = None,tr=None):
	maxIrrMethId = DBM.getMax('idr_irrmet_types', 'id')
	if maxIrrMethId is None:
		feedback.reportError('No irrigation method parameters to be processed. Exiting...', True)

	irrRecs = []
		
	for irrId in range(1, maxIrrMethId + 1):
		if not feedback._flag: return -1
		# make empty table
		aZip = zip(list(range(1,25)), [0.]*24)
		table = []
		for z in aZip:
			table.append('%s = %s # Irrigation between %s:00 and %s:59' % (
			z[0], z[1], str(int(z[0]) - 1).zfill(2), str(int(z[0]) - 1).zfill(2)))

		table = '\n'.join(table)

		# make default parameters with empty values
		irrDict = {'ID': irrId,
				   'NAME': 'not implemented',
				   'IRR_EFF': 0,
				   'QADAQ': 0,
				   'KSTRESS': 0,
				   'KSTRESSWELL': 0,
				   'FW': 0,
				   'AMIN': 0,
				   'AMAX': 0,
				   'BMIN': 0,
				   'BMAX': 0,
				   'ALOSSES': 0,
				   'BLOSSES': 0,
				   'CLOSSES': 0,
				   'FINTERCEPTION': 0,
				   'IRRTIMETABLE': table,
				   'ADV_OPTS': ''
				   }


		# load irrigation params from db
		irrMethod = DBM.getRecordAsDict(tableName = 'idr_irrmet_types',fieldsList='',filterFld='id', filterValue=irrId)
		#print(irrMethod)
		if len(irrMethod) > 0:
			irrMethod = irrMethod[0]
			feedback.pushInfo(tr('Exporting settings for irrigation method %s - %s') % (irrMethod['id'], irrMethod['name']))

			checkIrrMethodPars(irrMethod, feedback, tr)

			table = []
			flowRates = irrMethod['irr_fraction'].split(' ')
			starList = []
			totFract = 0.0

			for i,fr in enumerate(flowRates):
				if fr =='*':
					starList.append(i)
				else:
					totFract += float(fr)

			numOfStar = len(starList)
			if totFract>1.0:
				feedback.reportError(tr('Error in irrigation run time, total ratio exceed 1.0'), False)

			if ((totFract<1.0) and (numOfStar>0)):
				# equally distribute difference to missing values
				for i in starList:
					flowRates[i] = str((1.0-totFract)/numOfStar)

			aZip = zip(irrMethod['irr_time'].split(' '),flowRates)
			for z in aZip:
				table.append('%s = %s # Irrigation between %s:00 and %s:59'%(z[0],z[1],str(int(z[0])-1).zfill(2),str(int(z[0])-1).zfill(2)))

			table = '\n'.join(table)

			f_int = 'T'
			if irrMethod['f_interception'] in ['0',0,'F','FALSE','false','False']:
				f_int = 'F'

			adv_opts = ''
			fw = 1.
			if len(irrMethod) > 18:  # for legacy db structure
				fw = irrMethod['fw']
				if fw in ['',0, 0.,None]:
					feedback.reportError(tr('Null or zero wetted fraction parameter (fw) will be set to 1.0'), False)
					fw = 1.0

				adv_opts = irrMethod['adv_opts'].split(';')
				adv_opts = [opt.strip() for opt in adv_opts]
				adv_opts = '\n'.join(adv_opts)

			# replace default non implemented
			irrDict = {'ID':irrMethod['id'],
							'NAME':irrMethod['name'],
					   		'IRR_EFF':irrMethod['irr_eff'],
							'QADAQ':irrMethod['qadaq'],
							'KSTRESS':irrMethod['k_stress'],
							'KSTRESSWELL':irrMethod['k_stresswells'],
							'FW':fw,
							'AMIN':irrMethod['min_a'],
							'AMAX':irrMethod['max_a'],
							'BMIN':irrMethod['min_b'],
							'BMAX':irrMethod['max_b'],
							'ALOSSES':irrMethod['losses_a'],
							'BLOSSES':irrMethod['losses_b'],
							'CLOSSES':irrMethod['losses_c'],
							'FINTERCEPTION':f_int,
							'IRRTIMETABLE':table,
							'ADV_OPTS': adv_opts
					}

		# irrMethod = irrMethod[0]
		# irrMethod = irrMethod[1:]  # remove first field "fid"
		# feedback.pushInfo(tr('Exporting settings for irrigation method %s - %s') % (irrMethod[0], irrMethod[1]))
		#
		# table = []
		# flowRates = irrMethod[15].split(' ')
		# starList = []
		# totFract = 0.0
		#
		# for i, fr in enumerate(flowRates):
		# 	if fr == '*':
		# 		starList.append(i)
		# 	else:
		# 		totFract += float(fr)
		#
		# numOfStar = len(starList)
		# if totFract > 1.0:
		# 	feedback.reportError(tr('Error in irrigation run time, total ratio exceed 1.0'), False)
		#
		# if ((totFract < 1.0) and (numOfStar > 0)):
		# 	# equally distribute difference to missing values
		# 	for i in starList:
		# 		flowRates[i] = str((1.0 - totFract) / numOfStar)
		#
		# aZip = zip(irrMethod[14].split(' '), flowRates)
		# for z in aZip:
		# 	table.append('%s = %s # Irrigation between %s:00 and %s:59' % (
		# 	z[0], z[1], str(int(z[0]) - 1).zfill(2), str(int(z[0]) - 1).zfill(2)))
		#
		# table = '\n'.join(table)
		#
		# f_int = 'T'
		# if irrMethod[13] in ['0', 0, 'F', 'FALSE', 'false', 'False']:
		# 	f_int = 'F'
		#
		# adv_opts = ''
		# if len(irrMethod) > 17:  # for legacy db structure
		# 	adv_opts = irrMethod[17].split(';')
		# 	adv_opts = [opt.strip() for opt in adv_opts]
		# 	adv_opts = '\n'.join(adv_opts)
		#
		# # replace default non implemented
		# irrDict = {'ID': irrMethod[0],
		# 		   'NAME': irrMethod[1],
		# 		   'QADAQ': irrMethod[2],
		# 		   'KSTRESS': irrMethod[3],
		# 		   'KSTRESSWELL': irrMethod[4],
		# 		   'FW': irrMethod[5],
		# 		   'AMIN': irrMethod[6],
		# 		   'AMAX': irrMethod[7],
		# 		   'BMIN': irrMethod[8],
		# 		   'BMAX': irrMethod[9],
		# 		   'ALOSSES': irrMethod[10],
		# 		   'BLOSSES': irrMethod[11],
		# 		   'CLOSSES': irrMethod[12],
		# 		   'FINTERCEPTION': f_int,
		# 		   'IRRTIMETABLE': table,
		# 		   'ADV_OPTS': adv_opts
		# 		   }

		#loop in used crop and export
		# save to file
		#fileName = '%s_%s.txt' % (irrDict['ID'], speakingName(irrDict['NAME']))
		#print('irrDict',irrDict)
		fileName = '%s_%s.txt' % (irrId, speakingName(irrDict['NAME']))

		writeParsToTemplate(outfile=os.path.join(outPath,fileName),
									parsDict =  irrDict,
									templateName='irrigation_par.txt')
									
		irrRecs.append(fileName)
		
	nOfFile = len(irrRecs)
	fileList = '\n'.join(irrRecs)
	
	writeParsToTemplate(outfile=os.path.join(outPath,'irrmethods.txt'),
									parsDict =  {'NUMIRRMET':nOfFile, 'IRRMETLIST':fileList},
									templateName='irrmethods.txt')
