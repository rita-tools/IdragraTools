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
						
import processing

from numpy import array

from datetime import datetime

import os

class IdragraRasterizeMap(QgsProcessingAlgorithm):
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
		return IdragraRasterizeMap()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraRasterizeMap'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Raster map')

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
						The algorithm creates the raster from a layer (i.e. the area of application of the Idragra model). 
						<b>Parameters:</b>
						Source vector layer: the vector layer to use as limits (polygons) [VECTOR_LAY]
						Field to burn: source of value to burn in the raster [VECTOR_FLD]
						Raster extension: the maximum extension of the raster domain map (min x, max x, min y, max y) [RASTER_EXT]
						Raster cell dimension: the dimension of the squared cell in map units [CELL_DIM]
						Output raster: the complete path of the output file [DESTFILE]
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

		self.addParameter(QgsProcessingParameterExtent(self.RASTEREXT, self.tr('Raster extension')))
		
		self.addParameter(QgsProcessingParameterNumber(self.CELLDIM, self.tr('Raster cell dimension')))
		
		self.addParameter(QgsProcessingParameterFileDestination(self.DESTFILE, self.tr('Output raster'), self.tr('ASCII (*.asc)')))
		
		
	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		vectorLay = self.parameterAsVectorLayer(parameters, self.VECTORLAY, context)
		fieldName = self.parameterAsFields(parameters, self.VECTORFLD, context)[0]
		rasterExt = self.parameterAsExtent(parameters, self.RASTEREXT, context)
		cellDim = self.parameterAsDouble(parameters, self.CELLDIM, context)
		destFile = self.parameterAsFileOutput(parameters,	self.DESTFILE,	context)

		prov = vectorLay.dataProvider()
		fieldType = 4 # integer
		for field in prov.fields():
			if (field.name() == fieldName):
				fieldType = field.type()
				if fieldType in [1,2,3]:
					fieldType = 4 # int32 in GDAL
					digits = 0
				else:
					fieldType = 5 # float32 in GDAL
					digits = 6

				break

		algResults = processing.run("gdal:rasterize",
									{'INPUT': vectorLay, 'FIELD': fieldName, 'BURN': 0,
									 'UNITS': 1, 'WIDTH': cellDim, 'HEIGHT': cellDim,
									 'EXTENT': rasterExt,
									 'NODATA': -9999, 'OPTIONS': '', 'DATA_TYPE': fieldType, 'INIT': -9999, 'INVERT': False,
									 'EXTRA': '',
									 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=None, feedback=feedback, is_child_algorithm=False
									)
		processing.run("idragratools:IdragraSaveAscii",
					   {'INPUT': algResults['OUTPUT'], 'DIGITS': digits,
						'OUTPUT': destFile},
					   context=None, feedback=feedback, is_child_algorithm=False)

		# algResults = processing.run("gdal:translate", {
		# 	'INPUT': algResults['OUTPUT'],
		# 	'TARGET_CRS': None, 'NODATA': -9, 'COPY_SUBDATASETS': False, 'OPTIONS': '', 'EXTRA': '', 'DATA_TYPE': 0,
		# 	'OUTPUT': destFile},
		# 							context=None, feedback=feedback, is_child_algorithm=False)



		return {'OUTPUT':algResults['OUTPUT']}
		