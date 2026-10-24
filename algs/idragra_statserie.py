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
from qgis._analysis import QgsZonalStatistics
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

import numpy as np

from datetime import datetime, timedelta

import os

from algs.date_time_widget import DateTimeWidget
from tools.gis_grid import GisGrid
from ..tools.utils import isLeap


class IdragraStatserie(QgsProcessingAlgorithm):
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
	AGGRLAY = 'AGGR_LAY'
	AGGRFLD = 'AGGR_FLD'
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
		return IdragraStatserie()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraStatserie'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Make time serie from statistics')

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
						The algorithm create a time serie of selected statistic function of the selected variable. 
						<b>Parameters:</b>
						IdrAgra file: the parameters file used for the IdrAgra simulation (*.txt) [IDRAGRA_FILE]
						Aggregation map: the vector layer that define aggregation areas [AGGR_LAY]
						Aggregation field: the field that define aggregation groups [AGGR_FLD]
						Aggregation variable: the variable to be aggregated [AGGR_VAR]
						Aggregation function: the function to be used for aggregation [AGGR_FUN]
						Distribution function: the function to be used for daily distribution over the perod [DISTR_FUN]
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
		self.GROUPBY =  qgis.utils.plugins['IdragraTools'].GROUPBY

		self.AGGRFUNCTIONS = qgis.utils.plugins['IdragraTools'].AGGRFUNCTIONS

		self.TIMESTEP = qgis.utils.plugins['IdragraTools'].TIMESTEP

		#### PARAMETERS ####

		self.addParameter(QgsProcessingParameterFile(self.IDRAGRAFILE, self.tr('IdrAgra file'),
													  QgsProcessingParameterFile.Behavior.File,'*.*','',False,
													  'IdrAgra pars file (*.txt);;All files (*.*)'))
	
		self.addParameter(QgsProcessingParameterFeatureSource(self.AGGRLAY, self.tr('Aggregation map'),
															  [], None, True))

		self.addParameter(QgsProcessingParameterField(self.AGGRFLD, self.tr('Aggregation field'), 'fid', self.AGGRLAY,
													  QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterEnum(self.AGGRVAR, self.tr('Aggregation variable'),
													 list(self.STEPNAME.values())))

		self.addParameter(QgsProcessingParameterEnum(self.AGGRFUN, self.tr('Aggregation function'),
													 list(self.AGGRFUNCTIONS.values())))


		self.addParameter(QgsProcessingParameterFeatureSink (self.OUTPUTTABLE, self.tr('Select output file'),QgsProcessing.TypeVectorPolygon))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		idragraFile = self.parameterAsFile(parameters, self.IDRAGRAFILE, context)

		aggrLay = self.parameterAsVectorLayer(parameters, self.AGGRLAY, context)

		aggrFld = self.parameterAsFields(parameters, self.AGGRFLD, context)[0]

		varIdx = self.parameterAsEnum(parameters, self.AGGRVAR, context)
		varToUse = list(self.STEPNAME.keys())[varIdx]

		aggrFunIdx = self.parameterAsEnum(parameters, self.AGGRFUN, context)
		aggrFun = list(self.AGGRFUNCTIONS.keys())[aggrFunIdx]

		# TODO: explode over days in period

		fldList = QgsFields()
		fldList.append(QgsField('timestamp', QVariant.Date))
		fldList.append(QgsField('wsid', QVariant.String))
		fldList.append(QgsField('recval', QVariant.Double))

		# get output file
		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.OUTPUTTABLE,
			context,
			fldList
			)

		# loop in the idragra project file and get parameters

		monthlyFlag = True
		startDate = 1
		endDate = 366
		deltaDate = 366
		outputPath = ''

		try:
			f = open(idragraFile,'r')
			for l in f:
				l = l.replace(' ','') # remove inside blank characters
				l = l.rstrip('\r\n') # remove return carriage
				l = l.split('=')
				if len(l)==2:
					parName = l[0].lower()
					#print(parName)
					if parName== 'inputpath':
						inputPath = l[1]
					if parName == 'meteopath':
						meteoPath = l[1]
					elif parName== 'outputpath':
						outputPath = l[1]
					elif parName == 'monthlyflag':
						if l[1]=='F': monthlyFlag = False
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


		rootSimPath = os.path.dirname(idragraFile)
		# get cell size from domain map
		pathToImport = os.path.join(rootSimPath, inputPath)[:-1]
		pathToImport = os.path.join(pathToImport, 'domain.asc')

		domainGrd = GisGrid()
		domainGrd.openASC(pathToImport)
		cellSize = domainGrd.dx

		# get simulation time directly from meteodata
		pathToImport = os.path.join(rootSimPath, meteoPath)[:-1]  # because ends with //
		fileFilter = '*.dat'
		fileList = glob.glob(os.path.join(pathToImport, fileFilter))
		firstDay, endDay = self.getTimeLimits(filename=fileList[0])

		# call aggregation algorithm
		tempFile = QgsProcessingUtils.generateTempFilename('aggrOutput.gpkg')
		# algResults = processing.run("idragratools:IdragraGroupStats",
		# 						   {'IDRAGRA_FILE': idragraFile,
		# 							'AGGR_LAY': aggrLay, 'AGGR_FLD': aggrFld,
		# 							'AGGR_VAR': varIdx, 'AGGR_FUN': aggrFunIdx,
		# 							'OUTPUT_TABLE': tempFile},
		# 						   context=context,
		# 						   feedback=feedback,
		# 						   is_child_algorithm=True
		# 						   )

		algResults = processing.run("idragratools:IdragraGroupStatsByRaster",
					   {'IDRAGRA_FILE': idragraFile,
						'AGGR_LAY': 'irr_units', 'AGGR_VAR': varIdx, 'AGGR_FUN': aggrFunIdx,
						'OUTPUT_TABLE': tempFile},
					   context=context,
					   feedback=feedback,
					   is_child_algorithm=True
		)

		# get table and create time series
		table = QgsVectorLayer(tempFile,'temp','ogr')
		#print('features count:',table.featureCount()) #ok

		# get list of processed years
		firstYear = firstDay.year
		endYear = endDay.year
		yearList = list(range(firstYear, endYear + 1))
		#print('n. of year',len(yearList))

		# get the list of unique id
		attrIndex = table.fields().indexFromName('wsid')
		idList = table.uniqueValues(attrIndex)

		daysArray = np.array([])
		valuesArray = np.array([])
		idArray = np.array([])

		if monthlyFlag: startDate = None

		for i in idList:
			a,b = self.dayValueArray(table, i, yearList, startDate,0.0,cellSize)
			if len(daysArray)>0: daysArray = np.concatenate((daysArray, a))
			else: daysArray = a

			if len(valuesArray)>0: valuesArray = np.concatenate((valuesArray, b))
			else: valuesArray = b

			c = np.repeat(i, len(a))
			if len(idArray)>0: idArray = np.concatenate((idArray, c))
			else: idArray = c

		# save values to table
		nOfRec = len(daysArray)
		i=0.
		for k in np.stack((idArray, daysArray, valuesArray), axis=1):
			feat = QgsFeature(fldList)
			feat['wsid'] = k[0]
			feat['timestamp'] = k[1].strftime('%Y-%m-%d')
			feat['recval'] = k[2]

			sink.addFeature(feat, QgsFeatureSink.FastInsert)

			i+=1.
			self.FEEDBACK.setProgress(100.0*i/nOfRec)

		return {'OUTPUT_TABLE':dest_id}

	def stepToDate(self, year, step, periodStart, periodDelta):
		# calculate the day of the year for the selected periodù
		selDate = datetime(year, 1, 1)+timedelta(periodStart+step*periodDelta)
		return selDate.strftime('%Y-%m-%d')

	def monthToDate(self, year, month):
		if month == 12:
			month = 1
			year +=1
		else: month+=1

		selDate = datetime(year, month, 1)-timedelta(1)
		return selDate.strftime('%Y-%m-%d')

	def getTimeLimits(self, filename):
		lineToParse = ''
		with open(filename) as fp:
			for i, line in enumerate(fp):
				if i == 2:
					lineToParse = line[:-1] # remove return carriage symbol
					break

		toks = lineToParse.split(' -> ')
		firstDay = None
		endDay = None
		if len(toks)==2:
			firstDay = datetime.strptime(toks[0],'%d/%m/%Y')
			endDay = datetime.strptime(toks[1], '%d/%m/%Y')

		return firstDay, endDay

	def arrayOfDays(self,startDate, endDate):
		return np.arange(startDate, endDate+timedelta(days=1), timedelta(days=1)).astype(datetime)

	def dayValueArray(self,table,sensorId, yearList, startDay, nodata = -999,cellSize = 250.):
		# create an empty time series
		firstDate = datetime(yearList[0],1,1)
		endDay = datetime(yearList[-1],12,31)
		datesArray = self.arrayOfDays(firstDate, endDay)
		valueArray = np.zeros(len(datesArray)) + nodata

		#print('date len:',len(datesArray))

		nOfYears = len(yearList)
		for c,y in enumerate(yearList):
			firstDayOfYear = datetime(y, 1, 1)-timedelta(days=1)
			if startDay:
				#firstDayOfYear += timedelta(days=(startDay - 1-1)) # -1 to consider the previous date and -1 because the first day of the year is 1
				firstDayOfYear += timedelta(days=(startDay - 1))  # -1 to consider the previous date
				print('startDay',startDay,'firstDayOfYear:', firstDayOfYear)
				# FIXED: IdrAgra gets exactly the DoY number and does not consider the date
				# so the 155 day is the Jun-13 in leap year and Jun-14 in the others
				# if ((not isLeap(y)) and (startDay >= 59)):
				# 	#print('not leap year',y)
				# 	firstDayOfYear -= timedelta(days=(1))

			dayList = [firstDayOfYear]
			valueList = [None]
			# dayList = []
			# valueList = []
			# select a subset
			query = QgsExpression('"wsid" = %s and "timestamp" like \'%s%s\'' % (sensorId, y, '%'))
			request = QgsFeatureRequest(query)
			request.setFlags(QgsFeatureRequest.NoGeometry)
			selection = table.getFeatures(request)
			#dummy = 0
			for s in selection:
				dayList.append(datetime(s['timestamp'].year(),s['timestamp'].month(),s['timestamp'].day()))
				valueList.append(s['recval'])#*s['count']*cellSize*cellSize/1000.) # in cubic meters
				#dummy+=1

			#print('test table request',dummy)
			#print('dayList',dayList)
			#print('valueList',valueList)

			valueList = [x for _, x in sorted(zip(dayList, valueList))]
			dayList = sorted(dayList)

			#print('dayList', dayList)
			#print('valueList', valueList)

			i = 1
			while i < len(dayList):
				nOfDay = (dayList[i] - dayList[i - 1]).days
				#print(i,valueList[i],dayList[i - 1], dayList[i], nOfDay)
				# test = np.logical_and(datesArray >= dayList[i - 1], datesArray < dayList[i])
				test = np.logical_and(datesArray > dayList[i - 1], datesArray <= dayList[i])
				if valueList[i]: # if it is a valid number
					valueArray[test] = valueList[i] / nOfDay

				i += 1

			self.FEEDBACK.setProgress(100.0 * c / nOfYears)

		return datesArray,valueArray