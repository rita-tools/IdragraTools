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

from qgis.PyQt.QtCore import QSettings

from .write_pars_to_template import writeParsToTemplate

def exportIdrAgraBat(outPath):
	s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
	path2idragra = s.value('idragra3Path', '')
	writeParsToTemplate(outfile=os.path.join(outPath, 'run_idragra.bat'),
						parsDict={'PATHTOIDRAGRA': path2idragra.replace('/', '\\'),
								  'IDRAGRAPAR': 'idragra_parameters.txt'},
						templateName='run_idragra.txt')
