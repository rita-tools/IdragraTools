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

from datetime import datetime

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMdiSubWindow, QTableView
from qgis.PyQt import QtSql

from data_manager.chart_widget import ChartWidget


class DataWindow(QMdiSubWindow):
    def __init__(self, parent=None, title='', dbPath='', sql=''):
        QMdiSubWindow.__init__(self, parent)
        self.setWindowTitle(title)
        # connect to db
        db = QtSql.QSqlDatabase.addDatabase('QSQLITE')
        db.setDatabaseName(dbPath)

        model = QtSql.QSqlTableModel()  # <--- NECESSARY TO RUN QUERY WITH  QSqlQueryModel?!?!
        self.dataModel = QtSql.QSqlQueryModel()  # <-- USED BY TABLE VIEW ...
        self.dataModel.setQuery(sql)

        self.CHART = None
        self.TV = None

    def exportData(self, fileName, sep=';'):
        textData = []
        rows = self.dataModel.rowCount()
        columns = self.dataModel.columnCount()

        headData = []
        for j in range(columns):
            headData.append(self.dataModel.headerData(j, Qt.Horizontal))

        textData.append(sep.join(headData))

        for i in range(rows):
            textRow = []
            for j in range(columns):
                textRow.append(str(self.dataModel.data(self.dataModel.index(i, j))))

            textData.append(sep.join(textRow))

        textData = '\n'.join(textData)
        f = None
        res = ''
        try:
            f = open(fileName, 'w')
            f.write(textData)
        except Exception as e:
            # do nothing
            res = str(e)
        finally:
            f.close()

        return res

    def updateWinList(self, winList):
        if self.CHART:
            self.CHART.updateWinList(winList)

    def createTable(self):
        self.TV = QTableView(self)
        self.TV.setModel(self.dataModel)
        self.setWidget(self.TV)

    def createPlot(self, plotConf=[]):
        # ['name','plot','color','style','axes','query']
        self.CHART = ChartWidget(self, '',advanced = True, digits = True)
        self.CHART.resize(0.9 * self.geometry().width(), self.geometry().height())
        self.CHART.setAxis(111, False)

        # get all data from query
        while (self.dataModel.canFetchMore()):
            self.dataModel.fetchMore()

        # print('plotConf: %s'%plotConf)
        for c, conf in enumerate(plotConf):
            ts = []
            vals = []
            # print('n. %s'%self.dataModel.rowCount())
            for row in range(self.dataModel.rowCount()):
                index = self.dataModel.index(row, 0)
                ts.append(datetime.strptime(str(self.dataModel.data(index)), '%Y-%m-%d'))
                index = self.dataModel.index(row, 1 + c)
                val = self.dataModel.data(index)
                try:
                    val = float(val)
                except:
                    val = None

                vals.append(val)

            if len(ts) > 0:
                if conf['style'] == 'b':
                    self.CHART.addBarPlot(x=ts, y=vals, width=1, color=conf['color'], name=conf['name'])
                elif conf['style'] == 's':
                    # print('conf: %s'%conf)
                    self.CHART.addTimeSerie(dateTimeList=ts,
                                            values=vals,
                                            lineType='-',
                                            color=conf['color'],
                                            name=conf['name'],
                                            yaxis=1,
                                            shadow = conf['color']+'29'
                                            )
                else:
                    # print('conf: %s'%conf)
                    self.CHART.addTimeSerie(dateTimeList=ts,
                                            values=vals,
                                            lineType=conf['style'],
                                            color=conf['color'],
                                            name=conf['name'],
                                            yaxis=1)

        self.CHART.setTitles(xlabs=None, ylabs=None, xTitle=None, yTitle=None, y2Title=None, mainTitle=None)
        self.home_xlim = self.CHART.ax.get_xlim()
        self.home_ylim = self.CHART.ax.get_ylim()
        self.setWidget(self.CHART)
