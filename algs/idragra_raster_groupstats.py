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

import glob
from math import tan, radians

import qgis
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication, QVariant, QDate
from qgis.analysis import QgsZonalStatistics
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
					   NULL, QgsFeature, edit, QgsRaster, QgsProcessingUtils)
						
import processing
import calendar

from numpy import array

from datetime import datetime,timedelta

import os

from algs.date_time_widget import DateTimeWidget
from ..tools.gis_grid import GisGrid
from ..tools.utils import isLeap
import numpy as np
import pandas as pd


class IdragraRasterGroupStats(QgsProcessingAlgorithm):
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
	
	IDRAGRAFILE= 'IDRAGRA_FILE'
	AGGRMAP = 'AGGR_MAP'
	AGGRVAR = 'AGGR_VAR'
	AGGRFUN = 'AGGR_FUN'
	OUTPUTTABLE = 'OUTPUT_TABLE'
	FEEDBACK = None

	def __init__(self):
		super().__init__()


	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraRasterGroupStats()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraRasterGroupStats'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Make statistics by raster map')

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
						The algorithm calculate the selected statistic function of the selected variable. 
						<b>Parameters:</b>
						IdrAgra file: the parameters file used for the IdrAgra simulation (*.txt) [IDRAGRA_FILE]
						Aggregation map: the variable that define aggregation areas [AGGR_MAP]
						Aggregation variable: the variable to be aggregated [AGGR_VAR]
						Aggregation function: the function to be used for aggregation [AGGR_FUN]
						Output table: the resultant table [OUTPUT_TABLE]
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
		self.STEPNAME = qgis.utils.plugins['IdragraTools'].STEPNAME

		self.GROUPBYRASTER =  qgis.utils.plugins['IdragraTools'].GROUPBYRASTER
		self.AGGRFUNCTIONS = qgis.utils.plugins['IdragraTools'].AGGRFUNCTIONS

		self.TIMESTEP = qgis.utils.plugins['IdragraTools'].TIMESTEP

		#### PARAMETERS ####

		self.addParameter(QgsProcessingParameterFile(self.IDRAGRAFILE, self.tr('IdrAgra file'),
													  QgsProcessingParameterFile.Behavior.File,'*.*','',False,
													  'IdrAgra pars file (*.txt);;All files (*.*)'))
	
		self.addParameter(QgsProcessingParameterEnum(self.AGGRMAP, self.tr('Aggregation map'),
													 list(self.GROUPBYRASTER.values())))

		self.addParameter(QgsProcessingParameterEnum(self.AGGRVAR, self.tr('Aggregation variable'),
													 list(self.STEPNAME.values())))


		self.addParameter(QgsProcessingParameterFileDestination (self.OUTPUTTABLE, self.tr('Select output file'),
																 'Comma Separated File (*.csv);;All files (*.*)',
																 '*.csv', True, False))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		idragraFile = self.parameterAsFile(parameters, self.IDRAGRAFILE, context)

		aggrIdx = self.parameterAsEnum(parameters, self.AGGRMAP, context)
		aggrMap = list(self.GROUPBYRASTER.keys())[aggrIdx]

		varIdx = self.parameterAsEnum(parameters, self.AGGRVAR, context)
		varToUse = list(self.STEPNAME.keys())[varIdx]

		outFile = self.parameterAsFileOutput(parameters, self.OUTPUTTABLE, context)


		# loop in the idragra project file

		# ... get path to geodata folder InputPath
		# ... get path to results folder OutputPath
		# ... get output settings MonthlyFlag, StartDate, EndDate, DeltaDate
		monthlyFlag = True
		startDate = 1
		endDate = 366
		deltaDate = 366

		try:
			f = open(idragraFile,'r')
			for l in f:
				l = l.replace(' ','')
				l = l.rstrip('\n')  # remove return carriage
				l = l.split('=')
				if len(l)==2:
					parName = l[0].lower()
					#print(parName)
					if parName== 'inputpath':
						inputPath = l[1]
					elif parName== 'outputpath':
						outputPath = l[1]
					elif parName == 'monthlyflag':
						if l[1]=='F':
							monthlyFlag = False
					elif parName == 'startdate':
						startDate = int(l[1])
					elif parName == 'enddate':
						endDate = int(l[1])
					elif parName == 'deltadate':
						deltaDate = int(l[1])
					else:
						pass
		except Exception as e:
			self.FEEDBACK.reportError(self.tr('Cannot parse %s because %s') %
									  (idragraFile, str(e)),True)

		# set path
		rootSimPath = os.path.dirname(idragraFile)
		pathToImport = os.path.join(rootSimPath, outputPath)[:-1]  # because ends with //
		pathToGeoData = os.path.join(rootSimPath, inputPath)[:-1]  # because ends with //

		res = {'timestamp': []}

		fileFilter = aggrMap+'*.asc'
		path2find = os.path.join(pathToGeoData, fileFilter)

		refMapFileList = glob.glob(path2find)

		# open reference map
		for refMapFileName in refMapFileList:
			#refMapFileName = os.path.join(pathToGeoData, aggrMap+'.asc')
			refMap = GisGrid()
			refMap.openASC(refMapFileName)
			#print('shape refMap',refMap.data.shape)

			# get unique values
			uniqueIds = refMap.getUniqueValues()

			# make storage variable
			# TODO: check multiple years
			for uId in uniqueIds:
				if uId not in list(res.keys()):
					res[int(uId)]= [0.]*len(res['timestamp'])

			# get the list of the output for the selected variable

			fileFilter = '*'+varToUse[4:]+'.asc'
			#print('pathToImport',pathToImport)
			fileList = glob.glob(os.path.join(pathToImport, fileFilter))
			#print('fileList',fileList)
			nOfFiles = len(fileList)
			i = 0.
			for f in fileList:
				# parse file name
				fname = os.path.basename(f)
				# extract date time
				parsedDate = None
				if monthlyFlag:
					# 2000_month1_caprise
					try:
						y = int(fname[0:4])
						tokStart = fname.index('_month')+len('_month')
						tokEnd = fname.index('_', tokStart)
						s = int(fname[tokStart:tokEnd])
						parsedDate = self.monthToDate(year=y, month = s)
					except:
						pass
				else:
					# 2000_step1_caprise.asc
					if '_step' in fname:
						#self.FEEDBACK.pushInfo(self.tr('last file %s') % fname)
						y = int(fname[0:4])
						tokStart = fname.index('_step')+len('_step')
						tokEnd = fname.index('_',tokStart)
						s = int(fname[tokStart:tokEnd])
						# step to date
						parsedDate = self.stepToDate(year=y,step = s,periodStart =startDate, periodDelta = deltaDate)

				self.FEEDBACK.pushInfo(self.tr('Processing %s --> %s'%(f,parsedDate)))
				if parsedDate:
					res['timestamp'].append(parsedDate)
					# apply zonal statistics
					#'TEMPORARY_OUTPUT'
					varMap = GisGrid()
					varMap.openASC(f)
					varData = varMap.getMaskedData()
					#print('shape varMap', varData.data.shape)

					for uId in uniqueIds:
						#print('uId',uId)
						#selVarArray = varMap.data*refMap.data[refMap.data==uId]
						maskedArray = np.ma.masked_where((refMap.data != uId), varData)
						resVal = np.nanmean(maskedArray)
						#self.FEEDBACK.pushInfo(self.tr('Select value %s --> %s' % (str(uId), resVal)))
						res[int(uId)].append(resVal)

				i+=1.
				self.FEEDBACK.setProgress(100.0*i/nOfFiles)

		resDF = pd.DataFrame.from_dict(res)
		resDF.sort_values(by='timestamp',inplace=True)

		if '*' not in outFile:
			self.FEEDBACK.pushInfo(self.tr('Saving to %s' % (outFile)))
			resDF.to_csv(outFile, sep=',', na_rep='', header=True, index=False)

		return {'OUTPUT_TABLE':resDF}


	# TODO: step is calculate from the first day of the year or the irrigation period? --> from the outputs dates
	# TODO: check if it works correctly with leap year
	def stepToDate(self, year, step, periodStart, periodDelta):
		# calculate the day of the year for the selected period
		# added -2 to clear starting point
		# if ((not isLeap(year)) and (periodStart >= 59)):
		# 	#print('not leap year',y)
		#  	offset = -2 - 1
		# else:
		# 	offset = -1 - 1

		# offset = -2 - 1
		#if (isLeap(year)): offset = -1-1
		offset = -1 - 1 #FIXED: IdrAgra does not aware for leap year

		selDate = datetime(year, 1, 1)+timedelta(periodStart+step*periodDelta+offset)
		lastDate = datetime(year, 12, 31)
		#print('lastDate:',lastDate)
		if selDate>lastDate: selDate =lastDate #limit to selected period
		return selDate.strftime('%Y-%m-%d')

	def monthToDate(self, year, month):
		if month == 12:
			month = 1
			year +=1
		else: month+=1

		selDate = datetime(year, month, 1)-timedelta(1)
		return selDate.strftime('%Y-%m-%d')