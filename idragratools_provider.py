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

import os

from qgis.core import QgsProcessingProvider

from qgis.PyQt.QtGui import QIcon

from .algs.idragra_create_elev_to_field import IdragraCreateElevToField
from .algs.idragra_clean_overlap import IdragraCleanOverlap
from .algs.idragra_multi_join import IdragraMultiJoin
from .algs.idragra_resultsmap import IdragraResultsMap
from .algs.idragra_export_control_points_vector import IdragraExportControlPointsVector
from .algs.idragra_create_raster_to_field import IdragraCreateRasterToField
from .algs.idragra_create_field_table import IdragraCreateFieldTable
from .algs.idragra_report_overview import IdragraReportOverview
from .algs.idragra_import_from_existing_db import IdragraImportFromExistingDB
from .algs.idragra_groupstats_by_raster import IdragraGroupStatsByRaster
from .algs.idragra_import_irrunits_results import IdragraImportIrrUnitsResults
from .algs.idragra_raster_quality import IdragraRasterQuality
from .algs.idragra_annual_stats import IdragraAnnualStats
from .algs.idragra_raster_groupstats import IdragraRasterGroupStats
from .algs.idragra_import_crop_par import IdragraImportCropPar
from .algs.idragra_bulk_import_timeserie import IdragraBulkImportTimeserie
from .algs.idragra_statserie import IdragraStatserie
from .algs.idragra_export_control_points_grid import IdragraExportControlPointsGrid
from .algs.idragra_calc_waterdepth import IdragraCalcWaterDepth
from .algs.idragra_rasterize_time_map import IdragraRasterizeTimeMap
from .algs.idragra_rasterize_map import IdragraRasterizeMap
from .algs.idragra_saveascii import IdragraSaveAscii
from .algs.idragra_create_hsg_map import IdragraCreateHSGMap
from .algs.idragra_create_pre_hsg_table import IdragraCreatePreHSGTable
from .algs.idragra_create_caprise_table import IdragraCreateCapriseTable
from .algs.idragra_create_soilparams import IdragraSoilParams
from .algs.idragra_import_vector_map import IdragraImportVectorMap
from .algs.idragra_create_db import IdragraCreateDB
from .algs.idragra_groupstats import IdragraGroupStats
from .algs.idragra_make_slope import IdragraMakeSlope
from .algs.idragra_export_spatialdata import IdragraExportSpatialdataAlgorithm
from .algs.idragra_import_simoutput import IdragraImportSimoutput
from .algs.idragra_import_timeserie import IdragraImportTimeserie
from .algs.idragra_rasterize_maptable import IdragraRasterizeMaptable
from .algs.idragra_export_meteodata import IdragraExportMeteodata
from .algs.idragra_rasterize_domain import IdragraRasterizeDomain
from .algs.idragra_export_weights import IdragraExportWeights
from .algs.idragra_get_from_dtm import IdragraGetFromDtm

class IdrAgraToolsProvider(QgsProcessingProvider):

	def __init__(self):
		QgsProcessingProvider.__init__(self)

		# Load algorithms
		self.alglist = [IdragraExportSpatialdataAlgorithm(),
						IdragraImportSimoutput(),
						IdragraImportTimeserie(),
						IdragraRasterizeMaptable(),
						IdragraExportMeteodata(),
						IdragraRasterizeDomain(),
						IdragraExportWeights(),
						IdragraGetFromDtm(),
						IdragraMakeSlope(),
						IdragraGroupStats(),
						IdragraCreateDB(),
						IdragraImportVectorMap(),
						IdragraSoilParams(),
						IdragraCreateCapriseTable(),
						IdragraCreatePreHSGTable(),
						IdragraCreateHSGMap(),
						IdragraSaveAscii(),
						IdragraRasterizeMap(),
						IdragraRasterizeTimeMap(),
						IdragraCalcWaterDepth(),
						IdragraExportControlPointsGrid(),
						IdragraStatserie(),
						IdragraBulkImportTimeserie(),
						IdragraImportCropPar(),
						IdragraRasterGroupStats(),
						IdragraAnnualStats(),
						IdragraRasterQuality(),
						IdragraGroupStatsByRaster(),
						IdragraImportIrrUnitsResults(),
						IdragraImportFromExistingDB(),
						IdragraReportOverview(),
						IdragraCreateFieldTable(),
						IdragraCreateRasterToField(),
						IdragraExportControlPointsVector(),
						IdragraResultsMap(),
						IdragraMultiJoin(),
						IdragraCleanOverlap(),
						IdragraCreateElevToField()
						]

	def unload(self):
		"""
		Unloads the provider. Any tear-down steps required by the provider
		should be implemented here.
		"""
		pass

	def loadAlgorithms(self):
		"""
		Loads all algorithms belonging to this provider.
		"""
		for alg in self.alglist:
			self.addAlgorithm( alg )

	def id(self):
		"""
		Returns the unique provider id, used for identifying the provider. This
		string should be a unique, short, character only string, eg "qgis" or
		"gdal". This string should not be localised.
		"""
		return 'idragratools'

	def name(self):
		"""
		Returns the provider name, which is used to describe the provider
		within the GUI.

		This string should be short (e.g. "Lastools") and localised.
		"""
		return self.tr('IdrAgra Tools')

	def longName(self):
		"""
		Returns the a longer version of the provider name, which can include
		extra details such as version numbers. E.g. "Lastools LIDAR tools
		(version 2.2.1)". This string should be localised. The default
		implementation returns the same string as name().
		"""
		return self.tr('A set of tools to manage water in irrigation districts')

	def icon(self):
		self.plugin_dir = os.path.dirname(__file__)
		icon = QIcon(os.path.join(self.plugin_dir, 'idragratools_provider.png'))
		return icon