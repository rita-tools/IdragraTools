import copy
import glob
import math
import os
import random

import numpy as np
import pandas as pd
import re

import matplotlib
from matplotlib.colors import Normalize, LinearSegmentedColormap
from matplotlib.pyplot import cm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from osgeo import ogr

from report.toc_item import TocItem

matplotlib.use('Agg')

from datetime import datetime,date,timedelta

# import as module
from report.my_progress import MyProgress

class ReportBuilder():
    """
       This class represents object to use for report building
    """

    def __init__(self,feedback = None, tr = None):
        """
        Initialize the report builder object
        Parameters:
            feedback = an object that manage messagge and progression (see my_progress for example)
            tr = a function that makes string translation. if None, the same string is returned
        """
        if not feedback:self.FEEDBACK = MyProgress()
        else: self.FEEDBACK = feedback

        if not tr: self.tr = lambda x: x
        else: self.tr = tr

        self.rb_dir = os.path.dirname(__file__)

        self.index_template = os.path.join(self.rb_dir, 'default', 'index_report.html')
        self.sim_template = os.path.join(self.rb_dir, 'default', 'simulation_report.html')

        self.statFun= {'min':np.nanmin,'max':np.nanmax,'mean':np.nanmean,
                       'std':np.nanstd, 'var':np.nanvar,
                       'sum':np.nansum,'median':np.nanmedian,
                       'average':np.average}

        # these properties are for future developments
        self.name = ''
        self.description = ''

        self.NODATA = -9999

    def set_title(self, name):
        """
        Set report name
        """
        self.name = str(name)

    def set_description(self, description):
        """
        Set report description
        """
        self.description = str(description)

    def replace_values_by_list(self, a, oldVals, newVals):
        """
        Replace values contained in val_old with those contained in val_new
        """
        #a_new = np.array(a,copy=True)
        for old,new in zip(oldVals,newVals):
            np.place(a, a == old, new)

        return a

    def maskExtent(self,maskData):
        """
        Get the extent as cells coordinates of a 2d array mask (1-value area)
        """
        nrows,ncols = maskData.shape
        rindex = []
        cindex = []
        for r in range(nrows):
            cindex.append(list(range(ncols)))

        for c in range(ncols):
            rindex.append(list(range(nrows-1,-1,-1)))

        rindex = np.array(rindex)
        cindex = np.array(cindex)

        rindex = np.transpose(rindex)

        rindex_masked = rindex*maskData
        cindex_masked = cindex * maskData

        cmin = np.nanmin(cindex_masked)
        cmax = np.nanmax(cindex_masked)

        rmin = np.nanmin(rindex_masked)
        rmax = np.nanmax(rindex_masked)

        return (cmin,cmax,rmin,rmax)

    def calcExtent(self,cmin,cmax,rmin,rmax,xll_ref,yll_ref,cellsize):
       """
       Calculate extents in geographic projected coordinates from cells coordinates
       """
       xll = xll_ref+cmin*cellsize
       xlr = xll_ref + (cmax +1)* cellsize
       yll = yll_ref+rmin*cellsize
       yur = yll_ref + (rmax+1) * cellsize

       return (xll, xlr, yll, yur)

    def trim_labels(self,labels,trim_num):
        if trim_num>0:
            # trim header labels
            new_labels = []
            for l in labels:
                l = str(l)
                new_label = l
                if len(l)>trim_num: new_label = l[0:trim_num]+'.'
                new_labels.append(new_label)

            labels = new_labels

        return labels

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


    def dataframeToHtml(self, df, header,
                        subHeader=None, formatList=None, tableClass='statistics', oddClass='odd',
                        trim_header=-1, trim_subheader = 4):
        """
        Convert a pandas dataframe to html table
        More advanced respected to simple pandas.DataFrame.to_html method
        """

        header = self.trim_labels(header,trim_header)
        if subHeader: subHeader = self.trim_labels(subHeader,trim_subheader)

        nMains = len(header)
        if subHeader:
            nsubs = len(subHeader)
            subHeader =  subHeader * (nMains - 1)
            nMains = len(subHeader)

        if not formatList:
            formatList = ['{:}'] * nMains

        text = '<table class="' + tableClass + '">\n'
        # add header
        text += '<thead>\n'
        if subHeader:
            text += '<tr>'
            text += '<th rowspan="2">' + header[0] + '</th>' + ('<th colspan="%s">' % nsubs) + (
                        '</th><th colspan="%s">' % nsubs).join(header[1:]) + '</th>'
            text += '</tr><tr>'
            text += '<th>' + '</th><th>'.join(subHeader) + '</th>'
            text += '</tr>\n'
        else:
            text += '<tr>'
            text += '<th>' + '</th><th>'.join([str(x) for x in header]) + '</th>'
            text += '</tr>\n'

        text += '</thead>\n'
        text += '<tbody>\n'
        odd = True
        # print('type df',type(df))
        for v in df:
            # add values
            # print('v',v)

            if odd:
                text += '<tr class="' + oddClass + '">'
                odd = False
            else:
                text += '<tr>'
                odd = True

            record_values = [formatList[i].format(x) for i, x in enumerate(v)]
            for i,r in enumerate(record_values):
                if record_values[i].startswith(str(self.NODATA)): record_values[i] = self.tr('NA')

            text += '\t<td>' + '</td><td>'.join(record_values) + '</td>\n'

            text += '</tr>'

        text += '</tbody>\n'
        text += '</table>\n'

        return text

    def loadASC(self, filename, val_type=int):
        """
        Open and ascii raster file as dictionary
        The header structure should be:
            ncols 4
            nrows 3
            xllcorner 520197.5534
            yllcorner 5018050.0
            cellsize 250.0
            nodata_value -9

        Note that data are stored in numpy 2d array of type val_type
        """

        res = {'ncols': 0, 'nrows': 0, 'xllcorner': 0, 'yllcorner': 0, 'cellsize': 0, 'nodata_value': 0,
               'data': np.array([]),'extent':()}

        if not os.path.exists(filename):
            self.FEEDBACK.reportError(self.tr('Unknown file: %s'%filename))
            return None

        with open(filename) as f:
            for i in range(0, 6):
                line = f.readline()
                toks = line.split()
                k = toks[0].strip().lower()
                v = toks[1].strip()
                #print(filename,k,v)
                res[k] = float(v)

        # floats (left, right, bottom, top), optional
        xll = res['xllcorner']
        xlr = res['xllcorner'] + res['ncols'] * res['cellsize']
        yll = res['yllcorner']
        yur = res['yllcorner'] + res['nrows'] * res['cellsize']

        res['xll'] = xll
        res['xlr'] = xlr
        res['yll'] = yll
        res['yur'] = yur

        res['width'] = xlr - xll
        res['height'] = yur - yll

        res['extent'] = (xll, xlr, yll, yur)

        res['data'] = np.loadtxt(filename, dtype=val_type, skiprows=6)
        res['nodata_value'] = val_type(res['nodata_value'])
        return res

    def readIdragraParameters(self,idragraFile, feedback, tr):
        """
        Read (most of) idragra parameters files
        """
        pars = {}
        rows = []

        try:
            f = open(idragraFile, 'r')
            for l in f:
                l = l.replace('\t', ' ')
                # l = l.replace(' ', '')
                l = l.rstrip('\n')  # remove return carriage
                com = l.find('#')
                if com < 0: com = len(l)

                comment = l[com + 1:]
                l = l[:com]  # remove comment part if exists

                if 'Irrigation method:' in comment:
                    pars['irrmeth_name'] = comment.replace('Irrigation method:', '').strip()
                    pars['irr_eff'] = self.NODATA # for back compatibility

                if 'Irrigation efficiency:' in comment:
                    pars['irr_eff'] = comment.replace('Irrigation efficiency:', '').strip()

                l = l.split('=')
                if len(l) == 2:
                    parName = l[0].lower().strip()
                    l[1] = l[1].strip()
                    # print(parName)
                    if parName == 'inputpath':
                        pars['inputpath'] = l[1]
                    elif parName == 'outputpath':
                        pars['outputpath'] = l[1]
                    elif parName == 'watsourpath':
                        pars['watsourpath'] = l[1]
                    elif parName == 'monthlyflag':
                        if l[1] == 'F':
                            pars['monthlyflag'] = False
                        else:
                            pars['monthlyflag'] = True
                    elif parName == 'capillaryflag':
                        if l[1] == 'F':
                            pars['capillaryflag'] = False
                        else:
                            pars['capillaryflag'] = True
                    elif parName == 'startdate':
                        pars['startdate'] = int(l[1])
                    elif parName == 'enddate':
                        pars['enddate'] = int(l[1])
                    elif parName == 'deltadate':
                        pars['deltadate'] = int(l[1])
                    elif parName == 'startirrseason':
                        pars['startirrseason'] = int(l[1])
                    elif parName == 'endirrseason':
                        pars['endirrseason'] = int(l[1])
                    else:
                        # all the other cases
                        pars[parName] = l[1]

                if len(l) == 1:
                    # add as table
                    if l[0]: rows.append(l[0].strip())

            # parse table row
            table = {}
            header = []
            for i, r in enumerate(rows):
                toks = r.split(' ')
                if i == 0:
                    header = toks
                    for t in toks:
                        table[t] = []
                else:
                    for c, t in enumerate(toks):
                        if t.lower() == 'endtable': break

                        if t == '*':
                            table[header[c]].append(np.nan)
                        else:
                            table[header[c]].append(float(t))

            table = pd.DataFrame(table)
            pars['table'] = table

        except Exception as e:
            feedback.reportError(tr('Cannot parse %s because %s') %
                                 (idragraFile, str(e)), True)
        finally:
            if f: f.close()

        return pars

    def readWaterSources(self,wat_src_root,
                         wat_src_fn = 'watsources.txt',
                         mon_src_fn = 'monit_sources_i.txt',
                         by_months = True,
                         start_step = 1,end_step = 366,delta_step = 366):

        res = pd.DataFrame({'yr':[]}) # empty res

        wat_src_path = os.path.join(wat_src_root, wat_src_fn)
        mon_src_path = os.path.join(wat_src_root, mon_src_fn)

        # exit if files are missing
        if not (os.path.exists(wat_src_path) and os.path.exists(mon_src_path)): return res

        # watsources.txt contains the list of water sources for each irrigation uni
        # DISTR_ID	SOURCE_CODE	SOURCE_TYPE	FLOW_RATIO
        #    1	      1	             1   	0.5
        wat_src_df = pd.read_table(wat_src_path)

        # monit_sources_i.txt contains the daily delivered discharges at each irrigation unit
        # 1
        # 0.36
        # 01/01/2020 -> 31/12/2022
        #     0.000
        #     0.000
        #     [...]
        # read first line with irrigation district ids
        mon_src_ids = []
        mon_src_q_nom = []
        start_day = None
        end_day = None
        with open(mon_src_path, "r") as f:
            # read first line to get the list of monitored sources
            toks = f.readline().split(' ')
            mon_src_ids = [str(x.strip()) for x in toks]
            # read the second libe to get the list of nominal discharges
            toks = f.readline().split(' ')
            mon_src_q_nom = [float(x) for x in toks]
            # read the third line to get period (start and end days)
            toks = f.readline().split(' -> ')
            start_day = datetime.strptime(toks[0].strip(), '%d/%m/%Y')
            end_day = datetime.strptime(toks[1].strip(), '%d/%m/%Y')

        # read all dataset
        mon_src_df = pd.read_table(mon_src_path, names=mon_src_ids, skiprows=3)

        # add time columns
        mon_src_df['date'] = pd.date_range(start_day, end_day, freq='d')
        mon_src_df['year'] = pd.DatetimeIndex(mon_src_df['date']).year
        mon_src_df['month'] = pd.DatetimeIndex(mon_src_df['date']).month
        mon_src_df['doy'] = pd.DatetimeIndex(mon_src_df['date']).dayofyear
        mon_src_df['step'] = 0

        # add step codes
        step_doys = list(range(start_step, end_step, delta_step))+[end_step+1]
        for i in range(len(step_doys)-1):
            mon_src_df.loc[(mon_src_df['doy'] >= step_doys[i]) & (mon_src_df['doy'] < step_doys[i+1]),'step'] = i+1 # step ids start from 1

        wat_iu_df = mon_src_df.loc[:, ['year','month','doy','step']]

        # get the list of irrigation units
        iu_list = wat_src_df['DISTR_ID'].unique()
        # calculate the sum of water availabilty for each irrigation units
        for iu in iu_list:
            wat_iu_df[str(iu)] = 0.
            for index, row in wat_src_df.loc[wat_src_df['DISTR_ID'] == iu].iterrows():
                src_id = str(int(row['SOURCE_CODE']))
                frc = row['FLOW_RATIO']
                if src_id in mon_src_ids:
                    wat_iu_df[str(iu)] = wat_iu_df[str(iu)] + 24*3600*mon_src_df[str(src_id)]*frc

        if by_months:
            # make aggregated values by year-months
            res = wat_iu_df.groupby(['year', 'month'],as_index = False).sum()
        else:
            # make aggregated values by steps
            res = wat_iu_df.groupby(['year', 'step'], as_index=False).sum()
            # remove empty steps
            res = res.loc[res['step']>0]

        return res

    def writeParsToTemplate(self,outfile, parsDict, templateName):
        """
        Replace in a template file the contents assigned to a specific key in the provided dictionary
        """
        content = ''
        try:
            templateFileName = templateName
            if not os.path.exists(templateName):
                templateFileName = os.path.join(os.path.dirname(__file__), '..', 'templates', templateName)

            # open template file
            f = open(templateFileName)
            template = f.read()
            f.close()
            # replace value from the dictionary
            for k, v in parsDict.items():
                template = template.replace('[%' + k + '%]', str(v))
            content = template
            # save file
            if outfile:
                f = open(outfile, "w", encoding='UTF8')
                f.write(content)
                f.close()
        except Exception as e:
            self.FEEDBACK.reportError(str(e))

        return content

    def update_refnum(self, content, target = '[%tbl_num%]'):
        start_list = []
        start = 0
        while True:
            start = content.find(target, start)
            if start == -1: break
            start_list.append(start)
            start += len(target)  # use start += 1 to find overlapping matches

        c = len(start_list)
        start_list.reverse()
        for s in start_list:
            content = content[0:s]+str(c)+content[s+len(target):]
            c = c-1

        return content

    def makeSubFolder(self, outfile,suffix='_img'):
        """
        Set the image folder for html output
        """
        # set default folder
        outImageFolder = outfile[:-5] + suffix
        if not os.path.exists(outImageFolder):
            os.mkdir(outImageFolder)
        else:
            # delete all files inside
            files = glob.glob(os.path.join(outImageFolder,'*.*'))
            for f in files:
                try: os.remove(f)
                except: self.FEEDBACK.reportError(self.tr('Unable to remove file %s')%f)

        return outImageFolder

    def makeToc(self,text):
        """
        Make a table of cointents, ToC, from an html string
        """
        searchExp = '<a id="(.*)"><h[0-9]+.*>(.*)</h([0-9]+)></a>'
        result = re.findall(searchExp, text)
        root = TocItem('','')
        for r in result:
            subItem = TocItem(r[0], r[1])
            root.addSubItem(subItem,int(r[2]))

        return root.to_html()

    def makeReport(self,simFolder,outfile):
        """
        Make an html report file with tables and images
        It should be overloaded by inheriting class
        """
        outImageFolder = self.makeSubFolder(outfile)
        # read idragra file
        ### WRITE TO FILE ###
        self.writeParsToTemplate(outfile, {'sub_title': self.tr(' - example'),
                                           'current_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                           'sim_path': simFolder,
                                           'report_toc': 'Insert your table of content here',
                                           'report_body': 'Insert your body content here'},
                            self.index_template)

        self.FEEDBACK.setProgress(100.)

        return outfile

    def add_output_map_by_year(self,outputPath,out_name,outImageFolder,outfile,
                               max_val, min_val,palette='random'):
        # create water requirements maps
        watreq_image = os.path.join(outImageFolder, '%s_by_year_map.png'%out_name)

        if max_val >100: max_val = 100 * round(max_val / 100, 0)
        step = max_val / 5
        values = [min_val] + list(np.linspace(step, max_val, num=5))
        colors = [
            "#{:06x}".format(random.randint(0, 0xFFFFFF))
            for _ in range(6)
        ]
        if palette == 'yellowblue':
            colors = ['#d6d84f', '#b9e28c', '#acc8aa', '#9eadc8', '#5b618a', '#5b507a']
        if palette == 'grays':
            colors = ['white','#e5d0cc', '#bfacb5', '#7f7b82', '#444554', '#172121']
        if palette == 'greens':
            colors = ['white', '#11270b', '#71b340', '#669d31', '#598b2c', '#3c5a14'] # greens
        if palette == 'rainbow':
            colors = ['white', '#d7898b', '#fdbf86', '#ffffbf', '#baddb4', '#6499ba']

        outFileList = glob.glob(os.path.join(outputPath, '????_%s.asc'%out_name))
        outFileList.sort()

        # fig = plt.figure(figsize=(10, 3), constrained_layout=True)
        # fig, axs = plt.subplots(len(outFileList), 1,figsize=(10, 3*len(outFileList)), constrained_layout=True)
        nPlot = len(outFileList)
        nRows = math.ceil(nPlot / 2)
        nCols = 2
        if nPlot == 1: nCols = 1
        # print('nPlot',nPlot,'nRows',nRows,'nCols',nCols)
        fig, axs = plt.subplots(nRows, nCols, figsize=(10, 3.5 * nRows), constrained_layout=True)

        # axs = fig.add_subplot(len(outFileList),1,1)
        f = False
        for i, outFile in enumerate(outFileList):
            basename = os.path.basename(outFile)
            y = basename[0:4]
            valRL = self.loadASC(outFile, float)
            valRL['data'] = np.where(valRL['data'] == valRL['nodata_value'], np.nan, valRL['data'])
            if (i == 0):
                #extent = self.maskExtent(valRL['data'])
                extent = (0, valRL['ncols'], 0, valRL['nrows'])

                print('first',extent)
                extent = self.calcExtent(extent[0], extent[1], extent[2], extent[3], valRL['xllcorner'],
                                         valRL['yllcorner'],
                                         valRL['cellsize'])
                print('second',extent)
            # add map
            if i == nPlot - 1: f = True
            self.addRasterMapToPlotLinear(axs[i], valRL['data'], extent, values, colors, offset=0.1, add_colorbar=f)
            axs[i].set_title(str(y))

        # save to file
        fig.savefig(watreq_image, format='png')
        return os.path.relpath(watreq_image, os.path.dirname(outfile))

    def addRasterMapToPlotLinear(self, ax, map_data, extent, values,colors, offset=0.1, add_colorbar = True):

        thresholds = np.array(values, dtype=float)

        vmin = thresholds.min()
        vmax = thresholds.max()

        # normalize between 0 and 1
        norm_positions = (thresholds - vmin) / (vmax - vmin)
        # force exactly between 0 and 1
        norm_positions[0] = 0.0
        norm_positions[-1] = 1.0

        # create interpolated colormap
        cmap = LinearSegmentedColormap.from_list(
            "custom_interp_cmap",
            list(zip(norm_positions, colors))
        )

        norm = Normalize(vmin=vmin, vmax=vmax)

        # plot
        im = ax.imshow(map_data, extent=extent, cmap=cmap, norm=norm)

        if add_colorbar:
            # add colorbar
            cbar = plt.colorbar(im, ax=ax, fraction=0.05, pad=0.04)
            cbar.set_ticks(thresholds)

        # set axes extent
        xmin = round(extent[0] - offset * (extent[1] - extent[0]))
        xmax = round(extent[1] + offset * (extent[1] - extent[0]))
        ymin = round(extent[2] - offset * (extent[3] - extent[2]))
        ymax = round(extent[3] + offset * (extent[3] - extent[2]))

        # ax.set_xticks(np.arange(xmin, xmax, step=1000))
        # ax.set_yticks(np.arange(ymin, ymax, step=1000))
        ax.set_aspect(1.0)

        # ax.axis('equal')
        # print(xmin,xmax,ymin,ymax)
        ax.set_xlim([xmin, xmax])
        ax.set_ylim([ymin, ymax])

        ax.ticklabel_format(axis='both', style='sci', scilimits=(0, 0))

        return im

    def addRasterMapToPlot(self, ax, map_data, extent, values,lbl_values, offset=0.1):
        handles = []
        labels = []
        colors = []
        if len(values)>0:
            #print('debug values:', min(values),'-',max(values))
            #print(map_data.dtype)
            #print(np.unique(map_data))

            im = ax.imshow(map_data, extent=extent, interpolation='nearest', cmap='tab20',
                           norm=Normalize(min(values), max(values)))
                           #norm=Normalize(0, len(values))) not working


            # credits: https://stackoverflow.com/questions/25482876/how-to-add-legend-to-imshow-in-matplotlib
            #print('debug values:',values)
            # colormap used by imshow
            colors = [im.cmap(im.norm(value)) for value in values]
            #print('debug colors:', colors)
            # create a patch (proxy artist) for every color
            patches = [mpatches.Patch(color=colors[i]) for i in range(len(values))]

            handles = patches
            labels = lbl_values

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

        return handles, labels, colors

    def addVectorMapToPlot(self, ax, vector_data, vect_extent, values, unique_val,
                           offset=0.1, nodata = -9999.,
                           colors=None,patches=None,labels=None):
        # vector_data: a ogr shape object
        # values = QgsVectorLayerUtils.getValues(vector_data, val_fld)
        # values = list(set(values))

        if labels is None: labels = unique_val
        else:
            idx_list = [labels.index(a_val) for a_val in unique_val]
            labels = [labels[idx] for idx in idx_list]


        if colors is None: colors = cm.rainbow(np.linspace(0, 1, len(unique_val)))
        else: colors = [colors[idx] for idx in idx_list]

        # create a patch (proxy artist) for every color
        if patches is None: patches = [mpatches.Patch(color=colors[i]) for i in range(len(unique_val))]
        else: patches = [mpatches.Patch(color=colors[i]) for i in range(len(colors))]

        #patches = [copy.deepcopy(patches[idx]) for idx in idx_list]

        handles = patches

        extent = None

        nfeat = vector_data.GetFeatureCount()

        for f,feat in enumerate(vector_data):
            self.FEEDBACK.setProgress(100.*f/nfeat)
            geom = feat.GetGeometryRef()
            nbrRings = geom.GetGeometryCount()

            for i in range(nbrRings):
                ring = geom.GetGeometryRef(i)
                n_inner_ring = ring.GetGeometryCount()
                for i in range(n_inner_ring):
                    inner_ring = ring.GetGeometryRef(i)
                    x = []
                    y = []
                    for i in range(0, inner_ring.GetPointCount()):
                        # GetPoint returns a tuple not a Geometry
                        pt = inner_ring.GetPoint(i)
                        x.append(pt[0])
                        y.append(pt[1])

                    #x.append(x[0])
                    #y.append(y[0])

                    if not (np.isnan(values[f])):
                        if (values[f] !=nodata) :
                            #print('--> add feature')
                            #print('    x:', x)
                            #print('    y:', y)

                            icol = unique_val.index(values[f])
                            ax.fill(x, y, color=colors[icol])

                            if (f<-1):
                                print('    x:', x)
                                print('    y:', y)
                                print('    colors:', colors[icol])
                            # calculate extent with only visible features
                            feat_extent = geom.GetEnvelope()
                            #print('    extent:', feat_extent)
                            extent = self.getMaxExtent(feat_extent, extent)

        if vect_extent: extent = vect_extent

        # set axes extent
        xmin = round(extent[0] - offset * (extent[1] - extent[0]))
        xmax = round(extent[1] + offset * (extent[1] - extent[0]))
        ymin = round(extent[2] - offset * (extent[3] - extent[2]))
        ymax = round(extent[3] + offset * (extent[3] - extent[2]))

        # ax.set_xticks(np.arange(xmin, xmax, step=1000))
        # ax.set_yticks(np.arange(ymin, ymax, step=1000))
        ax.set_aspect(1.0)

        # ax.axis('equal')
        # print(xmin,xmax,ymin,ymax)
        ax.set_xlim([xmin, xmax])
        ax.set_ylim([ymin, ymax])

        ax.ticklabel_format(axis='both', style='sci', scilimits=(0, 0))
        return handles, labels, colors

    def getMaxExtent(self,ext1,ext2):
        # each extent is a tuple: xmin, xmax, ymin, ymax
        if ext1 and ext2:
            max_ext = (min(ext1[0], ext2[0]),
                       max(ext1[1], ext2[1]),
                       min(ext1[2], ext2[2]),
                       max(ext1[3], ext2[3]))
        elif (not ext1) and ext2:
            max_ext = ext2
        elif ext1 and (not ext2):
            max_ext = ext1
        else:
            max_ext = None

        return max_ext


if __name__ == '__main__':
    from test_conf import *  # should contain "simFolder","outputFile" and other useful variable

    # RB = ReportBuilder()
    # outfile = RB.makeReport(simFolder,outputFile)
    # # print(outfile)
    # maskData = np.array([[np.nan,np.nan,np.nan,np.nan,],
    #             [np.nan,1,1,np.nan],
    #             [np.nan,1,np.nan,np.nan],
    #             [np.nan,1,np.nan,np.nan],
    #             [1,1,1,np.nan]])
    #
    # RB = ReportBuilder()
    # res = RB.maskExtent(maskData)
    #
    # print(maskData)
    #
    # print(res)
    # fileName = r'C:\examples\test_img\test_irrigation_units.html'
    # RB = ReportBuilder()
    # with open(fileName) as f:
    #     lines = f.readlines()
    #
    # text = ''.join(lines)
    # res = RB.makeToc(text)
    # print('res',res)

    # debug read water sources
    RB = ReportBuilder()
    res = RB.readWaterSources(os.path.join(simFolder,'wsources'),
                              by_months = False,start_step = 150,end_step = 240,delta_step = 10)
    print('res', res)


