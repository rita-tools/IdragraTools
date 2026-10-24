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
					   NULL, QgsFeature, QgsProcessingOutputRasterLayer, QgsGeometry)

import numpy as np

from datetime import datetime

import os

from ..tools.make_weight_matrix import makeWeightMatrix_WW
from ..tools.import_from_csv import *
from ..tools.compact_dataset import getRasterInfos


class IdragraMultiJoin(QgsProcessingAlgorithm):
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

	BASE_LAY = 'BASE_LAY'
	ATTR_LAY = 'ATTR_LAY'
	ATTR_FLD = 'ATTR_FIELD'
	SEP = 'SEP'

	OUT_LAY = 'OUT_LAY'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraMultiJoin()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraMultiJoin'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Make multiple join by position')

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
						The algorithm create a new table with data referred to each field.
						<b>Parameters:</b>
						Base map: the base map to join to [BASE_LAY]
						Attributes map: the map with the attributes to join [ATTR_LAY]
						Attributes field: the column containing the attribute [LU_COL]
						Output: the file path to the output map [OUT_LAY]
						
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

		self.addParameter(QgsProcessingParameterFeatureSource(self.BASE_LAY, self.tr('Base map'),
															  [QgsProcessing.TypeVectorAnyGeometry], None, False))

		self.addParameter(QgsProcessingParameterFeatureSource(self.ATTR_LAY, self.tr('Attributes map'),
															  [QgsProcessing.TypeVectorPolygon], None, False))
		self.addParameter(QgsProcessingParameterField(self.ATTR_FLD, self.tr('Attributes field'), 'extid', self.ATTR_LAY,
													  QgsProcessingParameterField.Any))

		self.addParameter(QgsProcessingParameterString(self.SEP, self.tr('Separator'), ' ', False,False))

		self.addParameter(
			QgsProcessingParameterFeatureSink(self.OUT_LAY, self.tr('Output layer'), QgsProcessing.TypeVectorPolygon))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		base_lay = self.parameterAsVectorLayer(parameters, self.BASE_LAY, context)

		attr_lay = self.parameterAsVectorLayer(parameters, self.ATTR_LAY, context)
		attr_fld = self.parameterAsFields(parameters, self.ATTR_FLD, context)[0]

		sep = self.parameterAsString(parameters,self.SEP,context)

		# prepare the output layer
		fldList = base_lay.fields()
		fldList.append(QgsField('joined', QVariant.String))

		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.OUT_LAY,
			context,
			fldList,
			base_lay.wkbType(),
			base_lay.sourceCrs()
		)

		# get value from source table
		c = 0
		nFeat = base_lay.featureCount()
		for feat in base_lay.getFeatures():
			c+=1
			self.FEEDBACK.setProgress(100.0 * c / nFeat)

			# get geometry and geometry data
			geom = feat.geometry()
			#c_geom = geom.centroid()
			c_geom = geom.pointOnSurface()

			# get id from other maps (maximum covered area)
			attr_list, gidx_list = self.selectByLocation(inputLayer=attr_lay, refGeom=c_geom, inputFld=attr_fld)
			attr_joined = sep.join([str(x) for x in attr_list])

			attr_list =feat.attributes()+\
					   [attr_joined]

			new_feat = QgsFeature(fldList)
			new_feat.setGeometry(geom)
			new_feat.setAttributes(attr_list)

			sink.addFeature(new_feat, QgsFeatureSink.FastInsert)

		return {self.OUT_LAY: dest_id}

	def calcGeomIndex(self, aGeom, refGeom, refArea, refLen):
		xGeom = refGeom.intersection(aGeom)
		geomIndex = 0.0
		try:
			xArea = xGeom.area()
			xLen = xGeom.length()
			if refArea > 0:
				geomIndex = round(100 * xArea / refArea, 2)  # it's a polygon
			elif refLen > 0:
				geomIndex = round(100 * xLen / refLen, 2)  # it's a line
			else:
				geomIndex = 100.0  # it's a point
		except Exception as e:
			print('Error in calcGeomIndex, %s' % str(e))

		return geomIndex


	def selectByLocation(self, inputLayer, refGeom, inputFld,filter_string = ''):

		# set a filter
		refArea = refGeom.area()
		refLen = 0  # unused
		target_ids = []
		gidxs = [] # list of geometry indexes
		if filter_string:
			req = QgsFeatureRequest().setFilterRect(refGeom.boundingBox()).setFilterExpression(filter_string)
		else:
			req = QgsFeatureRequest().setFilterRect(refGeom.boundingBox())

		for feature in inputLayer.getFeatures(req):
			aGeom = feature.geometry()
			geomIndex = self.calcGeomIndex(aGeom, refGeom, refArea, refLen)
			if geomIndex > 0:
				gidxs.append(geomIndex)
				#print('inputFld', inputFld)
				target_ids.append(feature[inputFld])

		return target_ids, gidxs
