# -*- coding: utf-8 -*-

"""
/***************************************************************************
 mobidiQ
								 A QGIS plugin
 A plugin to import/export data to/from mobidic hydrological model
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
							  -------------------
		begin				: 2018-12-01
		copyright			: (C) 2018 by Enrico A. Chiaradia
		email				: enrico.chiaradia@yahoo.it
 ***************************************************************************/

/***************************************************************************
 *																		 *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or	 *
 *   (at your option) any later version.								   *
 *																		 *
 ***************************************************************************/
"""

__author__ = 'Enrico A. Chiaradia'
__date__ = '2018-12-01'
__copyright__ = '(C) 2018 by Enrico A. Chiaradia'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import sys
from PyQt5 import QtGui
from PyQt5.QtWidgets import QDialog,QAction,QMenu,QMessageBox,QPushButton,QWidget,QVBoxLayout,QComboBox,QLabel
		
import matplotlib
from matplotlib.backends.backend_qt5agg  import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
import matplotlib.dates as mdt
from matplotlib.patches import Polygon, Patch


import numpy as np

import random
from datetime import datetime

from matplotlib.sankey import Sankey

if (matplotlib.__version__).startswith('3.1.'):
	from data_manager.chart_tool_bar_3_1 import ChartToolBar
elif (matplotlib.__version__).startswith('3.5.'):
	from data_manager.chart_tool_bar_3_5 import ChartToolBar
else:
	from data_manager.chart_tool_bar_3_1 import ChartToolBar

class ChartWidget(QWidget):
	def __init__(self, parent=None, title = '', secondAxis = False, enableConnection = True,size= None):
		QWidget.__init__(self,parent) 
		
		self.setWindowTitle(title)
		
		# a figure instance to plot on
		if size is None:
			self.figure = plt.figure()
		else:
			figsize = (size[0] , size[1])
			self.figure = plt.figure(figsize =size)

		# this is the Canvas Widget that displays the `figure`
		# it takes the `figure` instance as a parameter to __init__
		self.canvas = FigureCanvas(self.figure)
		
		# this is the Navigation widget
		# it takes the Canvas widget and a parent
		#self.toolbar = NavigationToolbar(self.canvas, self)
		self.toolbar = ChartToolBar(self.canvas,parent)#self
		self.toolbar.update()

		if enableConnection:
			# Add
			self.WINCB = QComboBox(self)
			self.WINLBL = QLabel(self.tr('Connect to:'),self)
			self.WINCB.currentTextChanged.connect(self.parent().parent().manageSubConnection)
			self.toolbar.addWidget(self.WINLBL)
			self.toolbar.addWidget(self.WINCB)

		#self.line_edit.editingFinished.connect(self.do_something)
		# set the layout
		layout = QVBoxLayout()
		layout.addWidget(self.toolbar)
		layout.addWidget(self.canvas)
		#layout.addWidget(self.button)
		self.setLayout(layout)
		
		self.plotList = []
		#~ self.ax = self.figure.add_subplot(111)
		#~ if secondAxis: self.ax2 = self.ax.twinx()
		
		#~ legend = self.ax.legend(loc='upper center', shadow=True)
		self.h = []
		self.l = []
		
		self.cid = None
		self.cname = ''

		self.plotList = []
			
	def updateWinList(self,winList):
		oldItem = self.WINCB.currentText()
		self.WINCB.blockSignals(True)
		self.WINCB.clear()
		for winName in winList:
			self.WINCB.addItem(winName)
		
		self.WINCB.blockSignals(False)
		
		# set old text is exist
		self.WINCB.setCurrentText(oldItem)
		
	def setAxis(self,pos=111 , secondAxis=False, label =['First axes','Second axes']):
		axesToShare = None
		if len(self.plotList) > 0:
			axesToShare = self.plotList[0]

		self.ax = self.figure.add_subplot(pos, sharex=axesToShare, label=label[0])
		# ~ self.ax.spines['right'].set_visible(False)
		# ~ self.ax.spines['top'].set_visible(False)
		self.plotList.append(self.ax)
		if secondAxis:
			self.ax2 = self.ax.twinx()
			self.ax2.set_label(label[1])

		# legend = self.ax.legend(loc='upper center', shadow=True)
		self.h = []
		self.l = []

	def setYAxis(self,labels):
		#self.ax.set_ylim([-1, len(labels) + 0.1])
		self.ax.set_yticks(list(range(0, len(labels))))
		self.ax.set_yticklabels(labels)

		plt.tight_layout()
		
	def setTitles(self, xlabs = None, ylabs = None, xTitle = None, yTitle = None, y2Title = None, mainTitle = None):
		if xlabs is not None: self.ax.set_xticklabels(xlabs)
		if ylabs is not None: self.ax.set_yticklabels(ylabs)
		if mainTitle is not None: self.ax.set_title(mainTitle)
		if xTitle is not None: self.ax.set_xlabel(xTitle)
		if yTitle is not None: self.ax.set_ylabel(yTitle)
		#print('in setTitles, y2Title:',y2Title)
		if y2Title is not None: self.ax2.set_ylabel(y2Title)
		
		#ax.set_xticks(ind + width / 2)
		#plt.tight_layout()
		
		self.figure.autofmt_xdate()
		# beautify the x-labels
		#plt.gcf().autofmt_xdate()

	def flipAxes(self, x1 = None, y1 = None, x2 = None, y2 = None):
		if x1: self.ax.set_xlim(*list(reversed(self.ax.get_xlim())))
		if y1: self.ax.set_ylim(*list(reversed(self.ax.get_ylim())))
		if x2: self.ax2.set_xlim(*list(reversed(self.ax2.get_xlim())))
		if y2: self.ax2.set_ylim(*list(reversed(self.ax2.get_ylim())))

	def addTimeSerie_OLD(self, dateTimeList, values, lineType='-', color='r', name='lineplot', yaxis=1, shadow=False):
		dates = mdt.date2num(dateTimeList)

		if yaxis == 1:
			lines, = self.ax.plot_date(dates, values, lineType, color=color, label=name, picker=5)
		# cursor1 = FollowDotCursor(self.ax, x, y)
		else:
			lines, = self.ax2.plot_date(dates, values, lineType, color=color, label=name, picker=5)
		# cursor1 = FollowDotCursor(self.ax2, x, y)

		if shadow:
			verts = [(dates[0], 0), *zip(dates, values), (dates[-1], 0)]
			poly = Polygon(verts, facecolor=shadow, edgecolor=color)
			self.ax.add_patch(poly)
			lines = Patch(facecolor=shadow, edgecolor=color, label=name)

		self.plotList.append(lines)
		self.h.append(lines)
		self.l.append(name)
		# self.ax.legend(self.h, self.l)
		plt.legend(self.h, self.l)
		
	def addTimeSerie(self,dateTimeList,values,lineType='-',color='r',name = 'lineplot',yaxis = 1,shadow= False, addToLegend = True):
		if len(dateTimeList) > 0:
			dates = mdt.date2num(dateTimeList)

			if yaxis in [1, 'y']:
				lines, = self.ax.plot_date(dates, values, lineType, color=color, label=name, picker=5)
				if shadow:
					verts = [(dates[0], 0), *zip(dates, values), (dates[-1], 0)]
					poly = Polygon(verts, facecolor=shadow, edgecolor=color)
					self.ax.add_patch(poly)
					lines = Patch(facecolor=shadow, edgecolor=color, label=name, picker=5)
				# cursor1 = FollowDotCursor(self.ax, x, y)
				if addToLegend:
					self.h.append(lines)
					self.l.append(name)

			else:
				lines, = self.ax2.plot_date(dates, values, lineType, color=color, label=name, picker=5)
				if shadow:
					verts = [(dates[0], 0), *zip(dates, values), (dates[-1], 0)]
					poly = Polygon(verts, facecolor=shadow, edgecolor=color)
					self.ax2.add_patch(poly)
					lines = Patch(facecolor=shadow, edgecolor=color, label=name, picker=5)
				# cursor1 = FollowDotCursor(self.ax2, x, y)
				if addToLegend:
					self.h.append(lines)
					self.l.append(name)

			# self.plotList.append(lines)
			# self.ax.legend(self.h, self.l)
			# plt.legend(self.h, self.l)
			# plt.legend(handles = self.h, labels = self.l, loc='upper center', bbox_to_anchor=(0.5, -0.1),fancybox=True, shadow=True, ncol=len(self.h))
			plt.legend(handles=self.h, labels=self.l)#, loc='upper center', bbox_to_anchor=(0.5, 1.15), fancybox=True, shadow=True, ncol=len(self.h))

	def addFluxChart(self,flows=[25, 0, 60, -10, -20, -5, -15, -10, -40],
				   labels=['', '', '', 'First', 'Second', 'Third', 'Fourth',
						   'Fifth', 'Hurray!'],
				   orientations=[-1, 1, 0, 1, 1, 1, -1, -1, 0],
				   pathlengths=[0.25, 0.25, 0.25, 0.25, 0.25, 0.6, 0.25, 0.25,
								0.25],
				   patchlabel="Widget\nA"):

		#self.ax.get_xaxis().set_visible(False)
		#self.ax.get_yaxis().set_visible(False)
		self.ax.axis('off')

		sankey = Sankey(ax=self.ax, scale=0.01, offset=1, head_angle=160,format='%.0f', unit='')
		sankey.add(flows=flows, labels=labels, orientations=orientations, pathlengths=pathlengths,
				   patchlabel=patchlabel)  # Arguments to matplotlib.patches.PathPatch

		#sankey = Sankey(ax=self.ax, flows=flows, labels=labels, orientations=orientations)
		diagrams = sankey.finish()
		diagrams[0].texts[-1].set_color('r')
		diagrams[0].text.set_fontweight('bold')
		
	def addBarPlot(self,x,y,width=1,color='b',name = 'barplot'):
		
		# add some text for labels, title and axes ticks
		bars = self.ax.bar(x, y, width=width, color=color, edgecolor='white')
		self.plotList.append(bars)
		self.h.append(bars)
		self.l.append(name)
		#self.ax.legend(self.h, self.l)
		plt.legend(self.h, self.l)
		
		
		#~ h, l = self.ax.get_legend_handles_labels()
		#~ h += (bars,)
		#~ l += (name,)
		#~ self.ax.legend(h, l)

	def addLinePlot(self,x,y,lineType='-',color='r',name = 'lineplot',yaxis = 1):
		if yaxis == 1:
			lines, = self.ax.plot(x,y, lineType,color=color)
			#cursor1 = FollowDotCursor(self.ax, x, y)
		else:
			lines, = self.ax2.plot(x,y, lineType,color=color)
			#cursor1 = FollowDotCursor(self.ax2, x, y)
				
		self.plotList.append(lines)
		self.h.append(lines)
		self.l.append(name)
		self.ax.legend(self.h, self.l)
		
	def addSinglePointPlot(self,x,y,color='b',yaxis=1):
		if yaxis == 1:
			points, = self.ax.plot([x], [y], marker='o', markersize=3, color=color)
		else:
			points, = self.ax2.plot([x], [y], marker='o', markersize=3, color=color)
	
		
	def addInfVertical(self,x):
		self.ax.axvline(x=x, color='k', linestyle='-')
		
	def drawConduit(self,x1,y1,x2,y2,h):
		xs = [x1,x2,x2, x1]
		ys = [y1,y2,y2+h, y1+h]
		xy = np.column_stack([xs, ys])
		#print 'xy:',xy
		poly = Polygon(xy,edgecolor='black',facecolor='lightgray')
		self.ax.add_patch(poly)
		self.ax.autoscale_view()
		
	def drawManhole(self,Hb,Ht,pos,diam=1):
		xs = [pos-0.5*diam,pos+0.5*diam,pos+0.5*diam, pos-0.5*diam]
		ys = [Hb,Hb,Ht, Ht]
		xy = np.column_stack([xs, ys])
		#print 'xy:',xy
		poly = Polygon(xy,edgecolor='black',facecolor='gray')
		self.ax.add_patch(poly)
		self.ax.autoscale_view()


	def drawRectangle(self,xmin,xmax,ymin,ymax,facecolor='green',edgecolor='black'):
		xs = [xmin, xmax, xmax, xmin]
		ys = [ymin, ymin, ymax, ymax]
		xy = np.column_stack([xs, ys])
		poly = Polygon(xy,edgecolor=edgecolor,facecolor=facecolor)
		self.ax.add_patch(poly)
		self.ax.autoscale_view()

	def addHeadMap(self,data2D,xLabels,yLabels,showX=False, cRamp='viridis'):
		if data2D is None:
			self.addEmptyBox()
		else:
			self.pcm = self.ax.pcolorfast(data2D,cmap=cRamp)
			# We want to show all ticks...
			self.ax.set_yticks(np.arange(len(yLabels))+0.5)
			# ... and label them with the respective list entries
			self.ax.set_yticklabels(yLabels)

			self.ax.get_xaxis().set_visible(showX)
			self.figure.colorbar(self.pcm, ax=self.ax)

	def addEmptyBox(self):
		pass

	def fixLayout(self):
		self.figure.tight_layout()

	def plot(self):
		''' plot some random stuff '''
		# random data
		ind = range(10)
		width = 1
		data = [random.random() for i in ind]
		
		# discards the old graph
		#self.ax.hold(False)
		
		# create add plot
		self.addBarPlot(ind,data)
		#self.addLinePlot(ind,data)
		# refresh canvas
		self.canvas.draw()
		
	def addText(self, txt, xpos,ypos,rotAngle = 0.0):
		#print 'add text %s in (%s,%s)'%(txt,xpos, ypos)
		try:
			self.ax.text(xpos, ypos, txt,rotation = rotAngle, rotation_mode	='anchor',ha	= 'center',va	= 'center' )
			self.canvas.draw()
		except:
			pass
		
	def updateXLimits(self,event_ax):
		#print("updated xlims: ", event_ax.get_xlim())
		left, right = event_ax.get_xlim()
		self.ax.set_xlim(left, right,False)
		self.toolbar.push_current()
		self.figure.canvas.draw()

		
	def updateYLimits(self,event_ax):
		#print("updated ylims: ", event_ax.get_ylim())
		bottom, top = event_ax.get_ylim()
		self.ax.set_ylim(bottom, top,False)
		self.figure.canvas.draw()

	def saveToFile(self,fileName,w,h):
		self.figure.savefig(fileName,format='png')
		
		
if __name__ == '__console__':
	#app = QtGui.QApplication(sys.argv)

	main = Window()
	main.show()

	#sys.exit(app.exec_())