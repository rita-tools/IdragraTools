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

from qgis.gui import QgsDualView, QgsAttributeEditorContext
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QMenu

class AttributesTableView(QDialog):
    """
    AttributeTableView class to display filtered attributes table
    """

    def __init__(self, layer, canvas, request):
        """
        Constructor
        """
        QDialog.__init__(self)
        self.setWindowTitle(layer.name())
        self.__layout = QVBoxLayout()
        self.__menu = QMenu()
        #print(len(layer.actions().actions()))
        for a in layer.actions().actions():
            self.__menu.addAction(a)
        self.__layout.addWidget(self.__menu)
        self.__dual = QgsDualView()
        self.__context = QgsAttributeEditorContext()
        # self.__dual.init(layer, canvas,request, self.__context)
        self.__dual.init(layer, canvas)
        self.__dual.setView(QgsDualView.AttributeEditor)
        # TODO: add action
        #print('filtered',self.__dual.filteredFeatures())
        self.__layout.addWidget(self.__dual)
        self.setLayout(self.__layout)