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
					   NULL, QgsFeature, QgsProcessingOutputRasterLayer, QgsProcessingUtils)

import numpy as np

from datetime import datetime

import os

from ..tools.make_weight_matrix import makeWeightMatrix_WW
from ..tools.import_from_csv import *
from ..tools.compact_dataset import getRasterInfos


class IdragraCreateRasterToField(QgsProcessingAlgorithm):
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

	RASTER_LIST = 'RASTER_LIST'
	FLD_NAME_LIST = 'FLD_NAME_LIST'

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
		return IdragraCreateRasterToField()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCreateRasterToField'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Raster to field')

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
						The algorithm create a new shapes file with the most represented value
						in the raster(s) and add new fields as defined by the user.
						<b>Parameters:</b>
						Fields: the field map [FIELD_LAY]
						Raster(s): the list of selected rasters
						Attribute name(s): the list of the names of new attributes
						Output table: the file path to the output table [OUT_LAY]
						
						<b>Notes</b>
						The modal statistic (majority value) is calculated by default.
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

		self.addParameter(QgsProcessingParameterMultipleLayers(self.RASTER_LIST, self.tr('Raster(s) list'), \
															   QgsProcessing.TypeRaster, '', True))
		self.addParameter(QgsProcessingParameterString(self.FLD_NAME_LIST, self.tr('Attribute(s) list'),\
			'', False, True))

		self.addParameter(
			QgsProcessingParameterFeatureSink(self.OUT_LAY, self.tr('Output layer'), \
											  QgsProcessing.TypeVectorPolygon))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback

		# get params
		field_lay = self.parameterAsVectorLayer(parameters, self.FIELD_LAY, context)

		raster_lay_list =  self.parameterAsLayerList(parameters, self.RASTER_LIST, context)
		if not raster_lay_list: raster_lay_list=[]

		raster_names = [x.name() for x in raster_lay_list]

		self.FEEDBACK.pushInfo(self.tr('Raster names %s') % ','.join(raster_names))

		n_raster = len(raster_names)
		attributes_str = self.parameterAsString(parameters, self.FLD_NAME_LIST, context)
		attributes_list = attributes_str.split(' ')

		if '' in attributes_list: attributes_list = attributes_list.remove('')

		if attributes_list: n_attr = len(attributes_list)
		else:
			n_attr = 0
			attributes_list = []

		# fill missing attribute names
		if n_attr>=n_raster:
			attributes_list = attributes_list[0:n_raster]
		else:
			attributes_list = attributes_list+raster_names[n_attr:n_raster+1]

		self.FEEDBACK.pushInfo(self.tr('Attribute names %s') % ','.join(attributes_list))

		n_attr	= n_raster

		# init algresult
		self.alg_result1['OUTPUT'] = field_lay

		for raster_lay in raster_lay_list:
			self.FEEDBACK.pushInfo(self.tr('Processing %s' % raster_lay.name()))
			self.alg_result['OUTPUT'] = QgsProcessingUtils.generateTempFilename(raster_lay.name() + '.gpkg')

			# make zonal statistics
			self.alg_result = processing.run("native:zonalstatisticsfb",
											  {'INPUT': self.alg_result1['OUTPUT'],
											   'INPUT_RASTER': raster_lay.source(),
											   'RASTER_BAND': 1, 'COLUMN_PREFIX': raster_lay.name()+'_', 'STATISTICS': [9],
											   'OUTPUT': self.alg_result['OUTPUT']},
												context = context, feedback = self.FEEDBACK, is_child_algorithm = False
												)

			self.alg_result1['OUTPUT'] = self.alg_result['OUTPUT']

		self.alg_result['OUTPUT'] = QgsVectorLayer(self.alg_result['OUTPUT'], 'temp', 'ogr')

		# copy feature to sink and parse results
		fldList = field_lay.fields()

		for attr_name in attributes_list:
			if not (attr_name in fldList.names()):
				fldList.append(QgsField(attr_name, QVariant.Double))

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

			# DO SOMETHING

			sink.addFeature(new_feat, QgsFeatureSink.FastInsert)


		return {self.OUT_LAY: dest_id}
