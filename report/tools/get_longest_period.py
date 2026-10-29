import pandas as pd
from datetime import datetime

from report.tools.weather_analysis import make_avg_timeserie


def get_longest_period(df,time_fld,val_fld,lbound, ubound, mask = None):
    if mask is None:
        df['mask']= True
    else:
        df['mask']= mask
    # Assegna uno ai valori nel range e zero a quelli fuori range
    df['flag'] = 1
    df.loc[(df[val_fld]>=lbound)&(df[val_fld]<=ubound),'flag'] = 0
    df['cumsum_val'] = df.flag.cumsum()
    df.loc[df['mask']!=True,'cumsum_val']=pd.NA
    # prandi il valore più rappresentato di cumsum
    mod_value = df.cumsum_val.mode().values.tolist()[0]
    num_time = df.loc[df['cumsum_val'] == mod_value, time_fld].count()
    start_date = df.loc[df['cumsum_val']==mod_value,time_fld].min()
    end_date = df.loc[df['cumsum_val'] == mod_value, time_fld].max()
    #delta_time = datetime.strptime(end_date,'%Y-%m-%d')-datetime.strptime(start_date,'%Y-%m-%d')
    return num_time,start_date,end_date

if __name__ == '__main__':
    my_sim_path = r'C:\fake\test_ponte_trento\test1_dd_SIM'
    res = make_avg_timeserie(sim_path=my_sim_path)
    # ricorda che res è un dataframe con le seguenti colonne
    # ['data', 'doy', 'year', 'month', 'day', 'T_max', 'T_min', 'P_tot', 'U_max', 'U_min', 'V_med', 'RG_CORR']
    num_time,start_date,end_date = get_longest_period(res,
                                                     time_fld='data',
                                                     val_fld='P_tot',
                                                     lbound=0,
                                                     ubound=0)
    print(num_time)