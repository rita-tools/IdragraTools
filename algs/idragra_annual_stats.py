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
from ..tools.read_idragra_parameters import readIdragraParameters
from ..tools.gis_grid import GisGrid
from ..tools.utils import isLeap
import numpy as np
import pandas as pd


class IdragraAnnualStats(QgsProcessingAlgorithm):
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
	YEAR = 'YEAR'
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
		return IdragraAnnualStats()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraAnnualStats'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Make statistics by selected variables and year')

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
		self.ANNUALVARS = qgis.utils.plugins['IdragraTools'].ANNUALVARS

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
													 list(self.ANNUALVARS.values()),True,0,False))

		self.addParameter(QgsProcessingParameterNumber(self.YEAR, self.tr('Reference year ()'),
													   QgsProcessingParameterNumber.Integer))

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

		varIdxList = self.parameterAsEnums(parameters, self.AGGRVAR, context)

		year = self.parameterAsInt(parameters, self.YEAR, context)

		outFile = self.parameterAsFileOutput(parameters, self.OUTPUTTABLE, context)

		# loop in the idragra project file
		pars = readIdragraParameters(idragraFile, self.FEEDBACK, self.tr)

		# set path
		rootSimPath = os.path.dirname(idragraFile)
		pathToImport = os.path.join(rootSimPath, pars['outputpath'])[:-1]  # because ends with //
		pathToGeoData = os.path.join(rootSimPath, pars['inputpath'])[:-1]  # because ends with //

		# get the list of reference maps
		fileFilter = aggrMap + '*.asc'
		path2find = os.path.join(pathToGeoData, fileFilter)
		refMapFileList = glob.glob(path2find)
		refMapFile = ''

		if len(refMapFileList)==0:
			self.FEEDBACK.reportError(self.tr('Unable to find anyt reference map like %s') %
									  (path2find), True)

		if len(refMapFileList) == 1:
			refMapFile = refMapFileList[0]
		else:
			for f in refMapFileList:
				if year in f:
					refMapFile = f

		# open reference map
		refMap = GisGrid()
		refMap.openASC(refMapFile)
		#print('shape refMap', refMap.data.shape)

		# get unique values
		uniqueIds = list(refMap.getUniqueValues())
		sorted(uniqueIds)

		res = {'aggr.map.ids': [int(x) for x in uniqueIds]}

		nOfVars = len(varIdxList)

		for j,varIdx in enumerate(varIdxList):
			varToUse = list(self.ANNUALVARS.keys())[varIdx]
			# init column values
			res[varToUse] = [0.] * len(uniqueIds)

			# get the list of output for the selected variables
			filename = '%s_%s.asc'%(year,varToUse)
			path2find = os.path.join(pathToImport, filename)

			if not os.path.exists(path2find):
				self.FEEDBACK.reportError(self.tr('Cannot find %s') %
										  (path2find),False)
				# go to the next
				continue

			# apply zonal statistics
			varMap = GisGrid()
			varMap.openASC(path2find)
			#varData = varMap.getMaskedData()
			#print('shape varMap', varData.data.shape)

			for i,uId in enumerate(uniqueIds):
				#print('uId',uId)
				#selVarArray = varMap.data*refMap.data[refMap.data==uId]
				maskedArray = np.ma.masked_where(np.logical_or((refMap.data != uId),(varMap.data == varMap.nodata)), varMap.data)
				try:
					resVal = np.nanmean(maskedArray)
				except:
					resVal = np.nan

				if (resVal == varMap.nodata): resVal = np.nan
				#self.FEEDBACK.pushInfo(self.tr('Select value %s --> %s' % (str(uId), resVal)))
				res[varToUse][i] = resVal

		self.FEEDBACK.setProgress(100.0*j/nOfVars)

		resDF = pd.DataFrame.from_dict(res)
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