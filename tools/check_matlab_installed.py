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
import subprocess
from os import *
from sys import platform

def checkMatlabInstalled(version= '9.9'):
	stderr = ''
	print('platform: ',platform)
	try:
		if platform == "win32":
			queryMLruntime = ['reg','query',r'HKEY_LOCAL_MACHINE\SOFTWARE\MathWorks\MATLAB Runtime'+'\\'+version]
			queryMLframework = ['reg','query',r'HKEY_LOCAL_MACHINE\SOFTWARE\MathWorks\MATLAB'+'\\'+version]

			# try with matlab runtime
			proc = subprocess.Popen(queryMLruntime, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='utf8')
			stdout, stderr = proc.communicate()

			# print('stdout1\n',stdout)
			# print('stderr1\n', stderr)
			# try with matlab framework
			if stderr:
				proc = subprocess.Popen(queryMLframework, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
										encoding='utf8')
				stdout, stderr = proc.communicate()
				# print('stdout2', stdout)
				# print('stderr2', stderr)
		if platform == "linux" or platform == "linux2":
			# linux
			pass
		elif platform == "darwin":
			# OS X
			pass
	except Exception as e:
		stderr = str(e)

	path2ML = ''
 	# if stderr:
	# 	path2ML=''
	# else:
	# 	stdout = stdout.replace('\n','')
	# 	toks = stdout.split('REG_SZ    ')
	# 	folderPath = toks[1]
	# 	if 'MATLAB Runtime' in folderPath:
	# 		path2ML = os.path.join(folderPath,'v'+version.replace('.',''), 'runtime', 'win64')
	# 	else:
	# 		path2ML = os.path.join(folderPath,'runtime','win64')

	return path2ML

if __name__ == '__main__':
	res = checkMatlabInstalled()
	print('res',res)
