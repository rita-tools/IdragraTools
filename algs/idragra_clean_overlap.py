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


class IdragraCleanOverlap(QgsProcessingAlgorithm):
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

	IN_LAY = 'IN_LAY'
	OUT_LAY = 'OUT_LAY'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraCleanOverlap()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCleanOverlap'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Clean ovelapping features')

	def group(self):
		"""
		Returns the name of the group this algorithm belongs to. This string
		should be localised.
		"""
		return self.tr('Analysis')

	def groupId(self):
		"""
		Returns the unique ID of the group this algorithm belongs to. This
		string should be fixed for the algorithm, and must not be localised.
		The group id should be unique within each provider. Group id should
		contain lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraAnalysis'

	def shortHelpString(self):
		"""
		Returns a localised short helper string for the algorithm. This string
		should provide a basic description about what the algorithm does and the
		parameters and outputs associated with it..
		"""
		
		helpStr = """
						The algorithm creates a new layer with only not overlapping polygons.
						<b>Parameters:</b>
						Input: the input layer [IN_LAY]
						Output: the output layer [OUT_LAY]
						
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

		self.addParameter(QgsProcessingParameterFeatureSource(self.IN_LAY, self.tr('Input'),
															  [QgsProcessing.TypeVectorAnyGeometry], None, False))

		self.addParameter(
			QgsProcessingParameterFeatureSink(self.OUT_LAY, self.tr('Output'), QgsProcessing.TypeVectorPolygon))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		in_lay = self.parameterAsVectorLayer(parameters, self.IN_LAY, context)

		# prepare the output layer
		fldList = in_lay.fields()
		fldList.append(QgsField('joined', QVariant.String))

		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.OUT_LAY,
			context,
			fldList,
			in_lay.wkbType(),
			in_lay.sourceCrs()
		)


		nFeat = in_lay.featureCount()
		processCount = 0
		# loop in layer 2
		justProcessed = []
		for poly1 in in_lay.getFeatures():

			if feedback.isCanceled():
				break

			processCount += 1
			feedback.setProgress(100 * float(processCount) / nFeat)

			justProcessed.append(poly1.id())
			geom1 = poly1.geometry()

			bbox = geom1.boundingBox()
			fit = in_lay.getFeatures(
				QgsFeatureRequest().setFilterRect(bbox))

			# use prepared geometries for faster intersection tests
			engine = QgsGeometry.createGeometryEngine(geom1.constGet())
			engine.prepareGeometry()

			# for each polygon in layer 2, get touching polygons in layer 1
			extid_list = [str(poly1['extid'])]
			for poly2 in fit:
				if (poly2.id() != poly1.id()) and \
						(poly2.id() not in justProcessed):

					geom2 = poly2.geometry()
					# compare geometries
					if engine.intersects(geom2.constGet()):
						# cut current geometry with intersection
						extid_list.append(str(poly2['extid']))

			sorted(extid_list)

			newAttr = ' '.join(extid_list)
			newFeat = QgsFeature(fldList)
			newFeat.setGeometry(geom1)
			newFeat.setAttributes(poly1.attributes()+[newAttr])

			# add to sink
			sink.addFeature(newFeat, QgsFeatureSink.FastInsert)

		del sink

		return {self.OUT_LAY: dest_id}
