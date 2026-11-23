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

from qgis.core import QgsRasterLayer
import os.path as osp

def getRasterGeoinfo(fileName):
	# init variable
	ncols = None
	nrows = None
	xll_corner = None
	yll_corner = None
	xur_corner = None
	yur_corner = None
	pixelSizeX = None
	pixelSizeY = None
	nBands = None
	error = None
	
	if fileName is None: fileName = ''
	
	if osp.exists(fileName):
		baseName = osp.basename(fileName)[0:-4]
		path = fileName
		
		rlayer = QgsRasterLayer(path, baseName)
		
		if not rlayer.isValid():
			error = rlayer.error().summary()
		else:
			ncols = rlayer.width()
			nrows = rlayer.height()
			xll_corner = rlayer.extent().xminimum()
			yll_corner = rlayer.extent().yminimum()
			xur_corner = rlayer.extent().xmaximum()
			yur_corner = rlayer.extent().ymaximum()
			pixelSizeX = rlayer.rasterUnitsPerPixelX()
			pixelSizeY = rlayer.rasterUnitsPerPixelY()
			nBands = rlayer.bandCount()
			error = ''
	else:
		error = 'Cannot find %s'%fileName
	
	res = {'ncols':ncols,'nrows':nrows,'xll_corner':xll_corner, 'yll_corner':yll_corner,'xur_corner':xur_corner, 'yur_corner':yur_corner, 'dx':pixelSizeX, 'dy': pixelSizeY, 'n_band':nBands, 'error':error}
	return res
		
		
if __name__ == '__console__':
	fileName = 'C:/enricodata/lavori/firenze2018/elab/ch_from_gisdata_CECINA_2014.tif'
	res = getRasterGeoinfo(fileName)
	print('res:',res)
	