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
						QgsProcessingParameterFile,
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

from numpy import array

from datetime import datetime

import os.path as osp

from ..tools.regenerate_idragra_output import *


class IdragraImportSimoutput(QgsProcessingAlgorithm):
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
	
	INPUTFOLDER = 'INPUT_FOLDER'
	DESTFOLDER = 'DEST_FOLDER'
	REFMAP = 'REF_MAP'
	REFCRS = 'REF_CRS'
	FILEEXT = 'FILE_EXT'
	VARNAME = 'VAR_NAME'
	
	
	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraImportSimoutput()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraImportSimoutput'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Import simulation results')

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
						Import all simulation output map (*.asc) from the output folder.
						<b>Parameters:</b>
						Idragra outputs folder: path to the folder where Idragra model saved the output file [INPUT_FOLDER]
						File with reference parameters: is the file that contains georeferencing parameters, commonly created by idragra4qgis (e.g. validcell.asc) [REF_MAP]
						Export to: the path to the folder where save the resulting maps [DEST_FOLDER]
						File extension: the type of the file of the resulting raster maps [FILE_EXT]<sup>1</sup>
						Variable: the variable to be importarted [VAR_NAME_LIST] 
						<b>Note:</b>
						[1] suggested file format is geotif (*.tif). ASCII grid file is not supported. Use GDAL Translate to confert to *.asc file format.  
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
		self.addParameter(	QgsProcessingParameterFile(self.INPUTFOLDER, self.tr('Idragra outputs folder'),QgsProcessingParameterFile.Behavior.Folder))
		
		self.addParameter(	QgsProcessingParameterFile(self.REFMAP, self.tr('File with reference parameters'),QgsProcessingParameterFile.Behavior.File,'*.*','',False,'ASCII (*.asc);;All files (*.*)'))		
		
		self.addParameter(	QgsProcessingParameterFolderDestination(self.DESTFOLDER, self.tr('Export to'),'',False))
			
		self.EXTLIST = QgsRasterFileWriter.supportedFormatExtensions()
		self.addParameter(	QgsProcessingParameterEnum(self.FILEEXT, self.tr('File extension'),self.EXTLIST,False,'tif',False))
		
		# the order of the first 3 options is mandatory 
		self.VARDICT = {self.tr('All output'):'*.*',self.tr('Data table (*.csv)'):'*.csv',self.tr('All spatial output (*.asc)'):'*.asc',
								self.tr('Potential transpiration'):'*_trasp_pot.asc', self.tr('Actual transpiration'):'*_trasp_act.asc',
								self.tr('Runoff'):'*_runoff.asc', self.tr('Precipitation'):'*_prec.asc',
								self.tr('Irrigation ???'):'*_irr_privw.asc', self.tr('Irrigation losses'):'*_irr_loss.asc',
								self.tr('Irrigation distribution'):'*_irr_distr.asc', self.tr('Irrigation'):'*_irr.asc',
								self.tr('Flux to 2nd layer'):'*_flux2.asc', self.tr('Potential ET'):'*_et_pot.asc',
								self.tr('Actual ET'):'*_et_act.asc', self.tr('Capilar rise'):'*_caprise.asc'
								}
								
		self.VARNAMELIST = list(self.VARDICT.keys())
								
		self.addParameter(	QgsProcessingParameterEnum(self.VARNAME, self.tr('Variable'),self.VARNAMELIST,True,0,False))
		
		
	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		
		pathToImport = self.parameterAsFile(parameters, self.INPUTFOLDER, context)
		
		geoparFile = self.parameterAsFile(parameters, self.REFMAP, context)
		
		pathToExport = self.parameterAsFile(parameters, self.DESTFOLDER, context)
		
		rasterExtInd = self.parameterAsEnum(parameters, self.FILEEXT, context)
		rasterExt = self.EXTLIST[rasterExtInd]
		
		varList = self.parameterAsEnums(parameters, self.VARNAME, context)
		
		# create new array
		prms = readCellIndexFile(geoparFile)
		geoparString = 'XLLCORNER: %s\nYLLCORNER: %s\nDX: %s\nDY: %s\nNCOLS: %s\nNROWS: %s\n'%(prms['xllcorner'], prms['yllcorner'], prms['dx'], prms['dy'],prms['ncols'],prms['nrows'])
		self.FEEDBACK.pushInfo(self.tr('Georeference parameters:\n%s'%geoparString))
		
		# do something with layers and dest folder
		# loop in pathToImport and list all file
		c = 0.0
		fileList = []
		for i in varList:
			k = self.VARNAMELIST[i]
			self.FEEDBACK.pushInfo(self.tr('Looking for %s files'%k))
			fileFilter = self.VARDICT[k]
			fileList += glob.glob(os.path.join(pathToImport,fileFilter))
			if fileFilter in ['*.*','*.asc']:	break
			
		ntot = len(fileList)
		self.FEEDBACK.setProgress (0.0)
		self.FEEDBACK.pushInfo(self.tr('Number of file to be processed: %s'%ntot))
		for f in fileList:
			fname = os.path.basename(f)
			if fname.endswith('asc'):
				#compact
				importFrom = os.path.join(pathToImport,fname)
				prms2 = readCellIndexFile(importFrom)
				
				fileToExport = os.path.join(pathToExport,fname[:-4]+'.'+rasterExt)
				regenerateRaster(prms,prms2,fileToExport)
				self.FEEDBACK.pushInfo(self.tr('Import file %s to %s'%(fname,fileToExport)))
			elif fname.endswith('csv'):
				#make a copy
				fileToExport = os.path.join(pathToExport,fname)
				shutil.copyfile(os.path.join(pathToImport,fname),fileToExport)
				self.FEEDBACK.pushInfo(self.tr('Copy file %s as %s'%(fname,fileToExport)))
			else:
				self.FEEDBACK.pushInfo(self.tr('Not recognized file extension: %s'%f))
			
			c+=1.0
			self.FEEDBACK.setProgress (100.0*c/ntot)
			if self.FEEDBACK.isCanceled():
				self.FEEDBACK.pushInfo(self.tr('A total of %s file were imported'%c))
				break
		
		return {'NUMOFIMPORTEDMAP': c}
		
		#https://www.faunalia.eu/fr/blog/2019-07-02-custom-processing-widget
		