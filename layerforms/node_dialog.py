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

import sys
import os
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from qgis.PyQt import QtSql

from IdragraTools.layerforms.utils import *
from IdragraTools.tools.array_table_model import ArrayTableModel
from IdragraTools.data_manager.chart_widget import ChartWidget

from layerforms.utils import updateLineEdit, updateSelected, updateComboItems


def formOpen(dialog, layerid, featureid):
    global myDialog
    myDialog = dialog
    global layer
    layer = layerid
    global feature
    feature = featureid

    # prepare a list of widget to enable/disable
    global objToBeEnabledList
    objToBeEnabledList = []

    global actTrsLE
    global actRatioLE

    # global irrTimeLE
    actTrsLE = myDialog.findChild(QLineEdit, 'act_trshold')
    actRatioLE = myDialog.findChild(QLineEdit, 'act_ratio')

    actTrsLE.setHidden(True)
    actRatioLE.setHidden(True)

    tr = qgis.utils.plugins['IdragraTools'].tr

    global nodeTypes
    # populate combo
    nodeTypes = {tr('[1] Generic water source'): 1,
                 tr('[11] Monitored water source'): 11,
                 tr('[12] Runoff collactor'): 12,
                 tr('[13] Threshold rule water source'): 13,
                 tr('[14] On demand unlimited water source'): 14,
                 tr('[2] Junctions'): 2,
                 tr('[3] Water distributor'): 3
                 }

    setupCombo('node_type', nodeTypes)

    # enable/disable edit mode
    setEditMode(layer.isEditable())

    TRS_BTN = myDialog.findChild(QPushButton, 'trs_BTN')
    # for some reason, forms are initialized twice ...
    if TRS_BTN.receivers(TRS_BTN.clicked) == 0:
        TRS_BTN.clicked.connect(showEditDialog)

    PLOT_ACTDISC_BTN = myDialog.findChild(QPushButton, 'PLOT_ACTDISC_BTN')
    # for some reason, forms are initialized twice ...
    if PLOT_ACTDISC_BTN.receivers(PLOT_ACTDISC_BTN.clicked) == 0:
        PLOT_ACTDISC_BTN.clicked.connect(lambda: plotActualDischarge(int(myDialog.findChild(QLineEdit, 'id').text()),
                                                                 myDialog.findChild(QLineEdit, 'name').text()))


def setupCombo(attrName, allItems):
    CB = myDialog.findChild(QComboBox, attrName + '_CB')
    objToBeEnabledList.append(CB)
    updateComboItems(CB, allItems)
    LE = myDialog.findChild(QLineEdit, attrName)
    LE.setHidden(True)
    CB.currentIndexChanged[str].connect(lambda txt: hideShowElem(txt, allItems, LE))
    #CB.currentIndexChanged[str].connect(lambda txt: updateLineEdit(txt, allItems, LE))
    #LE.textChanged[str].connect(lambda txt: updateSelected(CB, LE, allItems))
    updateSelected(CB, LE, allItems)

def hideShowElem(txt, allItems, LE):
    updateLineEdit(txt, allItems, LE)
    txt = nodeTypes[txt]
    attrList = ['q_sum', 'q_win', 'sum_start', 'sum_end', 'win_start', 'win_end',
                'trs_BTN','PLOT_ACTDISC_BTN']
    visList = []
    if txt == 1:
        visList = [True, True, True, True, True, True, True,True]
    elif txt == 11:
        visList = [True, False, False, False, False, False, False,True]
    elif txt == 12:
        visList = [False, False, False, False, False, False, False,False]
    elif txt == 13:
        visList = [True, False, False, False, False, False, True,False]
    elif txt == 14:
        visList = [False, False, False, False, False, False, False,False]
    elif txt == 2:
        visList = [False, False, False, False, False, False, False,False]
    elif txt == 3:
        visList = [False, False, False, False, False, False, False,False]
    else:
        pass

    for label, flag in zip(attrList, visList):
        test = myDialog.findChild(QLineEdit, label)
        if test: test.setHidden(not flag)
        test = myDialog.findChild(QLabel, label + '_LB')
        if test: test.setHidden(not flag)
        test = myDialog.findChild(QSpinBox, label)
        if test: test.setHidden(not flag)
        test = myDialog.findChild(QPushButton, label)
        if test: test.setHidden(not flag)


def setEditMode(mode):
    try:
        for obj in objToBeEnabledList:
            obj.setEnabled(mode)
    except Exception as e:
        print('error: %s' % str(e))


def showEditDialog():
    tr = qgis.utils.plugins['IdragraTools'].tr
    # extract data
    t = parseString(actTrsLE.text(),' ',toSpecialFloat)

    v = parseString(actRatioLE.text(),' ',toSpecialFloat)

    data = list(zip(t, v))
    data = list(map(list, data))

    header = [tr('Activation thresholds'), tr('Flow rate ratio')]
    # make a dialog
    from IdragraTools.layerforms.table_dialog import TableDialog
    dlg = TableDialog(parent=myDialog, title='View/edit table')
    # make the model with data
    global aModel
    aModel = ArrayTableModel(dlg, data, header)

    if not layer.isEditable():
        aModel.setEditableColumn([])

    dlg.setEditMode(layer.isEditable())
    dlg.TV.setModel(aModel)
    # set size from qgis habits
    dlg.resize(0.5 * myDialog.geometry().width(), myDialog.geometry().height())
    #dlg.finished.connect(updateTableValues)
    dlg.show()
    result = dlg.exec()
    # See if OK was pressed
    if result == 1:
        updateTableValues()

def updateTableValues():
    if layer.isEditable():
        myDialog.changeAttribute('act_trshold', ' '.join(list(map(toSpecialFloat, aModel.getColumnValue(0)))))
        myDialog.changeAttribute('act_ratio', ' '.join(list(map(toSpecialFloat, aModel.getColumnValue(1)))))

def plotActualDischarge(wsId,name):
    # make a dialog
    #from IdragraTools.layerforms.chart_dialog import ChartDialog
    tr = qgis.utils.plugins['IdragraTools'].tr

    cw = ChartWidget(myDialog, tr('Measured discharges from %s'%name),False,False)
    cw.setAxis(pos=111, secondAxis=False, label=[tr('Main plot')])

    # add timeseries
    plotList = [
                {'name':qgis.utils.plugins['IdragraTools'].WATERSOURCENAME['node_act_disc'],
                 'plot':'True','color':'#416FA6','style': '-','axes':'y',
                 'table':'node_act_disc','id':wsId},
                ]

    y1Title = []
    y2Title = []
    for p in plotList:
        shadow = False
        # get data
        dateTimeList, values = qgis.utils.plugins['IdragraTools'].DBM.getTimeSeries(p['table'],p['id'])
        cw.addTimeSerie(dateTimeList,values,lineType='-',color=p['color'],name = p['name'],yaxis = p['axes'],shadow= shadow)
        if p['axes']=='y': y1Title.append(p['name'])
        if p['axes']=='y2': y2Title.append(p['name'])

    if len(y2Title)==0:
        y2Title = None
    else:
        y2Title = ', '.join(y2Title)

    # set title
    cw.setTitles(xlabs = None, ylabs = None, xTitle = None, yTitle = ', '.join(y1Title),
                  y2Title = y2Title, mainTitle = None)

    # add data to the chart
    # add chart to dialog
    dlg = QMainWindow(myDialog)
    dlg.setCentralWidget(cw)
    dlg.show()


if __name__ == '__console__':
    pass
