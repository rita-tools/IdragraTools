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

import math
from math import tan, radians

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant
from qgis.analysis import QgsZonalStatistics
from qgis.core import QgsProcessingParameterCrs
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

import numpy as np

from datetime import datetime

import os

from tools.add_features_from_csv import addFeaturesFromCSV
from tools.parse_par_file import parseParFile
from tools.sqlite_driver import SQLiteDriver


class IdragraSoilParams(QgsProcessingAlgorithm):
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
	TFC_FLD = 'TFC_FLD'
	TWP_FLD = 'TWP_FLD'
	TR_FLD = 'TR_FLD'
	TS_FLD = 'TS_FLD'
	DEPTHS = 'DEPTHS'
	OUT_TABLE = 'OUT_TABLE'

	FEEDBACK = None

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraSoilParams()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraSoilParams'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Soil Parameters table')

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
						The algorithm create a new table of soil parameters required by IdrAgra.
						Parameters derive from depth aggregation of soil profile properties.  
						<b>Parameters:</b>
						Source table: a table with all necessary input [SOURCE_TABLE]
						Soil id: the field with the unique identifier of the soil type [SOILID_FLD]
						Maximum soil layer depth: the field with the maximum soil depth [MAXDEPTH_FLD],
						K sat: the field with the hydraulic conductivity at saturation (cm h<sup>-1</sup>) [KSAT_FLD]										ksat double,
						Theta FC: the field with soil moisture at field capacity (-) [TFC_FLD]
						Theta WP: the field with soil moisture at wilting point (-) [TWP_FLD]
						Theta R: the field with residual soil moisture (-) [TR_FLD]
						Theta S: the field with residual soil moisture (-) [TS_FLD]
						Aggregation depths: the calculation depth. Multiple depths are separated by space. Unit must be the same of maximum soil layer depth [DEPTHS]
						Output table: the file path to the output table [OUT_TABLE]<sup>1</sup>
						
						<b>Notes</b>
						(1) Additional to K_sat, Theta FC, Theta WP. Theta R and Theta S, the following fields will be calculated:
						n: the field with the first parameter
						REW: the field with the second parameter
						
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
			QgsProcessingParameterField(self.MAXDEPTH_FLD, self.tr('Maximum soil layer depth'), None,
										self.SOURCE_TABLE, QgsProcessingParameterField.Numeric, False, True))
		self.addParameter(QgsProcessingParameterField(self.KSAT_FLD, self.tr('K sat'), None, self.SOURCE_TABLE,
													  QgsProcessingParameterField.Numeric,False, False))
		self.addParameter(QgsProcessingParameterField(self.TFC_FLD, self.tr('Theta FC'), None, self.SOURCE_TABLE,
													  QgsProcessingParameterField.Numeric, False, False))
		self.addParameter(QgsProcessingParameterField(self.TWP_FLD, self.tr('Theta WP'), None, self.SOURCE_TABLE,
													  QgsProcessingParameterField.Numeric, False, False))
		self.addParameter(QgsProcessingParameterField(self.TR_FLD, self.tr('Theta R'), None, self.SOURCE_TABLE,
													  QgsProcessingParameterField.Numeric, False, False))
		self.addParameter(QgsProcessingParameterField(self.TS_FLD, self.tr('Theta S'), None, self.SOURCE_TABLE,
													  QgsProcessingParameterField.Numeric, False, False))

		self.addParameter(QgsProcessingParameterString(self.DEPTHS,self.tr('Aggregation depths'),'0.1 0.9'))

		self.addParameter(QgsProcessingParameterFeatureSink(self.OUT_TABLE, self.tr('Output table'),QgsProcessing.TypeFile))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""

		self.FEEDBACK = feedback
		# get params
		sourceTable = self.parameterAsVectorLayer(parameters, self.SOURCE_TABLE, context)

		soilidFld = self.parameterAsFields(parameters, self.SOILID_FLD, context)
		soilidFld = soilidFld[0]
		maxdepthFld = self.parameterAsFields(parameters, self.MAXDEPTH_FLD, context)
		maxdepthFld = maxdepthFld[0]
		ksatFld = self.parameterAsFields(parameters, self.KSAT_FLD, context)
		ksatFld=ksatFld[0]
		theta_fcFld = self.parameterAsFields(parameters, self.TFC_FLD, context)
		theta_fcFld=theta_fcFld[0]
		theta_wpFld = self.parameterAsFields(parameters, self.TWP_FLD, context)
		theta_wpFld=theta_wpFld[0]
		theta_rFld = self.parameterAsFields(parameters, self.TR_FLD, context)
		theta_rFld=theta_rFld[0]
		theta_satFld = self.parameterAsFields(parameters, self.TS_FLD, context)
		theta_satFld=theta_satFld[0]

		# output field
		nFld = 'n'
		rewFld = 'rew'

		aggrDepths = self.parameterAsString(parameters,self.DEPTHS,context)
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
		ksatList = []
		theta_fcList = []
		theta_wpList = []
		theta_rList = []
		theta_satList = []

		for feature in sourceTable.getFeatures():
			soilidList.append(feature[soilidFld])
			maxdepthList.append(feature[maxdepthFld])
			ksatList.append(feature[ksatFld])
			theta_fcList.append(feature[theta_fcFld])
			theta_wpList.append(feature[theta_wpFld])
			theta_rList.append(feature[theta_rFld])
			theta_satList.append(feature[theta_satFld])

		# get list of unique id
		#print('soilidList',soilidList)
		uniqueSoilIds = list(set(soilidList))
		uniqueSoilIds.sort()

		self.FEEDBACK.pushInfo(self.tr('Processing the following soil codes: %s'%(str(uniqueSoilIds))))

		# prepare the destination field
		fldList = QgsFields()
		fldList.append(QgsField(soilidFld, QVariant.Int))

		for i in range(len(aggrDepths)-1):
			fldList.append(QgsField(ksatFld + str(i + 1), QVariant.Double))
			fldList.append(QgsField(nFld + str(i + 1), QVariant.Double))
			fldList.append(QgsField(rewFld + str(i + 1), QVariant.Double))
			fldList.append(QgsField(theta_fcFld + str(i + 1), QVariant.Double))
			fldList.append(QgsField(theta_wpFld + str(i + 1), QVariant.Double))
			fldList.append(QgsField(theta_rFld + str(i + 1), QVariant.Double))
			fldList.append(QgsField(theta_satFld + str(i + 1), QVariant.Double))

		# make a numpy array
		arrayList = []
		arrayList.append(soilidList)
		arrayList.append(maxdepthList)
		arrayList.append(ksatList)
		arrayList.append(theta_fcList)
		arrayList.append(theta_wpList)
		arrayList.append(theta_rList)
		arrayList.append(theta_satList)

		data = np.column_stack(arrayList)

		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.OUT_TABLE,
			context,
			fldList
		)

		#print('data', data)
		numOfSoilIds = len(uniqueSoilIds)
		# apply selected aggregation function
		c=0
		for i in uniqueSoilIds:
			feat = QgsFeature(fldList)
			feat[soilidFld] = i
			selData = data[np.where(data[:,0]==i),:][0]
			# sort array by depths
			selData = selData[np.argsort(selData[:, 1])]

			for d in range(len(aggrDepths)-1):
				# apply the function
				ksat = self.applyAggrFun(selData[:,2],selData[:,1],aggrDepths[d],
															      aggrDepths[d+1],self.harmonicMean)
				thetaFC = self.applyAggrFun(selData[:, 3], selData[:, 1], aggrDepths[d],
																   aggrDepths[d + 1], self.weightedArithmeticMean)
				thetaWP = self.applyAggrFun(selData[:, 4], selData[:, 1], aggrDepths[d],
																   aggrDepths[d + 1], self.weightedArithmeticMean)
				thetaR = self.applyAggrFun(selData[:, 5], selData[:, 1], aggrDepths[d],
																  aggrDepths[d + 1], self.weightedArithmeticMean)
				thetaSat = self.applyAggrFun(selData[:, 6], selData[:, 1], aggrDepths[d],
																	aggrDepths[d + 1], self.weightedArithmeticMean)

				feat[ksatFld + str(d + 1)] = ksat
				feat[theta_fcFld + str(d + 1)] = thetaFC
				feat[theta_rFld + str(d + 1)] = thetaR
				feat[theta_satFld + str(d + 1)] = thetaSat
				feat[theta_wpFld + str(d + 1)] = thetaWP

				# specific functions for n and rew
				feat[nFld + str(d + 1)] = math.log((0.2 / 10 / 24) / ksat) / math.log(
										(thetaFC - thetaR) / (thetaSat - thetaR))

				# with the empirical formula obtained from TABLE 19, FAO 1998 (Allen et al.1998)
				# TEW = 1000 * (T_fc - 0.5 * T_wp) * 0.15;
				# REW = -0.0108 * TEW. ^ 2 + 0.9227 * TEW - 4.4699; % formula
				TEW = 1000*(thetaFC - 0.5 * thetaWP) * 0.15
				REW = -0.0108 * TEW ** 2 + 0.9227 * TEW - 4.4699
				feat[rewFld + str(d + 1)] = REW

			sink.addFeature(feat, QgsFeatureSink.FastInsert)
			c+=1
			self.FEEDBACK.setProgress(100.0*c/numOfSoilIds)

		return {self.OUT_TABLE:dest_id}

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

	def harmonicMean(self,valueArray,weigthArray):
		meanValue = sum(weigthArray)/ sum(weigthArray/valueArray)
		return meanValue

	def weightedArithmeticMean(self,valueArray,weigthArray):
		meanValue = sum(weigthArray * valueArray)/sum(weigthArray)
		return meanValue
