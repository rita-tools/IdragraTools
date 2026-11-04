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

from math import tan

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant
from qgis import processing
from qgis.core import QgsProcessingParameterRasterDestination
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
					   NULL, QgsFeature, QgsProcessingOutputRasterLayer, QgsProcessingUtils)

import numpy as np

from datetime import datetime

import os

from ..tools.make_weight_matrix import makeWeightMatrix_WW
from ..tools.import_from_csv import *
from ..tools.compact_dataset import getRasterInfos


class IdragraCreateElevToField(QgsProcessingAlgorithm):
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

	FIELD_LAY = 'FIELD_LAY'

	ELEV_LAY = 'ELEV_LAY'
	WT_ELEV_LAY = 'WT_ELEV_LAY'
	LANDUSE_LAY = 'LANDUSE_LAY'
	IRRMETH_LAY = 'IRRMETH_LAY'

	SLP_MIN = 'SLP_MIN' # minimum values for slope
	SLP_MAX = 'SLP_MAX' # maximum values for slope

	WTD_MIN = 'WTD_MIN' # water table depth minimum value

	OUT_LAY = 'OUT_LAY'

	FEEDBACK = None

	alg_result = {'OUTPUT':None}
	alg_result1 = {'OUTPUT':None}
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraCreateElevToField()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCreateElevToField'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Elevation to field')

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
						The algorithm create a new shapes file with slope and water table depth values obtained from raster maps.
						<b>Parameters:</b>
						Fields: the field map [FIELD_LAY]
						Elevation: elevation raster map [ELEV_LAY]
						Water table elevation: one or more water table elevation raster map [WT_ELEV_LAY]
						Minimum slope value: the lowest acceptable value for slopes [SLP_MIN]
						Maximum slope value: the highest acceptable value for slopes [SLP_MAX]
						Minimum water table depth value: the lowest acceptable value for water table [WTD_MIN]
						Output table: the file path to the output table [OUT_LAY]
						
						<b>Notes</b>
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

		self.addParameter(QgsProcessingParameterFeatureSource(self.FIELD_LAY, self.tr('Fields'),
															  [QgsProcessing.TypeVectorPolygon], None, False))

		self.addParameter(QgsProcessingParameterRasterLayer(self.ELEV_LAY, self.tr('Elevation'),None, True))

		self.addParameter(QgsProcessingParameterMultipleLayers(self.WT_ELEV_LAY, self.tr('Water table elevation'), \
															   QgsProcessing.TypeRaster, '', True))

		self.addParameter(QgsProcessingParameterNumber(self.SLP_MIN, self.tr('Minimum slope value'),
													   QgsProcessingParameterNumber.Double, 0.0,True))

		self.addParameter(QgsProcessingParameterNumber(self.SLP_MAX, self.tr('Maximum slope value'),
													   QgsProcessingParameterNumber.Double, 1000,True))

		self.addParameter(QgsProcessingParameterNumber(self.WTD_MIN, self.tr('Minimum water table depth'),
													   QgsProcessingParameterNumber.Double, 0.5,True))

		self.addParameter(
			QgsProcessingParameterFeatureSink(self.OUT_LAY, self.tr('Output layer'), QgsProcessing.TypeVectorPolygon))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		wt_col_list = []

		# get params
		field_lay = self.parameterAsVectorLayer(parameters, self.FIELD_LAY, context)

		try:
			elev_lay = self.parameterAsRasterLayer(parameters, self.ELEV_LAY, context)
			wt_lay_list = self.parameterAsLayerList(parameters, self.WT_ELEV_LAY, context)
		except:
			elev_lay = None
			wt_lay_list = []

		slp_min = self.parameterAsDouble(parameters, self.SLP_MIN, context)
		slp_max = self.parameterAsDouble(parameters, self.SLP_MAX, context)
		wtd_min = self.parameterAsDouble(parameters, self.WTD_MIN, context)

		# TODO: check if elev and/or water table is missing
		# store elevation col name
		elev_col = 'elev_mean'
		# store slope col name
		slp_col = 'slp_mean'
		# store base water table depth
		wt_col = 'watertable_mean'

		# init algresult
		self.alg_result['OUTPUT'] = field_lay

		if elev_lay:
			self.FEEDBACK.pushInfo(self.tr('Processing %s' % elev_lay.name()))
			elev_file = QgsProcessingUtils.generateTempFilename('elev_stats.gpkg')
			# make zonal statistics
			self.alg_result = processing.run("native:zonalstatisticsfb",
											  {'INPUT': field_lay,
											   'INPUT_RASTER': elev_lay, 'RASTER_BAND': 1,
											   'COLUMN_PREFIX': 'elev_', 'STATISTICS': [2],
											   'OUTPUT': elev_file},
												context = context, feedback = self.FEEDBACK, is_child_algorithm = True
												)


			# make slope map
			slp_file = QgsProcessingUtils.generateTempFilename('slp_stats.gpkg')

			self.alg_result1 = processing.run("native:slope",
									   {'INPUT': elev_lay,
										'Z_FACTOR': 1,
										'OUTPUT': 'TEMPORARY_OUTPUT'},
												context = context, feedback = self.FEEDBACK, is_child_algorithm = True
												)


			self.alg_result = processing.run("native:zonalstatisticsfb",
										   {'INPUT': elev_file,
											'INPUT_RASTER': self.alg_result1['OUTPUT'], 'RASTER_BAND': 1,
											'COLUMN_PREFIX': 'slp_', 'STATISTICS': [2],
											'OUTPUT': slp_file},
												context = context, feedback = self.FEEDBACK, is_child_algorithm = True
												)

			self.alg_result['OUTPUT'] = slp_file
			self.alg_result1['OUTPUT'] = self.alg_result['OUTPUT']

			# get water table elevation
			for wt_lay in wt_lay_list:
				self.FEEDBACK.pushInfo(self.tr('Processing %s' % wt_lay.name()))
				self.alg_result['OUTPUT'] = QgsProcessingUtils.generateTempFilename(wt_lay.name()+'.gpkg')
				self.alg_result = processing.run("native:zonalstatisticsfb",
												 {'INPUT': self.alg_result1['OUTPUT'],
												  'INPUT_RASTER': wt_lay, 'RASTER_BAND': 1,
												  'COLUMN_PREFIX': wt_lay.name()+'_', 'STATISTICS': [2],
												  'OUTPUT': self.alg_result['OUTPUT']},
												context = context, feedback = self.FEEDBACK, is_child_algorithm = False
												)

				wt_col_list.append(wt_lay.name()+'_mean')
				self.alg_result1['OUTPUT'] = self.alg_result['OUTPUT']

		self.FEEDBACK.pushInfo(self.tr('Get data from %s' % self.alg_result['OUTPUT']))

		self.alg_result['OUTPUT'] = QgsVectorLayer(self.alg_result['OUTPUT'],'temp','ogr')

		# copy feature to sink and parse results
		fldList = self.alg_result['OUTPUT'].fields()

		if not (slp_col in fldList.names()):
			fldList.append(QgsField(slp_col,QVariant.Double))

		if not elev_lay:
			fldList.append(QgsField(wt_col,QVariant.Double))


		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.OUT_LAY,
			context,
			fldList,
			self.alg_result['OUTPUT'].wkbType(),
			self.alg_result['OUTPUT'].sourceCrs()
		)

		# get value from source table
		c = 0
		nFeat = self.alg_result['OUTPUT'].featureCount()

		for feat in self.alg_result['OUTPUT'].getFeatures():
			c+=1
			self.FEEDBACK.setProgress(100.0 * c / nFeat)

			new_feat = QgsFeature(feat)
			if elev_lay:
				elev = new_feat[elev_col]

				if elev:
					# transform slope from degree to tangent
					slp_deg = new_feat[slp_col]
					slp_tan = 100*tan(slp_deg/180)
					slp_tan = max(slp_tan,slp_min)
					slp_tan = min(slp_tan, slp_max)
				else:
					slp_tan = slp_min
					self.FEEDBACK.reportError(
						self.tr('Unable to calculate slope for element %s [%s]' %
								(new_feat['name'], new_feat['id'])), False)
				# save results
				new_feat[slp_col] = slp_tan

				# transform watertable elev to water table depth
				for wt_col in wt_col_list:
					wt_elev = new_feat[wt_col]

					if wt_elev:
						wt_depth = elev-wt_elev
					else:
						wt_depth = wtd_min
						self.FEEDBACK.reportError(
							self.tr('Unable to calculate water depth for element %s [%s]'%
									(new_feat['name'],new_feat['id'])),False)

					wt_depth = max(wt_depth, wtd_min)
					# save results
					new_feat[wt_col] = wt_depth
			else:
				new_feat[slp_col] = slp_min
				new_feat[wt_col] = wtd_min

			sink.addFeature(new_feat, QgsFeatureSink.FastInsert)

		return {self.OUT_LAY: dest_id}
