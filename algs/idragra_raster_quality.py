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
from qgis._analysis import QgsRasterCalculatorEntry, QgsRasterCalculator
from processing.algs.gdal import GdalUtils
from qgis.core import (QgsProcessing,
					   QgsFeatureSink,
					   QgsProcessingException,
					   QgsProcessingAlgorithm,
					   QgsProcessingParameterFeatureSource,
					   QgsProcessingParameterFeatureSink,
					   QgsProcessingParameterMultipleLayers,
					   QgsProcessingParameterFileDestination,
					   QgsProcessingParameterEnum,
					   QgsProcessingParameterRasterLayer,
					   QgsProcessingParameterVectorLayer,
					   QgsProcessingParameterFile,
					   QgsProcessingParameterString,
					   QgsProcessingParameterNumber,
					   QgsProcessingParameterBoolean,
					   QgsProcessingParameterField,
					   QgsProcessingParameterExtent,
					   QgsProcessingParameterRasterDestination,
					   QgsExpression,
					   QgsFeatureRequest,
					   QgsCoordinateReferenceSystem,
					   QgsCoordinateTransform,
					   QgsProcessingParameterFolderDestination,
					   QgsWkbTypes,
					   QgsFields,
					   QgsField,
					   QgsVectorFileWriter,
					   QgsRasterFileWriter,
					   QgsVectorLayer,
					   QgsRasterLayer,
					   QgsProject,
					   NULL,
					   QgsProcessingUtils, QgsFeature)
						
import processing

from numpy import array

from datetime import datetime

import os

class IdragraRasterQuality(QgsProcessingAlgorithm):
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
	
	VECTORLAY= 'VECTOR_LAY'
	MASKLAY = 'MASK_LAY'
	VECTORFLD = 'VECTOR_FLD'
	RASTEREXT = 'RASTER_EXT'
	CELLDIM = 'CELL_DIM'
	DESTFILE = 'DEST_FILE'
		
	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraRasterQuality()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraRasterQuality'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Raster quality')

	def group(self):
		"""
		Returns the name of the group this algorithm belongs to. This string
		should be localised.
		"""
		return self.tr('Analysis')

	def groupId(self):
		"""
		Returns the unique ID of the group this algorithm belongs to. This
		string should be fixed for the algorithm, and must not be localised.
		The group id should be unique within each provider. Group id should
		contain lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraAnalysis'

	def shortHelpString(self):
		"""
		Returns a localised short helper string for the algorithm. This string
		should provide a basic description about what the algorithm does and the
		parameters and outputs associated with it..
		"""
		
		helpStr = """
						The algorithm evaluates the quality of the rasterization process. 
						<b>Parameters:</b>
						Source vector layer: the vector layer to use as limits (polygons) [VECTOR_LAY]
						Field to burn: source of value to burn in the raster [VECTOR_FLD]
						Mask vector layer: the vector layer to use as boundaries (polygons) [VECTOR_LAY]
						Raster extension: the maximum extension of the raster domain map (min x, max x, min y, max y) [RASTER_EXT]
						Raster cell dimension: the dimension of the squared cell in map units [CELL_DIM]
						Output : a table with the results of comparison [DESTFILE]
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
	
		self.addParameter(QgsProcessingParameterVectorLayer(self.VECTORLAY, self.tr('Source vector layer'), [QgsProcessing.TypeVectorPolygon ]))


		self.addParameter(QgsProcessingParameterField(self.VECTORFLD, self.tr('Field to burn'), 'fid', self.VECTORLAY,
													  QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterVectorLayer(self.MASKLAY, self.tr('Mask vector layer'),
															[QgsProcessing.TypeVectorPolygon]))

		#self.addParameter(QgsProcessingParameterExtent(self.RASTEREXT, self.tr('Raster extension')))
		
		self.addParameter(QgsProcessingParameterNumber(self.CELLDIM, self.tr('Raster cell dimension')))
		
		self.addParameter(
			QgsProcessingParameterFeatureSink(self.DESTFILE, self.tr('Output table'), QgsProcessing.TypeFile))
		
		
	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		vectorLay = self.parameterAsVectorLayer(parameters, self.VECTORLAY, context)
		fieldName = self.parameterAsFields(parameters, self.VECTORFLD, context)[0]
		maskLay = self.parameterAsVectorLayer(parameters, self.MASKLAY, context)
		#rasterExt = self.parameterAsExtent(parameters, self.RASTEREXT, context)
		cellDim = self.parameterAsDouble(parameters, self.CELLDIM, context)
		#destFile = self.parameterAsFileOutput(parameters,	self.DESTFILE,	context)

		# VECTOR ANALYSIS
		# make zero buffer to prevent errors
		algResults =  processing.run("native:buffer",
						   {'INPUT': vectorLay, 'DISTANCE': 0, 'SEGMENTS': 1,
							'END_CAP_STYLE': 0, 'JOIN_STYLE': 0, 'MITER_LIMIT': 2, 'DISSOLVE': False,
							'OUTPUT': 'TEMPORARY_OUTPUT'},
						   context=None, feedback=feedback, is_child_algorithm=False)
		bufVectorLay = algResults['OUTPUT']
		algResults = processing.run("native:buffer",
									{'INPUT': maskLay, 'DISTANCE': 0, 'SEGMENTS': 1,
									 'END_CAP_STYLE': 0, 'JOIN_STYLE': 0, 'MITER_LIMIT': 2, 'DISSOLVE': False,
									 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=None, feedback=feedback, is_child_algorithm=False)
		bufMaskLay = algResults['OUTPUT']

		# intersect elements
		algResults = processing.run("native:clip", {
									'INPUT': bufVectorLay,
									'OVERLAY': bufMaskLay, 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=None, feedback=feedback, is_child_algorithm=False)

		clipBufVectorLay = algResults['OUTPUT']

		# calculate area
		algResults = processing.run("qgis:exportaddgeometrycolumns", {
									'INPUT': clipBufVectorLay,
									'CALC_METHOD': 0, 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=None, feedback=feedback, is_child_algorithm=False)

		areaClipBufVectorLay = algResults['OUTPUT']

		# sum areas by categories
		algResults = processing.run("qgis:statisticsbycategories", {
									'INPUT': areaClipBufVectorLay,
									'VALUES_FIELD_NAME': 'area', 'CATEGORIES_FIELD_NAME': [fieldName], 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=None, feedback=feedback, is_child_algorithm=False)

		vectorStatTable = algResults['OUTPUT']

		# print('vectorStatTable:')
		# for feat in vectorStatTable.getFeatures():
		# 	print(feat.attributes())


		# RASTER ANALYSIS
		# get extention from mask vector
		rasterExt = maskLay.extent()
		fieldType = 4  # for testing only

		# make raster map for vector layer
		algResults = processing.run("gdal:rasterize",
									{'INPUT': vectorLay, 'FIELD': fieldName, 'BURN': 0,
									 'UNITS': 1, 'WIDTH': cellDim, 'HEIGHT': cellDim,
									 'EXTENT': rasterExt,
									 'NODATA': -9999, 'OPTIONS': '', 'DATA_TYPE': fieldType, 'INIT': -9999, 'INVERT': False,
									 'EXTRA': '',
									 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=None, feedback=feedback, is_child_algorithm=False
									)
		rasterBaseMap = algResults['OUTPUT']

		# make raster map for the map
		# '520081.977200000,521263.129600000,5018226.041900000,5019118.541900000 [EPSG:32632]'

		algResults = processing.run("gdal:rasterize",
					   				{'INPUT': maskLay, 'FIELD': '', 'BURN': 1,
									'UNITS': 1, 'WIDTH': cellDim, 'HEIGHT': cellDim,
									'EXTENT': rasterExt,
									'NODATA': -9999, 'OPTIONS': '', 'DATA_TYPE': fieldType, 'INIT': -9999, 'INVERT': False, 'EXTRA': '',
									'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=None, feedback=feedback, is_child_algorithm=False
									)
		rasterMaskMap = algResults['OUTPUT']




		# make masked input map

		baseR = QgsRasterLayer(rasterBaseMap)
		maskR = QgsRasterLayer(rasterMaskMap)

		entries = []
		# Define band1
		raster1 = QgsRasterCalculatorEntry()
		raster1.ref = 'base@1'
		raster1.raster = baseR
		raster1.bandNumber = 1
		entries.append(raster1)

		raster2 = QgsRasterCalculatorEntry()
		raster2.ref = 'mask@1'
		raster2.raster = maskR
		raster2.bandNumber = 1
		entries.append(raster2)

		# Process calculation with input extent and resolution
		# slope must be in percent
		# calc = QgsRasterCalculator('100*tan("slope@1"*%s/180)'%math.pi, outSlpMap, driverName,
		#						   newExt, ncols, nrows, entries)

		expression = '"base@1"*"mask@1"'
		rasterMaskedBaseMap = QgsProcessingUtils.generateTempFilename('rasterMaskedBaseMap.tif')
		driverName = GdalUtils.GdalUtils.getFormatShortNameFromFilename(rasterMaskedBaseMap)

		calc = QgsRasterCalculator(expression,
								   rasterMaskedBaseMap,
								   driverName,
								   baseR.extent(),
								   baseR.width(),
								   baseR.height(),
								   entries)

		calc.processCalculation(self.FEEDBACK)

		# print('rasterBaseMap:', rasterBaseMap)
		#
		# expression =  f'\"{}@1\"*\"{}@1\"'.format(rasterBaseMap,rasterMaskMap)
		# print('expression:',expression)
		# algResults = processing.run("qgis:rastercalculator", {'EXPRESSION': expression, 'LAYERS': [rasterBaseMap],
		# 										 'CELLSIZE': 0, 'EXTENT': None, 'CRS': None,
		# 										 'OUTPUT': 'TEMPORARY_OUTPUT'},
		# 							context=context, feedback=feedback, is_child_algorithm=True
		# 							)
		#
		# rasterMaskedBaseMap = algResults['OUTPUT']



		# calculate values distribution respect to area

		algResults = processing.run("native:rasterlayeruniquevaluesreport", {
									'INPUT': rasterMaskedBaseMap,
									'BAND': 1, 'OUTPUT_HTML_FILE': 'TEMPORARY_OUTPUT', 'OUTPUT_TABLE': 'TEMPORARY_OUTPUT'},
									context=None, feedback=feedback, is_child_algorithm=False
									)




		algResults = processing.run("native:fieldcalculator", {
									'INPUT': algResults['OUTPUT_TABLE'],
									'FIELD_NAME': 'intval', 'FIELD_TYPE': 1, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 0, 'FORMULA': 'to_int(\"value\")',
									'OUTPUT': 'TEMPORARY_OUTPUT'},
					   				context=None, feedback=feedback, is_child_algorithm=False
					   				)

		rasterStatTable = algResults['OUTPUT']
		# print('rasterStatTable:')
		#
		# for feat in rasterStatTable.getFeatures():
		# 	print(feat.attributes())
		# PREPARE FINAL RESULT

		algResults = processing.run("native:joinattributestable", {
									'INPUT': vectorStatTable,
									'FIELD': fieldName,
									'INPUT_2': rasterStatTable,
									'FIELD_2': 'intval', 'FIELDS_TO_COPY': ['m²'], 'METHOD': 0, 'DISCARD_NONMATCHING': False, 'PREFIX': '',
									'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=None, feedback=feedback, is_child_algorithm=False
									)


		fldList = QgsFields()
		fldList.append(QgsField('uniquevalue', QVariant.Int))
		fldList.append(QgsField('v_area', QVariant.Double))
		fldList.append(QgsField('r_area', QVariant.Double))
		fldList.append(QgsField('sq_err', QVariant.Double))

		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.DESTFILE,
			context,
			fldList
		)

		# open results as layer
		resTable = algResults['OUTPUT']

		c = 0
		tot_area = 0.
		tot_sq_err = 0.
		for res in resTable.getFeatures():
			feat = QgsFeature(fldList)
			#print('feat:',res.fields().names())
			feat['uniquevalue'] = res[fieldName]
			feat['v_area'] = res['sum']
			tot_area+=res['sum']
			#print('res_m2',res['m²'])
			if res['m²']: feat['r_area'] = res['m²']
			else: feat['r_area']=0.

			sq_err = (feat['r_area']-feat['v_area'])**2
			tot_sq_err += sq_err
			c+=1
			feat['sq_err'] = sq_err
			sink.addFeature(feat, QgsFeatureSink.FastInsert)

		RMSE = NULL
		if c>0: RMSE = (tot_sq_err/c)**0.5

		qIndex = round(100*RMSE/tot_area,2)

		self.FEEDBACK.pushInfo(self.tr('Average error between raster and vector areas (RMSE/mask_area): %s %s' % (qIndex,'%')))

		return {self.DESTFILE: dest_id, 'ERROR':qIndex}