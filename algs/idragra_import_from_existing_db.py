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

import sqlite3
from math import tan, radians

import qgis
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant
from osgeo import gdal
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
					   NULL, QgsFeature, edit, QgsRaster, QgsGeometry, QgsRasterBlockFeedback, QgsRasterPipe,
					   QgsRasterProjector)
						
import processing

from numpy import array

from datetime import datetime

import os

#from tools.add_features_from_csv import addFeaturesFromCSV
from tools.parse_par_file import parseParFile
from tools.sqlite_driver import SQLiteDriver


class IdragraImportFromExistingDB(QgsProcessingAlgorithm):
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
	
	SOURCE_DB= 'SOURCE_DB'
	DEST_DB = 'DEST_DB'
	ASSETS = 'ASSETS'
	RASTER_FLAG = 'RASTER_FLAG'
	FEEDBACK = None
	DBM = None

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraImportFromExistingDB()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraImportFromExistingDB'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('From existing database')

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
						The algorithm import the dataset from existing gpkg file.
						Only common parameters with the newest version are imported. 
						<b>Parameters:</b>
						Source DB: the file path to the source database [SOURCE_DB]
						Assets: elements to be imported [ASSETS]
						Import raster: import also elevation and watertable rasters if exist [RASTER_FLAG]
						Destination DB: the file path to the destination database [DEST_DB]
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
		self.ASSETSDICT = qgis.utils.plugins['IdragraTools'].LYRNAME
		#self.ASSETSDICT['elevation'] =self.tr('Elevation')
		#self.ASSETSDICT['watertable'] = self.tr('Water table')

		self.addParameter(QgsProcessingParameterFile(self.SOURCE_DB, self.tr('Source DB'),
													 QgsProcessingParameterFile.Behavior.File, '*.*', '', False,
													 self.tr('Geopackage (*.gpkg);;All files (*.*)')))

		self.addParameter(QgsProcessingParameterEnum(self.ASSETS, self.tr('Assets'),
													 list(self.ASSETSDICT.values()),True))

		self.addParameter(QgsProcessingParameterBoolean(self.RASTER_FLAG, self.tr('Import rasters'),
													 False, False))

		self.addParameter(QgsProcessingParameterFile(self.DEST_DB, self.tr('Destination DB'),
													 QgsProcessingParameterFile.Behavior.File, '*.*', '', False,
													 self.tr('Geopackage (*.gpkg);;All files (*.*)')))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		sourceFn = self.parameterAsFile(parameters,	self.SOURCE_DB,	context)
		assetsIds = self.parameterAsEnums(parameters, self.ASSETS, context)
		assetsTables = [list(self.ASSETSDICT.keys())[i] for i in assetsIds]
		self.FEEDBACK.pushInfo(self.tr('Table to be processed %s' % str(assetsTables)))
		rasterFlag = self.parameterAsBoolean(parameters,self.RASTER_FLAG,context)
		destFn = self.parameterAsFile(parameters, self.DEST_DB, context)

		# open db connection
		self.SOURCE_DBM = SQLiteDriver(sourceFn, False, None, self.FEEDBACK, self.tr, QgsProject.instance())
		self.DEST_DBM = SQLiteDriver(destFn, False, None, self.FEEDBACK, self.tr, QgsProject.instance())

		# template for the insert command
		#sql = 'BEGIN; '
		#sql += 'SELECT load_extension("mod_spatialite");'

		#sql += 'COMMIT;'

		# loop in seletec assets tables
		numImportedTables = 0
		elevRasterDict = {}
		wtRasterDict = {}
		for tName in assetsTables:
			self.FEEDBACK.pushInfo(self.tr('Processing table %s' % tName))
			sql = 'INSERT INTO %s (%s) VALUES (%s);'
			numImportedTables+=1
			# get table structure (fields) from dest dbm
			# and prepare sql command
			# get table structure from source db
			destFieldList = self.DEST_DBM.getFieldsList(tName)
			if 'fid' in destFieldList: destFieldList.remove('fid')
			destFieldListStr = ', '.join(destFieldList)
			#if (tName=='idr_soilmap'): self.FEEDBACK.pushInfo(self.tr('Destination fields: %s' % destFieldList))
			destValListStr = ','.join(['?']*len(destFieldList))
			#if (tName=='idr_soilmap'): self.FEEDBACK.pushInfo(self.tr('Destination values: %s' % destValListStr))
			#if (tName=='idr_soilmap'): self.FEEDBACK.pushInfo(self.tr('Raw SQL: %s' % sql))
			sql = sql%(tName,destFieldListStr,destValListStr)
			#if (tName=='idr_soilmap'): self.FEEDBACK.pushInfo(self.tr('Formatted SQL: %s' % sql))

			# compare with source db table
			sourceFieldList = self.SOURCE_DBM.getFieldsList(tName)
			#if (tName=='idr_soilmap'): self.FEEDBACK.pushInfo(self.tr('Source fields: %s' % str(sourceFieldList)))

			# make a map between destination and source table
			sourceFieldIdx = [None] * len(sourceFieldList)
			for i, fieldName in enumerate(sourceFieldList):
				if (fieldName in destFieldList):
					sourceFieldIdx[i]= destFieldList.index(fieldName)

			#if (tName=='idr_soilmap'): self.FEEDBACK.pushInfo(self.tr('Source/Destination fields index: %s' % str(sourceFieldIdx)))

			# loop in table rows and populate sql command
			rows = self.SOURCE_DBM.getDataFromTable(tName)
			newDataRows = []
			if rows:
				numRows = len(rows)
				for r,row in enumerate(rows):
					self.FEEDBACK.setProgress(100.0*r/numRows)
					newDataList = ['']*len(destFieldList)
					for i,val in enumerate(row):
						if (sourceFieldIdx[i] is not None):
							if destFieldList[sourceFieldIdx[i]] == 'geom':
								newDataList[sourceFieldIdx[i]] = sqlite3.Binary(val)
							elif destFieldList[sourceFieldIdx[i]] == 'fid':
								newDataList[sourceFieldIdx[i]] = NULL
							else:
								newDataList[sourceFieldIdx[i]]=val

					#if (tName=='idr_soilmap'): self.FEEDBACK.pushInfo(self.tr('Add row: %s' % str(newDataList)))

					newDataRows.append(tuple(newDataList))


			#self.FEEDBACK.pushInfo(self.tr('Data to be imported: %s' % str(newDataRows)))

			msg = self.DEST_DBM.executeSQL(sql,newDataRows)

			if msg != '':
				self.FEEDBACK.reportError(self.tr('SQL error: %s') % msg, False)
				self.FEEDBACK.reportError(self.tr('at: %s') % sql, False)

		# save and close db connection
		sql = 'VACUUM;'
		msg = self.DEST_DBM.executeSQL(sql)
		if msg != '':
			self.FEEDBACK.reportError(self.tr('SQL error: %s') % msg, False)
			self.FEEDBACK.reportError(self.tr('at: %s') % sql, False)

		self.DEST_DBM = None
		self.SOURCE_DBM = None

		# import raster
		if rasterFlag:
			# search for all raster in source db
			gdal.UseExceptions()
			try:
				gpkg = gdal.Open(sourceFn)
			except Exception as e:
				self.FEEDBACK.reportError(self.tr('Unable to read database for raster layers (Complete error: %s)') % str(e), True)
			if gpkg:
				if gpkg.GetSubDatasets():
					for raster in gpkg.GetSubDatasets():
						rasterSrc = raster[0]
						rasterName = raster[1].split(' - ')[0]

						if rasterName.startswith('elevation'):
							# copy raster
							newRasterSource = self.copyRaster(rasterSrc, rasterName, destFn)
							if newRasterSource:
								elevRasterDict[rasterName] = newRasterSource
						elif rasterName.startswith('watertable'):
							# copy raster
							newRasterSource = self.copyRaster(rasterSrc, rasterName, destFn)
							if newRasterSource:
								wtRasterDict[rasterName] = newRasterSource
						else:
							self.FEEDBACK.reportError(self.tr('Unrecognized raster layer: %s') % rasterName, False)

		return {'NUMIMPORTEDTABLES':numImportedTables,'ELEVATION':elevRasterDict,'WATERTABLE':wtRasterDict}

	def copyRaster(self,rasterFileName, tableName,destGpkgFile):
		source = QgsRasterLayer(rasterFileName, tableName, 'gdal')
		rasterFilePath = None
		rfeedback = QgsRasterBlockFeedback()
		if source.isValid():
			provider = source.dataProvider()
			fw = QgsRasterFileWriter(destGpkgFile)
			fw.setOutputFormat('gpkg')
			fw.setCreateOptions(["RASTER_TABLE=" + str(tableName), 'APPEND_SUBDATASET=YES'])

			pipe = QgsRasterPipe()

			if pipe.set(provider.clone()) is True:
				projector = QgsRasterProjector()
				projector.setCrs(provider.crs(), provider.crs())
				if pipe.insert(2, projector) is True:
					# print('provider',provider.xSize(),provider.ySize(),provider.extent(),provider.crs())
					error = fw.writeRaster(pipe, provider.xSize(), provider.ySize(), provider.extent(),
										   provider.crs(), rfeedback)
					if error > 0:
						self.FEEDBACK.reportError(self.tr('Unable to copy the raster (%s)') % str(rfeedback.errors()), False)

					else:
						# gpkgFile = relpath(gpkgFile, QgsProject.instance().absolutePath())
						gpkgFile = os.path.basename(destGpkgFile)
						# rasterFilePath = 'GPKG:' + gpkgFile + ':' + tableName
						rasterFilePath = os.path.join('.', gpkgFile) + ':' + tableName

		return rasterFilePath.replace('\\', '/')

