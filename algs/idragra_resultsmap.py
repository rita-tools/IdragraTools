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

from datetime import datetime,timedelta

import os

import pandas as pd

class IdragraResultsMap(QgsProcessingAlgorithm):
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
	DOMAIN_LAY = 'DOMAIN_LAY'
	RES_VAR = 'RES_VAR'
	OUTPUT_LAY = 'OUTPUT_LAY'
	FEEDBACK = None

	def __init__(self):
		super().__init__()


	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraResultsMap()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraResultMaps'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Import results by domain map')

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
						The algorithm import the selected variable as map. 
						<b>Parameters:</b>
						IdrAgra file: the parameters file used for the IdrAgra simulation (*.txt) [IDRAGRA_FILE]
						Domain map: the vector layer that defines the domain map [DOMAIN_LAY]
						Result variable: the variable to be imported [RES_VAR]
						Output map: the results map [OUTPUT_LAY]
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

		#### PARAMETERS ####

		self.addParameter(QgsProcessingParameterFile(self.IDRAGRAFILE, self.tr('IdrAgra file'),
													  QgsProcessingParameterFile.Behavior.File,'*.*','',False,
													  'IdrAgra pars file (*.txt);;All files (*.*)'))
	
		self.addParameter(QgsProcessingParameterFeatureSource(self.DOMAIN_LAY, self.tr('Domain map'),
															  [], None, True))

		self.addParameter(QgsProcessingParameterEnum(self.RES_VAR, self.tr('Results variable'),
													 list(self.STEPNAME.values())))

		self.addParameter(QgsProcessingParameterFeatureSink (self.OUTPUT_LAY, self.tr('Select output file'),
															 QgsProcessing.TypeVectorPolygon))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		idragraFile = self.parameterAsFile(parameters, self.IDRAGRAFILE, context)

		domainLay = self.parameterAsVectorLayer(parameters, self.DOMAIN_LAY, context)

		varIdx = self.parameterAsEnum(parameters, self.RES_VAR, context)
		varToUse = list(self.STEPNAME.keys())[varIdx]

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

		# get list of output of the selected variable
		fileFilter = '*' + varToUse[4:] + '.asc'
		rootSimPath = os.path.dirname(idragraFile)
		pathToImport = os.path.join(rootSimPath, outputPath)[:-1]  # because ends with //
		# print('pathToImport',pathToImport)
		fileList = glob.glob(os.path.join(pathToImport, fileFilter))
		# prepare the output table
		# add domain fields
		allDomFldList = domainLay.fields()
		# get only some selected field'id','name' and 'area'
		selFldNames = ['id','name','area_m2','land_use','irrmeth_id','soil_id','irrunit_id']
		domFldList = QgsFields()
		for fld in allDomFldList:
			if fld.name() in selFldNames: domFldList.append(fld)

		resFldNames = []
		newFileList = []
		# add step results fields

		for f in fileList:
			# parse file name
			fname = os.path.basename(f)
			# extract date time
			parsedFld = None
			if '_month' in fname:
				# 2000_month1_caprise
				y = int(fname[0:4])
				tokStart = fname.index('_month') + len('_month')
				tokEnd = fname.index('_', tokStart)
				s = int(fname[tokStart:tokEnd])
				parsedFld = '%s_%s'%(y, str(s).rjust(2, '0'))
				resFldNames.append(parsedFld)
				newFileList.append(f)
			elif '_step' in fname:
				# 2000_step1_caprise.asc
				# self.FEEDBACK.pushInfo(self.tr('last file %s') % fname)
				y = int(fname[0:4])
				tokStart = fname.index('_step') + len('_step')
				tokEnd = fname.index('_', tokStart)
				s = int(fname[tokStart:tokEnd])
				# step to date
				parsedFld = '%s_%s'%(y, str(s).rjust(3, '0'))
				resFldNames.append(parsedFld)
				newFileList.append(f)
			else:
				# other outputs
				self.FEEDBACK.reportError(self.tr('Unmanaged file %s') %
										  (fname), False)

		if (varToUse[4:] == 'irr'):
			self.FEEDBACK.pushInfo(self.tr('Add special outputs'))
			# 2010_irr_mean.asc, 2010_irr_nr.asc, 2010_irr_tot.asc
			# get list of output of the selected variable
			for special_case in ['_mean','_nr','_tot']:
				fileFilter = '*' + varToUse[4:] + special_case+'.asc'
				pathToImport = os.path.join(rootSimPath, outputPath)[:-1]  # because ends with //
				fileList = glob.glob(os.path.join(pathToImport, fileFilter))
				for f in fileList:
					# parse file name
					fname = os.path.basename(f)
					y = int(fname[0:4])
					parsedFld = '%s%s' % (y,special_case)
					resFldNames.append(parsedFld)
					newFileList.append(f)

		# order fields to add
		newFileList = [x for _, x in sorted(zip(resFldNames, newFileList))]
		resFldNames = sorted(resFldNames)

		#print(newFileList)
		#print(resFldNames)

		resFldList = QgsFields()
		for fldName in resFldNames:
			resFldList.append(QgsField(fldName, QVariant.Double))

		finalFldList = QgsFields()
		finalFldList.extend(domFldList)
		finalFldList.extend(resFldList)

		# get output file
		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.OUTPUT_LAY,
			context,
			finalFldList,
			domainLay.wkbType(),
			domainLay.sourceCrs()
		)

		# save dataframe with domain data
		df = pd.DataFrame(columns=resFldNames)
		for fldName,filePath in zip(resFldNames, newFileList):
			self.FEEDBACK.pushInfo(self.tr('Reading %s from %s') % (fldName,filePath))
			# open file as dataframe
			tempDf = pd.read_csv(filePath,skiprows=6,header=None)

			# add column to res dataframe
			df[fldName] = tempDf.iloc[:,0]

		#print(df)
		# append results
		i = 0
		nOfFeat = domainLay.featureCount()
		for dom_feat in domainLay.getFeatures():
			feat = QgsFeature(finalFldList)
			feat.setGeometry(dom_feat.geometry())
			# add domain attributes
			for fld in domFldList:
				feat[fld.name()] = dom_feat[fld.name()]

			# add results values
			for c,fldName in enumerate(resFldNames):
				#print('test',i,'-',c, df.iloc[i, c])
				feat[fldName] = float(df.iloc[i,c])

			sink.addFeature(feat, QgsFeatureSink.FastInsert)

			i += 1
			self.FEEDBACK.setProgress(100.0 * i / nOfFeat)

		return {'OUTPUT_LAY':dest_id}
