import glob
import math
import os
from copy import deepcopy

import numpy as np
import pandas as pd
import re

import matplotlib
from matplotlib.sankey import Sankey

from report.tools.get_longest_period import get_longest_period
from report.tools.make_statistics import make_statistics
from report.tools.read_idragra_parameters import read_idragra_parameters
from report.tools.save_dataframe_with_comment import save_dataframe_with_comment
from report.tools.weather_analysis import make_avg_timeserie, make_stat_from_ts

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from matplotlib import cm
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec
from matplotlib.transforms import Bbox
from datetime import datetime,timedelta

# import as module
from report.annual_totals_report_builder import AnnualTotalsReportBuilder

class CompareScenariosReportBuilder(AnnualTotalsReportBuilder):

    def __init__(self,feedback = None, tr = None):
        super().__init__(feedback, tr)

        self.annual_template = os.path.join(self.rb_dir, 'default', 'water_productivity_report.html')

    def make_report_tables(self,sim_path):
        # store main statistics
        report_vals = []  # lista di tuple per ogni record

        if not os.path.exists(sim_path):
            print('ERROR: no simulation path "%s"' % sim_path)
            return

        # TODO: leggi l'idragra_parameters.txt per avere i riferimenti della simulazione
        sim_pars = read_idragra_parameters(os.path.join(sim_path, 'idragra_parameters.txt'),self.FEEDBACK,self.tr)
        start_irr_season = datetime.strptime('%s-%s' % (sim_pars['startirrseason'], 2020),
                                             '%j-%Y')  # use leap year as reference
        end_irr_season = datetime.strptime('%s-%s' % (sim_pars['endirrseason'], 2020),
                                           '%j-%Y')  # use leap year as reference
        n_irr_days = (end_irr_season - start_irr_season).days + 1  # add the first day

        report_vals.append(('start_irr_season',
                            start_irr_season.strftime('%d-%m'),
                            'Irrigation season starts'))
        report_vals.append(('end_irr_season',
                            end_irr_season.strftime('%d-%m'),
                            'Irrigation season ends'))
        report_vals.append(('n_irr_days',
                            n_irr_days,
                            'Irrigation season length (days)'))

        # SET OUTPUT PATH AND CREATE FOLDER IF IT NOT EXISTS
        out_path = os.path.join(sim_path, 'report_stats')
        if not os.path.exists(out_path):
            os.makedirs(out_path)
        else:
            files = glob.glob(os.path.join(out_path, '*'))
            for f in files:
                os.remove(f)

        # MAKE STATISTICS FROM WEATHER DATA
        print('INFO: statistics from weather data')

        res = make_avg_timeserie(sim_path=sim_path)
        # ricorda che res è un dataframe con le seguenti colonne
        # ['data', 'doy', 'year', 'month', 'day', 'T_max', 'T_min', 'P_tot', 'U_max', 'U_min', 'V_med', 'RG_CORR']
        # TODO: registra giorno di inizio e fine e il numero di anni
        all_res = make_stat_from_ts(df=res)
        # print(all_res)
        save_dataframe_with_comment(os.path.join(out_path, 'ts_stat_all_period.csv'), all_res,
                                    'all period statistics')
        yr_res = make_stat_from_ts(df=res, grp_col='year')
        save_dataframe_with_comment(os.path.join(out_path, 'ts_stat_by_year.csv'), yr_res,
                                    'statistics by years')
        month_res = make_stat_from_ts(df=res, grp_col='month')
        save_dataframe_with_comment(os.path.join(out_path, 'ts_stat_by_month.csv'), month_res,
                                    'statistics by months')
        doy_res = make_stat_from_ts(df=res, grp_col='doy')
        save_dataframe_with_comment(os.path.join(out_path, 'ts_stat_by_doy.csv'), doy_res,
                                    'statistics by doy')

        # T_min_min	T_min_max	T_min_mean
        # T_max_min	T_max_max	T_max_mean
        # P_tot_min	P_tot_max	P_tot_mean
        # RH_min_min	RH_min_max	RH_min_mean
        # RH_max_min	RH_max_max	RH_max_mean
        # SR_min	SR_max	SR_mean
        # WV_min	WV_max	WV_mean

        report_vals.append(
            ('T_min_min', round(yr_res['T_min-min'].min(), 1),
             'Minimum of low temperatures in the simulation period'))
        report_vals.append(
            ('T_min_max', round(yr_res['T_min-max'].max(), 1),
             'Maximum of low temperatures in the simulation period'))
        report_vals.append(
            ('T_min_mean', round(yr_res['T_min-mean'].mean(), 1),
             'Mean of low temperatures in the simulation period'))

        report_vals.append(
            ('T_max_min', round(yr_res['T_max-min'].min(), 1),
             'Minimum of high temperatures in the simulation period'))
        report_vals.append(
            ('T_max_max', round(yr_res['T_max-max'].max(), 1),
             'Maximum of high temperatures in the simulation period'))
        report_vals.append(
            ('T_max_mean', round(yr_res['T_max-mean'].mean(), 1),
             'Mean of high temperatures in the simulation period'))

        report_vals.append(
            ('P_tot_min', round(yr_res['P_tot-sum'].min(), 1),
             'Minimum of cumulative annual precipitation in the simulation period'))
        report_vals.append(
            ('P_tot_max', round(yr_res['P_tot-sum'].max(), 1),
             'Maximum of cumulative annual precipitation in the simulation period'))
        report_vals.append(
            ('P_tot_mean', round(yr_res['P_tot-sum'].mean(), 1),
             'Mean of cumulative annual precipitation in the simulation period'))

        report_vals.append(('yr_rain_min',
                            yr_res.loc[yr_res['P_tot-sum'] == yr_res['P_tot-sum'].min(), 'year'].values[0],
                            'Year with lower precipitation'))

        report_vals.append(
            ('U_min_min', round(yr_res['U_min-min'].min(), 1), 'Minimum of low air humidity in the simulation period'))
        report_vals.append(
            ('U_min_max', round(yr_res['U_min-min'].max(), 1), 'Maximum of low air humidity in the simulation period'))
        report_vals.append(
            ('U_min_mean', round(yr_res['U_min-min'].mean(), 1), 'Mean of low air humidity in the simulation period'))

        report_vals.append(
            ('U_max_min', round(yr_res['U_max-min'].min(), 1), 'Minimum of high air humidity in the simulation period'))
        report_vals.append(
            ('U_max_max', round(yr_res['U_max-min'].max(), 1), 'Maximum of high air humidity in the simulation period'))
        report_vals.append(
            ('U_max_mean', round(yr_res['U_max-min'].mean(), 1), 'Mean of high air humidity in the simulation period'))

        report_vals.append(
            ('RG_CORR_min', round(yr_res['RG_CORR-min'].min(), 1),
             'Minimum of solar radiation in the simulation period'))
        report_vals.append(
            ('RG_CORR_max', round(yr_res['RG_CORR-max'].max(), 1),
             'Maximum of solar radiation in the simulation period'))
        report_vals.append(
            ('RG_CORR_mean', round(yr_res['RG_CORR-mean'].mean(), 1),
             'Mean of solar radiation in the simulation period'))

        report_vals.append(
            ('V_med_min', round(yr_res['V_med-min'].min(), 1),
             'Minimum of wind velocity in the simulation period'))
        report_vals.append(
            ('V_med_max', round(yr_res['V_med-max'].max(), 1),
             'Maximum of wind velocity in the simulation period'))
        report_vals.append(
            ('V_med_mean', round(yr_res['V_med-mean'].mean(), 1),
             'Mean of wind velocity in the simulation period'))

        # calcola il periodo più asciutto (P<=5mm)
        num_time, start_date, end_date = get_longest_period(res,
                                                            time_fld='data',
                                                            val_fld='P_tot',
                                                            lbound=0,
                                                            ubound=5)

        report_vals.append(('n_days_wop', num_time, 'Num. of consecutive days without precipitation (> 5 mm)'))
        report_vals.append(('start_day', start_date, 'No-rain period starts'))
        report_vals.append(('end_day', end_date, 'No-rain period ends'))

        # calcola la media del numero di giorni con pioggia significativa
        res['doy'] = res['doy'].astype(int)
        flt = (res['doy'] >= sim_pars['startirrseason']) * (res['doy'] <= sim_pars['endirrseason'] * (res['P_tot'] > 5))
        prec_df = res[flt].groupby(['year'], as_index=True)['P_tot'].agg(['count'])

        mean_num_prec = prec_df['count'].mean()
        report_vals.append(('n_days_wp', round(mean_num_prec, 1),
                            'Num. of days with precipitation (> 5 mm) during the irrigation period'))
        report_vals.append(
            ('perc_days_wp',
             round(100 * mean_num_prec / n_irr_days, 2),
             'Percentage of days with precipitation (>5mm) during the irrigation period'))

        # TODO: MAKE STATISTICS FROM INPUT GEODATA
        print('INFO: statistics from geodata')
        geodata_path = os.path.join(sim_path, 'geodata')
        # calcola le statistiche di superficie
        domain_fn = os.path.join(sim_path, 'geodata', 'domain.asc')

        area_stat_df = make_statistics(out_folder=geodata_path,
                                       par_fn_List=['shapearea'],
                                       par_name_list=['shapearea'],
                                       stat_list=['min', 'mean', 'max', 'sum', 'count'],
                                       mask_fn=domain_fn, mask_id=1,
                                       weights_fn=None,
                                       feedback=lambda s: print(s), tr=lambda s: s)

        report_vals.append(
            ('tot_fld_area_ha', round(area_stat_df.loc[0, 'shapearea_sum'] / 10000, 4), 'Total area (ha)'))
        report_vals.append(('n_fld', round(area_stat_df.loc[0, 'shapearea_count'], 0), 'Num. of fields'))
        report_vals.append(
            ('mean_fld_area_ha', round(area_stat_df.loc[0, 'shapearea_mean'] / 10000, 4), 'Mean area (ha)'))
        report_vals.append(
            ('min_fld_area_ha', round(area_stat_df.loc[0, 'shapearea_min'] / 10000, 4), 'Minimum area (ha)'))
        report_vals.append(
            ('max_fld_area_ha', round(area_stat_df.loc[0, 'shapearea_max'] / 10000, 4), 'Maximum area (ha)'))

        # print(area_stat_df)
        # MAKE STATISTICS FROM SIMULATION RESULTS
        print('INFO: statistics from results data')
        simout_path = os.path.join(sim_path, 'simout')

        weights_fn = os.path.join(sim_path, 'geodata', 'shapearea.asc')

        water_flx_dict = {
            'prec_tot': 'prec',
            'eva_act_agr': 'eva_act_agr',
            'trasp_act_tot': 'trasp_act_tot',
            'irr_tot': 'irr',
            'irr_loss': 'irr_losses',
            'run_tot': 'runoff',
            'net_flux_gw': 'net_flux',
            'irr_nr': 'irr_nr',
            'irr_mean': 'irr_mean',
            'eff_tot': 'eff_tot',
            'eva_pot_agr':'eva_pot_agr',
            'trasp_pot_tot':'trasp_pot_tot'
        }

        res_df = make_statistics(out_folder=simout_path,
                                 par_fn_List=['????_' + x for x in list(water_flx_dict.keys())],
                                 par_name_list=list(water_flx_dict.values()),
                                 stat_list=['min', 'mean', 'average', 'max'],
                                 mask_fn=domain_fn, mask_id=1,
                                 weights_fn=weights_fn,
                                 feedback=lambda s: print(s), tr=lambda s: s)

        res_df['ETc_pot_average'] = res_df['eva_pot_agr_average']+res_df['trasp_pot_tot_average']
        res_df['ETc_act_average'] = res_df['eva_act_agr_average'] + res_df['trasp_act_tot_average']
        res_df['ETc_ratio'] = res_df['ETc_act_average'] / res_df['ETc_pot_average']

        stat_fn = os.path.join(out_path, 'fluxes_by_year.csv')
        save_dataframe_with_comment(fn=stat_fn, df=res_df, meta='Main fluxes by year (mm)')

        # salva i flussi medi annui
        # 'P', 'I', 'E', 'T', 'N', 'R', 'L'
        report_vals.append(
            ('mean_prec', round(res_df['prec_average'].mean(), 1),
             'Mean precipitation for the simulation period (mm)'))
        report_vals.append(
            ('mean_act_eva', round(res_df['eva_act_agr_average'].mean(), 1),
             'Mean evaporation for the simulation period (mm)'))
        report_vals.append(
            ('mean_act_transp', round(res_df['trasp_act_tot_average'].mean(), 1),
             'Mean transpiration for the simulation period (mm)'))
        report_vals.append(
            ('mean_act_etc', round(res_df['ETc_act_average'].mean(), 1),
             'Mean actual evapotranspiration for the simulation period (mm)'))
        report_vals.append(
            ('mean_pot_etc', round(res_df['ETc_pot_average'].mean(), 1),
             'Mean potential evapotranspiration for the simulation period (mm)'))

        report_vals.append(
            ('crop_water_satisfaction', round(100 * res_df['ETc_ratio'].mean(), 2),
             'Crop water requirements satisfaction (%)'))

        report_vals.append(
            ('mean_net_flux', round(res_df['net_flux_average'].mean(), 1),
             'Mean percolation for the simulation period (mm)'))
        report_vals.append(
            ('mean_runoff', round(res_df['runoff_average'].mean(), 1),
             'Mean runoff for the simulation period (mm)'))
        report_vals.append(
            ('mean_irr_losses', round(res_df['irr_losses_average'].mean(), 1),
             'Mean irrigation losses for the simulation period (mm)'))

        report_vals.append(
            ('mean_irr_eff', round(res_df['eff_tot_average'].mean(), 1),
             'Mean irrigation efficiency (-)'))
        report_vals.append(
            ('mean_n_irr', round(res_df['irr_nr_average'].mean(), 1),
             'Mean irrigation events (-)'))
        report_vals.append(
            ('mean_irr_application', round(res_df['irr_mean_average'].mean(), 1),
             'Mean irrigation application (mm)'))

        report_vals.append(
            ('mean_irr', round(res_df['irr_average'].mean(), 1),
             'Mean water need for the simulation period (mm)'))
        report_vals.append(
            ('max_irr', round(res_df['irr_average'].max(), 1),
             'Max water need for the simulation period (mm)'))
        report_vals.append(
            ('yr_max_irr', res_df.loc[res_df['irr_average'] == res_df['irr_average'].max(), 'year'].values[0],
             'Year with the maximum water need for the simulation period'))

        step_name = 'step'
        if sim_pars['monthlyflag']: step_name = 'month'

        water_flx_dict = {
            'et_act': 'et_act',
            'et_pot': 'et_pot',
            'flux2': 'flux2',
            'runoff': 'runoff',
            'caprise': 'caprise',
            'irr': 'irr',
            'irr_distr': 'irr_distr',
            'irr_privw': 'irr_privw',
            'irr_loss': 'irr_loss',
            'trasp_act': 'trasp_act',
            'trasp_pot': 'trasp_pot',
        }

        res_df = make_statistics(out_folder=simout_path,
                                 par_fn_List=['????_'+step_name+'*_' + x for x in list(water_flx_dict.keys())],
                                 par_name_list=list(water_flx_dict.values()),
                                 stat_list=['min', 'mean', 'average', 'max'],
                                 mask_fn=domain_fn, mask_id=1,
                                 weights_fn=weights_fn,
                                 feedback=lambda s: print(s), tr=lambda s: s)

        #
        res_df.sort_values(by=['year', 'month'], inplace=True)
        stat_fn = os.path.join(out_path, 'fluxes_by_month.csv')
        save_dataframe_with_comment(fn=stat_fn, df=res_df, meta='Main fluxes by month (mm)')

        res_df['irr_vol_m3'] = res_df['irr_average'] * res_df['area'] / 1000
        stat_df = res_df.groupby(['month'])['irr_vol_m3'].agg(['mean', 'min', 'max'])
        stat_df = stat_df.reset_index()
        stat_fn = os.path.join(out_path, 'volumes_by_month.csv')
        save_dataframe_with_comment(fn=stat_fn, df=stat_df, meta='Irrigation volumes by month (m^3)')

        report_vals.append(
            ('max_irr_volume', round(stat_df['mean'].max(), 0), 'Maximum water need in %s (m^3)'%step_name))
        report_vals.append(
            ('max_irr_month', stat_df.loc[stat_df['mean'] == stat_df['mean'].max(), 'month'].values[0],
             '%s with the highest water need' % step_name))

        # par_fn = 'irr_tot'
        # out_file_list = glob.glob(os.path.join(simout_path, '????_'+par_fn + '.asc'))
        # print(out_file_list)
        #
        # res_df = make_statistics_by_group(out_folder= simout_path,
        #                                   par_fn_list= out_file_list,
        #                                   par_name_list = ['2019_'+par_fn,'2020_'+par_fn],
        #                                   stat_list=['min', 'mean', 'average', 'max'],
        #                                   cat_fn=os.path.join(sim_path,'geodata','soiluse.asc'), cat_id_list=[],
        #                                   weights_fn=weights_fn,
        #                                   feedback=lambda s: print(s), tr=lambda s: s)
        #
        # stat_fn = os.path.join(out_path, '%s_by_soiluse.csv'%par_fn)
        # save_dataframe_with_comment(fn=stat_fn, df=res_df, meta='Total irrigation (mm) by soiluse')

        # calcola le rese

        prod1_dict = {
            'biomass_pot_1': 'biomass_pot',
            'yield_act_1': 'yield_act',
            'yield_pot_1': 'yield_pot'
        }

        prod1_df = make_statistics(out_folder=simout_path,
                                   par_fn_List=['????_' + x for x in list(prod1_dict.keys())],
                                   par_name_list=list(prod1_dict.values()),
                                   stat_list=['min', 'mean', 'average', 'max'],
                                   mask_fn=domain_fn, mask_id=1,
                                   weights_fn=weights_fn,
                                   feedback=lambda s: print(s), tr=lambda s: s)
        prod1_df = prod1_df.fillna(0.0)  # fix no crop
        prod1_fn = os.path.join(out_path, 'prod_first_stats.csv')
        save_dataframe_with_comment(fn=prod1_fn, df=prod1_df,
                                    meta='First crop production: biomass (t/ha), yield (t/ha)')

        report_vals.append(
            ('mean_biomass1', round(prod1_df['biomass_pot_average'].mean(), 2),
             'Mean potential biomass 1st crop (t/ha)'))
        report_vals.append(
            ('mean_pot_yield1', round(prod1_df['yield_pot_average'].mean(), 2),
             'Mean potential yield 1st crop (t/ha)'))
        report_vals.append(
            ('mean_act_yield1', round(prod1_df['yield_act_average'].mean(), 2),
             'Mean actual yield 1st crop (t/ha)'))

        prod2_dict = {
            'biomass_pot_2': 'biomass_pot',
            'yield_act_2': 'yield_act',
            'yield_pot_2': 'yield_pot'
        }

        prod2_df = make_statistics(out_folder=simout_path,
                                   par_fn_List=['????_' + x for x in list(prod2_dict.keys())],
                                   par_name_list=list(prod2_dict.values()),
                                   stat_list=['min', 'mean', 'average', 'max'],
                                   mask_fn=domain_fn, mask_id=1,
                                   weights_fn=weights_fn,
                                   feedback=lambda s: print(s), tr=lambda s: s)

        prod2_df = prod2_df.fillna(0.0)  # fix no crop
        prod2_fn = os.path.join(out_path, 'prod_second_stats.csv')
        save_dataframe_with_comment(fn=prod2_fn, df=prod2_df,
                                    meta='Second crop production: biomass (t/ha), yield (t/ha)')

        report_vals.append(
            ('mean_biomass2', round(prod2_df['biomass_pot_average'].mean(), 2),
             'Mean potential biomass 2nd crop (t/ha)'))
        report_vals.append(
            ('mean_pot_yield2', round(prod2_df['yield_pot_average'].mean(), 2),
             'Mean potential yield 2nd crop (t/ha)'))
        report_vals.append(
            ('mean_act_yield2', round(prod2_df['yield_act_average'].mean(), 2),
             'Mean potential yield 2nd crop (t/ha)'))

        # calculate total productivity and ratios
        prod_df = pd.DataFrame({'year': prod1_df['year'].tolist()})

        if prod2_df.empty:
            prod2_df = prod1_df.copy()* 0.

        prod_df['biomass_pot_average'] = prod1_df['biomass_pot_average'] + prod2_df['biomass_pot_average']
        prod_df['yield_pot_average'] = prod1_df['yield_pot_average'] + prod2_df['yield_pot_average']
        prod_df['yield_act_average'] = prod1_df['yield_act_average'] + prod2_df['yield_act_average']
        prod_df['yield_ratio'] = prod_df['yield_act_average'] / prod_df['yield_pot_average']

        prod_fn = os.path.join(out_path, 'prod_total_stats.csv')
        save_dataframe_with_comment(fn=prod_fn, df=prod_df,
                                    meta='Total production: biomass (t/ha), yield (t/ha), ratio (-)')

        report_vals.append(
            ('mean_act_yield', round(prod_df['yield_act_average'].mean(), 2),
             'Mean total actual yield (t/ha)'))

        report_vals.append(
            ('mean_yield_perc', round(100 * prod_df['yield_ratio'].mean(), 2),
             'Achieved productivity potential (%)'))

        report_vals.append(
            ('mean_water_efficiency', round((prod_df['yield_act_average'].mean()/10000)/(res_df['irr_average'].mean()/1000), 4),
             'Mean water use efficiency (t/m^3)'))


        # salva le statistiche principali
        main_stats_df = pd.DataFrame(report_vals, columns=['var_name', 'value', 'description'])
        stat_fn = os.path.join(out_path, 'main_stats.csv')
        save_dataframe_with_comment(fn=stat_fn, df=main_stats_df, meta='Main statistics')

        return pd.DataFrame(report_vals,columns=['var_name', 'value', 'description'])

    def makeReport(self,simFolder,outfile):
        #set default folder
        outImageFolder = self.makeSubFolder(outfile, suffix='_img')
        outStatFolder = self.makeSubFolder(outfile, suffix='_stat')

        # read idragra file
        idragraFile = os.path.join(simFolder, 'idragra_parameters.txt')
        simPar = self.readIdragraParameters(idragraFile, self.FEEDBACK, self.tr)

        start_irr_doy = simPar['startirrseason']
        end_irr_doy = simPar['endirrseason']

        step_start = simPar['startdate']
        step_end = simPar['enddate']
        step_delta = simPar['deltadate']

        stepname = 'step'
        if simPar['monthlyflag']:
            stepname = 'month'

        # set domain file
        geodataPath = os.path.join(simFolder, simPar['inputpath'])
        domainFile = os.path.join(geodataPath, 'domain.asc')

        areaFile = None
        if os.path.exists(os.path.join(geodataPath, 'shapearea.asc')):
            # only newest version of idragratools generates "cellarea" file
            areaFile = os.path.join(geodataPath, 'shapearea.asc')

        # set sim output path
        outputPath = os.path.join(simFolder,simPar['outputpath'])

        # annual report
        report_contents = ""

        statLabel = ['min', 'average','max']
        #statLabel = ['average']

        self.FEEDBACK.setProgress(0.)

        ### ADD IRRIGATION STATISTICS ###
        self.FEEDBACK.pushInfo(self.tr('Water fluxes processing ...'))

        waterFlux = {
            'prec_tot': self.tr('Precipitation (mm)'),
            'eva_act_agr': self.tr('Actual evaporation during growing season (mm)'),
            'trasp_act_tot': self.tr('Actual transpiration (mm)'),
            'irr_tot': self.tr('Irrigation (mm)'),
            'irr_loss': self.tr('Irrigation losses (mm)'),
            'run_tot':self.tr('Runoff (mm)'),
            'net_flux_gw': self.tr('Net flux to groundwater (mm)'),
            'eff_tot': self.tr('Irrigation efficiency (-)')
            }



        waterFlux_table = self.makeAnnualStats(outputPath,
                                               ['????_' + x for x in list(waterFlux.keys())],
                                               list(waterFlux.values()),
                                               statLabel,
                                               domainFile,
                                               1,
                                               areaFile,
                                               start_day=start_irr_doy,
                                               end_day=end_irr_doy,
                                               step_day=step_start,
                                               start_doy=step_delta
                                               )


        # create water requirements maps
        irrmap_img = self.add_output_map_by_year(outputPath, 'irr_tot', outImageFolder, outfile,
                                    max_val=waterFlux_table['Irrigation (mm)_max'].max(),
                                    min_val=0.0, palette='yellowblue')
                                    #min_val=waterFlux_table['Irrigation (mm)_min'].min())

        lossesmap_img = self.add_output_map_by_year(outputPath, 'irr_loss', outImageFolder, outfile,
                                                 max_val=waterFlux_table['Irrigation losses (mm)_average'].max(),
                                                 min_val=0.0, palette='rainbow')

        effmap_img = self.add_output_map_by_year(outputPath, 'eff_tot', outImageFolder, outfile,
                                                    max_val=1.0,
                                                    min_val=0.0, palette='grays')

        waterFlux_table = self.dataframeToHtml(waterFlux_table.values.tolist(),
                                                    ['year'] + list(waterFlux.values()),
                                                    statLabel,
                                                    ['{:.0f}'] + ['{:.0f}'] * (
                                                                len(list(waterFlux_table.columns)) - 1))


        self.FEEDBACK.setProgress(30.)

        ### ADD WATER PRODUCTIVITY STATISTICS ###

        self.FEEDBACK.pushInfo(self.tr('processing water productivity...'))

        waterProd = {
            'eva_act_agr': self.tr('Cumulative actual evaporation (mm)'),
            'eva_pot_agr': self.tr('Cumulative potential evaporation (mm)'),
            'trasp_act_tot': self.tr('Cumulative actual transpiration (mm)'),
            'trasp_pot_tot': self.tr('Cumulative potential transpiration (mm)'),

        }
        waterProd_table = self.makeAnnualStats(outputPath,
                                              ['????_' + x for x in list(waterProd.keys())],
                                              list(waterProd.values()),
                                              statLabel,
                                              domainFile,
                                              1,
                                              areaFile)
        waterProd_table = self.dataframeToHtml(waterProd_table.values.tolist(),
                                              ['year'] + list(waterProd.values()),
                                              statLabel,
                                              ['{:.0f}'] + ['{:.0f}'] * (
                                                      len(list(waterProd_table.columns)) - 1))

        ### ADD WATER MANAGEMENT STATISTICS ###
        self.FEEDBACK.pushInfo(self.tr('processing water management...'))

        waterMan = {
            'irr_tot': self.tr('Cumulative irrigation (mm)'),
            'irr_loss':self.tr('Irrigation application losses (mm)'),
            'irr_mean':self.tr('Mean irrigation application (mm)'),
            'irr_nr':self.tr('Number of irrigation application (-)')
        }
        waterMan_table = self.makeAnnualStats(outputPath,
                                              ['????_'+x for x in  list(waterMan.keys())],
                                              list(waterMan.values()),
                                              statLabel,
                                              domainFile,
                                              1,
                                              areaFile)
        waterMan_table = self.dataframeToHtml(waterMan_table.values.tolist(),
                                               ['year'] + list(waterMan.values()),
                                               statLabel,
                                               ['{:.0f}'] + ['{:.0f}'] * (
                                                       len(list(waterMan_table.columns)) - 1))



        self.FEEDBACK.setProgress(60.)

        ### ADD PRODUCTION STATISTICS ###
        self.FEEDBACK.pushInfo(self.tr('First crop production processing ...'))

        production1Vars = {
            'biomass_pot_1': self.tr('Potential biomass for the main crop (t/ha)'),
            'yield_act_1': self.tr('Actual yield for the main crop (t/ha)'),
            'yield_pot_1': self.tr('Potential yield for the main crop (t/ha)')
        }

        first_prod_table = self.makeAnnualStats(outputPath,
                                                ['????_'+x for x in  list(production1Vars.keys())],
                                                list(production1Vars.values()),
                                                statLabel,
                                                domainFile,
                                                1,
                                                areaFile)
        max_val = first_prod_table[['Actual yield for the main crop (t/ha)_average', 'Potential yield for the main crop (t/ha)_average']].max().max()

        yield_img =  self.make_yields_compare_map(outputPath, outImageFolder, 0.0, max_val)
        # add yield reduction index
        first_prod_table['ratio'] = (100*(first_prod_table['Actual yield for the main crop (t/ha)_average']-first_prod_table['Potential yield for the main crop (t/ha)_average'])/
                                     first_prod_table['Potential yield for the main crop (t/ha)_average'])

        first_prod_table = self.dataframeToHtml(first_prod_table.values.tolist(),
                                              ['year'] + list(production1Vars.values()),
                                              statLabel,
                                              ['{:.0f}'] + ['{:.2f}'] * (
                                                      len(list(first_prod_table.columns)) - 1))


        ### ADD PRODUCTION STATISTICS ###
        self.FEEDBACK.pushInfo(self.tr('Second crop production processing ...'))

        production2Vars = {
            'biomass_pot_2': self.tr('Potential biomass for the second crop (t/ha)'),
            'yield_act_2': self.tr('Actual yield for the second crop (t/ha)'),
            'yield_pot_2': self.tr('Potential yield for the second crop (t/ha)')
        }

        sec_prod_table = self.makeAnnualStats(outputPath,
                                              ['????_'+x for x in  list(production2Vars.keys())],
                                              list(production2Vars.values()),
                                              statLabel,
                                              domainFile,
                                              1,
                                              areaFile)
        sec_prod_table = self.dataframeToHtml(sec_prod_table.values.tolist(),
                                          ['year'] + list(production2Vars.values()),
                                          statLabel,
                                          ['{:.0f}'] + ['{:.2f}'] * (
                                                  len(list(sec_prod_table.columns)) - 1))


        self.FEEDBACK.setProgress(90.)
        temp_png_rel= ''
        report_contents = self.writeParsToTemplate(None, {
                                                          'wbf_table': waterFlux_table,
                                                          'irrmap_img': irrmap_img,
                                                          'lossesmap_img': lossesmap_img,
                                                          'effmap_img': effmap_img,
                                                          'yield_img': yield_img,
                                                          'wp_table': waterProd_table,
                                                          'wm_table':waterMan_table,
                                                          'fcp_table':first_prod_table,
                                                          'scp_table':sec_prod_table},
                                                    self.annual_template)

        # BUILD MAIN TOC
        mainToc = self.makeToc(report_contents)

        # UNPADE NUMBERING FOR FIGURES AND TABLES
        report_contents = self.update_refnum(report_contents, '[%tbl_num%]')
        report_contents = self.update_refnum(report_contents, '[%img_num%]')


        ### WRITE TO FILE ###
        self.writeParsToTemplate(outfile, {'sub_title': self.tr(' - Irrigation Season results'),
                                      'current_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                      'sim_path':simFolder,
                                      'report_toc': mainToc,
                                      'report_body': report_contents},
                               self.index_template)

        self.FEEDBACK.setProgress(100.)

        return outfile


if __name__ == '__main__':
    from test_conf import *  # should contain "simFolder = 'some/path/to/simulation'"
    import os
    # outpath = os.path.join(simFolder,'reports')
    # if not os.path.exists(outpath): os.makedirs(outpath)
    # outputFile = os.path.join(outpath,'water_productivity.html')
    RB = CompareScenariosReportBuilder()
    #outfile = RB.makeReport(simFolder,outputFile)
    res = RB.make_report_tables(simFolder)
    print(res)
