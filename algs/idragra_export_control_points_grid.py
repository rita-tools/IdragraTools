# -*- coding: utf-8 -*-

"""
/***************************************************************************
 IdrAgraTools
 A QGIS plugin to manage water demand simulation with IdrAgra model
 The plugin shares user interfaces and tools to manage water in irrigation districts
-------------------
        begin                : 2020-12-01
        copyright            : (C) 2020 by Enrico A. Chiaradia
        email                    : enrico.chiaradia@unimi.it
 ***************************************************************************/

/***************************************************************************
 *                                                                           *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or       *
 *   (at your option) any later version.                                   *
 *                                                                           *
 ***************************************************************************/
"""
__author__ = 'Enrico A. Chiaradia'
__date__ = '2020-12-01'
__copyright__ = '(C) 2020 by Enrico A. Chiaradia'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QCoreApplication,QVariant
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterMultipleLayers,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterString,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterField,
                       QgsProcessingParameterExtent,
                       QgsProcessingParameterRasterDestination,
                       QgsExpression,
                       QgsFeatureRequest,
                       QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform,
                       QgsProcessingParameterFolderDestination,
                       QgsWkbTypes,
                       QgsFields,
                       QgsField,
                       QgsVectorFileWriter,
                       QgsRasterFileWriter,
                       QgsVectorLayer,
                       QgsRasterLayer,
                       QgsProject,
                       NULL, QgsRectangle)

import os

from ..tools.write_pars_to_template import writeParsToTemplate
from ..tools.gis_grid import GisGrid


class IdragraExportControlPointsGrid(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.
    
    VECTORLAY= 'VECTOR_LAY'
    RASTEREXT = 'RASTER_EXT'
    CELLDIM = 'CELL_DIM'
    DESTFILE = 'DEST_FILE'
        
    FEEDBACK = None
    

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return IdragraExportControlPointsGrid()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'IdragraExportControlPointsGrid'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Control points')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('Export')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'IdragraExport'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        
        helpStr = """
                        The algorithm creates a file with the list of the cells where save detailed output. 
                        <b>Parameters:</b>
                        Source vector layer: the vector layer of control points (points) [VECTOR_LAY]
                        Raster extension: the maximum extension of the raster domain map (min x, max x, min y, max y) [RASTER_EXT]
                        Raster cell dimension: the dimension of the squared cell in map units [CELL_DIM]
                        Output file: the complete path of the output file (*.txt) [DESTFILE]
                        """
        
        return self.tr(helpStr)

    def icon(self):
        self.alg_dir = os.path.dirname(__file__)
        icon = QIcon(os.path.join(self.alg_dir, 'idragra_tool.png'))
        return icon

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
    
        self.addParameter(QgsProcessingParameterVectorLayer(self.VECTORLAY, self.tr('Source vector layer'), [QgsProcessing.TypeVectorPoint ]))

        self.addParameter(QgsProcessingParameterExtent(self.RASTEREXT, self.tr('Raster extension')))
        
        self.addParameter(QgsProcessingParameterNumber(self.CELLDIM, self.tr('Raster cell dimension')))
        
        self.addParameter(QgsProcessingParameterFileDestination(self.DESTFILE, self.tr('Output file'), self.tr('text file (*.txt)')))
        
        
    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        self.FEEDBACK = feedback
        # get params
        vectorLay = self.parameterAsVectorLayer(parameters, self.VECTORLAY, context)
        rasterExt = self.parameterAsExtent(parameters, self.RASTEREXT, context)
        cellDim = self.parameterAsDouble(parameters, self.CELLDIM, context)
        filename = self.parameterAsFileOutput(parameters,    self.DESTFILE,    context)


        # calculate extension
        xllcorner = rasterExt.xMinimum()
        # yllcorner = extension.yMinimum()
        yurcorner = rasterExt.yMaximum()
        h = rasterExt.height()
        w = rasterExt.width()

        nrows = round(h / cellDim)
        ncols = round(w / cellDim)

        xurcorner = xllcorner + ncols * cellDim
        # yurcorner = yllcorner+nrows*outputCellSize
        yllcorner = yurcorner - nrows * cellDim

        newExt = QgsRectangle(xllcorner, yllcorner, xurcorner, yurcorner)

        # make a grid object
        self.aGrid = GisGrid()
        self.aGrid.fitToExtent(newExt,cellDim,cellDim)

        # loop in layer and get point coordinates
        recs = ['ID\tX\tY']
        dummy = []
        nFeats = vectorLay.featureCount()
        n = 0
        for feature in vectorLay.getFeatures():
            name = feature['name']
            descr = feature['descr']
            try: geom = feature.geometry().asMultiPoint()[0]
            except: geom = None

            if geom:
                x = geom.x()
                y = geom.y()
                c, r = self.aGrid.coordToCell(x, y)
                # coordinates are one-based
                c+=1
                r+=1
                if (c<1) or (c>ncols) or (r<1) or (r>nrows):
                    self.FEEDBACK.reportError(
                        self.tr('Control point named %s is outside the extension') %
                        (feature['name']))
                else:
                    row_col = '%s\t%s' % (r, c)  # flipped
                    if row_col not in dummy:
                        dummy.append(row_col)
                        newRec = '%s\t%s\t# %s - %s' % (feature['id'], row_col, name, descr)  # flipped
                        recs.append(newRec)
                    else:
                        self.FEEDBACK.reportError(
                            self.tr('More than one control point falls in one computational cell. Only one will be exported. Consider to reduce cell size.') %
                            (feature['name']))


            n+=1
            self.FEEDBACK.setProgress(100. * n / nFeats)

        tableTxt = '\n'.join(recs)
        cpDict = {'NUMCELL':len(dummy), 'CELLTABLE':tableTxt}

        writeParsToTemplate(outfile=filename,
                            parsDict=cpDict,
                            templateName='cells.txt')


        return {'OUTPUT':cpDict}
        