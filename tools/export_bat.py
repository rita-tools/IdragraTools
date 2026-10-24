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

def exportBat(outPath, feedback = None,tr=None):
	#TODO: make something of better
	#path2cropcoeff = 'C:/idragra_code/cropcoeff_v4bis/CropCoef_v4/for_redistribution_files_only/CropCoef_v4.exe'
	#path2idragra = 'C:/idragra_code/Idragra/idragra_20210211ASC.exe'
	s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
	path2cropcoeff = s.value('cropcoeffPath', '')
	path2idragra = s.value('idragraPath', '')

	# save to file
	writeParsToTemplate(outfile=os.path.join(outPath,'run_cropcoef.bat'),
									parsDict =  {
									'SIMPATH':outPath,
									'PATHTOCROPCOEFF':path2cropcoeff.replace('/','\\'),
									'CROPCOEFFPAR':'cropcoef.txt',
									},
									templateName='run_cropcoef.txt')

	# save to file
	writeParsToTemplate(outfile=os.path.join(outPath,'run_idragra.bat'),
									parsDict =  {
									'SIMPATH':outPath,
									'PATHTOIDRAGRA':path2idragra.replace('/','\\'),
									'IDRAGRAPAR':'idragra_parameters.txt'
									},
									templateName='run_idragra.txt')



def exportCropCoefBat(outPath):
	s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
	path2cropcoeff = s.value('cropcoeffPath', '')

	# save to file
	writeParsToTemplate(outfile=os.path.join(outPath,'run_cropcoef.bat'),
									parsDict =  {
									'SIMPATH':outPath,
									'DRIVE':outPath[0:2],
									'PATHTOCROPCOEFF':path2cropcoeff.replace('/','\\'),
									'CROPCOEFFPAR':'cropcoef.txt',
									},
									templateName='run_cropcoef.txt')


def exportIdrAgraBat(outPath):
	s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
	path2idragra = s.value('idragraPath', '')

	# save to file
	writeParsToTemplate(outfile=os.path.join(outPath,'run_idragra.bat'),
									parsDict =  {
									'SIMPATH':outPath,
									'DRIVE': outPath[0:2],
									'PATHTOIDRAGRA':path2idragra.replace('/','\\'),
									'IDRAGRAPAR':'idragra_parameters.txt'
									},
									templateName='run_idragra.txt')
