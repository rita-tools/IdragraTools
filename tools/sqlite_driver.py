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
import numpy as np
import sqlite3 as sqlite
import io
from datetime import datetime,date
import pandas as pd

from qgis.core import QgsFeatureRequest
from qgis.core import QgsVectorLayer, QgsField, QgsVectorFileWriter, QgsCoordinateTransformContext
from qgis.PyQt.QtCore import QVariant, QObject


def adapt_array(arr):
	"""
	http://stackoverflow.com/a/31312102/190597 (SoulNibbler)
	"""
	out = io.BytesIO()
	np.save(out, arr)
	out.seek(0)
	return sqlite.Binary(out.read())

def convert_array(text):
	out = io.BytesIO(text)
	out.seek(0)
	return np.load(out)

def null_date_converter(value):
	"""
	https://github.com/mkleehammer/pyodbc/issues/475
	"""
	try:
		# test if it is a valid date string
		valueStr = value.decode('utf-8')
		valueStr = datetime.strptime(valueStr, "%Y-%m-%d").date().strftime("%Y-%m-%d")
	except:
		valueStr = 'NULL'

	return valueStr


# Converts np.array to TEXT when inserting
sqlite.register_adapter(np.ndarray, adapt_array)

# Converts TEXT to np.array when selecting
sqlite.register_converter("ARRAY", convert_array)
sqlite.register_converter("DATE", null_date_converter)

class MyProgress():
	
	def __init__(self):
		pass
		
	def setInfo(self, txt, isError):
		print('info: %s'%txt)

	def pushInfo(self, txt):
		print('info: %s'%txt)

	def reportError(self, txt, isBlocking):
		if isBlocking: print('blocking error: %s'%txt)
		else: print('error: %s'%txt)


class SQLiteDriver(QObject):
	
	def __init__(self, filename, overwrite = True, crs = None, progress = None,tr = None, parent = None):
		QObject.__init__(self, parent)
		self.conn = None
		self.cur = None
		self.DBName = filename
		#print('in sqlDriver',filename)
		if progress is None:
			self.progress = MyProgress()
		else:
			self.progress = progress

		if tr is None: self.tr = lambda x: x
		else: self.tr = tr
		
		# create a new file if necessary
		try:
			if not os.path.exists(filename):
				# create a new file if necessary
				self.initTables(filename,crs)
			else:
				if overwrite:
					os.remove(filename)
					self.initTables(filename,crs)
				else:
					# do nothing, simply store the name of the file
					pass
		except Exception as e:
			self.progress.setInfo(str(e),True)

		try:
			self.resetCounter()
		except Exception as e:
			self.progress.reportError('Unable to reset counter in %s (%s)'%(filename,str(e)), False)

	def resetCounter(self):
		sql = "UPDATE 'sqlite_sequence' SET 'seq' = 0;"
		msg = self.executeSQL(sql)
		if msg: self.progress(self.tr('SQL error at %s: %s') %(sql,msg),True)

	def initTables(self,gpkgPath,crs = None):
		
		STdefList = [{'type':'MultiPoint',
							'name':'idr_weather_stations',
							'fldNames':['id','name','lat','alt'],
							'fldTypes':[QVariant.Int,QVariant.String,QVariant.Double,QVariant.Double]},
						{'type':'MultiPoint',
							'name':'idr_gw_wells',
							'fldNames':['id','name','alt','type'],
							'fldTypes':[QVariant.Int,QVariant.String,QVariant.Double,QVariant.Int]},
					 {'type': 'MultiPoint',
					  'name': 'idr_control_points',
					  'fldNames': ['id','name', 'descr'],
					  'fldTypes': [QVariant.Int, QVariant.String, QVariant.String]},
						{'type':'MultiLinestring',
							'name':'idr_links',
							'fldNames':['id','name','inlet_node','outlet_node','flow_rate','inf_losses'],
							'fldTypes':[QVariant.Int,QVariant.String,QVariant.Int,QVariant.Int,QVariant.Double,QVariant.Double]},
						{'type':'MultiPoint',
							'name':'idr_nodes',
							'fldNames':['id','name','node_type','q_sum','q_win','sum_start','sum_end','win_start','win_end','act_trshold','act_ratio'],
							'fldTypes':[QVariant.Int,QVariant.String,QVariant.Int,QVariant.Double,QVariant.Double,QVariant.Int,QVariant.Int,QVariant.Int,QVariant.Int,QVariant.String,QVariant.String]},
						{'type': 'MultiPolygon',
							'name': 'idr_soilmap',
							'fldNames': ['id','name','extid','date'],
							'fldTypes': [QVariant.Int, QVariant.String, QVariant.Int, QVariant.Date]},
						{'type': 'MultiPolygon',
							'name': 'idr_usemap',
							'fldNames': ['id','name','extid', 'date'],
							'fldTypes': [QVariant.Int, QVariant.String, QVariant.Int, QVariant.Date]},
						{'type': 'MultiPolygon',
							'name': 'idr_irrmap',
							'fldNames': ['id','name','extid', 'date'],
							'fldTypes': [QVariant.Int, QVariant.String,QVariant.Int, QVariant.Date]},
						{'type': 'MultiPolygon',
							'name': 'idr_distrmap',
							'fldNames': ['id', 'name','inlet_node','outlet_node','distr_eff','expl_factor','wat_shift'],
							'fldTypes': [QVariant.Int,QVariant.String,QVariant.Int,QVariant.Int,QVariant.Double,QVariant.Int,QVariant.Int]},
						{'type': 'MultiPolygon',
							'name': 'idr_domainmap',
							'fldNames': ['id', 'name','area_m2'],
							'fldTypes': [QVariant.Int, QVariant.String, QVariant.Double]}
					 ]
		
		firstt = True
		options = QgsVectorFileWriter.SaveVectorOptions() 
		
		for STdef in STdefList:
			self.progress.pushInfo(self.tr('Processing %s'%STdef['name']))
			lyr =  QgsVectorLayer(STdef['type'], STdef['name'], "memory")
			if crs: lyr.setCrs(crs)
			
			pr = lyr.dataProvider()
			attrList = []
			for n, t in zip(STdef['fldNames'], STdef['fldTypes']):
				newField = QgsField(n,t)
				# if n == 'id':
				# 	cons = newField.constraints()
				# 	cons.setConstraint (QgsFieldConstraints.ConstraintUnique, QgsFieldConstraints.ConstraintOriginLayer)
				# 	newField.setConstraints(cons)

				attrList.append(newField)
				
			pr.addAttributes(attrList)
			lyr.updateFields()
			if firstt :            
				firstt = False
			else :
				options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer 
				options.EditionCapability = QgsVectorFileWriter.CanAddNewLayer 
				
			options.layerName = lyr.name()

			#print('in init table',gpkgPath)
			#_writer = QgsVectorFileWriter.writeAsVectorFormat(lyr, gpkgPath, options ) # deprecated
			_writer = QgsVectorFileWriter.writeAsVectorFormatV2(lyr, gpkgPath, QgsCoordinateTransformContext(), options)

			#print(options.layerName,_writer)

		# replace id field with constrained by sql command
		# for STdef in STdefList:
		# 	for n, t in zip(STdef['fldNames'], STdef['fldTypes']):
		# 		if n == 'id':
		# 			sql = """
		# 				ALTER TABLE %s ADD id INTEGER UNIQUE NOT NULL;
		# 				"""%(STdef['name'])
		# 			self.executeSQL(sql)
						
		# add simple tables trough simple sql commands
		
		initTableSQL =	"""
								-- a table to store crop combinations
								DROP TABLE IF EXISTS idr_crop_sequences;CREATE TABLE idr_crop_sequence (timestamp text,wsid integer, recval double);
								DROP TABLE IF EXISTS idr_soiluses;CREATE TABLE idr_soiluses (
																fid INTEGER PRIMARY KEY NOT NULL,
																id INTEGER,
																name text NOT NULL,
																descr text,
																croplist text);
								
								DROP TABLE IF EXISTS  ws_tmax;CREATE TABLE ws_tmax (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text,wsid integer, recval double);
								DROP TABLE IF EXISTS  ws_tmin;CREATE TABLE ws_tmin (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								DROP TABLE IF EXISTS  ws_ptot;CREATE TABLE ws_ptot (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								DROP TABLE IF EXISTS  ws_humax;CREATE TABLE ws_umax (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								DROP TABLE IF EXISTS  ws_humin;CREATE TABLE ws_umin (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								DROP TABLE IF EXISTS  ws_vave;CREATE TABLE ws_vmed (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								DROP TABLE IF EXISTS  ws_rgcorr;CREATE TABLE ws_rgcorr (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								DROP TABLE IF EXISTS  ws_co2;CREATE TABLE ws_co2 (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								
								-- a table to compute required water volume from field
								DROP TABLE IF EXISTS  node_disc;CREATE TABLE node_disc (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								-- store discharge to use in consumption mode
								DROP TABLE IF EXISTS  node_act_disc;CREATE TABLE node_act_disc (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								
								DROP TABLE IF EXISTS  well_watertable;CREATE TABLE well_watertable (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,timestamp text, wsid integer, recval double );
								
								DROP TABLE IF EXISTS  idr_soil_types;
								CREATE TABLE idr_soil_types (
																fid INTEGER PRIMARY KEY NOT NULL,
																id INTEGER NOT NULL UNIQUE,
																name text NOT NULL UNIQUE,
																descr text
																);
								
								DROP TABLE IF EXISTS  idr_soil_profiles;
								CREATE TABLE idr_soil_profiles (
																fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
																soilid integer,
																maxdepth double,
																ksat double,
																theta_fc double,
																theta_wp double,
																theta_r double,
																theta_sat double,
																txtr_code integer
																);
																
								
								
								DROP TABLE IF EXISTS  idr_crop_types;
								CREATE TABLE idr_crop_types (
																fid INTEGER PRIMARY KEY NOT NULL,
																id INTEGER NOT NULL UNIQUE,
																name text NOT NULL UNIQUE,
																sowingdate_min integer,
																sowingdelay_max integer,
																harvestdate_max integer,
																harvnum_max integer,
																cropsoverlap integer,
																tsowing double,
																tdaybase double,
																tcutoff double,
																vern integer,
																tv_min double,
																tv_max double,
																vfmin double,
																vstart integer,
																vend integer,
																vslope double,
																ph_r integer,
																daylength_if integer,
																daylength_ins integer,
																wp double,
																fsink double,
																tcrit_hs double,
																tlim_hs double,
																hi double,
																kyT double,
																ky1 double,
																ky2 double,
																ky3 double,
																ky4 double,
																praw double,
																ainterception double,
																cl_cn integer,
																irrigation integer,
																gdd text,
																kcb text,
																lai text,
																hc text,
																sr text,
																adv_opts text
																);
					
								DROP TABLE IF EXISTS  idr_irrmet_types;
								CREATE TABLE idr_irrmet_types (
																fid INTEGER PRIMARY KEY NOT NULL,
																id INTEGER NOT NULL UNIQUE,
																name text NOT NULL UNIQUE,
																qadaq double,
																k_stress double,
																k_stresswells double,
																fw double,
																min_a double,
																max_a double,
																min_b double,
																max_b double,
																losses_a double,
																losses_b double,
																losses_c double,
																f_interception integer,
																irr_time text,
																irr_fraction text,
																irr_eff double,
																adv_opts text
																);
							"""
		self.executeSQL(initTableSQL)
		
		self.initStepResults()

		#self.initControlPointResults() # results query at runtime is preferred
		
	def initStepResults(self):
		# step results refere to idragra spatial output
		sql = """
				DROP TABLE IF EXISTS  stp_caprise; CREATE TABLE stp_caprise (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_et_act; CREATE TABLE stp_et_act (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_et_pot; CREATE TABLE stp_et_pot (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_flux2; CREATE TABLE stp_flux2 (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_irr; CREATE TABLE stp_irr (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_irr_distr; CREATE TABLE stp_irr_distr (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_irr_loss; CREATE TABLE stp_irr_loss (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_irr_privw; CREATE TABLE stp_irr_privw (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_prec; CREATE TABLE stp_prec (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_runoff; CREATE TABLE stp_runoff (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_trasp_act; CREATE TABLE stp_trasp_act (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  stp_trasp_pot; CREATE TABLE stp_trasp_pot (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
		"""
		self.executeSQL(sql)

	def initControlPointResults(self):
		# step results refere to idragra spatial output
		sql = """
				DROP TABLE IF EXISTS  cp_rain_mm; CREATE TABLE cp_rain_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_Tmax; CREATE TABLE cp_Tmax (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_Tmin; CREATE TABLE cp_Tmin (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_et0; CREATE TABLE cp_et0 (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_kcb; CREATE TABLE cp_kcb (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_lai; CREATE TABLE cp_lai (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_pday; CREATE TABLE cp_pday (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_irrig_mm; CREATE TABLE cp_irrig_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_peff_mm; CREATE TABLE cp_peff_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_h2o_dispL_mm; CREATE TABLE cp_h2o_dispL_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_h2o_disp_mm; CREATE TABLE cp_h2o_disp_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_interception_mm; CREATE TABLE cp_interception_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_runoff_mm; CREATE TABLE cp_runoff_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_infiltration_mm; CREATE TABLE cp_infiltration_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_eva_pot_mm; CREATE TABLE cp_eva_pot_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_eva_mm; CREATE TABLE cp_eva_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_perc1_mm; CREATE TABLE cp_perc1_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_theta1_mm; CREATE TABLE cp_theta1_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_ponding_mm; CREATE TABLE cp_ponding_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_trasp_pot_mm; CREATE TABLE cp_trasp_pot_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_trasp_act_mm; CREATE TABLE cp_trasp_act_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_ks; CREATE TABLE cp_ks (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_thickness_II_m; CREATE TABLE cp_thickness_II_m (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_wat_table_depth_under_root_m; CREATE TABLE cp_wat_table_depth_under_root_m (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_capflux_mm; CREATE TABLE cp_capflux_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_perc2_mm; CREATE TABLE cp_perc2_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_theta2_mm; CREATE TABLE cp_theta2_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_theta_old_mm; CREATE TABLE cp_theta_old_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_rawbig; CREATE TABLE cp_rawbig (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_rawinf; CREATE TABLE cp_rawinf (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_wat_table_depth_m; CREATE TABLE cp_wat_table_depth_m (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_distr_irr_mm; CREATE TABLE cp_distr_irr_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_priv_well_irr_mm; CREATE TABLE cp_priv_well_irr_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_espperc1; CREATE TABLE cp_espperc1 (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_espperc2; CREATE TABLE cp_espperc2 (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
				DROP TABLE IF EXISTS  cp_irr_loss_mm; CREATE TABLE cp_irr_loss_mm (fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, timestamp text,wsid integer,recval double);
		"""
		self.executeSQL(sql)
		
		
	def createSettingsTable(self, commonCrs):
		initTableSQL =	"""
		CREATE TABLE geometry_columns (
															f_table_name TEXT, 
															f_geometry_column TEXT, 
															geometry_type INTEGER, 
															coord_dimension INTEGER, 
															srid INTEGER,
															geometry_format TEXT );
		
		CREATE TABLE spatial_ref_sys (
														srid INTEGER UNIQUE,
														auth_name TEXT,
														auth_srid INTEGER,
														srtext TEXT  );
		"""
		crsSQL = """
		INSERT INTO spatial_ref_sys (srid, auth_name , auth_srid, srtext)
		VALUES  (1, '%s', '%s', '%s' );
		""" %(commonCrs.description(), commonCrs.authid(), commonCrs.toWkt())
		sql = initTableSQL+'\n'+crsSQL
		self.executeSQL(sql)
		
	def startConnection(self):
		# start connection
		self.conn = sqlite.connect(self.DBName,detect_types=sqlite.PARSE_DECLTYPES)
		self.conn.enable_load_extension(True)
		self.conn.execute('SELECT load_extension("mod_spatialite")')
		# creating a Cursor
		self.cur = self.conn.cursor()
		
	def stopConnection(self):
		# run VACUUM to reduce the size
		self.conn.rollback()
		#self.cur.execute('VACUUM')
		self.conn.close()
	
	def executeSQL(self,sql,data=None):
		msg=''
		try:
			self.startConnection()
			#self.cur.execute('SELECT load_extension("mod_spatialite");')
			if data:
				self.cur.executemany(sql,data)
				self.conn.commit()
			else:
				self.cur.executescript(sql)
		except Exception as e:
			msg = str(e)
			self.progress.reportError(self.tr('SQL error at %s: %s \nwith data%s') %(sql,msg,str(data)),True)
		finally:
			self.stopConnection()
			
		return msg

	def getTableAsDF(self,sql):
		df = None
		try:
			self.startConnection()
			df = pd.read_sql_query(sql, self.conn)
		except Exception as e:
			msg = str(e)
			self.progress.reportError(self.tr('SQL error at %s: %s') %(sql,msg),True)
		finally:
			self.stopConnection()

		return df

	def popTableFromDF(self,df,tableName):
		res = 0

		try:
			self.startConnection()
			df.to_sql(tableName,self.conn,if_exists='append', index = True, index_label = 'fid')
			res=1
		except Exception as e:
			msg = str(e)
			self.progress.reportError(self.tr('Unable to import table %s because %s') %(tableName,msg),True)
		finally:
			self.stopConnection()

		return res

	def getTableAsLayer(self,name,displayName = None):
		if displayName is None: displayName = name
		# something like 'D:\\test_smartgreen\\aaaa_DATA\\tables.sqlite|layername=landuses'
		uri = '%s|layername=%s'%(self.DBName,name)
		table = None
		try:
			table = QgsVectorLayer(uri, displayName, 'ogr')
		except:
			print('Errore di collegamneto')

		return table
		
	def getTableSource(self,name):
		uri = '%s|layername=%s'%(self.DBName,name)
		return uri

	def parseValues(self, attrs):
		for i,a in enumerate(attrs):
			if type(a) =='unicode':
				a = a.encode('utf-8')

			a = '%s'%a
			a = a.replace("'","''")
			attrs[i] = a
		
		return attrs
		
	def joinRecord(self, data, digit = 3):
		data = [str(round(d,digit)) for d in data.tolist()]
		joinedData = "', '".join(data)
		joinedData = "('"+ joinedData +"')"
		return joinedData
		
	def importNumpyArray(self, name, columnNames, columnTypes, values, overwrite=True):
		from numpy import apply_along_axis
		#name = name.encode('utf-8')
		name = "'%s'"%name
		numCols = len(columnNames)
		fields = ', '.join(columnNames)
		fields_types = ["{} {}".format(f, t) for f, t in zip(columnNames, columnTypes)]
		fields_types = ', '.join(fields_types)
		concatValues = []
		nrows,ncols = values.shape
		for r in range(0,nrows):
			concatValues.append(self.joinRecord(values[r,:]))
		
		#concatValues = apply_along_axis(self.joinRecord, axis=1, arr=values)
		concatValues = ', '.join(concatValues)
		
		sql = 'BEGIN; '
		# DROP TABLE IF EXISTS  is exist
		if overwrite: sql += 'DROP TABLE IF EXISTS  IF EXISTS %s; ' %(name)
		# create table
		sql += 'CREATE TABLE %s (%s); ' %(name,fields_types)
		# populate table
		sql += 'INSERT INTO %s (%s) VALUES %s; ' %(name,fields,concatValues)
		sql += 'COMMIT;'
		
		try:
			self.startConnection()
			self.cur.executescript(sql)
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
			
	def OLDimportDataFromCSV(self, filename, tablename, timeFldIdx, valueFldIdx, sensorId, skip,timeFormat,column_sep):
		concatValues = []
		# oper CSV file
		in_file = open(filename,"r")
		i = 0
		while 1:
			in_line = in_file.readline()
			if i>=skip:
				if len(in_line) == 0:
					break
				
				# process the line
				in_line = in_line[:-1]
				#print 'LN %d: %s'%(i,in_line)
				data = in_line.split(column_sep)
				timestamp = datetime.strptime(data[timeFldIdx], timeFormat)
				value = float(data[valueFldIdx])
				
				concatValues.append("('"+ timestamp.strftime('%Y-%m-%d')+"', '"+str(sensorId)+"', '"+str(value)+"')")
			
			i+=1
		
		concatValues = ', '.join(concatValues)
		# save to table
		sql = 'BEGIN; '
		sql += 'REPLACE INTO "%s" (%s) VALUES %s; ' %(tablename,'timestamp,wsname,value',concatValues)
		sql += 'COMMIT;'
		
		try:
			self.startConnection()
			self.cur.executescript(sql)
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()

		

	def importCSV(self,filename,name, columnTypes = [], column_sep = ";", overwrite = True):
		columnNames = []
		#columnTypes = []
		concatValues = []
		# oper CSV file
		in_file = open(filename,"r")
		i = 0
		while 1:
			in_line = in_file.readline()
			if len(in_line) == 0:
				break
			
			if in_line[0] == '#':
				i = 0 # make valid line counter to zero
				pass # skip comments
			else:
				# process the line
				in_line = in_line[:-1]
				#print 'LN %d: %s'%(i,in_line)
				values = in_line.split(column_sep)
				if i == 0:
					# first is column name
					#print values
					columnNames = self.parseValues(values)
				else:
					# try to guess value types
					if len(columnTypes)!=len(columnNames):
						for val in values:
							try:
								toNumber = float(val)
								columnTypes.append('REAL')
							except:
								columnTypes.append('TEXT')
					
					concatValues.append("('"+ "', '".join(self.parseValues(values))+"')")
					
				i+=1
		
		fields = ', '.join(columnNames)
		fields_types = ["{} {}".format(f, t) for f, t in zip(columnNames, columnTypes)]
		fields_types = ', '.join(fields_types)
		concatValues = ', '.join(concatValues)
		
		name = name.encode('utf-8')
		
		sql = 'BEGIN; '
		# DROP TABLE IF EXISTS  is exist
		if overwrite: sql += 'DROP TABLE IF EXISTS  IF EXISTS "%s"; ' %(name)
		# create table
		sql += 'CREATE TABLE "%s" (%s); ' %(name,fields_types)
		# populate table
		sql += 'INSERT INTO "%s" (%s) VALUES %s; ' %(name,fields,concatValues)
		sql += 'COMMIT;'
		
		try:
			self.startConnection()
			self.cur.executescript(sql)
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
			
		
	def getTableFromLayer(self,layer):
		# dbname='D:/test_smartgreen\\aaaa_DATA.sqlite' table="soils" (geom) sql=
		marker = 'table="'
		source = layer.source()
		idx = source.index(marker)+len(marker)
		source = source[idx:]
		# get firt accourence of "
		idx = source.index('" ')
		source = source[:idx]
		return source
		
	def getNameFromLayer(self,layer):
		# D:/test_smartgreen\aaaa_DATA.sqlite|layername=nodes
		marker = '|layername='
		source = layer.source()
		#print 'source:',source
		#source = source.replace('\\','/')
		idx = source.index(marker)+len(marker)
		source = source[idx:]
		# get firt accourence of "
		#~ idx = source.index('" ')
		#~ source = source[:idx]
		return source
		
	def getTableFields(self, tablename):
		try:
			self.startConnection()
			sql = """PRAGMA table_info("%s")"""%(tablename)
			res = self.cur.execute(sql)
			data = self.cur.fetchall()
			names = ''
			for d in data:
				names = names+', '+d[1]
				
			# remove first 2 characters
			names = names[2:]
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
			names= ''
		finally:
			self.stopConnection()
			return names
			
	def getFieldsList(self, tablename):
		names = []
		try:
			self.startConnection()
			sql = """PRAGMA table_info("%s")"""%(tablename)
			res = self.cur.execute(sql)
			data = self.cur.fetchall()
			
			for d in data:
				names.append(d[1])
				
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
			names= []
		finally:
			self.stopConnection()
			return names
			
	def getTablesList(self):
		try:
			self.startConnection()
			sql = """SELECT name FROM sqlite_master WHERE type='table';"""
			res = self.cur.execute(sql)
			data = self.cur.fetchall()
			names = []
			for d in data:
				names.append(d[0])
				
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
			names= []
		finally:
			self.stopConnection()
			return names
			
	def removeTable(self, tablename):
		try:
			self.startConnection()
			sql = """DROP TABLE IF EXISTS  IF EXISTS '%s'""" %(tablename)
			res = self.cur.execute(sql)
			data = self.cur.fetchall()
			names = data
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
			names= ''
		finally:
			self.stopConnection()
			return names
			
	def deleteRow(self,tableName,wCond):
		try:
			self.startConnection()
			sql = """DELETE FROM %s WHERE %s""" %(tableName,wCond)
			res = self.cur.execute(sql)
			self.conn.commit() #!!!!!
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
	def addVectorTable(self,name, fieldList, typeList, vectorType):
		# add default fields
		fieldList = ['ogc_fid','GEOMETRY'] + fieldList
		typeList = ['INTEGER','BLOB'] + typeList
		fieldDefinition = ["'{}' {}".format(f, t) for f, t in zip(fieldList, typeList)]
		fieldDefinition = ', '.join(fieldDefinition)
		createVectorSQL = "CREATE TABLE '%s' (%s);" %(name,fieldDefinition)
		# update geometry columns
		updateSQL = """INSERT INTO geometry_columns (f_table_name, f_geometry_column , geometry_type, coord_dimension, srid, geometry_format)
								VALUES  ('%s', 'GEOMETRY', %s, 2, 1, 'WKB' );""" %(name,vectorType)
		sql = createVectorSQL+'\n'+updateSQL
		self.executeSQL(sql)
		
	def getDataFromTable(self,tableName,fieldList = ['*'],filter = None):
		fieldStr = ', '.join(fieldList)
		getDataSQL = "SELECT %s FROM '%s'" %(fieldStr,tableName)
		if filter is not None:
			getDataSQL+= ' WHERE '+str(filter)
		
		# run the query
		rows = None
		try:
			self.startConnection()
			res = self.cur.execute(getDataSQL)
			rows = self.cur.fetchall()
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),getDataSQL),True)
		finally:
			self.stopConnection()
		
		return rows
		
		
	def importFromLayer(self,fromLayer, toLayer, importData, settings, idList = []):
		"""
		Import geometry and attributes from a 'from layer' to a 'to layer'.
		Attributes are imported according to the conversion rules stored in settings
		"""
		
		toLayerType = toLayer.wkbType()
		fromLayerType = fromLayer.wkbType()
		
		#~ print 'importData:',importData
		
		if 	fromLayer.selectedFeatureCount()>0:
			# use current selection
			#print 'num. of selected features:',fromLayer.selectedFeatureCount()
			selection = fromLayer.selectedFeatures()
		else:
			# try with a list of ids provided by the user
			request = QgsFeatureRequest().setFilterFids(idList)
			selection = fromLayer.getFeatures(request)
			
		# something like: "crs":{"type":"name","properties":{"name":"EPSG:4326"}}
		vcrsAuthid = '"crs":{"type":"name","properties":{"name":"%s"}}' %(fromLayer.crs().authid())

		toTablename = self.getNameFromLayer(toLayer)
		
		# changes are only possible when editing the layer
		sql = 'INSERT INTO "%s" ' %(toTablename)
		fields = self.getTableFields(toTablename)
		toks = fields.split(', ')
		nFields = len(toks)
		#nFields = len(fromFldList)
		
		#sql += '(%s) ' %(fields)
		sql += '("%s") ' %('", "'.join(toks))
		
		sql += ' VALUES (%s)' %(', '.join(['?']*nFields))
		
		attrList = []
		for selectedFeat in selection:
			# get attribute value and transform it if necessary
			featAttr= (None,)
			# add the geometry blob
			geom = selectedFeat.geometry() # get geometry
			# Match geometry type
			if ((toLayerType == QGis.WKBMultiPoint) or (toLayerType == QGis.WKBPoint)) and ((fromLayerType != QGis.WKBMultiPoint) or (fromLayerType != QGis.WKBPoint)):
				# force centroid extraction
				geom = geom.centroid() #.asPoint()
			
			flag = geom.convertToMultiType() # cast geometry to multipart
			geomWKB = geom.asWkb() # export in well known binary format
			featAttr += (buffer(geomWKB),)
			
			toFldVars = importData.keys()
			#print 'toFldVars:',toFldVars
			for i,toFldVar in enumerate(toFldVars):
				fromField,unit = importData[toFldVar]
				# get attribute value
				idx = fromLayer.fieldNameIndex(fromField)
				
				value = None
				if idx>-1:
					value = selectedFeat.attributes()[idx]
					#print 'value type',type(value)
					if type(value) == QPyNullVariant:
						value = None
					else:
						# check if type of value is the same of the destination field
						toFldIdx = toLayer.fieldNameIndex(settings.getDefault(toFldVar))
						toFld = toLayer.fields().field(toFldIdx)
						if toFld>-1:
							#print fld.name(),fld.type()
							#print toFld.name(),'-',toFld.type(),'-',toFld.typeName()
							if (toFld.typeName() == 'String'):
								if not isinstance(value, (str, unicode)):
									value = '{0:g}'.format(value)
						
				#print  fromField, '- (',unit,') -->',settings[toFldVar][0],value,idx
				
				if unit == 'm':
					unit = 1.0
				elif unit == 'cm':
					unit = 0.01
				elif unit == 'mm':
					unit = 0.001
				else:
					unit = None
				
				if (unit is not None) and (value is not None) and not isinstance(value, (str, unicode)): value = value * unit
				
				#~ if toFldVar in settings:
					#~ toField = settings[toFldVar][0]
				#~ else:
					#~ toField = toFldList[i]
				
				# add the source layer to message
				#print 'fromField:',fromField
				if toFldVar == 'qgis.networklayer.field.msg':
					if (value is None) or (value == ''):
						value='4(%s)'%fromLayer.name()
					else:
						value+=', 4(%s)'%fromLayer.name()
				
				featAttr+=(value,)
			
			
			# append featAttr to attrList
			attrList.append(featAttr)
			#attrList = list(featAttr)
			#attrList[0] = 1
		
		#print sql
		try:
			self.startConnection()
			#self.cur.executemany(sql, attrList)
			self.cur.executemany(sql, attrList)
			self.conn.commit()
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
			
		# update layer's extent when new features have been added
		# because change of extent in provider is not propagated to the layer
		toLayer.updateExtents()
		toLayer.triggerRepaint()
		
	def importFromDB(self,fromDB,tableName):
		try:
			self.startConnection()
			sql = "ATTACH DATABASE '%s' AS other; INSERT INTO %s SELECT * FROM %s;"%(fromDB,tableName,'other'+'.'+tableName)
			self.progress.setInfo('SQL: %s' %(sql),False)
			self.cur.executescript(sql)
			self.conn.commit()
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
			
	def setDefault(self,defaultName,defaultValue, verbose= True):
		defaultTables = ['defaultprojectmetadata','defaultsimulationparameters','defaultconstants','defaulthydraulicparameters','defaulthydrologicalparameters','defaultdbstructure']
		for defaultTable in defaultTables:
			# search params
			# cursor.execute('INSERT INTO foo VALUES (?, ?)', ("It's okay", "No escaping necessary")
			#sql = "UPDATE %s SET value = '%s' WHERE id = '%s';"%(defaultTable,defaultValue,defaultName)
			sql = "UPDATE %s SET value = ? WHERE id = '%s';"%(defaultTable,defaultName)
			try:
				#print 'Running: %s' %(sql)
				self.startConnection()
				#res = self.cur.execute(sql)
				res = self.cur.execute(sql,(defaultValue,))
				self.conn.commit()
			except Exception as e:
				if verbose: self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
			finally:
				self.stopConnection()
		
	def getDefault(self,defaultName, verbose = True):
		defaultTables = ['defaultprojectmetadata','defaultsimulationparameters','defaultconstants','defaulthydraulicparameters','defaulthydrologicalparameters','defaultdbstructure']
		defaultValues = []
		for defaultTable in defaultTables:
			# search params
			try:
				self.startConnection()
				sql = "SELECT value FROM %s WHERE id = '%s';"%(defaultTable,defaultName)
				res = self.cur.execute(sql)
				data = self.cur.fetchall()
				for d in data:
					defaultValues.append(d[0])
					
			except Exception as e:
				if verbose: self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
				#defaultValues= []
			finally:
				self.stopConnection()
		
		return defaultValues[0]
		
	def getDefaultRecord(self,defaultName):
		defaultTables = ['defaultprojectmetadata','defaultsimulationparameters','defaultconstants','defaulthydraulicparameters','defaulthydrologicalparameters','defaultdbstructure']
		defaultValues = []
		for defaultTable in defaultTables:
			# search params
			try:
				self.startConnection()
				sql = "SELECT * FROM %s WHERE id = '%s';"%(defaultTable,defaultName)
				res = self.cur.execute(sql)
				data = self.cur.fetchall()
				for d in data:
					defaultValues.append(d)
					
			except Exception as e:
				self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
				#defaultValues= []
			finally:
				self.stopConnection()
				

		if len(defaultValues) > 0:
			res = defaultValues[0]
		else:
			self.progress.setInfo('Unable to find %s' %(defaultName),True)
			res = []
		
		return res

	def getMax(self, tableName, fieldName):
		data = None
		try:
			self.startConnection()
			sql = "SELECT max(%s) as maxvalue FROM %s;" % (fieldName, tableName)
			res = self.cur.execute(sql)
			data = self.cur.fetchall()
			if len(data)>0:
				data = data[0] # get from list
				data = data[0] # get from tuple
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' % (str(e), sql), True)
		finally:
			self.stopConnection()

		return data

	def getRecordAsDict(self,tableName,fieldsList,filterFld='', filterValue = None,orderBy = ''):
		data = {}
		if isinstance(fieldsList, list):
			fieldsList = ','.join(fieldsList)

		if fieldsList == '': fieldsList = '*'

		try:
			self.startConnection()
			if filterFld == '':
				sql = "SELECT %s FROM %s" % (fieldsList, tableName)
			else:
				sql = "SELECT %s FROM %s WHERE %s = '%s'" % (fieldsList, tableName, filterFld, filterValue)
			if orderBy != '': sql += ' ORDER BY ' + orderBy
			sql += ';'  # close query
			# TODO: check the use of apex in sql formula. It seems to not have effect on type of value filtered
			# print('sql',sql)
			df = pd.read_sql_query(sql, self.conn)
			data = df.to_dict(orient='records')
		# data = self.cur.fetchone()

		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' % (str(e), sql), True)
		finally:
			self.stopConnection()

		return data

	def getRecord(self,tableName,fieldsList,filterFld='', filterValue = None,orderBy = ''):
		data = []
		if isinstance(fieldsList,list):
			fieldsList = ','.join(fieldsList)
			
		if fieldsList == '': fieldsList='*'
		
		try:
			self.startConnection()
			if filterFld =='': sql = "SELECT %s FROM %s"%(fieldsList,tableName)
			else: sql = "SELECT %s FROM %s WHERE %s = '%s'"%(fieldsList,tableName,filterFld,filterValue)
			if orderBy != '': sql += ' ORDER BY '+orderBy
			sql+=';' # close query
			# TODO: check the use of apex in sql formula. It seems to not have effect on type of value filtered
			#print('sql',sql)
			res = self.cur.execute(sql)
			data = self.cur.fetchall()
			#data = self.cur.fetchone()
			
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
			
		return data
		
	def createArrayTable(self,tableName='results'):
		try:
			self.startConnection()
			sql = 'CREATE TABLE "%s" (%s)' %(tableName,'OBJ_ID TEXT UNIQUE, VALARRAY ARRAY')
			self.cur.execute(sql)
			self.conn.commit() #!!!!!
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
	def setArray(self,varName,nArray,tableName='results'):
		try:
			self.startConnection()
			sql = 'CREATE TABLE "%s" (%s)' %(tableName,'OBJ_ID TEXT UNIQUE, VALARRAY ARRAY')
			self.cur.execute(sql)
			sql = 'INSERT INTO %s (OBJ_ID, VALARRAY) VALUES (?, ?)'%(tableName)
			self.cur.execute(sql, (varName, nArray,))
			self.conn.commit() #!!!!!
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
			
	def setArrayName(self,oldVarName, newVarName, tableName):
		try:
			self.startConnection()
			# check if value already exists
			sql = "SELECT * FROM %s WHERE %s ='%s'" %(tableName,'OBJ_ID',newVarName)
			res = self.cur.execute(sql)
			data = self.cur.fetchall()
			defaultValues = []
			for d in data:
				defaultValues.append(d)
			
			if len(defaultValues) ==0:
				# if not, update old value
				sql = "UPDATE %s SET OBJ_ID = '%s' WHERE OBJ_ID ='%s'"%(tableName,newVarName,oldVarName)
				self.cur.execute(sql)
				self.conn.commit() #!!!!!
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
		
		
			
	def getArray(self,varName,tableName='results'):
		data = None
		try:
			self.startConnection()
			sql = "SELECT VALARRAY FROM %s WHERE OBJ_ID = '%s';" %(tableName,varName)
			self.cur.execute(sql)
			data = self.cur.fetchone()[0]
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
		return data
		
	def getColumnValues(self,fieldName,tableName):
		defaultValues = []
		try:
			self.startConnection()
			sql = "SELECT %s FROM %s;" %(fieldName,tableName)
			self.cur.execute(sql)
			data = self.cur.fetchall()
			for d in data:
				defaultValues.append(d[0])
				
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
		return defaultValues
		
	def replaceAllColumnValues(self,tableName,colName,tupleList):
		sql = ''
		#~ try:
			#~ self.startConnection()
			#~ sql = 'ALTER TABLE %s ADD COLUMN %s REAL default null;'%(tableName, colName)
			#~ self.cur.execute(sql)
		#~ except Exception as e:
			#~ print 'SQL error %s at %s' %(str(e),sql)
		#~ finally:
			#~ self.stopConnection()
		
		try:
			self.startConnection()
			sql = 'UPDATE %s SET %s= ? WHERE ogc_fid=?'%(tableName,colName)
			self.cur.executemany(sql, tupleList)
			self.conn.commit() #!!!!!
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
			
	def getMaxValue(self,tableName,colName):
		maxValue = None
		try:
			self.startConnection()
			sql = 'SELECT MAX(%s) FROM %s'%(colName,tableName)
			self.cur.execute(sql)
			data = self.cur.fetchall()
			for d in data:
				maxValue = d[0]
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
			
		return maxValue
		
	def getRowId(self,table, ids, idFld):
		res = []

		try:
			for id in ids:
				self.startConnection()
				sql = 'SELECT rowid FROM %s WHERE %s = "%s"'%(table,idFld,id)
				self.cur.execute(sql)
				data = self.cur.fetchall()
				for d in data:
					res.append(int(d[0]))
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
			
		return res
		
	def getUniqueValues(self,fieldName, tableName):
		res = []
		sql = 'SELECT DISTINCT %s FROM %s ORDER BY %s ASC'%(fieldName,tableName,fieldName)
	
		try:
			self.startConnection()
			self.cur.execute(sql)
			data = self.cur.fetchall()
			for d in data:
				res.append(int(d[0]))
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
		return res

	def getAllSourceNode(self, startNodeId):
		# get all water sources connecte to startNodeId

		nodeList = [startNodeId]
		flowRatio = [1.0]

		wsNode = []
		wsRatio = []

		sql = "SELECT idr_links.inlet_node, idr_links.flow_rate, idr_links.inf_losses FROM idr_links WHERE idr_links.outlet_node = '%s'"


		while len(nodeList)>0:
			#if len(nodeList)>100: break

			nodeId = nodeList[0]
			dsFlowRatio = flowRatio[0]
			# get all upslope node from the links connected to current node
			try:
				self.startConnection()
				self.cur.execute(sql%nodeId)
				data = self.cur.fetchall()
			except Exception as e:
				self.progress.setInfo('SQL error %s at %s' % (str(e), sql), True)
			finally:
				self.stopConnection()

			if len(data)>0:
				for i,d in enumerate(data):
					currId = d[0]
					linkFR = float(d[1])
					linkEff = 1.0-float(d[2])
					currFR = dsFlowRatio*linkFR*linkEff
					# follow the first
					if i == 0:
						# replace the first element in the list of processing nodes
						nodeList[0] = currId
						flowRatio[0] = currFR
						#print('the first %s' % nodeId)
					else:
						# leave the others as seeds for the next time
						#print('the next %s' % d[0])
						nodeList.append(currId)
						flowRatio.append(currFR)
			else:
				# is an edge point --> store node id and the cumulated ratio
				wsNode.append(nodeId)
				wsRatio.append(dsFlowRatio)

				# remove the first node of the list
				nodeList.pop(0)
				flowRatio.pop(0)

		return {'nodeList':wsNode,'ratioList':wsRatio}

	def getDictFromTable(self,table,keyFld,valueFld):
		res = {}
		try:
			self.startConnection()
			# sql = "SELECT links.OBJ_ID FROM links WHERE links.NODE_START IN (SELECT nodes.OBJ_ID FROM nodes, links WHERE nodes.OBJ_ID = links.NODE_END);"
			sql = "SELECT %s,%s FROM %s;" % (keyFld,valueFld,table)
			self.cur.execute(sql)
			data = self.cur.fetchall()
			for d in data:
				res[d[0]] = d[1]

		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' % (str(e), sql), True)
		finally:
			self.stopConnection()

		return res

	def getAllFollowingLink(self,nodeStart = 'NODE_START',nodeEnd ='NODE_END',downStream = False):
		if not downStream:
			nodeStart = 'NODE_END'
			nodeEnd ='NODE_START'
			
		defaultValues = []
		
		try:
			self.startConnection()
			#sql = "SELECT links.OBJ_ID FROM links WHERE links.NODE_START IN (SELECT nodes.OBJ_ID FROM nodes, links WHERE nodes.OBJ_ID = links.NODE_END);"
			sql = "SELECT links.OBJ_ID FROM links WHERE links.%s IN (SELECT nodes.OBJ_ID FROM nodes, links WHERE nodes.OBJ_ID = links.%s);"%(nodeEnd,nodeStart)
			self.cur.execute(sql)
			data = self.cur.fetchall()
			for d in data:
				defaultValues.append(d[0])
				
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
		return defaultValues
		
	def getFollowingLink(self,nodeId,nodeFld):
		defaultValues = []
		try:
			self.startConnection()
			#sql = "SELECT links.OBJ_ID FROM links WHERE links.NODE_START IN (SELECT nodes.OBJ_ID FROM nodes, links WHERE nodes.OBJ_ID = links.NODE_END);"
			sql = "SELECT links.OBJ_ID FROM links WHERE links.%s = '%s';"%(nodeFld,nodeId)
			self.cur.execute(sql)
			data = self.cur.fetchall()
			for d in data:
				defaultValues.append(d[0])
				
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
		return defaultValues

	def getMinMaxYear(self, tNameList, fName):
		minTime = ''
		maxTime = ''

		finalList = None
		for tName in tNameList:
			print('get min max',tName, fName)
			vals = self.getMinMax(tName, fName)
			print('vals', vals)
			vals = vals[0]

			if vals[0] and vals[1]:
				startDate = datetime.strptime(vals[0], '%Y-%m-%d')
				endDate = datetime.strptime(vals[1], '%Y-%m-%d')
				yearList = list(range(startDate.year, endDate.year + 1))
				if finalList:
					finalList = list(set(finalList) & set(yearList))
				else:
					finalList = yearList

		minTime = min(finalList)
		maxTime = max(finalList)

		return minTime, maxTime
		
	def getMultiMinMax(self,tNameList,fName):
		minTime = ''
		maxTime = ''
		
		for tName in tNameList:
			vals = self.getMinMax(tName,fName)
			vals = vals[0]
			if vals[0]:
				startDate = datetime.strptime(vals[0], '%Y-%m-%d').year
				if minTime =='':
					minTime = startDate
				else:
					if minTime>startDate:
						minTime = startDate
			
			if vals[1]:
				endDate = datetime.strptime(vals[1], '%Y-%m-%d').year
				if maxTime =='':
					maxTime = endDate
				else:
					if maxTime<endDate:
						maxTime = endDate
						
		return minTime,maxTime
		
	def getMinMax(self, tName,fName):
		sql = """select
					substr(min([%table%].[%field%]),0,11) as minValue,
					substr(max([%table%].[%field%]),0,11) as maxValue
					from [%table%]"""
		
		sql = sql.replace('[%table%]',tName)
		sql = sql.replace('[%field%]',fName)
		
		data = []
		try:
			self.startConnection()
			self.cur.execute(sql)
			data = self.cur.fetchall()
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
		return data
		
	def makeStatistics(self, tableName, sensorId, fromDate = None, toDate = None):
		sql = """
		select
			wsid,
			substr(min(timestamp),0,11) as startDate,
			substr(max(timestamp),0,11) as endDate,
			min(recval) as minVal,
			max(recval) as maxVal,
			avg(recval) as avgVal,
			sum(recval) as cumVal,
			count(recval) as countVal,
			count(case when (wsid = [%sensorId%] and  recval = '') then 1 end) as countEmpty,
			(SELECT recval FROM [%table%]
				WHERE wsid=[%sensorId%] ORDER BY recval ASC LIMIT 1 OFFSET
				(SELECT
					COUNT(*)
					FROM [%table%]
					WHERE wsid=[%sensorId%]) * 25 / 100 - 1) as perc25,
			(SELECT recval FROM [%table%]
				WHERE wsid=[%sensorId%] ORDER BY recval ASC LIMIT 1 OFFSET
				(SELECT
					COUNT(*)
					FROM [%table%]
					WHERE wsid=[%sensorId%]) * 50 / 100 - 1) as perc50,
			(SELECT recval FROM [%table%]
				WHERE wsid=[%sensorId%] ORDER BY recval ASC LIMIT 1 OFFSET
				(SELECT
					COUNT(*)
					FROM [%table%]
					WHERE wsid=[%sensorId%]) * 75 / 100 - 1) as perc75
			from [%table%]
			where wsid = [%sensorId%]
		"""
			
		sql = sql.replace('[%table%]',tableName)
		sql = sql.replace('[%sensorId%]',str(sensorId))

		if fromDate: sql += " AND date(timestamp) > date('%s')"%fromDate

		if toDate: sql += " AND date(timestamp) <= date('%s')" % toDate

		
		#print(sql)
		data = []
		try:
			self.startConnection()
			self.cur.execute(sql)
			data = self.cur.fetchall()
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()

		startDate = None
		endDate = None
		nOfExpDays = None
		fullness =None
		minVal = None
		maxVal = None
		meanVal = None
		cumVal = None
		perc25 = None
		perc50 = None
		perc75 = None
		nOfRecs = 0
		nOfEmpy = 0

		if len(data)>0:
			data = data[0]
			if (data[1] and data[2]):
				startDate = datetime.strptime(data[1],'%Y-%m-%d')
				endDate = datetime.strptime(data[2],'%Y-%m-%d')

				startYear = startDate.year
				endYear = endDate.year

				starDateTeo = date(startYear, 1,1)
				endDateTeo = date(endYear, 12, 31)

				nOfExpDays = (endDateTeo-starDateTeo).days+1
				nOfRecs = data[7]
				nOfEmpy = data[8]

				fullness = float(nOfRecs-nOfEmpy)/nOfExpDays

				minVal = data[3]
				maxVal = data[4]
				meanVal = data[5]
				cumVal = data[6]

				perc25 = data[9]
				perc50 = data[10]
				perc75 = data[11]

		return {'startDate':startDate, 'endDate':endDate, 'nOfExpDays':nOfExpDays,'nOfFilled':nOfRecs-nOfEmpy,'fullness':fullness,
				'minVal':minVal,'maxVal':maxVal,'meanVal':meanVal,'cumVal':cumVal,'perc25':perc25,'perc50':perc50,'perc75':perc75}
		
		
	def getTimeSeries(self,tableName, wsId):
		sql = 'select timestamp,recval from %s where wsid = %s order by timestamp'%(tableName, wsId)
		data = []
		try:
			self.startConnection()
			self.cur.execute(sql)
			data = self.cur.fetchall()
		except Exception as e:
			self.progress.setInfo('SQL error %s at %s' %(str(e),sql),True)
		finally:
			self.stopConnection()
		
		timestamp = []
		values = []
		for d in data:
			timestamp.append(datetime.strptime(d[0],'%Y-%m-%d'))
			values.append(float(d[1]))
			
		return timestamp, values
		
		
	def testArrayOK2(self):
		print('in <testArray>')
		x = np.arange(12).reshape(2,6)
		print(type(x))
		
		#~ self.setArray(varName = 'x',nArray = x, tableName='results')
		#~ res = self.getArray(varName = 'x',tableName='results')
		#~ print 'res:',res
		self.startConnection()
		
		self.cur.execute("create table results (varname TEXT, varvalue ARRAY)")
		#self.cur.execute("create table results (varname TEXT, varvalue BLOB)")
		print('after create')
		self.cur.execute("insert into results (varname,varvalue) values (?,?)", ('x',x,))
		
		#~ out = io.BytesIO()
		#~ np.save(out, x)
		#~ out.seek(0)
		#~ binx = sqlite.Binary(out.read())
		
		
		#~ self.cur.execute("insert into results (varname,varvalue) values (?,?)", ('x',binx))
		print('after insert')
		
		
		self.conn.commit() #!!!!!
		
		
		self.stopConnection()
		
		self.startConnection()
		self.cur.execute("select varname,varvalue from results")
		print('after select')
		rec = self.cur.fetchone()
		name = rec[0]
		data = rec[1]
		
		#~ databin = rec[1]
		
		#~ out = io.BytesIO(databin)
		#~ out.seek(0)
		#~ data =  np.load(out)

		print(name)
		print(data)
		print(type(data))
		
		self.stopConnection()
		
	def testGetArray(self):
		self.startConnection()
		self.cur.execute("select varname,varvalue from results")
		rec = self.cur.fetchone()
		
		name = rec[0]
		data = rec[1]

		print(name)
		print(data)
		print(type(data))
		
		self.stopConnection()
		
		
	def testArrayOK(self):
		print('in <testArrayOK>')
		x = np.arange(12).reshape(2,6)
		print(type(x))

		con = sqlite.connect(":memory:", detect_types=sqlite.PARSE_DECLTYPES)
		print('after connect')
		cur = con.cursor()
		print('after cursor')
		cur.execute("create table test (id TEXT, arr ARRAY)")
		print('after create')
		cur.execute("insert into test (id,arr) values (?,?)", ('x',x,))
		print('after insert')
		cur.execute("select id,arr from test")
		print('after select')
		rec = cur.fetchone()
		name = rec[0]
		data = rec[1]

		print(name)
		print(data)
		print(type(data))

		

if __name__ == '__console__':
	
	## CREATE TABLE t(x INTEGER, y, z,(x ASC));
	#~ DBM = SQLiteDriver('C:/idragra_code/dataset/idragra_db.gpkg', False)
	
	#~ initTableSQL =	"""DROP TABLE IF EXISTS tmax;
								#~ CREATE TABLE tmax (
																#~ timestamp text,
																#~ wsname text NOT NULL,
																#~ recval double
															#~ );
								#~ DROP TABLE IF EXISTS  tmin;
								#~ CREATE TABLE tmin (
																#~ timestamp text,
																#~ wsname text NOT NULL,
																#~ recval double
															#~ );
								#~ DROP TABLE IF EXISTS  ptot;
								#~ CREATE TABLE ptot (
																#~ timestamp text,
																#~ wsname text NOT NULL,
																#~ recval double
															#~ );
								#~ DROP TABLE IF EXISTS  umax;
								#~ CREATE TABLE umax (
																#~ timestamp text,
																#~ wsname text NOT NULL,
																#~ recval double
															#~ );
								#~ DROP TABLE IF EXISTS  umin;
								#~ CREATE TABLE umin (
																#~ timestamp text,
																#~ wsname text NOT NULL,
																#~ recval double
															#~ );
								#~ DROP TABLE IF EXISTS  vmed;
								#~ CREATE TABLE vmed (
																#~ timestamp text,
																#~ wsname text NOT NULL,
																#~ recval double
															#~ );
								#~ DROP TABLE IF EXISTS  rgcorr;
								#~ CREATE TABLE rgcorr (
																#~ timestamp text,
																#~ wsname text NOT NULL,
																#~ recval double
															#~ );
							#~ """
							
	#~ DBM.executeSQL(initTableSQL)
	
	#~ DBM = SQLiteDriver('C:/idragra_code/dataset/idragra_db.gpkg', False)
	#~ ## 8199,2020/01/01 00:00,0.0
	#~ #DBM.importDataFromCSV( filename ='C:/idragra_code/dataset/testpiogge2.csv', tablename='ptot', timeFldIdx=1, valueFldIdx=2, sensorId='1211', skip=1,timeFormat='%Y/%m/%d %H:%M',column_sep=',')
	#~ DBM.importDataFromCSV( filename ='C:/idragra_code/dataset/testpiogge3.csv', tablename='ptot', timeFldIdx=1, valueFldIdx=2, sensorId='666', skip=1,timeFormat='%Y/%m/%d %H:%M',column_sep=',')
	
	gpkgPath = 'C:/idragra_code/dataset/test.gpkg'

	options = QgsVectorFileWriter.SaveVectorOptions()
	#options.EditionCapability = QgsVectorFileWriter.CanAddNewLayer 
	
	
	#options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
	# create vectorlayer and save to new geopackage
	ws_lyr = QgsVectorLayer("Point", "idr_weather_stations", "memory")
	print(ws_lyr.name())
	options.layerName = ws_lyr.name() 
	pr = ws_lyr.dataProvider()
	pr.addAttributes([QgsField("id", QVariant.String),
								QgsField("name",  QVariant.String)])
	ws_lyr.updateFields()
	_writer = QgsVectorFileWriter.writeAsVectorFormat(ws_lyr, gpkgPath, options)
	print(_writer)
	
	options2 = QgsVectorFileWriter.SaveVectorOptions()
	options2.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
	
	field_lyr = QgsVectorLayer("Polygon", "idr_fields", "memory")
	print(field_lyr.name())
	options2.layerName = ws_lyr.name() 
	
	pr = field_lyr.dataProvider()
	pr.addAttributes([QgsField("id", QVariant.String),
								QgsField("name",  QVariant.String),
								QgsField("wtdepth",  QVariant.Double),
								QgsField("id_soil",  QVariant.String),
								QgsField("id_soiluse",  QVariant.String)])
	field_lyr.updateFields()
	_writer = QgsVectorFileWriter.writeAsVectorFormat(field_lyr, gpkgPath,  options2)
	print(_writer)
	print('OK')