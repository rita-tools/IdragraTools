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

from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QCoreApplication,QVariant
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
					   NULL, QgsProcessingParameterFile)
						
from numpy import array

from datetime import datetime

import os

from .date_time_widget import DateTimeWidget
from ..tools.export_geodata_vector import ExportGeodataVector

class IdragraExportGeodata(QgsProcessingAlgorithm):
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
	
	DB_FILE = 'DB_FILE'
	DEST_FOLDER = 'DEST_FOLDER'
	START_DATE = 'START_DATE'
	END_DATE = 'END_DATE'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraExportGeodata()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraExportGeodata'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('From db to geodata')

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
						The algorithm export all the geographic data from the database to the idragra input folder (e.g. geodata). 
						<b>Parameters:</b>
						Database file: the geopackage file [DB_FILE]<sup>1</sup>
						Export from date: the first day to be exported [START_DATE]
						Export to date: the last day to be exported [END_DATE]
						Export to: the path to the folder where exported data will be saved [DEST_FOLDER]<sup>2</sup>
						
						<b>Notes:</b>
						[1] the geopackage must be structured as required by the IdrAgra Tools plugin
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
		self.addParameter(QgsProcessingParameterFile(self.DB_FILE, self.tr('Database file'),
													 QgsProcessingParameterFile.Behavior.File, '*.*', '', False,
													 self.tr('Geopackage (*.gpkg);;All files (*.*)')))

		self.addParameter(	QgsProcessingParameterFolderDestination(self.DEST_FOLDER, self.tr('Export to')))

		param_start = QgsProcessingParameterString(self.START_DATE, self.tr('Export from date'), '', False, True)
		param_start.setMetadata({'widget_wrapper': {'class': DateTimeWidget}})
		self.addParameter(param_start)

		param_end = QgsProcessingParameterString(self.END_DATE, self.tr('Export to date'), '', False, True)
		param_end.setMetadata({'widget_wrapper': {'class': DateTimeWidget}})
		self.addParameter(param_end)

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback

		# get params
		db_file = self.parameterAsFile(parameters, self.DB_FILE, context)
		dest_folder = self.parameterAsFile(parameters, self.DEST_FOLDER, context)

		start_date_str = self.parameterAsString(parameters, self.START_DATE, context)
		end_date_str = self.parameterAsString(parameters, self.END_DATE, context)

		# check date sequence
		start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
		end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

		start_yr = start_date.year
		end_yr = end_date.year
		# TODO: implement also the RASTER MODE
		vector_mode = True

		# set imulation settings
		sim_dic = {'DBFILE': db_file,
					   'LOAD_SAMPLE_PAR': False,
					   'LOAD_SAMPLE_DATA': False,
					   'OUTPUTPATH': dest_folder,
					   'OUTPUTFOLDER': 'simout',
					   'SPATIALFOLDER': 'geodata',
					   'METEOFOLDER': 'meteodata',
					   'PHENOFOLDER': 'pheno',
					   'IRRFOLDER': 'irrmethods',
					   'WATSOURFOLDER': 'wsources',
					   'WSFOLDER': 'meteodata',
					   'WSFILE': 'weather_stations.dat',
					   'CANOPYRESMOD': 1,
					   'CO2FILE': 'CO2_conc.dat',
					   'MODE': 0,
					   'CAPILLARYFLAG': 'F',
					   'NOFMETEO': '',
					   'NUMMETEOWEIGTH': 5,
					   'NOFSOILUSES': '',
					   'SOILUSESLIST': '',
					   'SOILUSEVARFLAG': 'T',
					   'RANDWIND': 6,
					   'STARTIRRSEASON': 1,
					   'ENDIRRSEASON': 366,
					   'NBASINS': 0,
					   'NSOURCE': 0,
					   'NSOURCEDER': 0,
					   'NSFLOWWELLS': 0,
					   'NTAILWAT': 0,
					   'NPUBWELL': 0,
					   'STARTYEAR': str(start_yr),
					   'ENDYEAR': str(end_yr),
					   'YEARS': [],
					   'PERIOD': '',
					   'ZEVALAY': 0.1,
					   'ZTRANSLAY': 0.9,
					   'LANDUSES': 'landuses',
					   'EXTENT': '',
					   'CRS': '',
					   'CELLSIZE': 250,
					   'WATERTABLEMAP': {},# not implemented TODO
					   'ELEVMAP': {},# no more used
					   'LANDUSEMAP': {},
					   'IRRMETHMAP': {},
					   'STARTOUTPUT': 105,
					   'ENDOUTPUT': 273,
					   'STEPOUTPUT': 10,
					   'MONTHOUTPUT': 'F',
					   'MINSLOPE': 0.1,
					   'MAXSLOPE': 1000,
					   'SOURCE_DB': '',
					   'DEFAULT_LU': 0,
					   'DEFAULT_IM': 0,
					   'VECTOR_MODE': vector_mode
					   }

		geo_export = None
		if sim_dic['VECTOR_MODE']:
			geo_export = ExportGeodataVector(parent=None, sim_dict=sim_dic, feedback=self.FEEDBACK, tr=lambda x: x)

		if geo_export:
			geo_export.exportGeodata()
		else:
			return {'MESSAGE': 'Raster mode not implemented!'}

		return {'MESSAGE': 'Done!'}
