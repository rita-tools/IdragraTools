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

import numpy as np

import scipy.io as sio

from qgis.PyQt.QtCore import QObject

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsVectorLayer,QgsField,QgsPoint,QgsPointXY,QgsFeature,QgsGeometry,QgsProject,QgsVectorFileWriter,QgsCoordinateReferenceSystem,QgsFields,QgsWkbTypes

def arrayToString(dataArray, dataType = 'int'):
	dataArray = np.array(dataArray)
	if dataType=='int':
		dataList = np.array2string(dataArray,formatter={'int':lambda x: '%d'%x}) 
		dataList = dataList.replace('.','') # remove last point separator
	else:
		dataList = np.array2string(dataArray,formatter={'float_kind':lambda x: "%.3f" % x}) 
	
	dataList = dataList.replace('[','')
	dataList = dataList.replace(']','')
	dataList = dataList.replace('  ',' ') # remove double spaces
	dataList = dataList.strip() # clean from white saces from edges
	return dataList

def vectorExtractor(mv,varName,outFile ='',progress = None):
	if outFile == '': outFile = 'memory'
	vl = None
	
	if varName in mv.getVectorVarIds():
		# get georeferencing variable
		epsg = mv.GEOREF['crs'][1]
		
		if varName == 'ret':
			# get variable value
			tempData = mv.VECTORVAR[varName][1]
			xList = tempData['xx']
			yList = tempData['yy']
			codiceList = tempData['codice']
			ordCalcList = tempData['ord_calc']
			aMonteList = tempData['areamonte_km2']
			ramoValleList = tempData['ramovalle']
			ramiMonteList = tempData['ramimonte']
			ordineList = tempData['ordine']
			quoteList = tempData['quote']
			parList = tempData['par']
			celList =  tempData['cel']
			
			# create temporary vector
			vl = QgsVectorLayer("LineString?crs=epsg:%s"%epsg, varName, "memory")
			#print(xList)
			pr = vl.dataProvider()

			# add fields
			fieldList = [QgsField("id", QVariant.Int),
								QgsField("codice",  QVariant.String),
								QgsField("ord_calc",  QVariant.Int),
								QgsField("ramoValle", QVariant.String),
								QgsField("ramimonte", QVariant.String),
								QgsField("ordine", QVariant.Int),
								QgsField("quote", QVariant.String),
								QgsField("par1", QVariant.Double),
								QgsField("par2", QVariant.Double),
								QgsField("amonte_km2", QVariant.Double),
								QgsField("cel", QVariant.String)
								]
								
			flds = QgsFields()
			for f in fieldList:
				flds.append(f)
				
			pr.addAttributes(fieldList)
			vl.updateFields() # tell the vector layer to fetch changes from the provider
			
			i = 0
			for xx, yy,codice,ordCalc,ramoValle,ramiMonte,ordine,quote,par,aMonte, cel in zip(xList, yList,codiceList,ordCalcList,ramoValleList,ramiMonteList,ordineList,quoteList,parList,aMonteList,celList):
				pList = []
				if progress: progress.setInfo('record: %s, ordCalc: %s, aMonte: %s'%(i,ordCalc[0][0][0],aMonte[0][0][0]))
				for x, y in zip(xx[0][0], yy[0][0]):
					#print(x,'-',y)
					
					pList.append(QgsPoint(x,y))
					
				# add a feature
				feat = QgsFeature()
				feat.setGeometry(QgsGeometry.fromPolyline(pList))
				
				feat.setAttributes([i+1,
											arrayToString(codice[0][0],'int'),
											arrayToString(ordCalc[0][0],'int'),
											arrayToString(ramoValle[0][0],'int'),
											arrayToString(ramiMonte[0][0],'int'),
											arrayToString(ordine[0][0],'int'),
											arrayToString(quote[0][0],'float'),
											float(par[0][0][0]),
											float(par[0][0][1]),
											arrayToString(aMonte[0][0],'float'),
											arrayToString(cel[0][0],'float'),
											])
				pr.addFeatures([feat])

				# update layer's extent when new features have been added
				# because change of extent in provider is not propagated to the layer
				vl.updateExtents()
				i+=1
				
			if outFile != 'memory':
				# create shapefile
				crs = QgsCoordinateReferenceSystem()
				crs.createFromId(epsg)
				writer = QgsVectorFileWriter(outFile, "CP1250", flds, QgsWkbTypes.LineString, crs, "ESRI Shapefile")

				if writer.hasError() != QgsVectorFileWriter.NoError:
					#if progress: progress.setInfo("Error when creating shapefile: %s"%writer.errorMessage(),True)
					print("Error when creating shapefile: %s"%writer.errorMessage())

				# add all features
				for feat in vl.getFeatures():
					writer.addFeature(feat)

				# delete the writer to flush features to disk
				del writer
				vl = QgsVectorLayer(outFile, varName, "ogr")
				
		elif varName == 'reserv':
			# get variable value
			tempData = mv.VECTORVAR[varName][1]
			xyList =  tempData['XYdam']
			idList = tempData['idx']
			zmaxList = tempData['zmax']
			dampixList = tempData['dampix']
			bacinoList = tempData['bacino']
			inletsList = tempData['inlets']
			outletList = tempData['outlet']
			lawHList = tempData['lawH']
			lawQList = tempData['lawQ']
			nperList = tempData['nper']
			hv0List = tempData['hv0']
			hvaList = tempData['hva']
			hvnList = tempData['hvn']
			lawTList =  tempData['lawT']
			
			# create temporary vector
			vl = QgsVectorLayer("Point?crs=epsg:%s"%epsg, varName, "memory")
			#print(xList)
			pr = vl.dataProvider()

			# add fields
			fieldList = [QgsField("id", QVariant.Int),
							QgsField("zmax",  QVariant.Double),
							QgsField("dampix",  QVariant.Int),
							QgsField("bacino", QVariant.String),
							QgsField("inlets", QVariant.String),
							QgsField("outlet", QVariant.Int),
							QgsField("lawH", QVariant.String),
							QgsField("lawQ", QVariant.String),
							QgsField("nper", QVariant.Int),
							QgsField("hv0", QVariant.Double),
							QgsField("hva", QVariant.Double),
							QgsField("hvn", QVariant.Double),
							QgsField("lawT", QVariant.Double)
							]
								
			flds = QgsFields()
			for f in fieldList:
				flds.append(f)
				
			pr.addAttributes(fieldList)
			vl.updateFields() # tell the vector layer to fetch changes from the provider
			
			i = 0
			for xy, id, zmax, dampix, bacino, inlets, outlet, lawH, lawQ, nper, hv0, hva, hvn, lawT in zip(xyList, idList, zmaxList, dampixList, bacinoList, inletsList, outletList, lawHList, lawQList, nperList, hv0List, hvaList, hvnList, lawTList):
				#print('data:',xy, id, zmax, dampix, bacino, inlets, outlet, lawH, lawQ, nper, hv0, hva, hvn, lawT)
				x = xy[0][0][0]
				y = xy[0][0][1]
				pt = QgsPointXY(x,y)
					
				# add a feature
				feat = QgsFeature()
				feat.setGeometry(QgsGeometry.fromPointXY(pt))
				
				feat.setAttributes([int(id[0][0][0]),
											float(zmax[0][0][0]),
											int(dampix[0][0][0]),
											arrayToString(bacino[0][0],'int'),
											arrayToString(inlets[0][0],'int'),
											int(outlet[0][0][0]),
											arrayToString(lawH[0][0],'float'),
											arrayToString(lawQ[0][0],'float'),
											int(nper[0][0][0]),
											float(hv0[0][0][0]),
											float(hva[0][0][0]),
											float(hvn[0][0][0]),
											float(lawT[0][0][0])
											])
				pr.addFeatures([feat])

				# update layer's extent when new features have been added
				# because change of extent in provider is not propagated to the layer
				vl.updateExtents()
				i+=1
				
			if outFile != 'memory':
				# create shapefile
				crs = QgsCoordinateReferenceSystem()
				crs.createFromId(epsg)
				writer = QgsVectorFileWriter(outFile, "CP1250", flds, QgsWkbTypes.Point, crs, "ESRI Shapefile")

				if writer.hasError() != QgsVectorFileWriter.NoError:
					#if progress: progress.setInfo("Error when creating shapefile: %s"%w.errorMessage(),True)
					print("Error when creating shapefile: %s"%writer.errorMessage())

				# add all features
				for feat in vl.getFeatures():
					writer.addFeature(feat)
				
				if writer.hasError() != QgsVectorFileWriter.NoError:
					print("Error after inserting features: %s"%writer.errorMessage())
					
				# delete the writer to flush features to disk
				del writer
				vl = QgsVectorLayer(outFile, varName, "ogr")
				
		else:
			vl = None
			
	return vl
	

if __name__ == '__console__':
	fileName = 'C:/enricodata/lavori/firenze2018/dati_test/test/gisdata_CECINA_2014.mat'
	varName = 'ret'
	vl = vectorExtractor(fileName,varName)
	QgsProject.instance().addMapLayer(vl)
	