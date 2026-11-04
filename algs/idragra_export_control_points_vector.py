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
					   NULL, QgsRectangle)


from numpy import array

from datetime import datetime

import os

from ..tools.write_pars_to_template import writeParsToTemplate


class IdragraExportControlPointsVector(QgsProcessingAlgorithm):
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
	
	DOMAINLAY= 'DOMAIN_LAY'
	ROWCOL = 'ROW_COL'
	CPLAY = 'CP_LAY'
	IDCOL = 'ID_COL'
	DESTFILE = 'DEST_FILE'
		
	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraExportControlPointsVector()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraExportControlPointsVector'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Control points (vector mode)')

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
						The algorithm creates a file with the list of the cells where save detailed output. 
						<b>Parameters:</b>
						Domain layer: the vector layer of the domain shape (polygons) [DOMAIN_LAY]
						Row index column: the column with the row index [ROW_COL]
						CP layer: the vector layer of control points (points) [CP_LAY]
						CP id: the column with the id of the control poinr [ID_COL]
						Output file: the complete path of the output file (*.txt) [DESTFILE]
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
	
		self.addParameter(QgsProcessingParameterVectorLayer(self.DOMAINLAY, self.tr('Source vector layer'), [QgsProcessing.TypeVectorPolygon ]))

		self.addParameter(QgsProcessingParameterField(self.ROWCOL, self.tr('Row column'), 'row_count', self.DOMAINLAY,
													  QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterVectorLayer(self.CPLAY, self.tr('Control point layer'), [QgsProcessing.TypeVectorPoint ]))

		self.addParameter(QgsProcessingParameterField(self.IDCOL, self.tr('Id column'), 'id', self.CPLAY,
													  QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterFileDestination(self.DESTFILE, self.tr('Output file'), self.tr('text file (*.txt)')))
		
		
	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		domainLay = self.parameterAsVectorLayer(parameters, self.DOMAINLAY, context)
		rowCol = self.parameterAsFields(parameters, self.ROWCOL, context)[0]
		cpLay = self.parameterAsVectorLayer(parameters, self.CPLAY, context)
		idCol = self.parameterAsFields(parameters, self.IDCOL, context)[0]
		filename = self.parameterAsFileOutput(parameters,	self.DESTFILE,	context)

		# loop in layer and get point coordinates
		nOfCP = 0
		recs = ['ID\tX\tY']
		dummy = []
		nFeats = cpLay.featureCount()
		n = 0
		for feature in cpLay.getFeatures():
			try: geom = feature.geometry()
			except: geom = None

			if geom:
				for domShape in domainLay.getFeatures():
					if geom.intersects(domShape.geometry()):
						row_col = '%s\t%s'% (domShape[rowCol], 1)# flipped
						if not row_col in dummy:
							newRec = '%s\t%s' % (feature['id'],row_col)#(n + 1,row_col)
							dummy.append(row_col)
							recs.append(newRec)
						else:
							self.FEEDBACK.reportError(
								self.tr(
									'More than one control point falls in one computational cell. Only the first one will be exported. Consider to reduce computation shape size.') %
								(feature['name']))
						break

			n+=1
			self.FEEDBACK.setProgress(100. * n / nFeats)

		tableTxt = '\n'.join(recs)
		cpDict = {'NUMCELL':len(dummy), 'CELLTABLE':tableTxt}

		writeParsToTemplate(outfile=filename,
							parsDict=cpDict,
							templateName='cells.txt')


		return {'OUTPUT':cpDict}
		