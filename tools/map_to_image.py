from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QImage, QColor, QPainter
from qgis.core import QgsMapSettings, QgsProject, QgsRectangle, QgsMapRendererCustomPainterJob


def mapToImage(layerList,imageFile,extent = None):
    # create image
    img = QImage(QSize(800, 800), QImage.Format_ARGB32_Premultiplied)

    # set background color
    color = QColor(255, 255, 255, 255)
    img.fill(color.rgba())

    # create painter
    p = QPainter()
    p.begin(img)
    p.setRenderHint(QPainter.Antialiasing)

    # create map settings
    ms = QgsMapSettings()
    ms.setBackgroundColor(color)

    # set layers to render
    ms.setLayers(layerList)

    # set extent
    if not extent:
        extent = QgsRectangle(ms.fullExtent())
        extent.scale(1.1)

    ms.setExtent(extent)

    # set ouptut size
    ms.setOutputSize(img.size())

    # setup qgis map renderer
    render = QgsMapRendererCustomPainterJob(ms, p)
    render.start()
    render.waitForFinished()
    p.end()

    # save the image
    img.save(imageFile)