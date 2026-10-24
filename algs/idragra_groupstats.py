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

from numpy import array

from datetime import datetime,timedelta

import os

from algs.date_time_widget import DateTimeWidget
from ..tools.utils import isLeap


class IdragraGroupStats(QgsProcessingAlgorithm):
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
	MERGE = 'MERGE'
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
		return IdragraGroupStats()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraGroupStats'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Make statistics by group')

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
						Aggregation map: the vector layer that define aggregation areas [AGGR_LAY]
						Merge: merge shapes by field value [MERGE]
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

		self.addParameter(QgsProcessingParameterBoolean(self.MERGE, self.tr('Merge'),
														True, True))

		self.addParameter(QgsProcessingParameterField(self.AGGRFLD, self.tr('Aggregation field'), 'fid', self.AGGRLAY,
													  QgsProcessingParameterField.Any))

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

		merge = self.parameterAsBoolean(parameters, self.MERGE, context)

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
		fldList.append(QgsField('count', QVariant.Double))

		# get output file
		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.OUTPUTTABLE,
			context,
			fldList,
			aggrLay.wkbType(),
			aggrLay.sourceCrs()
		)

		if merge:
			dissolvedFile = QgsProcessingUtils.generateTempFilename('dissolved.gpkg')
			# dissolve element by selected field
			res = processing.run("native:dissolve", {'INPUT': aggrLay.source(),
													'FIELD': [aggrFld],
													 'OUTPUT': dissolvedFile},
								 context=None,
								 feedback=None,
								 is_child_algorithm=True)
		else:
			dissolvedFile = aggrLay.source()

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


		# get the list of the output for the selected variable

		fileFilter = '*'+varToUse[4:]+'.asc'
		rootSimPath = os.path.dirname(idragraFile)
		pathToImport = os.path.join(rootSimPath,outputPath)[:-1] # because ends with //
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
				# apply zonal statistics
				#'TEMPORARY_OUTPUT'
				tempFile = QgsProcessingUtils.generateTempFilename('aggrOutput.gpkg')
				res = processing.run("native:zonalstatisticsfb", {'INPUT': dissolvedFile,
															'INPUT_RASTER': f,
															'RASTER_BAND': 1, 'COLUMN_PREFIX': '_',
															'STATISTICS': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
															'OUTPUT': tempFile},
									   context=None,
									   feedback=None,
									   is_child_algorithm=True)

				# append results
				statLay = QgsVectorLayer(res['OUTPUT'],'temp','ogr')
				for k in statLay.getFeatures():
					feat = QgsFeature(fldList)
					feat.setGeometry(k.geometry())
					feat['wsid'] = k[aggrFld]
					feat['recval'] = k[aggrFun]
					feat['count'] = k['_count']
					feat['timestamp'] = parsedDate

					sink.addFeature(feat, QgsFeatureSink.FastInsert)

			i+=1.
			self.FEEDBACK.setProgress(100.0*i/nOfFiles)

		return {'OUTPUT_TABLE':dest_id}
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