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
					   QgsProcessingParameterVectorLayer,
					   QgsProcessingParameterString,
					   QgsProcessingParameterNumber,
					   QgsProcessingParameterRasterLayer,
					   QgsExpression,
					   QgsFeatureRequest,
					   QgsCoordinateReferenceSystem,
					   QgsCoordinateTransform,
					   QgsProcessingParameterFolderDestination,
					   QgsWkbTypes,
					   QgsFields,
					   QgsField,
					   QgsVectorFileWriter,
					   QgsVectorLayer,
					   QgsProject,
					   NULL, QgsProcessingParameterExtent, QgsProcessingParameterField)
						
import processing

from numpy import array

from datetime import datetime

import os

from ..tools.gis_grid import GisGrid
from ..tools.compact_dataset import getRasterInfos
from ..tools.make_weight_matrix import *


class IdragraExportWeights(QgsProcessingAlgorithm):
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
	
	VECTORLAY = 'VECTOR_LAYER'
	ID_FLD = 'ID_FLD'
	MAXNUM = 'MAX_NUM'
	RASTERLAY = 'RASTER_LAY'
	EXTENT = 'EXTENT'
	CELLSIZE = 'CELLSIZE'
	DESTFOLDER = 'DEST_FOLDER'
	
	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraExportWeights()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraExportWeights'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Weather weights')

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
						The algorithm exports the weights of each wheater stations to use for daily variable distribution. 
						<b>Parameters:</b>
						Weather station: the map of the weather stations [VECTOR_LAY]
						Weather station id: the field with the station id [ID_FLD]
						Maximum number: the maximum number of weather stations to consider [MAX_NUM]
						Reference raster: the raster map that define extiension and cell dimensions  (optional) [RASTERLAY]
						Reference extension: the output raster extension (optional) [EXTENT]
						Cell dimension: the output raster cell dimension (optional) [CELLSIZE]
						Export to: the path where new raster file will be saved [DEST_FOLDER]
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
		self.addParameter(QgsProcessingParameterFeatureSource(self.VECTORLAY, self.tr('Weather station'), [QgsProcessing.TypeVectorPoint]))

		self.addParameter(
			QgsProcessingParameterField(self.ID_FLD, self.tr('Weather station id'), '',
										self.VECTORLAY, QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterNumber(self.MAXNUM, self.tr('Maximum number')))
		
		self.addParameter(QgsProcessingParameterRasterLayer(self.RASTERLAY, self.tr('Reference raster'),None, True))

		self.addParameter(QgsProcessingParameterExtent(self.EXTENT, self.tr('Output extent'),None, True))

		self.addParameter(QgsProcessingParameterNumber(self.CELLSIZE, self.tr('Output cell size'),QgsProcessingParameterNumber.Double,None, True))
						
		self.addParameter(	QgsProcessingParameterFolderDestination(self.DESTFOLDER, self.tr('Export to')))
		

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		
		vectorLay = self.parameterAsSource(parameters, self.VECTORLAY, context)

		idFld = self.parameterAsFields(parameters, self.ID_FLD, context)[0]
		
		maxNum = self.parameterAsInt(parameters, self.MAXNUM, context)
		
		rasterLay = self.parameterAsRasterLayer(parameters, self.RASTERLAY, context)

		outputExt = self.parameterAsExtent(parameters, self.EXTENT, context)
		crs = self.parameterAsExtentCrs(parameters, self.EXTENT, context)
		outputCellSize = self.parameterAsDouble(parameters, self.CELLSIZE, context)
				
		destFolder = self.parameterAsFile(parameters, self.DESTFOLDER, context)
		
		nOfWS = -1
		
		# get raster georeferencing parameters
		if rasterLay:
			crs = rasterLay.crs()
			geoDict = getRasterInfos(rasterLay.source())
			feedback.pushInfo(self.tr('Georeference parameters: %s')%str(geoDict))
			dx = geoDict['dx']
			dy = geoDict['dy']
			ncols = geoDict['ncols']
			nrows = geoDict['nrows']
			xllcorner = geoDict['xllcorner']
			yllcorner = geoDict['yllcorner']
			xurcorner = geoDict['xllcorner']+ncols*geoDict['dx']
			yurcorner = geoDict['yllcorner']-nrows*geoDict['dy']
		else:
			# fit extension
			xllcorner = outputExt.xMinimum()
			# yllcorner = extension.yMinimum()
			yurcorner = outputExt.yMaximum()
			h = outputExt.height()
			w = outputExt.width()
			dx = outputCellSize
			dy = outputCellSize
			nrows = round(h / outputCellSize)
			ncols = round(w / outputCellSize)

			xurcorner = xllcorner + ncols * outputCellSize
			# yurcorner = yllcorner+nrows*outputCellSize
			yllcorner = yurcorner - nrows * outputCellSize

		self.FEEDBACK.pushInfo(self.tr('Ref params: %s %s %s %s %s %s %s %s'%
									   (xllcorner,xurcorner,yllcorner,yurcorner,dx,dy,ncols,nrows)))

		xList = []
		yList = []
		fidList = []
		# get coordinates of the selected weather stations (points)
		nOfWS = 0
		for feature in vectorLay.getFeatures():
			try:
				fidList.append(feature[idFld])
			except:
				feedback.reportError(self.tr('Selected layer has no numeric field named "%s"')%idFld,True)
				return {'NUMOFEXPORTEDMATRIX': -1}	
				
			xList.append(feature.geometry().asMultiPoint()[0].x())
			yList.append(feature.geometry().asMultiPoint()[0].y())
			nOfWS+=1
		
		# get matrix
		wMatrixList = makeWeightMatrix_WW(xllcorner, xurcorner, yllcorner, yurcorner, outputCellSize,
										  xList, yList, fidList, maxNum, feedback =feedback, tr = self.tr)
		
		# save matrix in folder
		aGrid = GisGrid(ncols=ncols, nrows=nrows, xcell=xllcorner, ycell=yllcorner,
						dx=dx, dy=dy,nodata = -9999,EPSGid = crs.postgisSrid (),progress = None)
		
		n = 0
		for wMatrix in wMatrixList:
			n+=1
			aGrid.data = wMatrix
			filename = os.path.join(destFolder,'Meteo_'+str(n)+'.asc')
			aGrid.saveAsASC(filename,d=6,useCellSize = True)
			
		return {'NUMOFEXPORTEDMATRIX': n}
		