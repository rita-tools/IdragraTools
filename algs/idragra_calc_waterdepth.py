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

from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QCoreApplication,QVariant
from processing.algs.gdal.GdalUtils import GdalUtils
from qgis._analysis import QgsRasterCalculatorEntry, QgsRasterCalculator
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
					   NULL, QgsProcessingUtils, QgsRectangle)
						
import processing

import numpy as np

from datetime import datetime

import os

from ..tools.gis_grid import GisGrid
from ..tools.compact_dataset import getRasterInfos


class IdragraCalcWaterDepth(QgsProcessingAlgorithm):
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

	DTM = 'DTM'
	WATERTABLE = 'WATERTABLE'
	EXTENT = 'EXTENT'
	CELLSIZE = 'CELLSIZE'
	OUTPUT = 'OUTPUT'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraCalcWaterDepth()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCalcWaterDepth'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Calculate water table depth')

	def group(self):
		"""
		Returns the name of the group this algorithm belongs to. This string
		should be localised.
		"""
		return self.tr('Utility')

	def groupId(self):
		"""
		Returns the unique ID of the group this algorithm belongs to. This
		string should be fixed for the algorithm, and must not be localised.
		The group id should be unique within each provider. Group id should
		contain lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraUtility'

	def shortHelpString(self):
		"""
		Returns a localised short helper string for the algorithm. This string
		should provide a basic description about what the algorithm does and the
		parameters and outputs associated with it..
		"""

		helpStr = """
						The algorithm calculate water table depth from elevetion and ground water level map. 
						<b>Parameters:</b>
						Input raster: the raster layer to be transformed [DTM]
						Digit: number of digit to maintain [WATERTABLE]
						Extension: extensione of the resulting grid [EXTENT]
						Cell size: dimension of the resulting grid cell [CELLSIZE]
						Output raster: the name of the output raster [OUTPUT]
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
		DTM = 'DTM'
		WATERTABLE = 'WATERTABLE'
		EXTENT = 'EXTENT'
		CELLSIZE = 'CELLSIZE'
		OUTPUT = 'OUTPUT'
		self.addParameter(QgsProcessingParameterRasterLayer(self.DTM, self.tr('Elevation')))

		self.addParameter(QgsProcessingParameterRasterLayer(self.WATERTABLE, self.tr('Water table')))

		self.addParameter(QgsProcessingParameterExtent(self.EXTENT, self.tr('Output extent')))

		self.addParameter(QgsProcessingParameterNumber(self.CELLSIZE, self.tr('Output cell size')))
		
		self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, self.tr('Water table depth'), self.tr('ASCII (*.asc)')))
		
		
	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		elevation = self.parameterAsRasterLayer(parameters, self.DTM, context)
		watertable = self.parameterAsRasterLayer(parameters, self.WATERTABLE, context)
		outputExt = self.parameterAsExtent(parameters, self.EXTENT, context)
		outputCrs = self.parameterAsCrs(parameters, self.EXTENT, context)
		outputCellSize = self.parameterAsDouble(parameters, self.CELLSIZE, context)

		outputFile = self.parameterAsFileOutput(parameters,	self.OUTPUT, context)

		sExtent = elevation.extent()
		ulx = sExtent.xMinimum()
		uly = sExtent.yMaximum()
		lrx = sExtent.xMaximum()
		lry = sExtent.yMinimum()
		feedback.pushInfo(self.tr('Source extension: %s %s %s %s') % (ulx, uly, lrx, lry))

		#print('selected extension', outputExt)
		ulx = outputExt.xMinimum()
		uly = outputExt.yMaximum()
		lrx = outputExt.xMaximum()
		lry = outputExt.yMinimum()
		feedback.pushInfo(self.tr('Selected extension: %s %s %s %s') % (ulx, uly, lrx, lry))

		# TODO: check if it couses errors
		extension = outputExt
		# extension = sExtent.intersect(outputExt)
		# ulx = extension.xMinimum()
		# uly = extension.yMaximum()
		# lrx = extension.xMaximum()
		# lry = extension.yMinimum()
		feedback.pushInfo(self.tr('intersected extension: %s %s %s %s') % (ulx, uly, lrx, lry))

		if extension.area() == 0:
			feedback.reportError(self.tr('Error: selected extension not intersects layer extension'), False)
			extension = sExtent

		ulx = extension.xMinimum()
		uly = extension.yMaximum()
		lrx = extension.xMaximum()
		lry = extension.yMinimum()

		extraString = '-projwin %s %s %s %s -tr %s %s' % (ulx, uly, lrx, lry, outputCellSize, outputCellSize)
		feedback.pushInfo(self.tr('Final extension: %s %s %s %s') % (ulx, uly, lrx, lry))
		# clip/resample raster
		algresult = processing.run("gdal:translate",
								   {'INPUT': elevation, 'TARGET_CRS': outputCrs, 'NODATA': None,
									'COPY_SUBDATASETS': False, 'OPTIONS': '', 'EXTRA': extraString, 'DATA_TYPE': 6,
									'OUTPUT': 'TEMPORARY_OUTPUT'},
								   context=None,
								   feedback=feedback,
								   is_child_algorithm=True)

		elevClip = QgsRasterLayer(algresult['OUTPUT'],'elevation','gdal')

		geoDict = getRasterInfos(algresult['OUTPUT'])
		# feedback.pushInfo(self.tr('Georeference parameters: %s') % str(geoDict))
		dx = geoDict['dx']
		dy = geoDict['dy']
		ncols = geoDict['ncols']
		nrows = geoDict['nrows']
		xllcorner = geoDict['xllcorner']
		yllcorner = geoDict['yllcorner']
		xurcorner = geoDict['xllcorner'] + ncols * geoDict['dx']
		yurcorner = geoDict['yllcorner'] - nrows * geoDict['dy']

		feedback.pushInfo(self.tr('GeoInfo for clipped elevation: %s %s %s %s %s %s %s %s'%(xllcorner, yllcorner, xurcorner, yurcorner,ncols,nrows,dx,dy)))


		algresult = processing.run("gdal:translate",
								   {'INPUT': watertable, 'TARGET_CRS': outputCrs, 'NODATA': None,
									'COPY_SUBDATASETS': False, 'OPTIONS': '', 'EXTRA': extraString, 'DATA_TYPE': 6,
									'OUTPUT': 'TEMPORARY_OUTPUT'},
								   context=None,
								   feedback=feedback,
								   is_child_algorithm=True)

		wtClip = QgsRasterLayer(algresult['OUTPUT'],'elevation','gdal')

		geoDict = getRasterInfos(algresult['OUTPUT'])
		# feedback.pushInfo(self.tr('Georeference parameters: %s') % str(geoDict))
		dx = geoDict['dx']
		dy = geoDict['dy']
		ncols = geoDict['ncols']
		nrows = geoDict['nrows']
		xllcorner = geoDict['xllcorner']
		yllcorner = geoDict['yllcorner']
		xurcorner = geoDict['xllcorner'] + ncols * geoDict['dx']
		yurcorner = geoDict['yllcorner'] - nrows * geoDict['dy']

		finalExt = QgsRectangle (xllcorner, yllcorner, xurcorner, yurcorner)

		feedback.pushInfo(self.tr('GeoInfo for clipped water table: %s %s %s %s %s %s %s %s'%(xllcorner, yllcorner, xurcorner, yurcorner,ncols,nrows,dx,dy)))

		feedback.pushInfo(self.tr('Calculating water table depth ...'))
		feedback.setProgress(40)
		# make watertable depth
		entries = []
		# Define elevation
		raster1 = QgsRasterCalculatorEntry()
		raster1.ref = 'elevation@1'
		raster1.raster = elevClip
		raster1.bandNumber = 1
		entries.append(raster1)

		# Define elevation
		raster2 = QgsRasterCalculatorEntry()
		raster2.ref = 'watertable@1'
		raster2.raster = wtClip
		raster2.bandNumber = 1
		entries.append(raster2)

		wtdepth = QgsProcessingUtils.generateTempFilename('wtdepth.tif')
		driverName = GdalUtils.getFormatShortNameFromFilename(wtdepth)
		# Process calculation with input extent and resolution
		# TODO: update extention
		xllcorner = extension.xMinimum()
		#yllcorner = extension.yMinimum()
		yurcorner = extension.yMaximum()
		h = extension.height()
		w = extension.width()

		nrows =round(h/outputCellSize)
		ncols = round(w/outputCellSize)

		xurcorner = xllcorner+ncols*outputCellSize
		#yurcorner = yllcorner+nrows*outputCellSize
		yllcorner = yurcorner - nrows * outputCellSize

		newExt = QgsRectangle(xllcorner, yllcorner, xurcorner, yurcorner)

		feedback.pushInfo(self.tr('GeoInfo for water table depth: %s %s %s %s %s %s %s %s' % (
		xllcorner, yllcorner, xurcorner, yurcorner, ncols, nrows, dx, dy)))

		#calc = QgsRasterCalculator('"elevation@1"-"watertable@1"', wtdepth, driverName, newExt,
		#						   ncols, nrows, entries)

		calc = QgsRasterCalculator(
			'(("elevation@1"-0.5) > "watertable@1") * ("elevation@1" - "watertable@1") + (("elevation@1"-0.5) <= "watertable@1") * (1.0/2.0)',
			wtdepth, driverName, newExt,
			ncols, nrows, entries)

		res = calc.processCalculation(self.FEEDBACK)
		if res > 0: self.FEEDBACK.error(self.tr('Unable to resolve the formula'))
		# save file
		feedback.pushInfo(self.tr('Saving output ...'))
		feedback.setProgress(90)

		processing.run("idragratools:IdragraSaveAscii",
					   {'INPUT': wtdepth, 'DIGITS': 6,
						'OUTPUT': outputFile},
					   context=None, feedback=feedback, is_child_algorithm=False)

		# inputArray = self.convertRasterToNumpyArray(wtdepth)
		#
		# feedback.pushInfo(self.tr('Saving output ...'))
		# feedback.setProgress(90)
		# geoDict = getRasterInfos(wtdepth)
		# # feedback.pushInfo(self.tr('Georeference parameters: %s') % str(geoDict))
		# dx = geoDict['dx']
		# dy = geoDict['dy']
		# ncols = geoDict['ncols']
		# nrows = geoDict['nrows']
		# xllcorner = geoDict['xllcorner']
		# yllcorner = geoDict['yllcorner']
		# xurcorner = geoDict['xllcorner'] + ncols * geoDict['dx']
		# yurcorner = geoDict['yllcorner'] - nrows * geoDict['dy']
		#
		# aGrid = GisGrid(ncols=ncols, nrows=nrows, xcell=xllcorner, ycell=yllcorner, dx=dx, dy=-dy, nodata=-999,
		# 				EPSGid=outputCrs.postgisSrid(), progress=self.FEEDBACK)
		# aGrid.data = inputArray  # maxDepthArray#
		#
		# # save to file
		# aGrid.saveAsASC(filename = outputFile, d=6, useCellSize=False)

		return {'OUTPUT':outputFile}

	def convertRasterToNumpyArray(self,lyrFile):  # Input: QgsRasterLayer
		lyr = QgsRasterLayer(lyrFile, 'temp')
		values = []
		provider = lyr.dataProvider()
		nodata = provider.sourceNoDataValue (1)
		block = provider.block(1, lyr.extent(), lyr.width(), lyr.height())

		for i in range(lyr.height()):
			for j in range(lyr.width()):
				values.append(block.value(i, j))

		a = np.array(values)
		#print('shape of %s: %s, %s'%(lyrFile,lyr.height(),lyr.width()))
		a = np.reshape(a,(lyr.height(),lyr.width()))
		a[a==nodata]= np.nan
		return a