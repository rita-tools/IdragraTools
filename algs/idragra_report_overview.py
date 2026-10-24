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

import qgis
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication

from qgis.core import (QgsProcessingAlgorithm,
					   QgsProcessingParameterFileDestination,
					   QgsProcessingParameterFile, QgsProcessingParameterEnum)
						


import os

from report.annual_totals_report_builder import AnnualTotalsReportBuilder
from report.irrunit_totals_report_builder import IrrunitTotalsReportBuilder
from report.report_builder import ReportBuilder
from ..report.overview_report_builder import OverviewReportBuilder



class IdragraReportOverview(QgsProcessingAlgorithm):
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
	
	SIM_FOLDER= 'SIM_FOLDER'
	OUTPUT = 'OUTPUT'
	REPORT_FORMAT = 'REPORT_FORMAT'
	FEEDBACK = None

	def __init__(self):
		super().__init__()


	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraReportOverview()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraReportOverview'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Make report of general information about the simulation')

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
						The algorithm makes a report of the general information about the simulation. 
						<b>Parameters:</b>
						IdrAgra simulation folder: the directory where IdrAgra I/O files are saved [SIM_FOLDER]
						Output file: the resultant report in html format [OUTPUT]
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
		#### PARAMETERS ####
		self.REPORT_TYPES =  qgis.utils.plugins['IdragraTools'].REPORT_TYPES

		self.addParameter(QgsProcessingParameterFile(self.SIM_FOLDER, self.tr('IdrAgra simulation folder'),
													  QgsProcessingParameterFile.Behavior.Folder,'','',False,''))
	
		self.addParameter(QgsProcessingParameterFileDestination (self.OUTPUT, self.tr('Output file'), 'Report file (*.html)', None, False, True))
		self.addParameter(QgsProcessingParameterEnum(self.REPORT_FORMAT, self.tr('Report type'),
													 list(self.REPORT_TYPES.values())))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback

		# get params
		simFolder = self.parameterAsFile(parameters, self.SIM_FOLDER, context)
		outfile = self.parameterAsFile(parameters, self.OUTPUT, context)
		repFrtIdx = self.parameterAsEnum(parameters, self.REPORT_FORMAT, context)
		repFrt = list(self.REPORT_TYPES.keys())[repFrtIdx]
		if repFrt=='general':
			RB = OverviewReportBuilder(self.FEEDBACK,self.tr)
		elif repFrt=='annuals_totals':
			RB = AnnualTotalsReportBuilder(self.FEEDBACK,self.tr)
		elif repFrt == 'irrunits_totals':
			RB = IrrunitTotalsReportBuilder(self.FEEDBACK,self.tr)
		else:
			RB = ReportBuilder(self.FEEDBACK,self.tr)

		outfile = RB.makeReport(simFolder, outfile)

		return {'OUTPUT': outfile}

