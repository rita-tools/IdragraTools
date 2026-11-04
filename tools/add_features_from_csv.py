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

from qgis.core import QgsVectorLayer,QgsFeature,QgsGeometry
from .parse_par_file import parseParFile

def addFeaturesFromCSV(laySource,csvSource,feedback = None):
	if feedback: feedback.pushInfo('in addFeaturesFromCSV, processing: %s'%laySource)
	#print('in addFeaturesFromCSV, processing: %s'%laySource)
	vlayer = QgsVectorLayer(laySource, 'dummy', "ogr")
	vlayer.startEditing()
	pr = vlayer.dataProvider()
	field_names = [field.name() for field in pr.fields()]
	dataDict = parseParFile(filename=csvSource, colSep=';', feedback = feedback,tr=None)
	
	dataDict = dataDict['table']
	nOfRec = len(dataDict['geometry'])
	
	for i in range(nOfRec):
		feat = QgsFeature()
		feat.setGeometry(QgsGeometry.fromWkt(dataDict['geometry'][i]))
		feat.setFields(pr.fields())
		for k in list(dataDict.keys()):
			if k in field_names:
				idx = field_names.index(k)
				#~ print('%s --> %s'%(k,idx))
				#~ print('value: %s'%dataDict[k][i])
				feat.setAttribute(idx,dataDict[k][i])
		
		f = pr.addFeatures([feat])
		if not f:
			#print('in addFeaturesFromCSV, error adding feature %s'%i)
			pass

	vlayer.commitChanges()	
	