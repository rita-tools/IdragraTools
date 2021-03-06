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
from .write_pars_to_template import writeParsToTemplate

def exportIrrigationMethod(DBM,outPath, feedback = None,tr=None):
	irrIdList = DBM.getUniqueValues(fieldName = 'id', tableName= 'idr_irrmet_types')
	irrRecs = []
		
	for irrId in irrIdList:
		# create crop params folder
		irrMethod = DBM.getRecord(tableName = 'idr_irrmet_types',fieldsList='',filterFld='id', filterValue=irrId)[0]
		irrMethod = irrMethod[1:] #remove first field "fid"
		feedback.pushInfo(tr('Exporting settings for irrigation method %s - %s') % (irrMethod[0], irrMethod[1]))
		table = []
		flowRates = irrMethod[14].split(' ')
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

		aZip = zip(irrMethod[13].split(' '),flowRates)
		for z in aZip:
			table.append('%s = %s # Irrigation between %s:00 and %s:59'%(z[0],z[1],str(int(z[0])-1).zfill(2),str(int(z[0])-1).zfill(2)))
			
		table = '\n'.join(table)
		
		f_int = 'T'
		if irrMethod[12] in ['0',0,'F','FALSE','false','False']:
			f_int = 'F'
		
		irrDict = {'ID':irrMethod[0],
						'NAME':irrMethod[1],
						'QADAQ':irrMethod[2],
						'KSTRESS':irrMethod[3],
						'KSTRESSWELL':irrMethod[4],
						'AMIN':irrMethod[5],
						'AMAX':irrMethod[6],
						'BMIN':irrMethod[7],
						'BMAX':irrMethod[8],
						'ALOSSES':irrMethod[9],
						'BLOSSES':irrMethod[10],
						'CLOSSES':irrMethod[11],
						'FINTERCEPTION':f_int,
						'IRRTIMETABLE':table
				}
		
		#loop in used crop and export
		# save to file
		writeParsToTemplate(outfile=os.path.join(outPath,'%s.txt'%irrId),
									parsDict =  irrDict,
									templateName='irrigation_par.txt')
									
		irrRecs.append('%s.txt'%irrId)
		
	nOfFile = len(irrRecs)
	fileList = '\n'.join(irrRecs)
	
	writeParsToTemplate(outfile=os.path.join(outPath,'irrmethods.txt'),
									parsDict =  {'NUMIRRMET':nOfFile, 'IRRMETLIST':fileList},
									templateName='irrmethods.txt')
