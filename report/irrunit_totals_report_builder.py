import copy
import glob
import math
import os

import numpy as np
import pandas as pd
import re

import matplotlib
from osgeo import ogr

from report.toc_item import TocItem

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import cm
from matplotlib.colors import Normalize


from datetime import datetime,timedelta

# import as module
from report.annual_totals_report_builder import AnnualTotalsReportBuilder

class IrrunitTotalsReportBuilder(AnnualTotalsReportBuilder):

    def __init__(self,feedback = None, tr = None):
        super().__init__(feedback, tr)

        self.irrunit_template = os.path.join(self.rb_dir, 'default', 'irrigation_unit_report.html')

    def addMapToPlot(self, ax, map_data, extent, values, offset=0.1):
        im = ax.imshow(map_data, extent=extent, interpolation='nearest', cmap='tab20',
                       norm=Normalize(min(values), max(values)))

        # credits: https://stackoverflow.com/questions/25482876/how-to-add-legend-to-imshow-in-matplotlib
        # colormap used by imshow
        colors = [im.cmap(im.norm(value)) for value in values]
        # create a patch (proxy artist) for every color
        patches = [mpatches.Patch(color=colors[i]) for i in range(len(values))]

        handles = patches
        labels = values

        # set axes extent
        xmin = round(extent[0] - offset * (extent[1]-extent[0]))
        xmax = round(extent[1] + offset * (extent[1]-extent[0]))
        ymin = round(extent[2] - offset * (extent[3]-extent[2]))
        ymax = round(extent[3] + offset * (extent[3]-extent[2]))

        #ax.set_xticks(np.arange(xmin, xmax, step=1000))
        #ax.set_yticks(np.arange(ymin, ymax, step=1000))
        ax.set_aspect(1.0)

        #ax.axis('equal')
        #print(xmin,xmax,ymin,ymax)
        ax.set_xlim([xmin, xmax])
        ax.set_ylim([ymin, ymax])

        ax.ticklabel_format(axis='both', style='sci', scilimits=(0, 0))
        return handles, labels

    def irrUnitsSummary(self, baseFN, mask_rl, values, areaFile = None, featFile = None, outFile= None,
                        colors=None, patches=None,labels=None):
        # TODO: think in another way
        if isinstance(mask_rl, str):
            mask_rl = self.loadASC(mask_rl,int)
            mask_data = np.where(mask_rl['data']==mask_rl['nodata_value'],
                                 np.nan,
                                 mask_rl['data'])
            mask_data = mask_data * 0 + 1
        else:
            #print('irrigation num.',np.nanmax(mask_rl['data']))
            mask_data = mask_rl['data']*0+1

        # search all files that match baseFN
        baseFileList = glob.glob(baseFN)
        #print('baseFileList',baseFileList)
        baseFileList.sort()
        numOfFile = len(baseFileList)
        nplot_col = 2
        nPlot = nplot_col*math.ceil((numOfFile) / nplot_col)
        if nPlot==numOfFile: nPlot=nPlot+1 # give space for legend
        nplot_row = math.ceil(nPlot/nplot_col)

        # always add one-axes for legend
        #if nPlot==1: nplot_col = 3
        #else: nPlot = nPlot+1
        #print('numOfFile',numOfFile,'nPlot',nPlot)
        fig, axs = plt.subplots(nplot_row, nplot_col, figsize=(10, 3 * nPlot/nplot_col), constrained_layout=True)
        #print('axs',axs)

        tableList = []

        i = 0
        for i,ax in enumerate(axs.flat):
            if i<len(baseFileList):
                baseFile=baseFileList[i]
                # extract date time
                fname = os.path.basename(baseFile)
                y = 'general'
                #print('fname: ',fname)
                try:
                    nums = re.findall(r'\d+', fname)
                    y = int(nums[0])
                except:
                    self.FEEDBACK.reportError(self.tr('Unrecognized year from file name "%s", considered as general') % fname, False)

                base_rl = self.loadASC(baseFile, float)
                base_data = np.where(base_rl['data']==base_rl['nodata_value'],np.nan,base_rl['data'])

                if (i==0):
                    # set area_data
                    area_data = mask_data * base_rl['cellsize'] * base_rl['cellsize']
                    if areaFile:
                        #print('areaFile:',areaFile)
                        area_rl = self.loadASC(areaFile, int)
                        area_data = np.where(area_rl['data'] == area_rl['nodata_value'], np.nan, area_rl['data'])

                masked_data = base_data*mask_data
                filtered_area_data = area_data[~np.isnan(masked_data)]
                filtered_data = masked_data[~np.isnan(masked_data)]
                int_filtered_data = filtered_data.astype(int)

                # count
                unique, counts = np.unique(int_filtered_data, return_counts=True)
                #if not all_values: all_values = unique
                #print('unique')
                #print(unique)
                # get total area
                tot_area = np.bincount(int_filtered_data,
                                       weights=filtered_area_data)
                #print('tot_area before filter')
                #print(tot_area)
                # note that bincount always returns an array of length np.amax(int_filtered_data)+1.
                # select only the values available in the map
                tot_area = tot_area[unique]
                #print('tot_area after filter')
                #print(tot_area)

                res = pd.DataFrame({y: tot_area}, index=unique)
                tableList.append(res)

                # add map to the figure
                #handles, labels = self.addMapToPlot(ax, filtered_data, extent,values)
                if not featFile:
                    values = np.unique(masked_data.ravel()).tolist()
                    values = [int(x) for x in values if not np.isnan(x)]
                    #print('debug values:',values)
                    im_values = range(len(values))
                    # values = values[~np.isnan(values)] # remove nan from list
                    if (base_rl['nodata_value'] in values): values.remove(base_rl['nodata_value'])

                    # save to file

                    # labels = ['{:.0f}'.format(x) for x in values]
                    masked_data = self.replace_values_by_list(masked_data, values, im_values)

                    #print('not featFile', ax)
                    if (i==0):
                        extent = self.maskExtent(mask_data)
                        extent = self.calcExtent(extent[0], extent[1], extent[2], extent[3], mask_rl['xllcorner'],
                                                 mask_rl['yllcorner'],
                                                 mask_rl['cellsize'])
                    handles, labels, colors = self.addRasterMapToPlot(ax, masked_data, extent, im_values,values)
                else:
                    # load geometries vector file
                    inDataSource = ogr.Open(featFile)
                    if not inDataSource: return  # exit if file not loaded

                    domain_rl = inDataSource.GetLayer(0)
                    #extent = domain_rl.GetExtent()
                    extent = None # calculate extent from plotted polygons
                    #print('masked_data',masked_data)
                    #print('y: %s'%str(y),'masked data n.:',masked_data[~np.isnan(masked_data)])
                    #print('ax',ax)

                    handles, labels, colors = self.addVectorMapToPlot(ax, domain_rl, extent, masked_data,
                                                                      unique.tolist(),0.1,-9999,
                                                                      colors=colors, patches=patches,labels=labels)
                #print('ax title', ax)
                ax.set_title(str(y))
                #print('labels', labels)
            else:
                ax.axis('off')

        n_items = len(handles)
        n_cols = math.ceil(n_items / 10)
        ax.legend(handles, labels,ncol=n_cols, loc='center')# loc=7,

        # join dataframe to only one
        newDf = pd.concat(tableList, axis=1)

        #print('newDf')
        #print(newDf)

        # save to file
        if outFile: fig.savefig(outFile, format='png')

        plt.close(fig)

        return newDf

    def makeReport(self,simFolder,outfile):
        #set default folder
        outImageFolder = self.makeSubFolder(outfile)

        # read idragra file
        idragraFile = os.path.join(simFolder, 'idragra_parameters.txt')
        simPar = self.readIdragraParameters(idragraFile, self.FEEDBACK, self.tr)

        cropcoefFile = os.path.join(simFolder, 'cropcoef.txt')
        cropcoefPar = self.readIdragraParameters(cropcoefFile, self.FEEDBACK, self.tr)

        # set domain file
        geodataPath = os.path.join(simFolder, simPar['inputpath'])
        domainFile = os.path.join(geodataPath, 'domain.asc')

        featFile = None
        if os.path.exists(os.path.join(geodataPath, 'domain.gpkg')):
            featFile = os.path.join(geodataPath, 'domain.gpkg')

        areaFile = None
        if os.path.exists(os.path.join(geodataPath, 'shapearea.asc')):
            # only newest version of idragratools generates "cellarea" file
            areaFile = os.path.join(geodataPath, 'shapearea.asc')

        # set sim output path
        outputPath = os.path.join(simFolder,simPar['outputpath'])

        self.FEEDBACK.setProgress(0.)
        self.FEEDBACK.pushInfo(self.tr('List irrigation units'))

        irrunitsFile = os.path.join(geodataPath, 'irr_units.asc')
        iuRl = self.loadASC(irrunitsFile,int)
        iu_data = iuRl['data']
        iuList = np.unique(iu_data.ravel()).tolist()
        if iuRl['nodata_value'] in iuList: iuList.remove(iuRl['nodata_value'])
        iuList.sort()

        self.FEEDBACK.pushInfo(str(iuList))

        # read landuse table file
        landusePath = os.path.join(simFolder, cropcoefPar['cropinputsfolder'])

        landuseFile = os.path.join(landusePath, 'soil_uses.txt')
        landusePar = self.parseLanduseFile(landuseFile)
        landusePar.sort_values(by='id', inplace=True)
        landusePar['new_id']= landusePar['id']
        landusePar.set_index('new_id',inplace=True)

        # read irrigation methods files
        irrmethPath = os.path.join(simFolder, simPar['irrmethpath'])
        irrmethFileList = glob.glob(os.path.join(irrmethPath, '*.txt'))

        irrmethPars = {}
        for irrmethFile in irrmethFileList:
            if os.path.basename(irrmethFile) != 'irrmethods.txt':
                irrmethPars[os.path.basename(irrmethFile)] = self.readIdragraParameters(irrmethFile, self.FEEDBACK,
                                                                                        self.tr)

        irrmethPar = {'id': [], 'name': []}
        for k, v in irrmethPars.items():
            irrmethPar['id'].append(int(v['id']))
            irrmethPar['name'].append(v['irrmeth_name'])

        irrmethPar = pd.DataFrame(irrmethPar)
        irrmethPar.sort_values(by='id', inplace=True)
        irrmethPar['new_id'] = irrmethPar['id']
        irrmethPar.set_index('new_id', inplace=True)

        # read irrigation sources (if available)
        mon_irr_vols = self.readWaterSources(os.path.join(simFolder, simPar['watsourpath']),
                                             wat_src_fn='watsources.txt',
                                             mon_src_fn='monit_sources_i.txt',
                                             by_months=simPar['monthlyflag'],
                                             start_step=simPar['startdate'],
                                             end_step=simPar['enddate'],
                                             delta_step=simPar['deltadate'])

        # set general land uses plot options
        lu_colors = cm.rainbow(np.linspace(0, 1, len(landusePar['id'])))
        # create a patch (proxy artist) for every color
        lu_patches = [mpatches.Patch(color=lu_colors[i]) for i in range(len(landusePar['id']))]
        # set labels
        lu_labels = landusePar['id'].to_list()

        # set general irrigation methods plot options
        im_colors = cm.rainbow(np.linspace(0, 1, len(irrmethPar['id'])))
        # create a patch (proxy artist) for every color
        im_patches = [mpatches.Patch(color=im_colors[i]) for i in range(len(irrmethPar['id']))]
        # set labels
        im_labels = irrmethPar['id'].to_list()

        ### PLOT IRRIGATION UNITS MAP

        irrunits_image = os.path.join(outImageFolder, 'all_irr_units.png')
        self.plotCatMap(irrunits_image, irrunitsFile, domainFile,areaFile,featFile)
        irrunits_image = os.path.relpath(irrunits_image, os.path.dirname(outfile))

        report_contents = """
                            <h3>Irrigation units map</h3>
                                <div>
                                    <div class="image_container">
                                        <img src="%s">
                                    </div>
                                </div>
                            """%irrunits_image

        # loop in each irrigation units
        for i,iu in enumerate(iuList):
            self.FEEDBACK.pushInfo(self.tr('Processing irrigation units n.: %s')%(str(iu)))
            selIuRL = copy.deepcopy(iuRl)
            selIuRL['data'] = np.where(selIuRL['data']==iu,1,np.nan)

            ### MAKE LANDUSE STATISTICS
            lu_image = os.path.join(outImageFolder, 'lu_by_year_map_%s.png'%(iu))
            soiluse_table = self.irrUnitsSummary(baseFN=os.path.join(geodataPath,'soiluse*.asc'),
                                                 mask_rl=selIuRL, values=list(landusePar['id']),
                                                 areaFile=os.path.join(geodataPath,'shapearea.asc'),
                                                 featFile=featFile,
                                                 outFile=lu_image,
                                                 colors=lu_colors,patches=lu_patches,labels=lu_labels)
            lu_image = os.path.relpath(lu_image, os.path.dirname(outfile))

            soiluse_table=pd.concat([landusePar,soiluse_table], axis=1)

            soiluse_table.drop(columns=['cr1', 'cr2'], inplace=True) # delete unused column
            soiluse_table.rename(columns={"cr_name": "Land use"},inplace=True) # rename specific column
            soiluse_table.fillna(0,inplace=True) # replace nan with zeros
            soiluse_table['id'] = pd.to_numeric(soiluse_table['id'])
            soiluse_table.sort_values(by='id',inplace=True)
            soiluse_table = soiluse_table.loc[soiluse_table.iloc[:, 2:].sum(axis=1) > 0, :]

            soiluse_table = self.dataframeToHtml(soiluse_table.values.tolist(),
                                                   list(soiluse_table.columns),
                                                   None,
                                                   ['{:.0f}','{:}']+['{:.2f}'] * (len(list(soiluse_table.columns)) -2))

            ### MAKE SOIL STATISTICS

            soilPar1FNList = ['ThetaI_r.asc', 'ThetaI_WP.asc', 'ThetaI_FC.asc', 'ThetaI_sat.asc', 'Ksat_I.asc']
            soilPar2FNList = ['ThetaII_r.asc', 'ThetaII_WP.asc', 'ThetaII_FC.asc', 'ThetaII_sat.asc', 'Ksat_II.asc']

            soilParName = ['Res. (-)', 'WP (-)', 'FC (-)', 'Sat. (-)', 'K sat. (cm/hour)']
            statLabel = ['min', 'mean','average', 'max']

            first_soil_par_table = self.makeGroupedStats(geodataPath,
                                                         soilPar1FNList,
                                                         soilParName,
                                                         statLabel,
                                                         irrunitsFile,
                                                         [iu],
                                                         areaFile)
            first_soil_par_table = self.dataframeToHtml(first_soil_par_table.values.tolist(),
                                                        ['id'] + soilParName,
                                                        statLabel,
                                                        ['{:.0f}'] + ['{:.2f}'] * (
                                                                    len(list(first_soil_par_table.columns)) - 1))

            sec_soil_par_table = self.makeGroupedStats(geodataPath,
                                                       soilPar2FNList,
                                                       soilParName,
                                                       statLabel,
                                                       irrunitsFile,
                                                       [iu],
                                                       areaFile)
            sec_soil_par_table = self.dataframeToHtml(sec_soil_par_table.values.tolist(),
                                                      ['id'] + soilParName,
                                                      statLabel,
                                                      ['{:.0f}'] + ['{:.2f}'] * (
                                                                  len(list(sec_soil_par_table.columns)) - 1))

            soilPar3FNList = ['CapRisePar_b1.asc', 'CapRisePar_b2.asc', 'CapRisePar_b3.asc', 'CapRisePar_b4.asc',
                              'CapRisePar_a3.asc', 'CapRisePar_b1.asc']

            soilParName = ['b1', 'b2', 'b3', 'b4', 'a4', 'a5']
            statLabel = ['min', 'mean', 'max']

            deep_soil_par_table = self.makeGroupedStats(geodataPath,
                                                        soilPar3FNList,
                                                        soilParName,
                                                        statLabel,
                                                        irrunitsFile,
                                                        [iu],
                                                        areaFile)
            deep_soil_par_table = self.dataframeToHtml(deep_soil_par_table.values.tolist(),
                                                      ['id'] + soilParName,
                                                      statLabel,
                                                      ['{:.0f}'] + ['{:.2f}'] * (
                                                                  len(list(deep_soil_par_table.columns)) - 1))

            soilPar4FNList = ['hydr_group.asc', 'main_txtr.asc']

            soilParName = ['HSG', 'Texture']
            statLabel = ['min', 'mean', 'average','max']

            other_soil_par_table = self.makeGroupedStats(geodataPath,
                                                         soilPar4FNList,
                                                         soilParName,
                                                         statLabel,
                                                         irrunitsFile,
                                                         [iu],
                                                         areaFile)
            other_soil_par_table = self.dataframeToHtml(other_soil_par_table.values.tolist(),
                                                        ['id'] + soilParName,
                                                        statLabel,
                                                        ['{:.0f}'] + ['{:.2f}'] * (
                                                                    len(list(other_soil_par_table.columns)) - 1))

            ### MAKE INTERNAL NETWORK EFFICIENCY STATISTICS
            effFNList = ['conv_eff.asc']

            effParName = ['Network Efficiency']
            statLabel = ['min', 'mean', 'average', 'max']

            net_eff_par_df = self.makeGroupedStats(geodataPath,
                                                         effFNList,
                                                         effParName,
                                                         statLabel,
                                                         irrunitsFile,
                                                         [iu],
                                                         areaFile)
            net_eff_par_table = self.dataframeToHtml(net_eff_par_df.values.tolist(),
                                                        ['id'] + effParName,
                                                        statLabel,
                                                        ['{:.0f}'] + ['{:.2f}'] * (
                                                                len(list(net_eff_par_df.columns)) - 1))

            ### MAKE IRRIGATION METHOD STATISTICS
            im_image = os.path.join(outImageFolder, 'im_by_year_map_%s.png'%(iu))
            irrmeth_table = self.irrUnitsSummary(baseFN=os.path.join(geodataPath,'irr_meth*.asc'),
                                                 mask_rl=selIuRL, values=list(irrmethPar['id']),
                                                 areaFile=os.path.join(geodataPath, 'shapearea.asc'),
                                                 featFile=featFile,
                                                 outFile=im_image,
                                                 colors=im_colors,patches=im_patches,labels=im_labels)
            im_image = os.path.relpath(im_image, os.path.dirname(outfile))

            irrmeth_table=pd.concat([irrmethPar,irrmeth_table], axis=1)
            irrmeth_table.fillna(0,inplace=True) # replace nan with zeros
            irrmeth_table['id'] = pd.to_numeric(irrmeth_table['id'])
            irrmeth_table.sort_values(by='id',inplace=True)
            irrmeth_table = irrmeth_table.loc[irrmeth_table.iloc[:, 2:].sum(axis=1)>0,:]

            irrmeth_table = self.dataframeToHtml(irrmeth_table.values.tolist(),
                                                   list(irrmeth_table.columns),
                                                   None,
                                                   ['{:.0f}','{:}']+['{:.2f}'] * (len(list(irrmeth_table.columns)) -2))

            ### ADD WATER FLUXES STATISTICS ###
            self.FEEDBACK.pushInfo(self.tr('Water fluxes processing ...'))

            waterFlux = {
                'prec_tot': self.tr('Cumulative precipitation (mm)'),
                'irr_tot': self.tr('Cumulative irrigation (mm)'),
                'irr_loss': self.tr('Irrigation application losses (mm)'),
                'eva_act_agr': self.tr('Cumulative actual evaporation (mm)'),
                'trasp_act_tot': self.tr('Cumulative actual transpiration (mm)'),
                'run_tot': self.tr('Cumulative runoff (mm)'),
                'net_flux_gw': self.tr('Net flux to groundwater (mm)')
            }

            waterFlux_table = self.makeAnnualStats(outputPath, ['????_' + x for x in list(waterFlux.keys())],
                                                   list(waterFlux.values()),
                                                   statLabel,
                                                   selIuRL,
                                                   1,
                                                   areaFile)

            years = waterFlux_table['year'].to_list()

            # make flux bar plot for each year
            temp_png = os.path.join(outImageFolder, 'wat_fluxes_%s.png'%(iu))
            fig, ax = plt.subplots(figsize=(10, 3), constrained_layout=True)
            patches, labels = self.makeFluxBars(ax, waterFlux_table, list(waterFlux.values()),
                                  ['P', 'I', 'L', 'E', 'T', 'R', 'N'],
                                  [1, 1, -1, -1, -1, -1, -1])

            fig.legend(patches, labels, loc=7)
            # save to file
            fig.savefig(temp_png, format='png')
            plt.close(fig)

            wat_fluxes_by_year = os.path.relpath(temp_png, os.path.dirname(outfile))

            # waterFlux_table = self.dataframeToHtml(
            #     waterFlux_table.loc[:,~waterFlux_table.columns.isin(['area'])].values.tolist(),
            #                                        ['year'] + list(waterFlux.values()),
            #                                        statLabel,
            #                                        ['{:.0f}'] + ['{:.0f}'] * (
            #                                                len(list(waterFlux_table.columns)) - 1))

            waterFlux_income_table = self.dataframeToHtml(
                waterFlux_table.loc[:, ['year',
                                        'Cumulative precipitation (mm)_min',
                                        'Cumulative precipitation (mm)_mean',
                                        'Cumulative precipitation (mm)_average',
                                        'Cumulative precipitation (mm)_max',

                                        'Cumulative irrigation (mm)_min',
                                        'Cumulative irrigation (mm)_mean',
                                        'Cumulative irrigation (mm)_average',
                                        'Cumulative irrigation (mm)_max',

                                        'Net flux to groundwater (mm)_min',
                                        'Net flux to groundwater (mm)_mean',
                                        'Net flux to groundwater (mm)_average',
                                        'Net flux to groundwater (mm)_max'
                                        ]].values.tolist(),
                ['year'] + ['Cumulative precipitation (mm)',
                            'Cumulative irrigation (mm)',
                            'Net flux to groundwater (mm)'],
                statLabel,
                ['{:.0f}'] + ['{:.0f}'] * 12)

            waterFlux_outcome_table = self.dataframeToHtml(
                waterFlux_table.loc[:, ['year',

                                        'Cumulative actual evaporation (mm)_min',
                                        'Cumulative actual evaporation (mm)_mean',
                                        'Cumulative actual evaporation (mm)_average',
                                        'Cumulative actual evaporation (mm)_max',

                                        'Cumulative actual transpiration (mm)_min',
                                        'Cumulative actual transpiration (mm)_mean',
                                        'Cumulative actual transpiration (mm)_average',
                                        'Cumulative actual transpiration (mm)_max',

                                        'Irrigation application losses (mm)_min',
                                        'Irrigation application losses (mm)_mean',
                                        'Irrigation application losses (mm)_average',
                                        'Irrigation application losses (mm)_max',

                                        'Cumulative runoff (mm)_min',
                                        'Cumulative runoff (mm)_mean',
                                        'Cumulative runoff (mm)_average',
                                        'Cumulative runoff (mm)_max'
                                        ]].values.tolist(),
                ['year'] + ['Cumulative actual evaporation (mm)',
                            'Cumulative actual transpiration (mm)',
                            'Irrigation application losses (mm)',
                            'Cumulative runoff (mm)'],
                statLabel,
                ['{:.0f}'] + ['{:.0f}'] * 16)

            # make flux plot for each period and year
            stepname = 'step'
            if simPar['monthlyflag']:
                stepname = 'month'

            # TODO: note that evaporation is not a standard output so it must be calculated from ET-T

            stepWaterFlux = {
                'prec': self.tr('Precipitation (mm)'),
                'irr': self.tr('Irrigation (mm)'),
                'irr_loss': self.tr('Irrigation application losses (mm)'),
                'et_act': self.tr('Actual evaporation (mm)'),
                'trasp_act': self.tr('Actual transpiration (mm)'),
                'runoff': self.tr('Runoff (mm)'),
                'flux2': self.tr('Flux to groundwater (mm)'),
                'caprise': self.tr('Capillary rise (mm)')
            }

            stepWaterLabel = ['P', 'I', 'L', 'E','T', 'R', 'F', 'C']
            stepWaterSign = [1, 1, -1, -1, -1, -1, -1, 1]

            if simPar['mode']in [0,'0']:
                stepWaterFlux = {
                    'prec': self.tr('Precipitation (mm)'),
                    'irr_distr': self.tr('Irrigation from collective source (mm)'),
                    'irr_privw': self.tr('Irrigation from private wells (mm)'),
                    'irr_loss': self.tr('Irrigation application losses (mm)'),
                    'et_act': self.tr('Actual evaporation (mm)'),
                    'trasp_act': self.tr('Actual transpiration (mm)'),
                    'runoff': self.tr('Runoff (mm)'),
                    'flux2': self.tr('Flux to groundwater (mm)'),
                    'caprise': self.tr('Capillary rise (mm)')
                }
                stepWaterLabel = ['P', 'Ic', 'Ip', 'L', 'E','T', 'R', 'F', 'C']
                stepWaterSign = [1, 1, 1, -1, -1, -1, -1, -1, 1]

            noteString = []
            for label,descr in zip(stepWaterLabel,list(stepWaterFlux.values())):
                noteString.append('%s: %s'%(label,descr))

            noteString = ', '.join(noteString)

            temp_png = os.path.join(outImageFolder, 'wat_fluxes_by_step_%s.png'%(iu))
            fig, axs = plt.subplots(len(years), 1,figsize=(10, 3*len(years)), constrained_layout=True)


            if len(years)>1: axsList = axs.flat
            else: axsList = [axs]

            step_stat_list = []

            for y,ax in zip(years,axsList):
                stepWaterFlux_table = self.makeAnnualStats(outputPath,
                                                           ['%s_%s*_'%(y,stepname) + x for x in list(stepWaterFlux.keys())],
                                                           list(stepWaterFlux.values()),
                                                           ['average'],
                                                           selIuRL,
                                                           1,
                                                           areaFile)
                # sort by step num
                stepWaterFlux_table.sort_values(stepname, inplace = True)




                # calculate E = ET-T
                stepWaterFlux_table['Actual evaporation (mm)_average'] = stepWaterFlux_table['Actual evaporation (mm)_average']\
                                                                         -stepWaterFlux_table['Actual transpiration (mm)_average']

                # adjust percolation (from net to gross)
                stepWaterFlux_table['Flux to groundwater (mm)_average'] = stepWaterFlux_table[
                                                                             'Flux to groundwater (mm)_average'] \
                                                                         + stepWaterFlux_table[
                                                                             'Capillary rise (mm)_average']

                # make flux bar plot for each year
                patches, labels = self.makeFluxBars(ax, stepWaterFlux_table, list(stepWaterFlux.values()),
                                                    stepWaterLabel,
                                                    stepWaterSign,
                                                    bar_w=1.,timeFld=stepname)
                ax.set_title(str(y))

                if simPar['mode'] in [0, '0']:
                    stepWaterFlux_table['irr_vol_m3'] = 0.001 * stepWaterFlux_table['area'] * stepWaterFlux_table[
                        'Irrigation from collective source (mm)_average']
                else:
                    stepWaterFlux_table['irr_vol_m3'] = 0.001 * stepWaterFlux_table['area'] * stepWaterFlux_table[
                        'Irrigation (mm)_average']

                step_stat_list.append(stepWaterFlux_table)

            plt.legend(patches, labels, loc='lower center', bbox_to_anchor=(0.5, -0.3), ncol=len(labels))
            # save to file
            fig.savefig(temp_png, format='png')
            plt.close(fig)

            wat_fluxes_by_step = os.path.relpath(temp_png, os.path.dirname(outfile))

            # add average value from plot
            stepWaterFlux_table = pd.concat(step_stat_list)

            # get only volumes
            stepIrrEstVol_table = stepWaterFlux_table.loc[:, ['year', stepname, 'irr_vol_m3']]

            # consider internal distribution efficiency
            stepIrrEstVol_table['irr_vol_m3'] = stepIrrEstVol_table['irr_vol_m3']/net_eff_par_df.loc[0,'Network Efficiency_average']

            stepWaterFlux_table = self.dataframeToHtml(
                stepWaterFlux_table.loc[:,~stepWaterFlux_table.columns.isin(['area','irr_vol_m3'])].values.tolist(),
                                                  ['year',stepname] + list(stepWaterFlux.values()),
                                                  [],
                                                  ['{:.0f}','{:.0f}'] + ['{:.0f}'] * (
                                                          len(list(stepWaterFlux_table.columns)) - 2))

            ### ADD WATER MANAGEMENT STATISTICS ###
            self.FEEDBACK.pushInfo(self.tr('Water management processing ...'))

            waterMan = {
                'eva_act_agr': self.tr('Cumulative actual evaporation (mm)'),
                'eva_pot_agr': self.tr('Cumulative potential evaporation (mm)'),
                'trasp_act_tot': self.tr('Cumulative actual transpiration (mm)'),
                'trasp_pot_tot': self.tr('Cumulative potential transpiration (mm)'),
                'irr_loss': self.tr('Irrigation application losses (mm)'),
                'irr_mean': self.tr('Mean irrigation application (mm)'),
                'irr_nr': self.tr('Number of irrigation application (-)'),
                'irr_tot': self.tr('Cumulative irrigation (mm)'),
                'eff_tot': self.tr('Irrigation efficiency (-)')
            }
            waterMan_table = self.makeAnnualStats(outputPath, ['????_' + x for x in list(waterMan.keys())],
                                                  list(waterMan.values()),
                                                  statLabel,
                                                  selIuRL,
                                                  1,
                                                  areaFile)
            # waterMan_table = self.dataframeToHtml(waterMan_table.loc[:,~waterMan_table.columns.isin(['area'])].values.tolist(),
            #                                       ['year'] + list(waterMan.values()),
            #                                       statLabel,
            #                                       ['{:.0f}'] + ['{:.0f}'] * (
            #                                               len(list(waterMan_table.columns)) - 1-4)
            #                                       +['{:.2f}']*4)

            waterMan_table = self.dataframeToHtml(
                waterMan_table.loc[:, ['year',

                                        'Cumulative potential evaporation (mm)_min',
                                        'Cumulative potential evaporation (mm)_mean',
                                        'Cumulative potential evaporation (mm)_average',
                                        'Cumulative potential evaporation (mm)_max',

                                        'Cumulative potential transpiration (mm)_min',
                                        'Cumulative potential transpiration (mm)_mean',
                                        'Cumulative potential evaporation (mm)_average',
                                        'Cumulative potential transpiration (mm)_max',

                                        'Irrigation application losses (mm)_min',
                                        'Irrigation application losses (mm)_mean',
                                        'Irrigation application losses (mm)_average',
                                        'Irrigation application losses (mm)_max',

                                        'Mean irrigation application (mm)_min',
                                        'Mean irrigation application (mm)_mean',
                                        'Mean irrigation application (mm)_average',
                                        'Mean irrigation application (mm)_max',

                                        'Number of irrigation application (-)_min',
                                        'Number of irrigation application (-)_mean',
                                        'Number of irrigation application (-)_average',
                                        'Number of irrigation application (-)_max',

                                        'Irrigation efficiency (-)_min',
                                        'Irrigation efficiency (-)_mean',
                                        'Irrigation efficiency (-)_average',
                                        'Irrigation efficiency (-)_max'

                                       ]].values.tolist(),
                ['year'] + ['Cumulative potential evaporation (mm)',
                            'Cumulative potential transpiration (mm)',
                            'Irrigation application losses (mm)',
                            'Mean irrigation application (mm)',
                            'Number of irrigation application (-)',
                            'Irrigation efficiency (-)'],
                statLabel,
                ['{:.0f}'] + ['{:.0f}'] * 6*4)

            # compare to measured dataset
            # if measure dataset exists, extract cumulate values according to the time steps

            if len(mon_irr_vols)>0:
                stepIrrMonVol_table = mon_irr_vols.loc[:, ['year',stepname, str(iu)]]
            else:
                stepIrrMonVol_table = stepIrrEstVol_table.loc[:, ['year', stepname]]
                stepIrrMonVol_table['irr_vol_m3'] = np.nan

            stepVol_table = pd.merge(stepIrrMonVol_table, stepIrrEstVol_table, left_on=['year', stepname],
                                     right_on=['year', stepname], how='left',
                                     suffixes=['_mon','_est'])#.drop('id1', axis=1)

            stepVol_table = self.dataframeToHtml(stepVol_table.values.tolist(),
                                                  ['year','step','Monitored volumes [m^3]','Estimated volumes [m^3]'],
                                                  None,
                                                  ['{:.0f}','{:.0f}','{:,.2f}','{:,.2f}'])

            ### ADD PRODUCTION STATISTICS ###
            self.FEEDBACK.pushInfo(self.tr('First crop production processing ...'))

            production1Vars = {
                'biomass_pot_1': self.tr('Potential biomass for the main crop (t/ha)'),
                'yield_act_1': self.tr('Actual yield for the main crop (t/ha)'),
                'yield_pot_1': self.tr('Potential yield for the main crop (t/ha)')
            }

            first_prod_table = self.makeAnnualStats(outputPath, ['????_' + x for x in list(production1Vars.keys())],
                                                    list(production1Vars.values()),
                                                    statLabel,
                                                    selIuRL,
                                                    1,
                                                    areaFile)
            first_prod_table = self.dataframeToHtml(first_prod_table.loc[:,~first_prod_table.columns.isin(['area'])].values.tolist(),
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

            sec_prod_table = self.makeAnnualStats(outputPath, ['????_' + x for x in list(production2Vars.keys())],
                                                  list(production2Vars.values()),
                                                  statLabel,
                                                  selIuRL,
                                                  1,
                                                  areaFile)
            sec_prod_table = self.dataframeToHtml(sec_prod_table.loc[:,~sec_prod_table.columns.isin(['area'])].values.tolist(),
                                                  ['year'] + list(production2Vars.values()),
                                                  statLabel,
                                                  ['{:.0f}'] + ['{:.2f}'] * (
                                                          len(list(sec_prod_table.columns)) - 1))


            report_contents += self.writeParsToTemplate(None, {'irr_unit_id': iu,
                                                               'lu_image':lu_image,
                                                              'landuse_table': soiluse_table,
                                                              'soil_first_table': first_soil_par_table,
                                                               'soil_second_table': sec_soil_par_table,
                                                               'soil_deep_table': deep_soil_par_table,
                                                               'soil_hydro_table': other_soil_par_table,
                                                               'im_image': im_image,
                                                              'irrmeth_table': irrmeth_table,
                                                               'annual_fluxes': wat_fluxes_by_year,
                                                               'stepname':stepname.capitalize(),
                                                               'step_fluxes':wat_fluxes_by_step,
                                                               'step_fluxes_table':stepWaterFlux_table,
                                                               'step_vol_table': stepVol_table,
                                                               'step_notes':noteString,
                                                               'wbf_income_table': waterFlux_income_table,
                                                               'wbf_outcome_table': waterFlux_outcome_table,
                                                               'wm_table': waterMan_table,
                                                               'fcp_table': first_prod_table,
                                                               'scp_table': sec_prod_table},
                                                       self.irrunit_template)

            self.FEEDBACK.setProgress(100.*(i+1)/len(iuList))

        ### BUILD MAIN TOC
        #mainToc = mainItem.to_html()
        mainToc = self.makeToc(report_contents)

        # UPDADE NUMBERING FOR FIGURES AND TABLES
        report_contents = self.update_refnum(report_contents,'[%tbl_num%]')
        report_contents = self.update_refnum(report_contents, '[%img_num%]')

        ### WRITE TO FILE ###
        self.writeParsToTemplate(outfile, {'sub_title': self.tr(' - Irrigation units results'),
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
    outputFile = os.path.join(outpath,'irrunit_totals.html')
    RB = IrrunitTotalsReportBuilder()
    outfile = RB.makeReport(simFolder,outputFile)
    print(outfile)
