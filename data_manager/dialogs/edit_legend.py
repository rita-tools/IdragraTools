# -*- coding: utf-8 -*-

"""
/***************************************************************************
 Data Manager
 A tool to manage time series from database
-------------------
		begin				: 2020-12-01
		copyright			: (C) 2020 by Enrico A. Chiaradia
		email				    : enrico.chiaradia@unimi.it
 ***************************************************************************/

/***************************************************************************
 *																		                                                               *
 *   This program is free software; you can redistribute it and/or modify                                *
 *   it under the terms of the GNU General Public License as published by                              *
 *   the Free Software Foundation; either version 2 of the License, or	                                   *
 *   (at your option) any later version.								                                                   *
 *																		                                                               *
 ***************************************************************************/
"""
__author__ = 'Enrico A. Chiaradia'
__date__ = '2020-12-01'
__copyright__ = '(C) 2020 by Enrico A. Chiaradia'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *

from qgis.PyQt import uic

from qgis.PyQt.QtWidgets import QDialog, QToolBox, QWidget, QVBoxLayout, QFileDialog, QListWidgetItem, QDialogButtonBox, \
	QTableWidgetItem

# qgis import
from qgis.core import *
from qgis.gui import *
# other
import os
import sys
import glob
from datetime import datetime


# ~ uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'project_dialog.ui'))
# ~ print('uiFilePath: %s'%uiFilePath)
# ~ FormClass = uic.loadUiType(uiFilePath)[0]

class EditLegend(QDialog):
    closed = pyqtSignal()

    def __init__(self, parent=None, line_styles_dict={}):
        QDialog.__init__(self, parent)
        # Set up the user interface from Designer.
        uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'edit_legend.ui'))
        uic.loadUi(uiFilePath, self)
        self.setWindowTitle(self.tr('Edit line style and legend'))

        self.line_style_dict = {'-': 'Solid (-)',
                           '--': 'Dashed (--)',
                           '-.': 'DashDot (-.)',
                           ':': 'Dotted (..)',
                           }

        self.STYLES = line_styles_dict

        for line_id, line_style in self.STYLES.items():
            self.LINE_CB.addItem(line_style['label'])

        for line_style_name in self.line_style_dict.values():
            self.LINETYPE_CB.addItem(line_style_name)

        self.set_style_params(0, False)
        self.current_index = 0

        self.LINE_CB.currentIndexChanged.connect(self.set_style_params)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        # QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
        # QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
        QMetaObject.connectSlotsByName(self)

    def closeEvent(self, event):
        self.closed.emit()

    def set_style_params(self,current_index,update_style = True):
        if update_style: self.update_style_params(self.current_index)

        current_line = list(self.STYLES.keys())[current_index]
        #print('in set style parameter, current_index:', current_index, 'current_line:',current_line)

        self.LINELABEL_TXT.setText(self.STYLES[current_line]['label'])
        #print('color name',QColor(self.STYLES[current_line]['color']).name())
        self.LINECOLOR_BTN.setColor(QColor(self.STYLES[current_line]['color']))
        index = self.LINETYPE_CB.findText(self.line_style_dict[self.STYLES[current_line]['type']])
        self.LINETYPE_CB.setCurrentIndex(index)

        self.current_index = current_index

    def update_style_params(self,ln_idx):
        #print('in update_style_params')
        line_id = list(self.STYLES.keys())[ln_idx]
        self.STYLES[line_id]['label'] = self.LINELABEL_TXT.text()
        self.STYLES[line_id]['color'] = self.LINECOLOR_BTN.color().name()
        index = self.LINETYPE_CB.currentIndex()
        self.STYLES[line_id]['type'] = list(self.line_style_dict.keys())[index]

    def getData(self):
        self.update_style_params(self.current_index)
        return self.STYLES