from datetime import datetime

def save_dataframe_with_comment(fn,df,meta=''):
    with open(fn,'w') as f:
        if meta:
            f.write('# %s - Created on %s\n'%(meta,datetime.now()))
        else:
            f.write('# Created on %s\n' % (datetime.now()))

    df.to_csv(fn, index=False,sep=';',mode='a')