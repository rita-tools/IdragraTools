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
import shutil

from .check_value import checkValue
from .speaking_name import speakingName
from .write_pars_to_template import writeParsToTemplate

def checkCropPars(crop,feedback,tr):
	messageList = []
	# uses_map@exid %in% soil_uses@id
	# soil_uses@croplist %in% crop_types@id
	# sowingdate_min [1-366]
	checkValue('sowingdate_min',crop['sowingdate_min'],[1,366],'>=<=',tr,feedback)
	# sowingdelay_max	[1-366]
	checkValue('sowingdelay_max', crop['sowingdelay_max'], [0, 365], '>=<=', tr, feedback)
	# sowingdate_min+sowingdelay_max < 366
	checkValue('sowingdate_min+sowingdelay_max', crop['sowingdate_min']+crop['sowingdelay_max'], 366, '<', tr, feedback)
	# harvestdate_max
	checkValue('harvestdate_max', crop['harvestdate_max'], [1, 366], '>=<=', tr, feedback)
	# harvnum_max > 1
	checkValue('harvnum_max', crop['harvnum_max'], 1, '>=', tr, feedback)
	# cropsoverlap [1-366]
	checkValue('cropsoverlap', crop['cropsoverlap'], [0, 366], '>=<=', tr, feedback)
	# tsowing, tdaybase, tcutoff ?
	# vern [0,1]
	checkValue('vern', crop['vern'], [0,1], 'in', tr, feedback)
	# if vern == 1:
	if crop['vern'] == 1:
		# tv_min < tv_max
		checkValue('tv_min minor tv_max', crop['tv_min'], crop['tv_max'], '<', tr, feedback)

		# vstart, vend [1-366]
		checkValue('vstart', crop['vstart'], [1, 366], '>=<=', tr, feedback)
		checkValue('vend', crop['vend'], [1, 366], '>=<=', tr, feedback)
		# vstart < vend
		checkValue('vstart < vend', crop['vstart'], crop['vend'], '<', tr, feedback)
		# vfmin, , vslope ?

	# ph_r, daylength_if, daylength_ins ?
	checkValue('ph_r', crop['ph_r'], [0, 1], 'in', tr, feedback)
	# wp ?
	# fsink ?
	# tcrit_hs, tlim_hs, hi

	# kyT,ky1,ky2,ky3,ky4,praw,ainterception [0-1]
	for k in ['kyT','ky1','ky2','ky3','ky4','praw','ainterception']:
		checkValue(k, crop[k], 0., '>=', tr, feedback)

	# cl_cn [1,2,3,4,5,6,7]
	checkValue('cl_cn', crop['cl_cn'], [1,2,3,4,5,6,7], 'in', tr, feedback)
	# irrigation [0,1]
	checkValue('irrigation', crop['irrigation'], [0,1], 'in', tr, feedback)
	# gdd %ASC&
	gdd = [float(x) for x in crop['gdd'].rstrip('\r\n').split(' ')]
	checkValue('gdd',gdd, None, 'asc', tr, feedback)

def exportLandUse(DBM,outPath, feedback = None,tr=None):
	#print('in export_land_use')
	# export crop params
	allCropsDict = {}

	maxCropId = DBM.getMax('idr_crop_types','id')
	if maxCropId is None:
		feedback.reportError('No crop parameters to be processed. Exiting...',True)

	path2croppar = os.path.join(outPath, 'crop_parameters')
	if os.path.exists(path2croppar):
		feedback.pushInfo('Directory %s already exists and will be deleted' % path2croppar, False)
		shutil.rmtree(path2croppar)

	os.makedirs(path2croppar)

	#print('in export_land_use, maxCropId:',maxCropId)

	fakeFileName = '*'
	for cropId in range(0, maxCropId + 1):
		if not feedback._flag: return -1
		# create crop params folder

		table = ['GDD	Kcb LAI	Hc	Sr']
		# FIX: set to running values
		cropDict = {'NAME': 'empty crop parameters file',
					'SOWINGDATE_MIN': 1,
					'SOWINGDATE_MAX': 0,
					'HARVESTDATE_MAX': 366,
					'HARVNUM_MAX': 1,
					'CROPSOVERLAP': 0,
					'TSOWING': 0,
					'TDAYBASE': 0,
					'TCUTOFF': 0,
					'VERN': 0,
					'TV_MIN': 0,
					'TV_MAX': 0,
					'VFMIN': 0,
					'VSTART': 0,
					'VEND': 0,
					'VSLOPE': 0,
					'PH_R': 0,
					'DAYLENGTH_IF': 0,
					'DAYLENGTH_INS': 0,
					'WP': 0,
					'FSINK': 0,
					'TCRIT_HS': 0,
					'TLIM_HS': 0,
					'HI': 0,
					'KYT': 0,
					'KY1': 0,
					'KY2': 0,
					'KY3': 0,
					'KY4': 0,
					'PRAW': 0,
					'AINTERCEPTION': 0,
					'CL_CN': 0,
					'IRRIGATION': 0,
					'ADV_OPTS':'',
					'CROPTABLE': 'GDD Kcb LAI Hc Sr\n0 0 0 0 0\n0 0 0 0 0'
					}
		soiluse = DBM.getRecordAsDict(tableName='idr_crop_types', fieldsList='', filterFld='id', filterValue=cropId)
		#print('in export_land_use, soiluse:',soiluse)
		if len(soiluse)>0:
			soiluse = soiluse[0]

			feedback.pushInfo(tr('Exporting settings for crop %s') % (soiluse['name']))

			checkCropPars(soiluse, feedback, tr)

			aZip = zip(soiluse['gdd'].rstrip('\r\n').split(' '),
					   soiluse['kcb'].rstrip('\r\n').split(' '),
					   soiluse['lai'].rstrip('\r\n').split(' '),
					   soiluse['hc'].rstrip('\r\n').split(' '),
					   soiluse['sr'].rstrip('\r\n').split(' '))

			adv_opts = ''
			if len(list(soiluse.keys()))>40: # for legacy db structure
				adv_opts = soiluse['adv_opts'].split(';')
				adv_opts = [opt.strip() for opt in adv_opts]
				adv_opts = '\n'.join(adv_opts)

			for z in aZip:
				table.append(' '.join(z))

			table = '\n'.join(table)

			cropDict['NAME'] = soiluse['name']
			cropDict['SOWINGDATE_MIN'] = soiluse['sowingdate_min']
			cropDict['SOWINGDATE_MAX'] = soiluse['sowingdelay_max']
			cropDict['HARVESTDATE_MAX'] = soiluse['harvestdate_max']
			cropDict['HARVNUM_MAX'] = soiluse['harvnum_max']
			cropDict['CROPSOVERLAP'] = soiluse['cropsoverlap']
			cropDict['TSOWING'] = soiluse['tsowing']
			cropDict['TDAYBASE'] = soiluse['tdaybase']
			cropDict['TCUTOFF'] = soiluse['tcutoff']
			cropDict['VERN'] = soiluse['vern']
			cropDict['TV_MIN'] = soiluse['tv_min']
			cropDict['TV_MAX'] = soiluse['tv_max']
			cropDict['VFMIN'] = soiluse['vfmin']
			cropDict['VSTART'] = soiluse['vstart']
			cropDict['VEND'] = soiluse['vend']
			cropDict['VSLOPE'] = soiluse['vslope']
			cropDict['PH_R'] = soiluse['ph_r']
			cropDict['DAYLENGTH_IF'] = soiluse['daylength_if']
			cropDict['DAYLENGTH_INS'] = soiluse['daylength_ins']
			cropDict['WP'] = soiluse['wp']
			cropDict['FSINK'] = soiluse['fsink']
			cropDict['TCRIT_HS'] = soiluse['tcrit_hs']
			cropDict['TLIM_HS'] = soiluse['tlim_hs']
			cropDict['HI'] = soiluse['hi']
			cropDict['KYT'] = soiluse['kyT']
			cropDict['KY1'] = soiluse['ky1']
			cropDict['KY2'] = soiluse['ky2']
			cropDict['KY3'] = soiluse['ky3']
			cropDict['KY4'] = soiluse['ky4']
			cropDict['PRAW'] = soiluse['praw']
			cropDict['AINTERCEPTION'] = soiluse['ainterception']
			cropDict['CL_CN'] = soiluse['cl_cn']
			cropDict['IRRIGATION'] = soiluse['irrigation']
			cropDict['CROPTABLE'] = table
			cropDict['ADV_OPTS'] = adv_opts

		# prepare new file name
		cropFileName = '%s_%s.tab' % (cropId, speakingName(cropDict['NAME']))
		if cropId ==0: fakeFileName = cropFileName

		# loop in used crop and export
		# save to file
		writeParsToTemplate(outfile=os.path.join(path2croppar,cropFileName),
							parsDict=cropDict,
							templateName='crop_par.txt')

		allCropsDict[str(cropId)]=cropFileName


	# FIX: adjust gaps between soil use ids
	# get maximum num of soil uses
	maxSoilUseId = DBM.getMax('idr_soiluses', 'id')

	#print('in export_land_use, maxSoilUseId:', maxSoilUseId)
	if maxSoilUseId is None:
		feedback.reportError('No aoil uses to be processed. Exiting...', True)

	#soiluseList = DBM.getRecord(tableName = 'idr_soiluses',fieldsList='',filterFld='', filterValue=None, orderBy='id')

	#recTemplate = '%-8s %-24s %-24s # %s'
	recTemplate = '%s\t%s\t%s\t# %s'
	soiluseRecs = []
	soiluseRecs.append(recTemplate%('Cr_ID','Crop1','Crop2','Comments'))
	soiluseIds = []

	# export soil uses
	#for soiluse in soiluseList:
	for i in range(1,maxSoilUseId+1):
		#
		#soiluse = soiluse[1:]  # remove first field "fid"
		#i = soiluse[0]
		landuseName = 'Fake soil use'
		soiluseIds.append(str(i))
		firstCrop = fakeFileName
		secondCrop = '*'

		soiluse = DBM.getRecordAsDict(tableName='idr_soiluses', fieldsList='', filterFld='id', filterValue=i)
		#print(soiluse)
		if len(soiluse)>0:
			soiluse = soiluse[0]

			landuseName = soiluse['name']
			cropIdList = soiluse['croplist'].split(' ')
			if len(cropIdList) ==0:
				feedback.reportError('Land use "%s" (id=%s) has empty crop list and will not be processed' % (landuseName,i),
									 False)
			elif len(cropIdList)==1:
				if cropIdList[0] not in list(allCropsDict.keys()):
					feedback.reportError(
						'Land use "%s" (id=%s) has an un-parametrized crop in the list.' % (
						landuseName, i),
						False)
				firstCrop = allCropsDict[cropIdList[0]]
			else:
				if len(cropIdList)>2:
					feedback.reportError(
						'Land use "%s" (id=%s) has more than two crops found. Only the first two will be considered'% (landuseName,i),
						False)

				if cropIdList[0] not in list(allCropsDict.keys()):
					feedback.reportError(
						'Land use "%s" (id=%s) has an un-parametrized crop in the list.' % (
						landuseName, i),
						False)
				firstCrop = allCropsDict[cropIdList[0]]
				if cropIdList[1] not in list(allCropsDict.keys()):
					feedback.reportError(
						'Land use "%s" (id=%s) has an un-parametrized crop in the list.' % (
						landuseName, i),
						False)
				secondCrop = allCropsDict[cropIdList[1]]

		soiluseRecs.append(recTemplate%(i,firstCrop,secondCrop,landuseName))
		
	# collapse soiluserecords
	tableString = '\n'.join(soiluseRecs)
	# save to file
	writeParsToTemplate(outfile=os.path.join(outPath,'soil_uses.txt'),
									parsDict =  {'SOILUSES':tableString},
									templateName='soil_uses.txt')
	

	#print('in export_land_use',soiluseIds)
	return soiluseIds