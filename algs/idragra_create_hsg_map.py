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

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant
from qgis.analysis import QgsRasterCalculatorEntry, QgsRasterCalculator
from qgis.core import (QgsRasterLayer,
					   QgsProcessing,
					   QgsProcessingAlgorithm,
					   QgsProcessingParameterFeatureSource,
					   QgsProcessingParameterRasterLayer,
					   QgsProcessingUtils,
					   QgsProcessingParameterField,
					   QgsProcessingParameterRasterDestination)
						
import processing

import numpy as np

import os

from ..tools.gis_grid import GisGrid
from ..tools.compact_dataset import getRasterInfos

from processing.algs.gdal.GdalUtils import GdalUtils

class IdragraCreateHSGMap(QgsProcessingAlgorithm):
	"""
	This is an example algorithm that takes a vector layer and
	creates a new identical one.

	It is meant to be used as an example of how to create your own
	algorithms and explain methods and variables used to do it. An
	algorithm like this will be available in all elements, and there
	is not need for additional work.

	All Processing algorithms should extend the QgsProcessingAlgorithm
	class.
	"""

	# Constants used to refer to parameters and outputs. They will be
	# used when calling the algorithm from another algorithm, or when
	# calling from the QGIS console.

	SOURCE_TABLE = 'SOURCE_TABLE'
	SOILID_FLD = 'SOILID_FLD'
	MAXDEPTH_FLD = 'MAXDEPTH_FLD'
	MINKS50  ='MIN_KS50'
	MINKS60 ='MIN_KS60'
	MINKS100 ='MIN_KS100'
	SOILMAP = 'SOIL_MAP'
	ELEVATION = 'ELEVATION'
	WATERTABLE = 'WATERTABLE'
	OUTPUT = 'OUTPUT'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraCreateHSGMap()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCreateHSGMap'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('HSG map')

	def group(self):
		"""
		Returns the name of the group this algorithm belongs to. This string
		should be localised.
		"""
		return self.tr('Create')

	def groupId(self):
		"""
		Returns the unique ID of the group this algorithm belongs to. This
		string should be fixed for the algorithm, and must not be localised.
		The group id should be unique within each provider. Group id should
		contain lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCreate'

	def shortHelpString(self):
		"""
		Returns a localised short helper string for the algorithm. This string
		should provide a basic description about what the algorithm does and the
		parameters and outputs associated with it..
		"""
		
		helpStr = """
						The algorithm create a new map of hydrologic soil groups, HSG, according to the
						National Engineering Handbook Hydrology (Mockus et al., 2009).
						<b>Parameters:</b>
						Source table: a table with all necessary soil parameters<sup>1</sup> [SOURCE_TABLE]
						Soil id: the field with the unique identifier of the soil type [SOILID_FLD]
						Maximum soil layer depth: the field with the maximum soil depth [MAXDEPTH_FLD],
						Min K sat (0-0.5 m): the field with the minimum hydraulic conductivity between 0-0.5 m [MIN_KS50]
						Min K sat (0-0.6 m): the field with the minimum hydraulic conductivity between 0-0.6 m [MIN_KS60]
						Min K sat (0-1 m): the field with the minimum hydraulic conductivity between 0-1.0 m [MIN_KS100]
						Elevation: the raster of the digital elevation model [ELEVATION]
						Water table: the raster of the water table elevation [WATERTABLE]
						Output map: the file path to the output raster [OUTPUT]
						
						<b>Notes</b>
						(1) see Create Pre HSG table algorithm
						"""
		
		return self.tr(helpStr)

	def icon(self):
		self.alg_dir = os.path.dirname(__file__)
		icon = QIcon(os.path.join(self.alg_dir, 'idragra_tool.png'))
		return icon

	def initAlgorithm(self, config=None):
		"""
		Here we define the inputs and output of the algorithm, along
		with some other properties.
		"""

		self.addParameter(QgsProcessingParameterFeatureSource(self.SOURCE_TABLE, self.tr('Source table'),
															  [QgsProcessing.TypeFile], None, True))

		self.addParameter(QgsProcessingParameterField(self.SOILID_FLD, self.tr('Soil id'), 'soilid', self.SOURCE_TABLE,
													  QgsProcessingParameterField.Numeric))
		self.addParameter(
			QgsProcessingParameterField(self.MAXDEPTH_FLD, self.tr('Maximum soil layer depth'), 'maxsoildepth',
										self.SOURCE_TABLE, QgsProcessingParameterField.Numeric))

		self.addParameter(
			QgsProcessingParameterField(self.MINKS50, self.tr('Min K sat (0-0.5 m)'), 'minksat50',
										self.SOURCE_TABLE, QgsProcessingParameterField.Numeric))

		self.addParameter(
			QgsProcessingParameterField(self.MINKS60, self.tr('Min K sat (0-0.6 m)'), 'minksat60',
										self.SOURCE_TABLE, QgsProcessingParameterField.Numeric))

		self.addParameter(
			QgsProcessingParameterField(self.MINKS100, self.tr('Min K sat (0-1.0 m)'), 'minksat100',
										self.SOURCE_TABLE, QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterRasterLayer(self.SOILMAP, self.tr('Soil distribution map')))

		self.addParameter(QgsProcessingParameterRasterLayer(self.ELEVATION, self.tr('Elevation'),None, True))

		self.addParameter(QgsProcessingParameterRasterLayer(self.WATERTABLE, self.tr('Water table'),None, True))

		self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, self.tr('HSG maps')))

	# self.addParameter(
		# 	QgsProcessingParameterFileDestination(self.OUTPUT, self.tr('HSG maps'), self.tr('ASCII (*.asc)')))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		sourceTable = self.parameterAsVectorLayer(parameters, self.SOURCE_TABLE, context)

		soilidFld = self.parameterAsFields(parameters, self.SOILID_FLD, context)[0]
		maxdepthFld = self.parameterAsFields(parameters, self.MAXDEPTH_FLD, context)[0]
		minksat50Fld = self.parameterAsFields(parameters, self.MINKS50, context)[0]
		minksat60Fld = self.parameterAsFields(parameters, self.MINKS60, context)[0]
		minksat100Fld = self.parameterAsFields(parameters, self.MINKS100, context)[0]
		soilmap = self.parameterAsRasterLayer(parameters, self.SOILMAP, context)
		elevation = self.parameterAsRasterLayer(parameters, self.ELEVATION, context)
		watertable = self.parameterAsRasterLayer(parameters, self.WATERTABLE, context)

		hsgMap = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
		# hsgMap = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

		# make lookup tables
		feedback.pushInfo(self.tr('Initializing lookup tables ...'))
		feedback.setProgress(10)
		maxDepthLT = []
		minksat50LT = []
		minksat60LT = []
		minksat100LT = []
		for feat in sourceTable.getFeatures():
			maxDepthLT += [feat[soilidFld],feat[soilidFld],feat[maxdepthFld]]
			minksat50LT += [feat[soilidFld], feat[soilidFld], feat[minksat50Fld]]
			minksat60LT += [feat[soilidFld], feat[soilidFld], feat[minksat60Fld]]
			minksat100LT += [feat[soilidFld], feat[soilidFld], feat[minksat100Fld]]

		feedback.pushInfo(self.tr('Assigning parameters to soil map ...'))
		feedback.setProgress(20)
		# make max depth map
		algResults = processing.run("native:reclassifybytable",
					   {'INPUT_RASTER': soilmap, 'RASTER_BAND': 1,
						'TABLE': maxDepthLT, 'NO_DATA': -9999, 'RANGE_BOUNDARIES': 2,
						'NODATA_FOR_MISSING': True, 'DATA_TYPE': 5, 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=context, feedback=feedback, is_child_algorithm=True)
		maxDepthLay = algResults['OUTPUT']

		# make max ksat 50 map
		algResults = processing.run("native:reclassifybytable",
					   {'INPUT_RASTER': soilmap, 'RASTER_BAND': 1,
						'TABLE': minksat50LT, 'NO_DATA': -9999, 'RANGE_BOUNDARIES': 2,
						'NODATA_FOR_MISSING': True, 'DATA_TYPE': 5, 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=context, feedback=feedback, is_child_algorithm=True)
		minksat50Lay = algResults['OUTPUT']

		# make max ksat 60 map
		algResults = processing.run("native:reclassifybytable",
									{'INPUT_RASTER': soilmap, 'RASTER_BAND': 1,
									 'TABLE': minksat60LT, 'NO_DATA': -9999, 'RANGE_BOUNDARIES': 2,
									 'NODATA_FOR_MISSING': True, 'DATA_TYPE': 5, 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=context, feedback=feedback, is_child_algorithm=True)
		minksat60Lay = algResults['OUTPUT']

		# make max ksat 100 map
		algResults = processing.run("native:reclassifybytable",
									{'INPUT_RASTER': soilmap, 'RASTER_BAND': 1,
									 'TABLE': minksat100LT, 'NO_DATA': -9999, 'RANGE_BOUNDARIES': 2,
									 'NODATA_FOR_MISSING': True, 'DATA_TYPE': 5, 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=context, feedback=feedback, is_child_algorithm=True)
		minksat100Lay = algResults['OUTPUT']

		wtdepth = ''
		if elevation and watertable:
			feedback.pushInfo(self.tr('Calculating water table depth ...'))
			feedback.setProgress(40)
			# make watertable depth
			entries = []
			# Define elevation
			raster1 = QgsRasterCalculatorEntry()
			raster1.ref = 'elevation@1'
			raster1.raster = elevation
			raster1.bandNumber = 1
			entries.append(raster1)

			# Define elevation
			raster2 = QgsRasterCalculatorEntry()
			raster2.ref = 'watertable@1'
			raster2.raster = watertable
			raster2.bandNumber = 1
			entries.append(raster2)

			wtdepth = QgsProcessingUtils.generateTempFilename('wtdepth.tif')
			driverName = GdalUtils.getFormatShortNameFromFilename(wtdepth)
			# Process calculation with input extent and resolution

			calc = QgsRasterCalculator('"elevation@1"-"watertable@1"', wtdepth, driverName, soilmap.extent(),
									   soilmap.width(), soilmap.height(), entries)
			res = calc.processCalculation(self.FEEDBACK)
			if res>0: self.FEEDBACK.error(self.tr('Unable to resolve the formula'))
			#print('res',res)
		else:
			feedback.reportError(self.tr('Unable to calculate water table depth.'), False)

		feedback.pushInfo(self.tr('Loading matrix ...'))
		feedback.setProgress(50)
		# get array from soild id layer
		# soilidArray = self.convertRasterToNumpyArray(soilmap.source())
		# print('array min:',np.nanmin(soilidArray))
		# print('array max:', np.nanmax(soilidArray))

		# get array from max imp layer
		maxDepthArray = self.convertRasterToNumpyArray(maxDepthLay)
		#print('dim maxDepthArray', maxDepthArray.shape)

		# get array from water table depth
		if wtdepth:
			wtDepthArray = self.convertRasterToNumpyArray(wtdepth)
		else:
			# set to very low
			wtDepthArray = maxDepthArray*0.0+1000

		# get array from min ksat 0-50
		minksat50Array = self.convertRasterToNumpyArray(minksat50Lay)
		#print('dim minksat50Array', minksat50Array.shape)
		# get array from min ksat 0-60
		minksat60Array = self.convertRasterToNumpyArray(minksat60Lay)

		# get array from min ksat 0-100
		minksat100Array = self.convertRasterToNumpyArray(minksat100Lay)

		# conversion factors
		cm2m = 0.01
		nms2cmh = 3600.0/(10*1000)

		feedback.pushInfo(self.tr('Run classification ...'))
		feedback.setProgress(75)
		# assign HSG code:
		# A=1, B=2, C=3 and D=4
		hsgArray = np.zeros(maxDepthArray.shape,np.float32)-9999
		# ---------------------------
		hsgArray[(maxDepthArray < 50.0 * cm2m)*(maxDepthArray >=0)] = 4
		# ---------------------------
		hsgArray[(wtDepthArray < 60.0 * cm2m)*(maxDepthArray >=0)] = 4
		# ---------------------------
		hsgArray[(maxDepthArray >= 50.0 * cm2m)*(maxDepthArray <= 100.0 * cm2m) *
				(wtDepthArray >= 60.0 * cm2m)*(minksat50Array > 40.0 * nms2cmh)] = 1
		hsgArray[(maxDepthArray >= 50.0 * cm2m)*(maxDepthArray <= 100.0 * cm2m) *
				(wtDepthArray >= 60.0 * cm2m)*(minksat50Array <= 40.0 * nms2cmh) *
				 (minksat50Array > 10.0 * nms2cmh)] = 2

		
		hsgArray[(maxDepthArray >= 50.0 * cm2m)*(maxDepthArray <= 100.0 * cm2m)*
				 (wtDepthArray >= 60.0 * cm2m)*
				 (minksat50Array <= 10.0 * nms2cmh)*(minksat50Array > 1.0 * nms2cmh)] = 3
		hsgArray[(maxDepthArray >= 50.0 * cm2m)*(maxDepthArray <= 100.0 * cm2m)*
				 (wtDepthArray >= 60.0 * cm2m)*
				 (minksat50Array <= 1.0 * nms2cmh)] = 4
		# ---------------------------
		hsgArray[(maxDepthArray > 100.0 * cm2m)*(wtDepthArray > 60.0 * cm2m)*(wtDepthArray <= 100.0 * cm2m)*
				 (minksat50Array > 40.0 * nms2cmh)] = 1
		hsgArray[(maxDepthArray > 100.0 * cm2m)*(wtDepthArray > 60.0 * cm2m)*(wtDepthArray <= 100.0 * cm2m)*
				 (minksat50Array <= 40.0 * nms2cmh)*(minksat50Array > 10.0 * nms2cmh)] = 2
		hsgArray[(maxDepthArray > 100.0 * cm2m)*(wtDepthArray > 60.0 * cm2m)*(wtDepthArray <= 100.0 * cm2m)*
				 (minksat50Array <= 10.0 * nms2cmh)*(minksat50Array > 1.0 * nms2cmh)] = 3
		hsgArray[(maxDepthArray > 100.0 * cm2m)*(wtDepthArray > 60.0 * cm2m)*(wtDepthArray <= 100.0 * cm2m)*
				 (minksat50Array <= 1.0 * nms2cmh)] = 4
		# ---------------------------
		hsgArray[(wtDepthArray > 100.0 * cm2m)*(minksat100Array > 40.0 * nms2cmh)] = 1
		hsgArray[(wtDepthArray > 100.0 * cm2m)*(minksat100Array <= 40.0 * nms2cmh)*(minksat100Array > 10.0 * nms2cmh)] = 2
		hsgArray[(wtDepthArray > 100.0 * cm2m)*(minksat100Array <= 10.0 * nms2cmh)*(minksat100Array > 1.0 * nms2cmh)] = 3
		hsgArray[(wtDepthArray > 100.0 * cm2m)*(minksat100Array <= 1.0 * nms2cmh)] = 4

		feedback.pushInfo(self.tr('HSG range: %s - %s')%(np.nanmin(hsgArray),np.nanmax(hsgArray)))


		# hsgArray[np.logical_and(np.logical_and(maxDepthArray >= 50.0 * cm2m, maxDepthArray <= 100.0 * cm2m),
		# 						np.logical_and( wtDepthArray >= 60.0 * cm2m, minksat50Array > 40.0 * nms2cmh))] = 1
		# hsgArray[np.logical_and(maxDepthArray >= 50.0 * cm2m, maxDepthArray <= 100.0 * cm2m, wtDepthArray >= 60.0 * cm2m,
		# 						minksat50Array <= 10.0 * nms2cmh, minksat50Array > 1.0 * nms2cmh)] = 3
		# hsgArray[np.logical_and(maxDepthArray >= 50.0 * cm2m, maxDepthArray <= 100.0 * cm2m, wtDepthArray >= 60.0 * cm2m,
		# 						minksat50Array <= 1.0 * nms2cmh)] = 4
		# # ---------------------------
		# hsgArray[np.logical_and(maxDepthArray > 100.0 * cm2m, wtDepthArray > 60.0 * cm2m,wtDepthArray <= 100.0 * cm2m,
		# 						minksat50Array > 40.0 * nms2cmh)] = 1
		# hsgArray[np.logical_and(maxDepthArray > 100.0 * cm2m, wtDepthArray > 60.0 * cm2m,wtDepthArray <= 100.0 * cm2m,
		# 						minksat50Array <= 40.0 * nms2cmh, minksat50Array > 10.0 * nms2cmh)] = 2
		# hsgArray[np.logical_and(maxDepthArray > 100.0 * cm2m, wtDepthArray > 60.0 * cm2m,wtDepthArray <= 100.0 * cm2m,
		# 						minksat50Array <= 10.0 * nms2cmh, minksat50Array > 1.0 * nms2cmh)] = 3
		# hsgArray[np.logical_and(maxDepthArray > 100.0 * cm2m, wtDepthArray > 60.0 * cm2m,wtDepthArray <= 100.0 * cm2m,
		# 						minksat50Array <= 1.0 * nms2cmh)] = 4
		# # ---------------------------
		# hsgArray[np.logical_and(wtDepthArray > 100.0 * cm2m,
		# 						minksat100Array > 40.0 * nms2cmh)] = 1
		# hsgArray[np.logical_and(wtDepthArray > 100.0 * cm2m,
		# 						minksat100Array <= 40.0 * nms2cmh, minksat100Array > 10.0 * nms2cmh)] = 2
		# hsgArray[np.logical_and(wtDepthArray > 100.0 * cm2m,
		# 						minksat100Array <= 10.0 * nms2cmh, minksat100Array > 1.0 * nms2cmh)] = 3
		# hsgArray[np.logical_and(wtDepthArray > 100.0 * cm2m,
		# 						minksat100Array <= 1.0 * nms2cmh)] = 4
		# save array to map
		# get raster georeferencing parameters
		feedback.pushInfo(self.tr('Saving output ...'))
		feedback.setProgress(90)
		geoDict = getRasterInfos(soilmap.source())
		#feedback.pushInfo(self.tr('Georeference parameters: %s') % str(geoDict))
		self.dx = geoDict['dx']
		self.dy = geoDict['dy']
		self.ncols = geoDict['ncols']
		self.nrows = geoDict['nrows']
		self.xllcorner = geoDict['xllcorner']
		self.yllcorner = geoDict['yllcorner']
		self.nodata = -9999
		self.data = hsgArray
		# xurcorner = geoDict['xllcorner'] + ncols * geoDict['dx']
		# yurcorner = geoDict['yllcorner'] - nrows * geoDict['dy']

		# aGrid = GisGrid(ncols=ncols, nrows=nrows, xcell=xllcorner, ycell=yllcorner, dx=dx, dy=-dy, nodata=-9,
		# 				EPSGid=soilmap.crs().postgisSrid () , progress=self.FEEDBACK)
		# aGrid.data = hsgArray#maxDepthArray#

		#feedback.pushInfo(self.tr('Array Data shape: %s') % str(hsgArray.shape))
		if hsgMap.endswith('.asc'):
			self.saveAsASCII(hsgMap, d=0, useCellSize=True)
		else:
			pass
			#aGrid.saveAsGDAL(hsgMap)

		feedback.setProgress(100)
		return {self.OUTPUT: hsgMap}

	def saveAsASCII(self,filename, d, useCellSize):
		"""
		savegrid		: save current grid in a Esri-like ASCII grid file.
		Arguments:
		filename		: the complete name of the new file (path + filename)
		d				 : decimal digit
		useCellSize	 : if True, write cellsize parameter instead of dx and dy
		"""
		try:
			# use of with to automatically close the file
			with open(filename, 'w') as f:
				f.write('ncols ' + str(self.ncols) + '\n')
				f.write('nrows ' + str(self.nrows) + '\n')
				f.write('xllcorner ' + str(self.xllcorner) + '\n')
				f.write('yllcorner ' + str(self.yllcorner) + '\n')
				if useCellSize:
					f.write('cellsize ' + str(self.dx) + '\n')
				else:
					f.write('dx ' + str(self.dx) + '\n')
					f.write('dy ' + str(self.dy) + '\n')

				if d == 0:
					f.write('nodata_value ' + str(int(self.nodata)) + '\n')
				else:
					f.write('nodata_value ' + str(round(self.nodata, d)) + '\n')

				s = ''
				c = 0

				i = 0
				# replace nan with nodata
				idx = np.where(np.isnan(self.data))
				dataToPrint = self.data
				dataToPrint[idx] = self.nodata

				if d == 0:
					for row in dataToPrint:
						i += 1
						self.FEEDBACK.setProgress(100 * float(i) / self.nrows)
						for el in row:
							# print len(el)
							s = s + str(int(round(el, d)))
							c = c + 1
							# add space if not EOF
							if c % self.ncols != 0:
								s = s + ' '
							else:
								s = s + '\n'

				else:
					for row in dataToPrint:
						i += 1
						self.FEEDBACK.setProgress(100 * float(i) / self.nrows)
						for el in row:
							# print len(el)
							s = s + str(round(el, d))
							c = c + 1
							# add space if not EOF
							if c % self.ncols != 0:
								s = s + ' '
							else:
								s = s + '\n'

				f.write(s)

			# f.write('projection ' + str(self.hd.prj) + '\n')
			# f.write('notes ' + str(self.hd.note))
			# TODO: this line causes memory issue, probably because self.progress is lost
			self.FEEDBACK.pushInfo(self.tr('Grid exported to %s')%(filename))
		except Exception as e:
			# print 'Cannot save file: %s' %filename
			self.FEEDBACK.error(self.tr('Cannot save to %s because %s') % (filename, str(e)))


	def convertRasterToNumpyArray(self,lyrFile):  # Input: QgsRasterLayer
		self.lyr = QgsRasterLayer(lyrFile, 'temp') # self to prevent del by garbage collector
		values = []
		provider = self.lyr.dataProvider()
		nodata = provider.sourceNoDataValue (1)
		block = provider.block(1, self.lyr.extent(), self.lyr.width(), self.lyr.height())

		for i in range(self.lyr.height()):
			for j in range(self.lyr.width()):
				values.append(block.value(i, j))

		a = np.array(values)
		#print('shape of %s: %s, %s'%(lyrFile,lyr.height(),lyr.width()))
		a = np.reshape(a,(self.lyr.height(),self.lyr.width()))
		#print('in convertRasterToNumpyArray, array shape',a.shape)
		a[a==nodata]= np.nan
		return a