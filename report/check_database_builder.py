import glob
import os

import numpy as np
import pandas as pd
import re

import sqlite3 as sqlite

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib import cm
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec

from datetime import datetime,timedelta

# import as module
from report.report_builder import ReportBuilder

class CheckDatabaseBuilder(ReportBuilder):

    def __init__(self,feedback = None, tr = None):
        super().__init__(feedback, tr)

        self.check_database_template = os.path.join(self.rb_dir, 'default', 'check_database_report.html')

        self.conn = None
        self.cur = None
        self.DBName = None

    def initDB(self,db_name):
        self.DBName = db_name

    def startConnection(self):
        # start connection
        self.conn = sqlite.connect(self.DBName, detect_types=sqlite.PARSE_DECLTYPES)
        self.conn.enable_load_extension(True)
        self.conn.execute('SELECT load_extension("mod_spatialite")')
        # creating a Cursor
        self.cur = self.conn.cursor()

    def stopConnection(self):
        # run VACUUM to reduce the size
        self.conn.rollback()
        # self.cur.execute('VACUUM')
        self.conn.close()

    def readTimeSerie(self, tableName, wsId, frm = '%Y-%m-%d'):
        sql = "SELECT * FROM %s WHERE wsid = %s" %(tableName,wsId)
        ts = pd.read_sql_query(sql, self.conn)
        ts['timestamp'] = pd.to_datetime(ts['timestamp'], format=frm,utc=True )
        return ts

    def getTimeLimits(self, ts, tsFld = 'timestamp'):
        start_ts = min(ts[tsFld])
        end_ts = max(ts[tsFld])
        return start_ts,end_ts

    def makeMeteoPlot(self,dataToPlot,meteoVarDict,outFile):
        fig, axs = plt.subplots(3, 1, figsize=(10, 3.5 * 3))  # , constrained_layout=True)
        #axs[0].setAxis(secondAxis=True, label=['Temp', 'Prec'])
        # add timeseries
        lines, = axs[0].plot_date(dataToPlot['timestamp'], dataToPlot['ws_ptot'], '-', '#416FA6',
                                  meteoVarDict['ws_ptot'])

        y1Title = [meteoVarDict['ws_ptot']]
        y2Title = [meteoVarDict['ws_tmax'],meteoVarDict['ws_tmin']]

        # flip y axes
        axs[0].invert_yaxis()
        # set title
        axs[0].set_ylabel(', '.join(y1Title))

        #newAxs = axs[0].twinx()
        lines, = axs[1].plot_date(dataToPlot['timestamp'], dataToPlot['ws_tmax'], '-', '#A8423F',
                                  meteoVarDict['ws_tmax'])
        # lines, = newAxs.plot_date(dataToPlot['timestamp'], dataToPlot['ws_tmin'], '-', '#4198AF',
        #                          meteoVarDict['ws_tmin'])

        #newAxs.set_ylabel(', '.join(y2Title))

        #axs[0].setTitles(xlabs=None, ylabs=None, xTitle=None, yTitle=, y2Title=', '.join(y2Title),
        #              mainTitle=None)

        # save to file
        fig.savefig(outFile, format='png')
        plt.close(fig)


    def makeReport(self,simFolder,outfile):
        #set default folder
        outImageFolder = self.makeSubFolder(outfile)

        if not self.conn: self.startConnection()

        ### Controls list ###
        ## meteo data ##
        # 0. get the list of weather station and check attributes
        wsid_list = []
        sql = """
                SELECT * FROM idr_weather_stations
                """
        ws_df = pd.read_sql_query(sql, self.conn)
        print(ws_df)
        for index, row in ws_df.iterrows():
            fid = row['fid']
            id = row['id']
            name = row['name']
            if not(id in wsid_list): wsid_list.append(id)
            else: self.FEEDBACK.reportError(self.tr('Weather station %s (fid=%s) has repeated id = %s')%(name,fid,id),True)
            lat = row['lat']
            if pd.isnull(lat): self.FEEDBACK.reportError(self.tr('Weather station %s (fid=%s) has empty <lat> value')%(name,fid),True)
            if ((lat<-90) or (lat>90)):self.FEEDBACK.reportError(self.tr('Weather station %s (fid=%s) has <lat> out of range [-90,90]')%(name,fid),True)
            alt = row['alt']
            if pd.isnull(alt): self.FEEDBACK.reportError(
                self.tr('Weather station %s (fid=%s) has empty <alt> value') % (name, fid),True)

        #print(wsid_list)
        # check time data
        for wsid in wsid_list:
            self.FEEDBACK.pushInfo(self.tr('Check data from weather station %s'%wsid))
            sList = []
            eList = []
            # 1. always ws_tmin < ws_tmax
            ws_tmin = self.readTimeSerie('ws_tmin',wsid)
            s,e = self.getTimeLimits(ws_tmin)
            sList.append(s)
            eList.append(e)

            ws_tmax = self.readTimeSerie('ws_tmax', wsid)
            s,e = self.getTimeLimits(ws_tmax)
            sList.append(s)
            eList.append(e)
            # join dataframe
            merged_df = pd.merge(ws_tmin, ws_tmax, how="inner", on='timestamp',suffixes=("_tmin", "_tmax"))
            filtered_df = merged_df[(merged_df['recval_tmin'] > merged_df['recval_tmax'])]
            nOfErr = len(filtered_df.index)
            if nOfErr>0:
                self.FEEDBACK.reportError(self.tr('A total of %s records has Tmin > Tmax') % (nOfErr), False)
                # print max first 10 rows
                self.FEEDBACK.reportError(self.tr('Max first 10 record reported'))
                self.FEEDBACK.reportError(self.tr('Timestamp Tmin Tmax'))
                for index, row in filtered_df.iterrows():
                    if index>10: break
                    self.FEEDBACK.reportError(self.tr('%s %s %s')%(row['timestamp'],row['recval_tmin'],row['recval_tmax']))
            else:
                self.FEEDBACK.pushInfo(self.tr('--> temperature OK!'))

            # 2. always prec >= 0
            ws_ptot = self.readTimeSerie('ws_ptot', wsid)
            s,e = self.getTimeLimits(ws_ptot)
            sList.append(s)
            eList.append(e)
            filtered_df = ws_ptot[ws_ptot['recval'] <0]
            nOfErr = len(filtered_df.index)
            if nOfErr>0:
                self.FEEDBACK.reportError(self.tr('A total of %s records has Ptot < 0') % (nOfErr), False)
                # print max first 10 rows
                self.FEEDBACK.reportError(self.tr('Max first 10 record reported'))
                self.FEEDBACK.reportError(self.tr('Timestamp Ptot'))
                for index, row in filtered_df.iterrows():
                    if index>10: break
                    self.FEEDBACK.reportError(self.tr('%s %s')%(row['timestamp'],row['recval']))
            else:
                self.FEEDBACK.pushInfo(self.tr('--> precipitation OK!'))

            # 3. always minRH,maxRH [0.-100.]
            # 4. always minRH < maxRH
            ws_umin = self.readTimeSerie('ws_umin', wsid)
            s,e = self.getTimeLimits(ws_umin)
            sList.append(s)
            eList.append(e)

            ws_umax = self.readTimeSerie('ws_umax', wsid)
            s,e = self.getTimeLimits(ws_umax)
            sList.append(s)
            eList.append(e)

            # check ranges
            filtered_df = ws_umin[(ws_umin['recval'] <0.) | (ws_umin['recval'] >100.)]
            nOfErr = len(filtered_df.index)
            if nOfErr > 0:
                self.FEEDBACK.reportError(self.tr('A total of %s records has RHmin out of range [0-100]') % (nOfErr), False)
                # print max first 10 rows
                self.FEEDBACK.reportError(self.tr('Max first 10 record reported'))
                self.FEEDBACK.reportError(self.tr('Timestamp RHmin'))
                for index, row in filtered_df.iterrows():
                    if index > 10: break
                    self.FEEDBACK.reportError(
                        self.tr('%s %s') % (row['timestamp'], row['recval']))
            else:
                filtered_df = ws_umax[(ws_umax['recval'] < 0.) | (ws_umax['recval'] > 100.)]
                nOfErr = len(filtered_df.index)
                if nOfErr > 0:
                    self.FEEDBACK.reportError(
                        self.tr('A total of %s records has RHmax out of range [0-100]') % (nOfErr), False)
                    # print max first 10 rows
                    self.FEEDBACK.reportError(self.tr('Max first 10 record reported'))
                    self.FEEDBACK.reportError(self.tr('Timestamp RHmax'))
                    for index, row in filtered_df.iterrows():
                        if index > 10: break
                        self.FEEDBACK.reportError(
                            self.tr('%s %s') % (row['timestamp'], row['recval']))
                else:
                    # check always RHmin < RHmax
                    # join dataframe
                    merged_df = pd.merge(ws_umin, ws_umax, how="inner", on='timestamp', suffixes=("_umin", "_umax"))
                    filtered_df = merged_df[(merged_df['recval_umin'] > merged_df['recval_umax'])]
                    nOfErr = len(filtered_df.index)
                    if nOfErr > 0:
                        self.FEEDBACK.reportError(self.tr('A total of %s records has RHmin > RHmax') % (nOfErr), False)
                        # print max first 10 rows
                        self.FEEDBACK.reportError(self.tr('Max first 10 record reported'))
                        self.FEEDBACK.reportError(self.tr('Timestamp RHmin RHmax'))
                        for index, row in filtered_df.iterrows():
                            if index > 10: break
                            self.FEEDBACK.reportError(
                                self.tr('%s %s %s') % (row['timestamp'], row['recval_umin'], row['recval_umax']))
                    else:
                        self.FEEDBACK.pushInfo(self.tr('--> relative humidity OK!'))

            # 5. check solar radiation
            ws_rgcorr = self.readTimeSerie('ws_rgcorr', wsid)
            s,e = self.getTimeLimits(ws_rgcorr)
            sList.append(s)
            eList.append(e)
            # https://www.sciencedirect.com/science/article/abs/pii/S0074614202800171
            # [0,600] W/m2 --> [0,600*0.0864] MJ/m2/day --> [0,50] MJ/m2/day
            filtered_df = ws_rgcorr[(ws_rgcorr['recval'] < 0) | (ws_rgcorr['recval'] > 50)]
            nOfErr = len(filtered_df.index)
            if nOfErr > 0:
                self.FEEDBACK.reportError(self.tr('A total of %s records has Rgcorr out of range [0,50]') % (nOfErr), False)
                # print max first 10 rows
                self.FEEDBACK.reportError(self.tr('Max first 10 record reported'))
                self.FEEDBACK.reportError(self.tr('Timestamp Rgcorr'))
                for index, row in filtered_df.iterrows():
                    if index > 10: break
                    self.FEEDBACK.reportError(self.tr('%s %s') % (row['timestamp'], row['recval']))
            else:
                self.FEEDBACK.pushInfo(self.tr('--> solar radiation OK!'))

            # 6. check wind speed
            ws_vmed = self.readTimeSerie('ws_vmed', wsid)
            s, e = self.getTimeLimits(ws_vmed)
            sList.append(s)
            eList.append(e)

            # https://globalwindatlas.info/en
            filtered_df = ws_rgcorr[(ws_vmed['recval'] < 0) | (ws_vmed['recval'] > 10)]
            nOfErr = len(filtered_df.index)
            if nOfErr > 0:
                self.FEEDBACK.reportError(self.tr('A total of %s records has ws_vmed out of range [0,10]') % (nOfErr),
                                          False)
                # print max first 10 rows
                self.FEEDBACK.reportError(self.tr('Max first 10 record reported'))
                self.FEEDBACK.reportError(self.tr('Timestamp ws_vmed'))
                for index, row in filtered_df.iterrows():
                    if index > 10: break
                    self.FEEDBACK.reportError(self.tr('%s %s') % (row['timestamp'], row['recval']))
            else:
                self.FEEDBACK.pushInfo(self.tr('--> wind speed OK!'))

            # put all values together
            minStartTs = min(sList)
            maxEndTs = max(eList)
            all_df = pd.date_range(start=minStartTs, end=maxEndTs).to_series(name = 'timestamp')
            all_df = pd.merge(all_df, ws_tmax, how="left", on='timestamp', suffixes=("", "_tmax"))
            all_df.rename(columns={'recval': 'ws_tmax'}, inplace=True)
            all_df = pd.merge(all_df, ws_tmin, how="left", on='timestamp', suffixes=("", "_tmin"))
            all_df.rename(columns={'recval': 'ws_tmin'}, inplace=True)
            all_df = pd.merge(all_df, ws_ptot, how="left", on='timestamp', suffixes=("", "_ptot"))
            all_df.rename(columns={'recval': 'ws_ptot'}, inplace=True)
            all_df = pd.merge(all_df, ws_umin, how="left", on='timestamp', suffixes=("", "_umin"))
            all_df.rename(columns={'recval': 'ws_umin'}, inplace=True)
            all_df = pd.merge(all_df, ws_umax, how="left", on='timestamp', suffixes=("", "_umax"))
            all_df.rename(columns={'recval': 'ws_umax'}, inplace=True)
            all_df = pd.merge(all_df, ws_vmed, how="left", on='timestamp', suffixes=("", "_vmed"))
            all_df.rename(columns={'recval': 'ws_vmed'}, inplace=True)

            # delete all unnecessary columns
            all_df.drop(all_df.filter(regex='^fid').columns, axis=1, inplace=True)
            all_df.drop(all_df.filter(regex='^wsid').columns, axis=1, inplace=True)

#            all_df['timestamp'] = pd.to_datetime(all_df['timestamp'], format='%Y-%m-%d', errors='coerce')

            #pd.set_option('display.max_rows', all_df.shape[0] + 1)

            #print(all_df)
            #all_df.set_index("timestamp", inplace=True)

            #print(all_df)

            #print(type(all_df['timestamp'][0]))

            temp_png = os.path.join(outImageFolder, 'meteo_var_ws_%s.png'%wsid)

            self.makeMeteoPlot(all_df, {'ws_ptot':'Precipitation (mm)','ws_tmax':'Temp.max (°C)','ws_tmin':'Temp.min (°C)'},
                               temp_png)
            temp_png_rel = os.path.relpath(temp_png, os.path.dirname(outfile))


            # axs = all_df.plot.area(figsize=(12, 4), subplots=True, stacked = False)
            # #plt.show()
            # plt.savefig(r'C:\examples\test_advopt\test1.png')

        if self.conn: self.stopConnection()


        # 5. %plot% all data/stations
        # 6. %plot% correlation between variables
        # 7. check complete periods, print only complete years

        ## Soils ##
        # Soilmap@exid %in% Soiltypes@id %in% Soilprofiles@id
        # maxdepth, ksat >0
        # theta_fc,theta_wp,theta_r,theta_sat > 0 & <= 1
        # theta_sat>theta_fc>theta_wp>theta_r
        # txtr_code compreso tra 1 e 12

        ## Soil uses ##
        # uses_map@exid %in% soil_uses@id
        # soil_uses@croplist %in% crop_types@id
        # sowingdate_min [1-366]
        # sowingdelay_max	[1-366]
        # sowingdate_min+sowingdelay_max < 366
        # harvestdate_max
        # harvnum_max > 1
        # cropsoverlap [1-366]
        # tsowing, tdaybase, tcutoff ?
        # vern [0,1]
        # if vern == 1:
        # tv_min < tv_max
        # vstart, vend [1-366]
        # vstart < vend
        # vfmin, , vslope ?
        # ph_r, daylength_if, daylength_ins ?
        # wp ?
        # fsink ?
        # tcrit_hs, tlim_hs, hi
        # kyT,ky1,ky2,ky3,ky4 [0-1]
        # praw [0-1]
        # ainterception [0,1]
        # cl_cn [1,2,3,4,5]
        # irrigation [0,1]
        # gdd %ASC&
        # gdd,kcb,lai,hc,sr %plot%
        # adv_opts

        ## Irrigation methods ##
        # irrmap@extid %in% irrtable@id
        # irrmap@extid > 0
        # name	qadaq
        # k_stress, k_stresswells [0-1]
        # fw
        # min_a,max_a,min_b,max_b ?
        # losses_a,losses_b,losses_c ?
        # f_interception [0,1]
        # len(irr_time)==24 & [1-24]
        # len(irr_fraction) == 24 & sum(irrfract) == 1.0
        # irr_eff [0.-1.]
        # adv_opts ?

        ## Network ##
        # continuity
        # discharges >= 0
        # nodes attributes
        # links attributes
        # irrigation units attributes

        ## raster data ##
        # watertable > dtm

        return outfile


if __name__ == '__main__':
    simFolder=r'C:\examples\ex_report_SIM'
    outputFile = 'C:/examples/test_img/test_overview.html'
    dbFile = r'C:\examples\test_advopt\test1.gpkg'
    RB = CheckDatabaseBuilder()
    RB.initDB(dbFile)
    outfile = RB.makeReport(simFolder,outputFile)
    print(outfile)
