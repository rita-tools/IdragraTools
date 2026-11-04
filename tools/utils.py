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

from qgis.core import QgsRectangle


def returnExtent(extStr):
    ext = None
    try:
        ll,ur = extStr.split(' : ')
        xll,yll = ll.split(',')
        xur, yur = ur.split(',')
        #print(xll,yll,xur,yur)
        ext = QgsRectangle(round(float(xll),4), round(float(yll),4), round(float(xur),4), round(float(yur),4))
    except Exception as e:
        print('In returnExtent, error:',str(e))

    return ext

def isLeap(year):
    res = False
    if (((year % 400 == 0) and (year % 100 == 0)) or ((year % 4 == 0) and (year % 100 != 0))):
        res = True

    return res

