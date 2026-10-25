import glob
import os
import shutil

from qgis.PyQt import Qt
#from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtPrintSupport import QPrinter
from qgis.PyQt.QtWebKitWidgets import QWebView
from qgis.PyQt.QtWidgets import QApplication, QMainWindow, QFileDialog, QTextBrowser
from qgis.PyQt.QtCore import QUrl, pyqtSignal

from ..qt_compat import QAction

# if hasattr(Qt, 'AA_EnableHighDpiScaling'):
#     QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
#
# if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
#     QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
from ..tools.show_message import showInfoMessageBox


class ReportDialog(QMainWindow):
    closed = pyqtSignal()
    accepted = pyqtSignal()
    rejected = pyqtSignal()

    def __init__(self, parent = None,url = None):
        QMainWindow.__init__(self, parent)
        self.setWindowTitle('IdrAgra Tools')
        self.current_url = ''
        self.initMenu()

        self.REPORT_WV = QWebView(self)
        # adjust scale factor
        screen = QApplication.primaryScreen()

        screenRes = screen.logicalDotsPerInch()
        scaleFact = screenRes / 96.

        self.REPORT_WV.setZoomFactor(scaleFact)

        self.setCentralWidget(self.REPORT_WV)
        if url: self.loadReport(QUrl(url))

    def initMenu(self):
        saveAsHtmlAct= QAction('&Save as html', self)
        saveAsHtmlAct.setShortcut('Ctrl+S')
        saveAsHtmlAct.setStatusTip('Save as htnml file')
        saveAsHtmlAct.triggered.connect(self.saveAsHtml)

        saveAsPdfAct = QAction('&Save as pdf', self)
        saveAsPdfAct.setShortcut('Ctrl+P')
        saveAsPdfAct.setStatusTip('Save as PDF file')
        saveAsPdfAct.triggered.connect(self.saveAsPdf)

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(saveAsHtmlAct)
        fileMenu.addAction(saveAsPdfAct)

    def saveAsHtml(self):
        filename, _ = QFileDialog.getSaveFileName(filter='HTML file (*.html)')
        if filename:
            # get image folder from current file
            sourceBaseName = os.path.basename(self.current_url)
            destBaseName = os.path.basename(filename)
            sourceImgFolder = self.current_url[:-5]+'_img'
            destImgFolder = filename[:-5] + '_img'

            if not os.path.exists(destImgFolder):
                os.mkdir(destImgFolder)
            else:
                # delete all files inside
                files = glob.glob(os.path.join(destImgFolder, '*.*'))
                for f in files:
                    try: os.remove(f)
                    except: pass

            # copy all file from source to dest
            for fileToCopy in glob.glob(os.path.join(sourceImgFolder, '*.*')):
                shutil.copy(fileToCopy, destImgFolder)

            # copy current_html to new file
            sourceImgFolder = os.path.basename(sourceImgFolder)
            destImgFolder = os.path.basename(destImgFolder)

            destTxt = ''
            with open(self.current_url,'r') as f:
                sourceTxt = f.read()
                destTxt = sourceTxt.replace(sourceImgFolder,destImgFolder)

            with open(filename,'w') as f:
                f.write(destTxt)

            showInfoMessageBox(self.tr('Concluded!'),self.tr('File saved to %s')%filename)

    def saveAsPdf(self):
        filename, _ = QFileDialog.getSaveFileName(filter='Pdf file (*.pdf)')
        if filename:
            # Initialize printer and set save location
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFileName(filename)
            printer.setPaperSize(QPrinter.A4)

            self.REPORT_WV.print(printer)

            showInfoMessageBox(self.tr('Concluded!'),self.tr('File saved to %s')%filename)

    def loadReport(self,url):
        self.current_url = url
        self.REPORT_WV.load(QUrl.fromLocalFile(self.current_url))

if __name__ == '__main__':
    pass
