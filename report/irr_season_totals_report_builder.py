import glob
import math
import os
from copy import deepcopy

import numpy as np
import pandas as pd
import re

import matplotlib
from matplotlib.sankey import Sankey

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

class IrrSeasonTotalsReportBuilder(AnnualTotalsReportBuilder):

    def __init__(self,feedback = None, tr = None):
        super().__init__(feedback, tr)

        self.annual_template = os.path.join(self.rb_dir, 'default', 'irr_season_report.html')

    def monthFromDoy(self,doy,year):
        # find the month the doy belongs to
        doy_by_month = [0,31,59,90,120,151,181,212,243,273,304,334,365]
        if divmod(year,4)==0: doy_by_month = [0,31,60,91,121,152,182,213,244,274,305,335,366]
        month = -1 # negative means out of range
        for i in range(0,12):
            l_doy = doy_by_month[i]
            h_doy = doy_by_month[i+1]
            if (doy>l_doy) and (doy<=h_doy):
                month =i+1 # one-based list
                break

        return month


    def stepFromDoy(self, doy, start_doy, step_size):
        # find the step the doy belongs to
        # make a list of doy limits
        step = -1
        doy_by_step = []
        i_step = start_doy
        while (i_step<=366):
            doy_by_step.append(i_step)
            i_step=i_step+step_size

        #TODO: select step
        for i in range(0,len(doy_by_step)-1):
            l_doy = doy_by_step[i]
            h_doy = doy_by_step[i+1]
            if (doy>l_doy) and (doy<=h_doy):
                step =i+1 # one-based list
                break

        return step


    def makeAnnualStats(self,outFolder,parFNList,parName,
                        statList=['min', 'mean', 'average','max'],
                        maskIdFN = 'pathTo/domain.asc',maskId = 1,
                        weightsFN = None,
                        start_day = 1,
                        end_day = 366,
                        step_day = 366,
                        start_doy = 1):

        print('here')

        if isinstance(maskIdFN,str):
            maskRl = self.loadASC(maskIdFN)
        else:
            maskRl = maskIdFN

        mask_data = np.where(maskRl['data'] == maskRl['nodata_value'], np.nan, maskRl['data'])
        mask_data = np.where(mask_data[:] != maskId, np.nan, mask_data[:] * 0 + 1)

        weights_data = mask_data

        if weightsFN:
            if isinstance(weightsFN, str):
                weights = self.loadASC(weightsFN)
                weights_data = weights['data']*mask_data
            else:
                weights_data = weightsFN*mask_data

        # setup res table
        res = {'year':[],'month':[],'step':[]}

        for i in parName:
            for s in statList: res['%s_%s'%(i,s)]= []

        for i,parFN in enumerate(parFNList):
            # match only if start with four characters
            #print('processing:',parFN)
            outFileList = glob.glob(os.path.join(outFolder, parFN + '.asc'))
            if len(outFileList) == 0: continue
            outFileList.sort()
            # reset year list
            res['year']=[]
            res['month']=[]
            res['step']=[]
            #print('outFileList:', outFileList)
            for outFile in outFileList:
                month = 0  # months range from 1 to 12
                step = 0  # always greater than 0

                # get year
                try:
                    nums = re.findall(r'\d+', os.path.basename(outFile))
                    y = int(nums[0])
                    if '_month' in os.path.basename(outFile):
                        month = int(nums[1])
                        s = self.monthFromDoy(start_day, y)
                        e = self.monthFromDoy(end_day, y)
                        print('month s:', s, 'e:', e)
                        if (month<s) or (month>e): continue

                    if '_step' in os.path.basename(outFile):
                        step = int(nums[1])
                        s = self.stepFromDoy(start_day, start_doy, step_day)
                        e = self.stepFromDoy(end_day, start_doy, step_day)
                        print('step s:',s,'e:',e)
                        if (step < s) or (step > e): continue
                except Exception as e:
                    self.FEEDBACK.reportError(self.tr('Bad-formatted landuse file name: %s')%outFile,False)
                    print(e)

                print(outFile,y,month,step)

                res['year'].append(y)
                res['month'].append(month)
                res['step'].append(step)

                # compute stats
                parRl = self.loadASC(outFile, float)
                par_data = np.where(parRl['data'] == parRl['nodata_value'], np.nan, parRl['data'])
                filtered_weights_data = weights_data[~np.isnan(par_data)]
                filtered_pars_data = par_data[~np.isnan(par_data)]

                nan_flag = np.isnan(filtered_pars_data).all()
                for stat in statList:
                    aVal = np.nan
                    if not nan_flag:
                        if stat == 'average':
                            # apply weights to calculate averages
                            aVal = self.statFun[stat](filtered_pars_data,None,filtered_weights_data)
                        else:
                            aVal = self.statFun[stat](filtered_pars_data)

                    res['%s_%s' % (parName[i], stat)].append(aVal)

        #print(res)
        # remove empty month and step
        if len(res['month']) == 0:
            del res['month']
        elif max(res['month'])==0:
            del res['month']
        else:
            pass
        if len(res['step']) == 0:
            del res['step']
        elif max(res['step']) == 0:
            del res['step']

        #print('res',res)
        n_tot = len(res['year'])
        for k,v in res.items():
            if len(v) == 0:
                res[k] = n_tot*[np.nan]

        return pd.DataFrame(res)

    def makeReport(self,simFolder,outfile):
        #set default folder
        outImageFolder = self.makeSubFolder(outfile)

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

        ### ADD WATER FLUXES STATISTICS ###
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
    outpath = os.path.join(simFolder,'reports')
    if not os.path.exists(outpath): os.makedirs(outpath)
    outputFile = os.path.join(outpath,'irrseason_totals.html')
    RB = IrrSeasonTotalsReportBuilder()
    outfile = RB.makeReport(simFolder,outputFile)
    print(outfile)
