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

import os
import sys
from qgis.PyQt import QtGui
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QDialog,QMenu,QMessageBox,QPushButton,QVBoxLayout

from matplotlib.backends.backend_qt5agg  import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
import matplotlib.dates as mdt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Polygon,Patch


import numpy as np

import random
from datetime import datetime

from data_manager.chart_tool_bar import ChartToolBar


class ChartDialog(QDialog):
	sizeChanged = pyqtSignal()

	def __init__(self, parent=None, title = '', secondAxis = True):
		QDialog.__init__(self,parent) 
		
		self.setWindowTitle(title)
		
		# a figure instance to plot on
		self.figure = plt.figure()

		# this is the Canvas Widget that displays the `figure`
		# it takes the `figure` instance as a parameter to __init__
		self.canvas = FigureCanvas(self.figure)
		
		# this is the Navigation widget
		# it takes the Canvas widget and a parent
		#self.toolbar = NavigationToolbar(self.canvas, self)
		self.toolbar = ChartToolBar(self.canvas,self)

		# Just some button connected to `plot` method
		self.button = QPushButton('Plot')
		self.button.clicked.connect(self.plot)

		# set the layout
		layout = QVBoxLayout()
		layout.addWidget(self.toolbar)
		layout.addWidget(self.canvas)
		#layout.addWidget(self.button)
		self.setLayout(layout)
		
		self.plotList = []

	def resizeEvent(self, event):
		self.sizeChanged.emit()

	def setAxis(self,pos=111 , secondAxis=False, share = True,label = ['First axis','Second axis']):
		axesToShare = None
		if len(self.plotList)>0:
			axesToShare = self.plotList[0] 
			
		self.ax = self.figure.add_subplot(pos,sharex = axesToShare,label = label[0])
		#~ self.ax.spines['right'].set_visible(False)
		#~ self.ax.spines['top'].set_visible(False)
		self.plotList.append(self.ax)
		if secondAxis:
			self.ax2 = self.ax.twinx()
			self.ax2.set_label(label[1])

		#legend = self.ax.legend(loc='upper center', shadow=True)
		self.h = []
		self.l = []
		
	def setTitles(self, xlabs = None, ylabs = None, xTitle = None, yTitle = None, y2Title = None, mainTitle = None):
		if xlabs is not None: self.ax.set_xticklabels(xlabs)
		if ylabs is not None: self.ax.set_yticklabels(ylabs)
		if mainTitle is not None: self.ax.set_title(mainTitle)
		if xTitle is not None: self.ax.set_xlabel(xTitle)
		if yTitle is not None: self.ax.set_ylabel(yTitle)
		print('in setTitles:',y2Title)
		if y2Title is not None:
			self.ax2.set_ylabel(y2Title)
		
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
		
	def addTimeSerie(self,dateTimeList,values,lineType='-',color='r',name = 'lineplot',yaxis = 1, shadow = False):
		if len(dateTimeList)>0:
			dates = mdt.date2num(dateTimeList)
					
			if yaxis in [1,'y']:
				lines, = self.ax.plot_date(dates,values, lineType,color=color,label=name)
				if shadow:
					verts = [(dates[0], 0), *zip(dates,values), (dates[-1], 0)]
					poly = Polygon(verts, facecolor=shadow, edgecolor=color)
					self.ax.add_patch(poly)
					lines =  Patch(facecolor=shadow, edgecolor=color, label=name)
				#cursor1 = FollowDotCursor(self.ax, x, y)
				self.h.append(lines)
				self.l.append(name)
			
			else:
				lines, = self.ax2.plot_date(dates,values, lineType,color=color,label=name)
				if shadow:
					verts = [(dates[0], 0), *zip(dates,values), (dates[-1], 0)]
					poly = Polygon(verts, facecolor=shadow, edgecolor=color)
					self.ax2.add_patch(poly)
					lines =  Patch(facecolor=shadow, edgecolor=color, label=name)
				#cursor1 = FollowDotCursor(self.ax2, x, y)
				self.h.append(lines)
				self.l.append(name)
				
			#self.plotList.append(lines)
			#self.ax.legend(self.h, self.l)
			#plt.legend(self.h, self.l)
			#plt.legend(handles = self.h, labels = self.l, loc='upper center', bbox_to_anchor=(0.5, -0.1),fancybox=True, shadow=True, ncol=len(self.h))
			plt.legend(handles = self.h, labels = self.l, loc='upper center',
					   bbox_to_anchor=(0.5, 1.15), fancybox=True, shadow=True,
					   ncol=len(self.h))
			
	def addBarPlot(self,x,y,width=1,color='b',name = 'barplot'):
		
		# add some text for labels, title and axes ticks
		bars = self.ax.bar(x, y, width=width, color=color, edgecolor='white')
		self.plotList.append(bars)
		
		h, l = self.ax.get_legend_handles_labels()
		h += (bars,)
		l += (name,)
		self.ax.legend(h, l)

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
		
	def plot(self):
		''' plot some random stuff '''
		# random data
		ind = range(10)
		width = 1
		data = [random.random() for i in ind]
		
		# discards the old graph
		self.ax.hold(False)
		
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
		
	def updateLimits(self):
		# recompute the ax.dataLim
		self.ax.relim()
		# update ax.viewLim using the new dataLim
		self.ax.autoscale_view()

	def addEmptyBox(self):
		self.ax.plot([], [])
		#self.ax.set_visible(False)
		self.ax.set_axis_off()

		font0 = FontProperties()
		alignment = {'horizontalalignment': 'center', 'verticalalignment': 'baseline'}
		self.ax.text(0.5, 0.9, 'Not available data', fontproperties=font0, **alignment)

		# self.ax.text(100, 0.5, 'Not available data', style='italic',
		# 		fontproperties=font0, **alignment)

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


	def fixLayout(self):
		self.figure.tight_layout()

if __name__ == '__console__':
	#app = QtGui.QApplication(sys.argv)

	main = Window()
	main.show()

	#sys.exit(app.exec())
