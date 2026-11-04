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
from plugins import processing
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
						NULL)

import os

class IdragraRasterizeTimeMap(QgsProcessingAlgorithm):
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
	DATAFLD = 'DATA_FLD'
	TIMEFLD = 'TIME_FLD'
	NAMEFORMAT = 'NAME_FORMAT'
	RASTEREXT = 'RASTER_EXT'
	CELLDIM = 'CELL_DIM'
	YEARLIST = 'YEAR_LIST'
	DESTFOLDER = 'DEST_FOLDER'
	INITVALUE = 'INIT_VALUE'

	FEEDBACK = None


	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraRasterizeTimeMap()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraRasterizeTimeMap'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Raster time map')

	def group(self):
		"""
		Returns the name of the group this algorithm belongs to. This string
		should be localised.
		"""
		return self.tr('Export')

	def groupId(self):
		"""
		Returns the unique ID of the group this algorithm belongs to. This
		string should be fixed for the algorithm, and must not be localised.
		The group id should be unique within each provider. Group id should
		contain lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraExport'

	def shortHelpString(self):
		"""
		Returns a localised short helper string for the algorithm. This string
		should provide a basic description about what the algorithm does and the
		parameters and outputs associated with it..
		"""

		helpStr = """
						The algorithm creates raster maps from a layer with datetime field. 
						<b>Parameters:</b>
						Vector layer: the vector layer to use as domain limits (polygons) [VECTOR_LAY]
						Field data: source of value to burn in the raster [DATA_FLD]
						Time field: source of dates [TIME_FLD]
						Base name: use as format for output name [NAME_FORMAT]
						Raster extension: the maximum extension of the raster domain map (min x, max x, min y, max y) [RASTER_EXT]
						Raster cell dimension: the dimension of the squared cell in map units [CELL_DIM]
						Init value: the value to assign as base [INIT_VALUE]
						Year list: spase separated list of year to be exported (e.g. 2000 2001 2002 ...). If empty, export all available years [YEAR_LIST]
						Output folder: the complete path of the output file [DEST_FOLDER]
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

		self.addParameter(QgsProcessingParameterVectorLayer(self.VECTORLAY, self.tr('Vector layer'), [QgsProcessing.TypeVectorPolygon ]))

		self.addParameter(QgsProcessingParameterField(self.DATAFLD, self.tr('Field source'), 'extid', self.VECTORLAY,
													  QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterField(self.TIMEFLD, self.tr('Date source'), 'date', self.VECTORLAY,
													  QgsProcessingParameterField.DateTime))

		self.addParameter(QgsProcessingParameterString(self.NAMEFORMAT, self.tr('Output base name'), 'output'))

		self.addParameter(QgsProcessingParameterExtent(self.RASTEREXT, self.tr('Raster extension')))

		self.addParameter(QgsProcessingParameterNumber(self.CELLDIM, self.tr('Raster cell dimension')))

		self.addParameter(QgsProcessingParameterNumber(self.INITVALUE, self.tr('Init value'),defaultValue = -9999))

		self.addParameter(QgsProcessingParameterString(self.YEARLIST, self.tr('Year list'),'', False, True))

		self.addParameter(QgsProcessingParameterFile(self.DESTFOLDER, self.tr('Output folder'),
													 QgsProcessingParameterFile.Behavior.Folder))



	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		vectorLay = self.parameterAsVectorLayer(parameters, self.VECTORLAY, context)
		dataFld = self.parameterAsFields(parameters, self.DATAFLD, context)[0]
		idx = vectorLay.fields().indexOf(dataFld)

		timeFld = self.parameterAsFields(parameters, self.TIMEFLD, context)[0]
		nameFormat = self.parameterAsString(parameters,self.NAMEFORMAT,context)
		rasterExt = self.parameterAsExtent(parameters, self.RASTEREXT, context)
		cellDim = self.parameterAsDouble(parameters, self.CELLDIM, context)
		initValue = self.parameterAsDouble(parameters, self.INITVALUE, context)

		yearList = self.parameterAsString(parameters, self.YEARLIST, context)
		yearList = yearList.split(' ')

		destFolder = self.parameterAsFile(parameters, self.DESTFOLDER, context)

		prov = vectorLay.dataProvider()
		vectorType = prov.wkbType()
		fieldType = 5  # float32 in GDAL
		digits = 6
		fields = prov.fields()
		field = fields.at(idx)
		if field.type() in [1, 2, 3]:
			fieldType = 4  # int32 in GDAL
			digits = 0
			initValue = int(initValue)

		# loop in yearList and make a selection of elements
		res = []
		yearList.sort()
		algResults = None

		for y in yearList:
			feedback.pushInfo(self.tr('Processing year: %s' % y))
			if y != '':
				yearQuery = QgsExpression(" \"%s\" ilike '%s' "%(timeFld,y+'%'))
			else:
				yearQuery = QgsExpression(" \"%s\" is NULL "%timeFld) # select all null values

			selection = vectorLay.getFeatures(QgsFeatureRequest(yearQuery))
			ids = ([k.id() for k in selection])

			if len(ids)==0:
				# repeat selection using empty default values
				self.FEEDBACK.reportError (self.tr('Unable to find valid data for year %s, trying with undateable shapes ...')%y,False)
				yearQuery = QgsExpression(" \"%s\" is NULL " %timeFld)  # select all null values
				selection = vectorLay.getFeatures(QgsFeatureRequest(yearQuery))
				ids = ([k.id() for k in selection])

			use_default = False
			if len(ids)==0:
				# stop algorithm because missing data
				self.FEEDBACK.reportError (self.tr('Unable to find undateable shapes too ... map will be set to default value!'),False)
				yearQuery = QgsExpression("True") # seleziona tutto
				if not algResults: use_default = True #use default value only if it is the first year

			newLayName = processing.QgsProcessingUtils.generateTempFilename('%s_%s.gpkg' %(nameFormat,y))

			writer = QgsVectorFileWriter(newLayName, "System", fields,
										 vectorType, vectorLay.crs(), "GPKG")
			if writer.hasError() != QgsVectorFileWriter.NoError:
				self.FEEDBACK.reportError(self.tr('An error occured when creting selection'), True)
			else:
				# loop and write
				selection = vectorLay.getFeatures(QgsFeatureRequest(yearQuery))
				if use_default:
					for s in selection:
						s[dataFld] = initValue
						writer.addFeature(s)
				else:
					for s in selection:
						writer.addFeature(s)

			del writer

			if y=='':
				destFile = os.path.join(destFolder, nameFormat + '.asc')
			else:
				destFile = os.path.join(destFolder, nameFormat + '_%s.asc'%y)

			# first year rasterization
			if not algResults:
				algResults = processing.run("gdal:rasterize",
											{'INPUT': newLayName, 'FIELD': dataFld, 'BURN': 0,
											 'UNITS': 1, 'WIDTH': cellDim, 'HEIGHT': cellDim,
											 'EXTENT': rasterExt,
											 'NODATA': -9999, 'OPTIONS': '', 'DATA_TYPE': fieldType, 'INIT': -9999,
											 'INVERT': False,
											 'EXTRA': '',
											 'OUTPUT': 'TEMPORARY_OUTPUT'},
											context=None, feedback=feedback, is_child_algorithm=False
											)
			else:
				# replace first year value for the following years
				algResults = processing.run("gdal:rasterize_over",
											{'INPUT': newLayName,
											 'INPUT_RASTER': algResults['OUTPUT'],
											 'FIELD': dataFld, 'ADD': False, 'EXTRA': ''},
											context=None, feedback=feedback, is_child_algorithm=False)

			# export to ascii
			processing.run("idragratools:IdragraSaveAscii",
							{'INPUT': algResults['OUTPUT'], 'DIGITS': digits,
							 'OUTPUT': destFile},
							context=None, feedback=feedback, is_child_algorithm=False)
			# replace rasterization with over burn

			# algResults = processing.run("gdal:rasterize",
			# 							{'INPUT': newLayName, 'FIELD': dataFld, 'BURN': 0,
			# 							 'UNITS': 1, 'WIDTH': cellDim, 'HEIGHT': cellDim,
			# 							 'EXTENT': rasterExt,
			# 							 'NODATA': -9999, 'OPTIONS': '', 'DATA_TYPE': fieldType, 'INIT': initValue,
			# 							 'INVERT': False,
			# 							 'EXTRA': '',
			# 							 'OUTPUT': 'TEMPORARY_OUTPUT'},
			# 							context=None, feedback=feedback, is_child_algorithm=False
			# 							)





			res.append(destFile)

		return {'OUTPUT':res}
