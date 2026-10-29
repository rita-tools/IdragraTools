import os
import glob
import pandas as pd
import numpy as np

# dato il percorso alla cartella delle simulazioni
from report.tools.read_asc import read_asc
from report.tools.read_meteo_dat import read_meteo_dat
from report.tools.save_dataframe_with_comment import save_dataframe_with_comment


def make_avg_timeserie(sim_path):
    meteo_path = os.path.join(sim_path,'meteodata')
    geodata_path = os.path.join(sim_path,'geodata')
    stat_path = os.path.join(sim_path, 'report_stats')

    # carica i file meteo delle stazioni
    wtr_fn_list = glob.glob(os.path.join(meteo_path,'*.dat'))
    ws_data = {}
    for wtr_fn in wtr_fn_list:
        ws_id = os.path.basename(wtr_fn).replace('.dat','')
        temp = read_meteo_dat(wtr_fn)
        ws_data[ws_id] = temp['data']
        start_date = temp['start_date']
        end_date = temp['end_date']

    ws_list = list(ws_data.keys())
    #print(ws_data)
    # carica le matrici dei pesi
    ww_fn_list = glob.glob(os.path.join(geodata_path,'meteo_*.asc'))
    ww_id = {}
    ww_data = {}

    for ww_fn in ww_fn_list:
        id = os.path.basename(ww_fn).replace('.asc','')
        temp = read_asc(ww_fn, float)['data']
        temp2 = np.trunc(temp)
        ww_id[id] = temp2.astype(int)
        ww_data[id] = temp - temp2

    meteo_id_list = list(ww_id.keys())

    #print(ww_data)

    # carica la matrice delle aree degli appezzamenti
    fld_area = read_asc(os.path.join(geodata_path,'shapearea.asc'), float)['data']
    tot_fld_area = fld_area.sum()

    dt_list = pd.date_range(start=start_date, end=end_date)
    res = pd.DataFrame({'data':dt_list.format(formatter=lambda x: x.strftime('%Y-%m-%d')),
                        'doy':dt_list.format(formatter=lambda x: x.strftime('%j')),
                        'year':dt_list.format(formatter=lambda x: x.strftime('%Y')),
                        'month':dt_list.format(formatter=lambda x: x.strftime('%m')),
                        'day':dt_list.format(formatter=lambda x: x.strftime('%d'))})

    for w_var in ['T_max','T_min','P_tot','U_max','U_min','V_med','RG_CORR']:
        # riorganizza i dati per renderli più comodi da analizzare
        var_df = pd.DataFrame()
        for k,v in ws_data.items():
            var_df[k] = v[w_var]

        n_days = len(var_df)

        #print(var_df)
        # per ogni giorno, spazializza il dato meteo
        avg_val = []
        for i,row in var_df.iterrows():
            # distribuisci il valore sulla matrice degli ws_id
            int_val = np.zeros(fld_area.shape)
            for meteo_id in meteo_id_list:
                cond = [ww_id[meteo_id] == int(x) for x in ws_list]
                repl = [row[x] for x in ws_list]
                temp_val = np.select(cond, repl, ww_id[meteo_id])
                temp_ww = ww_data[meteo_id]
                int_val = int_val +temp_val*temp_ww

            # e calcola il valore medio pesato sulle superfici
            avg_val.append((int_val*fld_area/tot_fld_area).sum())
            #avg_val.append(int_val.mean())

        res[w_var] = avg_val

    #print(res)
    # salva la serie temporale in csv
    save_dataframe_with_comment(os.path.join(stat_path,'avg_meteo_daily.csv'),res,'Average daily weather data')
    return res

def make_stat_from_ts(df, grp_col = '',var_col = ['T_max','T_min','P_tot','U_max','U_min','V_med','RG_CORR']):
    if not grp_col:
        grp_col = 'all'
        df[grp_col]=1

    stat_df = df.groupby(grp_col,as_index=True)[var_col].agg(['sum','min','max','mean','count'])
    stat_df.columns = ['-'.join(col).strip() for col in stat_df.columns.values]
    # riordina le colonne
    stat_df[grp_col] = stat_df.index
    cols = stat_df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    stat_df = stat_df[cols]

    #print(col_names)
    return stat_df


if __name__ == '__main__':
    my_sim_path = r'C:\fake\test_ponte_trento\test1_dd_SIM'
    res =make_avg_timeserie(sim_path=my_sim_path)
    # ricorda che res è un dataframe con le seguenti colonne
    # ['data', 'doy', 'year', 'month', 'day', 'T_max', 'T_min', 'P_tot', 'U_max', 'U_min', 'V_med', 'RG_CORR']

    all_res = make_stat_from_ts(df=res)
    #print(all_res)
    save_dataframe_with_comment(os.path.join(my_sim_path,'report_stats','ts_stat_all_period.csv'),all_res,'all period statistics')
    yr_res = make_stat_from_ts(df=res,grp_col='year')
    save_dataframe_with_comment(os.path.join(my_sim_path, 'report_stats','ts_stat_by_year.csv'), yr_res, 'statistics by years')
    month_res = make_stat_from_ts(df=res,grp_col='month')
    save_dataframe_with_comment(os.path.join(my_sim_path, 'report_stats','ts_stat_by_month.csv'), month_res, 'statistics by months')
    doy_res = make_stat_from_ts(df=res,grp_col='doy')
    save_dataframe_with_comment(os.path.join(my_sim_path, 'report_stats','ts_stat_by_doy.csv'), doy_res, 'statistics by doy')


