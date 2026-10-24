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
						NULL)
						
import processing

import numpy as np

from datetime import datetime

import os

from ..tools.gis_grid import GisGrid
from ..tools.compact_dataset import getRasterInfos


class IdragraSaveAscii(QgsProcessingAlgorithm):
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
	
	INPUT= 'INPUT'
	DIGITS = 'DIGITS'
	OUTPUT = 'OUTPUT'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraSaveAscii()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraSaveAscii'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Save raster as ascii')

	def group(self):
		"""
		Returns the name of the group this algorithm belongs to. This string
		should be localised.
		"""
		return self.tr('Utility')

	def groupId(self):
		"""
		Returns the unique ID of the group this algorithm belongs to. This
		string should be fixed for the algorithm, and must not be localised.
		The group id should be unique within each provider. Group id should
		contain lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraUtility'

	def shortHelpString(self):
		"""
		Returns a localised short helper string for the algorithm. This string
		should provide a basic description about what the algorithm does and the
		parameters and outputs associated with it..
		"""
		
		helpStr = """
						The algorithm transform a raster file in ascii format (i.e. useful for Idragra model). 
						<b>Parameters:</b>
						Input raster: the raster layer to be transformed [INPUT]
						Digit: number of digit to maintain [DIGIT]
						Output raster: the name of the output raster [OUTPUT]
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
	
		self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, self.tr('Input raster')))
				
		self.addParameter(QgsProcessingParameterNumber(self.DIGITS, self.tr('Digit')))
		
		self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, self.tr('Output raster'), self.tr('ASCII (*.asc)')))
		
		
	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback

		self.lyr = None
		# get params

		inputLay = self.parameterAsRasterLayer(parameters, self.INPUT, context)
		digits = self.parameterAsInt(parameters, self.DIGITS, context)
		outputFile = self.parameterAsFileOutput(parameters,	self.OUTPUT, context)

		# get array
		self.data = self.convertRasterToNumpyArray(inputLay.source())

		feedback.pushInfo(self.tr('Saving output ...'))
		feedback.setProgress(90)
		geoDict = getRasterInfos(inputLay.source())
		# feedback.pushInfo(self.tr('Georeference parameters: %s') % str(geoDict))
		self.dx = geoDict['dx']
		self.dy = geoDict['dy']
		self.ncols = geoDict['ncols']
		self.nrows = geoDict['nrows']
		self.xllcorner = geoDict['xllcorner']
		self.yllcorner = geoDict['yllcorner']
		self.nodata = -9999

		# xurcorner = geoDict['xllcorner'] + self.ncols * geoDict['dx']
		# yurcorner = geoDict['yllcorner'] - self.nrows * geoDict['dy']
		#
		# # TODO: check if the link to the QGSProject instance resolves the memory issues
		# self.aGrid = GisGrid(ncols=ncols, nrows=nrows, xcell=xllcorner, ycell=yllcorner, dx=dx, dy=-dy, nodata=-9,
		# 				EPSGid=inputLay.crs().postgisSrid(), progress=self.FEEDBACK,parent = QgsProject.instance())
		# self.aGrid.data = inputArray  # maxDepthArray#
		#
		# # save to file
		# self.aGrid.saveAsASC(filename = outputFile, d=digits, useCellSize=True)
		# feedback.pushInfo(self.tr('... to %s')%outputFile)
		#
		# self.aGrid = None

		self.saveAsASCII(filename=outputFile, d=digits, useCellSize=True)

		outRaster = QgsRasterLayer(outputFile,self.tr('As ascii'))

		return {'OUTPUT':outRaster}

	def saveAsASCII(self,filename, d, useCellSize):
		"""
		savegrid		: save current grid in a Esri-like ASCII grid file.
		Arguments:
		filename		: the complete name of the new file (path + filename)
		d				 : decimal digit
		useCellSize	 : if True, write cellsize parameter instead of dx and dy
		"""
		try:
			# use of with to automatically close the file
			with open(filename, 'w') as f:
				f.write('ncols ' + str(self.ncols) + '\n')
				f.write('nrows ' + str(self.nrows) + '\n')
				f.write('xllcorner ' + str(self.xllcorner) + '\n')
				f.write('yllcorner ' + str(self.yllcorner) + '\n')
				if useCellSize:
					f.write('cellsize ' + str(self.dx) + '\n')
				else:
					f.write('dx ' + str(self.dx) + '\n')
					f.write('dy ' + str(self.dy) + '\n')

				if d == 0:
					f.write('nodata_value ' + str(int(self.nodata)) + '\n')
				else:
					f.write('nodata_value ' + str(round(self.nodata, d)) + '\n')

				s = ''
				c = 0

				i = 0
				# replace nan with nodata
				idx = np.where(np.isnan(self.data))
				dataToPrint = self.data
				dataToPrint[idx] = self.nodata

				if d == 0:
					for row in dataToPrint:
						i += 1
						self.FEEDBACK.setProgress(100 * float(i) / self.nrows)
						for el in row:
							# print len(el)
							s = s + str(int(round(el, d)))
							c = c + 1
							# add space if not EOF
							if c % self.ncols != 0:
								s = s + ' '
							else:
								s = s + '\n'

				else:
					for row in dataToPrint:
						i += 1
						self.FEEDBACK.setProgress(100 * float(i) / self.nrows)
						for el in row:
							# print len(el)
							s = s + str(round(el, d))
							c = c + 1
							# add space if not EOF
							if c % self.ncols != 0:
								s = s + ' '
							else:
								s = s + '\n'

				f.write(s)

			# f.write('projection ' + str(self.hd.prj) + '\n')
			# f.write('notes ' + str(self.hd.note))
			# TODO: this line causes memory issue, probably because self.progress is lost
			self.FEEDBACK.pushInfo(self.tr('Grid exported to %s')%(filename))
		except Exception as e:
			# print 'Cannot save file: %s' %filename
			self.FEEDBACK.error(self.tr('Cannot save to %s because %s') % (filename, str(e)))

	def convertRasterToNumpyArray(self,lyrFile):  # Input: QgsRasterLayer
		#self.FEEDBACK.pushInfo(self.tr('In convertRasterToNumpyArray, start %s') % (lyrFile))
		self.lyr = QgsRasterLayer(lyrFile, 'temp')
		values = []
		provider = self.lyr.dataProvider()
		nodata = provider.sourceNoDataValue (1)
		block = provider.block(1, self.lyr.extent(), self.lyr.width(), self.lyr.height())

		#self.FEEDBACK.pushInfo(self.tr('In convertRasterToNumpyArray, middle'))

		for i in range(self.lyr.height()):
			for j in range(self.lyr.width()):
				values.append(block.value(i, j))

		a = np.array(values)
		#print('shape of %s: %s, %s'%(lyrFile,self.lyr.height(),self.lyr.width()))
		a = np.reshape(a,(self.lyr.height(),self.lyr.width()))
		a[a==nodata]= np.nan
		#self.FEEDBACK.pushInfo(self.tr('In convertRasterToNumpyArray, end'))
		return a