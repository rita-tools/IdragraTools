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

import numpy as np
import math
from math import floor,ceil
import struct 

import os

import scipy.io as sio

from qgis.PyQt.QtCore import QObject

from qgis.core import (Qgis,
									QgsRasterBlock,
									QgsErrorMessage,
									QgsProcessingException,
									QgsProcessing,
									QgsFeatureSink,
									QgsProcessingAlgorithm,
									QgsProcessingParameterFeatureSource,
									QgsProcessingParameterFeatureSink,
									QgsProcessingParameterFile,
									QgsVectorLayer,
									QgsProcessingParameterRasterLayer,
									QgsProcessingParameterRasterDestination,
									QgsProcessingParameterEnum,
									QgsCoordinateReferenceSystem,
									QgsApplication,
									QgsField,
									QgsFields,
									QgsPointXY,
									QgsFeature,
									QgsGeometry,
									QgsProject,
									QgsAction,
									QgsWkbTypes,
									QgsRectangle,
									QgsRasterFileWriter)

class GisGrid(QObject):
	def __init__(self,ncols=1, nrows=1, xcell=0, ycell=0, dx=1, dy=1,nodata = -3.4028234663852886e+038,EPSGid = 32632,progress = None,parent=None):
		QObject.__init__(self,parent)
		self.progress = progress
		self.initGrid(ncols, nrows, xcell, ycell, dx, dy,nodata,EPSGid)
				
	def initGrid(self,ncols, nrows, xcell, ycell, dx, dy,nodata,EPSGid):
		# store other important georeferencing data
		#~ print 'ncols:',ncols
		#~ print 'nrows:',nrows
		self.nrows = int(nrows)
		self.ncols = int(ncols)
		self.xcell = float(xcell)
		self.ycell = float(ycell)
		self.dx = float(dx)
		self.dy = float(dy)
		self.nodata = float(nodata)
		# create two numpy 2d-array, the first with cell xcoord and the second with cell ycoord
		# coords are zero based from the top left cell (0,0)
		self.cols = np.arange(self.ncols)
		self.cols = np.array([self.cols,]*self.nrows)
		self.rows = np.arange(self.nrows)
		self.rows = np.array([self.rows,]*self.ncols).transpose()
		# create an empty numpy 2d-array to store value
		self.data = np.zeros((self.nrows,self.ncols), dtype=float)+self.nodata
		self.extent = QgsRectangle(xcell, ycell, xcell+dx*ncols, ycell+dy*nrows)
		self.CRS = QgsCoordinateReferenceSystem()
		self.EPSGid = EPSGid
		if self.EPSGid: self.CRS.createFromSrid(self.EPSGid)
		
	def fitToLayer(self,layer,dx,dy,nodata = -3.4028234663852886e+038):
		extent = layer.extent()
		crsId = layer.sourceCrs().EpsgCrsId()
		self.fitToExtent(extent,dx,dy,nodata,crsId)
		
	def fitToExtent(self,extent,dx,dy,nodata = -3.4028234663852886e+038,EPSGid= 32632):
		# calcolate raster dimension
		xll = extent.xMinimum()
		yll = extent.yMinimum()
		xur = extent.xMaximum()
		yur = extent.yMaximum()
		
		#~ print 'ext:',xll,yll,xur,yur
		#~ print 'cellsize',dx,dy

		ncols = int(math.ceil((xur-xll)/dx))
		nrows = int(math.ceil((yur-yll)/dy))
		
		self.initGrid(ncols, nrows, xll, yll, dx, dy,nodata,EPSGid)
		
	def fitToGrid(self,grid):
		self.initGrid(grid.ncols, grid.nrows, grid.xcell, grid.ycell, grid.dx, grid.dy,grid.nodata,grid.EPSGid)
		
	def setToScalar(self,value):
		self.data = self.data*0.0+value
		
	def copy(self,newValue = None):
		newGrid = GisGrid()
		newGrid.fitToGrid(self)
		if newValue is None:
			newGrid.data = self.data
		else:
			newGrid.setToScalar(float(newValue))
			
		return newGrid
		
	def getValue(self,x,y):
		c,r = self.coordToCell(x, y)
		res = None
		if (c<0) or (c>=self.ncols):
			#print('c:%s - ncols: %s'%(c,self.ncols))
			return res
		
		if (r<0) or (r>=self.nrows):
			#print('r:%s - nrows: %s'%(r,self.nrows))
			return res
		
		res = self.data[r,c]
		if np.isnan(res): res = None
		#print('res:',res,'r:',r,'c:',c)
		return res
			
	def __add__(self, other):
		newGrid = GisGrid()
		newGrid.fitToGrid(self)
		if isinstance(other, GisGrid): newGrid.data = self.getMaskedData()+other.getMaskedData()
		else: newGrid.data = self.getMaskedData()+other
		newGrid.fixData()
		return newGrid
		
	def __sub__(self,other):
		newGrid = GisGrid()
		newGrid.fitToGrid(self)
		if isinstance(other, GisGrid): newGrid.data = self.getMaskedData()-other.getMaskedData()
		else: newGrid.data = self.getMaskedData()-other
		newGrid.fixData()
		return newGrid
		
	def __mul__(self,other):
		newGrid = GisGrid()
		newGrid.fitToGrid(self)
		if isinstance(other, GisGrid): newGrid.data = self.getMaskedData()*other.getMaskedData()
		else: newGrid.data = self.getMaskedData()*other
		newGrid.fixData()
		return newGrid
		
	def __div__(self,other):
		newGrid = GisGrid()
		newGrid.fitToGrid(self)
		if isinstance(other, GisGrid): newGrid.data = self.getMaskedData()/other.getMaskedData()
		else: newGrid.data = self.getMaskedData()/other
		newGrid.fixData()
		return newGrid
		
	def __pow__(self,exponent):
		newGrid = GisGrid()
		newGrid.fitToGrid(self)
		if isinstance(exponent, GisGrid): newGrid.data = np.power(self.getMaskedData(),exponent.getMaskedData())
		else: newGrid.data = self.getMaskedData()**exponent
		newGrid.fixData()
		return newGrid
		
	def __gt__(self,other):
		newGrid = GisGrid()
		newGrid.fitToGrid(self)
		if isinstance(other, GisGrid): newGrid.data = np.greater(self.getMaskedData(),other.getMaskedData())
		else: newGrid.data = np.greater(self.getMaskedData(),other)
		newGrid.fixData()
		return newGrid
		
	def max(self):
		return np.nanmax(self.getMaskedData())
		
	def min(self):
		return np.nanmin(self.getMaskedData())
		
	def mean(self):
		return np.nanmean(self.getMaskedData())
		
	def sum(self):
		return np.nansum(self.getMaskedData())
		
	def count(self):
		return np.count_nonzero(~np.isnan(self.getMaskedData()))
		
	def getMaskedData(self):
		return  np.ma.masked_where((self.data == self.nodata), self.data)
		
	def fixData(self):
		self.data = np.ma.filled(self.data,self.nodata)
		
	def coordToCell(self, xpos, ypos):
		"""
		coordToCell:		convert geographical coordinates to cell coordinates
								from the top left cell and zero based (like matrix).
								Return a tuple of value (col, row)
		Arguments:
		xpos			 : the longitude
		ypos			 : the latitude
		"""
		#~ col = int(round((xpos-self.xcell)/self.dx))
		#~ row = self.nrows - int(round((ypos-self.ycell)/self.dy))
		col = int(floor((xpos-self.xcell)/self.dx))
		
		#row = self.nrows - int(floor((ypos-self.ycell)/self.dy))
		row = self.nrows - int(ceil((ypos-self.ycell)/self.dy))
		#row = int(round((ypos-self.ycell)/self.dy))
		#print('xcell:',self.xcell,'xpos:',xpos,'self.dx:',self.dx,'ncols:',self.ncols,'col:',col)
		#print('ycell:',self.ycell,'ypos:',ypos,'self.dy:',self.dy,'nrows:',self.nrows,'row:',row)
		return col,row
		
	def cellToCoord(self, col, row):
		"""
		cellToCoord	 : convert cell coordinates to geographical coordinates.
					  Return a tuple of value (x_lon, y_lat)
		Arguments:
		col			 : the column index of the cell (zero based)
		row			 : the row index of the cell (zero based)
		"""
		x_lon = self.dx*col+0.5*self.dx+self.xcell
		y_lat = self.dy*(self.nrows-(row+1))+self.ycell+0.5*self.dy
		return x_lon, y_lat
		
	def sub2ind(self,array_shape = None, rows = 0, cols = 0, oneBased = True, fortran = False):
		#~ print 'in sub2ind'
		#~ print 'rr:',rr
		#~ print 'cc:',cc
		# coordToCell are zero based
		#~ if isinstance(rows,list): rows = [x+1 for x in rows]
		#~ else: rows = rows+1
		
		#~ if isinstance(cols,list): cols = [x+1 for x in cols]
		#~ else: cols = cols+1
		
		rows+=1
		cols+=1
		
		if array_shape == None: array_shape = self.data.shape
		#~ idx = (rows)*array_shape[1] + (cols)
		idx = (cols-1)*array_shape[0] +(array_shape[0] - rows+2)
		#~ if fortran: idx = (cols)*array_shape[0] + (rows)
					
		#~ if oneBased: 
			#~ idx = idx+1
			
		return idx
		
	def sub2indNew(self,array_shape = None, r = 0, c = 0, oneBased = True, fortran = False):
		if array_shape == None: array_shape = self.data.shape
		#print 'array_shape:',array_shape
		
		nrows = array_shape[0]
		ncols = array_shape[1]
		
		#print 'nrows:',nrows
		#print 'ncols:',ncols
		
		r = np.array(r)
		c = np.array(c)
		
		if oneBased: offset = 1
		else: offset = 0
				
		byRow = r*ncols+(c+offset)
		byCol = c*nrows+(r+offset)
		
		if fortran: idx = byCol.tolist()
		else: idx = byRow.tolist()
			
		return idx
		
	def sub2indMat(self,array_shape = None, r = 0, c = 0):
		# r and c are zero based coordinate while the function return the one based index
		# following row order
		
		if array_shape == None: array_shape = self.data.shape
		#print 'array_shape:',array_shape
		
		nrows = array_shape[0]
		ncols = array_shape[1]
		
		#print 'nrows:',nrows
		#print 'ncols:',ncols
		
		r = np.array(r)+1
		c = np.array(c)+1
		
		idx = (c-1)*nrows+r
			
		return idx
		
		
	def ind2sub(self,array_shape = None, ind = 0):
		if array_shape == None: array_shape = self.data.shape
		rows = (ind.astype('int') / array_shape[1])
		cols = (ind.astype('int') % array_shape[1]) # or numpy.mod(ind.astype('int'), array_shape[1])
		return (rows, cols)
		
	def getIndex(self,item):
		itemIndex = np.nonzero(self.data==item)
		itemIndex = self.sub2ind(array_shape = None, rows = itemIndex[0][0], cols = itemIndex[1][0])
		return itemIndex

	def getUniqueValues(self):
		uniqueVals = np.unique(self.data).tolist()
		# remove nodata
		uniqueVals.remove(self.nodata)
		return uniqueVals

	def saveAsGDAL(self, outputFile,dataType = Qgis.Float32):
		# create raster with array data
		outputFormat = QgsRasterFileWriter.driverForExtension(os.path.splitext(outputFile)[1])

		writer = QgsRasterFileWriter(outputFile)
		writer.setOutputProviderKey('gdal')
		writer.setOutputFormat(outputFormat)

		provider = writer.createOneBandRaster(dataType, self.ncols, self.nrows, self.extent, self.CRS)
		if provider is None:
			raise QgsProcessingException(self.tr("Could not create raster output: {}").format(outputFile))
		if not provider.isValid():
			raise QgsProcessingException(self.tr("Could not create raster output {}: {}").format(outputFile,
																								 provider.error().message(
																									 QgsErrorMessage.Text)))

		provider.setNoDataValue(1, self.nodata)

		block = QgsRasterBlock(dataType, self.ncols, 1)

		total = 100.0 / self.nrows if self.nrows else 0
		for i in range(self.nrows):

			# data = [3.0] * ncols
			# slice = self.data[self.nrows-i-1][:]
			slice = self.data[i][:]
			# feedback.pushInfo(self.tr('i: %s, n. of data: %s, ncols: %s')%(i, len(data), ncols))

			block.setData(struct.pack('{}f'.format(self.ncols), *slice))
			provider.writeBlock(block, 1, 0, i)
			if self.progress: self.progress.setProgress(100 * float(i) / self.nrows)

		provider.setEditable(False)
		
	def saveAsGDALFIXED(self,outputFile,dataType = Qgis.Float32):
		print('cols',self.ncols)
		print('rows', self.nrows)
		print('in saveAsGDAL, array shape',self.data.shape)
		# create raster with array data
		outputFormat = QgsRasterFileWriter.driverForExtension(os.path.splitext(outputFile)[1])

		writer = QgsRasterFileWriter(outputFile)
		writer.setOutputProviderKey('gdal')
		writer.setOutputFormat(outputFormat)
		
		provider = writer.createOneBandRaster(dataType , self.ncols, self.nrows, self.extent, self.CRS)
		if provider is None:
			raise QgsProcessingException(self.tr("Could not create raster output: {}").format(outputFile))
		if not provider.isValid():
			raise QgsProcessingException(self.tr("Could not create raster output {}: {}").format(outputFile,
																								provider.error().message(QgsErrorMessage.Text)))

		provider.setNoDataValue(1, self.nodata)
		print('size of array elem',sys.getsizeof(self.data[0][0]))
		print('size of array item', sys.getsizeof(self.data[0][0].item()))
		print('size of int*int', sys.getsizeof(1 * 1))
		print('size of float * float', sys.getsizeof(1.0*1.0))
		print('size of float(array)', sys.getsizeof(float(self.data[0][0])))

		#block = QgsRasterBlock(dataType, self.ncols, 1)
		block = QgsRasterBlock(dataType, self.ncols, self.nrows)
		total = 100.0 / self.nrows if self.nrows else 0
		for i in range(self.nrows):
			
			#data = [3.0] * ncols
			#slice = self.data[self.nrows-i-1][:]
			#slice = self.data[i][:]
			#print('add record of %s elements'%len(slice))
			#feedback.pushInfo(self.tr('i: %s, n. of data: %s, ncols: %s')%(i, len(data), ncols))
		
			#block.setData(struct.pack('{}f'.format(self.ncols), *slice))
			for j in range(0, self.ncols):
				#block.setValue(i, j, float(self.data[i][j]))#self.data[i][j].item()
				block.setValue(i, j, self.data[i][j])  # self.data[i][j].item()

			#provider.writeBlock(block, 1, 0, i)
			if self.progress: self.progress.setProgress(100*float(i)/self.nrows)

		provider.writeBlock(block, band=1)

		provider.setEditable(False)
		
	def saveAsASC(self,filename,d=8,useCellSize = False):
		"""
		savegrid		: save current grid in a Esri-like ASCII grid file.
		Arguments:
		filename		: the complete name of the new file (path + filename)
		d				 : decimal digit
		useCellSize	 : if True, write cellsize parameter instead of dx and dy
		"""
		if self.progress: self.progress.setProgress(0)
		try:
			# use of with to automatically close the file
			with open(filename,'w') as f:
				f.write('ncols ' + str(self.ncols) + '\n')
				f.write('nrows ' + str(self.nrows) + '\n')
				f.write('xllcorner ' + str(self.xcell) + '\n')
				f.write('yllcorner ' + str(self.ycell) + '\n')
				if useCellSize:
					f.write('cellsize ' + str(self.dx) + '\n')
				else:
					f.write('dx ' + str(self.dx) + '\n')
					f.write('dy ' + str(self.dy) + '\n')

				if d == 0:
					f.write('nodata_value ' + str(int(self.nodata))+ '\n')
				else:
					f.write('nodata_value ' + str(round(self.nodata,d))+ '\n')

				s = ''
				c = 0

				i=0
				# repalce nan with nodata
				idx = np.where(np.isnan(self.data))
				dataToPrint = self.data
				dataToPrint[idx] = self.nodata

				if d ==0:
					for row in dataToPrint:
						i += 1
						if self.progress: self.progress.setProgress(100 * float(i) / self.nrows)
						for el in row:
							# print len(el)
							s = s + str(int(round(el, d)))
							c = c + 1
							# add space if not EOF
							if c % self.ncols != 0:
								s = s + ' '
							else:
								s = s + '\n'

				else:
					for row in dataToPrint:
						i +=1
						if self.progress: self.progress.setProgress(100*float(i)/self.nrows)
						for el in row:
							#print len(el)
							s = s + str(round(el,d))
							c = c+1
							#add space if not EOF
							if c%self.ncols != 0:
								s = s + ' '
							else:
								s = s + '\n'

				f.write(s)
				#f.write('projection ' + str(self.hd.prj) + '\n')
				#f.write('notes ' + str(self.hd.note))
				# TODO: this line causes memory issue, probably because self.progress is lost
				#if self.progress: self.progress.pushInfo(self.tr('Grid exported to %s')%(filename))
		except Exception as e:
			#print 'Cannot save file: %s' %filename
			if self.progress: self.progress.error(self.tr('Cannot save to %s because %s') %(filename,str(e)))

	def openFromMAT(self,filename,name,nodata = -3.4028234663852886e+038, EPSGid = 32632, progress = None):
		# open mat file
		data = sio.loadmat(filename)
		
		# get variable matrix
		dataArray = data[name]
		dataArray[np.isnan(dataArray)]=nodata
		
		# get xll, yll, grid_size,
		xcell = data['xll'][0][0]
		ycell = data['yll'][0][0]
		cell_size = data['grid_size'][0][0]
		
		# adjust xll, yll to the corner
		xll = xcell-0.5*cell_size
		yll = ycell-0.5*cell_size
		
		# get row and column
		nrows, ncols = dataArray.shape
				
		self.initGrid(ncols, nrows, xll, yll, cell_size, cell_size,nodata,EPSGid)
		# update data matrix
		self.data = dataArray

	def saveAsMAT(self,filename,name,progress = None):
		dataDict = {}
		
		if os.path.exists(filename):
			dataDict = sio.loadmat(filename)
		
		dataDict['ncols'] = np.array([[self.ncols]], dtype=np.uint8)
		dataDict['nrows'] = np.array([[self.nrows]], dtype=np.uint8)
		dataDict['xll'] = np.array([[self.xcell+self.dx*0.5]])
		dataDict['yll'] = np.array([[self.ycell+self.dy*0.5]])
		dataDict['grid_size'] = np.array([[self.dx]])
		dataDict['grid_size2'] = np.array([[self.dy]])
		
		#flip data
		flipArray = np.flip(self.data,0)
		# replace nodata with nan
		flipArray[flipArray==self.nodata] = np.nan
		
		dataDict[name] = flipArray
		
		try:
			sio.savemat(filename, dataDict,do_compression =True)
			if self.progress: self.progress.setInfo(self.tr('Grid %s exported to %s')%(name,filename),False)
		except IOError:
			#print 'Cannot save file: %s' %filename
			if self.progress: self.progress.setInfo(self.tr('Cannot save to %s because %s') %(filename,str(IOError)),True)
			
	def openASC(self,filename):
		tempdata = []
		try:
			f = open(filename,'r')

			for l in f:
				# TODO: seems to manage both white space and tabs (verify)
				l = l.split()
				if l[0].lower() == 'ncols':
					self.ncols = int(l[1])
				elif l[0].lower() == 'nrows':
					self.nrows = int(l[1])
				elif l[0].lower() == 'xllcorner':
					self.xcell = float(l[1])
				elif l[0].lower() == 'yllcorner':
					self.ycell = float(l[1])
				elif l[0].lower() == 'cellsize':
					self.dx = float(l[1])
					self.dy = float(l[1])
				elif l[0].lower() == 'dx':
					self.dx = float(l[1])
				elif l[0].lower() == 'dy':
					self.dy = float(l[1])
				elif l[0].lower() == 'nodata_value':
					self.nodata = float(l[1])
				else:
					# load data to array
					for v in l:
						tempdata.append(float(v))

			# close the file
			f.close()

			# check if the file is complete
			if (len(tempdata) == (self.nrows*self.ncols)):
				self.data = np.array(tempdata)
				# reshape wants the number of row and the number of columns!
				self.data = self.data.reshape((self.nrows,self.ncols))
			else:
				if self.progress: self.progress.setInfo(self.tr('File %s data are not completed') %(filename),True)
				# clear all
				self.data = []
		except IOError:
			if self.progress: self.progress.setInfo(self.tr('Cannot open %s because %s') %(filename,str(IOError)),True)
		finally:
			pass#f.close()


if __name__ == '__console__':
	aGrid = GisGrid(ncols=3, nrows=4, xcell=0.0, ycell=0.0, dx=2.0, dy=2.0,nodata = -9999,EPSGid = 3003,progress = None)
	aGrid.data = np.array([[1,2,3],[2,4,6],[3,6,9],[4,8,12]])
	aGrid.saveAsGDAL('C:/enricodata/lavori/firenze2018/elab/test.tif')
	