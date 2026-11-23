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

from qgis.PyQt.QtGui import QColor
from qgis.core import QgsGradientColorRamp, QgsGradientStop,QgsMapLayer,QgsClassificationEqualInterval,QgsRendererRange,QgsGraduatedSymbolRenderer,QgsSymbol
## https://gis.stackexchange.com/questions/342352/apply-a-color-ramp-to-vector-layer-using-pyqgis3

def replaceColorRamp(vLayer,varToPlot,fieldName = 'tempvalue',minmax = None):
	colRampGrad = QgsGradientColorRamp()
	if varToPlot == 'stp_irr':
		pass
	else:
		colRampGrad.setColor1(QColor(5,113,176))
		colRampGrad.setColor2(QColor(202,0,32))
		colRampGrad.setStops(
		   [QgsGradientStop(0.25, QColor(146,197,222)),
		   QgsGradientStop(0.5, QColor(247,247,247)),
		   QgsGradientStop(0.75, QColor(244,165,130))]
		)

	# get min/max value
	fields = vLayer.fields()
	idx = fields.indexFromName(fieldName)

	if not minmax:
		ramp_min = vLayer.minimumValue(idx)
		ramp_max = vLayer.maximumValue(idx)
	else:
		ramp_min,ramp_max = minmax
		
	ramp_num_steps = 5

	setColorRamp(vLayer,ramp_min, ramp_max, ramp_num_steps, colRampGrad,fieldName)

def setColorRamp(vLayer,minVal, maxVal, numSteps, colRampGrad,fieldName = 'tempvalue'):
	# Apply colour ramp for vector / points layer
	if vLayer.type() == QgsMapLayer.VectorLayer:
		intervals = QgsClassificationEqualInterval().classes(minVal, maxVal, numSteps)
		render_range_list = [QgsRendererRange(i, QgsSymbol.defaultSymbol(vLayer.geometryType())) for i in intervals]
		renderer = QgsGraduatedSymbolRenderer(fieldName, render_range_list)
		renderer.updateColorRamp(colRampGrad)
		vLayer.setRenderer(renderer)
		vLayer.triggerRepaint()

if __name__ == '__console__':
	vLayer =  iface.activeLayer()
	replaceColorRamp(vLayer,'stp_irr')
