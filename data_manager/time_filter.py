from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from datetime import datetime
from datetime import timedelta
import os

class TimeFilter(QWidget):
	def __init__(self,initStartDate = '2000-01-01', initEndDate='2005-12-31'):
		QWidget.__init__(self)
		self.initStartDate = initStartDate
		self.initEndDate = initEndDate
		
		self.installation_dir = os.path.dirname(__file__)
		uiFilePath = os.path.abspath(os.path.join(self.installation_dir, 'time_filter.ui'))
		uic.loadUi(uiFilePath, self)
		
		self.objName = 'FIRST_RB'
		
		for rb in self.findChildren(QRadioButton):
			rb.toggled.connect(self.onClicked)
		
		# init year selector
		if self.initStartDate !='':
			startDate = datetime.strptime(self.initStartDate, '%Y-%m-%d')
		else:
			startDate = datetime.now()
			
		if self.initEndDate !='':
			endDate   = datetime.strptime(self.initEndDate, '%Y-%m-%d')
		else:
			endDate = datetime.now()
			
		yearList = range(startDate.year, endDate.year+1)
		yearList = [str(y) for y in yearList]
		self.YEAR_CB.clear()
		self.YEAR_CB.addItems(yearList)
		
		# init period selector
		self.FROMDAY.setDate(startDate)
		self.TODAY.setDate(endDate)
				
		self.YEAR_FR.setEnabled(False)
		self.PERIOD_FR.setEnabled(False)
		
	def setTimeRange(self,initStartDate = '2000-01-01', initEndDate='2005-12-31'):
		self.initStartDate = initStartDate
		self.initEndDate = initEndDate
		
	def onClicked(self):
		
		radioButton = self.sender()
		if not radioButton.isChecked(): return
		
		self.objName = radioButton.objectName()
		
		if self.objName == 'FIRST_RB':
			# disable other witgets
			self.YEAR_FR.setEnabled(False)
			self.PERIOD_FR.setEnabled(False)
		
		if self.objName == 'LAST_RB':
			# disable other witgets
			self.YEAR_FR.setEnabled(False)
			self.PERIOD_FR.setEnabled(False)
		
		if self.objName == 'YEAR_RB':
			# disable other witgets
			self.YEAR_FR.setEnabled(True)
			self.PERIOD_FR.setEnabled(False)
			
		if self.objName == 'PERIOD_RB':
			# disable other witgets
			self.YEAR_FR.setEnabled(False)
			self.PERIOD_FR.setEnabled(True)
			
		if self.objName == 'ALL_RB':
			# disable other witgets
			self.YEAR_FR.setEnabled(False)
			self.PERIOD_FR.setEnabled(False)
		
			
	def getTimeLimits(self):
		startDate = None
		endDate = None
		
		if self.objName == 'FIRST_RB':
			# set up start and end date
			startDate = datetime.strptime(self.initStartDate,'%Y-%m-%d').strftime("%Y-%m-%d")
			endDate = (datetime.strptime(self.initStartDate,'%Y-%m-%d')+ timedelta(days=100)).strftime("%Y-%m-%d")
			
		if self.objName == 'LAST_RB':
			# set up start and end date
			startDate = (datetime.strptime(self.initEndDate,'%Y-%m-%d')- timedelta(days=100)).strftime("%Y-%m-%d")
			endDate = (datetime.strptime(self.initEndDate,'%Y-%m-%d')).strftime("%Y-%m-%d")
			
		if self.objName == 'YEAR_RB':
			# get selected year
			selYear = self.YEAR_CB.currentText()
			# set up start and end date
			startDate = (datetime.strptime('%s-01-01'%selYear,'%Y-%m-%d')).strftime("%Y-%m-%d")
			endDate = (datetime.strptime('%s-12-31'%selYear,'%Y-%m-%d')).strftime("%Y-%m-%d")
			
		if self.objName == 'PERIOD_RB':
			# get from selected date 
			startDate = self.FROMDAY.date().toString("yyyy-MM-dd")
			endDate = self.TODAY.date().toString("yyyy-MM-dd")
		
		if self.objName == 'ALL_RB':
			# use extrem value
			startDate = (datetime.strptime(self.initStartDate,'%Y-%m-%d')).strftime("%Y-%m-%d")
			endDate = (datetime.strptime(self.initEndDate,'%Y-%m-%d')).strftime("%Y-%m-%d")
			
			
		return (startDate,endDate)