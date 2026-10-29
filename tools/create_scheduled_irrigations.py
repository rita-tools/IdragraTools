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

import io
import os
from .write_pars_to_template import writeParsToTemplate
import sqlite3 as sqlite
from datetime import date, timedelta
import numpy as np
import pandas as pd

def days_in_year(year):
    # return the number of days in specific year
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


def generate_year_doy_combinations(years, periods):
    result = []

    for period in periods:
        start, end, step = period['start_doy'], period['end_doy'], period['duration']

        for year in years:
            max_day = days_in_year(year)
            current_doy = start
            current_year = year

            while True:
                # Add (year-doy) couple only if the year is in the list
                if current_year in years:
                    result.append((current_year, current_doy))

                # next step
                current_doy += step

                # manage rollover
                if current_doy > max_day:
                    current_doy -= max_day
                    current_year += 1

                # exit condition:
                if (start <= end and current_year == year and current_doy > end) or \
                        (start > end and current_year > year and current_doy > end):
                    break

    return result

def createScheduledIrrigations(DBM,outPath, yr_list,h_irr=-1,feedback = None,tr=None):
    # the shape of the file must be:
    #    - an integer value "n" defining the number of record
    #    - a field header line
    #    - a 1-n list of record with data in the form:
    #    | irrigation unit id | year | doy | water depth |
    #      separated by tab character or spaces

    # h_irr could be a value greater than zero if it is a volume
    # or -1 to get fix volume defined by irrigation method
    # or -10 to fill field capacity
	# get node layers
    irrunitLay = DBM.getTableAsLayer(name='idr_distrmap')
    fld_names = [field.name() for field in irrunitLay.fields()]

    scheduled_list = []

    for feat in irrunitLay.getFeatures():
        # 'sum_start','sum_end','sum_turn','win_start','win_end','win_turn'
        id_distr = feat['id']
        sum_start = feat['sum_start'] if 'sum_start' in fld_names else None
        sum_end = feat['sum_end'] if 'sum_end' in fld_names else None
        sum_turn = feat['sum_turn'] if 'sum_turn' in fld_names else None
        win_start = feat['win_start'] if 'win_start' in fld_names else None
        win_end = feat['win_end'] if 'win_end' in fld_names else None
        win_turn = feat['win_turn'] if 'win_turn' in fld_names else None

        # create summer irrigation rotation
        if (sum_start and sum_end and sum_turn):
            if (sum_start < sum_end):
                # create irrigation scheduling
                res = generate_year_doy_combinations(yr_list,periods=[
                    {'start_doy': sum_start, 'end_doy': sum_end, 'duration': sum_turn}])
                scheduled_list += [(id_distr,)+ r + (h_irr,) for r in res]
            else:
                feedback.reportError(tr('Input error in scheduled irrigations: the summer irrigation ends ({sum_end}) before it starts ({sum_start}).'))
        # create winter irrigation rotation
        if (win_start and win_end and win_turn):
            if (win_start > win_end):
                # create irrigation scheduling
                res = generate_year_doy_combinations(yr_list, periods=[
                    {'start_doy': win_start, 'end_doy': win_end, 'duration': win_turn}])
                scheduled_list += [(id_distr,) + r + (h_irr,) for r in res]
            else:
                feedback.reportError(tr('Input error in scheduled irrigations: the winter irrigation starts ({win_start}) before it ends ({win_end}).'))

    scheduled_str = result = "\n".join(" ".join(map(str, s)) for s in scheduled_list)

    writeParsToTemplate(outfile=os.path.join(outPath, 'scheduled_irrigation.txt'),
						parsDict={'NUMOFROW': len(scheduled_list), 'RULELIST': scheduled_str},
						templateName='scheduled_irrigation.txt')
