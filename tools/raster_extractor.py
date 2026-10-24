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

import scipy.io as sio

from qgis.PyQt.QtCore import QObject

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsVectorLayer,QgsField,QgsPoint,QgsFeature,QgsGeometry,QgsProject

from .gis_grid import GisGrid


def rasterExtractor(mv,varName):
	# make a grid object
	xll = mv.GEOREF['xll'][1]
	yll = mv.GEOREF['yll'][1]
	grid_size = mv.GEOREF['grid_size'][1]
	nodata = mv.GEOREF['nodata'][1]
	crs = mv.GEOREF['crs'][1]
	
	# get raster data from gisdata or resfile
	resData = mv.RASTERVAR[varName][1]
	if resData is None:
		return None
		
	nrows, ncols = resData.shape
	# save to file
	resGrd = GisGrid(ncols, nrows, xll, yll, grid_size, grid_size,nodata,crs)
	resGrd.data = np.flip(resData,0)
	return resGrd
	
if __name__ == '__console__':
	pass	