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
					   QgsProcessingParameterRasterLayer,
					   QgsProcessingParameterVectorLayer,
					   QgsProcessingParameterFile,
					   QgsProcessingParameterString,
					   QgsProcessingParameterNumber,
					   QgsProcessingParameterBoolean,
					   QgsProcessingParameterField,
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
					   NULL, QgsProcessingParameterExtent)

import processing

from numpy import array

from datetime import datetime

import os

from ..tools.import_from_csv import *
from ..tools.compact_dataset import getRasterInfos


class IdragraRasterizeMaptable(QgsProcessingAlgorithm):
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

	VECTORLAY= 'VECTOR_LAY'
	VECTORFLD = 'VECTOR_FLD'
	TABLELAY = 'TABLE_LAY'
	TABLEFLD = 'TABLE_FLD'
	RASTERLAY = 'RASTER_LAY'
	RASTEREXT = 'RASTER_EXT'
	CELLDIM = 'CELL_DIM'
	DESTFOLDER = 'DEST_FOLDER'

	FEEDBACK = None


	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraRasterizeMaptable()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraRasterizeMaptable'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Raster maps from tables')

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
						The algorithm distributes the values of all the numeric field in the source table base on the category distribution of the vector map.
						Results is a set of raster layer with the same dimension of the reference raster map. 
						<b>Parameters:</b>
						Table: the source of the data to be written in raster format [TABLE_LAY]
						Table id: the field in Table with an unique identifier [TABLE_FLD]
						Distribution map: a polygon layer that represents the distribution of the variable contained in Table [VECTOR_LAY]
						Distribution id: the field in Distribution map that matches the Table id [VECTOR_FLD]
						Reference raster: a raster map to copy for georeference parameters [RASTER_LAY]
						Output folder: the path where output raster maps will be saved [DEST_FOLDER]
						<b>Notes:</b>
						This is a general purpose algorithm that can be applyed to different table-map combinations.
						It's useful to create raster maps of soil and other field parameters from the idragra4qgis database.
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

		self.addParameter(QgsProcessingParameterVectorLayer(self.TABLELAY, self.tr('Table'), [QgsProcessing.TypeFile]))

		self.addParameter(QgsProcessingParameterField (self.TABLEFLD, self.tr('Table id'), 'id', self.TABLELAY, QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterVectorLayer(self.VECTORLAY, self.tr('Distribution map'), [QgsProcessing.TypeVectorPolygon ]))

		self.addParameter(QgsProcessingParameterField (self.VECTORFLD, self.tr('Distribution id'), 'fid', self.VECTORLAY, QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterRasterLayer(self.RASTERLAY, self.tr('Reference raster'),None, True))

		self.addParameter(QgsProcessingParameterExtent(self.RASTEREXT, self.tr('Raster extension'),None, True))

		self.addParameter(QgsProcessingParameterNumber(self.CELLDIM, self.tr('Raster cell dimension'),QgsProcessingParameterNumber.Double,
													   None, True))

		self.addParameter(	QgsProcessingParameterFile(self.DESTFOLDER, self.tr('Output folder'),QgsProcessingParameterFile.Behavior.Folder))


	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# store output here:
		self.algresult1 = None
		self.algresult2 = None
		# get params
		tableLay = self.parameterAsVectorLayer(parameters, self.TABLELAY, context)
		tableFld = self.parameterAsFields(parameters, self.TABLEFLD, context)[0]
		vectorLay = self.parameterAsVectorLayer(parameters, self.VECTORLAY, context)
		vectorFld = self.parameterAsFields(parameters, self.VECTORFLD, context)[0]
		rasterLay = self.parameterAsRasterLayer(parameters, self.RASTERLAY, context)
		destFolder = self.parameterAsFile(parameters, self.DESTFOLDER, context)
		rasterExt = self.parameterAsExtent(parameters, self.RASTEREXT, context)
		dx = self.parameterAsDouble(parameters, self.CELLDIM, context)
		dy=dx

		# get raster georeferencing parameters
		if rasterLay:
			geoDict = getRasterInfos(rasterLay.source())
			feedback.pushInfo(self.tr('Georeference parameters: %s')%str(geoDict))
			dx = geoDict['dx']
			dy = -geoDict['dy']
			xllcorner = geoDict['xllcorner']
			yllcorner = geoDict['yllcorner']
			xurcorner = geoDict['xllcorner']+geoDict['ncols']*geoDict['dx']
			yurcorner = geoDict['yllcorner']-geoDict['nrows']*geoDict['dy']
			rasterExt = '%s, %s, %s, %s' % (xllcorner, xurcorner, yllcorner, yurcorner)

		# get the list of field name from table
		fldNameList = []
		fldTypeList = []
		prov = tableLay.dataProvider()
		nOfField = 0
		for field in prov.fields():
			if ((field.name() != tableFld) and (field.type()!=QVariant.String) and field.name() not in ['fid']):
				fldNameList.append(field.name())
				fldTypeList.append(field.type())
				nOfField+=1

		#print('fldTypeList:',fldTypeList)
		## 'EXTENT':'-2.1723558404658085,1.6390224197123306,-0.5515929222106931,0.834778761863708 [EPSG:4326]'
		## 'ncols': ncols, 'nrows':nrows, 'ncells':ncells, 'proj':proj, 'xllcorner':xll, 'yllcorner':yll, 'dx':dx, 'dy':dy, 'cellsize':dx, 'nodata':-9999.0

		# join vector with table first
		self.algresult = processing.run("qgis:joinattributestable",
				{ 'DISCARD_NONMATCHING' : True,
					'FIELD' : vectorFld,
					'FIELDS_TO_COPY' : [],
					'FIELD_2' : tableFld,
					'INPUT' : vectorLay,
					'INPUT_2' : tableLay,
					'METHOD' : 1,
					'OUTPUT' : 'TEMPORARY_OUTPUT',
					'PREFIX' : '' },
				context=context, feedback=feedback, is_child_algorithm=True)

		#joinedLay = self.algresult['OUTPUT']

		# rasterize each field in joined layer
		c =0

		for fldName, fldType in zip(fldNameList,fldTypeList):
			feedback.pushInfo(self.tr('Exporting field %s'%fldName))
			# rasterize
			self.algresult2 = processing.run("gdal:rasterize",
							{'INPUT':self.algresult['OUTPUT'],
								'FIELD':fldName,
								'BURN':0,
								'UNITS':1,
								'WIDTH':dx,
								'HEIGHT':dy,
								'EXTENT':rasterExt,
								'NODATA':-9999,
								'OPTIONS':'',
								'DATA_TYPE':fldType,
								'INIT':None,
								'INVERT':False,
								'EXTRA':'',
								'OUTPUT':'TEMPORARY_OUTPUT'},
							context=context, feedback=feedback, is_child_algorithm=True)

			outPath = os.path.join(destFolder,fldName+'.asc')
			# convert to ascii
			# algresult3 = processing.run("gdal:translate",
			# 									{'INPUT':newRasterLay,
			# 									'TARGET_CRS':None,
			# 									'NODATA':None,
			# 									'COPY_SUBDATASETS':False,
			# 									'OPTIONS':'',
			# 									'EXTRA':'',
			# 									'DATA_TYPE':0,
			# 									'OUTPUT':outPath},
			# 				context=context, feedback=feedback, is_child_algorithm=True)
			feedback.pushInfo(self.tr('Saving to file %s' % outPath))
			processing.run("idragratools:IdragraSaveAscii",
						   {'INPUT': self.algresult2['OUTPUT'], 'DIGITS': 6,
							'OUTPUT': outPath},
						   context=None, feedback=feedback, is_child_algorithm=False)

			c+=1

			feedback.setProgress(100*c/nOfField)

		return {'NUMOFEXPORTEDRASTER': c}

		#https://www.faunalia.eu/fr/blog/2019-07-02-custom-processing-widget
