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

def writeParsToTemplate(outfile, parsDict, templateName):
	content = ''
	try:
		templateFileName = templateName
		if not os.path.exists(templateName):
			templateFileName = os.path.join(os.path.dirname(__file__),'..','templates',templateName)

		# open template file
		f = open(templateFileName)
		template = f.read()
		f.close()
		# replace value from the dictionary
		for k,v in parsDict.items():
			template = template.replace('[%'+k+'%]', str(v))
		content = template
		# save file
		if outfile:
			f = open(outfile, "w")
			f.write(content)
			f.close()
	except Exception as e:
		print('error',str(e))

	return content
