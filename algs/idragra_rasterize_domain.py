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
from processing.algs.gdal.GdalUtils import GdalUtils
from qgis.analysis import QgsRasterCalculatorEntry, QgsRasterCalculator
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
					   QgsProcessingUtils, QgsRectangle)
						
import processing

from numpy import array

from datetime import datetime

import os

class IdragraRasterizeDomain(QgsProcessingAlgorithm):
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
	
	INPUTLIST= 'INPUT_LIST'
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
		return IdragraRasterizeDomain()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraRasterizeDomain'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Raster map of domain')

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
						The algorithm creates the raster of the domain map (i.e. the area of application of the Idragra model). 
						<b>Parameters:</b>
						Domain map: the vector layer to use as domain limits (polygons) [VECTOR_LAY]
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
	

		self.addParameter(QgsProcessingParameterMultipleLayers (self.INPUTLIST, self.tr('Layers to be exported'),\
																								QgsProcessing.TypeRaster, '', False))

				
		self.addParameter(QgsProcessingParameterExtent(self.RASTEREXT, self.tr('Raster extension')))
		
		self.addParameter(QgsProcessingParameterNumber(self.CELLDIM, self.tr('Raster cell dimension')))
		
		self.addParameter(QgsProcessingParameterFileDestination(self.DESTFILE, self.tr('Output raster'), self.tr('ASCII (*.asc)')))
		
		
	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		inputList = self.parameterAsLayerList(parameters, self.INPUTLIST, context)
		rasterExt = self.parameterAsExtent(parameters, self.RASTEREXT, context)
		cellDim = self.parameterAsDouble(parameters, self.CELLDIM, context)
		destFile = self.parameterAsFileOutput(parameters,	self.DESTFILE,	context)

		feedback.pushInfo(self.tr('Create domain from:'))
		# loop in input list
		entries = []
		preFormula = []
		for i,r in enumerate(inputList):
			# esclude time dependent raster
			rSource = r.source()
			# skip meteo matrix because they could be empty
			if not (('soiluse' in rSource) or ('irr_eff' in rSource) or ('irr_meth' in rSource) or ('Meteo_' in rSource)):
				feedback.pushInfo('* %s' % rSource)
				raster = QgsRasterCalculatorEntry()
				rasterAlias = 'raster'+str(i)+'@1'
				raster.ref = rasterAlias
				raster.raster = r
				raster.bandNumber = 1
				entries.append(raster)
				preFormula.append('("%s"* 0 + 1)'%rasterAlias)

		formula = ' * '.join(preFormula)
		formula = '('+formula+') * 0 +1'

		domainMap = QgsProcessingUtils.generateTempFilename('domain.tif')
		driverName = GdalUtils.getFormatShortNameFromFilename(domainMap)
		# Process calculation with input extent and resolution
		# TODO: update extention
		xllcorner = rasterExt.xMinimum()
		# yllcorner = extension.yMinimum()
		yurcorner = rasterExt.yMaximum()
		h = rasterExt.height()
		w = rasterExt.width()

		nrows = round(h / cellDim)
		ncols = round(w / cellDim)

		xurcorner = xllcorner + ncols * cellDim
		# yurcorner = yllcorner+nrows*outputCellSize
		yllcorner = yurcorner - nrows * cellDim

		newExt = QgsRectangle(xllcorner, yllcorner, xurcorner, yurcorner)

		feedback.pushInfo(self.tr('GeoInfo for domain map: %s %s %s %s %s %s %s %s' % (
			xllcorner, yllcorner, xurcorner, yurcorner, ncols, nrows, cellDim, cellDim)))

		calc = QgsRasterCalculator(formula, domainMap, driverName, newExt,
								   ncols, nrows, entries)
		res = calc.processCalculation(self.FEEDBACK)
		if res > 0:
			self.FEEDBACK.error(self.tr('Unable to resolve the formula %s')%formula,True)

		# tranform to ascii file
		algresult = processing.run("idragratools:IdragraSaveAscii",
						   {'INPUT': domainMap, 'DIGITS': 0,
							'OUTPUT': destFile},
						   context=context, feedback=feedback, is_child_algorithm=True)

		return {'DESTFILE':algresult['OUTPUT']}
		