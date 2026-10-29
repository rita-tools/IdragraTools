import pandas as pd
from datetime import datetime

def read_meteo_dat(fn):
    with open(fn) as f:
        head = [next(f) for _ in range(3)]

    # parse head lines
    # Id stazione: 500, località: Mantova Tridolino
    # 45.30616  22.0
    # 01/01/2019 -> 31/12/2020
    toks = head[0].split(',')
    lbl,ws_id = toks[0].split(':')
    lbl, ws_name = toks[1].split(':')
    lat,alt = head[1].split()
    start_date, end_date = head[2].split('->')

    # read the time series
    df = pd.read_csv(fn, sep=r'\s* \s*', engine='python', skiprows=3)

    res = {}
    res['ws_id'] = int(ws_id.strip())
    res['ws_name'] = ws_name.strip()
    res['lat'] = float(lat.strip())
    res['alt'] = float(alt.strip())
    res['start_date'] = datetime.strptime(start_date.strip(),format('%d/%m/%Y'))
    res['end_date'] = datetime.strptime(end_date.strip(), format('%d/%m/%Y'))
    res['data'] = df
    return res

if __name__ =='__main__':
    ws_data_fn = r'C:\fake\test_ponte_trento\test1_dd_SIM\meteodata\500.dat'
    res = read_meteo_dat(ws_data_fn)
    print(res)





