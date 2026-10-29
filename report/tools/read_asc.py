import numpy as np
import pandas as pd
import os

def read_asc(filename, val_type=int,feedback = lambda s:print(s), tr = lambda s:s):
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
           'data': np.array([]), 'extent': ()}

    if not os.path.exists(filename):
        feedback(tr('Unknown file: %s' % filename))
        return None

    with open(filename) as f:
        for i in range(0, 6):
            line = f.readline()
            toks = line.split()
            k = toks[0].strip().lower()
            v = toks[1].strip()
            # print(filename,k,v)
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