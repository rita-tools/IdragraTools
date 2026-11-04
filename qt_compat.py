"""Compatibility imports for Qt classes moved between Qt 5 and Qt 6."""

# Qt5 stores QAction in QtWidgets; Qt6 moved in QtGui. Try both imports.
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction
