from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QImage, QColor, QPainter
from qgis.core import QgsMapSettings, QgsProject, QgsRectangle, QgsMapRendererCustomPainterJob, QgsPrintLayout, \
    QgsLayoutSize, QgsUnitTypes, QgsLayoutItemLegend, QgsLayerTree, QgsLayoutExporter, QgsLayoutItemMap, QgsLayoutPoint, \
    QgsLayoutItemScaleBar


def layoutToImage(layerList,imageFile,width = 300, height= 150,extent = None, paperUnit = QgsUnitTypes.LayoutMillimeters):
    color = QColor(255, 255, 255, 255)
    map_w = width*2/3
    map_h = height
    leg_w = width*1/3
    leg_h = height

    layout = QgsPrintLayout(QgsProject.instance())
    layout.initializeDefaults()
    layout.pageCollection().pages()[0].setPageSize(QgsLayoutSize(width, height, paperUnit))
    layout.setName('temp lay')
    # add layou to the project mananger
    # manager = QgsProject.instance().layoutManager()
    # manager.addLayout(layout)

    # add map view
    # credits: https://data.library.virginia.edu/how-to-create-and-export-print-layouts-in-python-for-qgis-3/
    map = QgsLayoutItemMap(layout)
    # I have no idea what this does, but it is necessary
    map.setRect(20, 20, 20, 20)

    map.setBackgroundColor(color)

    # set layers to render
    map.setLayers(layerList)

    # set extent
    if not extent:
        extent = layerList[0].extent()
        #print('in layoutToImage',extent)
        for lay in layerList:
            if not extent.contains(lay.extent()):
                extent.combineExtentWith(lay.extent())

        extent.scale(1.1)

    layout.addLayoutItem(map)

    # Move & Resize map on print layout canvas
    map.attemptMove(QgsLayoutPoint(0, 0, paperUnit))
    map.attemptResize(QgsLayoutSize(map_w, map_h, paperUnit))
    map.setFixedSize(QgsLayoutSize(map_w, map_h, paperUnit)) # fix frame dimension to force scaling

    # adjust map extention
    map.setExtent(extent)
    # calculate max scale factor to fit extent
    #print('ext. fact.:', extent.width() / (map_w / 1000), extent.height() / (map_h / 1000))
    scaleFact = max(extent.width() / (map_w / 1000), extent.height() / (map_h / 1000))
    map.setScale(scaleFact)

    # add legend
    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("")

    layerTree = QgsLayerTree()
    for layer in layerList:  # add layers that you want to see in legend
        layerTree.addLayer(layer)

    legend.model().setRootGroup(layerTree)
    layout.addLayoutItem(legend)

    # Move & Resize legend on print layout canvas
    legend.attemptMove(QgsLayoutPoint(map_w, 0, paperUnit))
    legend.attemptResize(QgsLayoutSize(leg_w, leg_h, paperUnit))

    scalebar = QgsLayoutItemScaleBar(layout)
    scalebar.setStyle('Line Ticks Up')
    scalebar.setUnits(QgsUnitTypes.DistanceKilometers)
    scalebar.setNumberOfSegments(1)
    scalebar.setMaximumBarWidth(width-map_w)
    scalebar.setNumberOfSegmentsLeft(0)
    bar_w = (1/3)*extent.width()/1000
    if bar_w<1: bar_w=round(bar_w,1)
    else: bar_w=round(bar_w)

    scalebar.setUnitsPerSegment(bar_w)
    scalebar.setLinkedMap(map)
    scalebar.setUnitLabel('km')
    scalebar.update()
    layout.addLayoutItem(scalebar)
    scalebar.attemptMove(QgsLayoutPoint(map_w, map_h*2/3, paperUnit))


    exporter = QgsLayoutExporter(layout)
    #print('exp. settings:',QgsLayoutExporter.ImageExportSettings())
    newSettings = QgsLayoutExporter.ImageExportSettings()
    #newSettings.imageSize = QSize(600,1000)
    newSettings.dpi = 92

    exporter.exportToImage(imageFile, newSettings)
