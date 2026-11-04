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

from numpy import array

from datetime import datetime

import os

from algs.date_time_widget import DateTimeWidget
from tools.add_features_from_csv import addFeaturesFromCSV
from tools.parse_par_file import parseParFile
from tools.sqlite_driver import SQLiteDriver


class IdragraImportVectorMap(QgsProcessingAlgorithm):
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
	INPUT = 'INPUT'
	INPUT_LAY= 'INPUT_LAY'
	FIELD_BY = 'FIELD_BY'
	OUTPUT = 'OUTPUT'
	INIT_ASSIGN = 'INIT_ASSIGN'
	INIT_DATE = 'INIT_DATE'
	SAVE_EDIT = 'SAVE_EDIT'
	FEEDBACK = None

	EXTID_FLD = 'extid'
	DATE_FLD = 'date'

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraImportVectorMap()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraImportVectorMap'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Import vector map')

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
						The algorithm imports shapes from the input vector layer. 
						<b>Parameters:</b>
						Input layer: source shapes layer [INPUT_LAY]
						Category by: the attribute field with categories [FIELD_BY]
						Date: select a date to assign data, only if Assign to date is checked [INIT_DATE]
						Output layer: the destination container [OUTPUT]
						Save edit: automatically save all edits in the output layer [SAVE_EDIT]
						"""
		
		return self.tr(helpStr)

	def icon(self):
		self.alg_dir = os.path.dirname(__file__)
		icon = QIcon(os.path.join(self.alg_dir, 'idragra_tool.png'))
		return icon

	def flags(self):
		f = super().flags()| QgsProcessingAlgorithm.FlagSupportsInPlaceEdits
		return f

	def supportInPlaceEdit(self,layer):
		if not layer:
			return False
		return layer.isSpatial()

	def initAlgorithm(self, config=None):
		"""
		Here we define the inputs and output of the algorithm, along
		with some other properties.
		"""
		self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT, self.tr('Base layer'),
															  [QgsProcessing.TypeVectorPolygon]))

		self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT_LAY, self.tr('Input layer'),
															  [QgsProcessing.TypeVectorPolygon]))

		self.addParameter(QgsProcessingParameterField(self.FIELD_BY, self.tr('Category by'), None, self.INPUT_LAY,
													  QgsProcessingParameterField.Numeric))

		initDate = QgsProcessingParameterString(self.INIT_DATE, self.tr('Date'), '', False, False)
		initDate.setMetadata({'widget_wrapper': {'class': DateTimeWidget}})
		self.addParameter(initDate)

		# self.addParameter(QgsProcessingParameterFeatureSource(self.OUTPUT, self.tr('Output layer'),
		# 													  [QgsProcessing.TypeVectorPolygon]))

		self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr('Output layer'),
		 													  QgsProcessing.TypeVectorPolygon))


		# self.addParameter(QgsProcessingParameterBoolean(self.SAVE_EDIT, self.tr('Save edit'), True))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		source = self.parameterAsVectorLayer(parameters, self.INPUT, context)

		inLay = self.parameterAsVectorLayer(parameters, self.INPUT_LAY, context)

		catFld = self.parameterAsFields(parameters, self.FIELD_BY, context)[0]

		initDate = self.parameterAsString(parameters, self.INIT_DATE, context)

		# out_lay = self.parameterAsVectorLayer(parameters,self.OUTPUT,context)

		#(lay_id,out_lay) = self.parameterAsSink(parameters, self.OUTPUT, context)

		(out_lay, out_id) = self.parameterAsSink(
													parameters,
													self.OUTPUT,
													context,
													source.fields(),
													source.wkbType(),
													source.sourceCrs()
												)

		# saveEdit = self.parameterAsBoolean(parameters, self.SAVE_EDIT, context)

		self.FEEDBACK.pushInfo(self.tr('Get field names ...'))
		pr = out_lay.dataProvider()
		fieldNames = [field.name() for field in pr.fields()]
		nOfRec = 0

		self.FEEDBACK.pushInfo(self.tr('Check destination layer ...'))
		try:
			idxExtid = fieldNames.index(self.EXTID_FLD)
			idxDate = fieldNames.index(self.DATE_FLD)
		except Exception as e:
			msg = self.tr("""
						Destination file is not well formatted:
						You need at least the following fields:
						<%s> for category id,
						<%s> for timestamp
						Additional information:
						%s
						""")
			msg = msg % (self.EXTID_FLD, self.DATE_FLD, str(e))
			self.FEEDBACK.reportError(msg, True)
			return {'NUMOFIMPORTEDSHAPE':nOfRec}

		# loop in features and add to destination layer
		self.FEEDBACK.pushInfo(self.tr('Start editing destination layer ...'))
		out_lay.startEditing()

		self.FEEDBACK.pushInfo(self.tr('Inserting shapes ...'))
		numOfFeat =  inLay.featureCount()
		for feature in inLay.getFeatures():
			self.FEEDBACK.pushInfo('Inserting %s'%feature[catFld])
			newFeat = QgsFeature(pr.fields())
			geom = feature.geometry()
			geom.convertToMultiType()
			newFeat.setGeometry(geom)
			newFeat.setAttribute(idxExtid, feature[catFld])
			# ~ print('%s --> %s'%(k,idx))
			# ~ print('value: %s'%dataDict[k][i])
			newFeat.setAttribute(idxDate, initDate)
			out_lay.addFeature(newFeat)
			nOfRec+=1
			self.FEEDBACK.setProgress(100.0*nOfRec/numOfFeat)

		if saveEdit: out_lay.commitChanges()

		# load layer and set color scheme

		# self.FEEDBACK.pushInfo(
		# 		self.tr('Importation finished! Variable %s updated for station %s' % (tablename, sensorId)))
		# self.FEEDBACK.reportError(self.tr('Error: unable to import data'), False)
		#
		# self.FEEDBACK.setProgress(100)

		return {'NUMOFIMPORTEDSHAPE':nOfRec}


