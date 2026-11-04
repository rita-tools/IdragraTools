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
from qgis.core import (QgsProcessing,
						QgsFeatureSink,
						QgsProcessingException,
						QgsProcessingAlgorithm,
						QgsProcessingParameterFeatureSource,
						QgsProcessingParameterFeatureSink,
						QgsProcessingParameterMultipleLayers,
						QgsProcessingParameterFileDestination,
						QgsProcessingParameterEnum,
						QgsProcessingParameterVectorLayer,
						QgsProcessingParameterString,
						QgsExpression,
						QgsFeatureRequest,
						QgsCoordinateReferenceSystem,
						QgsCoordinateTransform,
						QgsProcessingParameterFolderDestination,
						QgsWkbTypes,
						QgsFields,
						QgsField,
						QgsVectorFileWriter,
						QgsVectorLayer,
						QgsProject,
						NULL)
						
import processing

from numpy import array

from datetime import datetime

import os

from .date_time_widget import DateTimeWidget
from ..tools.export_meteodata import exportMeteodata


class IdragraExportMeteodata(QgsProcessingAlgorithm):
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
	
	VECTORLAY = 'VECTOR_LAYER'
	DESTFOLDER = 'DEST_FOLDER'
	STARTDATE = 'START_DATE'
	ENDDATE = 'END_DATE'
	
	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraExportMeteodata()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraExportMeteodata'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Meteo data')

	def group(self):
		"""
		Returns the name of the group this algorithm belongs to. This string
		should be localised.
		"""
		return self.tr('Export')

	def groupId(self):
		"""
		Returns the unique ID of the group this algorithm belongs to. This
		string should be fixed for the algorithm, and must not be localised.
		The group id should be unique within each provider. Group id should
		contain lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraExport'

	def shortHelpString(self):
		"""
		Returns a localised short helper string for the algorithm. This string
		should provide a basic description about what the algorithm does and the
		parameters and outputs associated with it..
		"""
		
		helpStr = """
						The algorithm export weather time series in the format suitable for Idragra model. 
						<b>Parameters:</b>
						Weather station: the map of the weather stations [VECTOR_LAY]<sup>1</sup>
						Export to: the path to the folder where exported data will be saved [DEST_FOLDER]<sup>2</sup>
						Export from date: the first day to be exported [START_DATE]
						Export to date: the last day to be exported [END_DATE]
						
						<b>Notes:</b>
						[1] weather station layer and timeseries data structure is defined by IdrAgra Tools plugin
						[2] the algorithm will create all the necessary file and subfolder in the selected path
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
		self.addParameter(QgsProcessingParameterFeatureSource(self.VECTORLAY, self.tr('Weather station'),
															  [QgsProcessing.TypeVectorPoint]))
				
		self.addParameter(	QgsProcessingParameterFolderDestination(self.DESTFOLDER, self.tr('Export to')))
		
		
		paramStart = QgsProcessingParameterString(self.STARTDATE, self.tr('Export from date'),'', False, True)
		paramStart.setMetadata({'widget_wrapper': {'class': DateTimeWidget}})
		self.addParameter(paramStart)
		
		paramEnd = QgsProcessingParameterString(self.ENDDATE, self.tr('Export to date'),'', False, True)
		paramEnd.setMetadata({'widget_wrapper': {'class': DateTimeWidget}})
		self.addParameter(paramEnd)


	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		
		vectorLay = self.parameterAsSource(parameters, self.VECTORLAY, context)
				
		destFolder = self.parameterAsFile(parameters, self.DESTFOLDER, context)
		
		startDateStr = self.parameterAsString(parameters,self.STARTDATE,context)
		endDateStr = self.parameterAsString(parameters,self.ENDDATE,context)
		
		# check date sequence
		startDate = datetime.strptime(startDateStr, '%Y-%m-%d')
		endDate = datetime.strptime(endDateStr, '%Y-%m-%d')
		
		nOfWS = -1
		 
		if startDate > endDate:
			feedback.reportError(self.tr('Start date is greater than end date. Please invert time limits'),True)
			return {'NUMOFEXPORTEDSTATIONS': nOfWS}
		
		# make output dir
		datFolder = os.path.join(destFolder,'meteo_data')
		if not os.path.exists(datFolder):
			os.makedirs(datFolder)
		else:
			feedback.pushInfo(self.tr('"meteo_data" folder already exists. Output files will be overwritten.'))
		
		c = 0
		nFeat = vectorLay.featureCount()
		layName = vectorLay.sourceName()
		layers = QgsProject.instance().mapLayersByName(layName)
		dbName = ''
		for l in layers:
			test = l.source().split('|')[0]
			crsCode = l.sourceCrs().postgisSrid()
			if test.endswith('.gpkg'):
				dbName = test
				break
				
		
		if dbName == '':
			feedback.reportError(self.tr('Unable to find database'),True)
			return {'NUMOFEXPORTEDSTATIONS': nOfWS}
		
		
		feedback.pushInfo(self.tr('Working with db %s')%dbName)
		nOfWS = 0
		# loop in selected feature
		wsData = ''
		for feature in vectorLay.getFeatures():
			sName = feature['name']
			sId = feature['fid']
			sLat = feature['lat']
			sAlt = feature['alt']
			sx = feature.geometry().asMultiPoint()[0].x()
			sy = feature.geometry().asMultiPoint()[0].y()
			feedback.pushInfo(self.tr('Exporting station %s [%s]')%(sName,sId))
			exportMeteodata(filename=os.path.join(datFolder,sName+'.dat'), dbname = dbName,
									sensorId=sId, sensorName=sName, sensorLat=sLat, sensorAlt=sAlt,
									fromTime =  startDateStr, toTime=endDateStr,
									feedback=feedback,tr=self.tr)
			
			nOfWS+=1
			wsData+='%s   %s   %s\n'%(str(sId)+'.dat',sx,sy)
			feedback.setProgress(100*c/nFeat)
		# save list of weather stations
				
		wsText = """################ Meterological station input file  #################
#                                                                                                                      #
#                           Note: lines starting with <#> are comments                           #
#                                                                                                                      #
#####################################################

# Number of weather stations:		
StatNum = %s	
# Weather stations table:
Table =
sar.dat x%s            y%s
%s"""
	
		wsText = wsText%(nOfWS,crsCode,crsCode,wsData)

		filename = os.path.join(destFolder, 'weather_stations.dat')
		
		try:
			f = open(os.path.join(destFolder,'weather_stations.dat'),'w',encoding='utf-8')
			f.write(wsText)
		except IOError:
			feedback.reportError(self.tr('Cannot save to %s because %s')%(filename,str(IOError)),True)
		finally:
			f.close()
		
		return {'NUMOFEXPORTEDSTATIONS': nOfWS}
		
		#https://www.faunalia.eu/fr/blog/2019-07-02-custom-processing-widget
		