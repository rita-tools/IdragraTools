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
from qgis.core import QgsProcessingParameterMapLayer, QgsFeature
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
						QgsProcessingParameterFile,
						QgsProcessingParameterString,
						QgsProcessingParameterNumber,
						QgsProcessingParameterBoolean,
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
						NULL)
						
import processing

from numpy import array

from datetime import datetime

import os

from ..tools.import_from_csv import *


class IdragraImportTimeserie(QgsProcessingAlgorithm):
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
	
	INPUTFILE= 'INPUT_FILE'
	SENSORID = 'SENSOR_ID'
	TIMEFORMAT = 'TIME_FORMAT'
	SEP = 'SEP'
	TSCOL = 'TS_COL'
	VALCOL = 'VAL_COL'
	SKIPLINE = 'SKIP_LINE'
	OUTPUTTABLE = 'OUTPUT_TABLE'

	# default field configuration
	TIMESTAMP_FLD = 'timestamp'
	SENSORID_FLD = 'wsid'
	VALUE_FLD = 'recval'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraImportTimeserie()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraImportTimeserie'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Import time series')

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
						Import time series data from a text file (e.g. CSV) in the database.
						<b>Parameters:</b>
						Time serie text file: the source of the data [INPUT_FILE]
						Sensor id: the unique id of the measuring station [SENSOR_ID]<sup>1</sup>
						Column separator: the character used as column separator in the text file [SEP]<sup>2</sup>
						Date time column index: the index (1 is the first) of the column representing the time [TS_COL]
						Value column index: the index (1 is the first) of the column representing the value [VAL_COL]
						Time format: the way the time is stored in the text file [TIME_FORMAT]<sup>3</sup>
						Number of lines to skip: the number of line to skip in the file starting from the top (1 is the first) [SKIP_LINE]<sup>4</sup>
						Destination table: the file where data will be saved [OUTPUT_TABLE]
						<b>Notes:</b>
						[1] the unique id used in the database to define weather station, nodes or control points
						[2] use space character for TAB
						[3] time formats follow python 3 rules as reported here: <a href="https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes">strftime() and strptime() Format Codes</a>
						some common cases are:
						'%d/%m/%y' means 31/01/2000 (day is the first in zero-padded decimal number)
						'%d-%m-%y' means 31-01-2000 (same as before but with different separation character)
						'%y/%m/%d %H:%M' means 2020/01/01 00:00
						[4] column data must contains only recognizable date or number. Empty lines cause importation stop
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
		self.addParameter(	QgsProcessingParameterFile(self.INPUTFILE, self.tr('Time serie text file'),
														QgsProcessingParameterFile.Behavior.File,'*.*','',False,
														 'Comma Separated File (*.csv);;text file (*.txt);;All files (*.*)'))

		self.addParameter(	QgsProcessingParameterNumber(self.SENSORID, self.tr('Sensor id'),
														   QgsProcessingParameterNumber.Integer, 1, False, 1))
				
		self.addParameter(	QgsProcessingParameterString(self.SEP, self.tr('Column separator'), ';',False, False))
		
		self.addParameter(	QgsProcessingParameterNumber(self.TSCOL, self.tr('Date time column index'),
														   QgsProcessingParameterNumber.Integer, 1, False, 1))

		self.addParameter(	QgsProcessingParameterNumber(self.VALCOL, self.tr('Value column index'),
														   QgsProcessingParameterNumber.Integer, 1, False, 1))
				
		self.addParameter(	QgsProcessingParameterString(self.TIMEFORMAT, self.tr('Time format'), '%d/%m/%y',False, False))
		
		self.addParameter(	QgsProcessingParameterNumber(self.SKIPLINE, self.tr('Number of lines to skip'),
														   QgsProcessingParameterNumber.Integer, 0, False, 1))

		self.addParameter(
			QgsProcessingParameterFeatureSink(self.OUTPUTTABLE, self.tr('Select output file'), QgsProcessing.TypeFile))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		
		importFile = self.parameterAsFile(parameters, self.INPUTFILE, context)

		sensorId = self.parameterAsInt(parameters, self.SENSORID, context)
		
		sep = self.parameterAsString(parameters, self.SEP, context)
		
		tsCol = self.parameterAsInt(parameters, self.TSCOL, context)
		valCol = self.parameterAsInt(parameters, self.VALCOL, context)
				
		timeFormat = self.parameterAsString(parameters, self.TIMEFORMAT, context)
		
		skipLine = self.parameterAsInt(parameters, self.SKIPLINE, context)

		fldList = QgsFields()
		fldList.append(QgsField(self.TIMESTAMP_FLD, QVariant.String))
		fldList.append(QgsField(self.SENSORID_FLD, QVariant.Int))
		fldList.append(QgsField(self.VALUE_FLD, QVariant.Double))

		# get output file
		(destTable, dest_id) = self.parameterAsSink(
			parameters,
			self.OUTPUTTABLE,
			context,
			fldList
		)


		self.FEEDBACK.pushInfo(self.tr('Got parameters!') )

		c = -1
		c = self.importFromCSV(filename = importFile, tablelay=destTable, timeFldIdx=tsCol-1, valueFldIdx=valCol-1,
									sensorId=sensorId, skip=skipLine,timeFormat =timeFormat,column_sep=sep,fieldList = fldList)
			
		return {'NUMOFIMPORTEDRECORD': c,'OUTPUT_TABLE':dest_id}
		
		#https://www.faunalia.eu/fr/blog/2019-07-02-custom-processing-widget

	def importFromCSV(self,filename,tablelay, timeFldIdx, valueFldIdx, sensorId, skip,timeFormat,column_sep,fieldList):
		in_file = open(filename, "r")
		# check if destination table is well formatted
		nOfRec = 0

		parseLines = True
		i = 0
		while parseLines:
			in_line = in_file.readline()
			if i >= skip:
				if len(in_line) == 0:
					break

				# process the line
				in_line = in_line[:-1]
				# print 'LN %d: %s'%(i,in_line)
				data = in_line.split(column_sep)
				if len(data)<2:
					self.FEEDBACK.reportError(self.tr('Unable to parse line "%s", try another column separator')%
											  (in_line), True)
					break

				try:
					timestamp = datetime.strptime(data[timeFldIdx], timeFormat)
				except Exception as e:
					self.FEEDBACK.reportError(self.tr('Unable to parse timestamp "%s" with format "%s"\n%s')%
											  (data[timeFldIdx],timeFormat,str(e)), True)
					break
				try:
					value = float(data[valueFldIdx])
				except Exception as e:
					self.FEEDBACK.reportError(self.tr('Unable to parse value "%s"\n%s')%
											  (data[timeFldIdx],str(e)), True)
					break

				# add new record to table
				newFeat = QgsFeature(fieldList)
				newFeat.setAttribute(self.TIMESTAMP_FLD,timestamp.strftime('%Y-%m-%d'))
				newFeat.setAttribute(self.SENSORID_FLD, sensorId)
				newFeat.setAttribute(self.VALUE_FLD, value)
				tablelay.addFeature(newFeat, QgsFeatureSink.FastInsert)

				nOfRec += 1

			i += 1

		return nOfRec
