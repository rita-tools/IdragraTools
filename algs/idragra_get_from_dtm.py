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

from math import tan, radians

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant
from qgis._analysis import QgsZonalStatistics
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
					   NULL, QgsFeature, edit, QgsRaster)
						
import processing

from numpy import array

from datetime import datetime

import os


class IdragraGetFromDtm(QgsProcessingAlgorithm):
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
	
	CROPFIELDLAY= 'CROPFIELD_LAY'
	WEATSTATLAY = 'WEATSTAT_LAY'
	DTMLAY = 'DTM_LAY'
	EMPTYONLY = 'EMPTY_ONLY'

	FEEDBACK = None

	SLOPEFLD = 'slope'
	ELEVFLD = 'alt'

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraGetFromDtm()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraGetFromDtm'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Get from DTM')

	def group(self):
		"""
		Returns the name of the group this algorithm belongs to. This string
		should be localised.
		"""
		return self.tr('Import')

	def groupId(self):
		"""
		Returns the unique ID of the group this algorithm belongs to. This
		string should be fixed for the algorithm, and must not be localised.
		The group id should be unique within each provider. Group id should
		contain lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraImport'

	def shortHelpString(self):
		"""
		Returns a localised short helper string for the algorithm. This string
		should provide a basic description about what the algorithm does and the
		parameters and outputs associated with it..
		"""
		
		helpStr = """
						The algorithm gets elevation and slope from DTM raster map. 
						<b>Parameters:</b>
						Crop field map: the vector layer with field limits (polygons) [CROPFIELD_LAY]
						Weather station map: the vector layer with the weather stations position [WEATSTAT_EXT]
						DTM raster map: the source of the altimetric information [DTM_LAY]
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
	
		self.addParameter(QgsProcessingParameterFeatureSource(self.CROPFIELDLAY, self.tr('Crop field map'),
															  [QgsProcessing.TypeVectorPolygon], None, True))
				
		self.addParameter(QgsProcessingParameterFeatureSource(self.WEATSTATLAY, self.tr('Weather station map'),
															  [QgsProcessing.TypeVectorPoint], None, True))

		self.addParameter(QgsProcessingParameterRasterLayer(self.DTMLAY, self.tr('DTM raster map')))

		self.addParameter(QgsProcessingParameterBoolean(self.EMPTYONLY, self.tr('Fill empty values only'),True))
		
	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		cropFieldLay = self.parameterAsVectorLayer(parameters, self.CROPFIELDLAY, context)
		weatStatLay = self.parameterAsVectorLayer(parameters, self.WEATSTATLAY, context)
		dtmLayer = self.parameterAsRasterLayer(parameters,self.DTMLAY,context)
		emptyOnly = self.parameterAsBoolean(parameters,self.EMPTYONLY,context)
		totNumOfEdit = 0
		if cropFieldLay:
			# check if the layer has the slope field
			fldIndex = cropFieldLay.fields().indexFromName(self.SLOPEFLD)

			if fldIndex<0:
				# do nothing
				self.FEEDBACK.reportError(self.tr('Unable to find "%s" field in crop field map')%self.SLOPEFLD, True)
			else:
				# make slope maps
				algresult = processing.run("native:slope",
											{'INPUT': dtmLayer,
											'Z_FACTOR': 1,
											'OUTPUT': 'TEMPORARY_OUTPUT'},
											context=context,
											feedback=feedback,
											is_child_algorithm=True)
				slopeLay = QgsRasterLayer(algresult['OUTPUT'],'slope')
				# fill attributes
				totNumOfEdit+=self.fillWithRasterStat(cropFieldLay,emptyOnly,fldIndex,slopeLay,lambda x: tan(radians(x)))

		if weatStatLay:
			# for each point, get value from raster
			fldIndex = weatStatLay.fields().indexFromName(self.ELEVFLD)
			if fldIndex < 0:
				# do nothing
				self.FEEDBACK.reportError(self.tr('Unable to find "%s" field in weather station map'%self.ELEVFLD), True)
			else:
				totNumOfEdit+=self.fillWithRasterValue(weatStatLay, emptyOnly, fldIndex, dtmLayer)

		return {'NUMOFEDIT': totNumOfEdit}

	def fillWithRasterValue(self,featLayer,emptyOnly,fieldIndex,rasterLay, callback = lambda x: float(x)):
		if emptyOnly:
			expr = QgsExpression('\"%s\" is Null' % self.SLOPEFLD)
			featList = featLayer.getFeatures(QgsFeatureRequest(expr))
		else:
			featList = featLayer.getFeatures()

		nOfFeat = len(list(featList))

		with edit(featLayer):
			i = 0.0
			for feat in featList:
				pointGeom = feat.geometry()
				pointGeom.convertToSingleType()
				pointPoint = pointGeom.asPoint()
				res = rasterLay.dataProvider().identify(pointPoint, QgsRaster.IdentifyFormatValue).results()
				flg = featLayer.changeAttributeValue(feat.id(), fieldIndex, callback(res[1]))
				self.FEEDBACK.setProgress(100 * i / nOfFeat)
				i+=1.0

		return nOfFeat


	def fillWithRasterStat(self,featLayer,emptyOnly,fieldIndex,rasterLay,callback = lambda x: float(x)):
		zStat = QgsZonalStatistics(featLayer, rasterLay, attributePrefix='', rasterBand=1,
								   stats=QgsZonalStatistics.Statistics(
									   QgsZonalStatistics.Mean))
		if emptyOnly:
			expr = QgsExpression('\"%s\" is Null' % self.SLOPEFLD)
			featList = featLayer.getFeatures(QgsFeatureRequest(expr))
		else:
			featList = featLayer.getFeatures()

		nOfFeat = len(list(featList))

		with edit(featLayer):
			i = 0.0
			for feat in featList:
				geom = feat.geometry()
				res	= zStat.calculateStatistics(rasterLay.dataProvider(), geom,
															rasterLay.rasterUnitsPerPixelX(),
															rasterLay.rasterUnitsPerPixelY(),
															1,
															QgsZonalStatistics.Statistics(
																	QgsZonalStatistics.Mean))
				flg = featLayer.changeAttributeValue(feat.id(), fieldIndex, callback(res[0]))
				self.FEEDBACK.setProgress(100*i/nOfFeat)
				i+=1.0


		return nOfFeat