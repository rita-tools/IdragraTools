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

import numpy as np
from datetime import date,timedelta

# credits: https://stackoverflow.com/questions/6518811/interpolate-nan-values-in-a-numpy-array
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
	nans, x2 = nan_helper(y)
	if x is None: x=x2
	y[nans] = np.interp(x(nans), x(~nans), y[~nans])
	return y

# credits: https://stackoverflow.com/questions/14313510/how-to-calculate-rolling-moving-average-using-python-numpy-scipy
def movMean(a, n=5) :
	ret = np.cumsum(a, dtype=float)
	ret[n:] = ret[n:] - ret[:-n]
	ret[n - 1:] = ret[n - 1:] / n
	ret[0:n - 1] = ret[0:n-1] / (np.array(list(range(0,n-1)))+1)
	return ret

def findSowingDate(Tave,DoY,currentDayIndex,timeSpan,minSowingDate,sowingDelay,T_sowing,isWinterCrop):
	# return the index of the first available day for seeding
	sowingDateIdx = -1
	# test current days window
	testSpan = np.zeros(np.size(Tave))
	testSpan[currentDayIndex:currentDayIndex+timeSpan] = 1

	# test sowing window
	testSowingWindow = np.logical_and(DoY>=minSowingDate,DoY<=minSowingDate+sowingDelay)
	testSowingWindow = np.logical_and(testSowingWindow,testSpan)

	if sum(testSowingWindow) == 0:
		# no available dates in serie
		return sowingDateIdx

	# test temperature Tave > T_sowing and sowing window
	testT = np.logical_and(Tave>T_sowing,testSowingWindow)
	# adjust sowing date
	if sum(testT)==0:
		if isWinterCrop: sowingDate = minSowingDate
		else: sowingDate = minSowingDate+sowingDelay # summer crop
		rows = np.where(DoY == sowingDate)[0]
		if len(rows)>0:	sowingDateIdx = rows[0]
	else:
		# find the first element in array
		rows = np.where(testT == 1)[0]
		if len(rows)>0:	sowingDateIdx = rows[0]

	return sowingDateIdx

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
	i2 = np.logical_and(np.logical_and(Tmin < Tdaybase, Tmax <= Tcutoff), Tmax > Tdaybase)
	i3 = np.logical_and(np.logical_and(Tmin >= Tdaybase, Tmax > Tcutoff), Tmin < Tcutoff)
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

def adjustKcb(Kcb,RHmin, Wind, hc):
	adjKcb = np.copy(Kcb)
	# select mid
	flatIdx = getFlatArea(Kcb)
	descIdx = getDescArea(Kcb)
	for s,e in flatIdx:
		e+=1 # fix missing values
		if np.mean(Kcb[s:e]>0): # only non-zero flat areas
			CF = calcKcbCorrFact(np.mean(RHmin[s:e]), np.mean(Wind[s:e]), np.mean(hc[s:e]))
			adjKcb[s:e]=Kcb[s:e]+CF

	for s,e in descIdx:
		CF = calcKcbCorrFact(np.mean(RHmin[s:e]), np.mean(Wind[s:e]), np.mean(hc[s:e]))
		adjKcb[s:e]=Kcb[s:e]+CF

	return adjKcb,flatIdx,descIdx

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

def computeCropSeq(wsLat, startDay, Tmax, Tmin, cropSeq,tollerance=0.9,minGDDForVern=0.2):

	nOfDay = len(Tmax)
	days, DoY = calculateDoY(startDay,nOfDay)
	#print('DoY',DoY)
	#make a list of crops in field
	cropsOverYear = np.zeros(np.size(Tmax))
	T_GDD_corr = np.zeros(np.size(Tmax))

	Tave = 0.5*(Tmax+Tmin)

	DLH = calculateDLH(DoY, wsLat)
	#print('DLH',DLH)

	currentDayIndex = 0
	harvestIndex = 0
	timeSpan = 366

	cropSeqIter = iter(cropSeq)
	changeCrop = True

	while currentDayIndex<=nOfDay:
		# get the next crop in the list
		if changeCrop:
			cr = next(cropSeqIter, None)
			if cr is None:
				# reloop
				cropSeqIter = iter(cropSeq)
				cr = next(cropSeqIter, None)

		#print('try with',cr['id'],'-',cr['name'])

		#update timeSpan
		if nOfDay-currentDayIndex<timeSpan:
			timeSpan = nOfDay-currentDayIndex

		# find sowing index
		sowIndex = findSowingDate(Tave, DoY, currentDayIndex,timeSpan, cr['minSowingDate'], cr['sowingDelay'], cr['T_sowing'], cr['Vern'])
		if sowIndex<0:
			print('No condition to sow',cr['name'])
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
			if not cr['Vern']:
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
					print('Not enough cool days for complete vernalization of',cr['name'],'[',currentDayIndex,']')
					currentDayIndex += 1#cr['CropsOverlap']
					changeCrop = False
					continue

			PF_sub = np.ones(np.size(Tmax_sub))
			if cr['ph_r']:
				PF_sub = photoperiod(DLH_sub, cr['ph_r'], cr['daylength_if'], cr['daylength_ins'])
				minPF = np.min(PF_sub)
				minPFIdx = np.where(PF_sub == minPF)[0][0]

				if not ((minPF<1)):
					print('Not enough shirt/long days for complete photoperiod of', cr['name'],'[',currentDayIndex,']')
					currentDayIndex += 1 #cr['CropsOverlap']
					changeCrop = False
					continue


			T_GDD_corr_sub = T_GDD_sub * np.min([VF_sub, PF_sub],axis=0)
			#print('PF', PF)
			#### Computes GDD considering both VF and PF
			GDD_cum_sub = np.cumsum(T_GDD_corr_sub)  # PhD Thesis Anna Borghi: eq i-85 page 173
			if cr['Vern']:
				# check if vernalization minimum is at 1/10 of the maximum required GDD, crop has enought time to grow before vernalization
				if (GDD_cum_sub[minVFIdx]>minGDDForVern*max(cr['GDD'])):
					print('Not enough growing days before vernalization of',cr['name'],'[',currentDayIndex,']')
					currentDayIndex += 1#cr['CropsOverlap']
					changeCrop = False
					continue


			if max(GDD_cum_sub)>tollerance*max(cr['GDD']):
				# enough thermal resources to finish the crop
				rows = np.where(GDD_cum_sub > max(cr['GDD']))[0]
				# try with full thermal condition
				if len(rows)>0: maxGDDIdx = rows[0]
				else:
					# this condition is already verified
					rows = np.where(GDD_cum_sub>tollerance*max(cr['GDD']))[0]
					maxGDDIdx = rows[0]

				harvestIndex = sowIndex +maxGDDIdx
				# always check crop overlaps
				cropsOverYear[sowIndex-cr['CropsOverlap']:sowIndex] = 0
				T_GDD_corr[sowIndex-cr['CropsOverlap']:sowIndex] = 0.0
				# set the period to crop
				cropsOverYear[sowIndex:harvestIndex]=cr['id']
				T_GDD_corr[sowIndex:harvestIndex]=GDD_cum_sub[0:maxGDDIdx]
				print('set crop', cr['name'],
					  'from', days[sowIndex], '[idx:', sowIndex, ', day:', DoY[sowIndex], ']',
					  'to', days[harvestIndex], '[idx:', harvestIndex, ', day:', DoY[harvestIndex], ']')
				# update currentDayIndex
				currentDayIndex = harvestIndex+1 #cr['CropsOverlap']
				changeCrop = True
			else:
				print('Not enough thermal days to grow',cr['name'])
				currentDayIndex += 1 #cr['CropsOverlap']
				changeCrop = False

	return days, DoY,cropsOverYear,T_GDD_corr

def computeParamsDistro(cropsOverYears,T_GDD_corr,cropId,GDDList,pValueList):
	# get start and end index of the selected crop along the serie
	cropMask = cropsOverYears==cropId
	T_GDD_masked = T_GDD_corr*cropMask # get only the GDD count for the selected crop
	parValues = np.empty(np.size(T_GDD_corr)) # make a list of output values
	parValues[cropMask] = np.NaN
	parValues[~cropMask]=0 # mark as zeros the non crop period

	for gdd,pValue in zip(GDDList,pValueList):
		# mark param inflection points
		gddTest = 1*(T_GDD_masked >= gdd)
		infPoints = np.zeros(np.size(gddTest))
		infPoints[0:-1] = gddTest[1:]-gddTest[0:-1]
		infPoints[-1]=gddTest[-1]
		idx = np.where(infPoints==1)[0].tolist()
		parValues[idx] = pValue

	# fill nan with linear interpolation
	parValues = fillMissing(parValues)

	return parValues

def test1():
	import pandas as pd
	import matplotlib

	matplotlib.use('qt5agg')
	import matplotlib.pyplot as plt


	# open table
	csvFile = 'C:/test_landriano/test11_SIM/meteodata/100.dat'
	df = pd.read_csv(csvFile, sep=r'\s* \s*',usecols = ['T_max','T_min'],skiprows = 3, engine='python')

	# calculate
	cropTbase = 10.0
	cropTcutoff = 25.
	# 49.5
	days, DoY,DLH,T_GDD,T_GDD_corr,VF,PF,GDD_cum, = computeGDD(wsLat = 49.5, startDay = date(2000,1,1),
											  Tmax = df['T_max'], Tmin  = df['T_min'],
											  Tdaybase = cropTbase, Tcutoff = cropTcutoff,
											  Vern = 1, Tv_min = 3, Tv_max = 10, Vslope = 7, Vstart= 10, Vend=50, VFmin =0,
											  ph_r = 0, daylength_if=8, daylength_ins=20)
	# plot

	fig, axs = plt.subplots(5, 1)
	axs[0].plot(days,df['T_max'],label='T max')
	axs[0].plot(days, df['T_min'], label='T min')
	axs[0].plot(days, np.zeros(np.size(days))+cropTbase, label='T base')
	axs[0].plot(days, np.zeros(np.size(days)) + cropTcutoff, label='T cutoff')

	#axs[0].hlines(cropTbase,1,365,label='T base')
	#axs[0].hlines(cropTcutoff,1,365, label='T cutoff')
	axs[0].legend()
	axs[0].set_xlabel('days')
	axs[0].set_ylabel('T')
	axs[0].grid(True)

	axs[1].plot(days,DLH)
	axs[1].set_xlabel('days')
	axs[1].set_ylabel('DLH')
	axs[1].grid(True)
	axs[1].set_ylim([0,24])

	axs[2].plot(days, T_GDD, label='T_GDD')
	axs[2].plot(days, T_GDD_corr,label='T_GDD_corr')
	axs[2].legend()
	axs[2].set_xlabel('days')
	axs[2].set_ylabel('T_GDD')
	axs[2].grid(True)

	axs[3].plot(days, VF,label='VF')
	axs[3].plot(days, PF,label='PF')
	axs[3].legend()
	axs[3].set_xlabel('days')
	axs[3].set_ylabel('VF,PF')
	axs[3].grid(True)
	axs[3].set_ylim([0, 1.1])

	axs[4].plot(days, GDD_cum)
	axs[4].set_xlabel('days')
	axs[4].set_ylabel('GDD_cum')
	axs[4].grid(True)

	fig.tight_layout()
	plt.show()

def test2():
	import pandas as pd
	import matplotlib

	matplotlib.use('qt5agg')
	import matplotlib.pyplot as plt

	# open table
	csvFile = 'C:/test_landriano/test11_SIM/meteodata/100.dat'
	df = pd.read_csv(csvFile, sep=r'\s* \s*', usecols=['T_max', 'T_min'], skiprows=3, engine='python')

	cropsList = [{'id':1,'name':'mais600',
				 'minSowingDate':91, 'sowingDelay':14, 'T_sowing':9,
				 'Vern':0,'Tdaybase':9, 'Tcutoff':30,'Tv_min':3, 'Tv_max':10, 'Vslope':7, 'Vstart':10, 'Vend':50, 'VFmin':0,
				 'ph_r':0, 'daylength_if':8, 'daylength_ins':20,
				 'maxGDD':1720,'CropsOverlap':7},
				 {'id': 2, 'name': 'mais600_bis',
				  'minSowingDate': 20, 'sowingDelay': 90, 'T_sowing': 9,
				  'Vern': 0, 'Tdaybase': 9, 'Tcutoff': 30, 'Tv_min': 3, 'Tv_max': 10, 'Vslope': 7, 'Vstart': 10,
				  'Vend': 50, 'VFmin': 0,
				  'ph_r': 0, 'daylength_if': 8, 'daylength_ins': 20,
				  'maxGDD': 1720, 'CropsOverlap': 7}
				]

	days, DoY,cropsOverYear = computeCropSeq(wsLat = 49.5, startDay = date(2000,1,1),
											  Tmax = df['T_max'], Tmin  = df['T_min'], cropSeq=cropsList)

	fig, axs = plt.subplots(2, 1)
	axs[0].plot(days, df['T_max'], label='T max')
	axs[0].plot(days, df['T_min'], label='T min')

	axs[1].plot(days, cropsOverYear, label='crop id')

	fig.tight_layout()
	plt.show()

def test3():
	import pandas as pd
	import matplotlib

	matplotlib.use('qt5agg')
	import matplotlib.pyplot as plt

	# open table
	csvFile = 'C:/test_landriano/test11_SIM/meteodata/100.dat'
	df = pd.read_csv(csvFile, sep=r'\s* \s*', usecols=['T_max', 'T_min'], skiprows=3, engine='python')

	cropsList = [{'id':1,'name':'mais600',
				 'minSowingDate':91, 'sowingDelay':14, 'T_sowing':9,
				 'Vern':0,'Tdaybase':9, 'Tcutoff':30,'Tv_min':3, 'Tv_max':10, 'Vslope':7,
				  'Vstart':10, 'Vend':50, 'VFmin':0,
				 'ph_r':0, 'daylength_if':8, 'daylength_ins':20,
				 'maxGDD':1720,'CropsOverlap':7},
				 {'id': 2, 'name': 'wheat',
				  'minSowingDate': 288, 'sowingDelay': 14, 'T_sowing': 0,
				  'Vern': 1, 'Tdaybase': 0, 'Tcutoff': 25, 'Tv_min': 3, 'Tv_max': 10, 'Vslope': 7,
				  'Vstart': 10,'Vend': 50, 'VFmin': 0,
				  'ph_r': 1, 'daylength_if': 8, 'daylength_ins': 20,
				  'maxGDD': 1020, 'CropsOverlap': 7}
				]

	days, DoY,cropsOverYear = computeCropSeq(wsLat = 49.5, startDay = date(2000,1,1),
											  Tmax = df['T_max'], Tmin  = df['T_min'], cropSeq=cropsList)

	fig, axs = plt.subplots(2, 1)
	axs[0].plot(days, df['T_max'], label='T max')
	axs[0].plot(days, df['T_min'], label='T min')

	axs[1].plot(days, cropsOverYear, label='crop id')

	fig.tight_layout()
	plt.show()

def test4():
	import pandas as pd
	import matplotlib

	matplotlib.use('qt5agg')
	import matplotlib.pyplot as plt

	# open table
	csvFile = 'C:/test_landriano/test11_SIM/meteodata/100.dat'
	df = pd.read_csv(csvFile, sep=r'\s* \s*', usecols=['T_max', 'T_min','U_min','V_med'], skiprows=3, engine='python')

	T_max = df['T_max'].to_numpy()
	T_min = df['T_min'].to_numpy()
	U_min = df['U_min'].to_numpy()
	V_med = df['V_med'].to_numpy()
	# add some dummy values
	T_max = np.concatenate((T_max[0:366], T_max, T_max[np.size(T_max) - 365:]))
	T_min = np.concatenate((T_min[0:366], T_min, T_min[np.size(T_min) - 365:]))
	U_min = np.concatenate((U_min[0:366], U_min, U_min[np.size(U_min) - 365:]))
	V_med = np.concatenate((V_med[0:366], V_med, V_med[np.size(V_med) - 365:]))

	T_max = movMean(T_max,n=20)
	T_min = movMean(T_min,n=20)



	mais600 = {'id': 1, 'name': 'mais600',
				'minSowingDate': 1, 'sowingDelay': 366, 'T_sowing': 14,
				'Vern': 0, 'Tdaybase': 9, 'Tcutoff': 30, 'Tv_min': 3, 'Tv_max': 10, 'Vslope': 7,
				'Vstart': 10, 'Vend': 50, 'VFmin': 0,
				'ph_r': 0, 'daylength_if': 8, 'daylength_ins': 20,
				'GDD': [35,40,170,650,1400,1720],
				'kcb': [0,0.15,0.15,1.15,1.15,0.15],
				'lai': [0,0.05,0.5,5.2,4.7,3.7],
				'hc': [0,0.02,0.6,3,3,2.5],
				'sr': [0,0.3,0.5,0.85,0.85,0.85],
			  	'CropsOverlap': 7}
	wheat = {'id': 2, 'name': 'wheat',
			'minSowingDate': 1, 'sowingDelay': 366, 'T_sowing': 0,
			'Vern': 1, 'Tdaybase': 0, 'Tcutoff': 25, 'Tv_min': 3, 'Tv_max': 10, 'Vslope': 7,
			'Vstart': 10,'Vend': 50, 'VFmin': 0,
			'ph_r': 1, 'daylength_if': 8, 'daylength_ins': 20,
			'GDD': [30,35,80,200,650,1020],
			'kcb': [0,0.15,0.15,1.10,1.10,0.15],
			'lai': [0,0.05,0.05,7,7,0.385],
			'hc': [0,0.1,0.1,0.6,0.6,0.6],
			'sr': [0,0.5,0.5,1,1,1],
			'CropsOverlap': 7}
	mais300 = {'id': 3, 'name': 'mais300',
			   'minSowingDate': 1, 'sowingDelay': 366, 'T_sowing': 9,
			   'Vern': 0, 'Tdaybase': 9, 'Tcutoff': 30, 'Tv_min': 3, 'Tv_max': 10, 'Vslope': 7,
			   'Vstart': 10, 'Vend': 50, 'VFmin': 0,
			   'ph_r': 0, 'daylength_if': 8, 'daylength_ins': 20,
			   'GDD': [90,110,250,650,1350,1520],
				'kcb': [0,0.15,0.15,1.15,1.15,0.5],
				'lai': [0,np.NaN,0.5,4.5,4,3.5],
				'hc': [0,0.1,0.1,2,2,1.8],
				'sr': [0,0.3,0.5,0.85,0.85,0.85],
			  	'CropsOverlap': 7}

	cropsList = [
		wheat
				]

	days, DoY,cropsOverYears,T_GDD_corr = computeCropSeq(wsLat = 49.5, startDay = date(2000,1,1),
											  Tmax = T_max, Tmin  = T_min, cropSeq=cropsList)

	laiValues = np.zeros(np.size(T_GDD_corr))
	kcbValues = np.zeros(np.size(T_GDD_corr))
	hcValues = np.zeros(np.size(T_GDD_corr))
	for crop in cropsList:
		laiValues += computeParamsDistro(cropsOverYears, T_GDD_corr, crop['id'], crop['GDD'], crop['lai'])
		kcbValues += computeParamsDistro(cropsOverYears, T_GDD_corr, crop['id'], crop['GDD'], crop['kcb'])
		hcValues += computeParamsDistro(cropsOverYears, T_GDD_corr, crop['id'], crop['GDD'], crop['hc'])

	cropsOverYears[cropsOverYears==0]=np.NaN

	adjKcbValues,flatIdx,descIdx = adjustKcb(kcbValues,U_min,V_med,hcValues)


	fig, axs = plt.subplots(4, 1,sharex=True)
	axs[0].plot(days, T_max, label='T max', color='red')
	axs[0].plot(days, T_min, label='T min',color='blue')
	axs[0].legend()

	axs[1].plot(days, cropsOverYears, label='crop id',color='green')

	axs[2].plot(days, T_GDD_corr, label='T GDD',color='orange')

	axs[3].plot(days, kcbValues, label='Kcb', color='green')
	axs[3].plot(days, adjKcbValues, label='Kcb adj.', color='red')
	# mark flat areas
	flatIdx = flatIdx.flatten().tolist()
	# mark desc ares
	descIdx = descIdx.flatten().tolist()

	axs[3].plot(days[flatIdx], kcbValues[flatIdx], 'go', label='flat')
	axs[3].plot(days[descIdx], kcbValues[descIdx], 'r+', label='desc')

	axs[3].legend()

	fig.tight_layout()
	plt.show()


if __name__ == '__main__':
	test4()
