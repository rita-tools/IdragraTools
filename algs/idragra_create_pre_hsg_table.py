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
from qgis._core import QgsProcessingParameterRasterDestination
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
					   NULL, QgsFeature, QgsProcessingOutputRasterLayer)
						
import processing

import numpy as np

from datetime import datetime

import os

from ..tools.import_from_csv import *
from ..tools.compact_dataset import getRasterInfos


class IdragraCreatePreHSGTable(QgsProcessingAlgorithm):
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
	KSAT_FLD = 'KSAT_FLD'
	OUT_TABLE = 'OUT_TABLE'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraCreatePreHSGTable()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCreatePreHSGTable'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Pre HSG table')

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
						The algorithm create a new table of parameters necessary for the HSG classification (Mockus et al., 2009).
						<b>Parameters:</b>
						Source table: a table with all necessary input [SOURCE_TABLE]
						Soil id: the field with the unique identifier of the soil type [SOILID_FLD]
						Soil layer depth: the field with the maximum soil depth [MAXDEPTH_FLD],
						K sat: the field with the hydraulic conductivity at saturation (cm h<sup>-1</sup>) [KSAT_FLD]
						Output table: the file path to the output raster [OUT_TABLE]
						
						<b>Notes</b>
						The depth to water impermeable layer is set at least to the maximum depth of the soil profile
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
															  [QgsProcessing.TypeFile], None, False))

		self.addParameter(QgsProcessingParameterField(self.SOILID_FLD, self.tr('Soil id'), 'soilid', self.SOURCE_TABLE,
													  QgsProcessingParameterField.Numeric))
		self.addParameter(
			QgsProcessingParameterField(self.MAXDEPTH_FLD, self.tr('Maximum soil layer depth'), 'maxdepth',
										self.SOURCE_TABLE, QgsProcessingParameterField.Numeric))

		self.addParameter(
			QgsProcessingParameterField(self.KSAT_FLD, self.tr('K sat'), 'ksat',
										self.SOURCE_TABLE, QgsProcessingParameterField.Numeric))

		self.addParameter(
			QgsProcessingParameterFeatureSink(self.OUT_TABLE, self.tr('Output table'), QgsProcessing.TypeFile))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		sourceTable = self.parameterAsVectorLayer(parameters, self.SOURCE_TABLE, context)

		soilidFld = self.parameterAsFields(parameters, self.SOILID_FLD, context)[0]
		maxdepthFld = self.parameterAsFields(parameters, self.MAXDEPTH_FLD, context)[0]
		ksatFld = self.parameterAsFields(parameters, self.KSAT_FLD, context)[0]

		# get value from source table
		soilidList = []
		maxdepthList = []
		ksatList = []

		for feature in sourceTable.getFeatures():
			soilidList.append(feature[soilidFld])
			maxdepthList.append(feature[maxdepthFld])
			ksatList.append(feature[ksatFld])

		# get list of unique id
		# print('soilidList',soilidList)
		uniqueSoilIds = list(set(soilidList))
		uniqueSoilIds.sort()

		self.FEEDBACK.pushInfo(self.tr('Processing the following soil codes: %s' % (str(uniqueSoilIds))))

		# prepare the destination field
		fldList = QgsFields()
		fldList.append(QgsField(soilidFld, QVariant.Int))

		fldList.append(QgsField('maxsoildepth', QVariant.Double))
		fldList.append(QgsField('minksat50', QVariant.Double))
		fldList.append(QgsField('minksat60', QVariant.Double))
		fldList.append(QgsField('minksat100', QVariant.Double))

		# make a numpy array
		data = np.column_stack([soilidList,
								maxdepthList,
								ksatList
								])


		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.OUT_TABLE,
			context,
			fldList
		)

		# print('data', data)
		numOfSoilIds = len(uniqueSoilIds)
		# apply selected aggregation function
		c = 0
		for i in uniqueSoilIds:
			feat = QgsFeature(fldList)
			feat[soilidFld] = i
			selData = data[np.where(data[:, 0] == i), :][0]
			# print('i',i,'selData',selData)
			# sort array by depths
			selData = selData[np.argsort(selData[:, 1])]
			# print('i', i, 'sorted selData', selData)
			# TODO: manage length units
			# FIX: depth units
			# 0.01 micron/s --> 0.01 * 3600/(10*1000) cm/h
			ksLim = 0.01 * 3600/(10*1000)
			feat['maxsoildepth'] =self.maxImpDepth(selData[:, 2], selData[:, 1],ksLim)

			feat['minksat50'] = self.applyAggrFun(selData[:, 2], selData[:, 1], 0.0,
														   0.50, self.minVal)
			feat['minksat60'] = self.applyAggrFun(selData[:, 2], selData[:, 1], 0.0,
														   0.60, self.minVal)
			feat['minksat100'] = self.applyAggrFun(selData[:, 2], selData[:, 1], 0.0,
														   1.00, self.minVal)


			sink.addFeature(feat, QgsFeatureSink.FastInsert)
			c += 1
			self.FEEDBACK.setProgress(100.0 * c / numOfSoilIds)

		return {self.OUT_TABLE: dest_id}

	def applyAggrFun(self,valueArray,depthArray,minLim,maxLim,aggrFun):
		# subset on limits
		# calculate weigth
		depthArray = np.insert(depthArray, 0, 0.0)
		diff1 = depthArray-minLim
		diff2 = maxLim-depthArray
		depthArray[diff1<0]= minLim
		depthArray[diff2<0] = maxLim
		weigthArray = depthArray[1:]-depthArray[:-1]
		# apply aggregated function
		meanVal = aggrFun(valueArray,weigthArray)
		# return python type value
		return round(meanVal.item(),6)

	def minVal(self,valueArray,weigthArray):
		valueArray[weigthArray==0.0]=np.nan
		minVal = np.nanmin(valueArray)
		return minVal

	def maxImpDepth(self,valueArray,depthArray,ksLim):
		rankArray = np.arange(len(valueArray)) # init a new array with ordered value, implicitly from the most superficial to the deepest
		rankArray[valueArray>ksLim]=-1 # assign -1 where the layer is permeable more the ksLim
		resVal = np.amax(rankArray) # get the maximum value
		if resVal == -1: # the maximum value is -1
			# all layers are permeable
			resVal = np.amax(depthArray).item() # get the maximum layer depth
		else:
			# all other cases
			resVal = depthArray[resVal].item()

		return resVal
