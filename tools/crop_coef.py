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
 *   This program is free software you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation either version 2 of the License, or	   *
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

import numpy as np
from datetime import datetime,date,timedelta
import pandas as pd

# credits: https://stackoverflow.com/questions/6518811/interpolate-nan-values-in-a-numpy-array
from tools.my_progress import MyProgress
from tools.parse_par_file import parseParFile


def nan_helper(y):
	"""Helper to handle indices and logical indices of NaNs.

	Input:
		- y, 1d numpy array with possible NaNs
	Output:
		- nans, logical indices of NaNs
		- index, a function, with signature indices= index(logical_indices),
		  to convert logical indices of NaNs to 'equivalent' indices
	Example:
		>>> # linear interpolation of NaNs
		>>> nans, x= nan_helper(y)
		>>> y[nans]= np.interp(x(nans), x(~nans), y[~nans])
	"""

	return np.isnan(y), lambda z: z.nonzero()[0]

def fillMissing(y,x = None):
	y2 = np.copy(y)
	nans, x2 = nan_helper(y2)
	if x is None: x=x2
	y2[nans] = np.interp(x(nans), x(~nans), y2[~nans])
	return y2

# credits: https://stackoverflow.com/questions/14313510/how-to-calculate-rolling-moving-average-using-python-numpy-scipy
def movMean_OLD(a, n=5) :
	ret = np.cumsum(a, dtype=float)
	ret[n:] = ret[n:] - ret[:-n]
	ret[n - 1:] = ret[n - 1:] / n
	ret[0:n - 1] = ret[0:n-1] / (np.array(list(range(0,n-1)))+1)
	return ret

def movMean(a, n=5) :
	# TODO: tested only with odd n value
	tailValues = np.zeros(n)
	a = np.concatenate((tailValues,a,tailValues))
	csum = np.cumsum(a, dtype=float)
	# index of the limits before and after the center of the moving window
	before = int(float(n)/2)
	after =before+n

	diff = csum[after:-before]-csum[before:-after]
	diff = diff[:-1]
	# adjust the number of valid numbers
	tailCount =np.zeros(np.size(a))+n
	tailCount[:after]= np.array(list(range(-before,n)))+tailCount[:after]*0
	tailCount[-after:] = tailCount[-after:] - np.array(list(range(1, after+1)))
	tailCount =tailCount[n:-n]

	ret = diff / tailCount

	return ret


def movMeanWithPandas(a, n=5) :
	df = pd.DataFrame(a)
	ret = df[0].rolling(window=n).mean()
	return ret

# credits: https://stackoverflow.com/questions/11621740/how-to-determine-whether-a-year-is-a-leap-year
def is_leap_year(year):
	"""Determine whether a year is a leap year."""
	return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def getNumDays(yearList):
	numDays = [365]*len(yearList)
	for i,y in enumerate(yearList):
		if is_leap_year(y):
			numDays[i]=366
	return numDays

def getYearList(startDay,endDay):
	startYear = startDay.year
	endYear = endDay.year
	yearList = list(range(startYear,endYear+1))
	return yearList

def findSowingDate(Tave,DoY,currentDayIndex,timeSpan,SowingDate_min,SowingDelay_max,Tsowing,isWinterCrop):
	# return the index of the first available day for seeding
	sowingDateIdx = -1
	# test current days window
	testSpan = np.zeros(np.size(Tave))
	testSpan[currentDayIndex:currentDayIndex+timeSpan] =1

	# test sowing window
	testSowingWindow = np.logical_and(DoY>=SowingDate_min,DoY<=SowingDate_min+SowingDelay_max)
	testSowingWindow = np.logical_and(testSowingWindow,testSpan)

	msg = ''

	if sum(testSowingWindow) == 0:
		# no available dates in serie
		msg = 'Not in sowing period'
		return sowingDateIdx,msg

	# test temperature Tave > Tsowing and sowing window
	testT = np.logical_and(Tave>Tsowing,testSowingWindow)
	# adjust sowing date
	if sum(testT)==0:
		msg = 'Low temp to sow and out of sowing period'
		if isWinterCrop: sowingDate = SowingDate_min
		else: sowingDate = SowingDate_min+SowingDelay_max # summer crop
		rows = np.where(DoY == sowingDate)[0]
		if len(rows)>0:	sowingDateIdx = rows[0]
	else:
		# find the first element in array
		rows = np.where(testT == 1)[0]
		if len(rows)>0:	sowingDateIdx = rows[0]
		#print('Good to sow at ',sowingDateIdx)

	return sowingDateIdx,msg

def calculateDLH(DoY, wsLat):
	#### Computes daylight hours
	phi = np.pi / 180 * wsLat  # latitude [rad],          FAO56: eq. 22 pag 46
	delta = 0.409 * np.sin(2 * np.pi / 365 * DoY - 1.39)  # solar declination,       FAO56: eq. 24 pag 46
	omega_s = np.arccos(-np.tan(phi) * np.tan(delta))  # sunset hour angle [rad], FAO56: eq. 25 pag 46
	DLH = 24 / np.pi * omega_s  # daylight hours,          FAO56: eq. 34 pag 48
	return DLH

def calculateGDD(Tmax, Tmin, Tdaybase, Tcutoff):
	#### New version: sine wave
	Tave = np.mean([Tmax,Tmin],axis=0)
	T_GDD_low = np.zeros(np.size(Tmax))
	T_GDD_up = np.zeros(np.size(Tmax))
	W = (Tmax - Tmin) / 2
	i1 = np.logical_and(Tmin >= Tdaybase, Tmax <= Tcutoff)
	i2 = np.logical_and(Tmin < Tdaybase,np.logical_and(Tmax <= Tcutoff, Tmax > Tdaybase))
	i3 = np.logical_and(np.logical_and(Tmin >= Tdaybase, Tmin < Tcutoff),Tmax > Tcutoff )
	i4 = np.logical_and(Tmin < Tdaybase, Tmax > Tcutoff)
	i5 = Tmin >= Tcutoff
	# i6      both Tmax and T min are < Tcutoff -> no heat units accumulation (matrix already initialized to zero)

	# case 1
	if sum(i1) > 0:
		T_GDD_low[i1] = Tave[i1] - Tdaybase

	# case 2
	if sum(i2) > 0:
		theta2 = np.arcsin((Tdaybase - Tave[i2])/ W[i2])
		T_GDD_low[i2] = ((Tave[i2] - Tdaybase)* (np.pi / 2 - theta2) + W[i2]* np.cos(theta2))/ np.pi

	# case 3
	if sum(i3) > 0:
		phi3 = np.arcsin((Tcutoff - Tave[i3]) / W[i3])
		T_GDD_low[i3] = Tave[i3] - Tdaybase
		T_GDD_up[i3] = ((Tave[i3] - Tcutoff) * (np.pi / 2 - phi3) + W[i3]* np.cos(phi3))/ np.pi

	# case 4
	if sum(i4) > 0:
		theta4 = np.arcsin((Tdaybase - Tave[i4])/ W[i4])
		phi4 = np.arcsin((Tcutoff - Tave[i4])/ W[i4])
		T_GDD_low[i4] = ((Tave[i4] - Tdaybase)* (np.pi / 2 - theta4) + W[i4]* np.cos(theta4))/ np.pi
		T_GDD_up[i4] = ((Tave[i4] - Tcutoff) * (np.pi / 2 - phi4) + W[i4]* np.cos(phi4))/ np.pi
	# case 5
	if sum(i5) > 0:
		T_GDD_low[i5] = Tcutoff - Tdaybase

	# calcolate GDD
	T_GDD = T_GDD_low - T_GDD_up
	return T_GDD

def vernalization(Tave, Tv_min, Tv_max, Vslope, Vstart, Vend, VFmin):
	#### Vernalization
	Veff = np.zeros(np.size(Tave))  # vernalization contribution of the day
	# Calculate vernalization contribution of the day
	Veff[Tave < (Tv_min - Vslope)] = 0  # PhD Thesis Anna Borghi: eq i-81 page 172
	i = np.logical_and(Tave >= (Tv_min - Vslope), Tave < Tv_min)  # PhD Thesis Anna Borghi: eq i-81 page 172
	Veff[i] = 1 - (Tv_min - Tave[i]) / Vslope  # PhD Thesis Anna Borghi: eq i-81 page 172
	Veff[np.logical_and(Tave >= Tv_min, Tave < Tv_max)] = 1  # PhD Thesis Anna Borghi: eq i-81 page 172
	ii = np.logical_and(Tave >= Tv_max, Tave < (Tv_max + Vslope))  # PhD Thesis Anna Borghi: eq i-81 page 172
	Veff[ii] = 1 - (Tave[ii] - Tv_max) / Vslope  # PhD Thesis Anna Borghi: eq i-81 page 172
	Veff[Tave >= (Tv_max + Vslope)] = 0  # PhD Thesis Anna Borghi: eq i-81 page 172
	# Calculate  sum of accumulated vernalization days
	VDsum = np.cumsum(Veff)  # sum of the currently accumulated vernalization days
	# Calculate  vernalization factor
	VF = VFmin + ((1 - VFmin) * (VDsum - Vstart)) / (Vend - Vstart)  # vernalization factor (PhD Thesis Anna Borghi: eq i-81 page 172)
	VF[VDsum < Vstart] = 1
	VF[VDsum > Vend] = 1
	return VF

def photoperiod(DLH, ph_r, daylength_if, daylength_ins):
	#### Photoperiod
	PF = np.ones(np.size(DLH))  # photoperiod factor
	if ph_r == 1:  # Long-day plants, PhD Thesis Anna Borghi: eq i-82 page 172
		PF[DLH < daylength_if] = 0
		PF[DLH > daylength_ins] = 1
		threshInd = np.logical_and(DLH >= daylength_if, DLH <= daylength_ins)
		PF[threshInd] = (DLH[threshInd] - daylength_if) / (daylength_ins - daylength_if)
	elif ph_r == 2:  # Short-day plants, PhD Thesis Anna Borghi: eq i-83 page 172 (Corrected!!! see http://modeling.bsyse.wsu.edu/CS_Suite/cropsyst/manual/simulation/crop/photoperiod.htm)
		PF[DLH > daylength_if] = 0
		PF[DLH < daylength_ins] = 1 #TODO: questa condizione annulla la precedente se daylength_ins > daylength_if. Aggiugere check?
		threshInd = np.logical_and(DLH >= daylength_ins, DLH < daylength_if)
		PF[threshInd] = (daylength_if - DLH[threshInd]) / (daylength_if - daylength_ins)
	else:
		# do nothing
		pass

	return PF

def calculateDoY(startDay,nOfDay):
	testDay = startDay
	endDay = startDay+timedelta(days=nOfDay)
	DoY = []
	dateList = []
	while testDay < endDay:
		DoY.append(int(testDay.strftime('%j')))
		if int(testDay.strftime('%j'))==366:
			print('end of bis year',testDay)
		dateList.append(testDay)
		testDay += timedelta(days=1)

	return np.array(dateList),np.array(DoY)

def cumSumReset(values,resetAt = 0):
	# TODO: not the most efficient way
	cumValue = 0.0
	cumValueList = []
	for v in values.tolist():
		if v==resetAt:
			cumValue = 0.0
		else:
			cumValue += v

		cumValueList.append(cumValue)

	return np.array(cumValueList)

# credits: https://stackoverflow.com/questions/24885092/finding-the-consecutive-zeros-in-a-numpy-array/24892274#24892274
def getFlatArea(a):
	delta = a[1:] - a[0:-1]
	# delta1[0] = Kcb[1]-Kcb[0]
	delta = np.around(delta, 6)
	# Create an array that is 1 where a is 0, and pad each end with an extra 0.
	iszero = np.concatenate(([0],np.equal(delta, 0).view(np.int8),[0]))
	absdiff = np.abs(np.diff(iszero))
	# Runs start and end where absdiff is 1.
	ranges = np.where(absdiff == 1)[0].reshape(-1, 2)
	return ranges

def getDescArea(a):
	delta = a[1:] - a[0:-1]
	# delta1[0] = Kcb[1]-Kcb[0]
	delta = np.around(delta, 6)
	# Create an array that is 1 where a is 0, and pad each end with an extra 0.
	iszero = np.concatenate(([0],np.less(delta, 0).view(np.int8),[0]))
	absdiff = np.abs(np.diff(iszero))
	# Runs start and end where absdiff is 1.
	ranges = np.where(absdiff == 1)[0].reshape(-1, 2)
	return ranges

# credits: https://stackoverflow.com/questions/46365859/what-is-the-fastest-way-to-get-the-mode-of-a-numpy-array
def mode(x):
	values, counts = np.unique(x, return_counts=True)
	m = counts.argmax()
	return values[m]

def adjustKcbOLD(Kcb,RHmin, Wind, hc):
	adjKcb = np.copy(Kcb)
	# select mid
	flatIdx = getFlatArea(Kcb)
	descIdx = getDescArea(Kcb)
	for s,e in flatIdx:
		e+=1 # fix missing values
		if mode(Kcb[s:e])>0.45: # only non-zero flat areas
			CF = calcKcbCorrFact(np.mean(RHmin[s:e]), np.mean(Wind[s:e]), np.mean(hc[s:e]))
			adjKcb[s:e]=Kcb[s:e]+CF

	for s,e in descIdx:
		if mode(Kcb[s:e]) > 0.45:
			CF = calcKcbCorrFact(np.mean(RHmin[s:e]), np.mean(Wind[s:e]), np.mean(hc[s:e]))
			adjKcb[s:e]=Kcb[s:e]+CF

	return adjKcb,flatIdx,descIdx

def adjustKcb(Kcb,RHmin, Wind, hc):
	adjKcb = np.copy(Kcb)
	filledKcb = fillMissing(Kcb)
	# select mid
	flatIdx = getFlatArea(filledKcb)
	descIdx = getDescArea(filledKcb)
	for s,e in flatIdx:
		e+=1 # fix missing values
		if mode(Kcb[s:e])>0.45: # only non-zero flat areas
			CF = calcKcbCorrFact(np.mean(RHmin[s:e]), np.mean(Wind[s:e]), np.mean(hc[s:e]))
			adjKcb[s:e]=Kcb[s:e]+CF

	for s,e in descIdx:
		# get only second point of descending phase
		if Kcb[e] > 0.45:
			CF = calcKcbCorrFact(np.mean(RHmin[s:e]), np.mean(Wind[s:e]), np.mean(hc[s:e]))
			adjKcb[e]=Kcb[e]+CF

	return adjKcb,flatIdx,descIdx

def assignCNPhase(Kcb):
	# 0 = no crop in field, 1 = ascending phase (as difference from 2), 2 = flat and descending phase
	CNvalue = np.zeros(np.size(Kcb))
	CNvalue[Kcb>0]=1
	# select mid
	flatIdx = getFlatArea(Kcb)
	descIdx = getDescArea(Kcb)
	for s, e in flatIdx:
		e += 1  # fix missing values
		if np.max(Kcb[s:e]) > 0.45:
			CNvalue[s:e] = 2

	for s, e in descIdx:
		if np.max(Kcb[s:e]) > 0.45:
			CNvalue[s:e] = 2

	CNvalue[Kcb == 0] = 0

	return CNvalue, flatIdx, descIdx


def calcKcbCorrFact(RHmin, Wind, hc):
	if RHmin < 20:RHmin = 20
	elif RHmin > 80: RHmin = 80
	else: pass

	if Wind < 1: Wind = 1
	elif Wind > 6: Wind = 6;
	else: pass

	if hc < 0.1: hc = 0.1
	elif hc > 10: hc = 10
	else: pass

	kcbCorrFact = (0.04 * (Wind - 2) - 0.004 * (RHmin - 45)) * (hc / 3) ** 0.3
	return kcbCorrFact


def computeGDD(wsLat, startDay, Tmax, Tmin, Tdaybase, Tcutoff, Vern, Tv_min, Tv_max, Vslope, Vstart, Vend, VFmin, ph_r, daylength_if, daylength_ins):
	nOfDay = len(Tmax)
	days, DoY = calculateDoY(startDay,nOfDay)
	#print('DoY',DoY)

	Tave = 0.5*(Tmax+Tmin)

	DLH = calculateDLH(DoY, wsLat)
	#print('DLH',DLH)

	T_GDD = calculateGDD(Tmax, Tmin, Tdaybase, Tcutoff)
	#print('T_GDD', T_GDD)

	VF = np.ones(np.size(Tmax))
	if Vern:
		VF = vernalization(Tave, Tv_min, Tv_max, Vslope, Vstart, Vend, VFmin)

	#print('VF', VF)


	PF = np.ones(np.size(Tmax))
	if ph_r:
		PF = photoperiod(DLH, ph_r, daylength_if, daylength_ins)

	T_GDD_corr = T_GDD * min([VF, PF],axis=0)
	#print('PF', PF)
	#### Computes GDD considering both VF and PF
	GDD_cum = np.cumsum(T_GDD_corr)  # PhD Thesis Anna Borghi: eq i-85 page 173

	return days, DoY,DLH,T_GDD,T_GDD_corr,VF,PF,GDD_cum

def computeCropSeq(wsLat, startDay, Tmax, Tmin, cropSeq,tollerance=1.0,minGDDForVern=None,checkFutureTemp=False, progress = None,tr = None):
	if not progress: progress = MyProgress()
	if not tr: tr = lambda x: x

	nOfDay = len(Tmax)
	days, DoY = calculateDoY(startDay,nOfDay)
	#print('DoY',DoY)
	#make a list of crops in field
	cropsOverYear = np.zeros(np.size(Tmax))
	T_GDD_corr = np.zeros(np.size(Tmax))

	Tave = 0.5*(Tmax+Tmin)

	# apply movable mean
	# Tmin = movMean(Tmin)
	# Tmax = movMean(Tmax)
	Tave_mov = movMean(Tave)

	DLH = calculateDLH(DoY, wsLat)
	#print('DLH',DLH)

	currentDayIndex = 0
	harvestIndex = 0
	timeSpan = 366

	cropSeqIter = iter(cropSeq)
	changeCrop = True

	while currentDayIndex<nOfDay:
		#print('currentDayIndex', currentDayIndex, 'harvestIndex', harvestIndex, 'timeSpan', timeSpan,'nOfDay',nOfDay)
		# get the next crop in the list
		if changeCrop:
			cr = next(cropSeqIter, None)
			if cr is None:
				# reloop
				cropSeqIter = iter(cropSeq)
				cr = next(cropSeqIter, None)

		if len(cr['GDD'])==0:
			print('No data for', cr['name'])
			currentDayIndex += 1  # cr['CropsOverlap']
			changeCrop = False
			continue
		#print('try with',cr['id'],'-',cr['name'])

		#update timeSpan
		if nOfDay-currentDayIndex<timeSpan:
			timeSpan = nOfDay-currentDayIndex

		#print('currentDayIndex', currentDayIndex, 'harvestIndex', harvestIndex, 'timeSpan', timeSpan,'nOfDay',nOfDay)
		# find sowing index
		sowIndex,msg = findSowingDate(Tave_mov, DoY, currentDayIndex,timeSpan, cr['SowingDate_min'], cr['SowingDelay_max'], cr['Tsowing'], cr['Vern'])
		#print('sowIndex',sowIndex)

		if sowIndex<0:
			progress.reportError(tr('No condition to sow %s at %s [DoY: %s] error: %s')%(cr['name'],days[currentDayIndex],DoY[currentDayIndex],msg))
			currentDayIndex += 1 #cr['CropsOverlap']
			changeCrop = False
		else:
			# make a subset of variable
			Tmax_sub = Tmax[sowIndex:sowIndex+timeSpan]
			Tmin_sub = Tmin[sowIndex:sowIndex + timeSpan]
			Tave_sub = Tave[sowIndex:sowIndex + timeSpan]
			DLH_sub = DLH[sowIndex:sowIndex + timeSpan]

			T_GDD_sub = calculateGDD(Tmax_sub, Tmin_sub, cr['Tdaybase'], cr['Tcutoff'])

			# get first index with temperature lower than required (only for summer crops)
			if ((not cr['Vern']) and checkFutureTemp):
				lowTempIdx = np.where(T_GDD_sub==0)[0]
				if len(lowTempIdx)>0:
					lowTempIdx = lowTempIdx[0]
					T_GDD_sub[lowTempIdx:]=0 # set all following thermal day to zero, plant will die ...

			VF_sub = np.ones(np.size(Tmax_sub))
			if cr['Vern']:
				VF_sub = vernalization(Tave_sub, cr['Tv_min'], cr['Tv_max'], cr['Vslope'], cr['Vstart'], cr['Vend'], cr['VFmin'])
				# get minimum vernalization factor
				minVF = np.min(VF_sub)
				minVFIdx = np.where(VF_sub==minVF)[0][0]
				if not (minVF<1):
					progress.reportError(tr('Not enough cool days for complete vernalization of %s [%s]')%(cr['name'],currentDayIndex))
					currentDayIndex += 1#cr['CropsOverlap']
					changeCrop = False
					continue

			PF_sub = np.ones(np.size(Tmax_sub))
			if cr['ph_r']:
				PF_sub = photoperiod(DLH_sub, cr['ph_r'], cr['daylength_if'], cr['daylength_ins'])
				minPF = np.min(PF_sub)
				minPFIdx = np.where(PF_sub == minPF)[0][0]

				if not ((minPF<1)):
					progress.reportError(tr('Not enough shirt/long days for complete photoperiod of %s [%s]')%(cr['name'],currentDayIndex))
					currentDayIndex += 1 #cr['CropsOverlap']
					changeCrop = False
					continue


			T_GDD_corr_sub = T_GDD_sub * np.min([VF_sub, PF_sub],axis=0)
			#print('PF', PF)
			#### Computes GDD considering both VF and PF
			GDD_cum_sub = np.cumsum(T_GDD_corr_sub)  # PhD Thesis Anna Borghi: eq i-85 page 173
			if (cr['Vern'] and (minGDDForVern is not None)):
				# check if vernalization minimum is between +/- 1% of a percentage of the maximum required GDD,
				# i.e. crop has enought time to grow before vernalization
				if ((GDD_cum_sub[minVFIdx]>=0.9*minGDDForVern*max(cr['GDD'])) and (GDD_cum_sub[minVFIdx]<=1.1*minGDDForVern*max(cr['GDD']))):
					progress.reportError(tr('Not enough growing days before vernalization %s [%s]') % (cr['name'], currentDayIndex))
					currentDayIndex += 1#cr['CropsOverlap']
					changeCrop = False
					continue

			startFrom = 0
			notEnoughGDD = True
			numOfHarvest = 0
			#print('maxCalcGDD',max(GDD_cum_sub[startFrom:]),'maxReqGDD',tollerance*max(cr['GDD']))
			while max(GDD_cum_sub[startFrom:])>=tollerance*max(cr['GDD']):
				# enough thermal resources to finish the crop with one harvest at least
				notEnoughGDD = False
				numOfHarvest+=1
				rows = np.where(GDD_cum_sub[startFrom:] >= max(cr['GDD']))[0]
				# try with full thermal condition
				if len(rows)>0:
					#print('maxGDD',max(cr['GDD']))
					maxGDDIdx = startFrom+rows[0]+1 # TODO
				else:
					# this condition is already verified
					rows = np.where(GDD_cum_sub[startFrom:]>tollerance*max(cr['GDD']))[0]
					maxGDDIdx = startFrom+rows[0]+1 # TODO

				maxGDD = GDD_cum_sub[maxGDDIdx]
				harvestIndex = sowIndex + maxGDDIdx
				if startFrom==0:
					# always check crop overlaps from sowing
					try:
						maxGDDold = np.max(T_GDD_corr[sowIndex-cr['CropsOverlap']:sowIndex])
						cropsOverYear[sowIndex-cr['CropsOverlap']:sowIndex] = 0
						T_GDD_corr[sowIndex-cr['CropsOverlap']:sowIndex] = 0.0
						T_GDD_corr[sowIndex - cr['CropsOverlap']-1] = maxGDDold # set last GDD day to maximum GDD to complete growing
					except Exception as e:
						progress.reportError(tr('Unmanaged error %s') % str(e))

				# set the period to crop
				cropsOverYear[(sowIndex+startFrom):harvestIndex]=cr['id']
				T_GDD_corr[(sowIndex+startFrom):harvestIndex]=GDD_cum_sub[startFrom:maxGDDIdx]
				# update currentDayIndex
				
				if cr['HarvNum_max']==numOfHarvest:
					break
				else:
					startFrom = maxGDDIdx #TODO +1? check multiple harvest
					# cut GDD_cum_sum for following harvests
					GDD_cum_sub-=maxGDD#+min(cr['GDD'])

			if notEnoughGDD:
				#print('Not enough thermal days to grow',cr['name'],'sowing at',sowIndex,'at idx:',currentDayIndex,', day:',DoY[currentDayIndex])
				progress.reportError(
					tr('Not enough thermal days to grow %s from %s [idx: %s, day: %s] to %s [idx: %s, day: %s]') %
					(cr['name'],
					 days[sowIndex], sowIndex,DoY[sowIndex],
					 days[currentDayIndex+timeSpan-1], currentDayIndex+timeSpan-1, DoY[currentDayIndex+timeSpan-1]))

				currentDayIndex += 1 #cr['CropsOverlap']
				changeCrop = False
			else:
				progress.pushInfo(
					tr('Set crop %s from %s [idx: %s, day: %s] to %s [idx: %s, day: %s]') %
						(cr['name'], days[sowIndex], sowIndex, DoY[sowIndex],
						days[currentDayIndex + timeSpan - 1], currentDayIndex + timeSpan - 1,
						DoY[currentDayIndex + timeSpan - 1]))

				if harvestIndex<currentDayIndex:
					progress.reportError(
						tr('Harvest before current day harvestIndex= %s currentDayIndex= %s maxGDDIdx= %s') %
							(harvestIndex,currentDayIndex,maxGDDIdx))

					break

				currentDayIndex = harvestIndex + 1  # cr['CropsOverlap']
				changeCrop = True

	return days, DoY,cropsOverYear,T_GDD_corr

def computeParamsDistro(cropsOverYears,T_GDD_corr,cropId,GDDList,pValueList):
	# get start and end index of the selected crop along the serie
	cropMask = cropsOverYears==cropId
	T_GDD_masked = T_GDD_corr*cropMask # get only the GDD count for the selected crop
	parValues = np.empty(np.size(T_GDD_corr)) # make a list of output values
	parValues[cropMask] = np.NaN
	parValues[~cropMask]=min(pValueList) #TODO: 0 # mark as zeros the non crop period

	finalIdx = []
	for gdd,pValue in zip(GDDList,pValueList):
		# mark param inflection points
		gddTest = 1*(T_GDD_masked <= gdd) #TODO >=
		infPoints = np.zeros(np.size(gddTest))
		infPoints[0:-1] = gddTest[1:]-gddTest[0:-1]
		infPoints[-1]=gddTest[-1]
		# idx = np.where(infPoints==1)[0].tolist()
		# idx = [x+1 for x in idx] #TODO: why +1?
		# finalIdx += idx
		# parValues[idx] = pValue
		#idxList = np.where(infPoints == 1)[0].tolist()
		idxList = np.where(infPoints == -1)[0].tolist()
		for idx in idxList:
			idx+=1  #TODO: why +1? to fit m version...
			if not np.isnan(parValues[idx]):
				#print('val',parValues[idx],'already filled at',idx,'GDD',gdd,'pValue',pValue)
				idx += 1

			parValues[idx] = pValue
			finalIdx += [idx]

	# plotParDistro(parValues,finalIdx)

	return parValues

def computeAdjWaterProd(crop,CO2conc=None):
	adjWP = crop['WP']
	# Calculate ajusted water productivity
	if CO2conc:
		# calculate f type
		f_type = ((40-(crop['WP'])*100)/(40-20))
		if f_type < 0: f_type = 0
		if f_type > 1: f_type = 1
		# calculate w
		w = 1-(550-CO2conc)/(550-369.41)
		if w < 0: w = 0
		if w > 1: w = 1
		# calculate fCO2
		fCO2 = (CO2conc/369.41)/(1+(CO2conc-369.41)*((1-w)*0.000138 + w*(crop['fsink']*0.000138+(1-crop['fsink'])*0.001165)))
		adjWP = (1+f_type*(fCO2-1))*crop['WP']

	return adjWP

def computeAdjWP(WP,fsink,CO2conc):
	# calculate f type
	f_type = ((40 - WP * 100) / (40 - 20))
	if f_type < 0: f_type = 0
	if f_type > 1: f_type = 1
	# calculate w
	w = 1 - (550 - CO2conc) / (550 - 369.41)
	if w < 0: w = 0
	if w > 1: w = 1
	# calculate fCO2
	fCO2 = (CO2conc / 369.41) / (1 + (CO2conc - 369.41) * (
				(1 - w) * 0.000138 + w * (fsink * 0.000138 + (1 - fsink) * 0.001165)))

	adjWP = (1 + f_type * (fCO2 - 1)) * WP
	return adjWP

def computeCanopyResistance(CO2conc):
	# Calculate canopy resistance values
	LeafCond = 1 / 100 * (1.4 - 0.4 * (CO2conc / 330))  # Easterling WE et al. (1992) Preparing the erosion productivity impact calculator (EPIC) model to simulate crop response to climate change and the direct effects of CO2. Agricultural and Forest Meteorology 59 (1), 17 U34.
	LeafRes = 1. / LeafCond
	CanRes = LeafRes / (0.5 * 24 * 0.12)  # FAO56 pag. 22

	return CanRes

def readCropParsFile(fileName,id = 1, name = '', forceMultiCrop = True):
	tempDict = parseParFile(fileName,parSep = '=', colSep=' ')
	# parse pars in the proper way
	parDict = tempDict['table']
	#print('parDict:',parDict)
	for k,v in parDict.items():
		newVal = []
		for x in v:
			if x == '*': newVal.append(np.NaN)
			else: newVal.append(float(x))

		parDict[k] = newVal

	del tempDict['table']

	for k,v in tempDict.items():
		if k in ['SowingDate_min','SowingDelay_max','Vern','ph_r','CropsOverlap','HarvNum_max']:
			parDict[k] = int(v)
		else:
			parDict[k] = float(v)

	if (forceMultiCrop and (parDict['HarvNum_max']>1)):
		# calculate GDD sequence
		tempGDD = np.array([0]+parDict['GDD'])
		deltaGDD = (tempGDD[1:]-tempGDD[0:-1])
		newGDD = np.tile(deltaGDD,parDict['HarvNum_max'])
		newGDD = np.cumsum(newGDD)
		parDict['GDD'] = newGDD.tolist()
		#print('recalc',parDict['GDD'])
		# repeat all value
		parDict['LAI'] = np.tile(parDict['LAI'],parDict['HarvNum_max']).tolist()
		parDict['Kcb'] = np.tile(parDict['Kcb'], parDict['HarvNum_max']).tolist()
		parDict['Hc'] = np.tile(parDict['Hc'], parDict['HarvNum_max']).tolist()
		parDict['Sr'] = np.tile(parDict['Sr'], parDict['HarvNum_max']).tolist()
		parDict['HarvNum_max'] = 1

	# add name
	parDict['name']=name
	parDict['id']=id


	return parDict

def readCropSeqFile(fileName):
	# return a dictionary of lists
	# # List of crops to be simulated, columns must be separated by one or more tab characters
	# Cr_ID	Crop1	Crop2	# Comments
	# 1	13.tab	*	# corn monoculture
	# 2	4.tab	2.tab	# wheat and corn alternate
	# 3	12.tab	*	# wheat
	# endTable

	cropSeq = {}
	with open(fileName)as f:
		while 1:
			line = f.readline().replace('\n', '')
			# replace TAB
			line = line.replace('\t', ' ')
			# remove consecutive with spaces
			line = ' '.join([x for x in line.split()])

			if line.startswith('#'):
				pass # is a comment
			else:
				toks = line.split('#')
				if len(toks)>1: line = toks[0] # get only the part before comments otherwise it is all valid record
				toks = line.split(' ')
				if toks[0] == 'Cr_ID':
					pass # is the header
				elif  toks[0]=='endTable':
					break
				else:
					seqId = int(toks[0])
					crop1 = toks[1]
					if toks[2] != '*':
						crop2 = toks[2]
						cropSeq[seqId]=[crop1,crop2]
					else:
						cropSeq[seqId] = [crop1]

	return cropSeq


def readWeatherFile(fileName):
	# read headers:
	# Id stazione: 100, località: weather one
	# 49.5  235.0
	# 01/01/2000 -> 31/12/2001
	ws = {}
	with open(fileName)as f:
		# line 1
		line = f.readline().replace('\n','')
		toks = line.split(',')
		ws['id'] = int(toks[0].split(': ')[1])
		ws['name'] = toks[1].split(': ')[1]
		# line 2
		line = f.readline().replace('\n','')
		toks = line.split(' ')
		toks = [t for t in toks if t !='']
		ws['lat'] = float(toks[0])
		ws['alt'] = float(toks[1])
		# line 3
		line = f.readline().replace('\n','')
		toks = line.split(' -> ')
		ws['startDay'] = datetime.strptime(toks[0],'%d/%m/%Y').date()
		ws['endDay'] = datetime.strptime(toks[1], '%d/%m/%Y').date()

	df = pd.read_csv(fileName, sep=r'\s* \s*', usecols=['T_max', 'T_min', 'U_min', 'V_med'], skiprows=3, engine='python')

	T_max = df['T_max'].to_numpy()
	T_min = df['T_min'].to_numpy()
	U_min = df['U_min'].to_numpy()
	V_med = df['V_med'].to_numpy()
	# add some dummy values
	yearList = getYearList(ws['startDay'],ws['endDay'])
	daysInYears = getNumDays(yearList)

	T_max = np.concatenate((T_max[0:daysInYears[0]], T_max, T_max[np.size(T_max) - daysInYears[-1]:]))
	T_min = np.concatenate((T_min[0:daysInYears[0]], T_min, T_min[np.size(T_min) - daysInYears[-1]:]))
	U_min = np.concatenate((U_min[0:daysInYears[0]], U_min, U_min[np.size(U_min) - daysInYears[-1]:]))
	V_med = np.concatenate((V_med[0:daysInYears[0]], V_med, V_med[np.size(V_med) - daysInYears[-1]:]))

	# T_max = movMean(T_max, n=5)
	# T_min = movMean(T_min, n=5)

	newStartDay = ws['startDay']-timedelta(days=daysInYears[0])

	return ws, T_min, T_max, U_min, V_med, newStartDay, daysInYears

def saveWP(fileName,cropSeq,Crops,yearList,CO2List,canopyResMod):
	header = ['year']
	# init var dictionary
	data = {}
	for y in yearList:
		data[y] = []

	for i, cs in cropSeq.items():  # loop in crop sequence list
		for c in cs:  # loop in crop
			header.append('CrID_%d' % i)
			crop = Crops[c]
			for y,CO2 in zip(yearList,CO2List):
				if canopyResMod:
					WP = computeAdjWP(crop['WP'],crop['fsink'],CO2)
				else:
					WP = crop['WP']
				data[y].append(str(round(WP,2)))

	# prepare data to save
	text = '\t'.join(header)
	for k, v in data.items():
		text += '\n' + '\t'.join([str(k)] + v)

	# save to file
	with open(fileName, mode='wt')as f:
		f.write(text)

def saveCanRes(fileName, CO2File, canopyResMod):
	# TODO: fix
	if CO2File is None: return
	# open CO2 file
	df = pd.read_csv(CO2File, sep='\t', usecols=['Year', 'CO2'], engine='python')

	yearList = df['Year']
	CO2List = df['CO2']

	header = ['year','CanRes']
	# init var dictionary
	data = []
	if canopyResMod:
		for c in CO2List:
			data.append(round(computeCanopyResistance(c),2))
	else:
		data = [70.0]*len(yearList)

	# prepare data to save
	text = '\t'.join(header)
	for y,d in zip(yearList,data):
		text += '\n' + str(y)+'\t'+str(d)

	# save to file
	with open(fileName, mode='wt')as f:
		f.write(text)


def saveParsFile(fileName,cropSeq,Crops):
	#varToPrint = ['Irrig', 'CNclass', 'pRAW', 'aInt', 'Tlim', 'Tcrit', 'HI', 'kyT', 'ky1', 'ky2', 'ky3', 'ky4']
	# names are replaced with those included in the crop parameters files
	varToPrint = ['Irrigation', 'cl_CN', 'pRAW', 'aInterception', 'Tlim_HS', 'Tcrit_HS', 'HI', 'kyT', 'ky1', 'ky2', 'ky3', 'ky4']
	# TODO: check type of variable (int/float)
	header = ['Var']
	# init var dictionary
	data = {}
	for v in varToPrint:
		data[v]=[]

	for i,cs in cropSeq.items(): # loop in crop sequence list
		for c in cs: # loop in crop
			header.append('CrID_%d'%i)
			crop = Crops[c]
			for v in varToPrint:
				data[v].append(str(crop[v]))

	# prepare data to save
	text = '\t'.join(header)
	for k,v in data.items():
		text+='\n'+'\t'.join([k]+v)

	# save to file
	with open(fileName,mode='wt')as f:
		f.write(text)


def calculateCropPars(ws,T_max,T_min,U_min,V_med,cropsList):
	days, DoY, cropsOverYears, T_GDD_corr = computeCropSeq(wsLat=ws['lat'], startDay=ws['startDay'],
														   Tmax=T_max, Tmin=T_min, cropSeq=cropsList,
														   minGDDForVern=0.2,
														   checkFutureTemp=True)

	laiValues = np.zeros(np.size(T_GDD_corr))
	kcbValues = np.zeros(np.size(T_GDD_corr))
	adjKcbValues = np.zeros(np.size(T_GDD_corr))
	hcValues = np.zeros(np.size(T_GDD_corr))
	srValues = np.zeros(np.size(T_GDD_corr))

	for crop in cropsList:
		parValues = computeParamsDistro(cropsOverYears, T_GDD_corr, crop['id'], crop['GDD'], crop['LAI'])
		parValues = fillMissing(parValues) # fill nan with linear interpolation
		laiValues += parValues

		parValues = computeParamsDistro(cropsOverYears, T_GDD_corr, crop['id'], crop['GDD'], crop['Sr'])
		parValues = fillMissing(parValues)  # fill nan with linear interpolation
		srValues += parValues

		parValues = computeParamsDistro(cropsOverYears, T_GDD_corr, crop['id'], crop['GDD'], crop['Hc'])
		parValues = fillMissing(parValues)  # fill nan with linear interpolation
		hcValues += parValues

		# the last is Kcb because it requires Hc
		parValues = computeParamsDistro(cropsOverYears, T_GDD_corr, crop['id'], crop['GDD'], crop['Kcb'])
		kcbValues += fillMissing(parValues)  # fill nan with linear interpolation

		# the last is Kcb because it requires Hc
		parValues, flatIdx, descIdx = adjustKcb(parValues, U_min, V_med, hcValues)  # adjust Kcb
		parValues = fillMissing(parValues)  # fill nan with linear interpolation
		adjKcbValues += parValues

	cropsOverYears[cropsOverYears == 0] = np.NaN

	cnPhaseValues, flatIdx, descIdx = assignCNPhase(kcbValues)

	return days, DoY, cropsOverYears, T_GDD_corr,laiValues,kcbValues,hcValues,srValues,adjKcbValues,cnPhaseValues,flatIdx, descIdx

def plotParDistro(T_GDD_corr,finalIdx):
	import matplotlib
	matplotlib.use('qt5agg')
	import matplotlib.pyplot as plt
	fig, axs = plt.subplots(1, 1, sharex=True)
	day = np.ones(np.shape(T_GDD_corr))
	day = np.cumsum(day)-1
	axs = [axs]
	axs[0].plot(day,T_GDD_corr, label='T_GDD', color='red')
	axs[0].vlines(finalIdx,ymin = np.min(T_GDD_corr),ymax = np.max(T_GDD_corr), color='gray')
	axs[0].legend()

def plotCropPars(days, T_max, T_min, cropsOverYears, T_GDD_corr,flatIdx,descIdx,laiValues,kcbValues,hcValues,srValues,adjKcbValues,cnPhaseValues, crop=None):
	import matplotlib
	matplotlib.use('qt5agg')
	import matplotlib.pyplot as plt
	fig, axs = plt.subplots(4, 1, sharex=True)
	axs[0].plot(days, T_max, label='T max', color='red')
	axs[0].plot(days, T_min, label='T min', color='blue')
	axs[0].legend()
	axs[0].set_ylabel('Temp. (°C)')

	axs[1].plot(days, cropsOverYears, label='crop id', color='green')

	axs[2].plot(days, T_GDD_corr, color='orange')
	if crop:
		axs[2].hlines(crop['GDD'],xmin=np.min(days),xmax=np.max(days))

	axs[2].set_ylabel('T GDD')

	axs[3].plot(days, kcbValues, label='Kcb', color='green')
	axs[3].plot(days, adjKcbValues, label='Kcb adj.', color='red')
	# mark flat areas
	flatIdx = flatIdx.flatten().tolist()
	# mark desc ares
	descIdx = descIdx.flatten().tolist()

	axs[3].plot(days[flatIdx], kcbValues[flatIdx], 'go', label='flat')
	axs[3].plot(days[descIdx], kcbValues[descIdx], 'r+', label='desc')
	axs[3].set_ylabel('Kcb (-)')

	axs[3].legend()

	# axs[4].plot(days, cnPhaseValues, label='CN code', color='purple')
	# axs[4].set_ylabel('CN code (-)')
	#
	# axs[5].plot(days, hcValues, label='H crop', color='green')
	# axs[5].plot(days, -srValues, label='S root', color='brown')
	# axs[5].set_ylabel('heigth/depth (-)')
	# axs[5].legend()
	#
	# axs[6].plot(days, laiValues, label='Lai', color='darkgreen')
	# axs[6].set_ylabel('LAI (-)')
	fig.tight_layout()
	plt.show()


def applyCropCoef(cropSeq, cropParsDict,
				weatherFile, outputPath,
				CO2File):
	# prepare dataframe for each variable and crop sequence
	GDDcumDf = pd.DataFrame(columns=list(cropSeq.keys()))
	laiDf = pd.DataFrame(columns=list(cropSeq.keys()))
	adjKcbDf = pd.DataFrame(columns=list(cropSeq.keys()))
	hcDf = pd.DataFrame(columns=list(cropSeq.keys()))
	srDf = pd.DataFrame(columns=list(cropSeq.keys()))
	cnPhaseDf = pd.DataFrame(columns=list(cropSeq.keys()))
	daysDf = pd.DataFrame(columns=list(cropSeq.keys()))

	# read weather station data
	ws, T_min, T_max, U_min, V_med, newStartDay,daysInYears = readWeatherFile(fileName=weatherFile)

	ws['startDay']=newStartDay
	# loop in crops sequence and perform cropcoef
	for k,cs in cropSeq.items():
		cropsList = []
		for c in cs:
			cropsList.append(cropParsDict[c])

		#print('crop1',cropsList[0])

		# calculate
		days, DoY, cropsOverYears, T_GDD_corr,laiValues,kcbValues,hcValues,srValues,adjKcbValues,cnPhaseValues,flatIdx, descIdx = calculateCropPars(ws, T_max, T_min, U_min, V_med, cropsList)
		GDDcumDf[k]=T_GDD_corr[daysInYears[0]:-daysInYears[-1]]
		laiDf[k]=laiValues[daysInYears[0]:-daysInYears[-1]]
		adjKcbDf[k] = adjKcbValues[daysInYears[0]:-daysInYears[-1]]
		hcDf[k] = hcValues[daysInYears[0]:-daysInYears[-1]]
		srDf[k] = srValues[daysInYears[0]:-daysInYears[-1]]
		cnPhaseDf[k] = cnPhaseValues[daysInYears[0]:-daysInYears[-1]]
		daysDf[k]=DoY[daysInYears[0]:-daysInYears[-1]]

		# plot
		# plotCropPars(days, T_max, T_min, cropsOverYears, T_GDD_corr, flatIdx, descIdx, laiValues, kcbValues, hcValues,
		#  			 srValues, adjKcbValues, cnPhaseValues,cropsList[0])



	# save results to file
	header = ['CrID_%s' % x for x in laiDf.keys()]
	GDDcumDf.to_csv(path_or_buf=os.path.join(outputPath, 'GDDcum.dat'), float_format='%.4f', sep='\t', index=False,
				 header=header)
	laiDf.to_csv(path_or_buf=os.path.join(outputPath, 'LAI.dat'), float_format='%.4f', sep='\t', index=False,
				 header=header)
	adjKcbDf.to_csv(path_or_buf=os.path.join(outputPath, 'Kcb.dat'), float_format='%.4f', sep='\t', index=False,
				 header=header)
	hcDf.to_csv(path_or_buf=os.path.join(outputPath, 'H.dat'), float_format='%.4f', sep='\t', index=False,
				 header=header)
	srDf.to_csv(path_or_buf=os.path.join(outputPath, 'Sr.dat'), float_format='%.4f', sep='\t', index=False,
				 header=header)
	cnPhaseDf.to_csv(path_or_buf=os.path.join(outputPath, 'CNvalue.dat'), float_format='%d', sep='\t', index=False,
				 header=header)
	daysDf.to_csv(path_or_buf=os.path.join(outputPath, 'DoY.dat'), float_format='%d', sep='\t', index=False,
				 header=header)

	saveParsFile(os.path.join(outputPath, 'CropParam.dat'), cropSeq, cropParsDict)

	# read CO2 file
	if CO2File:
		df = pd.read_csv(CO2File, sep='\t', usecols=['Year', 'CO2'],  engine='python')

		yearList = df['Year']
		CO2List =df['CO2']

		# save WP or adjusted WP
		path2wp = os.path.join(outputPath,'WPadj.dat')
		saveWP(path2wp, cropSeq, cropParsDict, yearList, CO2List, 1)


def compare(cropSeqIds = [11],fileName = 'H.dat'):
	meteoFile = 'C:/testcropcoef/orig/meteo_data/100.dat'

	origFolder = 'C:/testcropcoef/orig/crop_series_matlab/Pheno_100'
	#origFolder = 'C:/testcropcoef/orig/crop_series/Pheno_100'

	#origFolder = 'C:/idragra_code/esempi/Idragra_examples/Example_1/simulazione_fabbisogni/crop_series/Pheno_100'
	newFolder= 'C:/testcropcoef/orig/crop_series/Pheno_100'

	import	matplotlib
	matplotlib.use('qt5agg')
	import matplotlib.pyplot as plt

	replaceEndLines(fileName = os.path.join(origFolder,fileName)) # remove strange end-of-line

	cols = ['CrID_%d'%x for x in cropSeqIds]

	meteoDf = pd.read_csv(meteoFile, sep=r'\s* \s*', usecols=['T_max', 'T_min'], skiprows=3, engine='python')
	#origDf = pd.read_csv(os.path.join(origFolder,fileName), sep='\t', usecols=cols)
	newDf = pd.read_csv(os.path.join(newFolder, fileName), sep='\t', usecols=cols)

	days =np.cumsum(np.ones(np.size(newDf[cols[0]])))
	labs = list(range(1,367))+list(range(1,366))

	fig, axs = plt.subplots(len(cols)+1, 1, sharex=True)
	#if len(cols)==1: axs = [axs]
	meteoDf['T_mean'] = meteoDf.mean(axis=1)
	axs[0].plot(days, meteoDf['T_mean'], label='T mean', color='gray', linewidth=3.0)
	axs[0].plot(days, meteoDf['T_max'], label='T max', color='red', linewidth=0.5)
	axs[0].plot(days, meteoDf['T_min'], label='T min', color='blue', linewidth=0.5)
	#axs[0].legend()
	axs[0].set_ylabel('Temp. °C')

	for i,c in enumerate(cropSeqIds):
		useFld = 'CrID_%s'%(c)
		axs[i+1].plot(days, origDf[useFld], label='orig', color='red',linewidth=3.0)
		axs[i+1].plot(days, newDf[useFld], label='new', color='blue')
		axs[i+1].legend()
		axs[i+1].set_ylabel(fileName.replace('.dat','')+' seq'+str(c))
		#axs[i].axes.set_xticks(ticks=labs)

	fig.tight_layout()
	plt.show()

def replaceEndLines(fileName):
	lines = []
	with open(fileName,mode='r') as f:
		lines = f.readlines()

	with open(fileName, mode='w') as f:
		for l in lines:
			newLine = l.replace('\t\n','\n').replace(' \n','\n')
			f.write(newLine)

def readCropCoefFile(fileName):
	ccPars = parseParFile(fileName)
	ccPars['CanopyResMod']=int(ccPars['CanopyResMod'])
	return ccPars

def readWeatherStationFile(fileName):
	wsPars = parseParFile(fileName,colSep=' ')
	return wsPars['table']

def runCropCoef(workingDir, ccParFilename = 'cropcoef.txt'):
	ccPars = readCropCoefFile(os.path.join(workingDir,ccParFilename))

	path2CO2File = None
	if ccPars['CanopyResMod']:
		path2CO2File = os.path.join(workingDir, 'CO2_conc.dat')

	path2ws = os.path.join(workingDir,ccPars['WeathStatFilename'])
	path2wdata = os.path.join(workingDir, ccPars['MeteoDataFolder'])
	path2crops = os.path.join(workingDir, ccPars['CropInputsFolder'])
	path2outs = os.path.join(workingDir, ccPars['OutputFolder'])
	if not os.path.exists(path2outs): os.mkdir(path2outs)

	# read ws file
	wsPars = readWeatherStationFile(path2ws)
	#print('ws pars:',wsPars)

	# read soil uses file
	soilUseFn = os.path.join(path2crops, 'soil_uses.txt')
	cropSeq = readCropSeqFile(soilUseFn)
	#print('crop seq:',cSeq)

	cropParamsFolder = os.path.join(path2crops,'crop_parameters')
	# read all crop parameteres files
	fileList = os.listdir(cropParamsFolder)
	cropParsDict = {}

	i = 1
	for f in fileList:
		cropParsDict[f] = readCropParsFile(fileName=os.path.join(cropParamsFolder, f), id=i, name=f)
		i += 1
	# print(cropParsDict)

	# save canopy resistance
	path2CanRes = os.path.join(path2outs, 'CanopyRes.dat')

	saveCanRes(fileName=path2CanRes, CO2File=path2CO2File, canopyResMod=ccPars['CanopyResMod'])

	for wsName in wsPars['sar.dat']:
		wsDataFn =os.path.join(path2wdata,wsName)
		wsName = wsName.replace('.dat','')
		wsPhenoOut = os.path.join(path2outs,'Pheno_%s'%wsName)
		if not os.path.exists(wsPhenoOut): os.mkdir(wsPhenoOut)

		applyCropCoef(cropSeq = cropSeq, cropParsDict = cropParsDict,
					  weatherFile = wsDataFn, outputPath = wsPhenoOut,
					  CO2File=path2CO2File)

if __name__ == '__main__':
	# cropSeq = [16]
	# runCropCoef(cropSeqFile='C:/testcropcoef/orig/crop_inputs/soil_uses2.txt',
	# 			cropParamsFolder='C:/testcropcoef/orig/crop_inputs/crop_parameters',
	# 			weatherFile='C:/testcropcoef/orig/meteo_data/100.dat', outputPath='C:/testcropcoef/new',
	# 			cropSeqIds=cropSeq)
	# compare(cropSeq)
	# A = [4,8,6,- 1,- 2,- 3,- 1,3,4,5]
	# M = movMean(A, 7)
	# print(M)
	#runCropCoef(workingDir='C:/testcropcoef/orig', ccParFilename='cropcoef.txt')
	cropSeq = [16]
	compare(cropSeq,'lai.dat')
