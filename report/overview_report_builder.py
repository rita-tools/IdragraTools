import glob
import os

import numpy as np
import pandas as pd
import re

import matplotlib
from qgis._core import QgsVectorLayer

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import cm
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec
from osgeo import ogr

from datetime import datetime,timedelta
import math
# import as module
from report.report_builder import ReportBuilder

class OverviewReportBuilder(ReportBuilder):

    def __init__(self,feedback = None, tr = None):
        super().__init__(feedback, tr)

        self.overview_template = os.path.join(self.rb_dir, 'default', 'overview_report.html')
        self.weather_station_template = os.path.join(self.rb_dir, 'default', 'weather_station_report.html')
        self.landuse_template = os.path.join(self.rb_dir, 'default', 'landuse_report.html')
        self.irrmeth_template = os.path.join(self.rb_dir, 'default', 'irrmeth_report.html')
        self.soil_template = os.path.join(self.rb_dir, 'default', 'soil_report.html')

        self.listOfVar = ['T_max', 'T_min','P_tot', 'P_tot_cum', 'U_max', 'U_min', 'V_med', 'RG_CORR']
        self.dictOfLabels = {'T_min': self.tr('Min temp. (°C)'), 'T_max': self.tr('Max temp.(°C)'),
                             'P_tot': self.tr('Precipitation (mm)'),
                             'P_tot_cum': self.tr('Cum. Precipitation (mm)'),
                             'U_min': self.tr('Min air humidity (-)'), 'U_max': self.tr('Max air humidity (-)'),
                             'V_med': self.tr('Wind velocity (m/s)'), 'RG_CORR': self.tr('Solar radiation (MJ/m^2/d)')}

    def parseMeteoFile(self, pathToMeteoFile):
        # skip 10 rows
        # sar.dat x32632            y32632
        # 100.dat 520827.026118634 5018562.6834552
        # 200.dat 520315.301608933 5019014.775729

        df = pd.read_csv(pathToMeteoFile, sep='\s* \s*', engine='python', skiprows=10)
        # print(df)
        res = {}
        for index, row in df.iterrows():
            # print(row)
            res[row['sar.dat']] = {'ws_x': row[1], 'ws_y': row[2]}

        return res

    def parseCropFile(self,pathToCropFile):
        # bare soil
        # SowingDate_min	= 1	# minimum sowing date (1-366)
        # SowingDelay_max	= 0	# maximum number of days allowed for sowing after SowingDate_min
        # HarvestDate_max	= 366	# maximum harvest date (1-366)

        # read the first line that contain the name
        with open(pathToCropFile) as f:
            line = f.readline()
            name = line[1:].strip()

        res = self.readIdragraParameters(pathToCropFile,self.FEEDBACK,self.tr)
        res['crop_name']= name
        return res


    def parseLanduseFile(self, pathToLanduseFile):
        # # List of crops to be simulated, columns must be separated by one or more tab characters
        # Cr_ID	Crop1	Crop2	# Comments
        # 1	3.tab	*	# corn monoculture
        # 2	4.tab	2.tab	# wheat and corn alternate
        # 3	1.tab	*	# bare soil
        # endTable
        with open(pathToLanduseFile) as f:
            # parse first row
            isFirst = True
            res = {'id':[],'cr1':[],'cr2':[],'cr_name':[]}
            lines = f.readlines()
            for l in lines:
                if l:
                    l = l.replace('\t', ' ')
                    l = l.rstrip('\n')  # remove return carriage
                    # split by comment
                    com = l.find('#')
                    if com<0: com = len(l)
                    dataStr = l[0:com]
                    commentStr = l[com+1:]
                    if dataStr:
                        if dataStr=='endTable': break

                        toks = dataStr.split(' ')
                        if not isFirst:
                            res['id'].append(int(toks[0]))
                            #print('toks1',toks[1])
                            res['cr1'].append(toks[1])
                            res['cr2'].append(toks[2])
                            res['cr_name'].append(commentStr.strip())
                        else:
                            # do nothing
                            isFirst = False

        return pd.DataFrame(res)

    def parseMeteoDataFile(self, pathToMeteoDataFile):
        # parse header
        # Id stazione: 100, località: weather one
        # 49.5 235.0
        # 01/01/2000 -> 31/12/2000
        # T_max   T_min   P_tot   U_max   U_min   V_med   RG_CORR
        #    15.400    4.500    0.000   77.000   34.000    1.520   10.160
        # ...

        with open(pathToMeteoDataFile) as f:
            # parse first row
            text = f.readline()
            toks = text.split(sep=',')
            # get station id
            toks2 = toks[0].split(sep=':')
            wsId = int(toks2[1].strip())
            # get station name
            toks2 = toks[1].split(sep=':')
            wsName = toks2[1].strip()
            # pass elevation data
            text = f.readline()
            toks = re.split('\s+', text)
            wsAlt = float(toks[1].strip())
            # parse start and end date
            text = f.readline()
            toks = text.split(sep='->')
            startDate = datetime.strptime(toks[0].strip(), '%d/%m/%Y')
            endDate = datetime.strptime(toks[1].strip(), '%d/%m/%Y')

        listOfYears = list(range(startDate.year, endDate.year + 1))

        df = pd.read_csv(pathToMeteoDataFile, sep='\s* \s*', engine='python', skiprows=3)
        df['datetime'] = pd.date_range(startDate, endDate)

        df['year'] = df["datetime"].dt.year
        # df['month'] = df["datetime"].dt.month
        # df['day'] = df["datetime"].dt.day
        df['datetime_leap'] = pd.to_datetime(df["datetime"].dt.strftime('2000-%m-%d'), format='%Y-%m-%d')
        df['doy_leap'] = df["datetime_leap"].dt.dayofyear
        df['P_tot_cum'] = df.groupby(['year'])['P_tot'].cumsum()
        # print('df',df)

        daily_res = {}
        stats_res = {'header': ['year', 'min', 'max', 'median', 'mean', 'sd', 'sum']}
        stats_res['format'] = ['{:.0f}', '{:.2f}', '{:.2f}', '{:.2f}', '{:.2f}', '{:.2f}', '{:.2f}']
        for var in self.listOfVar:
            listOfSeries = []
            listOfFields = []
            stat_rows = []
            for i, y in enumerate(listOfYears):
                # self.FEEDBACK.setProgress(100.0 * (i+1) / len(listOfYears))
                yearSerie = df.loc[df['year'] == y]
                yearSerie.index = yearSerie['doy_leap']
                # print('yearSerie', yearSerie)
                if len(listOfSeries) == 0:
                    listOfSeries.append(yearSerie['doy_leap'])
                    listOfFields.append('doy')

                listOfSeries.append(yearSerie[var])
                listOfFields.append(str(y))

                # make statistics over year
                minVal = yearSerie[var].min()
                maxVal = yearSerie[var].max()
                medVal = yearSerie[var].median()
                meanVal = yearSerie[var].mean()
                sdVal = yearSerie[var].std()
                sumVal = yearSerie[var].sum()
                stat_rows.append([y, minVal, maxVal, medVal, meanVal, sdVal, sumVal])

            stats_res[var] = stat_rows

            meanSerie = df.groupby(df["doy_leap"])[var].mean()

            listOfSeries.append(meanSerie)
            listOfFields.append('average')

            temp = pd.concat(listOfSeries, axis=1)
            # print('temp',temp)

            temp = temp.set_axis(listOfFields, axis=1)
            # res['year']=res.index
            temp.index.name = None
            daily_res[var] = temp

        return {'ws_id': wsId, 'ws_name': wsName, 'ws_alt': wsAlt, 'ws_means': daily_res, 'ws_stats': stats_res}

    def makeOverviewMap(self, fileName, xs, ys, ids, domainFile, featFile = None, offset=0.1,nodata=-9999.):
        #		fig, ax = plt.subplots(1, 2, figsize=(10, 3), constrained_layout=True)

        fig = plt.figure(figsize=(10, 3), constrained_layout=True)

        gs = GridSpec(1, 4, figure=fig)

        ax1 = fig.add_subplot(gs[0, :-1])

        handles = []
        labels = []

        if not featFile:
            rl = self.loadASC(domainFile, val_type=int)
            ext = rl['extent']
            data = rl['data']

            values = np.unique(data.ravel()).tolist()
            if rl['nodata_value'] in values: values.remove(rl['nodata_value'])

            data = np.where(data == rl['nodata_value'], np.nan, data)

            # save to file
            im = ax1.imshow(data, extent=rl['extent'], interpolation='nearest', cmap='gray')
            # credits: https://stackoverflow.com/questions/25482876/how-to-add-legend-to-imshow-in-matplotlib
            # colormap used by imshow
            colors = [im.cmap(im.norm(value)) for value in values]
            # create a patch (proxy artist) for every color
            patches = [mpatches.Patch(color=colors[i]) for i in range(len(values))]

            handles += patches
            labels.append('domain')

        else:
            rl = self.loadASC(domainFile, val_type=int)
            values = rl['data']

            # load geometries vector file
            inDataSource = ogr.Open(featFile)
            if not inDataSource: return  # exit if file not loaded
            domain_lay = inDataSource.GetLayer(0)
            ext = domain_lay.GetExtent() # xmin,xmax,ymin,ymax

            for f, feat in enumerate(domain_lay):
                geom = feat.GetGeometryRef()
                nbrRings = geom.GetGeometryCount()
                for i in range(nbrRings):
                    ring = geom.GetGeometryRef(i)
                    n_inner_ring = ring.GetGeometryCount()
                    for i in range(n_inner_ring):
                        x = []
                        y = []
                        inner_ring = ring.GetGeometryRef(i)
                        for i in range(0, inner_ring.GetPointCount()):
                            # GetPoint returns a tuple not a Geometry
                            pt = inner_ring.GetPoint(i)
                            x.append(pt[0])
                            y.append(pt[1])

                        if values[f] != nodata:
                            plt.plot(x, y, color='black')

        patches = [mpatches.Patch(edgecolor ='black',facecolor ='white', fill= False)]

        handles += patches
        labels.append('domain')

        # ax1.plot([xll,xlr],[yll,yur],'or')
        lay = ax1.scatter(xs, ys, edgecolors='white')
        handles.append(lay)
        # print('handles',handles)
        labels.append(self.tr('Weather stations'))
        for x, y, id in zip(xs, ys, ids):
            ax1.text(x + 10, y + 10, id, fontsize=10,
                     path_effects=[pe.withStroke(linewidth=2, foreground="white")])

        # calculate maximum extent
        xmin = min(xs+[ext[0]])
        xmax = max(xs+[ext[1]])
        ymin = min(ys+[ext[2]])
        ymax = max(ys+[ext[3]])
        # apply offset to extent
        xmean = 0.5 * (xmin+xmax)
        ymean = 0.5 * (ymin+ymax)
        w = xmax-xmin
        h = ymax-ymin

        max_edge = 0.5 * (1 + offset) * max(w, h)

        xmin = xmean - max_edge
        xmax = xmean + max_edge
        ymin = ymean - max_edge
        ymax = ymean + max_edge

        ax1.set_aspect(1.0)

        ax1.set_xlim([xmin, xmax])
        ax1.set_ylim([ymin, ymax])
        ax1.ticklabel_format(axis='both', style='sci', scilimits=(0, 0))

        # plot legend in the secondary axis
        ax2 = fig.add_subplot(gs[0, 3])
        ax2.axis('off')
        ax2.legend(handles, labels)

        # save to file
        fig.savefig(fileName, format='png')
        plt.close(fig)

    def makeDailyPlot(self, outFile, dataToPlot):
        klist = list(dataToPlot.keys())
        kNum = len(klist)
        fig, axs = plt.subplots(4, 2, figsize=(10, 6), constrained_layout=True)

        for i, ax in enumerate(axs.flat):
            if i < kNum:
                mainTitle = klist[i]
                # print('plotting var', klist[i])
                df = dataToPlot[klist[i]]
                colNames = list(df.columns)
                colNames.remove('doy')
                colNames.remove('average')

                colNum = len(colNames)
                # prepare a graduated color list
                colList = cm.get_cmap('gray', colNum + 2)  # +2 to avoid white
                handles = []
                j = 0
                for col in colNames:
                    # print(j,'plotting',col)
                    y = df[col]
                    # if mainTitle == 'P_tot': y = df[col].cumsum()
                    lines, = ax.plot(df['doy'].values, y.values, color=colList(j / colNum), label=str(y))
                    # lines.set_label(str(y))
                    handles.append(lines)
                    j += 1

                if j > 1:  # more than one year
                    lines, = ax.plot(df['doy'].values, df['average'].values, color='red', label=self.tr('Average'))
                    # lines.set_label(self.tr('Average'))
                    handles.append(lines)
                    colNames.append(self.tr('Average'))

                ax.set_title(self.dictOfLabels[mainTitle])
            else:
                # clear axis
                ax.axis('off')
                ax.legend(handles, colNames, ncol=3)

        # save to file
        fig.savefig(outFile, format='png')
        plt.close(fig)

    def makePieChart(self, outFile, sizes, labels, colors=None):
        fig, ax1 = plt.subplots()
        ax1.axis('off')
        ax1.pie(sizes, labels=labels, colors=colors)
        ax1.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        # save to file
        fig.savefig(outFile, format='png')
        plt.close(fig)  # clear memory



    def plotCatMap(self,outfile,mapFile,domainFile,areaFile= None, featFile=None, offset=0.1):
        #
        fig = plt.figure(figsize=(10, 3), constrained_layout=True)
        gs = GridSpec(1, 4, figure=fig)

        # add map
        ax1 = fig.add_subplot(gs[0, 0:2])

        handles = []
        labels = []

        if not featFile:
            # make a map as image
            map_rl = self.loadASC(mapFile, val_type=int)
            if not map_rl: return # exit if file not loaded
            map_data = map_rl['data']
            #print('debug map_data:',np.unique(map_data))

            domain_rl = self.loadASC(domainFile, val_type=int)
            if not domain_rl: return  # exit if file not loaded
            domain_data = domain_rl['data']
            #print('debug domain_data:', np.unique(map_data))

            map_data = np.where(domain_data != 1, map_rl['nodata_value'], map_data) # apply domain mask
            values = np.unique(map_data.ravel()).tolist()
            values = [int(x) for x in values ]
            im_values = range(len(values))
            #values = values[~np.isnan(values)] # remove nan from list
            if (map_rl['nodata_value'] in values): values.remove(map_rl['nodata_value'])

            # save to file

            #labels = ['{:.0f}'.format(x) for x in values]

            map_data = np.where(map_data == map_rl['nodata_value'], np.nan, map_data)

            map_data = self.replace_values_by_list(map_data,values,im_values)

            handles, labels, colors = self.addRasterMapToPlot(ax1, map_data, map_rl['extent'], im_values,values,offset)
        else:
            # make a map based on geometries
            map_rl = self.loadASC(mapFile, val_type=int)
            if not map_rl: return  # exit if file not loaded
            map_data = map_rl['data']

            # load geometries vector file
            inDataSource = ogr.Open(featFile)
            if not inDataSource: return  # exit if file not loaded

            domain_rl = inDataSource.GetLayer(0)
            extent = domain_rl.GetExtent()
            fld_name = os.path.basename(mapFile)[:-4]

            unique_values = np.unique(map_data.ravel()).tolist()
            if (-9999.0 in unique_values): unique_values.remove(-9999.0)
            unique_values.sort()

            #print('map_data',map_data.tolist())

            handles, labels, colors = self.addVectorMapToPlot(ax1, domain_rl,
                                                              extent, map_data.tolist(),
                                                              unique_values,0.1,-9999)


        # add pie chart
        mapStat = self.rasterStat(mapFile, domainFile,areaFile)
        #print('mapFile:',mapFile)
        #print('mapStat:',mapStat)
        ax2 = fig.add_subplot(gs[0, 2])
        ax2.axis('off')
        ax2.pie(mapStat['perc'], labels=None, colors=colors)
        ax2.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

        # add legend
        ax3 = fig.add_subplot(gs[0, 3])
        ax3.axis('off')
        # calc num of cols
        n_items = len(handles)
        n_cols = math.ceil(n_items/10)
        ax3.legend(handles, labels,ncol=n_cols)

        # TODO: fix long legend

        # save to file
        fig.savefig(outfile, format='png')
        plt.close(fig)  # clear memory



    def makeStatsTable(self, dataToPrint, printAsInt=['P_tot']):
        # print('dataToPrint',dataToPrint)
        allInt = ['{:.0f}', '{:.0f}', '{:.0f}', '{:.0f}', '{:.0f}', '{:.0f}', '{:.0f}']
        allFloat = ['{:.0f}', '{:.2f}', '{:.2f}', '{:.2f}', '{:.2f}', '{:.2f}', '{:.2f}']

        text = ''
        kList = list(dataToPrint.keys())
        kList.remove('header')
        kList.remove('format')

        for k in sorted(kList):
            # print('k', k)
            formatList = allFloat
            if k in printAsInt:
                formatList = allInt
            text += '<p class="caption">%s</p>\n' % self.dictOfLabels[k]
            text += self.dataframeToHtml(df=dataToPrint[k], header=dataToPrint['header'], formatList=formatList)

        return text

    def rasterStat(self, baseMapFN, maskMapFN, areaMapFN = None):
        res = pd.DataFrame.from_dict(
            {'id': [], 'count': [], 'area': [],
             'perc': []})

        baseRaster = self.loadASC(baseMapFN, int)
        maskRaster = self.loadASC(maskMapFN, int)

        baseData = baseRaster['data']
        maskData = maskRaster['data']
        areaData = maskRaster['data']*0.+(baseRaster['cellsize']*baseRaster['cellsize'])

        try:
            areaRaster = self.loadASC(areaMapFN, int)
            areaData = areaRaster['data']
        except:
            self.FEEDBACK.reportError(self.tr('Unable to open %s')%areaMapFN,False)

        baseList = list(np.unique(baseData))
        if baseRaster['nodata_value'] in baseList: baseList.remove(baseRaster['nodata_value'])

        countCells = []
        cellsArea = []
        for i in baseList:
            if len(baseData.shape)>1:
                mask = np.where(np.logical_and(baseData[:, :] == i, maskData[:, :] != maskRaster['nodata_value']))
            else:
                mask = np.where(np.logical_and(baseData[:] == i, maskData[:] != maskRaster['nodata_value']))

            #mask = np.where(np.logical_and(baseData == i, maskData != maskRaster['nodata_value']))

            countCells.append(np.count_nonzero(areaData[mask]))
            cellsArea.append(np.sum(areaData[mask]))


        baseList = np.asarray(baseList)
        countCells = np.asarray(countCells)
        cellsArea = np.asarray(cellsArea)

        totArea = sum(cellsArea)
        perc = 100. * cellsArea / totArea

        # print(baseList,countCells,cellsArea,perc)
        res = pd.DataFrame.from_dict(
            {'id': baseList.tolist(), 'count': countCells.tolist(), 'area': cellsArea.tolist(),
             'perc': perc.tolist()})

        return res

    def vectorStat(self, domainFile, group_fld, value_fld):
        res = pd.DataFrame.from_dict(
            {'id': [], 'count': [], 'area': [],
             'perc': []})

        inDataSource = ogr.Open(domainFile)
        if not inDataSource: return res # exit if file not loaded

        # get list of unique values from group_fld
        sql = 'SELECT DISTINCT ' + group_fld + ' FROM domain'
        selection = inDataSource.ExecuteSQL(sql)
        if not selection:
            self.FEEDBACK.reportError(self.tr('Unable to query: %s') % sql)
            return res

        values = []
        for i, feature in enumerate(selection):
            values.append(feature.GetField(0))

        if (-9999.0 in values): values.remove(-9999.0)
        values.sort()

        count_list = []
        area_list = []
        for val in values:
            sql = 'SELECT count(%s) as count_value, sum(%s) as sum_value from domain WHERE %s = %s'%(group_fld,value_fld,group_fld,val)
            selection = inDataSource.ExecuteSQL(sql)
            if not selection:
                self.FEEDBACK.reportError(self.tr('Unable to query: %s') % sql)
                return res

            for feat in selection:
                count_list.append(feat['count_value'])
                area_list.append(feat['sum_value'])

        totArea = sum(np.asarray(area_list))
        perc = 100*np.asarray(area_list)/totArea

        # print(baseList,countCells,cellsArea,perc)
        res = pd.DataFrame.from_dict(
            {'id': values, 'count': count_list, 'area': area_list,
             'perc': perc.tolist()})

        return res

    def makeGroupedStats(self,geodataFolder,parFNList,parName,
                         statList=['min', 'mean','average', 'max'],
                         catFN = 'soilid.asc',catIds=[],
                         weightsFN = None):

        catRL = self.loadASC(os.path.join(geodataFolder,catFN))
        if not catRL: return pd.DataFrame() # exit if file not loaded

        if len(catIds)==0:
            catIds = list(np.unique(catRL['data']))
            if (catRL['nodata_value'] in catIds): catIds.remove(catRL['nodata_value'])

        ids_data = np.where(catRL['data'] == catRL['nodata_value'], np.nan, catRL['data'])

        weights_data = ids_data*0+1

        if weightsFN:
            if isinstance(weightsFN, str):
                weights = self.loadASC(weightsFN)
                weights_data = weights['data'] * weights_data
            else:
                weights_data = weightsFN * weights_data

        # setup res table
        res = {'id':catIds}
        for i in parName:
            for s in statList: res['%s_%s'%(i,s)]= []

        # for i in soilParName:
        #     for s in statLabel: res['2nd %s (%s)'%(i,s)]= []

        for i,parFN in enumerate(parFNList):
            parRl = self.loadASC(os.path.join(geodataFolder, parFN),float)
            par_data = np.where(parRl['data'] == parRl['nodata_value'], np.nan, parRl['data'])

            for sid in catIds:
                filtered_pars_data = np.where(ids_data != sid, np.nan, par_data)
                filtered_weights_data = weights_data[~np.isnan(filtered_pars_data)]
                filtered_pars_data = par_data[~np.isnan(filtered_pars_data)]

                nan_flag = np.isnan(filtered_pars_data).all()
                for stat in statList:
                    aVal = np.nan
                    if not nan_flag:
                        if stat == 'average':
                            # apply weights to calculare averages
                            aVal = self.statFun[stat](filtered_pars_data,None,filtered_weights_data)
                        else:
                            aVal = self.statFun[stat](filtered_pars_data)

                    res['%s_%s' % (parName[i], stat)].append(aVal)

        return pd.DataFrame(res)


    def makeReport(self,simFolder,outfile):
        #set default folder
        outImageFolder = self.makeSubFolder(outfile,suffix='_img')
        outStatFolder = self.makeSubFolder(outfile,suffix='_stat')

        # read idragra file
        idragraFile = os.path.join(simFolder, 'idragra_parameters.txt')
        simPar = self.readIdragraParameters(idragraFile, self.FEEDBACK, self.tr)

        cropcoefFile = os.path.join(simFolder, 'cropcoef.txt')
        cropcoefPar = self.readIdragraParameters(cropcoefFile, self.FEEDBACK, self.tr)

        self.FEEDBACK.setProgress(5.)

        ### PROCESS METEO DATA ###
        self.FEEDBACK.pushInfo(self.tr('Meteo data processing ...'))
        # read weather station list
        ws_contents = ''
        wsDict = self.parseMeteoFile(os.path.join(simFolder, simPar['meteofilename']))

        # do some statistics
        # get meteofolder
        meteoPath = os.path.join(simFolder, simPar['meteopath'])
        geodataPath = os.path.join(simFolder, simPar['inputpath'])
        domainFile = os.path.join(geodataPath, 'domain.asc')

        featFile = None
        if os.path.exists(os.path.join(geodataPath, 'domain.gpkg')):
            featFile = os.path.join(geodataPath, 'domain.gpkg')

        areaFile = None
        if os.path.exists(os.path.join(geodataPath, 'shapearea.asc')):
            # only newest version of idragratools generates "cellarea" file
            areaFile = os.path.join(geodataPath, 'shapearea.asc')

        xs = []
        ys = []
        ids = []
        i = 0
        nOfFile = len(list(wsDict.keys()))
        for f, coord in wsDict.items():
            res = self.parseMeteoDataFile(os.path.join(meteoPath, f))

            xs.append(coord['ws_x'])
            ys.append(coord['ws_y'])
            ids.append(res['ws_id'])

            res['ws_x'] = '{:.2f}'.format(coord['ws_x'])
            res['ws_y'] = '{:.2f}'.format(coord['ws_y'])
            del res['ws_stats']['P_tot_cum']
            res['ws_stats'] = self.makeStatsTable(res['ws_stats'])

            temp_png = os.path.join(outImageFolder, 'daily_plot_%s.png' % res['ws_id'])
            self.makeDailyPlot(temp_png, res['ws_means'])
            temp_png_rel = os.path.relpath(temp_png, os.path.dirname(outfile))
            res[
                'temp_plot'] = temp_png_rel  # os.path.join('.',os.path.basename(outfile),outfile[:-5]+'_img','temp_pie_%s.png'% res['ws_id']) #temp_png
            ws_contents += self.writeParsToTemplate(None, res, self.weather_station_template)
            #self.FEEDBACK.setProgress(100.0 * (i + 1) / nOfFile)
            i += 1

        ws_overview_map = os.path.join(outImageFolder, 'ws_overview_map.png')
        # self.makeOverViewMap(ws_overview_map, xs, ys, ids, domainFile)
        self.makeOverviewMap(ws_overview_map, xs, ys, ids, domainFile,featFile)
        ws_overview_map = os.path.relpath(ws_overview_map, os.path.dirname(outfile))


        self.FEEDBACK.setProgress(20.)

        ### PROCESS LAND USE DATA ###
        self.FEEDBACK.pushInfo(self.tr('Land use data processing ...'))
        landusePath = os.path.join(simFolder, cropcoefPar['cropinputsfolder'])
        cropsPath = os.path.join(landusePath, 'crop_parameters')
        # read crops parameters
        cropFileList = glob.glob(os.path.join(cropsPath, '*.tab'))
        # print('fileList',fileList)
        cropPars = {}
        for cropFile in cropFileList:
            cropPars[os.path.basename(cropFile)] = self.parseCropFile(cropFile)

        # read landuse table file
        landuseFile = os.path.join(landusePath, 'soil_uses.txt')
        res = self.parseLanduseFile(landuseFile)

        # make a list of used crop
        unique_crop = pd.unique(res[['cr1', 'cr2']].values.ravel('K')).tolist()
        unique_crop.sort()

        cropsTable = {'name':[], 'max_lai':[], 'max_kcb':[], 'max_sr':[], 'max_hc':[]}
        # GDD	Kcb LAI	Hc	Sr
        for crop in unique_crop:
            if crop != '*':
                cropsTable['name'].append(cropPars[crop]['crop_name'])
                cropsTable['max_lai'].append(cropPars[crop]['table']['LAI'].max())
                cropsTable['max_kcb'].append(cropPars[crop]['table']['Kcb'].max())
                cropsTable['max_sr'].append(cropPars[crop]['table']['Sr'].max())
                cropsTable['max_hc'].append(cropPars[crop]['table']['Hc'].max())

        cropsTable = pd.DataFrame(cropsTable)
        out_stat_path = os.path.join(outStatFolder, 'crops_table.xlsx')
        cropsTable.to_excel(out_stat_path, index=False)
        crop_list_table = self.dataframeToHtml(cropsTable.values.tolist(),
                                          ['name','LAI (m^2/m^2)','Kcb (-)','root depth (m)','plant height (m)'],
                                          None,
                                          ['{:}', '{:.2f}', '{:.2f}', '{:.2f}', '{:.2f}'])

        # replace file name with crop name before printing
        cropMaptable = {'*':'*'}
        for k,v in cropPars.items():
            cropMaptable[k] =v['crop_name']

        res['cr1'] = res['cr1'].map(cropMaptable)
        res['cr2'] = res['cr2'].map(cropMaptable)


        out_stat_path = os.path.join(outStatFolder, 'lu_list_table.xlsx')
        res.to_excel(out_stat_path, index=False)

        lu_list_table = self.dataframeToHtml(res.values.tolist(),
                                        ['id', 'first crop', 'second crop', 'name'],
                                        None,
                                        ['{:}', '{:}', '{:}', '{:}'])

        lu_contents = ''
        # search for land use maps
        luFileList = glob.glob(os.path.join(geodataPath, 'soiluse*.asc'))
        # print('fileList',fileList)

        nOfFiles = len(luFileList)
        for luFile in luFileList:
            # parse year from soiluse_2005.asc
            fname = os.path.basename(luFile)
            # extract date time
            y = 'general'
            # print(fname)
            try:
                nums = re.findall(r'\d+', fname)
                y = int(nums[0])
            except Exception as e:
                self.FEEDBACK.reportError(self.tr('Skip landuse file name: %s [%s]')%(fname,str(e)),False)

            res = self.rasterStat(luFile, domainFile,areaFile)
            # make pie plot
            temp_png = os.path.join(outImageFolder, 'lu_pie_%s.png' % y)
            self.plotCatMap(temp_png, luFile, domainFile,areaFile,featFile)
            temp_png_rel = os.path.relpath(temp_png, os.path.dirname(outfile))

            # print('res',res)
            out_stat_path = os.path.join(outStatFolder, 'lu_table_%s.xlsx'%y)
            res.to_excel(out_stat_path, index=False)

            lu_table = self.dataframeToHtml(res.values.tolist(), ['id', 'num. of cells', 'area (map units)', 'percentage'],
                                       None,
                                       ['{:.0f}', '{:.0f}', '{:.0f}', '{:.0f}'])

            if y: lu_title = self.tr('Land use for year: %s'%y)
            else: lu_title = self.tr('General land use (constant over time)')

            lu_contents += self.writeParsToTemplate(None, {'lu_year':str(y),'lu_title': lu_title, 'lu_table': lu_table, 'lu_plot': temp_png_rel},
                                               self.landuse_template)

        self.FEEDBACK.setProgress(40.)

        ### PROCESS IRRIGATION METHODS DATA ###
        self.FEEDBACK.pushInfo(self.tr('Irrigation methods processing ...'))

        irrmethPath = os.path.join(simFolder, simPar['irrmethpath'])
        # read crops parameters
        irrmethFileList = glob.glob(os.path.join(irrmethPath, '*.txt'))

        # print('fileList',fileList)
        irrmethPars = {}
        for irrmethFile in irrmethFileList:
            if os.path.basename(irrmethFile) != 'irrmethods.txt':
                irrmethPars[os.path.basename(irrmethFile)] = self.readIdragraParameters(irrmethFile,self.FEEDBACK,self.tr)

        # TODO: actually, irr_eff is not a parameter of irrigation methods
        irrmethTable = {'id': [], 'name': [], 'irr_eff':[], 'h_wat_mm': [], 'k_stress': [], 'k_stress_well': []}
        for k,v in irrmethPars.items():
            irrmethTable['id'].append(int(v['id']))
            irrmethTable['name'].append(v['irrmeth_name'])
            irrmethTable['irr_eff'].append(float(v['irr_eff']))
            irrmethTable['h_wat_mm'].append(float(v['qadaq']))
            irrmethTable['k_stress'].append(float(v['k_stress']))
            irrmethTable['k_stress_well'].append(float(v['k_stresswells']))

        irrmethTable = pd.DataFrame(irrmethTable)
        irrmethTable.sort_values(by='id', inplace = True)

        out_stat_path = os.path.join(outStatFolder, 'irrmeth_table.xlsx')
        irrmethTable.to_excel(out_stat_path, index=False)

        irrmethTable = self.dataframeToHtml(irrmethTable.values.tolist(),
                                       [self.tr('id'), self.tr('name'), self.tr('irrigation efficiency'),self.tr('fixed irr. volume (mm)'),
                                        self.tr('k stress (collective)'), self.tr('k stress (private)')],
                                       None,
                                       ['{:.0f}', '{:}', '{:.2f}', '{:.2f}', '{:.2f}', '{:.2f}'])

        im_contents = ''
        # search for land use maps
        imFileList = glob.glob(os.path.join(geodataPath, 'irr_meth*.asc'))
        # print('fileList',fileList)
        nOfFiles = len(imFileList)
        for imFile in imFileList:
            # parse year from soiluse_2005.asc
            fname = os.path.basename(imFile)
            # extract date time
            y = 'general'
            # print(fname)
            try:
                nums = re.findall(r'\d+', fname)
                y = int(nums[0])
            except:
                self.FEEDBACK.reportError(self.tr('Skip irrigation method map file name: %s')%fname,False)

            res = self.rasterStat(imFile, domainFile,areaFile)
            # make pie plot
            temp_png = os.path.join(outImageFolder, 'im_pie_%s.png' % y)
            self.plotCatMap(temp_png, imFile, domainFile,areaFile,featFile)
            temp_png_rel = os.path.relpath(temp_png, os.path.dirname(outfile))

            # print('res',res)
            out_stat_path = os.path.join(outStatFolder, 'im_table_%s.xlsx'%y)
            res.to_excel(out_stat_path, index=False)

            im_table = self.dataframeToHtml(res.values.tolist(), ['id', 'num. of cells', 'area (map units)', 'percentage'],
                                       None,
                                       ['{:.0f}', '{:.0f}', '{:.0f}', '{:.0f}'])

            if y: im_title = self.tr('Irrigation methods for year: %s'%y)
            else: im_title = self.tr('General irrigation methods (constant over time)')

            im_contents += self.writeParsToTemplate(None, {'im_year':str(y),'im_title': im_title, 'im_table': im_table, 'im_plot': temp_png_rel},
                                               self.irrmeth_template)

        self.FEEDBACK.setProgress(60.)

        ### PROCESS SOILS DATA ###
        self.FEEDBACK.pushInfo(self.tr('Soils data processing ...'))

        soilPar1FNList = ['ThetaI_r.asc', 'ThetaI_WP.asc','ThetaI_FC.asc','ThetaI_sat.asc','Ksat_I.asc']
        soilPar2FNList = ['ThetaII_r.asc', 'ThetaII_WP.asc','ThetaII_FC.asc','ThetaII_sat.asc','Ksat_II.asc']

        soilParName = ['Res. (-)', 'WP (-)', 'FC (-)', 'Sat. (-)', 'K sat. (cm/hour)']
        statLabel = ['min', 'mean', 'max']

        first_soil_par_table = self.makeGroupedStats(geodataPath,soilPar1FNList,soilParName,statLabel)
        out_stat_path = os.path.join(outStatFolder, 'soil_table_1st.xlsx')
        first_soil_par_table.to_excel(out_stat_path, index=False)
        first_soil_par_table = self.dataframeToHtml(first_soil_par_table.values.tolist(),
                                          ['soil id']+soilParName,
                                          statLabel,
                                          ['{:.0f}']+['{:.2f}']*(len(list(first_soil_par_table.columns))-1))

        sec_soil_par_table = self.makeGroupedStats(geodataPath, soilPar2FNList, soilParName, statLabel)
        out_stat_path = os.path.join(outStatFolder, 'soil_table_2nd.xlsx')
        sec_soil_par_table.to_excel(out_stat_path, index=False)
        sec_soil_par_table = self.dataframeToHtml(sec_soil_par_table.values.tolist(),
                                               ['soil id'] + soilParName,
                                               statLabel,
                                               ['{:.0f}'] + ['{:.2f}'] * (len(list(sec_soil_par_table.columns)) - 1))

        soilPar3FNList = ['CapRisePar_b1.asc', 'CapRisePar_b2.asc', 'CapRisePar_b3.asc', 'CapRisePar_b4.asc', 'CapRisePar_a3.asc','CapRisePar_b1.asc']

        soilParName = ['b1', 'b2', 'b3', 'b4', 'a4', 'a5']
        statLabel = ['min', 'mean', 'max']

        dep_soil_par_table = self.makeGroupedStats(geodataPath, soilPar3FNList, soilParName, statLabel)
        dep_soil_par_table = self.dataframeToHtml(dep_soil_par_table.values.tolist(),
                                             ['soil id'] + soilParName,
                                             statLabel,
                                             ['{:.0f}'] + ['{:.2f}'] * (len(list(dep_soil_par_table.columns)) - 1))


        soilPar4FNList = ['hydr_group.asc', 'main_txtr.asc']

        soilParName = ['HSG', 'Texture']
        statLabel = ['min', 'mean', 'max']

        other_soil_par_table = self.makeGroupedStats(geodataPath, soilPar4FNList, soilParName, statLabel)
        out_stat_path = os.path.join(outStatFolder, 'soil_table_other.xlsx')
        other_soil_par_table.to_excel(out_stat_path, index=False)
        other_soil_par_table = self.dataframeToHtml(other_soil_par_table.values.tolist(),
                                             ['soil id'] + soilParName,
                                             statLabel,
                                             ['{:.0f}'] + ['{:.2f}'] * (len(list(other_soil_par_table.columns)) - 1))

        # make pie plot
        temp_png = os.path.join(outImageFolder, 'soil_pie.png')
        self.plotCatMap(temp_png, os.path.join(geodataPath,'soilid.asc'), domainFile,areaFile,featFile)
        temp_png_rel = os.path.relpath(temp_png, os.path.dirname(outfile))

        soil_stat_tbl = self.rasterStat(os.path.join(geodataPath,'soilid.asc'), domainFile, areaFile)
        soil_stat_tbl.sort_values(by='id', inplace = True)

        out_stat_path = os.path.join(outStatFolder, 'soilmap_table.xlsx')
        soil_stat_tbl.to_excel(out_stat_path, index=False)

        soil_stat_tbl = self.dataframeToHtml(soil_stat_tbl.values.tolist(),
                                             ['id', 'num. of cells', 'area (map units)', 'percentage'],
                                             None,
                                             ['{:.0f}', '{:.0f}', '{:.0f}', '{:.0f}'])

        #print('soil pars', soil_par_table)
        soil_contents = self.writeParsToTemplate(None, {'soil_plot': temp_png_rel,
                                                     'soil_first_table': first_soil_par_table,
                                                     'soil_second_table':sec_soil_par_table,
                                                     'soil_deep_table':dep_soil_par_table,
                                                     'soil_hydro_table': other_soil_par_table,
                                                     'soil_stat_table': soil_stat_tbl},
                                              self.soil_template)

        self.FEEDBACK.setProgress(80.)

        ### MAKE REPORT BODY ###
        report_contents = self.writeParsToTemplate(None,simPar,self.sim_template)
        report_contents += self.writeParsToTemplate(None, {'ws_overview_map': ws_overview_map,
                                                     'ws_block': ws_contents,
                                                     'lu_list_table':lu_list_table,
                                                     'crop_list_table':crop_list_table,
                                                     'lu_block': lu_contents,
                                                     'im_list_table':irrmethTable,
                                                     'im_block': im_contents,
                                                     'soil_block': soil_contents},
                                              self.overview_template)

        self.FEEDBACK.setProgress(90.)

        # BUILD MAIN TOC
        mainToc = self.makeToc(report_contents)

        # UNPADE NUMBERING FOR FIGURES AND TABLES
        report_contents = self.update_refnum(report_contents, '[%tbl_num%]')
        report_contents = self.update_refnum(report_contents, '[%img_num%]')

        ### WRITE TO FILE ###
        self.writeParsToTemplate(outfile, {'sub_title': self.tr(' - general information'),
                                      'current_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                      'sim_path': simFolder,
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
    outputFile = os.path.join(outpath,'sim_overview.html')
    RB = OverviewReportBuilder()
    outfile = RB.makeReport(simFolder,outputFile)
    print(outfile)
