# -*- coding: utf-8 -*-

"""
/***************************************************************************
 IdrAgraTools
 A QGIS plugin to manage water demand simulation with IdrAgra model
 The plugin shares user interfaces and tools to manage water in irrigation districts
-------------------
		begin				: 2020-12-01
		copyright			: (C) 2020 by Enrico A. Chiaradia
		email				    : enrico.chiaradia@unimi.it
 ***************************************************************************/

/***************************************************************************
 *																		   *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or	   *
 *   (at your option) any later version.								   *
 *																		   *
 ***************************************************************************/
"""
__author__ = 'Enrico A. Chiaradia'
__date__ = '2020-12-01'
__copyright__ = '(C) 2020 by Enrico A. Chiaradia'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'


from qgis.PyQt.QtCore import QObject
import pandas as pd

class Node(QObject):
    def __init__(self, parent=None, id = None, nodeType = None, numDay =0):
        QObject.__init__(self, parent)
        self.id = str(id)
        self.nodeType = nodeType
        self.upStreamNodes = []
        self.upStreamRatio = []
        self.upStreamLosses = []
        self.downStreamNodes = []
        self.downStreamRatio = []
        self.downStreamLosses = []

        # store value for water distribution
        self.QirrMax = 0.
        self.QcrsMax = 0.
        self.QprivateMax = 0.
        self.QcollMax = 0.

        self.nodeEfficiency = 1.

        self.Qirr = pd.DataFrame([0.]*numDay,dtype=float)
        self.Qcrs = pd.DataFrame([0.]*numDay,dtype=float)
        self.Qprivate = pd.DataFrame([0.]*numDay,dtype=float)
        self.Qcoll = pd.DataFrame([0.] * numDay, dtype=float)

    def setQnom(self,QirrNom,QcrsNom,QprivateNom,QcollNom):
        self.QirrMax += QirrNom
        self.QcrsMax += QcrsNom
        self.QprivateMax += QprivateNom
        self.QcollMax += QcollNom

    def addUpStreamNode(self,nodeId, flowRatio=1, infLosses = 0):
        self.upStreamNodes.append(nodeId)
        self.upStreamRatio.append(flowRatio)
        self.upStreamLosses.append(infLosses)

    def addDownStreamNode(self,nodeId, flowRatio=1, infLosses = 0):
        self.downStreamNodes.append(nodeId)
        self.downStreamRatio.append(flowRatio)
        self.downStreamLosses.append(infLosses)

class NetworkAnalyst(QObject):
    def __init__(self,progress=None, tr=None, parent=None):
        QObject.__init__(self, parent)
        self.progress = progress
        self.tr = tr
        self.nodeDict = {}
        self.divList = []
        self.crsList = []
        self.privList = []
        self.distrList = []
        self.collList = []

    def addNode(self, node, replace = True):
        if ((not replace) and (node.id in list(self.nodeDict.keys()))): return

        self.nodeDict[node.id]= node

    def buildNetwork(self, nodeDF, linkDF, numOfDay, effTable={}):
        self.divList = []
        self.crsList = []
        self.privList = []
        self.distrList = []
        self.collList = []
        # build the network
        for n, node in nodeDF.iterrows():
            #print('add node',node['id'])
            newNode = Node(self, int(node['id']), int(node['node_type']), numOfDay)
            # update node efficiency
            if newNode.id in list(effTable.keys()): newNode.nodeEfficiency = effTable[newNode.id]

            #print(newNode.id,'-',newNode.nodeEfficiency)

            if newNode.nodeType in [11]:
                newNode.setQnom(node['q_sum'],0.,0.,0.)
                self.divList.append(newNode.id)
            elif newNode.nodeType in [12]:
                newNode.setQnom(0.,0.,0.,0.)
                self.collList.append(newNode.id)
            elif newNode.nodeType in [13]:
                newNode.setQnom(0.,node['q_sum'],0.,0.)
                self.crsList.append(newNode.id)
            elif newNode.nodeType in [14]:
                newNode.setQnom(0.,0.,1.,0.)
                self.privList.append(newNode.id)
            elif newNode.nodeType in [3]:
                self.distrList.append(newNode.id)
            else:
                pass

            #print('newNode id', newNode.id)
            # filter all links that have this node as upStream
            linkSel = linkDF[linkDF['outlet_node'].isin([node['id']])]
            for l, link in linkSel.iterrows():
                #print('add upstream node', link['inlet_node'])
                newNode.addUpStreamNode(str(int(link['inlet_node'])),link['flow_rate'],link['inf_losses'])

            # filter all links that have this node as downStream
            linkSel = linkDF[linkDF['inlet_node'].isin([node['id']])]
            for l, link in linkSel.iterrows():
                #print('add downstream node', link['outlet_node'])
                newNode.addDownStreamNode(str(int(link['outlet_node'])), link['flow_rate'], link['inf_losses'])

            self.addNode(newNode, False)

    def assignDischarge(self,QirrDF=None,QprivateDF=None,QcrsDF=None,QcollDF=None):
        # update discharges for each distribution node
        for n in self.distrList:
            node = self.nodeDict[n]
            if QirrDF is not None:
                # consider also node internal efficiency
                node.Qirr.iloc[:, 0] = QirrDF['Source_'+str(node.id)]/node.nodeEfficiency
            if QprivateDF is not None:
                # consider also node internal efficiency
                node.Qprivate.iloc[:, 0] = QprivateDF['Source_'+str(node.id)]/node.nodeEfficiency
            if QcrsDF is not None:
                # consider also node internal efficiency
                node.Qcrs.iloc[:, 0] = QcrsDF['Source_' + str(node.id)] / node.nodeEfficiency

        # # update discharges at each cr source
        # if QcrsDF is not None:
        #     print('self.crsList:',self.crsList)
        #     for n in self.crsList:
        #         node = self.nodeDict[n]
        #         # node efficiency will be considered later
        #         print("QcrsDF['Source_' + str(node.id)", QcrsDF['Source_' + str(node.id)])
        #
        #         node.Qcrs.iloc[:, 0] = QcrsDF['Source_' + str(node.id)]

        # update discharges at each runoff collector source
        if QcollDF is not None:
            for n in self.collList:
                node = self.nodeDict[n]
                # consider also node internal efficiency
                node.Qcoll.iloc[:, 0] = QcollDF['Source_' + str(node.id)]/node.nodeEfficiency


    def computeNodeQirrMax(self):
        testNodeList = self.divList.copy()
        while len(testNodeList) > 0:
            testId = testNodeList[0]
            testNode = self.nodeDict[testId]
            # loop in upstream nodes
            for id, fr in zip(testNode.downStreamNodes, testNode.downStreamRatio):
                downstreamNode = self.nodeDict[id]
                downstreamNode.QirrMax += testNode.QirrMax * fr
                if id not in testNodeList: testNodeList.append(id)  # add to the list of node to be processed

            testNodeList.pop(0)  # remove the first in the list

    def computeNodeQprivateMax(self):
        testNodeList = self.privList.copy()
        while len(testNodeList) > 0:
            testId = testNodeList[0]
            testNode = self.nodeDict[testId]
            # loop in upstream nodes
            for id, fr in zip(testNode.downStreamNodes, testNode.downStreamRatio):
                downstreamNode = self.nodeDict[id]
                downstreamNode.QprivateMax += testNode.QprivateMax * fr
                if id not in testNodeList: testNodeList.append(id)  # add to the list of node to be processed

            testNodeList.pop(0)  # remove the first in the list

    def distrQcoll(self):
        # distribute discharges downstream following connections and flowrate
        testNodeList = self.collList.copy()
        while len(testNodeList) > 0:
            testId = testNodeList[0]
            testNode = self.nodeDict[testId]
            # loop in upstream nodes
            for id, fr in zip(testNode.downStreamNodes, testNode.downStreamRatio):
                downstreamNode = self.nodeDict[id]
                downstreamNode.Qcoll += testNode.Qcoll * fr/downstreamNode.nodeEfficiency # consider also node internal efficiency

                if id not in testNodeList: testNodeList.append(id)  # add to the list of node to be processed

            testNodeList.pop(0)  # remove the first in the list

    def distrQCrs(self):
        # distribute discharges downstream following connections and flowrate
        testNodeList = self.crsList.copy()
        while len(testNodeList) > 0:
            testId = testNodeList[0]
            testNode = self.nodeDict[testId]
            # loop in upstream nodes
            for id, fr in zip(testNode.downStreamNodes, testNode.downStreamRatio):
                downstreamNode = self.nodeDict[id]
                #print(testNode.id, '-->', downstreamNode.id, ', add', testNode.QcrsMax, 'to',
                #      downstreamNode.QcrsMax, 'm^3/s')

                downstreamNode.QcrsMax += testNode.QcrsMax * fr
                downstreamNode.Qcrs += testNode.Qcrs * fr#/downstreamNode.nodeEfficiency # consider also node internal efficiency

                if id not in testNodeList: testNodeList.append(id)  # add to the list of node to be processed

            if testNode.id not in self.distrList: testNode.Qcrs *=0 # reset discharge only if not the distribution node

            testNodeList.pop(0)  # remove the first in the list

        # distribute discharge upstream considering QcrsMax and losses
        testNodeList = self.distrList.copy()
        while len(testNodeList) > 0:
            testId = testNodeList[0]
            testNode = self.nodeDict[testId]
            # print('testNode', testNode.id, '=', testNode.QprivateMax)
            nUSNode = len(testNode.upStreamNodes)
            # loop in upstream nodes
            if self.waitPreviuosNode(testNode.downStreamNodes, testNodeList):
                if testId not in testNodeList: testNodeList.append(testId)  # move to the end of the list if not exists
            else:
                for id, fr, ls in zip(testNode.upStreamNodes, testNode.upStreamRatio, testNode.upStreamLosses):
                    upstreamNode = self.nodeDict[id]
                    # print('upstreamNode',upstreamNode.id,'=',upstreamNode.QprivateMax)
                    if testNode.QcrsMax > 0:
                        if nUSNode == 1:
                            ratio = 1
                        else:
                            ratio = min(1., upstreamNode.QcrsMax * fr / testNode.QcrsMax)

                        upstreamNode.Qcrs.iloc[:, 0] += testNode.Qcrs.iloc[:, 0] * (1.0 / (1.0 - ls)) * ratio
                        # print(testNode.id,'-->',upstreamNode.id,', from', testNode.QprivateMax, 'to',
                        #       upstreamNode.QprivateMax, 'm^3/s, ratio', ratio,'upstreamNode.Qprivate',upstreamNode.Qprivate.iloc[0, 0],'m^3/s')

                        if id not in testNodeList: testNodeList.append(id)  # add to the list of node to be processed if not exists

            testNodeList.pop(0)  # remove the first in the list

    def distrQIrr(self):
        self.computeNodeQirrMax()
        #print('self.nodeDict[id]',self.nodeDict)

        testNodeList = self.distrList.copy()
        while len(testNodeList) > 0:
            testId = testNodeList[0]
            testNode = self.nodeDict[testId]
            #print('testNode', testNode.id, '=', testNode.upStreamNodes)
            nUSNode = len(testNode.upStreamNodes)
            # loop in upstream nodes
            if self.waitPreviuosNode(testNode.downStreamNodes, testNodeList):
                if testId not in testNodeList: testNodeList.append(testId)  # move to the end of the list if not exists
            else:
                for id, fr, ls in zip(testNode.upStreamNodes, testNode.upStreamRatio, testNode.upStreamLosses):
                    upstreamNode = self.nodeDict[id]
                    # print('upstreamNode',upstreamNode.id,'=',upstreamNode.QprivateMax)
                    if testNode.QirrMax > 0:
                        if nUSNode == 1:
                            ratio = 1
                        else:
                            ratio = min(1., upstreamNode.QirrMax * fr / testNode.QirrMax)

                        upstreamNode.Qirr.iloc[:, 0] += testNode.Qirr.iloc[:, 0] * (1.0 / (1.0 - ls)) * ratio
                        # print(testNode.id,'-->',upstreamNode.id,', from', testNode.QprivateMax, 'to',
                        #       upstreamNode.QprivateMax, 'm^3/s, ratio', ratio,'upstreamNode.Qprivate',upstreamNode.Qprivate.iloc[0, 0],'m^3/s')

                        if id not in testNodeList: testNodeList.append(id)  # add to the list of node to be processed if not exists

            testNodeList.pop(0)  # remove the first in the list


    def distrQPrivate(self):
        self.computeNodeQprivateMax()

        testNodeList = self.distrList.copy()
        while len(testNodeList) > 0:
            testId = testNodeList[0]
            testNode = self.nodeDict[testId]
            #print('testNode', testNode.id, '=', testNode.QprivateMax)
            nUSNode = len(testNode.upStreamNodes)
            # loop in upstream nodes
            if self.waitPreviuosNode(testNode.downStreamNodes,testNodeList):
                if testId not in testNodeList: testNodeList.append(testId) # move to the end of the list if not exists
            else:
                for id, fr, ls in zip(testNode.upStreamNodes, testNode.upStreamRatio, testNode.upStreamLosses):
                    upstreamNode = self.nodeDict[id]
                    #print('upstreamNode',upstreamNode.id,'=',upstreamNode.QprivateMax)
                    if testNode.QprivateMax>0:
                        if nUSNode ==1: ratio =1
                        else: ratio = min(1.,upstreamNode.QprivateMax*fr/testNode.QprivateMax)

                        upstreamNode.Qprivate.iloc[:, 0] += testNode.Qprivate.iloc[:, 0] * (1.0 / (1.0 - ls)) * ratio
                        # print(testNode.id,'-->',upstreamNode.id,', from', testNode.QprivateMax, 'to',
                        #       upstreamNode.QprivateMax, 'm^3/s, ratio', ratio,'upstreamNode.Qprivate',upstreamNode.Qprivate.iloc[0, 0],'m^3/s')

                        if id not in testNodeList: testNodeList.append(id)  # add to the list of node to be processed if not exists

            testNodeList.pop(0)  # remove the first in the list

    def waitPreviuosNode(self,dsNodeList,tempNodeList):
        for dsn in dsNodeList:
            if dsn in tempNodeList:
                return True

        return False

    def calculateFlowAtNodes(self):
        self.distrQIrr()
        self.distrQPrivate()
        self.distrQCrs()
        self.distrQcoll()

    def getFlowAtNodes(self,dates):
        QirrAll = []
        QcrsAll = []
        QprivateAll = []
        QcollAll = []
        IdAll = []
        QirrMaxAll = []
        QprivateMaxAll = []
        QcrsMaxAll = []
        datesAll = []

        for id,node in self.nodeDict.items():
            #print('processing',id)
            #print('node.Qirr\n',node.Qirr)
            QirrAll += node.Qirr.iloc[:, 0].values.tolist()
            #print('node.Qcrs\n', node.Qcrs)
            QcrsAll += node.Qcrs.iloc[:, 0].values.tolist()
            #print('node.Qprivate\n', node.Qprivate)
            QprivateAll += node.Qprivate.iloc[:, 0].values.tolist()
            QcollAll += node.Qcoll.iloc[:, 0].values.tolist()

            IdAll+=[id]*len(dates)
            QprivateMaxAll +=[node.QprivateMax]*len(dates)
            QirrMaxAll += [node.QirrMax]*len(dates)
            QcrsMaxAll += [node.QcrsMax]*len(dates)
            datesAll+=dates

        df = pd.DataFrame(list(zip(datesAll, IdAll,QprivateMaxAll,QirrMaxAll,QcrsMaxAll,QirrAll,QcrsAll,QprivateAll,QcollAll)),
                          columns=['DoY','wsid','QprivMaxAll','QirrMaxAll','QcrsMaxAll','Qirr','Qcrs','Qprivate','Qcoll'])

        return df



### START TEST UNITS HERE ###


def example2():
    data = [[1,11,1],
            [2,3,0],
            [3,13,1],
            [4,14,0],
            [5,14,0]]
    nodesDF = pd.DataFrame.from_records(data, columns=['id', 'node_type', 'q_sum'])
    nodesDF['id'] = nodesDF['id'].astype(int, errors='ignore')
    nodesDF['node_type'] = nodesDF['node_type'].astype(int, errors='ignore')

    distrEffDict = {'2':0.8}

    data = [[1,2,1.,0.2],
            [3,2,1.,0.1],
            [4,2,1.,0.1],
            [5,2,1.,0.1]]
    linksDF = pd.DataFrame.from_records(data, columns=['inlet_node','outlet_node','flow_rate','inf_losses'])
    linksDF['inlet_node'] = linksDF['inlet_node'].astype(int, errors='ignore')
    linksDF['outlet_node'] = linksDF['outlet_node'].astype(int, errors='ignore')

    data = [[52, 0.3],
            [53, 0.5],
            [54, 0.7],
            [55, 1.2]
            ]
    QirrDF = pd.DataFrame.from_records(data, columns=['doy','Source_'+str(2)])

    data = [[52, 0.0],
            [53, 3.0],
            [54, 3.0],
            [55, 0.0]
            ]
    QcrsDF = pd.DataFrame.from_records(data, columns=['doy','Source_' + str(3)])

    data = [[52, 0.0],
            [53, 8.0],
            [54, 8.0],
            [55, 0.0]
            ]
    QprivateDF = pd.DataFrame.from_records(data, columns=['doy', 'Source_' + str(2)])

    NA = NetworkAnalyst()
    NA.buildNetwork(nodesDF, linksDF,4)
    NA.assignDischarge(QirrDF,QprivateDF,QcrsDF)
    NA.calculateFlowAtNodes()
    res = NA.getFlowAtNodes(QprivateDF['doy'].values.tolist())
    res['Qsum']=res['Qirr']+res['Qcrs']+res['Qprivate']
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print('res\n',res)

def example3():
    # two distrs served by two private wells connected with a junction
    data = [[1,2,0],
            [2,3,0],
            [3,3,0],
            [4,14,0],
            [5,14,0]]
    nodesDF = pd.DataFrame.from_records(data, columns=['id', 'node_type', 'q_sum'])
    nodesDF['id'] = nodesDF['id'].astype(int, errors='ignore')
    nodesDF['node_type'] = nodesDF['node_type'].astype(int, errors='ignore')

    data = [[4,1,1.,0.],
            [5,1,1.,0.],
            [1,2,0.2,0.],
            [1,3,0.8,0.]]
    linksDF = pd.DataFrame.from_records(data, columns=['inlet_node','outlet_node','flow_rate','inf_losses'])
    linksDF['inlet_node'] = linksDF['inlet_node'].astype(int, errors='ignore')
    linksDF['outlet_node'] = linksDF['outlet_node'].astype(int, errors='ignore')

    data = [[52, 1.0, 1.0]]
    QprivateDF = pd.DataFrame.from_records(data, columns=['doy', 'Source_' + str(2),'Source_' + str(3)])

    NA = NetworkAnalyst()
    NA.buildNetwork(nodesDF, linksDF,1)
    NA.assignDischarge(None,QprivateDF,None)
    NA.calculateFlowAtNodes()
    res = NA.getFlowAtNodes(QprivateDF['doy'].values.tolist())
    res['Qsum']=res['Qirr']+res['Qcrs']+res['Qprivate']
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print('res\n', res)


def example4():
    # two distrs served by two private wells connected with a junction
    data = [[1,2,0],
            [2,3,0],
            [3,3,0],
            [4,14,0],
            [5,14,0],
            [6,14,0],
            [7, 2, 0]
            ]
    nodesDF = pd.DataFrame.from_records(data, columns=['id', 'node_type', 'q_sum'])
    nodesDF['id'] = nodesDF['id'].astype(int, errors='ignore')
    nodesDF['node_type'] = nodesDF['node_type'].astype(int, errors='ignore')

    data = [[4, 1, 1., 0.1],
            [5, 1, 1., 0.1],
            [6, 7, 1., 0.1],
            [1, 7, 0.5, 0.1],
            [1, 2, 0.5,0.1],
            [7, 3, 1.,0.1]]
    linksDF = pd.DataFrame.from_records(data, columns=['inlet_node','outlet_node','flow_rate','inf_losses'])
    linksDF['inlet_node'] = linksDF['inlet_node'].astype(int, errors='ignore')
    linksDF['outlet_node'] = linksDF['outlet_node'].astype(int, errors='ignore')

    data = [[52, 1.0, 1.0]]
    QprivateDF = pd.DataFrame.from_records(data, columns=['doy', 'Source_' + str(2),'Source_' + str(3)])

    NA = NetworkAnalyst()
    NA.buildNetwork(nodesDF, linksDF,1)
    NA.assignDischarge(None,QprivateDF,None)
    NA.calculateFlowAtNodes()
    res = NA.getFlowAtNodes(QprivateDF['doy'].values.tolist())
    res['Qsum']=res['Qirr']+res['Qcrs']+res['Qprivate']
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print('res\n',res)

def example5():
    # two distrs served by three private wells connected with a junction
    data = [[1,2,0],
            [2,3,0],
            [3,3,0],
            [4,14,0],
            [5,14,0],
            [6,14,0]]
    nodesDF = pd.DataFrame.from_records(data, columns=['id', 'node_type', 'q_sum'])
    nodesDF['id'] = nodesDF['id'].astype(int, errors='ignore')
    nodesDF['node_type'] = nodesDF['node_type'].astype(int, errors='ignore')

    data = [[4,1,1.,0.],
            [5,1,1.,0.],
            [6, 1, 1., 0.],
            [1,2,0.2,0.],
            [1,3,0.8,0.]]
    linksDF = pd.DataFrame.from_records(data, columns=['inlet_node','outlet_node','flow_rate','inf_losses'])
    linksDF['inlet_node'] = linksDF['inlet_node'].astype(int, errors='ignore')
    linksDF['outlet_node'] = linksDF['outlet_node'].astype(int, errors='ignore')

    data = [[52, 1.0, 1.0]]
    QprivateDF = pd.DataFrame.from_records(data, columns=['doy', 'Source_' + str(2),'Source_' + str(3)])

    NA = NetworkAnalyst()
    NA.buildNetwork(nodesDF, linksDF,1)
    NA.assignDischarge(None,QprivateDF,None)
    NA.calculateFlowAtNodes()
    res = NA.getFlowAtNodes(QprivateDF['doy'].values.tolist())
    res['Qsum']=res['Qirr']+res['Qcrs']+res['Qprivate']
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print('res\n',res)


def example5():
    # two distrs served by three diversions connected with a junction
    data = [[1,2,0],
            [2,3,0],
            [3,3,0],
            [4,13,1.],
            [5,13,1.],
            [6,13,1.]]
    nodesDF = pd.DataFrame.from_records(data, columns=['id', 'node_type', 'q_sum'])
    nodesDF['id'] = nodesDF['id'].astype(int, errors='ignore')
    nodesDF['node_type'] = nodesDF['node_type'].astype(int, errors='ignore')

    data = [[4,1,1.,0.1],
            [5,1,1.,0.1],
            [6, 1, 1., 0.1],
            [1,2,0.5,0.1],
            [1,3,0.5,0.1]]
    linksDF = pd.DataFrame.from_records(data, columns=['inlet_node','outlet_node','flow_rate','inf_losses'])
    linksDF['inlet_node'] = linksDF['inlet_node'].astype(int, errors='ignore')
    linksDF['outlet_node'] = linksDF['outlet_node'].astype(int, errors='ignore')

    data = [[52, 1.0, 1.0, 1.0]]
    QcrsDF = pd.DataFrame.from_records(data, columns=['doy', 'Source_' + str(4),'Source_' + str(5),'Source_' + str(6)])

    NA = NetworkAnalyst()
    NA.buildNetwork(nodesDF, linksDF,1,{'2':0.9})
    NA.assignDischarge(None,None,QcrsDF)
    NA.calculateFlowAtNodes()
    res = NA.getFlowAtNodes(QcrsDF['doy'].values.tolist())
    res['Qsum']=res['Qirr']+res['Qcrs']+res['Qprivate']+res['Qcoll']
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print('res\n',res)



if __name__ == '__main__':
    # nodeDF, linkDF,QirrDF,QCrsDF,QPrivateDF
    example5()
