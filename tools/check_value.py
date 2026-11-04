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


def checkValue(nameVal, testVal, testPar, testFun, tr, feedback):
    res = 1
    if testFun == 'in':
        if not (testVal in testPar):
            feedback.reportError(tr('Not admissible value error: %s not in %s') %
                                 (nameVal, str(testPar)), True)
            res = 0
    elif testFun in ['><', 'between']:
        if not ((testVal > testPar[0]) and (testVal < testPar[1])):
            feedback.reportError(tr('Not admissible value error: %s not in range [%s-%s]') %
                                 (nameVal, testPar[0], testPar[1]), True)
            res = 0
    elif testFun in ['>=<=', 'in_between']:
        if not ((testVal >= testPar[0]) and (testVal <= testPar[1])):
            feedback.reportError(tr('Not admissible value error: %s not in range [%s-%s]') %
                                 (nameVal, testPar[0], testPar[1]), True)
            res = 0
    elif testFun in ['<', 'exclusive_minor']:
        if not (testVal < testPar):
            feedback.reportError(tr('Not admissible value error: %s equal-major than %s') %
                                 (nameVal, testPar), True)
            res = 0
    elif testFun in ['>', 'exclusive_major']:
        if not (testVal > testPar):
            feedback.reportError(tr('Not admissible value error: %s equal-minor than %s') %
                                 (nameVal, testPar), True)
            res = 0
    elif testFun in ['<=', 'minor']:
        if not (testVal <= testPar):
            feedback.reportError(tr('Not admissible value error: %s major than %s') %
                                 (nameVal, testPar), True)
            res = 0
    elif testFun in ['>=', 'major']:
        if not (testVal >= testPar):
            feedback.reportError(tr('Not admissible value error: %s minor than %s') %
                                 (nameVal, testPar), True)
            res = 0
    elif testFun in ['asc']:
        testVal1 = testVal
        testVal1.sort()
        if not (testVal == testVal1):
            feedback.reportError(tr('Not admissible value error: %s is not sorted ascending [%s]') %
                                 (nameVal, str(testVal)), True)
            res = 0
    else:
        pass

    return res