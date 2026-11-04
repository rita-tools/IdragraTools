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
import os
import numpy as np
from qgis.PyQt.QtCore import QObject
from qgis import processing
from qgis.core import QgsVectorLayer, QgsFeatureRequest

from .check_value import checkValue
from .compact_dataset import save2idragra
from .gis_grid import GisGrid
from .utils import returnExtent
from .write_pars_to_template import writeParsToTemplate
from datetime import date


class Exporter(QObject):

	def __init__(self, parent=None, simdic=None, feedback = None,tr=None):
		QObject.__init__(self, parent)
		self.feedback = feedback
		self.tr = tr
		self.simdic = simdic
		self.aGrid = None
		self.algResults = None # store temporary outputs
		self.algResults1 = None  # store temporary outputs
		self.algResults2 = None  # store temporary outputs

	def exportGeodata(self,DBM,outPath, extent, cellSize, dtm, watertableDict, depthList,yearList,):
		yearList = ['']+[str(x) for x in yearList] # make a list of strings, add first empty year for default values
		# TODO: fix output digits
		# export water district map
		# DISTRICT SOURCE
		self.feedback.pushInfo(self.tr('Exporting districts data'))
		self.feedback.setProgress(10.0)
		fileName = os.path.join(outPath, 'irr_units' + '.asc')
		laySource = DBM.DBName+ '|layername=idr_distrmap'
		fieldName = 'id'

		self.algResults = processing.run("idragratools:IdragraRasterizeMap",
								   {'VECTOR_LAY': laySource, 'VECTOR_FLD': fieldName,
									'RASTER_EXT': extent,
									'CELL_DIM': cellSize,
									'DEST_FILE': fileName},
								context = None, feedback = self.feedback, is_child_algorithm = False)

		# DISTRICT EFFICIENCY
		fileName = os.path.join(outPath, 'conv_eff' + '.asc')
		laySource = DBM.DBName+ '|layername=idr_distrmap'
		fieldName = 'distr_eff'

		self.feedback.setProgress(35.0)
		self.algResults = processing.run("idragratools:IdragraRasterizeMap",
									{'VECTOR_LAY': laySource, 'VECTOR_FLD': fieldName,
									 'RASTER_EXT': extent,
									 'CELL_DIM': cellSize,
									 'DEST_FILE': fileName},
									context=None, feedback=self.feedback, is_child_algorithm=False)

		self.feedback.pushInfo(self.tr('Exporting soils parameters'))
		self.feedback.setProgress(50.0)
		# SOIL PARAMETERS MAP
		# check soil params
		soil_prof = DBM.getRecordAsDict(tableName='idr_soil_profiles',fieldsList='')
		#print('soil_prof',soil_prof)
		for sp in soil_prof:
			check_flag = 1
			# maxdepth, ksat >0
			check_flag*=checkValue('maxdepth', sp['maxdepth'], 0, '>=', self.tr, self.feedback)
			check_flag*=checkValue('ksat', sp['ksat'], 0, '>=', self.tr, self.feedback)
			# theta_fc,theta_wp,theta_r,theta_sat > 0 & <= 1
			check_flag*=checkValue('theta_fc', sp['theta_fc'], [0., 1.], '>=<=', self.tr, self.feedback)
			check_flag*=checkValue('theta_wp', sp['theta_wp'], [0., 1.], '>=<=', self.tr, self.feedback)
			check_flag*=checkValue('theta_r', sp['theta_r'], [0., 1.], '>=<=', self.tr, self.feedback)
			check_flag*=checkValue('theta_sat', sp['theta_sat'], [0., 1.], '>=<=', self.tr, self.feedback)
			# theta_sat>theta_fc>theta_wp>theta_r
			check_flag *= checkValue('theta_sat>theta_fc', sp['theta_sat'], sp['theta_fc'], '>', self.tr,
									 self.feedback)
			check_flag *= checkValue('theta_fc>theta_wp', sp['theta_fc'], sp['theta_wp'], '>', self.tr,
									 self.feedback)
			check_flag *= checkValue('theta_wp>theta_r', sp['theta_wp'], sp['theta_r'], '>', self.tr,
									 self.feedback)
			# txtr_code in 1 - 12
			check_flag *= checkValue('txtr_code', sp['txtr_code'], list(range(1,13)), 'in', self.tr, self.feedback)

			if check_flag == 0: return -1

		# export soil ids. Actually not used by IdrAgra but needed to test cell dimension
		fileName = os.path.join(outPath, 'soilid' + '.asc')
		soilMap = DBM.DBName + '|layername=idr_soilmap'
		fieldName = 'extid'
		self.algResults = processing.run("idragratools:IdragraRasterizeMap",
										 {'VECTOR_LAY': soilMap, 'VECTOR_FLD': fieldName,
										  'RASTER_EXT': extent,
										  'CELL_DIM': cellSize,
										  'DEST_FILE': fileName},
										 context=None, feedback=self.feedback, is_child_algorithm=False)

		# make aggregate parameters
		sourceTable = DBM.DBName + '|layername=idr_soil_profiles'
		depths = ' '.join([str(x) for x in depthList])
		print('depths:',depths)
		# make aggregate soil params
		self.algResults = processing.run("idragratools:IdragraSoilParams",
									{'SOURCE_TABLE':sourceTable,
									 'SOILID_FLD':'soilid','MAXDEPTH_FLD':'maxdepth',
									 'KSAT_FLD':'ksat',
									 'TFC_FLD':'theta_fc','TWP_FLD':'theta_wp','TR_FLD':'theta_r','TS_FLD':'theta_sat',
									 'DEPTHS':depths,'OUT_TABLE':'TEMPORARY_OUTPUT'},
									context=None, feedback=self.feedback, is_child_algorithm=False)

		# export to maps
		self.algResults =  processing.run("idragratools:IdragraRasterizeMaptable",
									 {'TABLE_LAY': self.algResults['OUT_TABLE'],# export aggregate params maps by aritmetic mean ...
									  'TABLE_FLD': 'soilid', 'VECTOR_LAY': soilMap,
									  'VECTOR_FLD': 'extid', 'RASTER_LAY': None,
									  'RASTER_EXT':extent,
									  'CELL_DIM': cellSize, 'DEST_FOLDER': outPath},
									 context=None, feedback=self.feedback, is_child_algorithm=False)

		# make capillary rise params maps
		self.algResults = processing.run("idragratools:IdragraCreateCapriseTable",
					   {'SOURCE_TABLE': sourceTable,
						'SOILID_FLD': 'soilid', 'MAXDEPTH_FLD': 'maxdepth',
						'TXTR_FLD': 'txtr_code', 'DEPTHS': depths,
						'OUT_TABLE': 'TEMPORARY_OUTPUT'},
					   context=None, feedback=self.feedback, is_child_algorithm=False)

		# export capillary rise params maps...
		self.algResults = processing.run("idragratools:IdragraRasterizeMaptable", {
			'TABLE_LAY': self.algResults['OUT_TABLE'],
			'TABLE_FLD': 'soilid', 'VECTOR_LAY': soilMap,
			'VECTOR_FLD': 'extid', 'RASTER_LAY': None,
			'RASTER_EXT': extent,
			'CELL_DIM': cellSize, 'DEST_FOLDER': outPath},
									context=None, feedback=self.feedback, is_child_algorithm=False)

		# HSG MAP
		self.feedback.pushInfo(self.tr('Exporting HSG map'))
		self.feedback.setProgress(70.0)

		self.algResults1 = processing.run("idragratools:IdragraCreatePreHSGTable",
								   {'SOURCE_TABLE': sourceTable,
									'SOILID_FLD': 'soilid', 'MAXDEPTH_FLD': 'maxdepth', 'KSAT_FLD': 'ksat',
									'OUT_TABLE': 'TEMPORARY_OUTPUT'},
									context=None, feedback=self.feedback, is_child_algorithm=False)

		self.algResults2 = processing.run("gdal:rasterize",
									{'INPUT': soilMap, 'FIELD': 'extid', 'BURN': 0,
									 'UNITS': 1, 'WIDTH': cellSize, 'HEIGHT': cellSize,
									 'EXTENT': extent,
									 'NODATA': -9999, 'OPTIONS': '', 'DATA_TYPE': 4, 'INIT': -9999, 'INVERT': False,
									 'EXTRA': '',
									 'OUTPUT': 'TEMPORARY_OUTPUT'},
									context=None, feedback=self.feedback, is_child_algorithm=False
									)

		fileName = os.path.join(outPath, 'hydr_group' + '.asc')
		waterTableFirst = ''
		for var, waterTable in watertableDict.items():
			waterTableFirst = 'GPKG:' + self.simdic['DBFILE']+ ':'+var

			# waterTableFirst = waterTable
			# if waterTableFirst.startswith('.'):
			# 	waterTableFirst = 'GPKG:'+os.path.join(os.path.dirname(self.simdic['DBFILE']), waterTableFirst[2:])

			break

		self.algResults = processing.run("idragratools:IdragraCreateHSGMap", {
									'SOURCE_TABLE': self.algResults1['OUT_TABLE'],
									'SOILID_FLD': 'soilid', 'MAXDEPTH_FLD': 'maxsoildepth', 'MIN_KS50': 'minksat50', 'MIN_KS60': 'minksat60',
									'MIN_KS100': 'minksat100', 'SOIL_MAP': self.algResults2['OUTPUT'],
									'ELEVATION': dtm,
									'WATERTABLE': waterTableFirst, 'OUTPUT': fileName},
									context=None, feedback=self.feedback, is_child_algorithm=False)

		self.feedback.pushInfo(self.tr('Exporting land uses'))
		self.feedback.setProgress(80.0)

		# LANDUSE maps (time)
		# TODO: check if time is always necessary
		landuseMap = DBM.DBName + '|layername=idr_usemap'
		defaultValue = -9999
		if self.simdic['DEFAULT_LU']: defaultValue = self.simdic['DEFAULT_LU']
		processing.run("idragratools:IdragraRasterizeTimeMap",
					   {'VECTOR_LAY': landuseMap, 'DATA_FLD': 'extid',
						'TIME_FLD': 'date', 'NAME_FORMAT': 'soiluse',
						'RASTER_EXT': extent,
						'CELL_DIM': cellSize,
						'INIT_VALUE':defaultValue,
						'YEAR_LIST': ' '.join(yearList),'DEST_FOLDER': outPath},
									context=None, feedback=self.feedback, is_child_algorithm=False)

		# IRRIGATION MAP (time)
		self.feedback.pushInfo(self.tr('Exporting irrigation methods'))
		self.feedback.setProgress(90.0)
		irrMethodsMap = DBM.DBName + '|layername=idr_irrmap'

		defaultValue = -9999
		if self.simdic['DEFAULT_IM']: defaultValue = self.simdic['DEFAULT_IM']

		processing.run("idragratools:IdragraRasterizeTimeMap",
					   {'VECTOR_LAY': irrMethodsMap, 'DATA_FLD': 'extid',
						'TIME_FLD': 'date', 'NAME_FORMAT': 'irr_meth',
						'RASTER_EXT': extent,
						'CELL_DIM': cellSize,
						'INIT_VALUE':defaultValue,
						'YEAR_LIST': ' '.join(yearList), 'DEST_FOLDER': outPath},
									context=None, feedback=self.feedback, is_child_algorithm=False)

		# EXPORT IRRIGATION EFFICIENCY MAP (time)
		# join irrigation methods map with irrigation params
		irrMethodsPars = DBM.DBName + '|layername=idr_irrmet_types'

		# get irrigation efficiency for default method
		parTable = QgsVectorLayer(irrMethodsPars,'irrmethods')
		defaultValue = -9999
		if self.simdic['DEFAULT_IM']:
			req = QgsFeatureRequest().setFilterExpression('"id" = %s'%(self.simdic['DEFAULT_IM']))
			for feat in parTable.getFeatures(req):
				defaultValue = feat['irr_eff']


		algresult = processing.run("qgis:joinattributestable",
								   {'DISCARD_NONMATCHING': True,
									'FIELD': 'extid',
									'FIELDS_TO_COPY': ['irr_eff'],
									'FIELD_2': 'id',
									'INPUT': irrMethodsMap,
									'INPUT_2': irrMethodsPars,
									'METHOD': 1,
									'OUTPUT': 'TEMPORARY_OUTPUT',
									'PREFIX': ''},
								   context=None, feedback=self.feedback, is_child_algorithm=False)

		joinedLay = algresult['OUTPUT']

		# rasterize time maps of irrigation efficiency
		# efficiency is set to zero by default in order to accidentally compute irrigation requirements
		processing.run("idragratools:IdragraRasterizeTimeMap",
					   {'VECTOR_LAY': joinedLay, 'DATA_FLD': 'irr_eff',
						'TIME_FLD': 'date', 'NAME_FORMAT': 'irr_eff',
						'RASTER_EXT': extent,
						'CELL_DIM': cellSize,
						'INIT_VALUE':defaultValue,
						'YEAR_LIST': ' '.join(yearList),'DEST_FOLDER': outPath},
					   context=None, feedback=self.feedback, is_child_algorithm=False)
		# SLOPE MAPS
		self.feedback.pushInfo(self.tr('Exporting slope maps'))
		self.feedback.setProgress(90.0)
		outputSlopeFile = os.path.join(outPath,'slope.asc')
		if dtm:
			self.algResults = processing.run("idragratools:IdragraMakeSlope",
						   {'DTM_LAY': dtm,
							'EXTENT': extent,
							'CELLSIZE': cellSize,
							'LOWER_LIM': self.simdic['MINSLOPE'], 'UPPER_LIM': self.simdic['MAXSLOPE'],
							'OUTSLOPE_LAY': 'TEMPORARY_OUTPUT'},
							context=None, feedback=self.feedback, is_child_algorithm=False)

			processing.run("idragratools:IdragraSaveAscii",
						   {'INPUT':self.algResults['OUTSLOPE_LAY'], 'DIGITS': 6,
							'OUTPUT': outputSlopeFile},
						   context=None, feedback=self.feedback, is_child_algorithm=False)
		else:
			# make a zero raster
			self.feedback.reportError(self.tr('Slope will be set to %s for all the area'%str(self.simdic['MINSLOPE'])), False)
			self.aGrid = GisGrid(progress=self.feedback)
			self.aGrid.openASC(fileName)
			self.aGrid = self.aGrid *0.0+self.simdic['MINSLOPE']
			self.aGrid.saveAsASC(outputSlopeFile, 6, True)

		# WATER TABLE DEPTHS
		nOfWTdepths = 0
		if dtm:
			for var,waterTable in watertableDict.items():
				#if waterTable.startswith('.'):
				#	waterTable = 'GPKG:'+os.path.join(os.path.dirname(self.simdic['DBFILE']), waterTable[2:])

				waterTable = 'GPKG:' + self.simdic['DBFILE'] + ':' + var

				if nOfWTdepths==0:
					# make a general water table for the first year
					self.feedback.pushInfo(self.tr('A base waterdepth map was set for the simulation period'))
					wtdepthName = os.path.join(outPath, 'waterdepth.asc')  # remove month and day
					processing.run("idragratools:IdragraCalcWaterDepth", {'DTM': dtm,
																		  'WATERTABLE': waterTable,
																		  'EXTENT': extent,
																		  'CELLSIZE': cellSize,
																		  'OUTPUT': wtdepthName},
								   context=None, feedback=self.feedback, is_child_algorithm=False
								   )
				nOfWTdepths+=1
				# get year and number of days from the 1st of January
				# FIXED: manage missing year-day
				try:
					year = int(var[11:-4])
					month = int(var[15:-2])
					day = int(var[17:])
					delta =  date(year, month, day) - date(year, 1, 1)
					nOfDays = delta.days+1

					#wtdepthName = os.path.join(outPath,'waterdepth'+var[10:-4]+'.asc') # remove month and day
					wtdepthName = os.path.join(outPath, 'waterdepth' + str(year)+'_'+ str(nOfDays) + '.asc')  # set year and num of days from the beginning
					processing.run("idragratools:IdragraCalcWaterDepth", {'DTM': dtm,
																		  'WATERTABLE': waterTable,
																		  'EXTENT': extent,
																		  'CELLSIZE': cellSize,
																		  'OUTPUT': wtdepthName},
								   context=None, feedback=self.feedback, is_child_algorithm=False
								   )
				except:
					pass

		if nOfWTdepths==0:
			self.feedback.reportError(self.tr('No water depths were processed. DTM or water table maps are missing.'),False)

		# export rice params
		writeParsToTemplate(outfile=os.path.join(outPath, 'rice_soilparam.txt'),
							parsDict={},
							templateName='rice_soilparam.txt')

		# export domain map
		domainFile = os.path.join(outPath, 'domain.asc')
		# make a list of file *.asc in the output path
		fileList = glob.glob(os.path.join(outPath, '*.asc'))
		#feedback.pushInfo(tr('Map List: %s'%fileList))

		processing.run("idragratools:IdragraRasterizeDomain", {
			'INPUT_LIST': fileList,
			'RASTER_EXT': extent,
			'CELL_DIM': cellSize, 'DEST_FILE': domainFile},
						   context=None, feedback=self.feedback, is_child_algorithm=False)

		# export hydrological condition set to 1
		hydrcondFile = os.path.join(outPath, 'hydr_cond.asc')

		processing.run("idragratools:IdragraRasterizeDomain", {
			'INPUT_LIST': [domainFile],
			'RASTER_EXT': extent,
			'CELL_DIM': cellSize, 'DEST_FILE': hydrcondFile},
						   context=None, feedback=self.feedback, is_child_algorithm=False)

		# export cell area map
		cellareaFile = os.path.join(outPath, 'shapearea.asc')
		self.aGrid = GisGrid(progress= self.feedback)
		self.aGrid.openASC(domainFile)
		self.aGrid = self.aGrid*cellSize*cellSize
		self.aGrid.saveAsASC(cellareaFile,6,True)


		# weather weight maps, mandatory after the domain map!
		# TODO: max_num is always 5
		self.feedback.setText(self.tr('Export weight maps'))
		wsLaySource = DBM.DBName + '|layername=idr_weather_stations'
		processing.run("idragratools:IdragraExportWeights",
					   {'VECTOR_LAYER': wsLaySource,
						'ID_FLD':'id',
						'MAX_NUM': 5, 'RASTER_LAY': None,
						'EXTENT': extent,
						'CELLSIZE': cellSize, 'DEST_FOLDER': outPath},
					   context=None, feedback=self.feedback, is_child_algorithm=False
					   )

		# remove unused file xml
		fileList = glob.glob(os.path.join(outPath, '*.xml'))
		for f in fileList:
			os.remove(f)

		# rename file
		# TODO: to be removed
		replaceDict = {'theta_fc1': 'ThetaI_FC',
					   'theta_fc2': 'ThetaII_FC',
					   'theta_r1': 'ThetaI_r',
					   'theta_r2': 'ThetaII_r',
					   'theta_sat1': 'ThetaI_sat',
					   'theta_sat2': 'ThetaII_sat',
					   'theta_wp1': 'ThetaI_WP',
					   'theta_wp2': 'ThetaII_WP',
					   'ksat1': 'Ksat_I',
					   'ksat2': 'Ksat_II',
					   'n1': 'N_I',
					   'n2': 'N_II',
					   'rew1': 'REW_I',
					   'rew2': 'REW_II',
					   'landuse':'soiluse',
					   'irr_eff':'appl_eff'
					   }
		fileList = glob.glob(os.path.join(outPath, '*.asc'))
		for f in fileList:
			for k, v in replaceDict.items():
				newName = f.replace(k, v)
				if newName != f:
					break

			os.rename(f, newName)

		# export control points
		self.feedback.setText(self.tr('Export control points'))
		cellListFile = os.path.join(self.simdic['OUTPUTPATH'], 'cells.txt')
		controlPointMap = DBM.DBName + '|layername=idr_control_points'

		processing.run("idragratools:IdragraExportControlPointsGrid",
					   {'VECTOR_LAY': controlPointMap,
						'RASTER_EXT': extent,
						'CELL_DIM': self.simdic['CELLSIZE'], 'DEST_FILE': cellListFile},
					   context=None, feedback=self.feedback, is_child_algorithm=False)

		self.feedback.setPercentage(100.0)