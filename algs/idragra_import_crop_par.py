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
from qgis._core import QgsProcessingParameterCrs
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
					   NULL, QgsFeature, edit, QgsRaster, QgsGeometry)
						
import processing

from numpy import array

from datetime import datetime

import os

#from tools.add_features_from_csv import addFeaturesFromCSV
from tools.parse_par_file import parseParFile
from tools.sqlite_driver import SQLiteDriver


class IdragraImportCropPar(QgsProcessingAlgorithm):
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
	
	DB_FILENAME= 'DB_FILENAME'
	FILE_DIR = 'FILE_DIR'
	FEEDBACK = None
	DBM = None

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraImportCropPar()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraImportCropPar'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Crop pars files')

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
						The algorithm import crop parameters from files contained in the selected folder. 
						<b>Parameters:</b>
						DB filename: the file path to the database [DB_FILENAME]
						Files directory: the path where crop parameters files are saved [FILE_DIR]<sup>1<\sup>
						<b>Note:</b>
						[1] default is *.tab, the standard file format from IdrAgra.  
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
		self.addParameter(QgsProcessingParameterFile(self.DB_FILENAME, self.tr('DB filename'),
													 QgsProcessingParameterFile.Behavior.File, '*.*', '', False,
													 self.tr('Geopackage (*.gpkg);;All files (*.*)')))

		self.addParameter(QgsProcessingParameterFile(self.FILE_DIR, self.tr('Files directory'),
													 QgsProcessingParameterFile.Behavior.Folder))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		dbFilename = self.parameterAsFile(parameters,	self.DB_FILENAME,	context)
		fileDir = self.parameterAsFile(parameters, self.FILE_DIR, context)

		# open db connection
		self.DBM = SQLiteDriver(dbFilename, False, None, self.FEEDBACK, self.tr, QgsProject.instance())

		maxId = self.DBM.getMaxValue(tableName='idr_crop_types',colName='id')
		if not maxId: maxId =0

		# list all csv file in the source folder
		fileList = os.listdir(fileDir)
		nOfFile = len(fileList)
		# for each file
		c = 1 # counter of the added file
		for i, f in enumerate(fileList):
			self.FEEDBACK.setProgress(100. * i / nOfFile)
			self.FEEDBACK.pushInfo(self.tr('INFO: processing %s' % f))
			if f.endswith('.tab'):
				try:
					# read params from selected file
					cropDict = parseParFile(filename=os.path.join(fileDir, f), parSep='=', colSep=' ',
											feedback=self.FEEDBACK, tr=self.tr)
					cropDict['id'] = maxId+c
					cropDict['name'] = "'"+f.replace('.tab','')+"'"
					# update table in db
					# replace table with specific pars name GDD	Kcb	LAI	Hc	Sr
					cropDict['gdd'] = "'"+' '.join(list(cropDict['table']['GDD']))+"'"
					cropDict['kcb'] = "'"+' '.join(list(cropDict['table']['Kcb']))+"'"
					cropDict['lai'] = "'"+' '.join(list(cropDict['table']['LAI']))+"'"
					cropDict['hc'] = "'"+' '.join(list(cropDict['table']['Hc']))+"'"
					cropDict['sr'] = "'"+' '.join(list(cropDict['table']['Sr']))+"'"

					# delete table
					del cropDict['table']

					fieldNames = ','.join(list(cropDict.keys()))

					# convert all values to string
					for keys in cropDict:
						cropDict[keys] = str(cropDict[keys])

					fieldValues = ','.join(list(cropDict.values()))


					# add to db table
					sql = 'BEGIN; '
					sql += 'INSERT INTO idr_crop_types (%s) VALUES (%s); ' % (fieldNames,fieldValues)
					sql += 'COMMIT;'

					msg = self.DBM.executeSQL(sql)
					if msg != '':
						self.FEEDBACK.pushInfo(self.tr('SQL error: %s' % msg))
						self.FEEDBACK.pushInfo(self.tr('at: %s' % sql))
					c += 1
				except Exception as e:
					self.FEEDBACK.reportError(self.tr('Unable to parse crop par file %s')%f,False)
					continue


		return {self.DB_FILENAME:dbFilename}
