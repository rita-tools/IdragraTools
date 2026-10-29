import glob
import os

import numpy as np
import pandas as pd
import re

import matplotlib
from fontTools.ttLib.tables.TupleVariation import inferRegion_
from qgis._core import QgsVectorLayer

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import cm
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec
import matplotlib.dates as mdates
from osgeo import ogr

from datetime import datetime,timedelta
import math
# import as module
from report.annual_totals_report_builder import AnnualTotalsReportBuilder

class ControlPointReportBuilder(AnnualTotalsReportBuilder):

    def __init__(self,feedback = None, tr = None):
        super().__init__(feedback, tr)

        self.irrunit_template = os.path.join(self.rb_dir, 'default', 'irrigation_unit_report.html')

    def readCells(self,cellsFile, feedback, tr):
        # sample structure
        # ncells = 2
        # table =
        # ID	X	Y
        # 2	25	18 # name - descr
        # 1	5	9 # name - descr
        # endtable =
        cells = []

        if not os.path.exists(cellsFile):
            feedback.reportError("Cells file does not exist")
            return cells

        cells_rows = []
        with open(cellsFile,'r') as f:
            cells_rows = f.readlines()

        if len(cells_rows)>0:
            ncells = int(cells_rows[0].split('=')[1].strip())
            for i in range(0,ncells):
                toks = cells_rows[3+i].split('#')
                descr = ''
                if len(toks)>1: name,descr = toks[1].split('-')
                temp = toks[0].split()
                temp = tuple([int(x) for x in temp])+(name,descr,)
                cells.append(temp)

        return cells

    def readControlPointsParams(self, csvFile, col_names):
        df = None
        msg = ''

        try:
            # open csv file as dataframe
            res = pd.read_csv(csvFile, sep=r'\s*;\s*', names=col_names,
                             engine='python', header=0, skiprows=1)
            res = res.set_index('pars')
        except Exception as e:
            msg += str(e) + '\n'

        return res, msg

    def parsToDataframe(self, df, year, varList=[]):
        msg = ''
        res = None
        try:
            # open csv file as dataframe
            res = pd.DataFrame(columns=['timestamp'] + varList)
            dateList = pd.date_range(datetime.strptime('%s0101' % year, '%Y%m%d'),
                                     datetime.strptime('%s1231' % year, '%Y%m%d'),
                                     freq='d').tolist()
            res['timestamp'] = dateList

            for var in varList:
                varValue = df.loc[var,'value']
                res[var] = [varValue] * len(dateList)


        except Exception as e:
            msg += str(e) + '\n'

        return res, msg

    def readControlPointsResults(self,csvFile, year, columList=None):
        msg = ''
        df = None

        try:
            # open csv file as dataframe
            df = pd.read_csv(csvFile, sep=r'\s*;\s*', usecols=columList, engine='python')
            # print('df',year,df)
            # replace Giulian_date with date
            df['doy'] = df['Giulian_day']
            df['Giulian_day'] = df['Giulian_day'].apply(lambda x: datetime.strptime(str(year) + str(x), '%Y%j'))
        except Exception as e:
            msg += str(e) + '\n'

        return df, msg

    def makeSoilStats(self, df, pars_df,evap_lay_m=0.1):
        # calculate TAW respect to rference 1 m soil depth
        taw_ref = (df['ThetaI_fc']- df['ThetaI_wp'])*evap_lay_m*1000 + (df['ThetaII_fc']  - df['ThetaII_wp']) * (1-evap_lay_m) * 1000
        taw = (df['ThetaI_fc']- df['ThetaI_wp'])*evap_lay_m*1000 + (df['ThetaII_fc']  - df['ThetaII_wp']) * df['thickness_II_m'] * 1000

        crop1_start = pars_df.loc['ii0','crop1']
        crop1_end = pars_df.loc['iie', 'crop1']
        crop2_start = pars_df.loc['ii0', 'crop2']
        crop2_end = pars_df.loc['iie', 'crop2']
        taw1_max = np.nan
        taw2_max = np.nan
        taw1_min = np.nan
        taw2_min = np.nan
        taw1_mean = np.nan
        taw2_mean = np.nan

        if crop1_start and crop1_end:
            if crop1_start < crop1_end:
                # do something
                mask = (df['doy'] >= crop1_start) & (df['doy'] <= crop1_end)
            else:
                # split with end date
                mask = ((df['doy'] >= crop1_start) & (df['doy'] <= 366)) | ((df['doy'] >= 0) & (df['doy'] <= crop1_end))
            taw1_min = taw[mask].min()
            taw1_max = taw[mask].max()
            taw1_mean = taw[mask].mean()

        if crop2_start and crop2_end:
            if crop2_start < crop2_end:
                # do something
                mask = (df['doy'] >= crop2_start) & (df['doy'] <= crop2_end)
            else:
                # split with end date
                mask = ((df['doy'] >= crop2_start) & (df['doy'] <= 366)) | ((df['doy'] >= 0) & (df['doy'] <= crop2_end))

            taw2_min = taw[mask].min()
            taw2_max = taw[mask].max()
            taw2_mean = taw[mask].mean()

        # TODO calculate the number of days with deficit
        res = {'taw_ref': taw_ref[0],
               'taw1_min': taw1_min, 'taw2_min': taw2_min,
               'taw1_max': taw1_max, 'taw2_max': taw2_max,
               'taw1_mean': taw1_mean, 'taw2_mean': taw2_mean}
        return res

    def makeIrrigationStats(self, df, pars_df):
        # Index(['Giulian_day', 'rain_mm', 'pday', 'irrig_mm', 'theta1_mm', 'ks',
        #        'thickness_II_m', 'theta_old_mm', 'rawbig', 'rawinf', 'timestamp',
        #        'ThetaI_fc', 'ThetaI_wp', 'ThetaII_fc', 'ThetaII_wp',
        #        'Method efficiency'],
        #       dtype='object')
        mask = df['irrig_mm'] != 0.

        irr_count = mask.sum()
        irr_sum = df.loc[mask,'irrig_mm'].sum()
        irr_mean = df.loc[mask,'irrig_mm'].mean()
        irr_min = df.loc[mask, 'irrig_mm'].min()
        irr_max = df.loc[mask, 'irrig_mm'].max()

        pos = df.index[mask]
        diff = pos.to_series().diff().dropna()
        #print('diff:',diff)
        mean_diff = diff.mean()
        min_diff = diff.min()

        first_irr_idx = mask.idxmax()
        last_irr_idx = mask[::-1].idxmax()
        first_date = df.iloc[first_irr_idx]['timestamp'].strftime('%Y-%m-%d')
        last_date = df.iloc[last_irr_idx]['timestamp'].strftime('%Y-%m-%d')
        diff_between_irr = last_irr_idx - first_irr_idx
        #average_diff = diff_between_irr / (irr_count-1) # the same as mean diff

        return {'irr_count':irr_count, 'irr_sum':irr_sum,'irr_mean':irr_mean,
                'irr_min':irr_min,'irr_max':irr_max,
                'diff_between_irr':diff_between_irr, 'mean_diff':mean_diff,'min_diff':min_diff,
                'first_date':first_date, 'last_date':last_date,
                'first_irr_idx':first_irr_idx, 'last_irr_idx':last_irr_idx}

    def makeSWCPlot(self, days, theta_soil,theta_wp, theta_fc, yr, outpath, main_title,irr_start, irr_end, tr):
        fileName = os.path.join(outpath, main_title.lower().replace(' ', '_') + '.png')
        irr_start_date = datetime.strptime(f'{yr}-{irr_start}', '%Y-%j')
        irr_start_end = datetime.strptime(f'{yr}-{irr_end}', '%Y-%j')

        fig, ax = plt.subplots(1, 1,
                                sharex=True, figsize=(8, 4))

        ### plot all water inputs
        ax.axvspan(irr_start_date, irr_start_end,
                       color='gray', label=tr("Irrigation season"), alpha=0.2)

        ax.plot(days, theta_soil, linestyle="-", marker="",
                color='#4A7EBB', label=tr('Soil water content (-)'), linewidth=2)

        ax.plot(days, theta_wp, linestyle="-", marker="",
                color='#BE4B48', label=tr('Wilting point (-)'), linewidth=2)

        ax.plot(days, theta_fc, linestyle="-", marker="",
                color='#98B954', label=tr('Field capacity (-)'), linewidth=2)

        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(framealpha=0.5)
        ax.set_title(tr(main_title))

        plt.subplots_adjust(top=0.95, bottom=0.15, hspace=0.1)
        plt.tight_layout()
        fig.savefig(fileName, format='png')
        plt.close(fig)

        return fileName

    def makeWatFluxPlot(self, df, yr, outpath,main_title,irr_start, irr_end, tr):
        fileName = os.path.join(outpath, main_title.lower().replace(' ', '_') + '.png')
        # Index(['Giulian_day', 'rain_mm', 'pday', 'irrig_mm', 'theta1_mm', 'ks',
        #        'thickness_II_m', 'theta_old_mm', 'rawbig', 'rawinf', 'timestamp',
        #        'ThetaI_fc', 'ThetaI_wp', 'ThetaII_fc', 'ThetaII_wp',
        #        'Method efficiency'],
        #       dtype='object')
        days = df['Giulian_day'].to_numpy()

        prec_mm = df['rain_mm'].to_numpy()
        irr_mm = df['irrig_mm'].to_numpy()

        irr_start_date = datetime.strptime(f'{yr}-{irr_start}', '%Y-%j')
        irr_start_end = datetime.strptime(f'{yr}-{irr_end}', '%Y-%j')

        interception_mm = df['rain_mm'].to_numpy()
        runoff_mm = df['runoff_mm'].to_numpy()
        eva_mm = df['eva_mm'].to_numpy()
        trasp_act1_mm = df['trasp_act1_mm'].to_numpy()
        trasp_act2_mm = df['trasp_act2_mm'].to_numpy()
        trasp_act_mm = trasp_act1_mm + trasp_act2_mm

        soilwat1_mm = df['theta1_mm'].to_numpy()
        perc1_mm = df['perc1_mm'].to_numpy()

        soilwat2_mm = df['theta_old_mm'].to_numpy()
        perc2_mm = df['perc2_mm'].to_numpy()
        capflux_mm = df['capflux_mm'].to_numpy()

        max_input = 1.1 * (prec_mm + irr_mm).max()

        fig, axs = plt.subplots(5, 1,
                                sharex=True, figsize=(8, 8))

        ### plot all water inputs
        axs[0].axvspan(irr_start_date, irr_start_end,
                       color='gray', label=tr("Irrigation season"), alpha=0.2)

        axs[0].bar(days, prec_mm,
                   label=tr('Precipitation (mm)'), alpha=0.7
                   )

        axs[0].bar(days, irr_mm,
                   bottom=prec_mm,
                   label=tr("Irrigation (mm)"), alpha=0.7
                   )

        axs[0].text(1.02, 0.5, tr("WATER INPUT"),
                    transform=axs[0].transAxes,
                    va="center", ha="left", rotation=90
                    )
        axs[0].set_ylim([0, max(5, max_input)])
        axs[0].invert_yaxis()
        axs[0].grid(True, linestyle="--", alpha=0.5)
        axs[0].legend(framealpha=0.5)
        axs[0].set_title(tr(main_title))


        # plot atmosphere fluxes
        axs[1].axvspan(irr_start_date, irr_start_end,
                       color='gray', alpha=0.2)

        axs[1].plot(days, eva_mm,
                    linestyle="-", marker="",
                    color="#DA8137", linewidth=2,
                    label=tr("Evaporation (mm)")
                    )

        axs[1].plot(days, trasp_act_mm,
                    linestyle="-", marker="",
                    color="#86A44A", linewidth=2,
                    label=tr("Transpiration (mm)")
                    )

        axs[1].text(1.02, 0.5, tr("ATMOSPHERE"),
                    transform=axs[1].transAxes,
                    va="center", ha="left", rotation=90
                    )
        axs[1].grid(True, linestyle="--", alpha=0.5)
        axs[1].legend(framealpha=0.5)

        # plot canopy
        axs[2].axvspan(irr_start_date, irr_start_end,
                       color='gray', alpha=0.2)

        axs[2].plot(days, interception_mm,
                    linestyle="-", marker="",
                    color="#A8423F", linewidth=2,
                    label=tr("Interception (mm)")
                    )

        axs[2].plot(days, runoff_mm,
                    linestyle="-", marker="",
                    color="#6E548D", linewidth=2,
                    label=tr("Runoff (mm)")
                    )

        axs[2].text(1.02, 0.5, tr("ABOVE GROUND"),
                    transform=axs[2].transAxes,
                    va="center", ha="left", rotation=90
                    )
        axs[2].set_ylim([0, max(5, max_input)])
        axs[2].grid(True, linestyle="--", alpha=0.5)
        axs[2].legend(framealpha=0.5)

        # plot first layer

        axs[3].axvspan(irr_start_date, irr_start_end,
                       color='gray', alpha=0.2)

        axs[3].plot(days, soilwat1_mm,
                    linestyle="-", marker="",
                    color="#4198AF", linewidth=2,
                    label=tr("Soil water content (mm)")
                    )

        axs[3].plot(days, perc1_mm,
                    linestyle="-", marker="",
                    color="#416FA6", linewidth=2,
                    label=tr("Percolation (mm)")
                    )

        axs[3].text(1.02, 0.5, tr(r"1$^{st}$ SOIL LAYER"),
                    transform=axs[3].transAxes,
                    va="center", ha="left", rotation=90
                    )
        axs[3].grid(True, linestyle="--", alpha=0.5)
        axs[3].legend(framealpha=0.5)

        # plot second layer
        axs[4].axvspan(irr_start_date, irr_start_end,
                       color='gray', alpha=0.2)

        axs[4].plot(days, soilwat2_mm,
                    linestyle="-", marker="",
                    color="#4198AF", linewidth=2,
                    label=tr("Soil water content (mm)")
                    )


        axs[4].plot(days, capflux_mm,
                    linestyle="-", marker="",
                    color="#A8423F", linewidth=2,
                    label="Capillary rise (mm)"
                    )

        axs[4].plot(days, perc2_mm,
                    linestyle="-", marker="",
                    color="#6E548D", linewidth=2,
                    label="Percolation (mm)"
                    )

        axs[4].text(1.02, 0.5, tr(r"2$^{nd}$ SOIL LAYER"),
                    transform=axs[4].transAxes,
                    va="center", ha="left", rotation=90
                    )
        # axs[2].set_xticks(giorni)  # assicura che ci siano tick sui giorni
        # axs[2].set_xticklabels(giorni, rotation=90)  # ruota 90° (verticale)
        axs[4].xaxis.set_major_locator(mdates.AutoDateLocator())
        axs[4].xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        axs[4].set_xlabel(tr('Days'))
        # axs[2].set_ylabel("Umidità del suolo (mm)")
        axs[4].grid(True, linestyle="--", alpha=0.5)
        axs[4].legend(framealpha=0.5)

        plt.subplots_adjust(top=0.95, bottom=0.15, hspace=0.1)
        plt.tight_layout()
        fig.savefig(fileName, format='png')
        plt.close(fig)

        return fileName

    def makeIrrEventsPlot(self, df, yr, outpath,main_title,irr_start, irr_end, tr):
        #
        fileName = os.path.join(outpath, main_title.lower().replace(' ','_')+ '.png')
        # Index(['Giulian_day', 'rain_mm', 'pday', 'irrig_mm', 'theta1_mm', 'ks',
        #        'thickness_II_m', 'theta_old_mm', 'rawbig', 'rawinf', 'timestamp',
        #        'ThetaI_fc', 'ThetaI_wp', 'ThetaII_fc', 'ThetaII_wp',
        #        'Method efficiency'],
        #       dtype='object')
        days = df['Giulian_day'].to_numpy()
        soilwat_mm = df['theta1_mm'].to_numpy()+df['theta_old_mm'].to_numpy()
        irr_thrs_mm = df['rawbig'].to_numpy()
        leaf_area_idx = df['lai'].to_numpy()
        prec_mm = df['rain_mm'].to_numpy()
        irr_mm = df['irrig_mm'].to_numpy()
        irr_start_date = datetime.strptime(f'{yr}-{irr_start}', '%Y-%j')
        irr_start_end = datetime.strptime(f'{yr}-{irr_end}', '%Y-%j')

        max_input = 1.1 * (prec_mm + irr_mm).max()

        fig, axs = plt.subplots(3, 1,
                                sharex=True, figsize=(8, 6))

        ### plot all water inputs
        axs[0].axvspan(irr_start_date, irr_start_end,
                       color='gray', label=tr("Irrigation season"), alpha=0.2)

        axs[0].bar(days, prec_mm,
                   label=tr('Precipitation (mm)'), alpha=0.7
                   )

        axs[0].bar(days, irr_mm,
                   bottom=prec_mm,
                   label=tr("Irrigation (mm)"), alpha=0.7
                   )

        axs[0].text(1.02, 0.5, tr("WATER INPUT"),
                    transform=axs[0].transAxes,
                    va="center", ha="left", rotation=90
                    )
        axs[0].set_ylim([0, max(5, max_input)])
        axs[0].invert_yaxis()
        axs[0].grid(True, linestyle="--", alpha=0.5)
        axs[0].legend(framealpha=0.5)
        axs[0].set_title(tr(main_title))

        # plot crop grow

        axs[1].axvspan(irr_start_date, irr_start_end,
                       color='gray', alpha=0.2)

        axs[1].plot(days, leaf_area_idx,
                    linestyle="-", marker="",
                    color="green", linewidth=2,
                    label=tr("Leaf Area Index (-)")
                    )

        axs[1].text(1.02, 0.5, tr("CROP"),
                    transform=axs[1].transAxes,
                    va="center", ha="left", rotation=90
                    )
        axs[1].grid(True, linestyle="--", alpha=0.5)
        axs[1].legend(framealpha=0.5)

        # plot soil
        axs[2].axvspan(irr_start_date, irr_start_end,
                       color='gray', alpha=0.2)

        axs[2].plot(days, soilwat_mm,
                    linestyle="-", marker="",
                    color="blue", linewidth=2,
                    label=tr("Soil water content (mm)")
                    )

        axs[2].plot(days, irr_thrs_mm,
                    linestyle="-", marker="",
                    color="r", linewidth=2,
                    label="Irrigation threshold (mm)"
                    )
        axs[2].text(1.02, 0.5, tr("SOIL"),
                    transform=axs[2].transAxes,
                    va="center", ha="left", rotation=90
                    )
        # axs[2].set_xticks(giorni)  # assicura che ci siano tick sui giorni
        # axs[2].set_xticklabels(giorni, rotation=90)  # ruota 90° (verticale)
        axs[2].xaxis.set_major_locator(mdates.AutoDateLocator())
        axs[2].xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        axs[2].set_xlabel(tr('Days'))
        # axs[2].set_ylabel("Umidità del suolo (mm)")
        axs[2].grid(True, linestyle="--", alpha=0.5)
        axs[2].legend(framealpha=0.5)

        plt.subplots_adjust(top=0.95, bottom=0.15, hspace=0.1)
        plt.tight_layout()
        fig.savefig(fileName, format='png')
        plt.close(fig)

        return fileName

    def makeReport(self,simFolder,outfile):
        #set folder for images
        outImageFolder = self.makeSubFolder(outfile,'_img')
        #set folder for statistics
        outStatFolder = self.makeSubFolder(outfile,'_stat')

        # read idragra file
        idragraFile = os.path.join(simFolder, 'idragra_parameters.txt')
        simPar = self.readIdragraParameters(idragraFile, self.FEEDBACK, self.tr)

        cropcoefFile = os.path.join(simFolder, 'cropcoef.txt')
        cropcoefPar = self.readIdragraParameters(cropcoefFile, self.FEEDBACK, self.tr)

        cellsFile = os.path.join(simFolder, 'cells.txt')
        cellsList = self.readCells(cellsFile, self.FEEDBACK, self.tr)

        self.FEEDBACK.setProgress(5.)
        irr_stats = []
        soil_stats = []
        for cell in cellsList:
            cell_id = cell[0]
            cell_name = cell[3]

            self.FEEDBACK.pushInfo(self.tr(f'Processing cell id: {cell_id}: {cell[3]} ...'))
            # get the available years:
            yr_list = []
            cellout_list = glob.glob(
                os.path.join(simFolder, simPar['outputpath'], f'*_cell_{cell[1]}_{cell[2]}.csv'))

            for cellout in cellout_list:
                self.FEEDBACK.pushInfo(self.tr(f'--> {cellout}'))
                yr = int(os.path.basename(cellout)[0:4])
                # open cell output
                cellout_df, msg = self.readControlPointsResults(cellout, yr,
                                                                columList=['Giulian_day', 'rain_mm', 'pday', 'rawbig',
                                                                           'rawinf', 'theta1_mm', 'theta_old_mm',
                                                                           'irrig_mm', 'thickness_II_m', 'lai','perc1_mm', 'perc2_mm',
                                                                           'runoff_mm', 'eva_mm','trasp_act1_mm','trasp_act2_mm',
                                                                           'capflux_mm'])
                cellout_df['theta1'] = cellout_df['theta1_mm']/(float(simPar['zevap'])*1000)
                cellout_df['theta2'] = cellout_df['theta_old_mm'] / (cellout_df['thickness_II_m'] * 1000)

                # open cell info too
                # TODO: extract info and parameters synthesis
                cellinfo = os.path.join(simFolder, simPar['outputpath'], f'{yr}_cellinfo_{cell[1]}_{cell[2]}.csv')
                cellinfo_df, msg = self.readControlPointsParams(csvFile = cellinfo, col_names=['pars', 'value'])

                # open cell parameters
                cellpars = os.path.join(simFolder, simPar['outputpath'], f'{yr}_cellparameters_{cell[1]}_{cell[2]}.csv')
                cellpars_df, mgs = self.readControlPointsParams(csvFile = cellpars, col_names=['pars', 'crop1','crop2'])

                cellinfo_daily_df, msg = self.parsToDataframe(cellinfo_df, yr,
                                     varList=['ThetaI_fc', 'ThetaI_wp', 'ThetaII_fc',
                                              'ThetaII_wp',
                                              'Method efficiency'])

                # combine data
                df = pd.merge(cellout_df, cellinfo_daily_df, left_on='Giulian_day', right_on='timestamp')

                plt_fn = self.makeSWCPlot(days = df['Giulian_day'].to_numpy(), theta_soil = df['theta1'].to_numpy(),
                                          theta_wp = df['ThetaI_wp'].to_numpy(), theta_fc = df['ThetaI_fc'].to_numpy(),
                                          yr =yr, outpath = outImageFolder, main_title = f'First layer soil water {yr} [{cell_name}]',
                                          irr_start = simPar['startirrseason'], irr_end = simPar['endirrseason'],
                                          tr = self.tr)

                plt_fn = self.makeSWCPlot(days = df['Giulian_day'].to_numpy(), theta_soil = df['theta2'].to_numpy(),
                                          theta_wp = df['ThetaII_wp'].to_numpy(), theta_fc = df['ThetaII_fc'].to_numpy(),
                                          yr =yr, outpath = outImageFolder, main_title = f'Second layer soil water {yr} [{cell_name}]',
                                          irr_start = simPar['startirrseason'], irr_end = simPar['endirrseason'],
                                          tr = self.tr)

                plt_fn = self.makeWatFluxPlot(df, yr, outImageFolder, f'Water fluxes {yr} [{cell_name}]',
                                              simPar['startirrseason'], simPar['endirrseason'],self.tr)

                plt_fn = self.makeIrrEventsPlot(df, yr,outImageFolder,f'Irrigation events {yr} [{cell_name}]',
                                                simPar['startirrseason'], simPar['endirrseason'],self.tr)


                # TODO: crop statistics
                # TODO: water balance fluxes all_year, crop1, crop2

                irr_stat_dict = self.makeIrrigationStats(df, cellpars_df)
                irr_stat_dict['cp_id']=cell_id
                irr_stat_dict['cp_name'] = cell_name
                irr_stat_dict['year'] = yr
                irr_stats.append(irr_stat_dict)

                soil_stat_dict = self.makeSoilStats(df, cellpars_df)
                soil_stat_dict['cp_id'] = cell_id
                soil_stat_dict['cp_name'] = cell_name
                soil_stat_dict['year'] = yr
                soil_stats.append(soil_stat_dict)

        irr_stats_df = pd.DataFrame(irr_stats)
        # sort column
        cols_to_front = ['cp_id','cp_name', 'year']
        other_cols = [c for c in irr_stats_df.columns if c not in cols_to_front]
        new_order = cols_to_front + other_cols
        irr_stats_df = irr_stats_df[new_order]

        irr_stats_df = irr_stats_df.sort_values(by=['cp_id', 'year'], ascending=[True, True])
        irr_stats_df.to_excel(os.path.join(outStatFolder,'irr_stats.xlsx'), index=False)

        soil_stats_df = pd.DataFrame(soil_stats)
        # sort column
        cols_to_front = ['cp_id','cp_name', 'year']
        other_cols = [c for c in soil_stats_df.columns if c not in cols_to_front]
        new_order = cols_to_front + other_cols
        soil_stats_df = soil_stats_df[new_order]

        soil_stats_df = soil_stats_df.sort_values(by=['cp_id', 'year'], ascending=[True, True])
        soil_stats_df.to_excel(os.path.join(outStatFolder,'soil_stats.xlsx'), index=False)

        return ''

if __name__ == '__main__':
    from test_conf import *  # should contain "simFolder","outputFile" and other useful variable
    RB = ControlPointReportBuilder()
    cp_stats = RB.makeReport(simFolder,outputFile)
    print('done!')