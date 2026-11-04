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
					   NULL, QgsFeature)
						
import processing

import numpy as np

from datetime import datetime

import os

from ..tools.import_from_csv import *
from ..tools.compact_dataset import getRasterInfos


class IdragraCreateCapriseTable(QgsProcessingAlgorithm):
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
	TXTR_FLD = 'TXTR_FLD'
	DEPTHS = 'DEPTHS'
	OUT_TABLE = 'OUT_TABLE'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraCreateCapriseTable()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCreateCapriseTable'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Capillary rise table')

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
						The algorithm create a new table of capillary rise parameters required by IdrAgra.
						Parameters derive depth .  
						<b>Parameters:</b>
						Source table: a table with all necessary input [SOURCE_TABLE]
						Soil id: the field with the unique identifier of the soil type [SOILID_FLD]
						Maximum soil layer depth: the field with the maximum soil depth [MAXDEPTH_FLD],
						Texture code: the field with the numerical code of texture [TXTR_FLD]<sup>1</sup>
						Aggregation depths: the calculation depth. Multiple depths are separated by space. Unit must be the same of maximum soil layer depth [DEPTHS]
						Output table: the file path to the output table [OUT_TABLE]
						
						<b>Notes</b>
						(1) Texture codes from USDA textural Soil Classification - Module 3 - Study Guide: 1:sand, 2:Loamy sand, 3:sandy loam, 4:loam, 5:silt loam, 6:silt, 7:sandy clay loam, 8: clay loam, 9: silty clay loam, 10: sandy clay, 11: silty clay, 12:clay
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
			QgsProcessingParameterField(self.MAXDEPTH_FLD, self.tr('Maximum soil layer depth'), 'maxdepth',
										self.SOURCE_TABLE, QgsProcessingParameterField.Numeric))

		self.addParameter(
			QgsProcessingParameterField(self.TXTR_FLD, self.tr('Soil texture code'), 'txtr_code',
										self.SOURCE_TABLE, QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterString(self.DEPTHS, self.tr('Aggregation depths'), '0.1 0.9'))

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
		textFld = self.parameterAsFields(parameters, self.TXTR_FLD, context)[0]


		aggrDepths = self.parameterAsString(parameters, self.DEPTHS, context)
		aggrDepthList = aggrDepths.split(' ')
		aggrDepths = [0.0]
		try:
			for v in aggrDepthList:
				aggrDepths.append(float(v))
		except Exception as e:
			self.FEEDBACK.error(self.tr('Unable to parse %s parameter.') % self.DEPTHS, True)

		self.FEEDBACK.pushInfo(self.tr('Processing the following soil depths: %s' % (str(aggrDepths))))

		aggrDepths = np.cumsum(aggrDepths).tolist()

		# get value from source table
		soilidList = []
		maxdepthList = []
		txtrList = []

		for feature in sourceTable.getFeatures():
			soilidList.append(feature[soilidFld])
			maxdepthList.append(feature[maxdepthFld])
			txtrList.append(feature[textFld])

		# get list of unique id
		# print('soilidList',soilidList)
		uniqueSoilIds = list(set(soilidList))
		uniqueSoilIds.sort()

		self.FEEDBACK.pushInfo(self.tr('Processing the following soil codes: %s' % (str(uniqueSoilIds))))

		# prepare the destination field
		fldList = QgsFields()
		fldList.append(QgsField(soilidFld, QVariant.Int))

		fldList.append(QgsField('main_txtr', QVariant.Double))
		fldList.append(QgsField('CapRisePar_a3', QVariant.Double))
		fldList.append(QgsField('CapRisePar_a4', QVariant.Double))
		fldList.append(QgsField('CapRisePar_b1', QVariant.Double))
		fldList.append(QgsField('CapRisePar_b2', QVariant.Double))
		fldList.append(QgsField('CapRisePar_b3', QVariant.Double))
		fldList.append(QgsField('CapRisePar_b4', QVariant.Double))

		# make a numpy array
		data = np.column_stack([soilidList,
								maxdepthList,
								txtrList
								])

		# convert texture code in classes useful for the model of Liu et al. (2006)
		# USDA texture codes
		# 1:sand, 2:Loamy sand, 3:sandy loam,
		# 4:loam, 5:silt loam, 6:silt,
		# 7:sandy clay loam, 8: clay loam, 9: silty clay loam, 10: sandy clay, 11: silty clay, 12:clay
		# Macro texture classes VS USDA texture classes
		# 101: Sandy loam soil -> 1,2,3,
		# 102: Silt loam soil -> 4,5,6
		# 103: Clay loam soil -> 7,8,9,10,11,12
		data[data[:, 2] == 1, 2] = 101
		data[data[:, 2] == 2, 2] = 101
		data[data[:, 2] == 3, 2] = 101
		data[data[:, 2] == 4, 2] = 102
		data[data[:, 2] == 5, 2] = 102
		data[data[:, 2] == 6, 2] = 102
		data[data[:, 2] == 7, 2] = 103
		data[data[:, 2] == 8, 2] = 103
		data[data[:, 2] == 9, 2] = 103
		data[data[:, 2] == 10, 2] = 103
		data[data[:, 2] == 11, 2] = 103
		data[data[:, 2] == 12, 2] = 103
		# parameters 101 102 103
		liuPars = {
			'CapRisePar_b1': [-0.16, -0.17, -0.32],
			'CapRisePar_b2': [-0.54, -0.27, -0.16],
			'CapRisePar_a3': [-0.15, -1.3, -1.4],
			'CapRisePar_b3': [2.1, 6.6, 6.8],
			'CapRisePar_a4': [7.55, 4.6, 1.11],
			'CapRisePar_b4': [-2.03, -0.65, -0.98]
		}
		# TODO: check a4, b1, !!!
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
			self.FEEDBACK.pushInfo(self.tr('Processing soil id: %s' % (str(i))))
			feat = QgsFeature(fldList)
			feat[soilidFld] = i
			selData = data[np.where(data[:, 0] == i), :][0]
			#print('i',i,'selData',selData)
			# sort array by depths
			selData = selData[np.argsort(selData[:, 1])]
			#print('i', i, 'sorted selData', selData)


			# apply the function
			mainClass = int(self.applyAggrFun(selData[:, 2], selData[:, 1], max(aggrDepths),
														   np.amax(selData[:, 1]), self.mainValue))
			feat['main_txtr'] = mainClass

			feat['CapRisePar_b1'] = liuPars['CapRisePar_b1'][mainClass-101]
			feat['CapRisePar_b2'] = liuPars['CapRisePar_b2'][mainClass - 101]
			feat['CapRisePar_a3'] = liuPars['CapRisePar_a3'][mainClass - 101]
			feat['CapRisePar_b3'] = liuPars['CapRisePar_b3'][mainClass - 101]
			feat['CapRisePar_a4'] = liuPars['CapRisePar_a4'][mainClass - 101]
			feat['CapRisePar_b4'] = liuPars['CapRisePar_b4'][mainClass - 101]

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
		#print('valueArray',valueArray)
		#print('weigthArray',weigthArray)
		meanVal = aggrFun(valueArray,weigthArray)
		# return python type value
		return round(meanVal.item(),6)

	def mainValue(self,valueArray,weigthArray):
		rankArray = np.arange(len(valueArray))
		meanIdx = np.max(rankArray)
		if (sum(weigthArray)>0):
			meanIdx = round(sum(weigthArray * rankArray)/sum(weigthArray))
		else:
			self.FEEDBACK.reportError(self.tr('Unable to find the main value, the deeper layer will be used as reference.'),False)

		return valueArray[meanIdx]