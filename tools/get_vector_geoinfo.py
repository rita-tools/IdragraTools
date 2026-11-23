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

from qgis.core import QgsVectorLayer
import os.path as osp

def getVectorGeoinfo(fileName):
	baseName = osp.basename(fileName)[0:-4]
	path = fileName
	
	vlayer = QgsVectorLayer(path, baseName)
	
	if not vlayer.isValid():
		ext = None
		error = vlayer.error().summary()
	else:
		ext = vlayer.extent()
		error = ''
	
	res = {'ext':ext,'error':error}
	return res
		
		
if __name__ == '__console__':
	fileName = 'C:/enricodata/lavori/firenze2018/elab/ch_from_gisdata_CECINA_2014.tif'
	res = getRasterGeoinfo(fileName)
	print('res:',res)
	