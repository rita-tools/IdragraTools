import glob
import os
import shutil

from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
from qgis.PyQt.QtWidgets import QApplication, QMainWindow, QFileDialog
from qgis.PyQt.QtCore import QUrl, pyqtSignal

from ..qt_compat import QAction

from ..tools.show_message import showCriticalMessageBox, showInfoMessageBox


class ReportDialog(QMainWindow):
    closed = pyqtSignal()
    accepted = pyqtSignal()
    rejected = pyqtSignal()

    def __init__(self, parent = None,url = None):
        QMainWindow.__init__(self, parent)
        self.setWindowTitle('IdrAgra Tools')
        self.current_url = ''
        self.initMenu()

        self.REPORT_WV = QWebEngineView(self)
        self.REPORT_WV.loadFinished.connect(self.reportLoaded)
        self.REPORT_WV.page().pdfPrintingFinished.connect(self.pdfPrintingFinished)
        # adjust scale factor
        screen = QApplication.primaryScreen()

        screenRes = screen.logicalDotsPerInch()
        scaleFact = screenRes / 96.

        self.REPORT_WV.setZoomFactor(scaleFact)

        self.setCentralWidget(self.REPORT_WV)
        if url: self.loadReport(url)

    def initMenu(self):
        saveAsHtmlAct= QAction('&Save as html', self)
        saveAsHtmlAct.setShortcut('Ctrl+S')
        saveAsHtmlAct.setStatusTip('Save as htnml file')
        saveAsHtmlAct.triggered.connect(self.saveAsHtml)

        self.saveAsPdfAct = QAction('&Save as pdf', self)
        self.saveAsPdfAct.setShortcut('Ctrl+P')
        self.saveAsPdfAct.setStatusTip('Save as PDF file')
        self.saveAsPdfAct.setEnabled(False)
        self.saveAsPdfAct.triggered.connect(self.saveAsPdf)

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(saveAsHtmlAct)
        fileMenu.addAction(self.saveAsPdfAct)

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
            self.saveAsPdfAct.setEnabled(False)
            self.REPORT_WV.page().printToPdf(filename)

    def reportLoaded(self, success):
        self.saveAsPdfAct.setEnabled(success)

    def pdfPrintingFinished(self, filename, success):
        self.saveAsPdfAct.setEnabled(True)
        if success:
            showInfoMessageBox(self.tr('Concluded!'), self.tr('File saved to %s') % filename)
        else:
            showCriticalMessageBox(self.tr('Unable to save the report'),
                                   self.tr('PDF export failed for %s') % filename, '')

    def loadReport(self,url):
        self.current_url = url
        self.REPORT_WV.load(QUrl.fromLocalFile(self.current_url))

if __name__ == '__main__':
    pass
