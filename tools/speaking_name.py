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

def speakingName(origName,repSpace='_',maxLen=10):
    newName = origName.replace(' ', repSpace)

    if len(newName) > maxLen:
        newName = newName[:maxLen]
    else:
        newName = newName + ''.join([repSpace] * (maxLen - len(newName)))

    return newName


if __name__ == '__main__':
    oldName = 'ab3 gsh4 pski   111'
    print('newName long', speakingName(oldName))

    oldName = 'ab3'
    print('newName shirt', speakingName(oldName))