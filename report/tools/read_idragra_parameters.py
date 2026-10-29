import numpy as np
import pandas as pd

def read_idragra_parameters(idragraFile, feedback = lambda s:print(s), tr = lambda s:s, NODATA= -9999):
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
                pars['irr_eff'] = NODATA  # for back compatibility

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