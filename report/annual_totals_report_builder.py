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
from report.overview_report_builder import OverviewReportBuilder

class AnnualTotalsReportBuilder(OverviewReportBuilder):

    def __init__(self,feedback = None, tr = None):
        super().__init__(feedback, tr)

        self.annual_template = os.path.join(self.rb_dir, 'default', 'annual_report.html')

    def makeBoxPlot(self, outFile, all_data):
        # remove nodata
        all_data = all_data.loc[all_data['category'].notna()]
        all_data = all_data.loc[all_data['value'].notna()]
        # dataToPlot is a dataframe with the following structure:
        # year | category | value

        # get the list of unique year
        yrs = sorted(list(all_data['year'].unique()))
        num_yrs = len(yrs)
        cats = sorted(list(all_data['category'].unique()))
        num_cats = len(cats)
        fig, axs = plt.subplots(num_yrs, 1, figsize=(min(max(0.25*num_cats,6),10),3*num_yrs), constrained_layout=True)

        if len(yrs) > 1: axsList = axs.flat
        else: axsList = [axs]

        for i, ax in enumerate(axsList):
                sub_data = all_data.loc[all_data['year'] == yrs[i],['category','value']]
                data_plot = []
                for cat in cats:
                    data_plot.append(sub_data.loc[sub_data['category'] == cat,:]['value'].tolist())

                # ax.violinplot(data_plot,
                #                   showmeans=False,
                #                   showmedians=True)
                ax.boxplot(data_plot)

                ax.yaxis.grid(True)
                ax.set_xticks([y + 1 for y in range(len(cats))],
                              labels=cats)
                ax.set_xlabel('Category')
                ax.set_ylabel('Volumes (mm)')
                ax.set_title(yrs[i])

        # save to file
        fig.savefig(outFile, format='png')
        plt.close(fig)

    def makeStatByGroup(self,varFN,groupFN,stat_list=['mean','min','max','median','std','sum', 'count']):
        if isinstance(varFN,str): varRL = self.loadASC(varFN)
        else: varRL = varFN

        if isinstance(groupFN, str): groupRL = self.loadASC(groupFN)
        else: groupRL = groupFN

        # make a dataframe
        val_df = pd.DataFrame({'group':groupRL['data'].flatten(),
                      'val':varRL['data'].flatten()})

        # remove any nan values
        val_df = val_df.loc[val_df['val']!= varRL['nodata_value'],:]
        val_df = val_df.loc[val_df['val'].notna(), :]

        res = val_df.groupby(['group'],as_index=False).agg(stat_list)#.reset_index(names=stat_list) aliases
        res.columns = stat_list
        return(res)

    def makeAnnualStats(self,outFolder,parFNList,parName,
                        statList=['min', 'mean', 'average','max'],
                        maskIdFN = 'pathTo/domain.asc',maskId = 1,
                        weightsFN = None):

        if isinstance(maskIdFN,str):
            maskRl = self.loadASC(maskIdFN)
        else:
            maskRl = maskIdFN

        mask_data = np.where(maskRl['data'] == maskRl['nodata_value'], np.nan, maskRl['data'])
        mask_data = np.where(mask_data[:] != maskId, np.nan, mask_data[:] * 0 + 1)

        weights_data = mask_data*maskRl['cellsize']*maskRl['cellsize']

        if weightsFN:
            if isinstance(weightsFN, str):
                weights = self.loadASC(weightsFN)
                weights_data = weights['data']*mask_data
            else:
                weights_data = weightsFN*mask_data

        area_iu = np.nansum(weights_data)
        # setup res table
        res = {'year':[],'month':[],'step':[],'area':[]}

        for i in parName:
            for s in statList: res['%s_%s'%(i,s)]= []

        for i,parFN in enumerate(parFNList):
            # match only if start with four characters
            #print('processing:',parFN)
            outFileList = glob.glob(os.path.join(outFolder, parFN + '.asc'))
            outFileList.sort()
            # reset year list
            res['year']=[]
            res['month']=[]
            res['step']=[]
            res['area']=[]

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
                    if '_step' in os.path.basename(outFile):
                        step = int(nums[1])

                except:
                    self.FEEDBACK.reportError(self.tr('Bad-formatted landuse file name: %s')%outFile,False)

                print(outFile,y,month,step)

                res['year'].append(y)
                res['month'].append(month)
                res['step'].append(step)
                res['area'].append(area_iu)

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
                            # apply weights to calculare averages
                            # remove first all nans
                            filtered_weights_data2 = filtered_weights_data[~np.isnan(filtered_weights_data)]
                            filtered_pars_data2 = filtered_pars_data[~np.isnan(filtered_weights_data)]
                            # print('DEBUG: tot.area:',sum(filtered_weights_data2))
                            #filtered_weights_data = np.nan_to_num(filtered_weights_data,False,0.)
                            aVal = self.statFun[stat](filtered_pars_data2,None,filtered_weights_data2)
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
        else:
            pass

        #print('res',res)

        return pd.DataFrame(res)

    def addFluxChart(self, ax, flows=[25, 0, 60, -10, -20, -5, -15, -10, -40],
                     labels=['', '', '', 'First', 'Second', 'Third', 'Fourth',
                             'Fifth', 'Hurray!'],
                     orientations=[-1, 1, 0, 1, 1, 1, -1, -1, 0],
                     pathlengths=[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25,
                                  0.25],
                     patchlabel="Widget\nA"):

        def add_v_arrow(ax, x,y,l,w_arrow,lim_area,label):
            if abs(l) < lim_area: w_arrow = (abs(l) / lim_area) * w_arrow

            x_start = x
            y_start = y + l
            # flip if negative
            if l < 0: y_start = y

            new_arrow = matplotlib.patches.FancyArrow(x_start, y_start, 0, -l, width=w_arrow,
                                                      length_includes_head=True,
                                                      head_width=w_arrow, head_length=None,
                                                      shape='full', overhang=0, head_starts_at_zero=False,
                                                      facecolor='#acc9ffff', edgecolor='#2f6bdcff')

            ax.add_patch(new_arrow)
            arrow_bbox = new_arrow.get_extents().transformed(ax.transAxes.inverted())

            # add label
            #new_text = ax.text(x, y + 1.1 * abs(l), '%s %s' % (label, int(l)),horizontalalignment='center')
            new_text = ax.text(0.5 * (arrow_bbox.xmin + arrow_bbox.xmax),
                               0.5 * (arrow_bbox.ymin + arrow_bbox.ymax),
                               '%s' % (label), horizontalalignment='center')

            return Bbox.from_extents(x,y,x+w_arrow, y + 1.4 * abs(l))

        ax.axis('off')

        # predict ax dimension
        y_max = max(flows)
        y_min = flows[labels.index('N')]-1000

        # drow control volume
        evap_lay = matplotlib.patches.Rectangle((0, -100), 700, 100, facecolor='#ffcc00ff', edgecolor='black')
        trasp_lay = matplotlib.patches.Rectangle((0, -1000), 700, 900, facecolor='#c87137ff', edgecolor='black')

        ax.add_patch(evap_lay)
        ax.add_patch(trasp_lay)

        evap_bbox = evap_lay.get_extents().transformed(ax.transAxes.inverted())
        trasp_bbox = trasp_lay.get_extents().transformed(ax.transAxes.inverted())

        max_bbox = Bbox.union([evap_bbox,trasp_bbox])
        #print('bbox with control volume:', max_bbox)
        # draw fluxes
        x_offset = 100
        y_offset = 0.05*max([y_max,abs(y_min)])
        y = y_offset
        lim_area = 130

        flow = flows[labels.index('P')]
        ext = add_v_arrow(ax, 100, y, flow, 0.9 * x_offset, lim_area,'%s %s'%('P',int(flow)))
        max_bbox = Bbox.union([max_bbox,ext])

        flow = flows[labels.index('I')]
        ext = add_v_arrow(ax, 200, y, flow, 0.9 * x_offset, lim_area,'%s %s'%('I',int(flow)))
        max_bbox = Bbox.union([max_bbox, ext])

        flow = flows[labels.index('E')]
        ext = add_v_arrow(ax, 300, y, flow, 0.9 * x_offset, lim_area,'%s %s'%('E',int(flow)))
        max_bbox = Bbox.union([max_bbox, ext])

        flow = flows[labels.index('T')]
        ext = add_v_arrow(ax, 400, y, flow, 0.9 * x_offset, lim_area,'%s %s'%('T',int(flow)))
        max_bbox = Bbox.union([max_bbox, ext])

        flow = flows[labels.index('N')]
        ext = add_v_arrow(ax, 400, -1000+flow-y_offset, -flow, 0.9 * x_offset, lim_area, '%s %s'%('N',int(flow)))
        max_bbox = Bbox.union([max_bbox, ext])

        flow = flows[labels.index('R')]
        ext = add_v_arrow(ax, 500, y,flow, 0.9 * x_offset, lim_area, '%s %s'%('R',int(flow)))
        max_bbox = Bbox.union([max_bbox, ext])

        flow = flows[labels.index('L')]
        ext = add_v_arrow(ax, 600, y, flow, 0.9 * x_offset, lim_area, '%s %s'%('L',int(flow)))
        max_bbox = Bbox.union([max_bbox, ext])

        ax.set_xlim([max_bbox.xmin, max_bbox.xmax])
        ax.set_ylim([max_bbox.ymin, max_bbox.ymax])
        ax.set_title(patchlabel)

    def addFluxChart_v1(self, ax, flows=[25, 0, 60, -10, -20, -5, -15, -10, -40],
                     labels=['', '', '', 'First', 'Second', 'Third', 'Fourth',
                             'Fifth', 'Hurray!'],
                     orientations=[-1, 1, 0, 1, 1, 1, -1, -1, 0],
                     pathlengths=[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25,
                                  0.25],
                     patchlabel="Widget\nA"):

        #ax.axis('off')

        # drow control volume
        evap_lay = matplotlib.patches.Rectangle((0, -100), 1000, 100, facecolor='#ffcc00ff', edgecolor='black')
        trasp_lay = matplotlib.patches.Rectangle((0, -1000), 1000, 900, facecolor='#c87137ff', edgecolor='black')

        ax.add_patch(evap_lay)
        ax.add_patch(trasp_lay)

        # draw fluxes
        x_offset = 100
        scale = 10
        x = x_offset
        y = 10

        lim_area = 130
        for flow, label, orient, path_l in zip(flows,labels,orientations,pathlengths):
            #new_arrow = matplotlib.patches.Arrow(x_tail, y_tail, 10, 100)
            print(label,':',flow,'(',orient,')','path:',path_l)
            h_row = flow#/(0.9*x_offset)
            arr_width = 0.9*x_offset
            if abs(h_row)<lim_area:
                arr_width = (abs(h_row)/lim_area)*arr_width

            h_row = h_row#*scale
            x_start = x
            y_start = y+h_row
            if h_row <0: y_start = y

            new_arrow = matplotlib.patches.FancyArrow( x_start, y_start,0,-h_row, width=arr_width,
                                                      length_includes_head=True,
                                                      head_width=arr_width, head_length=None,
                                                      shape='full', overhang=0, head_starts_at_zero=False,
                                                       facecolor='#acc9ffff', edgecolor='#2f6bdcff')

                #FancyArrowPatch((x_tail, y_tail+path_l*1000), (x_tail, y_tail),
                #                                           mutation_scale=100,
                #                                           length_includes_head=True, color="C1")
            ax.add_patch(new_arrow)

            ax.text(x, y+1.1*abs(h_row), '%s\n%s'%(label,int(flow)))

            x = x+x_offset

        ax.set_xlim([-10, 1010])
        ax.set_ylim([-1010, 1000])
        ax.set_title(patchlabel)

    def addFluxChart_OLD(self, ax, flows=[25, 0, 60, -10, -20, -5, -15, -10, -40],
                     labels=['', '', '', 'First', 'Second', 'Third', 'Fourth',
                             'Fifth', 'Hurray!'],
                     orientations=[-1, 1, 0, 1, 1, 1, -1, -1, 0],
                     pathlengths=[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25,
                                  0.25],
                     patchlabel="Widget\nA"):

        ax.axis('off')

        sankey = Sankey(ax=ax, scale=0.01, offset=2, head_angle=160, format='%.0f', unit='', gap=0.1)
        sankey.add(flows=flows, labels=labels, orientations=orientations, pathlengths=pathlengths,
                   patchlabel=patchlabel,edgecolor = 'skyblue', facecolor = 'skyblue')  # Arguments to matplotlib.patches.PathPatch

        # sankey = Sankey(ax=self.ax, flows=flows, labels=labels, orientations=orientations)
        diagrams = sankey.finish()

        diagrams[0].texts[-1].set_color('r')
        diagrams[0].text.set_fontweight('bold')


        # xmin,xmax = ax.get_xlim()
        # ymin, ymax = ax.get_ylim()
        #
        # w = xmax-xmin
        # h = ymax-ymin
        #
        # ax.set_xlim(xmin-0.1*w,xmax+0.1*w)
        # ax.set_ylim(ymin - 0.1 * h, ymax + 0.1 * h)

    def makeFluxPlot(self,outFile, dataToPlot, labels, alias,signs, orientations,pathlengths):
        dataToPlot = dataToPlot.fillna(0.)
        print(dataToPlot.to_string())
        nPlot = len(dataToPlot.index)
        nRows = math.ceil(nPlot/2)
        nCols = 2
        if nPlot==1: nCols=1
        # print('nPlot',nPlot,'nRows',nRows,'nCols',nCols)
        fig, axs = plt.subplots(nRows, nCols, figsize=(10,3.5*nRows))#, constrained_layout=True)
        #fig.canvas.draw() # to calculate extents

        if nPlot > 1:
            axsList = axs.flat
        else:
            axsList = [axs]

        for n in range(nRows * nCols):
            if n<nPlot:
                flows = []
                row = dataToPlot.iloc[[n]]
                for label,sign in zip(labels,signs):
                    #print('row val',float(row[label+'_mean']))
                    flows.append(float(row[label+'_average'])*sign)

                self.addFluxChart(axsList[n],flows,alias,orientations,pathlengths,'year\n%s'%int(row['year']))
            else:
                axsList[n].set_axis_off()

        # save to file
        fig.savefig(outFile, format='png')
        plt.close(fig)

    def makeFluxBars(self,ax, dataToPlot, labels, aliases,signs,bar_w=0.35,timeFld = 'year'):
        nRows = len(dataToPlot.index)
        barList =[]

        pos_flows = np.array([0.]*nRows)
        neg_flows = np.array([0.] * nRows)

        for label, sign, alias in zip(labels, signs,aliases):
            flows = []
            time_step = []
            for n in range(nRows):
                row = dataToPlot.iloc[[n]]
                #print('row val',float(row[label+'_mean']))
                signed_val = float(row[label + '_average'].iloc[0]) * sign
                flows.append(signed_val) #float(ser.iloc[0])
                time_step.append(str(int(row[timeFld].iloc[0])))

            if sign>0:
                bar = ax.bar(range(nRows), flows, bar_w, bottom=pos_flows, label=alias)
                barList.append(bar)
                pos_flows+=np.array(flows)
            else:
                bar = ax.bar(range(nRows), flows, bar_w, bottom=neg_flows, label=alias)
                barList.append(bar)
                neg_flows += np.array(flows)

            # add junction lines
            if bar_w<1.:
                i=0
                while i<(len(time_step)-1):
                    xmin = i+0.5*bar_w
                    xmax = (i+1) - 0.5*bar_w
                    if sign>0:
                        ymin = pos_flows[i]
                        ymax = pos_flows[i + 1]
                    else:
                        ymin = neg_flows[i]
                        ymax = neg_flows[i+1]

                    l = mlines.Line2D([xmin, xmax], [ymin, ymax],color=bar.patches[0].get_facecolor())
                    ax.add_line(l)
                    i+=1

        # customize plot
        ax.hlines(0,0.-bar_w,(nRows-1)+bar_w)
        ax.set_xlim([-bar_w,(nRows-1)+bar_w])

        # draw maximum 20+1 labels
        numTs = len(time_step)
        skip = int(numTs/20)
        skip = max(skip,1)

        new_time_step = deepcopy(time_step)
        for i,ts in enumerate(time_step):
            f1,f2 = divmod(i, skip)
            if f2>0:
                new_time_step[i] =''

        ax.set_xticks(range(nRows))
        ax.set_xticklabels(new_time_step)

        ylim = ax.get_ylim()
        max_ylim = max([abs(y) for y in ylim])
        ax.set_ylim([-max_ylim,max_ylim])
        ax.set_ylabel(self.tr('Volume per unit area (mm)'))

        return barList, aliases


    def makeReport(self,simFolder,outfile):
        #set default folder
        outImageFolder = self.makeSubFolder(outfile, suffix='_img')
        outStatFolder = self.makeSubFolder(outfile, suffix='_stat')

        # read idragra file
        idragraFile = os.path.join(simFolder, 'idragra_parameters.txt')
        simPar = self.readIdragraParameters(idragraFile, self.FEEDBACK, self.tr)

        # read cropcoef file
        cropcoefFile = os.path.join(simFolder, 'cropcoef.txt')
        cropcoefPar = self.readIdragraParameters(cropcoefFile, self.FEEDBACK, self.tr)
        landusePath = os.path.join(simFolder, cropcoefPar['cropinputsfolder'])
        landuseFile = os.path.join(landusePath, 'soil_uses.txt')
        landuse_df = self.parseLanduseFile(landuseFile)
        landuse_df = landuse_df.set_index(['id'])
        landuse_df = landuse_df.rename(columns={'cr_name':'name'})

        # read irrigation methods
        irrmethPath = os.path.join(simFolder, simPar['irrmethpath'])
        irrmethFileList = glob.glob(os.path.join(irrmethPath, '*.txt'))

        irrmethPars = {}
        for irrmethFile in irrmethFileList:
            if os.path.basename(irrmethFile) != 'irrmethods.txt':
                irrmethPars[os.path.basename(irrmethFile)] = self.readIdragraParameters(irrmethFile, self.FEEDBACK,self.tr)

        irrmeth_df = pd.DataFrame(irrmethPars).T
        irrmeth_df['id'] = irrmeth_df['id'].astype(int)
        irrmeth_df = irrmeth_df.set_index(['id'])
        irrmeth_df = irrmeth_df.rename(columns={'irrmeth_name': 'name'})

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

        statLabel = ['min', 'mean', 'average','std','max']

        self.FEEDBACK.setProgress(0.)

        ### ADD WATER FLUXES STATISTICS ###
        self.FEEDBACK.pushInfo(self.tr('Water fluxes processing ...'))

        waterFlux = {
            'prec_tot': self.tr('Cumulative precipitation (mm)'),
            'eva_act_agr': self.tr('Cumulative actual evaporation (mm)'),
            'trasp_act_tot': self.tr('Cumulative actual transpiration (mm)'),
            'irr_tot': self.tr('Cumulative irrigation (mm)'),
            'irr_loss': self.tr('Irrigation application losses (mm)'),
            'run_tot':self.tr('Cumulative runoff (mm)'),
            'net_flux_gw': self.tr('Net flux to groundwater (mm)'),
        }

        waterFlux_table = self.makeAnnualStats(outputPath, ['????_'+x for x in list(waterFlux.keys())],
                                               list(waterFlux.values()),
                                               statLabel,
                                               domainFile,
                                               1,
                                               areaFile)

        out_stat_path = os.path.join(outStatFolder, 'water_flux.xlsx')
        waterFlux_table.to_excel(out_stat_path, index=False)

        temp_png = os.path.join(outImageFolder, 'wat_fluxes.png')
        self.makeFluxPlot(temp_png, waterFlux_table, list(waterFlux.values()),['P','E','T','I','L','R','N'],
                          [1,-1,-1,1,-1,-1,-1], [1, 1, 1, 1, 1, 0, -1],
                          [0.25, 0.25, 0.25, 2., 0.5, 2., 2.])

        temp_png_rel = os.path.relpath(temp_png, os.path.dirname(outfile))

        waterFlux_income_table = self.dataframeToHtml(
            waterFlux_table.loc[:,['year',
                                   'Cumulative precipitation (mm)_min',
                                    'Cumulative precipitation (mm)_mean',
                                    'Cumulative precipitation (mm)_average',
                                    'Cumulative precipitation (mm)_std',
                                    'Cumulative precipitation (mm)_max',
                                    'Cumulative irrigation (mm)_min',
                                    'Cumulative irrigation (mm)_mean',
                                    'Cumulative irrigation (mm)_average',
                                    'Cumulative irrigation (mm)_std',
                                    'Cumulative irrigation (mm)_max',
                                    'Net flux to groundwater (mm)_min',
                                    'Net flux to groundwater (mm)_mean',
                                    'Net flux to groundwater (mm)_average',
                                    'Net flux to groundwater (mm)_std',
                                    'Net flux to groundwater (mm)_max'
                                    ]].values.tolist(),
            ['year'] + ['Cumulative precipitation (mm)',
                            'Cumulative irrigation (mm)',
                            'Net flux to groundwater (mm)'],
            statLabel,
            ['{:.0f}'] + ['{:.0f}'] *15)

        waterFlux_outcome_table = self.dataframeToHtml(
            waterFlux_table.loc[:, ['year',
                                    'Cumulative actual evaporation (mm)_min',
                                    'Cumulative actual evaporation (mm)_mean',
                                    'Cumulative actual evaporation (mm)_average',
                                    'Cumulative actual evaporation (mm)_std',
                                    'Cumulative actual evaporation (mm)_max',
                                    'Cumulative actual transpiration (mm)_min',
                                    'Cumulative actual transpiration (mm)_mean',
                                    'Cumulative actual transpiration (mm)_average',
                                    'Cumulative actual transpiration (mm)_std',
                                    'Cumulative actual transpiration (mm)_max',
                                    'Irrigation application losses (mm)_min',
                                    'Irrigation application losses (mm)_mean',
                                    'Irrigation application losses (mm)_average',
                                    'Irrigation application losses (mm)_std',
                                    'Irrigation application losses (mm)_max',
                                    'Cumulative runoff (mm)_min',
                                    'Cumulative runoff (mm)_mean',
                                    'Cumulative runoff (mm)_average',
                                    'Cumulative runoff (mm)_std',
                                    'Cumulative runoff (mm)_max'
                                    ]].values.tolist(),
            ['year'] + ['Cumulative actual evaporation (mm)',
                        'Cumulative actual transpiration (mm)',
                        'Irrigation application losses (mm)',
                        'Cumulative runoff (mm)'],
            statLabel,
            ['{:.0f}'] + ['{:.0f}'] * 20)

        # waterFlux_table = self.dataframeToHtml(
        #     waterFlux_table.loc[:, ~waterFlux_table.columns.isin(['area', 'irr_vol_m3'])].values.tolist(),
        #     ['year'] + list(waterFlux.values()),
        #     statLabel,
        #     ['{:.0f}'] + ['{:.0f}'] * (
        #             len(list(waterFlux_table.columns)) - 2))
        #
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


        out_stat_path = os.path.join(outStatFolder, 'water_productivity.xlsx')
        waterProd_table.to_excel(out_stat_path, index=False)

        waterProd_table = self.dataframeToHtml(waterProd_table.loc[:,~waterProd_table.columns.isin(['area','irr_vol_m3'])].values.tolist(),
                                              ['year'] + list(waterProd.values()),
                                              statLabel,
                                              ['{:.0f}'] + ['{:.0f}'] * (
                                                      len(list(waterProd_table.columns)) - 2))

        ### ADD WATER MANAGEMENT STATISTICS ###
        self.FEEDBACK.pushInfo(self.tr('processing water management...'))

        waterMan = {
            'irr_tot': self.tr('Cumulative irrigation (mm)'),
            'irr_loss':self.tr('Irrigation application losses (mm)'),
            'irr_mean':self.tr('Mean irrigation application (mm)'),
            'irr_nr':self.tr('Number of irrigation application (-)'),
            'eff_tot': self.tr('Irrigation efficiency (-)')
        }
        waterMan_df = self.makeAnnualStats(outputPath,
                                              ['????_'+x for x in  list(waterMan.keys())],
                                              list(waterMan.values()),
                                              statLabel,
                                              domainFile,
                                              1,
                                              areaFile)

        out_stat_path = os.path.join(outStatFolder, 'water_management.xlsx')
        waterMan_df.to_excel(out_stat_path, index=False)

        waterMan_table = self.dataframeToHtml(waterMan_df.loc[:,~waterMan_df.columns.isin(['area','irr_vol_m3'])].values.tolist(),
                                               ['year'] + list(waterMan.values()),
                                               statLabel,
                                               ['{:.0f}'] + ['{:.0f}'] * (
                                                       len(list(waterMan_df.columns)) - 2-4)
                                                  +['{:.2f}']*4)

        # create water requirements maps
        watreq_image = os.path.join(outImageFolder, 'watreq_by_year_map.png')

        irr_max = waterMan_df['Cumulative irrigation (mm)_average'].max()
        irr_max = 100*round(irr_max/100,0)
        step = irr_max/5
        values = [0.0]+list(np.linspace(step, irr_max, num=5))
        colors = ['white','#d7898b','#fdbf86','#ffffbf','#baddb4','#6499ba']

        outFileList = glob.glob(os.path.join(outputPath, '????_irr_tot.asc'))
        outFileList.sort()

        #fig = plt.figure(figsize=(10, 3), constrained_layout=True)
        #fig, axs = plt.subplots(len(outFileList), 1,figsize=(10, 3*len(outFileList)), constrained_layout=True)
        nPlot = len(outFileList)
        nRows = math.ceil(nPlot / 2)
        nCols = 2
        if nPlot == 1: nCols = 1
        # print('nPlot',nPlot,'nRows',nRows,'nCols',nCols)
        fig, axs = plt.subplots(nRows, nCols, figsize=(10, 3.5 * nRows), constrained_layout=True)

        #axs = fig.add_subplot(len(outFileList),1,1)
        f = False
        for i,outFile in enumerate(outFileList):
            basename = os.path.basename(outFile)
            y = basename[0:4]
            valRL = self.loadASC(outFile, float)
            valRL['data'] = np.where(valRL['data'] == valRL['nodata_value'], np.nan, valRL['data'])
            if (i == 0):
                #extent = self.maskExtent(valRL['data'])
                extent = (0,valRL['ncols'],0,valRL['nrows'])
                extent = self.calcExtent(extent[0], extent[1], extent[2], extent[3], valRL['xllcorner'],
                                         valRL['yllcorner'],
                                         valRL['cellsize'])
            # add map
            if i == nPlot-1: f = True
            self.addRasterMapToPlotLinear(axs[i], valRL['data'], extent, values, colors, offset=0.1, add_colorbar=f)
            axs[i].set_title(str(y))

        # save to file
        fig.savefig(watreq_image, format='png')
        watreq_image = os.path.relpath(watreq_image, os.path.dirname(outfile))

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

        out_stat_path = os.path.join(outStatFolder, 'production_1st.xlsx')
        first_prod_table.to_excel(out_stat_path, index=False)

        first_prod_table = self.dataframeToHtml(first_prod_table.loc[:,~first_prod_table.columns.isin(['area','irr_vol_m3'])].values.tolist(),
                                              ['year'] + list(production1Vars.values()),
                                              statLabel,
                                              ['{:.0f}'] + ['{:.2f}'] * (
                                                      len(list(first_prod_table.columns)) - 2))

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

        out_stat_path = os.path.join(outStatFolder, 'production_2nd.xlsx')
        sec_prod_table.to_excel(out_stat_path, index=False)

        sec_prod_table = self.dataframeToHtml(sec_prod_table.loc[:,~sec_prod_table.columns.isin(['area','irr_vol_m3'])].values.tolist(),
                                          ['year'] + list(production2Vars.values()),
                                          statLabel,
                                          ['{:.0f}'] + ['{:.2f}'] * (
                                                  len(list(sec_prod_table.columns)) - 2))



        ### ADD VOLUME STATISTICS BY SOIL TYPES AND LAND USES ###

        areaFile = os.path.join(geodataPath,'shapearea.asc')
        areaRL = self.loadASC(areaFile,float)
        areaRL['data'] = np.where(areaRL['data'] == areaRL['nodata_value'],np.nan,areaRL['data'])

        soilidFile = os.path.join(geodataPath, 'soilid.asc')
        soilidRL = self.loadASC(soilidFile, int)
        soilidRL['data'] = np.where(soilidRL['data'] == soilidRL['nodata_value'], np.nan, soilidRL['data'])

        soil_stat_table = self.makeStatByGroup(areaRL, soilidRL,['sum'])
        soil_stat_table.columns = ['area']
        soil_area = deepcopy(soil_stat_table)

        soil_stat_table['id'] = soil_stat_table.index
        soil_stat_table = soil_stat_table.drop('area', axis=1)

        soiluseFile = os.path.join(geodataPath, 'soiluse.asc')
        soiluseRL = self.loadASC(soiluseFile, int)

        use_stat_table = self.makeStatByGroup(areaRL, soiluseRL, ['sum'])
        use_stat_table.columns = ['area']
        use_area = deepcopy(use_stat_table)

        use_stat_table['id'] = use_stat_table.index
        use_stat_table = use_stat_table.drop('area', axis=1)
        use_stat_table = pd.merge(use_stat_table, landuse_df.loc[:,['name']], left_index=True, right_index=True, how='outer')

        irrmethFile = os.path.join(geodataPath, 'irr_meth.asc')
        irrmethRL = self.loadASC(irrmethFile, int)
        irrmeth_stat_table = self.makeStatByGroup(areaRL, irrmethRL, ['sum'])
        irrmeth_stat_table.columns = ['area']
        irrmeth_area = deepcopy(irrmeth_stat_table)

        irrmeth_stat_table['id'] = irrmeth_stat_table.index
        irrmeth_stat_table = irrmeth_stat_table.drop('area', axis=1)
        irrmeth_stat_table = pd.merge(irrmeth_stat_table, irrmeth_df.loc[:, ['name']], left_index=True, right_index=True,
                                  how='outer')

        outFileList = glob.glob(os.path.join(outputPath,'????_irr_tot.asc'))
        outFileList.sort()

        soilid_plot_df = pd.DataFrame(columns=['year', 'category', 'value'])
        use_plot_df = pd.DataFrame(columns=['year', 'category', 'value'])
        irrmeth_plot_df = pd.DataFrame(columns=['year', 'category', 'value'])

        for outFile in outFileList:
            basename = os.path.basename(outFile)
            year = basename[0:4]
            valRL = self.loadASC(outFile, float)
            valRL['data'] = np.where(valRL['data'] == valRL['nodata_value'], np.nan, valRL['data'])

            soil_valRL = deepcopy(valRL)

            soilid_plot_df = pd.concat([soilid_plot_df,
                                        pd.DataFrame({
                                            'year': [year] * len(soil_valRL['data'].flatten().tolist()),
                                            'category': soilidRL['data'].flatten().tolist(),
                                            'value': soil_valRL['data'].flatten().tolist()
                                        })
                                        ]
                                       )

            soil_valRL['data'] = 0.001 * soil_valRL['data']*areaRL['data']
            mean_by_soilid = self.makeStatByGroup(soil_valRL, soilidRL,['sum'])#['group',['val']['mean']]
            mean_by_soilid.columns = [year]
            mean_by_soilid[year] = 1000 * mean_by_soilid[year] / soil_area['area']
            # append to area
            soil_stat_table = pd.merge(soil_stat_table, mean_by_soilid, left_index=True, right_index=True,how='outer')


            # do the same also with land uses (update if necessary)
            if os.path.exists(os.path.join(geodataPath,'soiluse_'+year+'.asc')):
                soiluseFile = os.path.join(geodataPath,'soiluse_'+year+'.asc')
                soiluseRL = self.loadASC(soiluseFile, int)
                use_area = self.makeStatByGroup(areaRL, soiluseRL, ['sum'])
                use_area.columns = ['area']

            use_valRL = deepcopy(valRL)

            use_plot_df = pd.concat([use_plot_df,
                                        pd.DataFrame({
                                            'year': [year] * len(use_valRL['data'].flatten().tolist()),
                                            'category': soiluseRL['data'].flatten().tolist(),
                                            'value': use_valRL['data'].flatten().tolist()
                                        })
                                        ]
                                       )

            use_valRL['data'] = 0.001 * use_valRL['data'] * areaRL['data']
            mean_by_soiluse = self.makeStatByGroup(use_valRL, soiluseRL, ['sum'])  # ['group',['val']['mean']]
            mean_by_soiluse.columns = [year]
            mean_by_soiluse[year] = 1000*mean_by_soiluse[year]/use_area['area']
            # append to area
            use_stat_table = pd.merge(use_stat_table, mean_by_soiluse, left_index=True, right_index=True, how='outer')

            # do the same also with land uses (update if necessary)
            if os.path.exists(os.path.join(geodataPath, 'irr_meth_' + year + '.asc')):
                irrmethFile = os.path.join(geodataPath, 'irr_meth_' + year + '.asc')
                irrmethRL = self.loadASC(irrmethFile, int)
                irrmeth_area = self.makeStatByGroup(areaRL, irrmethRL, ['sum'])
                irrmeth_area.columns = ['area']

            irrmeth_valRL = deepcopy(valRL)

            irrmeth_plot_df = pd.concat([irrmeth_plot_df,
                                        pd.DataFrame({
                                            'year': [year] * len(irrmeth_valRL['data'].flatten().tolist()),
                                            'category': irrmethRL['data'].flatten().tolist(),
                                            'value': irrmeth_valRL['data'].flatten().tolist()
                                        })
                                        ]
                                       )

            irrmeth_valRL['data'] = 0.001 * irrmeth_valRL['data'] * areaRL['data']
            mean_by_irrmeth = self.makeStatByGroup(irrmeth_valRL, irrmethRL, ['sum'])  # ['group',['val']['mean']]
            mean_by_irrmeth.columns = [year]
            mean_by_irrmeth[year] = 1000 * mean_by_irrmeth[year] / irrmeth_area['area']
            # append to area
            irrmeth_stat_table = pd.merge(irrmeth_stat_table, mean_by_irrmeth, left_index=True, right_index=True, how='outer')

        # update index
        soil_stat_table['id'] = soil_stat_table.index
        use_stat_table['id'] = use_stat_table.index
        irrmeth_stat_table['id'] = irrmeth_stat_table.index

        # merge soil name
        out_stat_path = os.path.join(outStatFolder, 'soil_stat.xlsx')
        soil_stat_table.to_excel(out_stat_path, index=False)
        out_stat_path = os.path.join(outStatFolder, 'use_stat.xlsx')
        use_stat_table.to_excel(out_stat_path, index=False)
        out_stat_path = os.path.join(outStatFolder, 'irrmeth_stat.xlsx')
        irrmeth_stat_table.to_excel(out_stat_path, index=False)

        soil_stat_table = self.dataframeToHtml(soil_stat_table.values.tolist(),
                                                  list(soil_stat_table.columns),
                                                  None,
                                                  ['{:.0f}'] + ['{:.2f}'] * (
                                                          len(list(soil_stat_table.columns)) - 1))

        # make a plot
        soil_vol_bxp = os.path.join(outImageFolder, 'soil_vol_bxp.png')
        self.makeBoxPlot(soil_vol_bxp, soilid_plot_df)
        soil_vol_bxp = os.path.relpath(soil_vol_bxp, os.path.dirname(outfile))

        use_vol_bxp = os.path.join(outImageFolder, 'use_vol_bxp.png')
        self.makeBoxPlot(use_vol_bxp, use_plot_df)
        use_vol_bxp = os.path.relpath(use_vol_bxp, os.path.dirname(outfile))

        irrmeth_vol_bxp = os.path.join(outImageFolder, 'irrmeth_vol_bxp.png')
        self.makeBoxPlot(irrmeth_vol_bxp, irrmeth_plot_df)
        irrmeth_vol_bxp = os.path.relpath(irrmeth_vol_bxp, os.path.dirname(outfile))

        use_stat_table = use_stat_table.dropna(subset=use_stat_table.columns[2:], how='all')

        use_stat_table = self.dataframeToHtml(use_stat_table.values.tolist(),
                                                  list(use_stat_table.columns),
                                                  None,
                                                  ['{:.0f}','{:}'] + ['{:.2f}'] * (
                                                          len(list(use_stat_table.columns)) - 2))

        irrmeth_stat_table = irrmeth_stat_table.dropna(subset=irrmeth_stat_table.columns[2:], how='all')

        irrmeth_stat_table = self.dataframeToHtml(irrmeth_stat_table.values.tolist(),
                                          list(irrmeth_stat_table.columns),
                                          None,
                                          ['{:.0f}','{:}'] + ['{:.2f}'] * (
                                                  len(list(irrmeth_stat_table.columns)) - 2))


        self.FEEDBACK.setProgress(90.)

        report_contents = self.writeParsToTemplate(None, {'annual_fluxes': temp_png_rel,
                                                          'wbf_table_income': waterFlux_income_table,
                                                          'wbf_table_outcome': waterFlux_outcome_table,
                                                          'wp_table': waterProd_table,
                                                          'wm_table':waterMan_table,
                                                          'wr_map':watreq_image,
                                                          'soil_stat_table':soil_stat_table,
                                                          'soil_vol_bxp':soil_vol_bxp,
                                                          'use_stat_table': use_stat_table,
                                                          'use_vol_bxp':use_vol_bxp,
                                                          'irrmeth_stat_table':irrmeth_stat_table,
                                                          'irrmeth_vol_bxp': irrmeth_vol_bxp,
                                                          'fcp_table':first_prod_table,
                                                          'scp_table':sec_prod_table},
                                                    self.annual_template)

        # BUILD MAIN TOC
        mainToc = self.makeToc(report_contents)

        # UNPADE NUMBERING FOR FIGURES AND TABLES
        report_contents = self.update_refnum(report_contents, '[%tbl_num%]')
        report_contents = self.update_refnum(report_contents, '[%img_num%]')

        ### WRITE TO FILE ###
        self.writeParsToTemplate(outfile, {'sub_title': self.tr(' - Annual results'),
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
    outputFile = os.path.join(outpath,'annual_totals.html')
    RB = AnnualTotalsReportBuilder()
    outfile = RB.makeReport(simFolder,outputFile)
    print(outfile)
