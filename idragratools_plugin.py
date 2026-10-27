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

import gc
import math
import os
import re
import shutil
import sys
import inspect
import glob
from datetime import datetime, timedelta, date
import time
import random

import scipy.io as sio
import os.path as osp
import numpy as np

from qgis.PyQt import QtSql
from qgis.PyQt.QtXml import QDomDocument
from qgis import processing

from tools.export_geodata_vector import ExportGeodataVector
from .forms.report_view import ReportDialog
from .tools.show_message import showInfoMessageBox, showCriticalMessageBox
from .tools.network_analyst import NetworkAnalyst
from .tools.check_matlab_installed import checkMatlabInstalled
from .data_manager.chart_widget import ChartWidget
from .tools.gis_grid import GisGrid
from .tools.iface_progress import IfaceProgress
from .tools.import_raster_in_db import importRasterInDB
from .tools.my_progress import MyProgress
from .forms.manage_rasters_dialog import ManageRastersDialog
from .tools.export_irrigation_method import exportIrrigationMethod
from .forms.attribute_table_view import AttributesTableView
from .forms.new_db_dialog import NewDbDialog
from .tools.utils import returnExtent
from .tools.export_bat import exportCropCoefBat, exportIdrAgraBat
from .tools.export_land_use import exportLandUse
from .tools.export_water_sources import makeDischSerie, exportWaterSources
from .tools.write_pars_to_template import writeParsToTemplate

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

from qgis.core import QgsProcessingAlgorithm, QgsApplication, QgsProject, QgsProviderRegistry, QgsVectorLayer, \
    QgsGeometry, QgsFeature, QgsFeatureRequest, QgsExpression
from qgis.PyQt.QtCore import QVariant, QUrl

from qgis.PyQt.QtCore import qVersion, QCoreApplication, QLocale, QSettings, QTranslator, QThread, Qt, QTimer
from qgis.PyQt.QtGui import QIcon, QColor, QPixmap
from qgis.PyQt.QtWidgets import QMenu, QMessageBox, QProgressBar, QDialog

from .qt_compat import QAction

from .idragratools_provider import IdrAgraToolsProvider

from .forms.custom_input import *

from .tools.save_metadata import saveMetadata
from .tools.get_raster_geoinfo import getRasterGeoinfo
from .tools.get_vector_geoinfo import getVectorGeoinfo
from .tools.raster_extractor import rasterExtractor
from .tools.vector_extractor import vectorExtractor
from .tools.export_geodata import Exporter

from .tools.sqlite_driver import SQLiteDriver
from .tools.parse_par_file import parseParFile
from .tools.add_features_from_csv import addFeaturesFromCSV

from .tools.export_meteodata import exportMeteodataFromDB

import pandas as pd
import sys
if (sys.version_info >= (3, 9)):
    def checkTread(t):
        return t.is_alive()
else:
    def checkTread(t):
        return t.isAlive()


class Feedback():
    def __init__(self, iface):
        self.iface = iface
        self.progressMessageBar = iface.messageBar().createMessage("IdrAgraTools...")
        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.progressMessageBar.layout().addWidget(self.progress)
        self.iface.messageBar().pushWidget(self.progressMessageBar, Qgis.Info)

    def setPercentage(self, val):
        try:
            val = int(val)
        except:
            val = 0

        self.progress.setValue(val)

    def setInfo(self, msg):
        self.progressMessageBar.setText("INFO: %s" % msg)

    def error(self, msg):
        self.progressMessageBar.setText("ERROR: %s" % msg)

    def unload(self):
        self.progressMessageBar.clearWidgets()



class IdrAgraTools():

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        localePath = os.path.join(self.plugin_dir, 'i18n', 'idragra_tools_{}.qm'.format(locale))

        if os.path.exists(localePath):
            self.translator = QTranslator(QCoreApplication.instance())
            self.translator.load(localePath)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # add processing provider
        self.provider = IdrAgraToolsProvider()

        # TODO: check the latest version of idragra and cropcoef
        self.s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
        if self.s.value('idragraPath','')=='': self.s.setValue('idragraPath', os.path.join(self.plugin_dir,'bin','idragra.exe'))
        if self.s.value('cropcoeffPath','')=='': self.s.setValue('cropcoeffPath', os.path.join(self.plugin_dir,'bin','cropcoef.exe'))
        if self.s.value('MCRpath', '') == '': self.s.setValue('MCRpath',checkMatlabInstalled(version= '9.9'))
        #if self.s.value('MinGWPath', '') == '': self.s.setValue('MinGWPath', checkMatlabInstalled(version='9.9'))

        self.PRJNAME = 'Idragra simulation'
        self.FILEFORMAT = 'Geopackage file (*.gpkg)'#'Idragra db (*.idb)'
        self.FILEEXT = 'gpkg'#'idb'
        self.HTMLFILE = None # store reference to html report file

        self.STATFUN = {'SUM': self.tr('Sum'), 'AVG': self.tr('Mean'), 'MAX': self.tr('Max'), 'MIN': self.tr('Min')}

        # init table and layer names and labels
        # TODO: for the next release 'idr_gw_wells': self.tr('Ground water wells'),
        self.LYRNAME = {'idr_control_points':self.tr('Control points'),
                        'idr_domainmap':self.tr('Domain'),
                        'idr_nodes': self.tr('Nodes'),
                        'idr_links': self.tr('Links'),
                        'idr_distrmap': self.tr('Irrigation units'),
                        'node_act_disc': self.tr('Actual discharge at node (m^3/s)'),
                        'node_disc': self.tr('Estimated discharge at node (m^3/s)'),
                        'idr_weather_stations': self.tr('Weather stations'),
                        'idr_soilmap': self.tr('Soils map'),
                        'idr_soil_types': self.tr('Soil types'),
                        'idr_soil_profiles': self.tr('Soil profiles'),
                        'idr_usemap': self.tr('Uses map'),
                        'idr_irrmap': self.tr('Irrigation methods map'),
                        'idr_crop_types': self.tr('Crop types'),
                        'idr_soiluses': self.tr('Soil uses'),
                        'idr_irrmet_types': self.tr('Irrigation methods'),
                        'ws_tmin': self.tr('Min temp. (°C)'), 'ws_tmax': self.tr('Max temp.(°C)'),
                        'ws_ptot': self.tr('Precipitation (mm)'),
                        'ws_umin': self.tr('Min air humidity (-)'), 'ws_umax': self.tr('Max air humidity (-)'),
                        'ws_vmed': self.tr('Wind velocity (m/s)'), 'ws_rgcorr': self.tr('Solar radiation (MJ/m^2/d)'),
                        'ws_co2':self.tr('CO2 concentration (p.p.m.)')
                        }

        # the order is the same in the legend (from bottom to top)
        self.LYRGRPNAME = { 'idr_soil_types': self.tr('Soil'),
                            'idr_soil_profiles':self.tr('Soil'),
                            'idr_crop_types': self.tr('Land use'),
                            'idr_soiluses': self.tr('Land use'),
                            'idr_irrmet_types': self.tr('Land use'),
                            'ws_tmin': self.tr('Weather'), 'ws_tmax': self.tr('Weather'),
                            'ws_ptot': self.tr('Weather'),
                            'ws_umin': self.tr('Weather'), 'ws_umax': self.tr('Weather'),
                            'ws_vmed': self.tr('Weather'), 'ws_rgcorr': self.tr('Weather'),
                            'ws_co2': self.tr('Weather'),
                            'idr_soilmap': self.tr('Soil'),
                            'idr_usemap': self.tr('Land use'),
                            'idr_irrmap': self.tr('Land use'),
                            'idr_weather_stations': self.tr('Weather'),
                            'idr_gw_wells': self.tr('Ground water'),

                            'stp_irr': self.tr('Analysis'),
                            'stp_irr_distr': self.tr('Analysis'),
                            'stp_irr_loss': self.tr('Analysis'),
                            'stp_irr_privw': self.tr('Analysis'),
                            'stp_prec': self.tr('Analysis'),
                            'stp_runoff': self.tr('Analysis'),
                            'stp_trasp_act': self.tr('Analysis'),
                            'stp_trasp_pot': self.tr('Analysis'),
                            'stp_et_act': self.tr('Analysis'),
                            'stp_et_pot': self.tr('Analysis'),
                            'stp_caprise': self.tr('Analysis'),
                            'stp_flux2': self.tr('Analysis'),

                            'node_act_disc': self.tr('Network'),
                            'node_disc': self.tr('Network'),
                            'idr_nodes': self.tr('Network'), 'idr_links': self.tr('Network'),
                            'idr_distrmap': self.tr('Network'),

                            'idr_domainmap': self.tr('Computing'),

                            'idr_control_points': self.tr('Analysis')
                            }

        self.METEONAME = {'ws_tmin': self.tr('Min temp. (°C)'), 'ws_tmax': self.tr('Max temp.(°C)'),
                          'ws_ptot': self.tr('Precipitation (mm)'),
                          'ws_umin': self.tr('Min air humidity (-)'), 'ws_umax': self.tr('Max air humidity (-)'),
                          'ws_vmed': self.tr('Wind velocity (m/s)'), 'ws_rgcorr': self.tr('Solar radiation (MJ/m^2/d)'),
                          'ws_co2':self.tr('CO2 concentration (p.p.m.)')}

        self.WELLNAME = {'well_watertable': self.tr('Water table (m)')}

        self.CPVARNAME = {
            'cp_rain_mm': self.tr('Local precipitation (mm)'),
            'cp_Tmax': self.tr('Local max temp.(°C)'),
            'cp_Tmin': self.tr('local min temp.(°C)'),
            'cp_et0': self.tr('Potential ET (mm)'),
            'cp_kcb': self.tr('Crop coefficient'),
            'cp_lai': self.tr('Leaf Area index (-)'),
            'cp_pday': self.tr('p factor'),
            'cp_irrig_mm': self.tr('Irrigation (mm)'),
            'cp_peff_mm': self.tr('Local actual precipitation (mm)'),
            'cp_h2o_dispL_mm': self.tr('Gross available water (mm)'),
            'cp_h2o_disp_mm': self.tr('Net available water (mm)'),
            'cp_interception_mm': self.tr('Interception (mm)'),
            'cp_runoff_mm': self.tr('Runoff (mm)'),
            'cp_infiltration_mm': self.tr('Infiltration (mm)'),
            'cp_eva_pot_mm': self.tr('Potential evaporation (mm)'),
            'cp_eva_mm': self.tr('Actual evaporation (mm)'),
            'cp_perc1_mm': self.tr('1st layer percolation (mm)'),
            'cp_theta1_mm': self.tr('1st layer water content (mm)'),
            'cp_ponding_mm': self.tr('Ponding (mm)'),
            'cp_trasp_pot_mm': self.tr('Potential transpiration (mm)'),
            'cp_trasp_act_mm': self.tr('Actual transpiration (mm)'),
            'cp_ks': self.tr('Stress coefficient'),
            'cp_thickness_II_m': self.tr('2nd layer thickness (m)'),
            'cp_wat_table_depth_under_root_m': self.tr('Water table depth (m)'),
            'cp_capflux_mm': self.tr('Capillary rise (mm)'),
            'cp_perc2_mm': self.tr('2nd layer percolation (mm)'),
            'cp_theta2_mm': self.tr('2nd layer water content (mm)'),
            'cp_theta_old_mm': self.tr('Soil water content before (mm)'),
            'cp_rawbig': self.tr('RAW big'),
            'cp_rawinf': self.tr('RAW inf'),
            'cp_wat_table_depth_m': self.tr('Local Water table depth (mm)'),
            'cp_distr_irr_mm': self.tr('District irrigation (mm)'),
            'cp_priv_well_irr_mm': self.tr('Private well irrigation (mm)'),
            'cp_espperc1': self.tr('Esp perc 1'),
            'cp_espperc2': self.tr('Esp perc 2'),
            'cp_irr_loss_mm': self.tr('Irrigation losses (mm)')
        }

        # add control points time serie to analysis
        # for k,v in self.CPVARNAME.items():
        #     self.LYRGRPNAME[k]= self.tr('Analysis')
        #     self.LYRNAME[k]= v

#        print(self.LYRGRPNAME)

        self.STEPNAME = {
            'stp_irr': self.tr('Irrigation (mm)'),
            'stp_irr_distr': self.tr('Irrigation from district’s water supply (mm)'),
            'stp_irr_loss': self.tr('Irrigation losses (mm)'),
            'stp_irr_privw': self.tr('Irrigation from private wells (mm)'),
            'stp_prec': self.tr('Precipitation at field (mm)'),
            'stp_runoff': self.tr('Runoff (mm)'),
            'stp_trasp_act': self.tr('Actual transpiration (mm)'),
            'stp_trasp_pot': self.tr('Potential transpiration (mm)'),
            'stp_et_act': self.tr('Actual evapotranspiration (mm)'),
            'stp_et_pot': self.tr('Potential evapotranspiration (mm)'),
            'stp_caprise': self.tr('Capillary rise from groundwater (mm)'),
            'stp_flux2': self.tr(
                'Net flux to groundwater (mm)')
        }
        # add stepname to lyrname
        self.LYRNAME.update(self.STEPNAME)

        self.AGGRFUNCTIONS = {
            '_count':self.tr('Count'),
            '_sum': self.tr('Sum'),
            '_mean': self.tr('Mean'),
            '_median': self.tr('Median'),
            '_stdev': self.tr('Standard deviation'),
            '_min': self.tr('Minimum'),
            '_max': self.tr('Maximum'),
            '_range': self.tr('Range'),
            '_variance': self.tr('Variance'),
        }

        self.DISTRFUNCTIONS = {
            'repeat': self.tr('Repeat over the step'),
            'distribute': self.tr('Distribute over the step')
                               }

        self.WATERSOURCENAME = {'node_disc': self.tr('Estimated discharge (m^3/s)'),
                                'node_act_disc': self.tr('Actual discharge (m^3/s)')}

        self.STATS = {
                    'varName': self.tr('Variable'),
                    'startDate': self.tr('Start date'),
                    'endDate': self.tr('End date'),
                    'nOfExpDays': self.tr('Num. exp. val.'),
                    'nOfFilled': self.tr('Num. fil. val.'),
                    'fullness': self.tr('Perc. of fullness'),
                    'minVal': self.tr('Minimum'),
                    'maxVal': self.tr('Maximum'),
                    'meanVal': self.tr('Mean'),
                    'cumVal': self.tr('Cumulative'),
                    'perc25': self.tr('25 perc.'),
                    'perc50': self.tr('50 perc.'),
                    'perc75': self.tr('75 perc.'),
                    }

        self.GROUPBY = {
            'name':self.tr('Field name'),
            'id_soil':self.tr('Soil type'),
            'id_soiluse': self.tr('Soil use'),
            'id_wsource': self.tr('Water source'),
            'id_wstation': self.tr('Weather station'),
            'id_gw_well': self.tr('Ground water well'),
            'id_drainto': self.tr('Drainage node')
        }

        self.GROUPBYRASTER = {
            'irr_units':self.tr('Irrigation units'),
            'irr_meth': self.tr('Irrigation methods'),
            'soilid': self.tr('Soils type'),
            'soiluse': self.tr('Land uses')
        }

        self.ANNUALVARS = {
            'biomass_pot_1':self.tr('Potential biomass for the main crop (t/ha)'),
            'yield_act_1':self.tr('Actual yield for the main crop (t/ha)'),
            'yield_pot_1':self.tr('Potential yield for the main crop (t/ha)'),
            'biomass_pot_2':self.tr('Potential biomass for the second crop (t/ha)'),
            'yield_act_2':self.tr('Actual yield for the second crop (t/ha)'),
            'yield_pot_2':self.tr('Potential yield for the second crop (t/ha)'),
            'eff_tot':self.tr('Irrigation efficiency (-)'),
            'eva_act_agr':self.tr('Cumulative actual evapotranspiration (mm)'),
            'eva_pot_agr':self.tr('Cumulative potential evapotranspiration (mm)'),
            'flux_tot':self.tr('Net flux to groundwater (mm)'),
            'irr_loss':self.tr('Irrigation application losses (mm)'),
            'irr_mean':self.tr('Mean irrigation application (mm)'),
            'irr_nr':self.tr('Number of irrigation application (-)'),
            'irr_tot':self.tr('Cumulative irrigation (mm)'),
            'prec_tot':self.tr('Cumulative precipitation (mm)'),
            'run_tot':self.tr('Cumulative runoff (mm)'),
            'trasp_act_tot':self.tr('Cumulative actual transpiration (mm)'),
            'trasp_pot_tot':self.tr('Cumulative potential transpiration (mm)')
        }

        self.TIMESTEP = {
            'years': self.tr('Years'),
            'months': self.tr('Months'),
            'days': self.tr('Days')
        }

        self.SIMMODE = {
                        '0':'Without irrigation',
                        '1':'Consumptions',
                        '2':'Field capacity needs satisfaction',
                        '3':'Fixed volumes',
                        '4':'Scheduled irrigation [NOT AVAILABLE]'
                        }

        self.SIMDIC = {'DBFILE':'',
                       'LOAD_SAMPLE_PAR':True,
                       'LOAD_SAMPLE_DATA': False,
                        'OUTPUTPATH':'',
                        'OUTPUTFOLDER':'simout',
                        'SPATIALFOLDER':'geodata',
                        'METEOFOLDER':'meteodata',
                        'PHENOFOLDER':'pheno',
                        'IRRFOLDER':'irrmethods',
                        'WATSOURFOLDER':'wsources',
                        'WSFOLDER':'meteodata',
                        'WSFILE':'weather_stations.dat',
                        'CANOPYRESMOD':1,
                        'CO2FILE': 'CO2_conc.dat',
                        'MODE':0,
                        'CAPILLARYFLAG':'F',
                        'NOFMETEO':'',
                        'NUMMETEOWEIGTH':5,
                        'NOFSOILUSES':'',
                        'SOILUSESLIST':'',
                        'SOILUSEVARFLAG':'T',
                        'RANDWIND':6,
                        'STARTIRRSEASON':1,
                        'ENDIRRSEASON':366,
                        'NBASINS':0,
                        'NSOURCE':0,
                        'NSOURCEDER':0,
                        'NSFLOWWELLS':0,
                        'NTAILWAT':0,
                        'NPUBWELL':0,
                        'STARTYEAR' : '',
                        'ENDYEAR': '',
                        'YEARS':[],
                        'PERIOD':'',
                        'ZEVALAY':0.1,
                        'ZTRANSLAY':0.9,
                        'LANDUSES':'landuses',
                        'EXTENT': '',
                        'CRS': '',
                        'CELLSIZE': 250,
                        'WATERTABLEMAP': {},
                        'ELEVMAP': {},
                        'LANDUSEMAP':{},
                        'IRRMETHMAP': {},
                        'STARTOUTPUT':105,
                        'ENDOUTPUT': 273,
                        'STEPOUTPUT': 10,
                        'MONTHOUTPUT':'F',
                        'MINSLOPE':0.1,
                        'MAXSLOPE':1000,
                        'SOURCE_DB':'',
                        'DEFAULT_LU':0,
                        'DEFAULT_IM':0,
                        'VECTOR_MODE':0
                       }

        self.PHENOVARS = {'CNvalue':self.tr('CN value'),
                         'H':self.tr('Plant height'),
                         'Kcb':self.tr('Crop coefficient'),
                         'LAI': self.tr('Leaf area index'),
                         'Sr': self.tr('Root depth')
                         }

        # supported report types
        self.REPORT_TYPES = {'general': self.tr('Simulation overview'),
                            'annuals_totals': self.tr('Annual totals'),
                            'irrunits_totals': self.tr('Irrigation units totals')
                            }

        # enable macro for this session
        s = QgsSettings()
        self.MACROPOLICY = s.value('qgis/enableMacros')
        #self.TABLEPOLICY = s.value('qgis/attributeTableView')
        s.setValue('qgis/enableMacros', 'SessionOnly')
        #s.setValue('qgis/attributeTableView', 1)

        self.DBM = None

        # force activation state for specific names
        # None means always set as initialization
        self.actionList = ['Advanced','Options','testexport','Test']
        self.actionState = [None,None,None,None]

        self.mainMenu = None
        self.iface.projectRead.connect(self.loadFromProject)
        self.iface.newProjectCreated.connect(self.resetMenuItemState)

        # reload if project is already loaded
        #if QgsProject.instance():
        #    self.loadFromProject()

    def printSome(self):
        showCriticalMessageBox(self.tr('Not implemented yet'),
                                    self.tr('This function is not implemented, I\'m sorry :('),
                                    self.tr('Really so sorry ...'))

    def initGui(self):
        # add Main Menu
        self.mainMenu = self._addmenu(self.iface.mainWindow().menuBar(), 'IdrAgraTools', 'IdrAgraTools')
        self.dbMenu = self._addmenu(self.mainMenu, 'Database', self.tr('Start'),True)
        self._addmenuitem(self.dbMenu, 'LoadDB', self.tr('Open'), self.openDB, True)
        self._addmenuitem(self.dbMenu, 'NewDB', self.tr('New'), self.newDB, True)
        self.mainMenu.addMenu(self.dbMenu)

        self.weatherMenu = self._addmenu(self.mainMenu, 'Weather', self.tr('Weather'), False)
        self._addmenuitem(self.weatherMenu, 'ImportWeatherStations', self.tr('Import weather stations'), self.importWeatherStations,
                          False)
        # self._addmenuitem(self.weatherMenu, 'ImportWeightMap', self.tr('Import weight map'),
        #                   self.importWeightMap,
        #                   False)
        self._addmenuitem(self.weatherMenu, 'ImportMeteoData', self.tr('Import meteo data'), self.importMeteoData, False)

        self.mainMenu.addMenu(self.weatherMenu)


        self.soilMenu = self._addmenu(self.mainMenu, 'Soil', self.tr('Soil'), False)
        self._addmenuitem(self.soilMenu, 'ImportSoilMap', self.tr('Import soil map'), self.importSoilMap, False)
        #self._addmenuitem(self.soilMenu, 'EditSoilType', self.tr('Edit soil type'), self.printSome, False)

        self.mainMenu.addMenu(self.soilMenu)

        self.landuseMenu = self._addmenu(self.mainMenu, 'LandUse', self.tr('Land use'), False)
        self._addmenuitem(self.landuseMenu, 'ImportLandUseMap', self.tr('Import land use map [vector]'), self.importLandUseMap, False)
        self._addmenuitem(self.landuseMenu, 'SetLandUse', self.tr('Set/edit land use map [raster]'),
                          self.setRasterLanduse, False)

        #self._addmenuitem(self.landuseMenu, 'EditLandUseType', self.tr('Edit land use type'), self.printSome, False)
        self.mainMenu.addMenu(self.landuseMenu)

        self.irrigationMenu = self._addmenu(self.mainMenu, 'Irrigation', self.tr('Irrigation'), False)
        self._addmenuitem(self.irrigationMenu, 'ImportWaterDistrictMap', self.tr('Import irrigation units map'), self.importWaterDistrictMap, False)
        self._addmenuitem(self.irrigationMenu, 'importIrrMethMap', self.tr('Import irrigation methods map [vector]'),
                          self.importIrrMethMap, False)
        self._addmenuitem(self.irrigationMenu, 'SetIrrMeth', self.tr('Set/edit irrigation map [raster]'), self.setRasterIrrmeth, False)

        self._addmenuitem(self.irrigationMenu, 'ImportNodeMap', self.tr('Import node map'),  self.importNodes, False)
        self._addmenuitem(self.irrigationMenu, 'ImportLinkMap', self.tr('Import link map'), self.importLinks, False)
        #self._addmenuitem(self.irrigationMenu, 'CheckNetwork', self.tr('Check network'), self.printSome, False)
        self._addmenuitem(self.irrigationMenu, 'ImportDischargeData', self.tr('Import discharge data'), self.importDischargeData, False)

        self.mainMenu.addMenu(self.irrigationMenu)

        self.elevationMenu = self._addmenu(self.mainMenu, 'Elevation', self.tr('Elevation'), False)
        self._addmenuitem(self.elevationMenu, 'SetDTM', self.tr('Set/edit elevation'), self.setElevation, False)
        self.mainMenu.addMenu(self.elevationMenu)

        self.wtMenu = self._addmenu(self.mainMenu, 'WaterTable', self.tr('Ground water'), False)
        self._addmenuitem(self.wtMenu, 'SetWT', self.tr('Set/edit water table'), self.setWaterTable, False)
        self.mainMenu.addMenu(self.wtMenu)

        self.cptMenu = self._addmenu(self.mainMenu, 'Domain', self.tr('Domain'), False)
        self._addmenuitem(self.cptMenu, 'ImportDomain', self.tr('Import domain'), self.importDomainMap, False)
        self._addmenuitem(self.cptMenu, 'CreateDomain', self.tr('Create domain'), self.createDomainMap, False)
        self.mainMenu.addMenu(self.cptMenu)

        self.simulationMenu = self._addmenu(self.mainMenu, 'Simulation', self.tr('IdrAgra'), False)
        self._addmenuitem(self.simulationMenu, 'RunAll', self.tr('Run all'), self.runAll, False)
        self.simulationMenu.addSeparator()
        self._addmenuitem(self.simulationMenu, 'Step1', self.tr('Set simulation'), self.setSimulation, False)
        self._addmenuitem(self.simulationMenu, 'Step2', self.tr('Export meteo data'), self.exportMeteoData, False)
        self._addmenuitem(self.simulationMenu, 'Step3', self.tr('Export spatial data'), self.exportSpatialData, False)
        self._addmenuitem(self.simulationMenu, 'Step4', self.tr('Export irrigation methods'),
                          self.exportIrrigationMethods, False)

        self._addmenuitem(self.simulationMenu, 'Step5', self.tr('Export water sources data'), self.exportWaterSourcesData, False)
        self._addmenuitem(self.simulationMenu, 'Step6', self.tr('Export simulation project'), self.exportSimProj, False)
        self._addmenuitem(self.simulationMenu, 'Step7', self.tr('Run CropCoef module'),
                          lambda: self.runAsThread(self.execBatFile, batFile ='run_cropcoef.bat'), False)

        self._addmenuitem(self.simulationMenu, 'Step8', self.tr('Run IdrAgra'),
                          lambda: self.runAsThread(self.execBatFile, batFile ='run_idragra.bat'), False)

        self.mainMenu.addMenu(self.simulationMenu)

        self.reportMenu = self._addmenu(self.mainMenu, 'GenerateReport', self.tr('Report for'), False)

        self._addmenuitem(self.reportMenu, 'GenerateReport0', self.tr('Simulation inputs overview'),
                          lambda: self.runAsThread(self.generateReport, self.showReportExplorer, repIndex=0),
                          False)

        self._addmenuitem(self.reportMenu, 'GenerateReport1', self.tr('Annual outputs totals'),
                          lambda: self.runAsThread(self.generateReport, self.showReportExplorer, repIndex=1),
                          False)

        self._addmenuitem(self.reportMenu, 'GenerateReport2', self.tr('Irrigation units outputs'),
                          lambda: self.runAsThread(self.generateReport, self.showReportExplorer, repIndex=2),
                          False)

        self.mainMenu.addMenu(self.reportMenu)

        self.analysisMenu = self._addmenu(self.mainMenu, 'Analysis', self.tr('Analysis'), False)
        #self._addmenuitem(self.analysisMenu, 'ImportControlPointsResults', self.tr('Import control points results'),
        #                  lambda: self.runAsThread(self.importControlPointsResults), False)

        self._addmenuitem(self.analysisMenu, 'ImportDistrictData', self.tr('Import irrigation units results'),
                          lambda: self.runAsThread(self.importWaterDistrictData), False)
        self._addmenuitem(self.analysisMenu, 'DischargeToNode', self.tr('Node water demand'),
                          lambda: self.runAsThread(self.computeNodeDischarge), False)
        self._addmenuitem(self.analysisMenu, 'GroupedStats', self.tr('Grouped statistics'),
                          self.makeGroupedStats, False)
        self._addmenuitem(self.analysisMenu, 'ImportResultsMap', self.tr('Import results map'),
                          self.importResultsMap, False)
        self._addmenuitem(self.analysisMenu, 'ManageTimeSerie', self.tr('Explore timeseries'), self.manageTimeSerie,
                          False)




        self.mainMenu.addMenu(self.analysisMenu)

        self.advancedMenu = self._addmenu(self.mainMenu, 'Advanced', self.tr('Advanced'), True)
        self._addmenuitem(self.advancedMenu, 'Options', self.tr('Options'), self.setOptions,True)
        #self._addmenuitem(self.advancedMenu, 'Test', self.tr('test'), lambda: self.runAsThread(self.test),True)
        #self._addmenuitem(self.advancedMenu, 'testexport', self.tr('Test esport'), self.createImageMap, True)

        self.mainMenu.addMenu(self.advancedMenu)

        # add to the QGIS GUI
        menuBar = self.iface.mainWindow().menuBar()
        menuBar.insertMenu(self.iface.firstRightStandardMenu().menuAction(), self.mainMenu)

        # Init settings
        # self.setSettings()

        # Init procesing provider
        QgsApplication.processingRegistry().addProvider(self.provider)

    # init demo db
    # self.openDB('C:/idragra_code/dataset/test.gpkg')

    def resetMenuItemState(self):
        if self.mainMenu:
            for action,activate in zip(self.actionList,self.actionState):
                if activate is not None:
                    try:
                        ACT = self.mainMenu.findChild(QAction, action)
                    except:
                        ACT = None

                    if ACT: ACT.setEnabled(activate)
                    MENU = self.mainMenu.findChild(QMenu, action)
                    if MENU: MENU.setEnabled(activate)


    def checkLayerToBeRemoved(self,layerIds):
        proj = QgsProject.instance()
        for id in layerIds:
            lay = proj.mapLayer (id)
            laySource = lay.source().replace('\\','/')

            for name,path in self.SIMDIC['RASTERMAP'].items():
                if laySource == path.replace('\\','/'):
                    showInfoMessageBox(
                        self.tr('The selected file is used as %s map and will be removed')%name,
                        self.tr('TODO: It may not effect the process...'))
                    #self.deleteRaster(name)

    def setMenuItemState(self):
        # activate function
        for action,activate in zip(self.actionList,self.actionState):
            if activate is not None:
                ACT = self.mainMenu.findChild(QAction, action)
                if ACT: ACT.setEnabled(not ACT.isEnabled())
                MENU = self.mainMenu.findChild(QMenu, action)
                if MENU: MENU.setEnabled(not MENU.isEnabled())

    def unload(self):
        self.mainMenu.deleteLater()
        # remove processing provider
        QgsApplication.processingRegistry().removeProvider(self.provider)
        # restore macro policy
        s = QgsSettings()
        s.setValue('qgis/enableMacros', self.MACROPOLICY)
        #s.setValue('qgis/attributeTableView', self.TABLEPOLICY)

    def _addmenuitem(self, parent, name, text, function, activate=True):
        if name not in self.actionList:
            self.actionList.append(name)
            self.actionState.append(activate)

        action = QAction(parent)
        action.setObjectName(name)
        action.setIcon(QIcon(self.plugin_dir + '/icons/' + name + '.svg'))
        action.setText(text)
        action.setEnabled(activate)
        # connect the action to the run method
        action.triggered.connect(function)
        # QObject.connect(action, SIGNAL("activated()"), function)
        parent.addAction(action)

    def _addAction(self, parent, name, text, description, function, checkable=False, activate=False):
        action = QAction(parent)
        action.setObjectName(name)
        action.setIcon(QIcon(self.plugin_dir + '/icons/' + name + '.svg'))
        action.setText(text)
        action.setWhatsThis(description)
        action.setCheckable(checkable)
        action.setEnabled(activate)
        action.triggered.connect(function)
        if parent:
            parent.addAction(action)
        else:
            self.iface.addToolBarIcon(action)

        return action

    def _addmenu(self, parent, name, text, activate=True):
        if name not in self.actionList:
            self.actionList.append(name)
            self.actionState.append(activate)
        menu = QMenu(parent)
        menu.setIcon(QIcon(self.plugin_dir + '/icons/' + name + '.svg'))
        menu.setObjectName(name)
        menu.setTitle(text)
        menu.setEnabled(activate)
        return menu

    def _getAction(self, parent, name):
        for action in parent.actions():
            if action.objectName() == name:
                return action

    def tr(self, source_text):
        return QgsApplication.translate('IdrAgraTools', source_text)

    def setSettings(self):
        s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
        if not s.value('bufDist'):
            s.setValue('bufDist', str(self.bufDist))
        else:
            self.bufDist = float(s.value('bufDist'))
        if not s.value('bufSeg'):
            s.setValue('bufSeg', str(self.bufSeg))
        else:
            self.bufSeg = int(s.value('bufSeg'))
        if not s.value('plotVar'):
            s.setValue('plotVar', self.plotVar)
        else:
            self.plotVar = s.value('plotVar')
        if not s.value('crsId'):
            s.setValue('crsId', str(self.CRS))
        else:
            self.CRS = int(s.value('crsId'))

    def setOptions(self):
        # show dialog to set options
        from .forms.common_settings import CommonSettings
        dlg = CommonSettings(self.iface)

        result = dlg.exec()
        # See if OK was pressed
        if result:
            res = dlg.getData()
            ### set executable path
            s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
            s.setValue('idragraPath', res['idragraPath'])
            s.setValue('cropcoeffPath', res['cropcoeffPath'])
            s.setValue('MCRpath', res['MCRpath'])
            s.setValue('MinGWPath', res['MinGWPath'])


    def extractDateTime(self, text, dateFormat='state_%d%m%y_%H%M.mat'):
        # filename is "state_080518_0000.mat"
        dt = datetime.strptime(text, dateFormat)
        return dt

    def newDB(self,isDemo = False):
        # get the filename of the project file
        proj = QgsProject.instance()
        filename = proj.fileName()
        crs =  proj.crs()
        #print('crs',crs.postgisSrid())
        # if filename == '':
        #     # ask to save the project first
        #     showCriticalMessageBox(self.tr("Please save the project first"),
        #                                 self.tr("Before continue you have to save the project"),
        #                                 self.tr("Go to Project --> Save "))
        # else:
        rootName = os.path.basename(filename)
        rootName = rootName[:-4]
        rootPath = os.path.dirname(filename)
        #dbpath = os.path.join(rootPath, rootName + '_DATA' + '.'+self.FILEEXT)
        dbpath = ''

        self.SIMDIC['DBFILE']= dbpath
        self.SIMDIC['OUTPUTPATH'] = os.path.join(rootPath, rootName + '_SIM')
        self.SIMDIC['CRS'] = crs.postgisSrid()
        self.updatePars()

        # show dialog
        # TODO
        dlg = NewDbDialog(self.iface.mainWindow(),self.SIMDIC,self.FILEEXT)
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            #print('res',res)
            self.SIMDIC['LOAD_SAMPLE_PAR'] = res['loadSamplePar']
            self.SIMDIC['LOAD_SAMPLE_DATA'] = res['loadSampleData']
            self.SIMDIC['DBFILE'] = res['dbFile']
            self.SIMDIC['SOURCE_DB'] = res['sourceFile']
            self.SIMDIC['CRS'] = res['crs']
            for rasterKey in ('WATERTABLEMAP', 'ELEVMAP', 'LANDUSEMAP', 'IRRMETHMAP'):
                self.SIMDIC[rasterKey] = {}
            rootName = os.path.basename(res['dbFile'])
            rootName = rootName[:-5]
            rootPath = os.path.dirname(res['dbFile'])

            self.SIMDIC['OUTPUTPATH'] = os.path.join(rootPath, rootName + '_SIM')
            self.updatePars()

            self.runAsThread(self.newDBTH,self.updateProj)

    def updateProj(self,dbpath = None):
        if not dbpath:
            dbpath = self.SIMDIC['DBFILE']
        else:
            self.SIMDIC['DBFILE'] = dbpath

        self.DBM = SQLiteDriver(dbpath, False,None,None,self.tr, QgsProject.instance())
        # activate other actions
        self.setMenuItemState()
        # load layers
        self.loadLayer()
        self.setupAllLayers()
        self.updatePars()

    def updatePars(self):
        proj = QgsProject.instance()
        #proj.writeEntry('IdrAgraTools', 'dbname', str(self.SIMDIC['DBFILE']))
        proj.writeEntry('IdrAgraTools', 'simsettings', str(self.SIMDIC))
        #print('OK update pars',str(self.SIMDIC))
        uri = 'geopackage:'+self.SIMDIC['DBFILE']+'?projectName='+self.PRJNAME
        #print('updatePars, CRS', self.SIMDIC['CRS'])
        try:
            crsCode = float(self.SIMDIC['CRS'])
            crs = QgsCoordinateReferenceSystem()
            # crs.createFromSrid(self.SIMDIC['CRS']) deprecated since 3.10
            crs.createFromSrsId(crsCode)
        except:
            crsCode = self.SIMDIC['CRS']
            crs = QgsCoordinateReferenceSystem(crsCode)


        proj.setCrs(crs)
        proj.write(uri)
        proj.writeEntry('Paths', 'Absolute', 'false')
        proj.write(uri)

        # if dialog res is true then
            # set up SIMDICT

    def newDBTH(self,progress):
        crs = QgsCoordinateReferenceSystem()
        #crs.createFromSrsId(int(self.SIMDIC['CRS']))
        crs.createFromString('EPSG:%s'%self.SIMDIC['CRS'])
        # print('crs id',self.SIMDIC['CRS'])
        # print(crs)

        if (os.path.isfile(self.SIMDIC['SOURCE_DB'])):
            processing.run("idragratools:IdragraCreateDB", {'DB_FILENAME': self.SIMDIC['DBFILE'],
                                                            'CRS': crs,
                                                            'LOAD_SAMPLE_PAR': False,
                                                            'LOAD_SAMPLE_DATA': False},
                           context=None, feedback=progress, is_child_algorithm=False)

            res = processing.run("idragratools:IdragraImportFromExistingDB", {'SOURCE_DB': self.SIMDIC['SOURCE_DB'],
                                                                        'ASSETS': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
                                                                                   12, 13, 14, 15, 16, 17, 18, 19, 20,
                                                                                   21, 22, 23, 24, 25, 26, 27, 28, 29,
                                                                                   30, 31, 32, 33, 34],
                                                                        'RASTER_FLAG': True,
                                                                        'DEST_DB': self.SIMDIC['DBFILE']},
                           context = None, feedback = progress, is_child_algorithm = False)
            # update current settings
            self.SIMDIC['WATERTABLEMAP'] = res['WATERTABLE']
            self.SIMDIC['ELEVMAP'] = res['ELEVATION']
        else:
            processing.run("idragratools:IdragraCreateDB", {'DB_FILENAME': self.SIMDIC['DBFILE'],
                                                            'CRS': crs,
                                                            'LOAD_SAMPLE_PAR': bool(self.SIMDIC['LOAD_SAMPLE_PAR']),
                                                            'LOAD_SAMPLE_DATA': bool(self.SIMDIC['LOAD_SAMPLE_DATA'])},
                           context=None, feedback=progress, is_child_algorithm=False)

    def openDB(self, dbpath=None):
        s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
        if not dbpath:
            #print('dbpath in openDB',dbpath)
            dbpath = QFileDialog.getOpenFileName(None, self.tr('Open idragra database'), s.value('lastPath'),
                                                 self.tr(self.FILEFORMAT))
            dbpath = dbpath[0]
            if not dbpath:
                return

        proj = None
        # update project record
        # see https://gis.stackexchange.com/questions/357344/trying-to-repair-layer-paths-on-opening-of-a-qgis-project-from-geopackage
        def path_processor(path):
            # Replacing GPKG datasources if project is stored in GPKG
            simDict = eval(proj.readEntry('IdrAgraTools', 'simsettings')[0])
            oldPath = simDict['DBFILE']
            oldFileName = os.path.basename(oldPath)
            if dbpath:
                fileName = os.path.basename(dbpath)
                if re.search(oldFileName, path, flags=re.IGNORECASE):
                    if not re.search(fileName, path, flags=re.IGNORECASE):
                        QgsMessageLog.logMessage('Replace Layer Source: %s' % path, 'GPKG', Qgis.Info)
                        path = re.sub(oldFileName, fileName, path, flags=re.IGNORECASE)
                        QgsMessageLog.logMessage('with: %s' % path, 'GPKG', Qgis.Info)

            return path

        idProc = QgsPathResolver.setPathPreprocessor(path_processor)

        proj = QgsProject.instance()
        uri = 'geopackage:' + dbpath + '?projectName=' + self.PRJNAME
        proj.read(uri)

        # load parameters without removing defaults if exist
        tempSimDic = eval(proj.readEntry('IdrAgraTools', 'simsettings')[0])
        for k,v in tempSimDic.items():
            self.SIMDIC[k]=v
        for rasterKey in ('WATERTABLEMAP', 'ELEVMAP', 'LANDUSEMAP', 'IRRMETHMAP'):
            rasterMap = self.SIMDIC.get(rasterKey, {})
            if isinstance(rasterMap, dict):
                self.SIMDIC[rasterKey] = {name: source for name, source in rasterMap.items() if name}

        # TODO: INIT DB
        self.updateProj(dbpath)

        # TODO: check path to raster
        # self.DBM = SQLiteDriver(dbpath, False,None,None,self.tr, QgsProject.instance())
        # # activate other actions
        # self.setMenuItemState()
        # # load layers
        # self.loadLayer()
        # self.setupAllLayers()
        #
        # # add to project
        # #QgsProject.instance().writeEntry('IdrAgraTools', 'dbname', str(dbpath))
        # self.SIMDIC['DBFILE'] = str(dbpath)
        # self.updatePars()

        # remove preprocessor
        QgsPathResolver.removePathPreprocessor(idProc)

    def loadLayer(self):
        project = QgsProject.instance()
        dbPath = os.path.normcase(os.path.abspath(self.DBM.DBName))

        def sourceIdentity(layer):
            if layer.providerType() != 'ogr':
                return None
            decoded = QgsProviderRegistry.instance().decodeUri('ogr', layer.source())
            path = decoded.get('path', '')
            tableName = decoded.get('layerName', '')
            if not path or not tableName:
                sourceParts = layer.source().replace('\\', '/').split('|')
                path = path or sourceParts[0]
                for part in sourceParts[1:]:
                    if part.casefold().startswith('layername='):
                        tableName = part.split('=', 1)[1]
                        break
            if not path or not tableName:
                return None
            path = project.readPath(path)
            return os.path.normcase(os.path.abspath(path)), tableName.casefold()

        existingLayers = {}
        for layer in project.mapLayers().values():
            identity = sourceIdentity(layer)
            if identity and identity[0] == dbPath:
                existingLayers.setdefault(identity[1], []).append(layer)

        for n, a in self.LYRNAME.items():
            matches = existingLayers.get(n.casefold(), [])
            validMatches = [layer for layer in matches if layer.isValid()]
            if validMatches:
                keepLayer = validMatches[0]
                for duplicate in matches:
                    if duplicate.id() != keepLayer.id():
                        project.removeMapLayer(duplicate.id())
                continue

            for brokenLayer in matches:
                project.removeMapLayer(brokenLayer.id())

            gpkg_layer = self.DBM.DBName + '|layername=' + n
            gpkg_layer = gpkg_layer.replace('\\', '/')
            vlayer = QgsVectorLayer(gpkg_layer, a, "ogr")
            if not vlayer.isValid():
                print("Failed to load layer %s"%a)  # TODO
            else:
                groupIndex, mygroup = self.getGroupIndex(self.LYRGRPNAME[n])
                print(os.path.join(self.plugin_dir, 'styles', n + '.qml'))
                vlayer.loadNamedStyle(os.path.join(self.plugin_dir, 'styles', n + '.qml'))
                project.addMapLayer(vlayer, False)
                mygroup.insertChildNode(groupIndex, QgsLayerTreeLayer(vlayer))

            # set up layer field

        # load rasters
        for n,s in self.SIMDIC['ELEVMAP'].items():
            self.loadRaster(rasterPath = s, rasterName=n, layGroup=self.tr('Elevation'))

        for n,s in self.SIMDIC['WATERTABLEMAP'].items():
            self.loadRaster(rasterPath = s, rasterName=n, layGroup=self.tr('Ground water'))

        for n,s in self.SIMDIC['IRRMETHMAP'].items():
            self.loadRaster(rasterPath = s, rasterName=n, layGroup=self.tr('Land use'))

        for n,s in self.SIMDIC['LANDUSEMAP'].items():
            self.loadRaster(rasterPath = s, rasterName=n, layGroup=self.tr('Land use'))


    def setupAllLayers(self):
        self.setupNodeLayer()
        self.setupLinkLayer()
        self.setupWeatherStationsLayer()
        self.setupCropTypesLayer()
        self.setupSoilUsesLayer()
        self.setupLanduseMapLayer()
        self.setupSoilMapLayer()
        self.setupIrrigationMapLayer()
        self.setupIrrTypesLayer()
        self.setupIrrigationUnitLayer()
        self.setupControlPointLayer()
        self.setupDomainLayer()

    def setupControlPointLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_control_points'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'control_point_dialog')

    def setupIrrigationUnitLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_distrmap'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'irrigation_unit_dialog')

    def setupNodeLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_nodes'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'node_dialog')

    def setupLinkLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_links'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'link_dialog')

    def setupWeatherStationsLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_weather_stations'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'weather_station_dialog')

    def setupCropTypesLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_crop_types'])
        for vlayer in vlayerList:
            self.setFieldCheckable(vlayer, 'irrigation')
            self.setFieldCheckable(vlayer, 'vern')
            self.setCustomForm(vlayer, 'crop_type_dialog')

    def setupSoilUsesLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_soiluses'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'soiluse_dialog')

    def setupIrrigationMapLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_irrmap'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'irrigation_map_dialog')

    def setupLanduseMapLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_usemap'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'landuse_dialog')

    def setupSoilMapLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_soilmap'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'soil_map_dialog')

        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_soil_types'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'soil_type_dialog')


        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_soil_profiles'])
        for vlayer in vlayerList:
            self.setCustomForm(vlayer, 'soil_profile_dialog')


    def setupIrrTypesLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_irrmet_types'])
        for vlayer in vlayerList:
            self.setFieldCheckable(vlayer, 'f_interception')
            self.setCustomForm(vlayer, 'irrigation_method_dialog')

    def setupDomainLayer(self):
        vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_domainmap'])
        for vlayer in vlayerList:
            print('domain map: %s'%vlayer.name())

    def importMeteoData(self):
        # get meteo id,name
        data = self.DBM.getRecord(tableName='idr_weather_stations',
                                  fieldsList=['id', 'name'], filterFld='', filterValue='')
        sensorsDict = {}
        for d in data:
            sensorsDict[d[0]] = '%s [%s]'%(d[1],d[0])

        self.importData(sensorsDict,self.METEONAME)

    def importDischargeData(self):
        # get meteo id,name
        data = self.DBM.getRecord(tableName='idr_nodes',
                                  fieldsList=['id', 'name'], filterFld='', filterValue='')
        sensorsDict = {}
        for d in data:
            sensorsDict[d[0]] = '%s [%s]' % (d[1], d[0])

        self.importData(sensorsDict, self.WATERSOURCENAME)

    def importData(self,sensorsDict = {},varDict={}):
        from .forms.import_data import ImportData
        dlg = ImportData(
            self.iface.mainWindow(), varDict, sensorsDict, self.s,
            databasePath=self.DBM.DBName
        )
        dlg.dataImported.connect(self.reloadImportedTimeSeries)
        dlg.exec()

    def reloadImportedTimeSeries(self, tableNames):
        tableNames = set(tableNames)
        for layer in QgsProject.instance().mapLayers().values():
            source = layer.source().replace('\\', '/')
            if any('|layername=%s' % tableName in source for tableName in tableNames):
                layer.dataProvider().reloadData()
                layer.triggerRepaint()

    def importWeatherStations(self):
        wsLay = self.getVectorLayerByName('idr_weather_stations')
        layList = self.getLayerList(geomTypeList = [QgsWkbTypes.PointGeometry])
        from .forms.import_vector_dialog import ImportVectorDialog
        dlg = ImportVectorDialog(self.iface.mainWindow(), layList = layList, fields=wsLay.fields(),
                                 skipFields = ['fid'], settings=self.s, title= self.tr('Weather stations'))
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            progress = IfaceProgress(self.iface)
            self.importVector(
                             fromLay=res['lay'],toLay=wsLay, fieldDict=res['fieldDict'],assignDate = None,
                             saveEdit = res['saveEdit'],
                             progress=progress)

    def importNodes(self):
        nodeLay = self.getVectorLayerByName('idr_nodes')
        layList = self.getLayerList(geomTypeList=[QgsWkbTypes.PointGeometry])
        from .forms.import_vector_dialog import ImportVectorDialog
        dlg = ImportVectorDialog(self.iface.mainWindow(), layList=layList, fields=nodeLay.fields(),
                                 skipFields=['fid'], settings=self.s, title= self.tr('Import nodes'))
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            progress = IfaceProgress(self.iface)
            self.importVector(
                fromLay=res['lay'], toLay=nodeLay, fieldDict=res['fieldDict'], assignDate=None,
                saveEdit=res['saveEdit'],
                progress=progress)


    def importLinks(self):
        linkLay = self.getVectorLayerByName('idr_links')
        layList = self.getLayerList(geomTypeList=[QgsWkbTypes.LineGeometry])
        from .forms.import_vector_dialog import ImportVectorDialog
        dlg = ImportVectorDialog(self.iface.mainWindow(), layList=layList, fields=linkLay.fields(),
                                 skipFields=['fid'], settings=self.s, title = self.tr('Import links'))
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            progress = IfaceProgress(self.iface)
            self.importVector(
                fromLay=res['lay'], toLay=linkLay, fieldDict=res['fieldDict'], assignDate=None,
                saveEdit=res['saveEdit'],
                progress=progress)

    def importVector(self,fromLay,toLay, fieldDict, assignDate = None, saveEdit = False, progress=None):
        # reset counter
        self.DBM.resetCounter()
        # start ediding
        toLay.startEditing()
        if toLay.isEditable():
            pass
        else:
            flg = toLay.startEditing()
            if flg == False:
                progress.reportError(
                    self.tr('Unable to edit layer %s') %
                    (toLay.name()), True)
                return

        pr = toLay.dataProvider()
        fieldNames = [field.name() for field in pr.fields()]

        # loop in fromLay feature
        nOfFeat =  fromLay.selectedFeatureCount()
        if nOfFeat>0:
            featureList = fromLay.getSelectedFeatures()
        else:
            nOfFeat = fromLay.featureCount()
            featureList = fromLay.getFeatures()

        i=0
        progress.pushInfo(self.tr('Copying features ...'))

        for feat in featureList:
            newFeat = QgsFeature(pr.fields())
            newFeat.setGeometry(feat.geometry())
            for k,v in fieldDict.items():
                #print('-->',k,v)
                idx = fieldNames.index(k)
                newFeat.setAttribute(idx, feat[v])

            if assignDate:
                idx = fieldNames.index('date')
                newFeat.setAttribute(idx, assignDate)

            toLay.addFeature(newFeat)

            i += 1
            if progress: progress.setPercentage(100 * i / nOfFeat)

        progress.pushInfo(self.tr('Copying completed!'))

        if saveEdit:
            toLay.commitChanges()
            progress.pushInfo(self.tr('Edits saved'))

    def importWeightMap(self):
        pass

    def importSoilMap(self):
        wsLay = self.getVectorLayerByName('idr_soilmap')
        layList = self.getLayerList(geomTypeList = [QgsWkbTypes.PolygonGeometry])
        from .forms.import_vector_dialog import ImportVectorDialog
        dlg = ImportVectorDialog(self.iface.mainWindow(), layList=layList, fields=wsLay.fields(),
                                 skipFields=['fid', 'name', 'date'], dateFld=[], settings=self.s,
                                 title=self.tr('Import soil map'),
                                 fieldLabels={
                                     'id': self.tr('Polygon ID'),
                                     'extid': self.tr('Soil type ID'),
                                 })
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            progress = IfaceProgress(self.iface)
            self.importVector(
                             fromLay=res['lay'], toLay=wsLay, fieldDict=res['fieldDict'], assignDate=res['assignDate'],
                             saveEdit=res['saveEdit'],
                             progress=progress)

    def importLandUseMap(self):
        wsLay = self.getVectorLayerByName('idr_usemap')
        layList = self.getLayerList(geomTypeList=[QgsWkbTypes.PolygonGeometry])
        from .forms.import_vector_dialog import ImportVectorDialog
        dlg = ImportVectorDialog(self.iface.mainWindow(), layList=layList, fields=wsLay.fields(),
                                 skipFields=['fid', 'name'], dateFld=['date'], settings=self.s,
                                 title=self.tr('Import land use map'),
                                 fieldLabels={
                                     'id': self.tr('Polygon ID'),
                                     'extid': self.tr('Land-use ID'),
                                 })
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            progress = IfaceProgress(self.iface)
            self.importVector(
                             fromLay=res['lay'], toLay=wsLay, fieldDict=res['fieldDict'], assignDate=res['assignDate'],
                             saveEdit=res['saveEdit'],
                             progress=progress)

    def importWaterDistrictMap(self):
        wsLay = self.getVectorLayerByName('idr_distrmap')
        layList = self.getLayerList(geomTypeList=[QgsWkbTypes.PolygonGeometry])
        from .forms.import_vector_dialog import ImportVectorDialog
        dlg = ImportVectorDialog(self.iface.mainWindow(), layList=layList, fields=wsLay.fields(),
                                 skipFields=['fid'], dateFld=[], settings=self.s, title= self.tr('Import irrigation units map'))
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            progress = IfaceProgress(self.iface)
            self.importVector(
                             fromLay=res['lay'], toLay=wsLay, fieldDict=res['fieldDict'], assignDate=None,
                             saveEdit=res['saveEdit'],
                             progress=progress)

    def importIrrMethMap(self):
        wsLay = self.getVectorLayerByName('idr_irrmap')
        layList = self.getLayerList(geomTypeList=[QgsWkbTypes.PolygonGeometry])
        from .forms.import_vector_dialog import ImportVectorDialog
        dlg = ImportVectorDialog(self.iface.mainWindow(), layList=layList, fields=wsLay.fields(),
                                 skipFields=['fid', 'name'], dateFld=[], settings=self.s,
                                 title=self.tr('Import irrigation methods map'),
                                 fieldLabels={
                                     'id': self.tr('Polygon ID'),
                                     'extid': self.tr('Irrigation method ID'),
                                 })
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            progress = IfaceProgress(self.iface)
            self.importVector(
                fromLay=res['lay'], toLay=wsLay, fieldDict=res['fieldDict'], assignDate=None,
                saveEdit=res['saveEdit'],
                progress=progress)

    def importDomainMap(self):
        domLay = self.getVectorLayerByName('idr_domainmap')
        layList = self.getLayerList(geomTypeList=[QgsWkbTypes.PolygonGeometry])
        from .forms.import_vector_dialog import ImportVectorDialog
        dlg = ImportVectorDialog(self.iface.mainWindow(), layList=layList, fields=domLay.fields(),
                                 skipFields=['fid'], dateFld=[], settings=self.s,
                                 title=self.tr('Import domain map'))
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            progress = IfaceProgress(self.iface)
            self.importVector(
                fromLay=res['lay'], toLay=domLay, fieldDict=res['fieldDict'], assignDate=None,
                saveEdit=res['saveEdit'],
                progress=progress)

    def createDomainMap(self):
        # open grid settings
        from .forms.create_grid_dialog import CreateGridDialog
        dlg = CreateGridDialog(self.iface,title=self.tr('Create regular domain grid'))
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        res = []
        if result == 1:
            res = dlg.getData()
            print('res',res)
            # res = {'cell_size':cell_size, 'grid_extent':grid_extent,'grid_crs':grid_crs,
            # 				'save_edits':save_edits,'use_integer':use_integer}
            progress = IfaceProgress(self.iface)

            cell_size = res['cell_size']
            grd_ext = res['grid_extent']
            grd_crs = res['grid_crs']

            save_edits = res['save_edits']
            # regularize the grid to integer coordinates
            if res['use_integer']:
                grd_ext = QgsRectangle(math.floor(grd_ext.xMinimum()),
                                       math.floor(grd_ext.yMinimum()),
                                       math.ceil(grd_ext.xMaximum()),
                                       math.ceil(grd_ext.yMaximum()))

            progress.setProgress(0.)
            progress.pushInfo(self.tr('Creating grid ...'))
            # run the algorithm
            self.algResults = processing.run("native:creategrid", {'TYPE': 2,
                                                 'EXTENT': '%s,%s,%s,%s [%s]'%(grd_ext.xMinimum(),grd_ext.xMaximum(),
                                                                                    grd_ext.yMinimum(),grd_ext.yMaximum(),grd_crs.authid()),
                                                 'HSPACING': cell_size, 'VSPACING': cell_size,
                                                 'HOVERLAY': 0, 'VOVERLAY': 0,
                                                 'CRS': grd_crs,
                                                 'OUTPUT': 'TEMPORARY_OUTPUT'},
                                                context=None, feedback=None, is_child_algorithm=False)

            progress.setProgress(50.)
            # copy the result to the map
            domLay = self.getVectorLayerByName('idr_domainmap')
            domLay.startEditing()
            c = 0
            #temp_lay = QgsVectorLayer(self.algResults['OUTPUT'], 'temp','ogr')
            num_feat = self.algResults['OUTPUT'].featureCount()
            for feat in self.algResults['OUTPUT'].getFeatures():
                c+=1
                progress.setProgress(100*c/num_feat)
                newFeat = QgsFeature(domLay.fields())
                newFeat.setGeometry(feat.geometry())
                newFeat['id'] = c
                newFeat['name'] = 'cell_grid_%s'%c
                newFeat['area_m2'] = feat.geometry().area()
                domLay.addFeature(newFeat)

            domLay.updateExtents()
            self.iface.mapCanvas().refresh()

            if save_edits: domLay.commitChanges()


    def getVectorLayerByName(self, tablename):
        gpkg_layer = self.DBM.DBName + '|layername=' + tablename
        gpkg_layer = gpkg_layer.replace('\\', '/')
        vLayer = None
        for layer in QgsProject.instance().mapLayers().values():
            if (layer.source().replace('\\', '/') == gpkg_layer) :
                vLayer = layer
                break

        if vLayer is None:
            vLayer = QgsVectorLayer(gpkg_layer, tablename, "ogr")

        return vLayer

    def getRasterLayerByName(self,tablename):
        gpkg_layer = 'GPKG:'+self.DBM.DBName + ':' + tablename
        gpkg_layer = gpkg_layer.replace('\\', '/')
        rLayer = None
        for layer in QgsProject.instance().mapLayers().values():
            if (layer.source().replace('\\', '/') == gpkg_layer) :
                rLayer = layer
                break

        return rLayer

    def getRasterLayerBySource(self,tablesource):
        rLayer = None
        for layer in QgsProject.instance().mapLayers().values():
            if (layer.source().replace('\\', '/') == tablesource) :
                rLayer = layer
                break

        return rLayer

    def getLayerByName(self,layName):
        rLayer = None
        for layer in QgsProject.instance().mapLayers().values():
            if (layer.name() == layName) :
                rLayer = layer
                break

        return rLayer

    def getLayerList(self,geomTypeList = [QgsWkbTypes.PointGeometry,QgsWkbTypes.LineGeometry,
                                          QgsWkbTypes.PolygonGeometry,QgsWkbTypes.UnknownGeometry,
                                          QgsWkbTypes.NullGeometry]):
        res = {}
        dbPath = getattr(getattr(self, 'DBM', None), 'DBName', '')
        dbPath = dbPath.replace('\\', '/').casefold()
        managedSources = {
            '%s|layername=%s' % (dbPath, tableName.casefold())
            for tableName in self.LYRNAME
        } if dbPath else set()

        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsMapLayer.VectorLayer:
                source = layer.source().replace('\\', '/').casefold()
                if any(source == managed or source.startswith(managed + '|') for managed in managedSources):
                    continue
                vector_type = layer.geometryType()
                if vector_type in geomTypeList:
                    res[layer.name()]=layer

        return res


    def manageTimeSerie(self):
        from .data_manager.data_manager_mainwindow import DataManagerMainwindow
        import copy
        import random

        minTime = ''
        maxTime = ''

        tNameList = list(self.METEONAME.keys()) + list(self.WATERSOURCENAME.keys())

        for tName in tNameList:
            vals = self.DBM.getMinMax(tName, 'timestamp')
            vals = vals[0]
            if vals[0]:
                if minTime == '':
                    minTime = vals[0]
                else:
                    if minTime > vals[0]:
                        minTime = vals[0]

            if vals[1]:
                if maxTime == '':
                    maxTime = vals[1]
                else:
                    if maxTime < vals[1]:
                        maxTime = vals[1]

        confDict = {}
        for lyrTable, lyrName in self.LYRNAME.items():
            # 'idr_crop_fields','idr_weather_stations','idr_gw_wells','idr_nodes','idr_links'
            lyrDict = {}
            baseList = []
            if lyrTable == 'idr_weather_stations':
                baseList = [{'name': self.METEONAME['ws_tmax'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
                             'axes': 'y', 'table': "ws_tmax", 'id': -1},
                            {'name': self.METEONAME['ws_tmin'], 'plot': 'False', 'color': '#00ffffff', 'style': '-',
                             'axes': 'y', 'table': "ws_tmin", 'id': -1},
                            {'name': self.METEONAME['ws_ptot'], 'plot': 'False', 'color': '#0000ff', 'style': 's',
                             'axes': 'y', 'table': "ws_ptot", 'id': -1},
                            {'name': self.METEONAME['ws_umin'], 'plot': 'False', 'color': '#00ffff54', 'style': '-',
                             'axes': 'y', 'table': "ws_umin", 'id': -1},
                            {'name': self.METEONAME['ws_umax'], 'plot': 'False', 'color': '#0000ff54', 'style': '-',
                             'axes': 'y', 'table': "ws_umax", 'id': -1},
                            {'name': self.METEONAME['ws_vmed'], 'plot': 'False', 'color': '#ff660054', 'style': '-',
                             'axes': 'y', 'table': "ws_vmed", 'id': -1},
                            {'name': self.METEONAME['ws_rgcorr'], 'plot': 'False', 'color': '#80800054', 'style': '-',
                             'axes': 'y', 'table': "ws_rgcorr", 'id': -1}
                            ]

            # if lyrTable == 'idr_control_points':
            #     baseList = [
            #         {'name': self.CPVARNAME['cp_rain_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_rain_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_Tmax'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_Tmax', 'id': -1},
            #         {'name': self.CPVARNAME['cp_Tmin'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_Tmin', 'id': -1},
            #         {'name': self.CPVARNAME['cp_et0'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_et0', 'id': -1},
            #         {'name': self.CPVARNAME['cp_kcb'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_kcb', 'id': -1},
            #         {'name': self.CPVARNAME['cp_lai'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_lai', 'id': -1},
            #         {'name': self.CPVARNAME['cp_pday'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_pday', 'id': -1},
            #         {'name': self.CPVARNAME['cp_irrig_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_irrig_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_peff_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_peff_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_h2o_dispL_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_h2o_dispL_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_h2o_disp_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_h2o_disp_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_interception_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_interception_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_runoff_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_runoff_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_infiltration_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_infiltration_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_eva_pot_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_eva_pot_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_eva_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_eva_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_perc1_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_perc1_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_theta1_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_theta1_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_ponding_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_ponding_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_trasp_pot_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_trasp_pot_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_trasp_act_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_trasp_act_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_ks'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-', 'axes': 'y',
            #          'table': 'cp_ks', 'id': -1},
            #         {'name': self.CPVARNAME['cp_thickness_II_m'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_thickness_II_m', 'id': -1},
            #         {'name': self.CPVARNAME['cp_wat_table_depth_under_root_m'], 'plot': 'False', 'color': '#ff0000ff',
            #          'style': '-', 'axes': 'y', 'table': 'cp_wat_table_depth_under_root_m', 'id': -1},
            #         {'name': self.CPVARNAME['cp_capflux_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_capflux_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_perc2_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_perc2_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_theta2_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_theta2_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_theta_old_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_theta_old_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_rawbig'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_rawbig', 'id': -1},
            #         {'name': self.CPVARNAME['cp_rawinf'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_rawinf', 'id': -1},
            #         {'name': self.CPVARNAME['cp_wat_table_depth_m'], 'plot': 'False', 'color': '#ff0000ff',
            #          'style': '-', 'axes': 'y', 'table': 'cp_wat_table_depth_m', 'id': -1},
            #         {'name': self.CPVARNAME['cp_distr_irr_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_distr_irr_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_priv_well_irr_mm'], 'plot': 'False', 'color': '#ff0000ff',
            #          'style': '-', 'axes': 'y', 'table': 'cp_priv_well_irr_mm', 'id': -1},
            #         {'name': self.CPVARNAME['cp_espperc1'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_espperc1', 'id': -1},
            #         {'name': self.CPVARNAME['cp_espperc2'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_espperc2', 'id': -1},
            #         {'name': self.CPVARNAME['cp_irr_loss_mm'], 'plot': 'False', 'color': '#ff0000ff', 'style': '-',
            #          'axes': 'y', 'table': 'cp_irr_loss_mm', 'id': -1}
            #     ]

            if lyrTable == 'idr_nodes':
                baseList = [
                    {'name': self.WATERSOURCENAME['node_disc'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'node_disc', 'id': -1},
                    {'name': self.WATERSOURCENAME['node_act_disc'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'node_act_disc', 'id': -1}
                ]

            if lyrTable == 'idr_distrmap':
                baseList = [
                    {'name': self.STEPNAME['stp_irr'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_irr', 'id': -1},
                    {'name': self.STEPNAME['stp_irr_distr'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_irr_distr', 'id': -1},
                    {'name': self.STEPNAME['stp_irr_loss'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_irr_loss', 'id': -1},
                    {'name': self.STEPNAME['stp_irr_privw'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_irr_privw', 'id': -1},
                    {'name': self.STEPNAME['stp_prec'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_prec', 'id': -1},
                    {'name': self.STEPNAME['stp_runoff'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_runoff', 'id': -1},
                    {'name': self.STEPNAME['stp_trasp_act'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_trasp_act', 'id': -1},
                    {'name': self.STEPNAME['stp_trasp_pot'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_trasp_pot', 'id': -1},
                    {'name': self.STEPNAME['stp_et_act'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_et_act', 'id': -1},
                    {'name': self.STEPNAME['stp_et_pot'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_et_pot', 'id': -1},
                    {'name': self.STEPNAME['stp_caprise'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_caprise', 'id': -1},
                    {'name': self.STEPNAME['stp_flux2'], 'plot': 'False', 'color': '', 'style': '-', 'axes': 'y',
                     'table': 'stp_flux2', 'id': -1},
                ]

            if len(baseList) > 0:
                # open layer
                # ~ gpkg_layer = self.DBM.DBName + '|layername='+lyrTable
                # ~ vLayer = QgsVectorLayer(gpkg_layer, lyrTable, "ogr")
                vlayerList = QgsProject.instance().mapLayersByName(self.LYRNAME[lyrTable])
                vLayer = None
                if len(vlayerList) > 0:
                    vLayer = vlayerList[0]

                    # thanks to https://gis.stackexchange.com/questions/138769/is-it-possible-to-sort-the-features-by-an-attribute-programmatically
                    request = QgsFeatureRequest()

                    # set order by field
                    clause = QgsFeatureRequest.OrderByClause('id', ascending=True)
                    orderby = QgsFeatureRequest.OrderBy([clause])
                    request.setOrderBy(orderby)

                    # loop in features
                    featDict = {}
                    if vLayer.selectedFeatureCount() > 0:
                        featList = vLayer.getSelectedFeatures(request)
                    else:
                        featList = vLayer.getFeatures(request)

                    for feat in featList:
                        f_add = 1
                        # ~ try: f_add = feat['f_alloutput']
                        # ~ except: f_add = 1

                        if f_add == 1:
                            # add to dictionary
                            featName = '%s [%s]' % (feat['name'], feat['id'])
                            featDict[featName] = copy.deepcopy(baseList)

                            for p in range(len(baseList)):
                                featDict[featName][p]['name'] = '%s [%s]' % (baseList[p]['name'], feat['id'])
                                featDict[featName][p]['id'] = feat['id']
                                if featDict[featName][p]['color'] == '': featDict[featName][p]['color'] = "#" + ''.join(
                                    [random.choice('0123456789ABCDEF') for j in range(6)])

                            confDict[self.LYRNAME[lyrTable]] = featDict

        self.dlg = DataManagerMainwindow(self.iface.mainWindow(), self.tr('Data manager'), confDict, self.DBM.DBName,
                                         minTime,
                                         maxTime,
                                         self.s)  # it's required the new mainwindow lives in the plugin object
        self.dlg.show()

    def runAll(self):
        self.setSimulation(callback = lambda: self.runAsThread(self.runAllTH))

    def runAllTH(self, progress):
        self.exportMeteoDataTH(progress)
        self.updatePars()
        self.exportSpatialDataTH(progress)
        self.updatePars()
        self.exportIrrigationMethodsTH(progress)
        self.updatePars()
        # if (self.SIMDIC['MODE'] in [1,'1']):
        #     self.exportWaterSourcesDataTH(progress)
        #     self.updatePars()
        #
        self.exportWaterSourcesDataTH(progress)
        self.updatePars()

        self.exportSimProjTH(progress)
        self.execBatFile('run_cropcoef.bat',progress)
        self.execBatFile('run_idragra.bat',progress)

    def setSimulation(self, callback = None):
        tNameList = list(self.METEONAME.keys()) + list(self.WATERSOURCENAME.keys())
        startDate, endDate = self.DBM.getMultiMinMax(tNameList, 'timestamp')
        # fix bug when no time series are imported
        yearList = []
        if (startDate and endDate):
            yearList = range(startDate, endDate + 1)
            yearList = [str(y) for y in yearList]
        else:
            showCriticalMessageBox(self.tr('Missing data'),
                                   self.tr('No time data to use'),
                                   self.tr('It is necessary to complete the database with time series'))
            return

        # get dictionary of landuses
        luDict = {0:self.tr('Not selected')}
        luDict.update(self.DBM.getDictFromTable('idr_soiluses','id','name'))
        #luDict[0] = self.tr('Not selected')

        # get dictionary of irrigation methods
        imDict = {0:self.tr('Not selected')}
        imDict.update(self.DBM.getDictFromTable('idr_irrmet_types', 'id', 'name'))
        #imDict[0] = self.tr('Not selected')

        # show dialog to choose folder and set simulation parameters
        from .forms.set_simulation_dialog import SetSimulationDialog
        # update extent and crs from domain map
        self.SIMDIC['EXTENT'] = self.getVectorLayerByName('idr_domainmap').extent().toString(4)
        # fix proj issues
        self.SIMDIC['CRS'] = self.getVectorLayerByName('idr_domainmap').crs().authid()

        dlg = SetSimulationDialog(self.iface, yearList, list(self.SIMMODE.values()),self.SIMDIC, luDict,imDict)
        result = 1
        #result = dlg.exec()
        # See if OK was pressed
        res = []
        def updateSim():
            res = dlg.getData()
            ### set output path
            self.SIMDIC['OUTPUTPATH'] = res['outfolder']
            self.SIMDIC['SOILUSEVARFLAG'] = res['useyearlymaps']
            ### set simulation options
            self.SIMDIC['RANDWIND'] = res['randWind']
            ### set simulation period
            self.SIMDIC['STARTYEAR'] = res['from']
            self.SIMDIC['ENDYEAR'] = res['to']
            self.SIMDIC['YEARS'] = list(range(res['from'], res['to'] + 1))
            ### set spatial resolution
            self.SIMDIC['VECTOR_MODE'] = res['vectorMode']
            self.SIMDIC['EXTENT'] = res['extent'].toString(4)
            # fix proj issues
            self.SIMDIC['CRS'] = res['crs'].authid()

            self.SIMDIC['CELLSIZE'] = res['cellsize']
            ### set hydrological model
            self.SIMDIC['ZEVALAY'] = res['zevalay']
            self.SIMDIC['ZTRANSLAY'] = res['ztranslay']
            self.SIMDIC['CAPILLARYFLAG'] = res['capRise']
            self.SIMDIC['MINSLOPE'] = res['minSlope']
            self.SIMDIC['MAXSLOPE'] = res['maxSlope']
            ### set irrigation variable
            self.SIMDIC['MODE'] = res['simMode']
            self.SIMDIC['STARTIRRSEASON'] = res['irrStart']
            self.SIMDIC['ENDIRRSEASON'] = res['irrEnd']
            ### set output settings
            self.SIMDIC['MONTHOUTPUT']=res['outMonth']
            self.SIMDIC['STARTOUTPUT'] = res['outStartDate']
            self.SIMDIC['ENDOUTPUT'] = res['outEndDate']
            self.SIMDIC['STEPOUTPUT'] = res['outStep']
            # set default landuse and method
            self.SIMDIC['DEFAULT_LU'] = res['defLU']
            self.SIMDIC['DEFAULT_IM'] = res['defIM']

            #print(self.SIMDIC)
            self.updatePars()

            if callback:
                callback()

        dlg.accepted.connect(updateSim)
        dlg.show()

        return result

    def calcRasterErrorTH(self, progress):
        # TODO: calculare raster error
        # get extention and make a shapefile
        # check soil map
        # check land use map
        # check irrigation units map
        # check irrigation methods map

        pass

    def exportIrrigationMethods(self):
        self.runAsThread(function = self.exportIrrigationMethodsTH, onFinished = None)

    def exportIrrigationMethodsTH(self,progress):
        # export irrigation parameters
        progress.setText(self.tr('Export irrigation parameters'))
        path2irrigation = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['IRRFOLDER'])
        if not os.path.exists(path2irrigation):
            os.makedirs(path2irrigation)
        else:
            progress.pushInfo('Directory %s already exists' % path2irrigation, False)

        exportIrrigationMethod(self.DBM, path2irrigation, progress, self.tr)

    def exportMeteoData(self,progress):
        self.runAsThread(function = self.exportMeteoDataTH, onFinished = self.updatePars)

    def exportMeteoDataTH(self,progress):
        # make output directory
        path2Pheno = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['PHENOFOLDER'])
        if not os.path.exists(path2Pheno):
            os.makedirs(path2Pheno)
        else:
            progress.pushInfo('Directory %s already exists' % path2Pheno, False)

        path2Meteodata = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['METEOFOLDER'])
        if not os.path.exists(path2Meteodata):
            os.makedirs(path2Meteodata)
        else:
            progress.pushInfo('Directory %s already exists' % path2Meteodata, False)

        path2Geodata = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['SPATIALFOLDER'])
        if not os.path.exists(path2Geodata):
            os.makedirs(path2Geodata)
            progress.pushInfo(self.tr('Exporting to %s ...') % path2Geodata)
        else:
            progress.pushInfo(self.tr('Directory %s already exists') % path2Geodata)

        # export meteo data
        progress.setText(self.tr('Export meteo data'))
        stationDataList, yearList, CO2List = exportMeteodataFromDB(self.DBM, path2Meteodata, self.SIMDIC['YEARS'][0], self.SIMDIC['YEARS'][-1], progress, self.tr)
        numOfStat = len(stationDataList)
        numOfMatrix = 5 # maximum number of weigth matrix
        if numOfStat<5:
            # this is very important because no data matrix delete precipitation without error
            numOfMatrix = numOfStat

        # in case of one station, weight is divided by two in order to sum to 100%
        if numOfMatrix == 1:
            numOfMatrix = 2

        self.SIMDIC['NOFMETEO']=numOfStat
        self.SIMDIC['NUMMETEOWEIGTH']= numOfMatrix

        stationsdata = '\n'.join(stationDataList)
        writeParsToTemplate(outfile=os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['WSFILE']),
                            parsDict={'NUMOFSTATIONS': numOfStat,
                                      'STATIONSDATA': stationsdata
                                      },
                            templateName='weather_stations.txt')

        # export CO2 data
        CO2Text = ''
        for y,co2 in zip(yearList,CO2List):
            if not co2:
                co2 = 337
                progress.reportError(self.tr('CO2 concentration set to default value (337 p.p.m.) for year %s')%y,False)

            CO2Text+='%s %s\n'%(y,co2)

        writeParsToTemplate(outfile=os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['CO2FILE']),
                            parsDict={'YEAR_CONC': CO2Text},
                            templateName='co2_conc.txt')

        progress.setText(self.tr('Export crop parameters'))
        path2fielduse = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['LANDUSES'])
        if not os.path.exists(path2fielduse):
            os.makedirs(path2fielduse)
        else:
            progress.pushInfo('Directory %s already exists' % path2fielduse, False)

        soiluseIds = exportLandUse(self.DBM, path2fielduse, progress, self.tr)
        #print('soiluseIds',soiluseIds)
        numOfLanduses = len(soiluseIds)
        self.SIMDIC['NOFSOILUSES'] = numOfLanduses
        self.SIMDIC['SOILUSESLIST'] = ' '.join(soiluseIds)

        # setup cropcoeff par file
        writeParsToTemplate(outfile=os.path.join(self.SIMDIC['OUTPUTPATH'], 'cropcoef.txt'),
                            parsDict={
                                'WSFILENAME': self.SIMDIC['WSFILE'],
                                'METEOFOLDER': self.SIMDIC['METEOFOLDER'],
                                'CROPFOLDER': self.SIMDIC['LANDUSES'],
                                'OUTPUTFOLDER': self.SIMDIC['PHENOFOLDER'],
                                'CANOPYRESMOD': self.SIMDIC['CANOPYRESMOD']
                            },
                            templateName='cropcoef.txt')

        progress.setPercentage(100.)

    def exportWaterSourcesData(self, progress):
        self.runAsThread(function=self.exportWaterSourcesDataTH, onFinished=self.updatePars)
        # if str(self.SIMDIC['MODE'])=='1':
        #     self.runAsThread(function = self.exportWaterSourcesDataTH, onFinished = self.updatePars)
        # else:
        #     showCriticalMessageBox(self.tr('Water sources are not required by simulation mode'),'','')

    def exportWaterSourcesDataTH(self, progress):
        progress.setText(self.tr('Export water sources'))
        path2WSources = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['WATSOURFOLDER'])
        if not os.path.exists(path2WSources):
            os.makedirs(path2WSources)
        else:
            progress.pushInfo('Directory %s already exists' % path2WSources, False)

        res = exportWaterSources(self.DBM, path2WSources, self.SIMDIC['YEARS'][0], self.SIMDIC['YEARS'][-1], progress, self.tr)

        # update sim parameters
        self.SIMDIC['NBASINS'] = res['nbasins']
        self.SIMDIC['NSOURCE'] = res['nsource']
        self.SIMDIC['NSOURCEDER'] = res['nsourceder']
        self.SIMDIC['NTAILWAT'] = res['noftwostage']
        self.SIMDIC['NPUBWELL'] = res['npubwell']

        progress.setPercentage(100.)

    def exportSimProj(self, progress):
        self.runAsThread(function = self.exportSimProjTH, onFinished = self.updatePars)

    def exportSimProjTH(self,progress):
        # export cell list
        progress.setPercentage(25.)
        progress.setText(self.tr('Export ancillary file'))

        # export simulation parameters
        progress.setPercentage(50.)
        progress.setText(self.tr('Export IdrAgra simulation parameters'))

        writeParsToTemplate(outfile=os.path.join(self.SIMDIC['OUTPUTPATH'], 'idragra_parameters.txt'),
                            parsDict=self.SIMDIC,
                            templateName='idragra_parameters.txt')

        progress.setPercentage(75.)
        progress.setText(self.tr('Export Cropcoeff simulation parameters'))

        # export bat/sh file
        progress.setPercentage(100.)
        progress.setText(self.tr('Export bat file'))

        exportCropCoefBat(self.SIMDIC['OUTPUTPATH'])
        exportIdrAgraBat(self.SIMDIC['OUTPUTPATH'])

    def exportSpatialData(self,progress):
        self.runAsThread(function = self.exportSpatialDataTH, onFinished = self.updatePars)
        #prog = MyProgress()
        #self.exportSpatialDataTH(prog)

    def exportSpatialDataTH(self,progress=None):
        progress.setProgress(0.0)

        path2Geodata = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['SPATIALFOLDER'])
        if not os.path.exists(path2Geodata):
            os.makedirs(path2Geodata)
            progress.pushInfo(self.tr('Exporting to %s ...') % path2Geodata)
        else:
            progress.pushInfo(self.tr('Directory %s already exists and all file will be remove') % path2Geodata)
            # delete all file
            fileList = glob.glob(os.path.join(path2Geodata, '*.*'))
            for f in fileList:
                os.remove(f)

        progress.setProgress(25.0)

        # get elevation layer
        # dtmLay = ''
        # try:
        #     dtmLay = self.SIMDIC['ELEVMAP']['elevation']
        # except:
        #     progress.reportError(self.tr('Elevation is not set'), False)

        # FIXED: check relative path
        #if dtmLay.startswith('.'):
        #    dtmLay = 'GPKG:'+os.path.join(os.path.dirname(self.SIMDIC['DBFILE']),dtmLay[2:])

        dtmLay = 'GPKG:' + self.SIMDIC['DBFILE'] + ':elevation'
        aRaster = QgsRasterLayer(dtmLay,'elevation','gdal') # check if dtm file exists

        if not aRaster.isValid():
            progress.reportError(self.tr('Unable to load elevation layer from %s')%dtmLay,False)
            dtmLay = ''

        # get water table maps
        wtLayDic = self.SIMDIC['WATERTABLEMAP']

        progress.setProgress(50.0)

        # TODO: choose type of exporter (regular, vector)


        if self.SIMDIC['VECTOR_MODE']:
            self.EXP = ExportGeodataVector(parent = QgsProject.instance(), sim_dict = self.SIMDIC,
                                           feedback=progress, tr=self.tr)
            self.EXP.exportGeodata()
        else:
            ext = returnExtent(self.SIMDIC['EXTENT'])

            self.EXP = Exporter(parent = QgsProject.instance(), simdic = self.SIMDIC, feedback=progress, tr=self.tr)
            self.EXP.exportGeodata(self.DBM, path2Geodata, ext, self.SIMDIC['CELLSIZE'], dtmLay,
                          wtLayDic, [self.SIMDIC['ZEVALAY'],self.SIMDIC['ZTRANSLAY']],
                          list(range(int(self.SIMDIC['STARTYEAR']),int(self.SIMDIC['ENDYEAR'])+1))
                          )

        progress.setProgress(100.0)

    def execBatFile(self, batFile, progress=None):
        import sys
        from subprocess import PIPE, Popen
        from threading import Thread, stack_size
        import os

        try:
            from Queue import Queue, Empty
        except ImportError:
            from queue import Queue, Empty  # python 3.x

        def enqueue_output(out, err, queue):
            for line in iter(out.readline, b''):
                queue.put(line)
            out.close()

            for e in iter(err.readline, b''):
                queue.put(e)
            err.close()

        if progress: progress.setPercentage(0.0)

        # update here *.bat file
        if batFile == 'run_cropcoef.bat':
            exportCropCoefBat(self.SIMDIC['OUTPUTPATH'])

        if batFile == 'run_idragra.bat':
            exportIdrAgraBat(self.SIMDIC['OUTPUTPATH'])

        # delete existing simulation TODO better fix
        if batFile == 'run_idragra.bat':
            outputPath = os.path.join(self.SIMDIC['OUTPUTPATH'],self.SIMDIC['OUTPUTFOLDER'])
            if os.path.exists(outputPath):
                if progress: progress.reportError(
                    self.tr('WARNING! output folder %s already exists and will be removed!')%outputPath,False)
                shutil.rmtree(outputPath)

        execPath = os.path.join(self.SIMDIC['OUTPUTPATH'], batFile)
        # print execPath,arg1,arg2
        if progress: progress.setText('%s' % (execPath))

        s = QSettings('UNIMI-DISAA', 'IdrAgraTools')
        # C:/Program Files/MATLAB/R2020b/runtime/win64
        MCRpath = s.value('MCRpath', '')
        # C:/MinGW/bin
        MinGWPath = s.value('MinGWPath', '')

        toks = os.environ['PATH'].split(';')
        if not MCRpath in toks:
            os.environ['PATH'] = os.environ['PATH'] + ';' + MCRpath

        if not MinGWPath in toks:
            os.environ['PATH'] = os.environ['PATH'] + ';' + MinGWPath

        try:
            # progress.setText('%s'%os.environ['PATH'])
            proc = Popen(([execPath]), shell=True, stdout=PIPE, stderr=PIPE)

            q = Queue()
            # ~ print('stacksize',stack_size())
            # ~ stack_size(200 * 1024 * 1024)
            # ~ print('stacksize2',stack_size())

            t = Thread(target=enqueue_output, args=(proc.stdout, proc.stderr, q))

            t.daemon = True  # thread dies with the program
            t.start()
            # t.join()

            perc = 0.0
            currentYear = -1
            year = -1

            while checkTread(t):
                try:
                    line = q.get(timeout=.1)  # q.get_nowait() # or #TODO_check performance
                    #line = q.get_nowait()
                    line = line.decode('utf-8','ignore')
                    line = line.strip()
                except Empty:
                    # do nothing
                    pass
                else:  # got line
                    # ... do something with line
                    if line.startswith('print'):
                        line = ''
                    elif line.startswith('Simulation day'):
                        toks = line.split()
                        try:
                            perc = float(toks[2]) / 366
                            year = int(toks[4])
                        except:
                            pass
                        line = ''
                    elif line.startswith('progress'):
                        toks = line.split()
                        try:
                            perc = float(toks[1]) / 100
                        except:
                            pass
                        line = ''
                    else:
                        line = line

                    if progress:
                        # print('perc',perc)
                        progress.setPercentage(100 * perc)
                        if line != '':
                            # print('line',line)
                            progress.setText(line)

                        if year != currentYear:
                            currentYear = year
                            progress.setText(self.tr('Current year: %s')%currentYear)


        except Exception as e:
            progress.setInfo('Processing error: %s' % (str(e)), True)

        #if progress: progress.setText(self.tr('Process concluded'))

    def readCropCoefReasults(self,varId, wsId,yearList = []):
        import pandas as pd
        msg = ''
        df = None
        if len(yearList) == 0:
            yearList = self.SIMDIC['YEARS']

        fileName = os.path.join(self.SIMDIC['OUTPUTPATH'],
                                self.SIMDIC['PHENOFOLDER'],
                                'Pheno_%s' % wsId, '%s.dat' % varId)

        # get date list
        if len(yearList)>0:
            dateList = pd.date_range(datetime.strptime('%s0101' % yearList[0], '%Y%m%d'),
                                     datetime.strptime('%s1231' % yearList[-1], '%Y%m%d'),
                                     freq='d').tolist()

        try:
            soiluseNames = self.DBM.getColumnValues(fieldName ='("[" || id || "] " || name) AS label' ,
                                                    tableName='idr_soiluses ORDER BY id')

            # this output are for matlab cropcoef
            # df = pd.read_csv(fileName, sep='\t', names = soiluseNames+['timestamp'],
            #                  engine='python', skiprows=1)
            df = pd.read_csv(fileName, sep=r'\s* \s*', names=soiluseNames + ['timestamp'],
                             skiprows=1)

            df['timestamp']=dateList
        except Exception as e:
            msg += str(e) + '\n'

        return df, msg

    def readControlPointsParams(self, r, c, yearList=[],varList = []):
        import pandas as pd
        df=None
        finalDF = pd.DataFrame(columns=['timestamp']+varList)
        msg=''
        if len(yearList)==0:
            yearList = self.SIMDIC['YEARS']

        for year in yearList:

            csvFile = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['OUTPUTFOLDER'],
                                   '%s_cellinfo_%s_%s.csv' % (year, r, c))
            try:
                # open csv file as dataframe
                df = pd.read_csv(csvFile, sep=r'\s*;\s*',names=['pars','value'],
                                 engine='python',header=0,skiprows=1)
                res = pd.DataFrame(columns=['timestamp'] + varList)
                dateList = pd.date_range(datetime.strptime('%s0101' % year, '%Y%m%d'),
                                         datetime.strptime('%s1231' % year, '%Y%m%d'),
                                         freq='d').tolist()
                res['timestamp'] = dateList

                for var in varList:
                    # find index
                    idxList = df.index[df['pars'] == var].tolist()
                    varValue = None
                    if len(idxList)>0:
                        varIdx = idxList[0]
                        varValue = df.iat[varIdx,1]

                    res[var]= [varValue]*len(dateList)

                #finalDF = finalDF.append(res, ignore_index=True) # deprecated
                finalDF = pd.concat([finalDF, res], ignore_index=True)

            except Exception as e:
                 msg += str(e)+'\n'

        return finalDF,msg

    def readControlPointsResults(self,r,c,yearList=None,columList = None):
        import pandas as pd
        msg = ''
        if yearList is None:
            yearList = self.SIMDIC['YEARS']

        finalDF = None
        for year in yearList:
            csvFile = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['OUTPUTFOLDER'],
                                   '%s_cell_%s_%s.csv' % (year, r, c))

            try:
                # open csv file as dataframe
                df = pd.read_csv(csvFile, sep=r'\s*;\s*',usecols = columList,engine='python')
                #print('df',year,df)
                # replace Giulian_date with date
                df['Giulian_day'] = df['Giulian_day'].apply(lambda x: datetime.strptime(str(year) + str(x), '%Y%j'))
                if finalDF is None:
                    finalDF = df
                else:
                    #finalDF = finalDF.append(df,ignore_index = True) # deprecated
                    finalDF = pd.concat([finalDF, df], ignore_index=True)

            except Exception as e:
                msg += str(e) + '\n'

        return finalDF,msg

    def getRowCol(self,feature):
        c = -1
        r = -1
        cp_id = feature['id']

        # open cells.txt and get c,r
        # ncells = 2
        # table =
        # ID	X	Y
        # 100	7	1
        # 21	19	1
        # endtable =
        cells_fn = os.path.join(self.SIMDIC['OUTPUTPATH'],'cells.txt')
        with open(cells_fn) as f:
            for line in f:
                if line.startswith(str(cp_id)+'\t'):
                    id,r,c = line.split('\t')
                    break

        return int(r), int(c)

    def getRowCol_OLD(self,feature):
        rasterExt = returnExtent(self.SIMDIC['EXTENT'])
        c=-1
        r=-1
        if rasterExt:
            cellDim = self.SIMDIC['CELLSIZE']
            # calculate extension
            xllcorner = rasterExt.xMinimum()
            # yllcorner = extension.yMinimum()
            yurcorner = rasterExt.yMaximum()
            h = rasterExt.height()
            w = rasterExt.width()

            nrows = round(h / cellDim)
            ncols = round(w / cellDim)

            xurcorner = xllcorner + ncols * cellDim
            # yurcorner = yllcorner+nrows*outputCellSize
            yllcorner = yurcorner - nrows * cellDim

            newExt = QgsRectangle(xllcorner, yllcorner, xurcorner, yurcorner)

            # make a grid object
            self.aGrid = GisGrid()
            self.aGrid.fitToExtent(newExt, cellDim, cellDim)
            if feature.geometry():
                x = feature.geometry().asMultiPoint()[0].x()
                y = feature.geometry().asMultiPoint()[0].y()
                c, r = self.aGrid.coordToCell(x, y)
                # fortran start form 1
                c+=1
                r+=1

        return r,c


    def importControlPointsResults(self, progress=None):
        if not progress:
            from .tools.my_progress import MyProgress
            progress = MyProgress()

        progress.pushInfo(self.tr('Note that it will refer to current simulation settings'))


        rasterExt = returnExtent(self.SIMDIC['EXTENT'])
        cellDim = self.SIMDIC['CELLSIZE']
        # calculate extension
        xllcorner = rasterExt.xMinimum()
        # yllcorner = extension.yMinimum()
        yurcorner = rasterExt.yMaximum()
        h = rasterExt.height()
        w = rasterExt.width()

        nrows = round(h / cellDim)
        ncols = round(w / cellDim)

        xurcorner = xllcorner + ncols * cellDim
        # yurcorner = yllcorner+nrows*outputCellSize
        yllcorner = yurcorner - nrows * cellDim

        newExt = QgsRectangle(xllcorner, yllcorner, xurcorner, yurcorner)

        # make a grid object
        self.aGrid = GisGrid()
        self.aGrid.fitToExtent(newExt, cellDim, cellDim)

        #print('aGrid',self.aGrid)
        # get CO layer
        self.vectorLay = self.getVectorLayerByName('idr_control_points')

        #print('vectorLay', self.vectorLay)
        varList = list(self.CPVARNAME.keys())
        #print('varList', varList)
        numYear = len(self.SIMDIC['YEARS'])
        #print('numYear',numYear)

        # use
        from .algs.idragra_bulk_import_timeserie import IdragraBulkImportTimeserie
        self.alg = IdragraBulkImportTimeserie()
        self.alg.DBM = self.DBM

        for feature in self.vectorLay.getFeatures():
            id = feature['id']
            progress.pushInfo(self.tr('Processing control point %s - %s')%(id,feature['name']))
            x = feature.geometry().asMultiPoint()[0].x()
            y = feature.geometry().asMultiPoint()[0].y()
            c, r = self.aGrid.coordToCell(x, y)
            #print('c', c,'r',r)
            c += 1
            r += 1

            for n, y in enumerate(self.SIMDIC['YEARS']):
                progress.setPercentage(100.0 * n / numYear)
                #print('y', y)

                # get r and c from
                filePath = os.path.join(os.path.join(self.SIMDIC['OUTPUTPATH'],
                                                     self.SIMDIC['OUTPUTFOLDER'],
                                                     '%s_cell_%s_%s.csv' % (y,r,c)))
                #print('filePath',filePath)
                if os.path.exists(filePath):
                    for i, var in enumerate(varList):
                        # import data from csv using sqlite query
                        self.alg.importDataFromCSV(filename=filePath, tablename=var, timeFldIdx=0,
                                               valueFldIdx=i + 1, sensorId=id, skip=1,
                                               timeFormat='%Y%j', column_sep=';', progress=progress, year=y)
                else:
                    progress.reportError(self.tr('Unable to find %s')%filePath,False)

    def importFromIdragra(self, progress=None):
        numOfTable = len(self.STEPNAME.items())
        n = 1
        for tableName, tableAlias in self.STEPNAME.items():
            if progress:
                progress.setText(self.tr('Processing %s') % tableAlias)
                progress.setPercentage(100.0 * n / numOfTable)

            self.importDataFromASCII(tableName)
            n += 1

    def importDataFromASCII(self, tablename):
        import glob
        from .tools.regenerate_idragra_output import readCellIndexFile
        varName = tablename.replace('stp_', '')
        concatValues = []

        # get fid from cellindex
        res = readCellIndexFile(os.path.join(self.OUTPUTPATH, 'geodata', 'validcell.asc'))
        sensorId = res['data']

        # get all file that ends with varName.asc
        for f in glob.glob(os.path.join(self.OUTPUTPATH, 'simout', '*%s.asc' % varName)):
            fname = os.path.basename(f)
            if ('step' in fname):
                # get filename and extract datetime
                timestamp = datetime.strptime(fname, '%Y_step%j_' + varName + '.asc')
                # get value from file
                res = readCellIndexFile(os.path.join(self.OUTPUTPATH, 'simout', fname))
                data = res['data']

                # populate query
                for i, d in enumerate(data):
                    concatValues.append("('" + timestamp.strftime('%Y-%m-%d') + "', '" + str(int(sensorId[i])) + "', '" + str(d) + "')")

        # create and submit query
        concatValues = ', '.join(concatValues)

        sql = 'DROP TABLE IF EXISTS dummy;'
        sql += 'CREATE TABLE dummy (timestamp2 text, wsid2 integer, recval2 double);'
        sql += 'BEGIN; '
        sql += 'REPLACE INTO dummy (timestamp2,wsid2,recval2) VALUES %s; ' % (concatValues)
        sql += 'COMMIT;'
        sql += 'UPDATE %s SET recval = (SELECT d.recval2 FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid)	WHERE EXISTS (SELECT * FROM dummy d WHERE d.timestamp2 = timestamp AND d.wsid2 = wsid);' % (
            tablename)
        sql += 'INSERT INTO %s (timestamp,wsid,recval) SELECT timestamp2,wsid2,recval2 FROM dummy d WHERE NOT EXISTS (SELECT * FROM %s WHERE timestamp = d.timestamp2 AND wsid = d.wsid2);' % (
        tablename, tablename)
        sql += 'DROP TABLE IF EXISTS dummy;'

        msg = self.DBM.executeSQL(sql)

    def importWaterDistrictData(self,progress=None):
        for v in list(self.STEPNAME.values()):
            i = list(self.STEPNAME.values()).index(v)
            k = list(self.STEPNAME.keys())[i]
            if progress: progress.setText(self.tr('Processing %s ...'%v))
            self.importDistrictData(i,k,progress)

    def computeNodeDischarge(self, progress=None):
        destTable = 'node_disc'
        # first clear all record in destination table
        if progress: progress.setText(self.tr('Clearing data from table...'))
        sql = 'DELETE FROM %s;' % destTable
        msg = self.DBM.executeSQL(sql)

        if ((msg != '') and progress):
            progress.setText(self.tr('Command stopped because the following error: %s') % msg)
            return

        self.computeDischarge(destTable,progress)

    def computeDischarge(self,destTable,progress):
        # read discharge tables from output file
        yearList = self.SIMDIC['YEARS']
        irrFromDiversionDF = None
        irrFromPrivateDF = None
        irrFromCrsDF = None
        surplusDF = None

        # get irrigation district table
        irrdistrDF = self.DBM.getTableAsDF('SELECT * FROM idr_distrmap')
        irrdistrDF.fillna(value=0, inplace=True)
        irrdistrDF['id'] = irrdistrDF['id'].astype(int, errors='ignore')
        irrdistrDF['inlet_node'] = irrdistrDF['inlet_node'].astype(int, errors='ignore')
        irrdistrDF['outlet_node'] = irrdistrDF['outlet_node'].astype(int, errors='ignore')

        # get nodes table
        nodesDF = self.DBM.getTableAsDF('SELECT * FROM idr_nodes')
        nodesDF.fillna(value=0, inplace=True)
        nodesDF['id'] = nodesDF['id'].astype(int, errors='ignore')
        nodesDF['node_type'] = nodesDF['node_type'].astype(int, errors='ignore')

        # get links table
        linksDF = self.DBM.getTableAsDF('SELECT * FROM idr_links')
        linksDF.fillna(value=0, inplace=True)
        linksDF['inlet_node'] = linksDF['inlet_node'].astype(int, errors='ignore')
        linksDF['outlet_node'] = linksDF['outlet_node'].astype(int, errors='ignore')

        replaceFieldTableIN = {}
        replaceFieldTableOUT = {}
        effTable = {}
        for i, irrDistr in irrdistrDF.iterrows():
            replaceFieldTableIN['SubDistr_'+str(irrDistr['id'])]='Source_'+str(irrDistr['inlet_node'])
            if (self.SIMDIC['MODE'] in [1, '1']):
                effTable[str(irrDistr['inlet_node'])] = irrDistr['distr_eff']
            else:
                # irrDistr['distr_eff'] FIX: "need mode" always considers the internal network distribution see interventi_fabbisogni_fc in ogg_bilancio.f90
                #effTable[str(irrDistr['inlet_node'])] = 1. # OLD IDRAGRA
                effTable[str(irrDistr['inlet_node'])] = irrDistr['distr_eff'] # from new release, water need are calculated at field

            #effTable[str(irrDistr['outlet_node'])] = 1. #/ irrDistr['distr_eff'] # OLD IDRAGRA
            effTable[str(irrDistr['outlet_node'])] = 1./irrDistr['distr_eff'] # from new release, water need are calculated at field
            replaceFieldTableOUT['SubDistr_' + str(irrDistr['id'])] = 'Source_' + str(irrDistr['outlet_node'])

        # calculate irrigation district areas
        areaTable = self.calculateDistrictArea(progress)

        print('areaTable',areaTable)

        if (self.SIMDIC['MODE'] in [1,'1']):
            # get consume table
            irrFromDiversionDF = self.getDischargeFromCSV(yearList, '%s_Qirr.csv',progress,replaceFieldTableIN)
            irrFromPrivateDF = self.getDischargeFromCSV(yearList, '%s_Qprivate.csv', progress,replaceFieldTableIN)
            #surplusDF = self.getDischargeFromCSV(yearList, '%s_Qsurplus.csv', progress)
            replaceFieldTable = {}
            for i, node in nodesDF.iterrows():
                if node['node_type'] in [13]: replaceFieldTable[str(node['id'])] = 'Source_' + str(node['id'])

            irrFromCrsDF = self.getDischargeFromCSV(yearList, '%s_Qcrs.csv', progress, replaceFieldTableIN) #replaceFieldTable)
            surplusDF = self.getDischargeFromCSV(yearList, '%s_Qsurplus.csv', progress, replaceFieldTableOUT)
        else:
            irrFromDiversionDF = self.getDischargeFromMaps(watDistrAreas = areaTable, tableName ='stp_irr',
                                                           progress= progress, colMapper = replaceFieldTableIN)
            surplusDF = self.getDischargeFromMaps(watDistrAreas = areaTable, tableName ='stp_runoff',
                                                           progress= progress, colMapper = replaceFieldTableOUT)

        #print(irrFromDiversionDF)

        # with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        #     print('nodesDF\n', nodesDF)
        #     print('linksDF\n', linksDF)
        #     print('irrdistrDF\n',irrdistrDF)
        #     print('irrFromDiversionDF\n',irrFromDiversionDF)
        #     print('irrFromPrivateDF\n', irrFromPrivateDF)
        #     print('irrFromCrsDF\n', irrFromCrsDF)
        #     print('surplusDF\n',surplusDF)

        #print(linksDF['inlet_node'])
        #print(linksDF['outlet_node'])

        # loop in irrigation district
        # get the code of the connected inlet node

        NA = NetworkAnalyst()
        NA.buildNetwork(nodesDF, linksDF, len(irrFromDiversionDF.index),effTable)
        NA.assignDischarge(irrFromDiversionDF, irrFromPrivateDF, irrFromCrsDF,surplusDF)
        NA.calculateFlowAtNodes()
        res = NA.getFlowAtNodes(irrFromDiversionDF['DoY'].values.tolist())

        irrSum= res['Qirr'] + res['Qcrs'] + res['Qprivate']+res['Qcoll']
        res['recval'] = irrSum
        # delete Qirr, Qcrs Qprivate
        res = res.drop('Qirr', axis=1)
        res = res.drop('Qcrs', axis=1)
        res = res.drop('Qprivate', axis=1)
        res = res.drop('Qcoll', axis=1)
        res = res.drop('QprivMaxAll', axis=1)
        res = res.drop('QirrMaxAll', axis=1)
        res = res.drop('QcrsMaxAll', axis=1)

        res.rename(columns={'DoY':'timestamp'},inplace=True)

        print(res)

        # add res to the database
        self.DBM.popTableFromDF(res,destTable)

    def getDischargeFromCSV(self,yearList, template,progress,colMapper=None):
        finalDF = None
        nOfYear = len(yearList)
        for i,year in enumerate(yearList):
            csvFile = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['OUTPUTFOLDER'],
                                   template % year)

            if progress:
                progress.setPercentage(100.0 * i / nOfYear)
                progress.setText(self.tr('Reading %s') % csvFile)

            try:
                # open csv file as dataframe
                df = pd.read_csv(csvFile, sep=r'\s*;\s*', usecols=None, engine='python')
                if colMapper: df.rename(columns=colMapper,inplace=True)
                # print('df\n',df)
                # print('DoY\n', df['DoY'])
                # replace day_of_year with date
                df['DoY'] = df['DoY'].apply(lambda x: datetime.strptime(str(year) + str(x), '%Y%j').strftime('%Y-%m-%d'))

                #print('df types', df.dtypes)

                if finalDF is None:
                    finalDF = df
                else:
                    #finalDF = finalDF.append(df,ignore_index=True) #deprecated
                    finalDF = pd.concat([finalDF, df], ignore_index=True)

            except Exception as e:
                progress.reportError(self.tr('Unable to open %s')%csvFile,False)

        return finalDF

    def getDischargeFromMaps(self,watDistrAreas = {'11834':24000000,'9999':0},
                             tableName ='stp_irr', progress= None, colMapper = None):
        # get/update irrigation, runoff volumes (mm) from maps
        i = list(self.STEPNAME.values()).index(self.STEPNAME[tableName])
        self.importDistrictData(i, tableName, progress)
        #select table1.timestamp,SubDistr_11834, SudDistr_999 from (select timestamp, recval as 'SudDistr_11834' from stp_irr where wsid = 11834) as table1
        #left join (select timestamp,recval as 'SudDistr_999' from stp_irr where wsid = 999) as 'table_xxx' on table_xxx.timestamp = table1.timestamp
        # get table of discharge (not only volumes!) as DF
        subDistrList = []
        subDistrSqlList = []
        firstTimeStamp = ''
        for k,v in watDistrAreas.items():
            subDistrList.append('SubDistr_%s'%k)
            if not firstTimeStamp:
                firstTimeStamp = 'table_%s'%k
                subDistrSqlList.append(
                    "(select timestamp, recval*%s/(24*60*60*1000) as 'SubDistr_%s' from %s where wsid = %s) as 'table_%s'"
                    % (v,k,tableName, k, k))
            else:
                subDistrSqlList.append(
                    "left join (select timestamp, recval*%s/(24*60*60*1000) as 'SubDistr_%s' from %s where wsid = %s) as 'table_%s' on table_%s.timestamp = %s.timestamp" % (
                    v,k,tableName, k, k, k,firstTimeStamp))

        # make a big query
        #print('watDistrAreas',watDistrAreas)

        sql = 'select %s.timestamp as DoY, %s from %s'%(firstTimeStamp, ', '.join(subDistrList),' '.join(subDistrSqlList))

        print('sql',sql)

        tableDF = self.DBM.getTableAsDF(sql)
        if colMapper: tableDF.rename(columns=colMapper, inplace=True)
        return tableDF

    def calculateDistrictArea(self,progress,nodata=-9999):
        resDict = {}

        areaFile = os.path.join(self.SIMDIC['OUTPUTPATH'],self.SIMDIC['SPATIALFOLDER'], 'shapearea.asc')
        irrUnitsFile = os.path.join(self.SIMDIC['OUTPUTPATH'], self.SIMDIC['SPATIALFOLDER'], 'irr_units.asc')

        irrUnitData = np.loadtxt(irrUnitsFile, dtype=np.int32, skiprows=6)
        irrUnitList = list(np.unique(irrUnitData))
        if nodata in irrUnitList: irrUnitList.remove(nodata)# remove nodata

        try:
            areaData = np.loadtxt(areaFile, dtype=float, skiprows=6)

            for i in irrUnitList:
                # print('varData shape',np.shape(varData))
                # mask = np.where(np.logical_and(baseData[:,:] == i,varData[:,:] != nodata))
                # mask where there are valid values for the selected district
                mask = np.where(np.logical_and(irrUnitData == i, areaData != float(nodata)))

                calcVal = np.sum(areaData[mask])
                resDict[str(i)] = calcVal

            return resDict
        except:
            progress.reportError(self.tr('Unable to open %s, using vector data') % areaFile, False)
            return self.calculateDistrictArea_OLD(progress)

    def calculateDistrictArea_OLD(self,progress):
        resDict = {}
        domainFile = os.path.join(self.SIMDIC['OUTPUTPATH'],self.SIMDIC['SPATIALFOLDER'], 'domain.asc')
        gpkg_layer = self.DBM.DBName + '|layername=' + 'idr_distrmap'
        gpkg_layer = gpkg_layer.replace('\\', '/')
        tempFile = QgsProcessingUtils.generateTempFilename('aggrOutput.gpkg')

        res = processing.run("native:zonalstatisticsfb", {'INPUT': gpkg_layer,
                                                          'INPUT_RASTER': domainFile,
                                                          'RASTER_BAND': 1, 'COLUMN_PREFIX': '_',
                                                          'STATISTICS': [0],
                                                          'OUTPUT': tempFile},
                             context=None,
                             feedback=progress,
                             is_child_algorithm=True)

        # append results
        statLay = QgsVectorLayer(res['OUTPUT'], 'temp', 'ogr')
        for k in statLay.getFeatures():
            resDict[str(k['id'])] = k['_count']*self.SIMDIC['CELLSIZE']*self.SIMDIC['CELLSIZE']


        return resDict

    def importDistrictData(self,varIndex,sourceTable,progress):
        idragraFile = os.path.join(self.SIMDIC['OUTPUTPATH'], 'idragra_parameters.txt')

        # calculate irrigation timeserie from district and upload to stp_irr
        tempFile = QgsProcessingUtils.generateTempFilename('aggrOutput.gpkg')
        algResults = processing.run("idragratools:IdragraImportIrrUnitsResults",
                                    {'IDRAGRA_FILE':idragraFile,'AGGR_VAR':varIndex,
                                     'VOLUME':False,
                                     'DB_FILENAME':self.DBM.DBName},
                                   context=None,
                                   feedback=progress,
                                   is_child_algorithm=False
                                   )


    def importDistrictData_OLD(self,varIndex,sourceTable,progress):
        idragraFile = os.path.join(self.SIMDIC['OUTPUTPATH'], 'idragra_parameters.txt')
        gpkg_layer = self.DBM.DBName + '|layername=' + 'idr_distrmap'
        gpkg_layer = gpkg_layer.replace('\\', '/')

        # TODO: add district area
        # 'AGGR_FUN': 2 == mean [OK], 'AGGR_FUN': 1 == sum
        # calculate irrigation timeserie from district and upload to stp_irr
        tempFile = QgsProcessingUtils.generateTempFilename('aggrOutput.gpkg')
        algResults = processing.run("idragratools:IdragraStatserie",
                       {'IDRAGRA_FILE': idragraFile,
                        'AGGR_LAY': gpkg_layer,
                        'AGGR_FLD': 'id','AGGR_VAR': varIndex, 'AGGR_FUN': 2,
                        'OUTPUT_TABLE': tempFile},
                       context=None,
                       feedback=progress,
                       is_child_algorithm=False
                       )

        table = QgsVectorLayer(tempFile, 'temp', 'ogr')
        # featList = list(table.getFeatures())

        # clear data
        sql = 'DELETE FROM %s;' % sourceTable
        msg = self.DBM.executeSQL(sql)

        sql = 'VACUUM;'
        msg = self.DBM.executeSQL(sql)

        if ((msg != '') and progress):
            progress.setText(self.tr('Command stopped because the following error: %s') % msg)
            return

        gpkg_layer = self.DBM.DBName + '|layername=' + sourceTable

        dbTable = QgsVectorLayer(gpkg_layer, 'temp', 'ogr')
        # dbTable.dataProvider().addFeatures(featList)

        toField = dbTable.dataProvider().fields()
        newFeatList = []
        for feat in table.getFeatures():
            newFeat = QgsFeature(toField)
            newFeat['timestamp']=datetime(feat['timestamp'].year(),
                                          feat['timestamp'].month(),
                                          feat['timestamp'].day()).strftime('%Y-%m-%d')
            newFeat['wsid'] = feat['wsid']
            #print('wsid',feat['wsid'])
            #print('vals', distrDict[feat['wsid']])
            # from mm to cubic meters
            newFeat['recval'] = feat['recval']#*self.SIMDIC['CELLSIZE']*self.SIMDIC['CELLSIZE']/1000.0
            newFeatList.append(newFeat)

        dbTable.startEditing()
        dbTable.addFeatures(newFeatList)
        dbTable.commitChanges()


    def waterDemandAtNode(self, destTable, sourceTable, progress=None,mode = 1,exclNodeType = [13,14]):
        import copy

        if progress: progress.setText(self.tr('Calculating water demand at nodes...'))
        # loop in node list and check if there are data
        #nodeList = self.DBM.getUniqueValues(fieldName='id', tableName='idr_nodes')
        nodeTable = self.DBM.getRecord(tableName='idr_nodes', fieldsList=['id', 'node_type'])
        #print('nodeList',nodeList)
        nodeList = []
        for row in nodeTable:
            if row[1] not in exclNodeType:
                nodeList.append(row[0])

        nOfNode = len(nodeList)
        loopLimit = nOfNode * 1
        n = 0
        while len(nodeList) > 0:
            n += 1
            if n > loopLimit:
                if progress: progress.error(self.tr('Maximum number of iteration, exiting ...'))
                return

            for nodeId in nodeList:
                #print('nodeId',nodeId)
                firstSql = ''
                fieldSql = ''

                isComplete = True
                calcField = []
                tableAliases = []
                sql = ''
                # base sql string for nodes
                sql1 = '(SELECT timestamp,recval as node%s from %s WHERE wsid = %s)'
                sql2 = 'LEFT JOIN (SELECT timestamp as timestamp%s,recval as node%s from %s where wsid = %s) ON timestamp%s=timestamp'
                # base sql string for water districts
                sql3 = '(SELECT timestamp,recval as wd%s from %s WHERE wsid = %s)'
                sql4 = 'LEFT JOIN (SELECT timestamp as timestamp%s,recval as wd%s from %s where wsid = %s) ON timestamp%s=timestamp'

                # get following links that start with idNode
                linkList = self.DBM.getRecord(tableName='idr_links', fieldsList=['id', 'outlet_node', 'inf_losses'],
                                              filterFld='inlet_node', filterValue=nodeId)
                #print('linkList',linkList)
                isFirst = True
                for link in linkList:
                    # get outletNode
                    outletNode = link[1]
                    inf_losses = link[2]
                    # make the query
                    calcField.append('node%s/(1-%s)' % (outletNode, inf_losses)) # old: node%s*(1+%s)
                    if isFirst:
                        firstSql = sql1 % (outletNode, destTable, outletNode)
                        #print('IN LINK LOOP: firstSql',firstSql)
                        isFirst = False
                    else:
                        nodeSql = sql2 % (outletNode, outletNode, destTable, outletNode, outletNode)
                        tableAliases.append(nodeSql)

                    # check if outletnode has data
                    recVal = self.DBM.getRecord(tableName=destTable, fieldsList=[], filterFld='wsid',
                                                filterValue=outletNode)
                    if len(recVal) == 0:
                        #print('discharge at node %s is empty'%outletNode)
                        # discharge at node is empty!
                        isComplete = False

                # get water volumes from district
                wdList = self.DBM.getRecord(tableName='idr_distrmap', fieldsList=['inlet_node', 'distr_eff'],
                                               filterFld='inlet_node', filterValue=nodeId)

                #print('wdList',wdList)
                for wd in wdList:
                    wdDistrEff = wd[1]

                    if mode: calcField.append('wd%s' % (nodeId)) # get discharges from csv
                    else: calcField.append('wd%s*%s/(24*60*60)' % (nodeId, 1/wdDistrEff)) # get volume from maps

                    if isFirst:
                        firstSql = sql3 % (nodeId, sourceTable, nodeId)
                        #print('IN WD LOOP: firstSql', firstSql)
                        isFirst = False
                    else:
                        fieldSql = sql4 % (nodeId, nodeId, sourceTable, nodeId, nodeId)
                        tableAliases.append(fieldSql)

                discFormula = ' + '.join(calcField)

                if len(tableAliases) > 0:
                    sql += 'INSERT INTO %s (timestamp, wsid, recval) SELECT timestamp, %s as wsid, %s as recval FROM %s %s ORDER BY timestamp ASC;' % (
                    destTable, nodeId, discFormula, firstSql, '\n'.join(tableAliases))
                else:
                    sql += 'INSERT INTO %s (timestamp, wsid, recval) SELECT timestamp, %s as wsid, %s as recval FROM %s ORDER BY timestamp ASC;' % (
                    destTable, nodeId, discFormula, firstSql)

                if discFormula == '':
                    # node has no served fields or following links
                    nodeList.remove(nodeId)
                    progress.setText(self.tr('Node "%s" has no served fields or following link') % nodeId)
                else:
                    if isComplete:
                        # remove from the list of Node
                        nodeList.remove(nodeId)
                        # execute query
                        msg = self.DBM.executeSQL(sql)
                        #print('sql',sql)

                        if ((msg != '') and progress):
                            progress.setText(self.tr('Command stopped because the following error: %s') % msg)
                            return


            if progress: progress.setPercentage(100.0 * (nOfNode - len(nodeList)) / nOfNode)

    def printMsg(self, text,col = None):
        self.progressDlg.setText(text,col)

    def updateProgBar(self, val):
        self.progressDlg.setPercentage(val)

    def closeReportForm(self):
        self.progressDlg.close()

    def enableOKBtn(self):
        #print('enableOKBtn')
        self.thread.quit()
        self.threadIsConcluded = True  # it's true only in this case
        if self.worker.exception is not None:
            self.threadIsConcludedWithError = True
            self.progressDlg.setText(self.tr('** Process failed! **'), 'red')
            self.progressDlg.enableOK()
            return

        if not self.threadIsConcludedWithError:
            self.progressDlg.setPercentage(100.)
            self.progressDlg.setText(self.tr('** Process concluded! **'), 'green')
            self.progressDlg.enableOK()

    def stopThread(self):
        self.thread.quit()
        self.thread.wait()
        self.threadIsConcludedWithError = True
        self.progressDlg.setText(self.tr('** Process stopped before finished! **'), 'red')

        if not self.threadIsConcluded:
            showCriticalMessageBox(self.tr('Process stopped before finished'),
                                        self.tr('Output may not be completed'),
                                        self.tr('Consider to repeat the process.'))

    def runAsThread(self, function, onFinished=None, *args, **kwargs):
        from .tools.stoppable_thread import StoppableThread

        from .forms.worker_dialog import WorkerDialog
        self.progressDlg = WorkerDialog(parent=self.iface.mainWindow())
        self.progressDlg.show()

        # try:
        from .tools.worker import Worker

        # clean garbage collector to make space
        # TODO: needs some more thought
        before = gc.get_count()
        #print('gc count',before)
        removed = gc.collect()
        after = gc.get_count()
        # print('removed by gc',removed)

        #print('ok')
        self.thread = StoppableThread()  # QThread()
        self.worker = Worker(self.iface.mainWindow(),function, *args, **kwargs)
        # self.worker.reportProgress.connect(dlg.setPercentage)
        # self.worker.reportMessage.connect(dlg.setText)
        self.worker.reportMessage.connect(self.printMsg)
        self.worker.reportProgress.connect(self.updateProgBar)

        self.worker.finishedBefore.connect(self.stopThread)

        # self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.enableOKBtn)
        if onFinished: self.worker.succeeded.connect(onFinished)
        # self.thread.finished.connect(self.enableOKBtn)

        # self.progressDlg.closed.connect(self.stopThread)
        # self.progressDlg.closed.connect(self.thread.stop)
        self.progressDlg.closed.connect(self.worker.stop)
        self.threadIsConcluded = False
        self.threadIsConcludedWithError = False

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.process)
        self.thread.start()
        # print('thread end')

        # except Exception as e:
        # showCriticalMessageBox('mobidiQ',self.tr("An error occurred! See details."),self.tr("Error message: %s")%(str(e)))
        # finally:
        # return True
        return self.worker.getFlag()

    def setValueRelation(self, layer, field_idx, tableName, keyFld='id', valueFld='name'):
        # https://gisunchained.wordpress.com/2019/09/30/configure-editing-form-widgets-using-pyqgis/
        fields = layer.fields()
        # field_idx = fields.indexOf(fieldName)
        config = {'AllowMulti': False,
                  'AllowNull': True,
                  'FilterExpression': '',
                  'Key': '',
                  'Layer': '',
                  'LayerSource': '',
                  'NofColumns': 1,
                  'OrderByValue': False,
                  'UseCompleter': False,
                  'Value': ''}
        target_layers = QgsProject.instance().mapLayersByName(self.LYRNAME[tableName])
        flag = False
        if len(target_layers) > 0:
            target_layer = target_layers[0]
            config['Layer'] = target_layer.id()
            config['Key'] = keyFld
            config['Value'] = valueFld
            widget_setup = QgsEditorWidgetSetup('ValueRelation', config)
            layer.setEditorWidgetSetup(field_idx, widget_setup)
            flag = True

        return flag

    def setFieldAlias(self, layer, origName, aliasName):
        fields = layer.fields()
        field_idx = fields.indexOf(origName)
        layer.setFieldAlias(field_idx, aliasName)
        return field_idx

    def setFieldCheckable(self, layer, fldName):
        fields = layer.fields()
        field_idx = fields.indexOf(fldName)
        # see https://gis.stackexchange.com/questions/346363/how-to-set-widget-type-to-attachment
        # for useful infos
        config = {'CheckedState': 1,
                  'UncheckedState': 0,
                  'TextDisplayMethod': 1}

        widget_setup = QgsEditorWidgetSetup('CheckBox', config)
        layer.setEditorWidgetSetup(field_idx, widget_setup)

        return field_idx

    def setCustomForm(self, layer, formNameRoot):
        EFC = QgsEditFormConfig()
        customDlg = self.plugin_dir + '/layerforms/' + formNameRoot + '.ui'
        if os.path.exists(customDlg):
            EFC.setUiForm(customDlg)

        customSource = self.plugin_dir + '/layerforms/' + formNameRoot + '.py'
        if os.path.exists(customSource):
            EFC.setInitCodeSource(QgsEditFormConfig.PythonInitCodeSource.CodeSourceFile)
            EFC.setInitFilePath(customSource)
            EFC.setInitFunction('formOpen')

        layer.setEditFormConfig(EFC)

    def getIdNameDict(self, tableName,idFld = 'id',nameFld = 'name',filterName='',filterValues=[]):
        # get the layer
        vLayer = self.DBM.getTableAsLayer(tableName)
        # get field name list
        fieldList = self.DBM.getFieldsList(tableName)
        # check if fid, id, name exist
        idNameDict = {self.tr('Not selected or not available'): ''}

        if idFld not in fieldList:
            return idNameDict

        if nameFld not in fieldList:
            return idNameDict

        if len(filterValues)==0:
            for feat in vLayer.getFeatures():
                idNameDict['[' + str(feat[idFld]) + '] ' + feat[nameFld]] = feat[idFld]
        else:
            for feat in vLayer.getFeatures():
                if feat[filterName] in filterValues:
                    idNameDict['[' + str(feat[idFld]) + '] ' + feat[nameFld]] = feat[idFld]

        return idNameDict

    def getIdNameDictXY(self, tableName, x, y):
        # get the layer
        vLayer = self.DBM.getTableAsLayer(tableName)
        # get field name list
        fieldList = self.DBM.getFieldsList(tableName)
        # check if fid, id, name exist
        idFld = 'id'
        # if 'fid' in fieldList:
        #     idFld = 'fid'

        nameFld = 'name'

        data = []

        for feat in vLayer.getFeatures():
            # calculate distance
            geom = feat.geometry()
            dist = geom.distance(QgsGeometry().fromWkt('Point(%s %s)' % (x, y)))
            data.append((dist, feat[idFld], feat[nameFld]))

        # sort data by dist
        data = sorted(data)

        # populate dictionary
        idNameDict = {self.tr('Not selected'): ''}
        for r in range(len(data)):
            idNameDict[data[r][2] + ' [' + str(data[r][0]) + ']'] = data[r][1]

        return idNameDict

    def getData(self, tList, sensorId,startDate=None, endDate=None):
        # set results dictionary
        res = {}

        res['startDate'] = []
        res['endDate'] = []
        res['nOfExpDays'] = []
        res['nOfFilled'] = []
        res['fullness'] = []
        res['minVal'] = []

        res['minVal'] = []
        res['maxVal'] = []
        res['meanVal'] = []
        res['cumVal'] = []
        res['perc25'] = []
        res['perc50'] = []
        res['perc75'] = []

        res['varName'] = []

        for i, table in enumerate(tList):
            tableAlias = ''
            if table in list(self.METEONAME.keys()):
                tableAlias = self.METEONAME[table]
            if table in list(self.WATERSOURCENAME.keys()):
                tableAlias = self.WATERSOURCENAME[table]
            if table in list(self.STEPNAME.keys()):
                tableAlias = self.STEPNAME[table]

            data = self.DBM.makeStatistics(table, sensorId,startDate, endDate)

            res['varName'].append(tableAlias)

            res['startDate'].append(data['startDate'])
            res['endDate'].append(data['endDate'])
            res['nOfExpDays'].append(data['nOfExpDays'])
            res['nOfFilled'].append(data['nOfFilled'])
            if data['fullness']: res['fullness'].append(int(100.0*data['fullness']))
            else: res['fullness'].append(None)

            res['minVal'].append(data['minVal'])
            res['maxVal'].append(data['maxVal'])
            if data['meanVal']: res['meanVal'].append(qgsRound(data['meanVal'],2))
            else: res['meanVal'].append(None)

            if data['cumVal']: res['cumVal'].append(qgsRound(data['cumVal'],2))
            else: res['cumVal'].append(None)

            res['perc25'].append(data['perc25'])
            res['perc50'].append(data['perc50'])
            res['perc75'].append(data['perc75'])

        return res

    def checkData(self,statTable):
        msg = ''

        for varName,startDate, endDate, fullness in zip(statTable['varName'],statTable['startDate'],statTable['endDate'],statTable['fullness']):
            if not (startDate and endDate): msg += '<li>'+self.tr('%s have no valid data\n') % (varName)+'</li>'
            else:
                if fullness < 100:
                    msg += '<li>'+self.tr('%s is not complete\n') % (varName)+'</li>'

        if msg == '':
            msg = self.tr('<p style="color:green">No error message</p>')
        else:
            msg = self.tr('<p style="color:red">Please check the following error messages:</p>')+'<ul>'+msg+'</ul>'

        return msg

    def checkDataOLD(self, tList, sensorId,startDate=None, endDate=None):
        firstDay = None
        lastDay = None
        errs = []
        warns = []
        res = 'varName\tstartDate\tendDate\tnOfExpDays\tnOfFilled\tfullness\tminVal\tmaxVal\tmeanVal\tcumVal\tperc25\tperc50\tperc75\n'

        for i, table in enumerate(tList):
            tableAlias = ''
            if table in list(self.METEONAME.keys()):
                tableAlias = self.METEONAME[table]
            if table in list(self.WATERSOURCENAME.keys()):
                tableAlias = self.WATERSOURCENAME[table]
            if table in list(self.STEPNAME.keys()):
                tableAlias = self.STEPNAME[table]

            data = self.DBM.makeStatistics(table, sensorId,startDate, endDate)
            res += '\t'.join([tableAlias]+[str(x) for x in data.values()])+'\n'

            if i == 0:
                firstDay = data['startDate']
                lastDay = data['endDate']
            else:
                if firstDay != data['startDate']:
                    errs.append(self.tr('Different start date for variable %s' % tableAlias))
                if lastDay != data['endDate']:
                    errs.append(self.tr('Different start date for variable %s' % tableAlias))

        res += self.tr('No error message. Data are available from %s to %s' % (firstDay, lastDay))
        if (firstDay is None) and (lastDay is None):
            res = self.tr('Data are not available for this feature')

        if len(errs) > 0:
            res = '\n'.join(errs)

        return res

    def updateVector(self, vLayer=None, dataList=None):
        with edit(vLayer):
            i = 0
            for feat in vLayer.getFeatures():
                feat["tempValue"] = dataList[i]
                vLayer.updateFeature(feat)
                i += 1

    def runTimeUpdate(self):
        from .tools.make_color_ramp import replaceColorRamp
        from .time_manager.time_manager import TimeManager

        # make a temporary layer
        crs = QgsProject.instance().crs().authid()
        layName = self.tr('Time layer')
        newLayer = QgsVectorLayer("Polygon?crs=%s" % crs, layName, "memory")
        fldDict = {'fid': QVariant.Int, 'name': QVariant.String, 'value': QVariant.Double}

        pr = newLayer.dataProvider()
        attrList = []
        for n, t in fldDict.items():
            attrList.append(QgsField(n, t))

        pr.addAttributes(attrList)
        newLayer.updateFields()

        # populate newLayer with geometry from source
        sourceLayer = QgsProject.instance().mapLayersByName(self.LYRNAME['idr_crop_fields'])
        if len(sourceLayer)>0:
            sourceLayer = sourceLayer[0]
        else:
            gpkg_layer = self.DBM.DBName + '|layername=' + 'idr_crop_fields'
            sourceLayer = QgsVectorLayer(gpkg_layer, 'idr_crop_fields', "ogr")

        with edit(newLayer):
            if sourceLayer.selectedFeatureCount() > 0:
                featList = sourceLayer.getSelectedFeatures()
            else:
                featList = sourceLayer.getFeatures()

            for sourceFeat in featList:
                geom = sourceFeat.geometry()
                fid = sourceFeat['fid']
                name = sourceFeat['name']
                feat = QgsFeature()
                feat.setGeometry(geom)
                feat.setAttributes([fid, name, None])
                newLayer.addFeature(feat)

        # add to map
        groupIndex, mygroup = self.getGroupIndex(self.tr('Analysis'), True)
        QgsProject.instance().addMapLayer(newLayer, False)  # False is the key
        mygroup.insertChildNode(groupIndex, QgsLayerTreeLayer(newLayer))

        # make a function to update temporary layer
        def updateTemporaryLayer(tableName, selDay, minmax=None):
            print('updateTemporaryLayer:', tableName, ' - ', selDay)
            # make a query
            sql = "SELECT wsid ,recval FROM %s WHERE date(timestamp) = date('%s') ORDER BY wsid ASC;" % (
            tableName, selDay)
            msg = ''
            try:
                self.DBM.startConnection()
                self.DBM.cur.execute(sql)
                data = self.DBM.cur.fetchall()
            except Exception as e:
                msg = str(e)
            finally:
                self.DBM.stopConnection()

            if msg != '':
                showCriticalMessageBox(text=self.tr('Critical error'),
                                            infoText=self.tr('Cannot performe function'), detailText=msg)
                return
            # update tempLayer
            newLayer.startEditing()
            for d in data:
                featIter = newLayer.getFeatures(QgsFeatureRequest(QgsExpression("\"fid\" = %s" % d[0])))
                for feat in featIter:
                    newid = feat.id()
                    flg = newLayer.changeAttributeValue(newid, 2, float(d[1]))
                    break

            newLayer.commitChanges()
            # set style
            replaceColorRamp(vLayer=newLayer, varToPlot='', fieldName='value', minmax=minmax)

        # make a list of days
        tNameList = list(self.STEPNAME.keys())
        startDate, endDate = self.DBM.getMultiMinMax(tNameList, 'timestamp')

        # init year selector
        startDate = datetime.strptime(startDate, '%Y-%m-%d')
        endDate = datetime.strptime(endDate, '%Y-%m-%d')
        dateList = []
        for n in range(int((endDate - startDate).days) + 1):
            dateList.append((startDate + timedelta(n)).strftime("%Y-%m-%d"))

        dlg = TimeManager(self.iface.mainWindow(), 'Timer', self.STEPNAME, updateTemporaryLayer, dateList)
        dlg.show()

    def updateMe(self):
        print("hey", self.count)
        self.count += 1
        if self.count > 1000: self.timer.stop()

    def updateVectorOLD(self, vLayer=None, dataList=None):
        print('update', self.count)
        self.count += 1
        if self.count > 1000: self.timer.stop()

        if not vLayer: vLayer = self.VECTORLAYER

        if not dataList:
            numOfFeat = vLayer.featureCount()
            dataList = random.sample(range(0, 100), numOfFeat)

        if vLayer:
            i = 0
            with edit(vLayer):
                for feat in vLayer.getFeatures():
                    feat["tempValue"] = dataList[i]
                    vLayer.updateFeature(feat)
                    i += 1

    def getGroupIndex(self, group, onTop = False):
        # Get the layer tree object
        root = QgsProject.instance().layerTreeRoot()
        # Find the desired group by name
        mygroup = root.findGroup(group)
        if mygroup is None:
            # create a new group
            if onTop: root.insertGroup(0,group)
            else: root.addGroup(group)
            mygroup = root.findGroup(group)

        # Get the group index
        groupIndex = len(mygroup.children())
        return groupIndex, mygroup

    def importResultsMap(self):
        if not self.SIMDIC['VECTOR_MODE']:
           showCriticalMessageBox(self.tr('Not available function'),
                                   self.tr('This function is available for VECTOR mode simulation only'),
                                   self.tr('Consider to use "Make grouped statistics" instead'))
           return

        # open the selector with the variable to be imported
        from .forms.resultsmap_dialog import ResultsMapDialog

        dlg = ResultsMapDialog(self.iface.mainWindow(), self.STEPNAME)
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        if result == 1:
            res = dlg.getData()
            # TODO: fix dlg update problem

            # self.progressDlg = WorkerDialog(parent=self.iface.mainWindow())
            # self.progressDlg.show()
            # feedback = Worker(None)
            # feedback.reportMessage.connect(self.progressDlg.setText)
            self.data = None

            def processOutput(progress):
                idragraFile = os.path.join(self.SIMDIC['OUTPUTPATH'], 'idragra_parameters.txt')
                #domain_lay = self.getVectorLayerByName('idr_domainmap') # use db domain
                domain_lay = os.path.join(self.SIMDIC['OUTPUTPATH'], 'geodata','domain.gpkg') # use domain in simulation
                # TODO: check if input files exist
                self.data = processing.run("idragratools:IdragraResultMaps",
                                           {'IDRAGRA_FILE': idragraFile,
                                            'DOMAIN_LAY': domain_lay,
                                            'RES_VAR': res['selVarIdx'],
                                            'OUTPUT_LAY': 'TEMPORARY_OUTPUT'},
                                           context=None,
                                           feedback=progress,
                                           is_child_algorithm=False
                                           )

            def loadResults():
                # load data in table view ...
                if self.data:
                    self.progressDlg.close()
                    # add to
                    groupIndex, mygroup = self.getGroupIndex(self.tr('Analysis'), True)
                    # mygroup.insertChildNode(groupIndex, QgsLayerTreeLayer(data['OUTPUT_TABLE']))
                    baseName = '%s' % (list(self.STEPNAME.values())[res['selVarIdx']])
                    self.data['OUTPUT_LAY'].setName(baseName)
                    QgsProject.instance().addMapLayer(self.data['OUTPUT_LAY'], False)  # False is the key
                    mygroup.insertChildNode(groupIndex, QgsLayerTreeLayer(self.data['OUTPUT_LAY']))

            # print('data:',data)
            self.runAsThread(function=processOutput, onFinished=loadResults, progress=None)



    def makeGroupedStats(self):
        if self.SIMDIC['VECTOR_MODE']:
           showCriticalMessageBox(self.tr('Not available function'),
                                   self.tr('This function is available for RASTER mode simulation only'),
                                   self.tr('Consider to use "Import result maps" instead'))
           return

        # TODO: fix UI
        from .forms.groupstats_dialog import GroupstatsDialog

        dlg = GroupstatsDialog(self.iface.mainWindow(), self.STEPNAME, self.AGGRFUNCTIONS)
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        if result == 1:
            res = dlg.getData()
            # TODO: fix dlg update problem

            #self.progressDlg = WorkerDialog(parent=self.iface.mainWindow())
            #self.progressDlg.show()
            #feedback = Worker(None)
            #feedback.reportMessage.connect(self.progressDlg.setText)
            self.data = None

            def processOutput(progress):
                idragraFile = os.path.join(self.SIMDIC['OUTPUTPATH'],'idragra_parameters.txt')

                self.data = processing.run("idragratools:IdragraGroupStats",
                               {'IDRAGRA_FILE': idragraFile,
                                'AGGR_LAY': res['selGroupLay'],'MERGE': res['selMerge'],
                                'AGGR_FLD': res['selGroupField'],
                                'AGGR_VAR': res['selVarIdx'], 'AGGR_FUN': res['selFunIdx'],
                                'OUTPUT_TABLE': 'TEMPORARY_OUTPUT'},
                               context=None,
                               feedback=progress,
                               is_child_algorithm=False
                               )
            def loadResults():
                # load data in table view ...
                if self.data:
                    self.progressDlg.close()
                    # add to
                    groupIndex, mygroup = self.getGroupIndex(self.tr('Analysis'),True)
                    #mygroup.insertChildNode(groupIndex, QgsLayerTreeLayer(data['OUTPUT_TABLE']))
                    baseName = '%s %s by %s and %s' % (list(self.STEPNAME.values())[res['selVarIdx']],
                                                          list(self.AGGRFUNCTIONS.values())[res['selFunIdx']],
                                                          res['selGroupName'],res['selGroupField']
                                                          )
                    self.data['OUTPUT_TABLE'].setName(baseName)
                    QgsProject.instance().addMapLayer(self.data['OUTPUT_TABLE'], False)  # False is the key
                    mygroup.insertChildNode(groupIndex, QgsLayerTreeLayer(self.data['OUTPUT_TABLE']))

            #print('data:',data)
            self.runAsThread(function=processOutput, onFinished=loadResults,progress=None)


    def loadFromProject(self):
        proj = QgsProject.instance()
        dbpath = ''
        try:
            #dbpath = proj.readEntry('IdrAgraTools', 'dbname')[0]
            tempDic = eval(proj.readEntry('IdrAgraTools', 'simsettings')[0])
            usedKeys = list(self.SIMDIC.keys())
            for k,v in tempDic.items():
                if k in usedKeys: # to prevent bugs
                    self.SIMDIC[k]=v

            dbpath = self.SIMDIC['DBFILE']

        except Exception as e:
            if dbpath != '': # set silent if dbpath is not set
                showCriticalMessageBox(self.tr('Loading settings error'),
                                            self.tr('An error occurred when loading %s'%proj.fileName()),
                                            str(e))
        #print('dbpath:',dbpath)
        dbpath = os.path.normpath(dbpath)
        # TODO: remove dbname, modify DBFILE
        if os.path.isfile(dbpath):
            #if (value is not None):
            self.openDB(dbpath=dbpath)
        else:
            print('dbpath is not a file:', dbpath)
            if dbpath not in ['','.']:
                # ask for new dbpath
                dbpath = QFileDialog.getOpenFileName(None, self.tr('Open idragra database'), self.s.value('lastPath'),
                                                     self.tr(self.FILEFORMAT))
                dbpath = dbpath[0]
                if os.path.isfile(dbpath): self.openDB(dbpath=dbpath)

    def setRaster(self,tableName,layName, layGroup, assignTime=False):

        from .forms.import_raster_dialog import ImportRasterDialog
        dlg = ImportRasterDialog(self.iface,assignTime)
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        if result == 1:
            res = dlg.getData()
            filePath = res['rasterFile']
            outputExt = res['extent']
            importRasterFlag = res['importRaster']
            startDate = res['date']
            if assignTime:
                tableName += '_' + startDate

            if layName is None:
                layName = tableName

            gpkgFile = None
            if importRasterFlag:
                gpkgFile = self.DBM.DBName

            self.runAsThread(self.importRaster,
                             gpkgFile=gpkgFile,
                            rasterFileName=filePath, tableName=tableName,
                            crs=QgsProject.instance().crs(),
                            extension=outputExt,
                            layName = layName, layGroup = layGroup,
                            onFinished=lambda: self.loadRaster(self.SIMDIC['RASTERMAP'][tableName],layName,layGroup),
                            progress=None)

    def setElevation(self):
        dlg = ManageRastersDialog(iface=self.iface, assignTime=False,
                               rasterDict=self.SIMDIC['ELEVMAP'],
                               tableName='elevation', DBM=self.DBM)
        dlg.rasterAdded.connect(lambda source,name: self.loadRaster(source, name, self.tr('Elevation')))
        dlg.rasterDeleted.connect(lambda source, name: self.unloadRaster(source, name))

        def updatePar():
            self.SIMDIC['ELEVMAP'] = dlg.getData()
            #print('elevmap:',self.SIMDIC['ELEVMAP'])
            self.updatePars()

        dlg.closed.connect(updatePar)
        dlg.show()

    def setWaterTable(self):
        dlg = ManageRastersDialog(iface= self.iface, assignTime = True,
                                  rasterDict = self.SIMDIC['WATERTABLEMAP'],
                                  tableName='watertable',DBM = self.DBM)
        dlg.rasterAdded.connect(lambda source, name: self.loadRaster(source, name, self.tr('Ground water')))
        dlg.rasterDeleted.connect(lambda source, name: self.unloadRaster(source, name))

        def updatePar():
            self.SIMDIC['WATERTABLEMAP'] = dlg.getData()
            self.updatePars()

        dlg.closed.connect(updatePar)
        dlg.show()

    def setRasterLanduse(self):
        dlg = ManageRastersDialog(iface= self.iface, assignTime = True,
                                  rasterDict = self.SIMDIC['LANDUSEMAP'],
                                  tableName='landuse',DBM = self.DBM)
        dlg.rasterAdded.connect(lambda source, name: self.loadRaster(source, name, self.tr('Land use')))
        dlg.rasterDeleted.connect(lambda source, name: self.unloadRaster(source, name))

        def updatePar():
            self.SIMDIC['LANDUSEMAP'] = dlg.getData()
            self.updatePars()

        dlg.closed.connect(updatePar)
        dlg.show()


    def setRasterIrrmeth(self):
        dlg = ManageRastersDialog(iface= self.iface, assignTime = True,
                                  rasterDict = self.SIMDIC['IRRMETHMAP'],
                                  tableName='irrmeth',DBM = self.DBM)
        dlg.rasterAdded.connect(lambda source, name: self.loadRaster(source, name, self.tr('Land use')))
        dlg.rasterDeleted.connect(lambda source, name: self.unloadRaster(source, name))

        def updatePar():
            self.SIMDIC['IRRMETHMAP'] = dlg.getData()
            self.updatePars()

        dlg.closed.connect(updatePar)
        dlg.show()

    def loadRaster(self,rasterPath, rasterName, layGroup):
        proj = QgsProject.instance()

        if not rasterName:
            return

        oldlayer = self.getLayerByName(rasterName)
        if oldlayer and oldlayer.type() == QgsMapLayer.RasterLayer and oldlayer.isValid():
            return

        rasterPath = 'GPKG:' + self.DBM.DBName+':'+rasterName
        rlayer = QgsRasterLayer(rasterPath, rasterName, 'gdal')

        if rlayer.isValid():
            if oldlayer:
                # rlayer.setCacheImage(None)
                # proj.removeMapLayers([rlayer.id()])
                self.setDataSource(oldlayer, 'gdal', rasterPath, rlayer.extent())
            else:
                groupIndex, mygroup = self.getGroupIndex(layGroup)
                # rlayer.loadNamedStyle(os.path.join(self.plugin_dir, 'styles', n + '.qml'))
                proj.addMapLayer(rlayer, False)
                mygroup.insertChildNode(groupIndex, QgsLayerTreeLayer(rlayer))
        else:
            showCriticalMessageBox(self.tr('Loading error'),
                                        self.tr('Unable to load %s')%rasterPath,
                                        self.tr('The selected layer seems broken or not exist'))

    def unloadRaster(self,rasterPath, rasterName):
        # loop in project
        proj = QgsProject.instance()

        # if not os.path.exists(rasterPath):
        #     rasterPath = 'GPKG:' + os.path.join(proj.absolutePath(), rasterPath)
        #
        #
        # for layer in proj.mapLayers().values():
        #     if ((layer.source().replace('\\', '/') == rasterPath) and (layer.name()==rasterName)) :
        #         proj.removeMapLayer(layer.id())
        layer = self.getRasterLayerByName(rasterName)
        if layer: proj.removeMapLayer(layer.id())

    def setDataSource(self, layer, newProvider, newDatasource, extent=None):
        # modified from https://github.com/enricofer/changeDataSource/blob/master/setdatasource.py

        XMLDocument = QDomDocument("style")
        XMLMapLayers = XMLDocument.createElement("maplayers")
        XMLMapLayer = XMLDocument.createElement("maplayer")
        context = QgsReadWriteContext()
        layer.writeLayerXml(XMLMapLayer, XMLDocument, context)
        # apply layer definition
        XMLMapLayer.firstChildElement("datasource").firstChild().setNodeValue(newDatasource)
        XMLMapLayer.firstChildElement("provider").firstChild().setNodeValue(newProvider)
        if extent:  # if a new extent (for raster) is provided it is applied to the layer
            XMLMapLayerExtent = XMLMapLayer.firstChildElement("extent")
            XMLMapLayerExtent.firstChildElement("xmin").firstChild().setNodeValue(str(extent.xMinimum()))
            XMLMapLayerExtent.firstChildElement("xmax").firstChild().setNodeValue(str(extent.xMaximum()))
            XMLMapLayerExtent.firstChildElement("ymin").firstChild().setNodeValue(str(extent.yMinimum()))
            XMLMapLayerExtent.firstChildElement("ymax").firstChild().setNodeValue(str(extent.yMaximum()))

        XMLMapLayers.appendChild(XMLMapLayer)
        XMLDocument.appendChild(XMLMapLayers)
        layer.readLayerXml(XMLMapLayer, context)
        layer.reload()

        self.iface.actionDraw().trigger()
        self.iface.mapCanvas().refresh()
        self.iface.layerTreeView().refreshLayerSymbology(layer.id())

    def makeDistroPlot(self,cropIds,w,h):
        cropData = []
        for id in cropIds:
            # get crop name and parameter
            res = self.DBM.getRecord(tableName='idr_crop_types',
                               fieldsList=['name','sowingdate_min','sowingdelay_max','harvestdate_max'],
                               filterFld = 'id', filterValue=id)
            if len(res)>0:
                cropData.append(res[0])

        print('cropData\n',cropData)

        cw = ChartWidget(None, '', False, False,(w,h))
        cw.setAxis(pos=111, secondAxis=False, label=['test'])
        tempFile = QgsProcessingUtils.generateTempFilename('plot.png')
        ylabs = []
        for i,crop in enumerate(cropData):
            #('autumn-sown grains', 288, 14, 200)
            sowingDay = crop[1]
            maxDelay = crop[2]
            harvestDay = crop[3]
            if harvestDay<sowingDay:
                sowingDay = sowingDay-365

            cw.drawRectangle(sowingDay,harvestDay,i-0.5,i+0.5,'#71c83780',None)
            cw.drawRectangle(sowingDay+maxDelay, harvestDay, i - 0.5, i + 0.5, '#71c83780', None)
            ylabs.append(crop[0])

        cw.setTitles( xlabs=None, ylabs=None, xTitle=self.tr('day of the year'), yTitle=None, y2Title=None, mainTitle=None)
        cw.setYAxis(ylabs)
        #cw.plot()
        cw.saveToFile(tempFile,w,h)
        pmap = QPixmap(tempFile)
        return pmap

        #plot parameters
        import matplotlib.pyplot as plt

        plt.figure()
        plt.plot(cropIds)
        plt.title('')

        # im = Image.open(buf)
        # im.show()
        # buf.close()

    def tempLoop(self):
        #res = self.DBM.getAllSourceNode(3)
        tempDict = {'1': [100, 70, 90, 10, 300, 20],
                    '2': [200, 75, 100, 20, 310, 30]}
        print('tempDict',tempDict)
        dList, aList = makeDischSerie(tempDict, 2000, 2001)
        print('dList',dList)
        print('aList',aList)

    def callAlg(self):
        # from processing import execAlgorithmDialog
        #
        # params = {}  # A dictionary to load some default value in the dialog
        # execAlgorithmDialog('idragratools:IdragraGetFromDtm', params)
        from .forms.import_raster_dialog import ImportRasterDialog
        dlg = ImportRasterDialog(self.iface)
        dlg.show()
        result = dlg.exec()
        # See if OK was pressed
        if result == 1:
            res = dlg.getData()
            filePath = res['dtmfile']
            ext = res['extent']
            print('extention',ext)
            self.runAsThread(self.importRaster,gpkgFile = self.DBM.DBName,
                             rasterFileName =filePath, tableName='sss',crs=QgsCoordinateReferenceSystem('EPSG:32632'),
                             extension=QgsRectangle(),progress=None)
            #msg = importRaster('c:/test_landriano/xxx.gpkg',filePath,'dtm2')
            #print('res',msg)

    def callTableForm(self):
        print('Simulation options')
        print(self.SIMDIC)

    def test(self,progress):
        EGV = ExportGeodataVector(None,self.SIMDIC,progress,self.tr)
        EGV.exportGeodata()

    def test2(self):
        from .tools.get_timeseries_consistency import getTimeSeriesConsistency
        progress = MyProgress()
        weatStatList = self.DBM.getUniqueValues('fid','idr_weather_stations')
        watSourceWithData = self.DBM.getUniqueValues('wsid','node_act_disc')
        watSourceList = []
        if (self.SIMDIC['MODE']  in [1,'1']):
            tempList = self.DBM.getUniqueValues('inlet_node','idr_distrmap')

            for watSource in tempList:
                if watSource in watSourceWithData:
                    if watSource not in watSourceList: watSourceList.append(watSource)
                else:
                    # get upper nodes
                    res= self.DBM.getAllSourceNode(watSource)
                    print('nodeList', res['nodeList'])
                    for node in res['nodeList']:
                        if node in watSourceWithData:
                            if node not in watSourceList: watSourceList.append(node)


        print('weatStatList',weatStatList)
        print('watSourceList',watSourceList)

        res = getTimeSeriesConsistency(dbname = self.DBM.DBName, fromTime='1998-01-01', toTime='2002-12-31',
                                       weatStatList=weatStatList, watSourceList=watSourceList,
                                       feedback=progress,tr=self.tr)
        print(res)

    def createImageMap(self):
        from tools.layout_to_image import layoutToImage

        layerNames = ['idr_weather_stations','idr_distrmap','idr_soilmap']
        layerList = []
        for layName in layerNames:
            layerList.append(self.getVectorLayerByName(layName))

        fileName = r'C:\examples\test_img\test.png'
        #mapToImage(layerList,fileName)
        layoutToImage(layerList,fileName)

        # from data_manager.chart_widget import ChartWidget
        # fileName = r'C:\examples\test_img\test_chart.png'
        #
        # cw = ChartWidget(None, '', False, False, None)
        # cw.setAxis(pos=111, secondAxis=False, label=['test'])
        # cw.addPieChart()
        # cw.saveToFile(fileName,400,400)

    def generateReport(self,repIndex, progress=None):
        # run algorithm
        self.HTMLFILE = None
        algResults = processing.run("idragratools:IdragraReportOverview",
                       {'SIM_FOLDER': self.SIMDIC['OUTPUTPATH'], 'OUTPUT': 'TEMPORARY_OUTPUT',
                        'REPORT_FORMAT':repIndex},
                                         context=None, feedback=progress, is_child_algorithm=False)
        self.HTMLFILE = algResults['OUTPUT']
        return algResults['OUTPUT']

    def showReportExplorer(self, htmlFile=None):
        if not htmlFile: htmlFile = self.HTMLFILE

        if htmlFile:
            self.dlg = ReportDialog(self.iface.mainWindow())
            self.dlg.loadReport(htmlFile)
            self.dlg.show()

    def createHeatMap(self):
        pass

        #outPath = os.path.join(self.SIMDIC['OUTPUTPATH'],self.SIMDIC['SPATIALFOLDER'])

        # self.layer = self.iface.activeLayer()
        # self.editor = AttributesTableView(self.layer, self.iface.mapCanvas(),None)
        # self.editor.show()

        # self.editor = QgsAttributeTableView()
        # self.editor.show()

        # self.editor = QgsDualView(None)
        # self.layer = self.iface.activeLayer()
        # self.editor.init(self.layer, self.iface.mapCanvas())
        # self.editor.setView(QgsDualView.AttributeEditor)
        # self.editor.show()

        # self.layer = self.iface.activeLayer()
        # #self.editor = QgsAttributeForm (self.layer)
        # self.editor =  	QgsAttributeTableView ()
        # self.editor.show()

        # layer = self.iface.activeLayer()
        # canvas = self.iface.mapCanvas()
        # vector_layer_cache = QgsVectorLayerCache(layer, 10000)
        # self.attribute_table_model = QgsAttributeTableModel(vector_layer_cache)
        # self.attribute_table_model.loadLayer()
        #
        # self.attribute_table_filter_model = QgsAttributeTableFilterModel(
        #     canvas,
        #     self.attribute_table_model
        # )
        # self.attribute_table_view = QgsAttributeTableView()
        # self.attribute_table_view.setModel(self.attribute_table_filter_model)
        #
        # self.attribute_table_view.show()
