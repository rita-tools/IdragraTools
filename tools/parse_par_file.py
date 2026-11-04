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

from qgis.core import QgsVectorDataProvider

def all_encodings():
	return QgsVectorDataProvider.availableEncodings()

def parseParFile(filename,parSep = '=', colSep=' ', feedback = None,tr=None):
	#~ if not feedback: feedback=MyProgress()
	#~ if not tr: tr=translate
	#if feedback: feedback.pushInfo('in parseParFile, processing: %s'%filename)
	#print('in parseParFile, processing: %s'%filename)
	lines=[]
	encodings = all_encodings()
	#print('encodings:',encodings)
	for enc in encodings:
		# TODO: lost reference to feedback if called from algorithm
		#if feedback: feedback.pushInfo(tr('INFO: try with codec %s' % str(enc)))
		try:
			with open(filename, encoding=enc, errors='strict') as f:
				lines = f.readlines()
				# check if there are not hexadecimal representations of strings caused by erroneous codec selection
				if r'\x' not in repr(''.join(lines)):
					break
		except ValueError:
			print('test encoding:', enc,'returned value error')
			pass
		except Exception:
			pass

	parDict = {}
	tableList = []
	for l in lines:
		# replace TAB
		l = l.replace('\t',' ')
		# remove consecutive with spaces
		l = ' '.join([x for x in l.split()])
		# remove EOL
		l = l.rstrip('\r\n')
		# remove all comments
		comIdx = l.find('#')
		subStr = l
		if comIdx>=0:
			# get substring to comIdx
			subStr = l[0:comIdx]
			
		if len(subStr)>0:
			subStr = subStr.strip() #remove leading and trailing spaces
			toks = subStr.split(parSep)
			if len(toks)==2:
				# k,v pair
				parDict[toks[0].strip()]=toks[1].strip()
			else:
				# is not a inline par, probably is a table
				# print('Is a table record', subStr)
				tableList.append(subStr)
				
	#process tableList
	isFirst = True
	tableDict = {}
	nCol = 0
	
	for r in  tableList:
		if isFirst:
			isFirst = False
			colNames = [x for x in r.split(colSep) if x]
			nCol = len(colNames)
			for c in range(0,nCol):
				tableDict[colNames[c]]=[]
		else:
			vals = r.split(colSep)
			if len(vals)==nCol:
				for c in range(0,nCol):
					tableDict[colNames[c]].append(vals[c])
			# else:
			# 	print(len(vals),'!=',nCol)

	if not isFirst:
		parDict['table']=tableDict
			
	return parDict
		
	
if __name__ == '__console__':
	pars = parseParFile(filename='C:/Users/enrico/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/idragra4qgis/sample/geodata/links.csv',colSep=';')
	print(pars)