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

import os
from os.path import relpath

import processing
from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle, QgsRasterLayer, QgsRasterBlockFeedback, \
    QgsRasterFileWriter, QgsRasterPipe, QgsRasterProjector, QgsProject

from tools.delete_raster_from_DB import deleteRasterFromDB


def importRasterInDB(DBM, rasterFileName, tableName, crs=QgsCoordinateReferenceSystem(),
                     extension=QgsRectangle()):
    rasterFilePath = rasterFileName

    if DBM is None:
        msg = deleteRasterFromDB(tableName, DBM)
        if msg != '':
            # progress.reportError(self.tr('Error: %s') % msg, True)
            print('errore', msg)

    else:
        msg = deleteRasterFromDB(tableName, DBM)
        if msg != '':
            # progress.reportError(self.tr('Error: %s') % msg, True)
            print('errore', msg)

        source = QgsRasterLayer(rasterFileName, tableName, 'gdal')

        sExtent = source.extent()
        ulx = sExtent.xMinimum()
        uly = sExtent.yMaximum()
        lrx = sExtent.xMaximum()
        lry = sExtent.yMinimum()

        print('selected extension', extension)
        ulx = extension.xMinimum()
        uly = extension.yMaximum()
        lrx = extension.xMaximum()
        lry = extension.yMinimum()

        extension = sExtent.intersect(extension)
        ulx = extension.xMinimum()
        uly = extension.yMaximum()
        lrx = extension.xMaximum()
        lry = extension.yMinimum()

        if extension.area() == 0:
            extension = sExtent

        ulx = extension.xMinimum()
        uly = extension.yMaximum()
        lrx = extension.xMaximum()
        lry = extension.yMinimum()
        extraString = '-projwin %s %s %s %s ' % (ulx, uly, lrx, lry)

        # ds = ogr.Open(gpkgFile, True)
        # gdal.GetDriverByName('GPKG').Create(gpkgFile, 1, 1, 1)
        # print('gpkgFile', gpkgFile)
        # first convert file format
        # TODO: check extension and projection
        algresult = processing.run("gdal:translate",
                                   {'INPUT': rasterFileName, 'TARGET_CRS': crs, 'NODATA': None,
                                    'COPY_SUBDATASETS': False, 'OPTIONS': '', 'EXTRA': extraString, 'DATA_TYPE': 6,
                                    'OUTPUT': 'TEMPORARY_OUTPUT'},
                                   context=None,
                                   feedback=None,
                                   is_child_algorithm=False)

        source = QgsRasterLayer(algresult['OUTPUT'], tableName, 'gdal')
        # source = QgsRasterLayer(rasterFileName, tableName, 'gdal')

        xmin = source.extent().xMinimum()
        ymax = source.extent().yMaximum()
        xres = source.rasterUnitsPerPixelX()
        yres = source.rasterUnitsPerPixelY()

        geotransform = [xmin, xres, 0, ymax, 0, -yres]
        #
        # source.SetGeoTransform(geotransform)

        rfeedback = QgsRasterBlockFeedback()
        gpkgFile = DBM.DBName
        if source.isValid():
            provider = source.dataProvider()
            fw = QgsRasterFileWriter(gpkgFile)
            fw.setOutputFormat('gpkg')
            fw.setCreateOptions(["RASTER_TABLE=" + str(tableName), 'APPEND_SUBDATASET=YES'])

            pipe = QgsRasterPipe()
            clipExt = provider.extent()
            xSize = provider.xSize()
            ySize = provider.ySize()

            if pipe.set(provider.clone()) is True:
                projector = QgsRasterProjector()
                projector.setCrs(provider.crs(), provider.crs())
                if pipe.insert(2, projector) is True:
                    # print('provider',provider.xSize(),provider.ySize(),provider.extent(),provider.crs())
                    error = fw.writeRaster(pipe, provider.xSize(), provider.ySize(), provider.extent(),
                                           provider.crs(), rfeedback)
                    if error > 0:
                        print('err', rfeedback.errors())
                    # progress.reportError('\n'.join(rfeedback.errors()), True)
                    else:
                        #gpkgFile = relpath(gpkgFile, QgsProject.instance().absolutePath())
                        gpkgFile = os.path.basename(gpkgFile)
                        #rasterFilePath = 'GPKG:' + gpkgFile + ':' + tableName
                        rasterFilePath =os.path.join('.',gpkgFile) + ':' + tableName
                # rasterFilePath = rasterFilePath.replace('\\', '/')
                # if layName:
                #    self.loadRaster(rasterFilePath, layName, layGroup)
    # if QgsProject.instance().filePathStorage()==1:
    #     # get relative path to the project
    #     rasterFilePath = relpath(rasterFilePath, QgsProject.instance().absolutePath())

    return rasterFilePath.replace('\\', '/')
