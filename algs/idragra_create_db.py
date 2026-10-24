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


class IdragraCreateDB(QgsProcessingAlgorithm):
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
	LOAD_SAMPLE_PAR = 'LOAD_SAMPLE_PAR'
	LOAD_SAMPLE_DATA = 'LOAD_SAMPLE_DATA'
	CRS = 'CRS'
	FEEDBACK = None
	DBM = None

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraCreateDB()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCreateDB'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Data base')

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
						The algorithm create a new database as support for the simulation. 
						<b>Parameters:</b>
						Load sample parameters: create a new database file with sample parameters in it [LOAD_SAMPLE_PAR]
						Load sample data: create a new database file with sample data in it [LOAD_SAMPLE_DATA]
						Coordinates Reference System: the CRS to use [CRS]
						DB filename: the file path to the database [DB_FILENAME]
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
		self.addParameter(QgsProcessingParameterFileDestination(self.DB_FILENAME, self.tr('DB filename'),
																self.tr('Geopackage (*.gpkg)')))#'Idragra db (*.idb)'

		self.addParameter(QgsProcessingParameterCrs (self.CRS, self.tr('Coordinates Reference System'),None, False))
				
		self.addParameter(QgsProcessingParameterBoolean(self.LOAD_SAMPLE_PAR, self.tr('Load sample parameter'),True))

		self.addParameter(QgsProcessingParameterBoolean(self.LOAD_SAMPLE_DATA, self.tr('Load sample data'), True))
		
	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		dbfilename = self.parameterAsFileOutput(parameters,	self.DB_FILENAME,	context)
		crs = self.parameterAsCrs(parameters,self.CRS,context)
		loadsamplePars = self.parameterAsBoolean(parameters,self.LOAD_SAMPLE_PAR,context)
		loadsampleData = self.parameterAsBoolean(parameters, self.LOAD_SAMPLE_DATA, context)

		self.FEEDBACK.setProgress(25.0)
		self.DBM = SQLiteDriver(dbfilename, True, crs,self.FEEDBACK,self.tr)

		self.plugin_dir = os.path.join(os.path.dirname(__file__), os.pardir)

		# TODO: divide load sample and load geodata
		if loadsamplePars:
			self.FEEDBACK.pushInfo(self.tr('Loading sample parameters ...'))

			#print('loading data')
			self.loadDemoData(loadsampleData)

		self.FEEDBACK.setProgress(100.0)
		return {self.DB_FILENAME:dbfilename}


	def loadDemoData(self, fGeodata=True):
		# load crop types
		self.FEEDBACK.setProgress(10.0)
		self.FEEDBACK.pushInfo(self.tr('Import crop types'))
		path2crop = os.path.join(self.plugin_dir, 'sample', 'crop')
		fileList = os.listdir(path2crop)
		for f in fileList:
			cropDict = parseParFile(filename=os.path.join(path2crop, f), parSep='=', colSep=' ', feedback=self.FEEDBACK, tr=self.tr)
			cropValues = list(cropDict.values())
			cropValues += [''] # add option pars
			sql = "INSERT INTO idr_crop_types VALUES (null,'%s');" % ("','".join(cropValues))
			msg = self.DBM.executeSQL(sql)

		# load irrigation methods
		self.FEEDBACK.setProgress(20.0)
		self.FEEDBACK.pushInfo(self.tr('Import irrigation methods'))
		path2irrmethod = os.path.join(self.plugin_dir, 'sample', 'irr_method')
		fileList = os.listdir(path2irrmethod)
		for f in fileList:
			irrDict = parseParFile(filename=os.path.join(path2irrmethod, f), parSep='=', colSep=' ', feedback=self.FEEDBACK,
								   tr=self.tr)
			irrValues = list(irrDict.values())
			irrValues += ['']  # add option pars
			sql = "INSERT INTO idr_irrmet_types VALUES (null,'%s');" % ("','".join(irrValues))
			msg = self.DBM.executeSQL(sql)

		# load soil types
		self.FEEDBACK.setProgress(30.0)
		self.FEEDBACK.pushInfo(self.tr('Import soil types'))
		path2soil = os.path.join(self.plugin_dir, 'sample', 'soil')
		self.importTableFromCSV(filename=os.path.join(path2soil, 'soiltypes.csv'),tablename='idr_soil_types',
								fieldList=['id','name','descr'],
								skip=1, column_sep=';')

		# load soil profiles
		self.FEEDBACK.setProgress(40.0)
		self.FEEDBACK.pushInfo(self.tr('Import soil profiles'))
		self.importTableFromCSV(filename=os.path.join(path2soil, 'soilprofiles.csv'), tablename='idr_soil_profiles',
								fieldList=['soilid','maxdepth','ksat','theta_fc','theta_wp','theta_r','theta_sat','txtr_code'],
								skip=1, column_sep=';')

		# load soil uses
		self.FEEDBACK.setProgress(50.0)
		self.FEEDBACK.pushInfo(self.tr('Import soil uses'))
		path2soiluse = os.path.join(self.plugin_dir, 'sample', 'soiluse')
		fileList = os.listdir(path2soiluse)
		for f in fileList:
			soiluseDict = parseParFile(filename=os.path.join(path2soiluse, f), parSep='=', colSep=' ', feedback=self.FEEDBACK, tr=self.tr)
			soiluseValues = list(soiluseDict.values())
			sql = "INSERT INTO idr_soiluses VALUES (null,'%s');" % ("','".join(soiluseValues))
			msg = self.DBM.executeSQL(sql)

		if (fGeodata == True):
			# load geometries
			self.FEEDBACK.pushInfo(self.tr('Loading sample data ...'))
			self.FEEDBACK.setProgress(60.0)
			path2geodata = os.path.join(self.plugin_dir, 'sample', 'geodata')
			# TODO: next release, 'idr_gw_wells'
			listOfFile = ['idr_weather_stations', 'idr_nodes', 'idr_links','idr_soilmap','idr_usemap',
						  'idr_irrmap','idr_distrmap','idr_control_points','idr_domainmap']
			for f in listOfFile:
				# load crop field
				gpkg_layer = self.DBM.DBName + '|layername=' + f
				#print('in loadDemoData', gpkg_layer)

				self.FEEDBACK.pushInfo(self.tr('Import %s in %s') % (f, gpkg_layer))
				csvFile = os.path.join(path2geodata, f + '.csv')
				try:
					self.addFeaturesFromCSV(gpkg_layer, csvFile,self.FEEDBACK) # use embedded version to prevent(hopefully) memory leaks
				except Exception as e:
					self.FEEDBACK.reportError(self.tr('Error in addFeaturesFromCSV %s') % str(e),False)

			# load meteo data
			self.FEEDBACK.setProgress(70.0)
			self.FEEDBACK.pushInfo(self.tr('Import meteo data'))
			path2weather = os.path.join(self.plugin_dir, 'sample', 'weather')
			fileList = os.listdir(path2weather)
			varList = ['ws_tmax', 'ws_tmin', 'ws_ptot', 'ws_umax', 'ws_umin', 'ws_vmed', 'ws_rgcorr']
			for c, f in enumerate(fileList):
				for i, var in enumerate(varList):
					self.importDataFromCSV(filename=os.path.join(path2weather, f), tablename=var, timeFldIdx=0,
										   valueFldIdx=i + 1, sensorId=int(f[:-4]), skip=1, timeFormat='%Y/%m/%d',
										   column_sep=',', progress=self.FEEDBACK)

			# load discharge data
			self.FEEDBACK.setProgress(80.0)
			self.FEEDBACK.pushInfo(self.tr('Import discharge data'))
			path2disch = os.path.join(self.plugin_dir, 'sample', 'discharge')
			fileList = os.listdir(path2disch)
			varList = ['node_act_disc']
			for c, f in enumerate(fileList):
				for i, var in enumerate(varList):
					self.importDataFromCSV(filename=os.path.join(path2disch, f), tablename=var, timeFldIdx=0,
										   valueFldIdx=i + 1, sensorId=int(f[:-4]), skip=1, timeFormat='%d/%m/%Y',
										   column_sep=';', progress=self.FEEDBACK)
			self.FEEDBACK.setProgress(100.0)

	def importDataFromCSV(self, filename, tablename, timeFldIdx, valueFldIdx, sensorId, skip, timeFormat, column_sep,
						  progress, year=''):
		msg = ''
		progress.pushInfo(self.tr('INFO: loading %s' % filename))
		concatValues = []
		# oper CSV file
		with open(filename, "r") as in_file:
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
					timestamp = datetime.strptime(str(year) + data[timeFldIdx], timeFormat)
					value = float(data[valueFldIdx])

					concatValues.append("('" + timestamp.strftime('%Y-%m-%d') + "', '" + str(sensorId) + "', '" + str(value) + "')")

				i += 1

		#print('n. of imported record: %s' % len(concatValues))

		concatValues = ', '.join(concatValues)
		# create a temporary table to store uploaded data
		progress.pushInfo(self.tr('INFO: creating temporary table'))
		sql = 'DROP TABLE IF EXISTS dummy;'
		sql += 'CREATE TABLE dummy (timestamp2 text, wsid2 integer, recval2 double);'

		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.pushInfo(self.tr('SQL error: %s' % msg))
			progress.pushInfo(self.tr('at: %s' % sql))
		else:
			progress.pushInfo(self.tr('--> OK'))

		progress.setProgress(30)

		progress.pushInfo(self.tr('INFO: populating temporary table'))

		sql = 'BEGIN; '
		sql += 'REPLACE INTO dummy (timestamp2,wsid2,recval2) VALUES %s; ' % (concatValues)
		sql += 'COMMIT;'

		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.pushInfo(self.tr('SQL error: %s' % msg))
			progress.pushInfo(self.tr('at: %s' % sql))
		else:
			progress.pushInfo(self.tr('--> OK'))

		progress.setProgress(50)

		progress.pushInfo(self.tr('INFO: updating existing values in %s' % tablename))
		# update value if they already exist
		sql = 'UPDATE %s SET recval = (SELECT d.recval2 FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid)	WHERE EXISTS (SELECT * FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid);' % (
			tablename)
		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.pushInfo(self.tr('SQL error: %s' % msg))
			progress.pushInfo(self.tr('at: %s' % sql))
		else:
			progress.pushInfo(self.tr('--> OK'))

		progress.setProgress(75)

		# copy value to tablename id they aren't
		progress.pushInfo(self.tr('INFO: appending new values in %s' % tablename))
		sql = 'INSERT INTO %s (timestamp,wsid,recval) SELECT timestamp2,wsid2,recval2 FROM dummy d WHERE NOT EXISTS (SELECT * FROM %s WHERE timestamp = d.timestamp2 AND wsid = d.wsid2);' % (
			tablename, tablename)
		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.pushInfo(self.tr('SQL error: %s' % msg))
			progress.pushInfo(self.tr('at: %s' % sql))
		else:
			progress.pushInfo(self.tr('--> OK'))

		progress.setProgress(80)

		progress.pushInfo(self.tr('INFO: removing temporary table'))
		sql = 'DROP TABLE IF EXISTS dummy;'
		msg = self.DBM.executeSQL(sql)
		if msg != '':
			progress.pushInfo(self.tr('SQL error: %s' % msg))
			progress.pushInfo(self.tr('at: %s' % sql))
		else:
			progress.pushInfo(self.tr('--> OK'))

		progress.setProgress(90)

		if msg == '':
			progress.pushInfo(
				self.tr('Importation finished! Variable %s updated for station %s' % (tablename, sensorId)))
		else:
			self.FEEDBACK.reportError(self.tr('Error: unable to import data'), False)

		progress.setProgress(100)

	def importTableFromCSV(self,filename, tablename, fieldList,skip=1, column_sep=';'):
		concatValues = []

		# open CSV file
		with open(filename, "r") as in_file:
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

	def addFeaturesFromCSV(self,laySource, csvSource, feedback=None):
		# if feedback: feedback.pushInfo('in addFeaturesFromCSV, processing: %s'%laySource)
		# print('in addFeaturesFromCSV, processing: %s'%laySource)

		self.vlayer = QgsVectorLayer(laySource, 'dummy', "ogr")
		self.vlayer.startEditing()
		pr = self.vlayer.dataProvider()
		field_names = [field.name() for field in pr.fields()]
		dataDict = parseParFile(filename=csvSource, parSep='=', colSep=';', feedback=feedback, tr=None)

		dataDict = dataDict['table']
		nOfRec = len(dataDict['geometry'])

		for i in range(nOfRec):
			feat = QgsFeature()
			feat.setGeometry(QgsGeometry.fromWkt(dataDict['geometry'][i]))
			feat.setFields(pr.fields())
			for k in list(dataDict.keys()):
				if k in field_names:
					idx = field_names.index(k)
					# ~ print('%s --> %s'%(k,idx))
					# ~ print('value: %s'%dataDict[k][i])
					feat.setAttribute(idx, dataDict[k][i])

			f = pr.addFeatures([feat])
			if not f:
				# print('in addFeaturesFromCSV, error adding feature %s'%i)
				pass

		self.vlayer.commitChanges()



