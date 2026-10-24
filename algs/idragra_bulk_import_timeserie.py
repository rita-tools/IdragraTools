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
					   NULL, QgsFeature, edit, QgsRaster)
						
import processing

from numpy import array

from datetime import datetime

import os

import pandas as pd

from tools.add_features_from_csv import addFeaturesFromCSV
from tools.parse_par_file import parseParFile
from tools.sqlite_driver import SQLiteDriver



class IdragraBulkImportTimeserie(QgsProcessingAlgorithm):
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
	SOURCEFOLDER = 'SOURCE_FOLDER'
	TIMEFORMAT = 'TIME_FORMAT'
	SEP = 'SEP'
	REPLACE_EXISTING = 'REPLACE_EXISTING'
	FEEDBACK = None

	def __init__(self):
		super().__init__()
		self.supportedTableList =  ['ws_tmin','ws_tmax',
                        'ws_ptot','ws_umin','ws_umax',
                        'ws_vmed','ws_rgcorr','node_act_disc',
                        'node_disc']

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraBulkImportTimeserie()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraBulkImportTimeserie'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Bulk import time series')

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
						The algorithm import in the selected database all file in  the selected directory. 
						<b>Parameters:</b>
						DB filename: the file path to the existing database [DB_FILENAME]
						Source folder: the path to the folder that contains source file [SOURCE_FOLDER]<sup>1</sup>
						Timestamp format: the string to use to interpreter datetime value in the file
						Sep: the string separate to use to define column
						Notes:
						<sup>1</sup> in the source folder, each file must have CSV extention and the name is the numerical code of the sensor id (e.g. 100.CSV).
						The first line in the file is the header.
						The column with datetime should be marked as <i>timestamp</i>
						The column with the data to be imported should be marked with the name of the destination table (e.g. ws_tmax)
						The complete list of supported table names is: <i>%s</i>
						Note that the destination table must have the following structure: fid|timestamp|wsid|recval 
						""" %(', '.join(self.supportedTableList))
		
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
		self.addParameter(QgsProcessingParameterFile (self.DB_FILENAME, self.tr('DB filename'),
													  QgsProcessingParameterFile.Behavior.File, '*.*', '', False,
													  self.tr('Geopackage (*.gpkg);;All files (*.*)')))

		self.addParameter(QgsProcessingParameterFile (self.SOURCEFOLDER, self.tr('Source folder'),
													  QgsProcessingParameterFile.Behavior.Folder))

		self.addParameter(QgsProcessingParameterString(self.SEP, self.tr('Column separator'), ';', False, False))

		self.addParameter(
			QgsProcessingParameterString(self.TIMEFORMAT, self.tr('Time format'), '%d/%m/%Y', False, False))

		self.addParameter(QgsProcessingParameterBoolean(self.REPLACE_EXISTING, self.tr('Replace existing'),True,True))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		dbFilename = self.parameterAsFile(parameters,	self.DB_FILENAME,	context)
		sourceFolder = self.parameterAsFile(parameters, self.SOURCEFOLDER, context)
		sep = self.parameterAsString(parameters, self.SEP, context)
		timeFormat = self.parameterAsString(parameters, self.TIMEFORMAT, context)
		replace_existing = self.parameterAsBool(parameters,self.REPLACE_EXISTING,context)
		self.DBM = SQLiteDriver(dbFilename, False, None,self.FEEDBACK,self.tr, QgsProject.instance())

		# get list of table

		# list all csv file in the source folder
		fileList = os.listdir(sourceFolder)
		nOfFile = len(fileList)
		# for each file
		timeFld = 'timestamp'
		for i,f in enumerate(fileList):
			if self.FEEDBACK.isCanceled(): break

			self.FEEDBACK.setProgress(100.*i/nOfFile)
			self.FEEDBACK.pushInfo(self.tr('INFO: processing %s' % f))
			if f.endswith('.csv'):
				try:
					sensorId = int(f.replace('.csv',''))# try to convert the code
				except Exception as e:
					self.FEEDBACK.reportError(self.tr('Unable to parse sensor is from %s')%f,False)
					continue

				filePath = os.path.join(sourceFolder,f)
				#replace_existing = False
				if not replace_existing:
					self.DBM.startConnection()
					self.importDataFromCSV_wpandas(filename = filePath,
												   sensor_id = sensorId,
												   conn = self.DBM.conn,
												   progress = self.FEEDBACK,
												   timeFldName=timeFld,
												   timeFormat=timeFormat,
												   column_sep=sep)
					self.DBM.stopConnection()
				else:
					# for each supported table, find the field index
					for supportedTable in self.supportedTableList:
						# read the first line and get the timestamp field index
						tsIndex,valueIndex = self.readHeaderLine(filePath, sep, supportedTable,timeFld)
						# import the table
						if ((tsIndex>-1) and (valueIndex>-1)):
							self.importDataFromCSV(filePath, supportedTable,
												   tsIndex, valueIndex,
												   sensorId, 1, timeFormat, sep,
											  self.FEEDBACK, '')
						else:
							self.FEEDBACK.reportError(self.tr('Unsupported file format from %s') % filePath, False)
							self.FEEDBACK.pushInfo(self.tr('Field index for %s: %s' % (timeFld, tsIndex)))
							self.FEEDBACK.pushInfo(self.tr('Field index for %s: %s' % (supportedTable, valueIndex)))
							continue

		self.plugin_dir = os.path.join(os.path.dirname(__file__), os.pardir)

		self.FEEDBACK.setProgress(100.0)
		return {}

	def readHeaderLine(self,filename,column_sep,valueFld,tsFld):
		in_file = open(filename, "r")
		in_line = in_file.readline()
		in_line = in_line[:-1]
		if column_sep != ' ': in_line = in_line.replace(' ', '')
		data = in_line.split(column_sep)

		tsIndex = -1
		valueIndex = -1
		if tsFld in data: tsIndex = data.index(tsFld)
		if valueFld in data: valueIndex = data.index(valueFld)

		return tsIndex,valueIndex

	def importDataFromCSV_wpandas(self, filename, sensor_id, conn, progress,
								  timeFldName ='timestamp', timeFormat = '%Y-%m-%d', column_sep = ';'):
		# load as dataframe
		data = pd.read_csv(filename, sep=column_sep)
		print(data)
		data['timestamp'] = pd.to_datetime(data[timeFldName], format=timeFormat).dt.strftime('%Y-%m-%d')
		data['wsid'] =  sensor_id
		all_cols = list(data.columns.values)
		for col_name in all_cols:
			if col_name in self.supportedTableList:
				progress.pushInfo(self.tr('INFO: appending new values in %s' % col_name))
				# create temporary dataframe
				temp_df = data[['timestamp','wsid',col_name]]
				temp_df = temp_df.rename(columns={col_name: 'recval'})
				#append temporary dataframe to each table
				temp_df.to_sql(col_name, con=conn, if_exists='append', index= False)

	def importDataFromCSV(self, filename, tablename, timeFldIdx, valueFldIdx, sensorId, skip, timeFormat, column_sep,
						  progress, year=''):
		msg = ''
		progress.pushInfo(self.tr('INFO: loading %s' % filename))
		concatValues = []
		# oper CSV file
		in_file = open(filename, "r")
		i = 0
		while 1:
			in_line = in_file.readline()
			if i >= skip:
				if len(in_line) == 0:
					break

				# process the line
				in_line = in_line[:-1]
				if column_sep != ' ': in_line = in_line.replace(' ', '')
				# print 'LN %d: %s'%(i,in_line)
				data = in_line.split(column_sep)
				# try:
				timestamp = datetime.strptime(str(year) + data[timeFldIdx], timeFormat)
				value = float(data[valueFldIdx])
				concatValues.append("('" + timestamp.strftime('%Y-%m-%d') + "', '" + str(sensorId) + "', '" + str(value) + "')")
				# except ValueError:
				# 	progress.reportError(self.tr('Unable to parse line %s: %s') % (i,in_line), False)
				# except Exception as e:
				# 	progress.reportError(self.tr('Unmanaged error: %s') % str(e), False)

			i += 1

		progress.pushInfo(self.tr('n. of imported record: %s') % len(concatValues))
		if len(concatValues)<=0:
			return

		concatValues = ', '.join(concatValues)
		# create a temporary table to store uploaded data
		progress.pushInfo(self.tr('INFO: creating temporary table'))
		sql = 'DROP TABLE IF EXISTS dummy;'
		sql += 'CREATE TABLE dummy (timestamp2 text, wsid2 integer, recval2 double);'

		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.reportError(self.tr('SQL error: %s') % msg,False)
			progress.reportError(self.tr('at: %s') % sql,False)

		progress.pushInfo(self.tr('INFO: populating temporary table'))

		sql = 'BEGIN; '
		sql += 'REPLACE INTO dummy (timestamp2,wsid2,recval2) VALUES %s; ' % (concatValues)
		sql += 'COMMIT;'

		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.pushInfo(self.tr('SQL error: %s' % msg))
			progress.pushInfo(self.tr('at: %s' % sql))

		progress.pushInfo(self.tr('INFO: updating existing values in %s' % tablename))
		# update value if they already exist
		sql = 'UPDATE %s SET recval = (SELECT d.recval2 FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid)	WHERE EXISTS (SELECT * FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid);' % (
			tablename)
		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.pushInfo(self.tr('SQL error: %s' % msg))
			progress.pushInfo(self.tr('at: %s' % sql))

		# copy value to tablename id they aren't
		progress.pushInfo(self.tr('INFO: appending new values in %s' % tablename))
		sql = 'INSERT INTO %s (timestamp,wsid,recval) SELECT timestamp2,wsid2,recval2 FROM dummy d WHERE NOT EXISTS (SELECT * FROM %s WHERE timestamp = d.timestamp2 AND wsid = d.wsid2);' % (
			tablename, tablename)
		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.pushInfo(self.tr('SQL error: %s' % msg))
			progress.pushInfo(self.tr('at: %s' % sql))

		progress.pushInfo(self.tr('INFO: removing temporary table'))
		sql = 'DROP TABLE IF EXISTS dummy;'
		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.pushInfo(self.tr('SQL error: %s' % msg))
			progress.pushInfo(self.tr('at: %s' % sql))

		if msg == '':
			progress.pushInfo(
				self.tr('Importation finished! Variable %s updated for station %s' % (tablename, sensorId)))
		else:
			self.FEEDBACK.reportError(self.tr('Error: unable to import data'), False)

	def importTableFromCSV(self,filename, tablename, fieldList,skip=1, column_sep=';'):
		concatValues = []

		# oper CSV file
		in_file = open(filename, "r")
		i = 0
		while 1:
			in_line = in_file.readline()
			if i >= skip:
				if len(in_line) == 0:
					break

				# process the line
				in_line = in_line[:-1]
				#if column_sep != ' ': in_line = in_line.replace(' ', '')
				# print 'LN %d: %s'%(i,in_line)
				data = in_line.split(column_sep)

				concatValues.append("('" + "', '".join(data) + "')")

			i += 1

		sql = 'BEGIN; '
		sql += 'REPLACE INTO %s (%s) VALUES %s;' % (tablename, ', '.join(fieldList), ', '.join(concatValues))
		sql += 'COMMIT;'
		#self.FEEDBACK.pushInfo(self.tr('sql: %s' % sql))

		msg = self.DBM.executeSQL(sql)
		if msg != '':
			self.FEEDBACK.pushInfo(self.tr('SQL error: %s' % msg))
			self.FEEDBACK.pushInfo(self.tr('at: %s' % sql))
		else:
			self.FEEDBACK.pushInfo(self.tr('--> OK'))

