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

def readIdragraParameters(idragraFile, feedback,tr):

    pars = {}

    try:
        f = open(idragraFile, 'r')
        for l in f:
            l = l.replace(' ', '')
            l = l.rstrip('\n')  # remove return carriage
            l = l.split('=')
            if len(l) == 2:
                parName = l[0].lower()
                # print(parName)
                if parName == 'inputpath':
                    pars['inputpath'] = l[1]
                elif parName == 'outputpath':
                    pars['outputpath'] = l[1]
                elif parName == 'monthlyflag':
                    if l[1] == 'F': pars['monthlyflag'] = False
                    else: pars['monthlyflag'] = True
                elif parName == 'startdate':
                    pars['startdate'] = int(l[1])
                elif parName == 'enddate':
                    pars['enddate'] = int(l[1])
                elif parName == 'deltadate':
                    pars['deltadate'] = int(l[1])
                else:
                    # all the other cases
                    pars[parName] = l[1]
    except Exception as e:
        feedback.reportError(tr('Cannot parse %s because %s') %
                              (idragraFile, str(e)), True)
    finally:
        if f: f.close()

    return pars