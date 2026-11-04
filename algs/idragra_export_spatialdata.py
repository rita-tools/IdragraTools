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

import os.path as osp

from ..tools.compact_dataset import *


class IdragraExportSpatialdataAlgorithm(QgsProcessingAlgorithm):
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
	
	INPUTLIST = 'INPUT_LIST'
	DESTFOLDER = 'DEST_FOLDER'
	
	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraExportSpatialdataAlgorithm()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraExportSpatialData'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Spatial dataset')

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
				Export all selected raster maps in a non georeferenced but consistent compacted form suitable for Idragra simulation. 
				<b>Parameters:</b>
				Layer to be exported: the list of the raster layers to be exported [INPUT_LIST]
				Export to: the path to the folder where exported data will be saved [DEST_FOLDER]
				
				<b>Notes:</b>
				Raster maps must have the same georeferencing parameters.
								
				The algorithm selects only the cells that have valid data (i.e it skips all nodata cells).
				Data will be stored as 1D array in a text file. Georeferencing values have no spatial meaning in this case.
				Exported file are text file with the following structure:
				
				ncols 1
				nrows 23908
				xllcorner 519418.5301
				yllcorner 4988100.06335
				cellsize 250.0
				nodata_value -9999.0000000000
				-0.1500000060
				-0.3
				...
				
				Additionally, the algorithm will create the following file:
				
				cellarea.asc: contains the area of the cell. The file has the same format as before.
				validcell.asc: contains the consecutive index of the original domain map. In this case, the first six lines report the correct georeferencing parameters. 
				
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


		self.addParameter(QgsProcessingParameterMultipleLayers (self.INPUTLIST, self.tr('Layers to be exported'),\
																								QgsProcessing.TypeRaster, '', False))
		
		self.addParameter(	QgsProcessingParameterFolderDestination(self.DESTFOLDER, self.tr('Export to')))
		

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		
		layers = self.parameterAsLayerList(parameters, self.INPUTLIST, context)
		
		destFolder = self.parameterAsFile(parameters, self.DESTFOLDER, context)
		
		# do something with layers and dest folder
		numExportedMap = exportDataSet(layers, destFolder, self.FEEDBACK.pushInfo, self.tr)
		
		return {'NUMOFEXPORTEDMAP': numExportedMap}
		
		#https://www.faunalia.eu/fr/blog/2019-07-02-custom-processing-widget
		