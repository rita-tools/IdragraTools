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

import numpy as np
from osgeo import gdal
import os
import struct
import glob
import shutil

from qgis.PyQt.QtCore import QObject

from qgis.core import (Qgis,
									QgsRasterBlock,
									QgsErrorMessage,
									QgsProcessingException,
									QgsProcessing,
									QgsFeatureSink,
									QgsProcessingAlgorithm,
									QgsProcessingParameterFeatureSource,
									QgsProcessingParameterFeatureSink,
									QgsProcessingParameterFile,
									QgsVectorLayer,
									QgsProcessingParameterRasterLayer,
									QgsProcessingParameterRasterDestination,
									QgsProcessingParameterEnum,
									QgsCoordinateReferenceSystem,
									QgsApplication,
									QgsField,
									QgsFields,
									QgsPointXY,
									QgsFeature,
									QgsGeometry,
									QgsProject,
									QgsAction,
									QgsWkbTypes,
									QgsRectangle,
									QgsRasterFileWriter)

def saveAsGDAL(outputFile,ncols, nrows, extent, crs,nodata,data):
	# create raster with array data
	outputFormat = QgsRasterFileWriter.driverForExtension(os.path.splitext(outputFile)[1])

	writer = QgsRasterFileWriter(outputFile)
	writer.setOutputProviderKey('gdal')
	writer.setOutputFormat(outputFormat)
	
	provider = writer.createOneBandRaster(Qgis.Float32 , ncols, nrows, extent, crs)
	if provider is None:
		raise QgsProcessingException(self.tr("Could not create raster output: {}").format(outputFile))
	if not provider.isValid():
		raise QgsProcessingException(self.tr("Could not create raster output {}: {}").format(outputFile,
																							provider.error().message(QgsErrorMessage.Text)))

	provider.setNoDataValue(1, nodata)
	
	block = QgsRasterBlock(Qgis.Float32, ncols, 1)
	
	total = 100.0 / nrows if nrows else 0
	for i in range(nrows):
		
		#data = [3.0] * ncols
		#slice = self.data[self.nrows-i-1][:]
		slice = data[i][:]
		#feedback.pushInfo(self.tr('i: %s, n. of data: %s, ncols: %s')%(i, len(data), ncols))
	
		block.setData(struct.pack('{}f'.format(ncols), *slice))
		provider.writeBlock(block, 1, 0, i)
		
	provider.setEditable(False)

def readCellIndexFile(filepath):
	data = []
	ncols = -1 
	nrows = -1 
	ncells = -1
	proj = -1 
	xll = -1
	yll = -1
	dx = -1
	dy = -1
	notata = -1
	
	try:
		f = open(filepath,'r')
		for l in f:
			# TODO: seems to manage both white space and tabs (verify)
			l = l.split()
			if l[0].lower() == 'ncols':
				ncols = int(l[1])
			elif l[0].lower() == 'nrows':
				nrows = int(l[1])
			elif l[0].lower() == 'xllcorner':
				xll = float(l[1])
			elif l[0].lower() == 'yllcorner':
				yll = float(l[1])
			elif l[0].lower() == 'cellsize':
				dx = float(l[1])
				dy = float(l[1])
			elif l[0].lower() == 'dx':
				dx = float(l[1])
			elif l[0].lower() == 'dy':
				dy = float(l[1])
			elif l[0].lower() == 'nodata_value':
				nodata = float(l[1])
			else:
				# load data to array
				for v in l:
					data.append(float(v))

		# close the file
		f.close()
	except IOError:
		print('Cannot open file: %s' %filepath)
	finally:
		pass#f.close()
		
	return {'ncols': ncols, 'nrows':nrows,'proj':proj, 'xllcorner':xll, 'yllcorner':yll, 'dx':dx, 'dy':dy, 'cellsize':dx, 'nodata':notata, 'data':data, 'crs':''}
	
def regenerateRaster(prms,prms2,fileToExport):
	# empty data
	tempdata = np.full((prms['nrows']*prms['ncols']), prms['nodata'], dtype=np.float32)

	#open outputfile
	importedData = prms2['data']
	
	# populate by index
	#print(prms['data'].astype(int))
	tempdata[np.array(prms['data'],int)]=importedData
	
	# reshape
	tempdata = np.reshape(tempdata, (prms['nrows'],prms['ncols']))
	
	# create new raster object
	extent = QgsRectangle(prms['xllcorner'], prms['yllcorner'], prms['xllcorner']+prms['dx']*prms['ncols'], prms['yllcorner']+prms['dy']*prms['nrows'])
	saveAsGDAL(fileToExport,prms['ncols'], prms['nrows'], extent, QgsCoordinateReferenceSystem(),prms['nodata'],tempdata)


if __name__ == '__console__':
	# read cell index file
	fileOfindex = 'C:/idragra_code/dataset/rid_data_base/validcell.asc'
	
	# create new array
	prms = readCellIndexFile(fileOfindex)
	
	#open outputfile
	pathToImport = 'C:/idragra_code/dataset/test1'
	pathToExport = 'C:/idragra_code/dataset/test1exp'
	
	print('pathToImport: %s',pathToImport)
	print('pathToExport: %s',pathToExport)
	
	# loop in pathToImport and list all file
	for f in glob.glob(os.path.join(pathToImport,'*.*')):
		fname = os.path.basename(f)
		if fname.endswith('asc'):
			print('process file: %s'%fname)
			#compact
			importFrom = os.path.join(pathToImport,fname)
			print('import %s'%importFrom)
			prms2 = readCellIndexFile(importFrom)
			
			fileToExport = os.path.join(pathToExport,fname[:-4]+'.tif')
			print('export to %s'%fileToExport)
			regenerateRaster(prms,prms2,fileToExport)
		elif fname.endswith('csv'):
			#make a copy
			shutil.copyfile(os.path.join(pathToImport,fname),os.path.join(pathToExport,fname))
		else:
			print('%s is other'%f)
		
	
	