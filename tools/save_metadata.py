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
from qgis.core import QgsVectorLayer,QgsField,QgsPoint,QgsFeature,QgsGeometry,QgsProject,QgsVectorFileWriter,QgsCoordinateReferenceSystem,QgsFields,QgsWkbTypes


def saveMetadata(outFile, name,origin,description,abstract):
	template = """
<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.2.0-Bonn">
	<identifier>%s</identifier>
	<parentidentifier>%s</parentidentifier>
	<title>%s</title>
	<abstract>%s</abstract>
</qgis>
"""%(name,origin,description,abstract)
					
	f = None
	try:
		f = open(outFile,'w')
		f.write(template)
	except Exception as e:
		# do nothing
		res = str(e)
	finally:
		f.close()
	

if __name__ == '__console__':
	fileName = 'C:/enricodata/lavori/firenze2018/elab/test.qmd'
	saveMetadata(fileName,'a test','c:/atest/gisdata.mat','a short description','a small abstract\nwith return carriage')
	