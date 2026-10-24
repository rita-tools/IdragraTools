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
from qgis._core import QgsProcessingParameterRasterDestination
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
					   NULL, QgsFeature, QgsProcessingOutputRasterLayer, QgsGeometry)

import numpy as np

from datetime import datetime

import os

from ..tools.make_weight_matrix import makeWeightMatrix_WW
from ..tools.import_from_csv import *
from ..tools.compact_dataset import getRasterInfos


class IdragraCreateFieldTable(QgsProcessingAlgorithm):
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

	FIELD_LAY = 'FIELD_LAY'

	LU_LAY = 'LU_LAY'
	LU_COL = 'LU_COL'

	SOIL_LAY = 'SOIL_LAY'
	SOIL_COL = 'SOIL_COL'

	IRRMETH_LAY = 'IRRMETH_LAY'
	IRRMETH_COL = 'IRRMETH_COL'

	IRRUNIT_LAY = 'IRRUNIT_LAY'
	IRRUNIT_COL = 'IRRUNIT_COL'

	WSTAT_LAY = 'WSTAT_LAY'
	WSTAT_COL = 'WSTAT_COL'
	WSTAT_NUM = 'WSTAT_NUM'

	START_YR = 'START_YR'
	END_YR = 'END_YR'

	OUT_LAY = 'OUT_LAY'

	FEEDBACK = None
	

	def tr(self, string):
		"""
		Returns a translatable string with the self.tr() function.
		"""
		return QCoreApplication.translate('Processing', string)

	def createInstance(self):
		return IdragraCreateFieldTable()

	def name(self):
		"""
		Returns the algorithm name, used for identifying the algorithm. This
		string should be fixed for the algorithm, and must not be localised.
		The name should be unique within each provider. Names should contain
		lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCreateFieldTable'

	def displayName(self):
		"""
		Returns the translated algorithm name, which should be used for any
		user-visible display of the algorithm name.
		"""
		return self.tr('Pre field table')

	def group(self):
		"""
		Returns the name of the group this algorithm belongs to. This string
		should be localised.
		"""
		return self.tr('Create')

	def groupId(self):
		"""
		Returns the unique ID of the group this algorithm belongs to. This
		string should be fixed for the algorithm, and must not be localised.
		The group id should be unique within each provider. Group id should
		contain lowercase alphanumeric characters only and no spaces or other
		formatting characters.
		"""
		return 'IdragraCreate'

	def shortHelpString(self):
		"""
		Returns a localised short helper string for the algorithm. This string
		should provide a basic description about what the algorithm does and the
		parameters and outputs associated with it..
		"""
		
		helpStr = """
						The algorithm create a new table with data referred to each field.
						<b>Parameters:</b>
						Fields: the field map [FIELD_LAY]
						Land uses: the soil map [LU_LAY]
						Land use id: the column with the id of the landuse [LU_COL]
						Soils: the soil map [SOIL_LAY]
						Soil id: the column with the id of the soil [SOIL_COL]
						Irrigation methods: the irrigation methods map [IRRMETH_LAY]
						Irr. method id: the column with the id of the irrigation method [IRRMETH_COL]
						Irrigation units: the irrigation unit map [IRRUNIT_LAY]
						Irr. unit id: the column of irrigation unit id [IRRUNIT_COL]
						Weather stations: the map of weather stations as point layer [WSTAT_LAY]
						W. station id: the field with weather station ids [WSTAT_COL]
						Output table: the file path to the output table [OUT_LAY]
						
						<b>Notes</b>
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

		self.addParameter(QgsProcessingParameterFeatureSource(self.FIELD_LAY, self.tr('Fields'),
															  [QgsProcessing.TypeVectorPolygon], None, False))

		self.addParameter(QgsProcessingParameterFeatureSource(self.LU_LAY, self.tr('Land uses'),
															  [QgsProcessing.TypeVectorPolygon], None, False))
		self.addParameter(QgsProcessingParameterField(self.LU_COL, self.tr('Land use id'), 'extid', self.LU_LAY,
													  QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterFeatureSource(self.SOIL_LAY, self.tr('Soils'),
															  [QgsProcessing.TypeVectorPolygon], None, False))
		self.addParameter(QgsProcessingParameterField(self.SOIL_COL, self.tr('Soil id'), 'extid', self.SOIL_LAY,
													  QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterFeatureSource(self.IRRMETH_LAY, self.tr('Irrigation methods'),
															  [QgsProcessing.TypeVectorPolygon], None, False))
		self.addParameter(QgsProcessingParameterField(self.IRRMETH_COL, self.tr('Irr. method id'), 'extid', self.IRRMETH_LAY,
													  QgsProcessingParameterField.Numeric))

		self.addParameter(QgsProcessingParameterFeatureSource(self.IRRUNIT_LAY, self.tr('Irrigation units'),
															  [QgsProcessing.TypeVectorPolygon], None, False))
		self.addParameter(QgsProcessingParameterField(self.IRRUNIT_COL, self.tr('Irr. unit id'), 'extid', self.IRRUNIT_LAY,
													  QgsProcessingParameterField.Numeric))


		self.addParameter(QgsProcessingParameterFeatureSource(self.WSTAT_LAY, self.tr('Weather stations layer'),
															  [QgsProcessing.TypeVectorPoint], None, False))
		self.addParameter(QgsProcessingParameterField(self.WSTAT_COL, self.tr('W. station id'), 'id', self.WSTAT_LAY,
													  QgsProcessingParameterField.Numeric))
		self.addParameter(QgsProcessingParameterNumber(self.WSTAT_NUM, self.tr('Number of station to use'),
													   QgsProcessingParameterNumber.Integer, 5))

		self.addParameter(QgsProcessingParameterNumber(self.START_YR, self.tr('Start year'),
													   QgsProcessingParameterNumber.Integer),0)

		self.addParameter(QgsProcessingParameterNumber(self.END_YR, self.tr('End year'),
													   QgsProcessingParameterNumber.Integer),0)

		self.addParameter(
			QgsProcessingParameterFeatureSink(self.OUT_LAY, self.tr('Output layer'), QgsProcessing.TypeVectorPolygon))

	def processAlgorithm(self, parameters, context, feedback):
		"""
		Here is where the processing itself takes place.
		"""
		self.FEEDBACK = feedback
		# get params
		field_lay = self.parameterAsVectorLayer(parameters, self.FIELD_LAY, context)

		lu_lay = self.parameterAsVectorLayer(parameters, self.LU_LAY, context)
		lu_col = self.parameterAsFields(parameters, self.LU_COL, context)[0]

		soil_lay = self.parameterAsVectorLayer(parameters, self.SOIL_LAY, context)
		soil_col = self.parameterAsFields(parameters, self.SOIL_COL, context)[0]

		irrmeth_lay = self.parameterAsVectorLayer(parameters, self.IRRMETH_LAY, context)
		irrmeth_col = self.parameterAsFields(parameters, self.IRRMETH_COL, context)[0]

		irrunit_lay = self.parameterAsVectorLayer(parameters, self.IRRUNIT_LAY, context)
		irrunit_col = self.parameterAsFields(parameters, self.IRRUNIT_COL, context)[0]

		wstat_lay = self.parameterAsVectorLayer(parameters, self.WSTAT_LAY, context)
		wstat_col = self.parameterAsFields(parameters, self.WSTAT_COL, context)[0]
		wstat_num = self.parameterAsInt(parameters, self.WSTAT_NUM, context)

		start_yr = self.parameterAsInt(parameters, self.START_YR, context)
		end_yr = self.parameterAsInt(parameters, self.END_YR, context)

		year_seq = []
		if ((start_yr <= end_yr) and (start_yr and end_yr)):
			year_seq = list(range(start_yr,end_yr+1))

		# TODO: needs optimization
		# get the list of weather stations
		ws_xs = []
		ws_ys = []
		ws_ids = []
		for feat_ws in wstat_lay.getFeatures():
			pt = feat_ws.geometry().asMultiPoint()[0]
			ws_xs.append(pt.x())
			ws_ys.append(pt.y())
			ws_ids.append(feat_ws[wstat_col])

		#wstat_num = min(len(ws_ids), wstat_num)

		# prepare the destination field
		# WARNING: the order of the fields must match with the order of the attributes inserted
		fldList = field_lay.fields()

		fldList.append(QgsField('x_c', QVariant.Double))
		fldList.append(QgsField('y_c', QVariant.Double))
		fldList.append(QgsField('shape_area', QVariant.Double))
		fldList.append(QgsField('row_count', QVariant.Int))

		fldList.append(QgsField('land_use', QVariant.Int))
		for yr in year_seq:
			temp_name = 'land_use_%s' % yr
			if temp_name not in fldList: fldList.append(QgsField('land_use_%s' % yr, QVariant.Int))

		fldList.append(QgsField('soil_id', QVariant.Int))
		#fldList.append(QgsField('soil_gidx', QVariant.Double))

		fldList.append(QgsField('irrmeth_id', QVariant.Int))
		#fldList.append(QgsField('irrmeth_gidx', QVariant.Double))

		for yr in year_seq:
			temp_name = 'irrmeth_id_%s' % yr
			if temp_name not in fldList: fldList.append(QgsField('irrmeth_id_%s'%yr, QVariant.Int))

		fldList.append(QgsField('irrunit_id', QVariant.Int))
		# fldList.append(QgsField('irrunit_gidx', QVariant.Double))

		# add meteo fields
		for n in range(wstat_num):
			fldList.append(QgsField('meteo_%s'%(n+1), QVariant.Double))

		(sink, dest_id) = self.parameterAsSink(
			parameters,
			self.OUT_LAY,
			context,
			fldList,
			field_lay.wkbType(),
			field_lay.sourceCrs()
		)

		# get value from source table
		c = 0
		nFeat = field_lay.featureCount()
		for feat in field_lay.getFeatures():
			c+=1
			self.FEEDBACK.setProgress(100.0 * c / nFeat)

			# get geometry and geometry data
			id = feat['id']
			geom = feat.geometry()
			try:
				shape_area = feat['area_m2']
			except:
				shape_area = float(geom.area())

			#c_geom = geom.centroid()
			c_geom = geom.pointOnSurface()
			x_c = c_geom.asPoint().x()
			y_c = c_geom.asPoint().y()

			# get id from other maps (maximum covered area)
			lu_id, lu_gidx = self.selectByLocation(inputLayer=lu_lay, refGeom=c_geom, inputFld=lu_col)
			if not lu_id: lu_id = -9999

			lu_id_list = [lu_id]
			for yr in year_seq:
				lu_id_year, lu_gidx_year = self.selectByLocation(inputLayer=lu_lay, refGeom=c_geom, inputFld=lu_col,
																 filter_string=' year("date")=%s '%yr)
				if not lu_id_year: lu_id_year = lu_id
				lu_id_list.append(lu_id_year)

			soil_id, soil_gidx = self.selectByLocation(inputLayer=soil_lay, refGeom=c_geom, inputFld=soil_col)

			irrmeth_id, irrmeth_gidx = self.selectByLocation(inputLayer=irrmeth_lay, refGeom=c_geom, inputFld=irrmeth_col)
			if not irrmeth_id: irrmeth_id = -9999

			irrmeth_list = [irrmeth_id]
			for yr in year_seq:
				irrmeth_id_year, irrmeth_gidx_year = self.selectByLocation(inputLayer=irrmeth_lay, refGeom=c_geom, inputFld=irrmeth_col,
															 filter_string=' year("date")=%s '%yr)
				if not irrmeth_id_year: irrmeth_id_year = irrmeth_id
				irrmeth_list.append(irrmeth_id_year)

			irrunit_id, irrunit_gidx = self.selectByLocation(inputLayer=irrunit_lay, refGeom=c_geom, inputFld=irrunit_col)

			# calculate weather weights matrix
			ws_ww = makeWeightMatrix_WW(xmin=None, xmax=None, ymin=None, ymax=None, cellsize=None,
								xList =ws_xs, yList=ws_ys, idList=ws_ids, nMax=wstat_num,
								xc_list=[x_c], yc_list=[y_c],
								feedback=self.FEEDBACK, tr=None)

			attr_list =feat.attributes()+\
					   [x_c,y_c,shape_area,c]+\
						lu_id_list+\
						[soil_id]+\
						irrmeth_list+\
						[irrunit_id]

			for x in ws_ww:
				if np.isnan(x[0]): x_val = -9999.0
				else: x_val = float(x[0])

				attr_list.append(x_val)

			#print('attr_list',attr_list)

			new_feat = QgsFeature(fldList)
			new_feat.setGeometry(geom)
			new_feat.setAttributes(attr_list)

			sink.addFeature(new_feat, QgsFeatureSink.FastInsert)

		return {self.OUT_LAY: dest_id}

	def calcGeomIndex(self, aGeom, refGeom, refArea, refLen):
		xGeom = refGeom.intersection(aGeom)
		geomIndex = 0.0
		try:
			xArea = xGeom.area()
			xLen = xGeom.length()
			if refArea > 0:
				geomIndex = round(100 * xArea / refArea, 2)  # it's a polygon
			elif refLen > 0:
				geomIndex = round(100 * xLen / refLen, 2)  # it's a line
			else:
				geomIndex = 100.0  # it's a point
		except Exception as e:
			print('Error in calcGeomIndex, %s' % str(e))

		return geomIndex


	def selectByLocation(self, inputLayer, refGeom, inputFld,filter_string = ''):

		# set a filter
		refArea = refGeom.area()
		refLen = 0  # unused
		max_gidx = 0
		target_id = None
		if filter_string:
			req = QgsFeatureRequest().setFilterRect(refGeom.boundingBox()).setFilterExpression(filter_string)
		else:
			req = QgsFeatureRequest().setFilterRect(refGeom.boundingBox())

		for feature in inputLayer.getFeatures(req):
			aGeom = feature.geometry()
			geomIndex = self.calcGeomIndex(aGeom, refGeom, refArea, refLen)
			if geomIndex > max_gidx:
				max_gidx = geomIndex
				#print('inputFld', inputFld)
				target_id = feature[inputFld]

		return target_id, max_gidx
