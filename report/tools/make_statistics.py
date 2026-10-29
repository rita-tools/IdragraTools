import numpy as np
import pandas as pd
import os
import glob
import re

from report.tools.read_asc import read_asc

def count_notna(a):
    n = np.count_nonzero(~np.isnan(a))
    return n

def make_statistics(out_folder, par_fn_List, par_name_list,
                    stat_list=['min', 'mean', 'average', 'max'],
                    mask_fn='pathTo/domain.asc', mask_id=1,
                    weights_fn=None,
                    feedback = lambda s:print(s), tr = lambda s:s):

    stat_fun = {'min': np.nanmin, 'max': np.nanmax, 'mean': np.nanmean,
                'std': np.nanstd, 'var': np.nanvar,
                'sum': np.nansum, 'median': np.nanmedian,
                'average': np.average, 'count': count_notna}

    mask_rl = read_asc(mask_fn)

    mask_data = np.where(mask_rl['data'] == mask_rl['nodata_value'], np.nan, mask_rl['data'])
    if (len(mask_data.shape)==0):
        mask_data = np.where(mask_data != mask_id, np.nan, mask_data * 0 + 1)
    else:
        mask_data = np.where(mask_data[:] != mask_id, np.nan, mask_data[:] * 0 + 1)

    weights_data = mask_data * mask_rl['cellsize'] * mask_rl['cellsize']

    if weights_fn:
        weights_rl = read_asc(weights_fn,float)
        weights_data = weights_rl['data'] * mask_data

    area_iu = np.nansum(weights_data)
    # setup res table
    res = {'year': [], 'month': [], 'step': [], 'area': []}

    for i in par_name_list:
        for s in stat_list: res['%s_%s' % (i, s)] = []

    for i, par_fn in enumerate(par_fn_List):
        # match only if start with four characters
        feedback(tr('par name: %s') % par_fn)

        out_file_list = glob.glob(os.path.join(out_folder, par_fn + '.asc'))
        out_file_list.sort()
        # reset year list
        res['year'] = []
        res['month'] = []
        res['step'] = []
        res['area'] = []

        # print('out_file_list:', out_file_list)
        for outFile in out_file_list:
            feedback(tr('--> %s') % outFile)

            y = 0
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
                feedback(tr('Bad-formatted landusstep/month file name: %s') % outFile)

            res['year'].append(y)
            res['month'].append(month)
            res['step'].append(step)
            res['area'].append(area_iu)

            # compute stats

            parRl = read_asc(outFile, float)
            par_data = np.where(parRl['data'] == parRl['nodata_value'], np.nan, parRl['data'])
            filtered_weights_data = weights_data[~np.isnan(par_data)]
            filtered_pars_data = par_data[~np.isnan(par_data)]

            nan_flag = np.isnan(filtered_pars_data).all()
            for stat in stat_list:
                aVal = np.nan
                if not nan_flag:
                    if stat == 'average':
                        # apply weights_rl to calculare averages
                        # remove first all nans
                        filtered_weights_data2 = filtered_weights_data[~np.isnan(filtered_weights_data)]
                        filtered_pars_data2 = filtered_pars_data[~np.isnan(filtered_weights_data)]
                        # print('DEBUG: tot.area:',sum(filtered_weights_data2))
                        # filtered_weights_data = np.nan_to_num(filtered_weights_data,False,0.)
                        aVal = stat_fun[stat](filtered_pars_data2, None, filtered_weights_data2)
                    else:
                        aVal = stat_fun[stat](filtered_pars_data)

                res['%s_%s' % (par_name_list[i], stat)].append(aVal)

    # print(res)

    # remove empty month and step
    if len(res['month']) == 0:
        del res['month']
    elif max(res['month']) == 0:
        del res['month']
    else:
        pass

    if len(res['step']) == 0:
        del res['step']
    elif max(res['step']) == 0:
        del res['step']
    else:
        pass

    return pd.DataFrame(res)

if __name__ == '__main__':

    outFolder = r'C:\test_micheleP\monocella\new_idragra_f_c_05'
    domain_fn = r'C:\test_micheleP\monocella\spatial_data\domain.asc'

    waterFlux = {
        'prec_tot': 'Cumulative precipitation (mm)',
        'eva_act_agr': 'Cumulative actual evaporation (mm)',
        'trasp_act_tot': 'Cumulative actual transpiration (mm)',
        'irr_tot': 'Cumulative irrigation (mm)',
        'irr_loss': 'Irrigation application losses (mm)',
        'run_tot': 'Cumulative runoff (mm)',
        'net_flux_gw': 'Net flux to groundwater (mm)',
    }
    parFNList = ['????_'+x for x in list(waterFlux.keys())]
    parName = list(waterFlux.values())

    res = make_statistics(out_folder= outFolder, par_fn_List= parFNList, par_name_list= parName,
                          stat_list=['min', 'mean', 'average', 'std', 'max'],
                          mask_fn=domain_fn, mask_id=1,
                          weights_fn=None,
                          feedback=lambda s: print(s), tr=lambda s: s)
    print(res)
