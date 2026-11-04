# -*- coding: utf-8 -*-

import csv
import os
from datetime import datetime

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QHBoxLayout, QLabel, QMessageBox, QTableWidget,
    QTableWidgetItem, QWidget,
)

from ..tools.timeseries_importer import (
    TimeSeriesImportError, csv_files_in_folder, import_jobs,
    normalized_separator, read_header, station_id_from_filename,
)


class ImportData(QDialog):
    closed = pyqtSignal()
    dataImported = pyqtSignal(object)

    def __init__(self, parent=None, vars=None, sensors=None, settings=None, databasePath=''):
        super().__init__(parent)
        uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'import_data.ui'))
        uic.loadUi(uiFilePath, self)

        self.VARS = vars or {}
        self.SENSORS = sensors or {}
        self.s = settings
        self.databasePath = databasePath
        self.columns = []

        self._buildModeSelector()
        self._buildTimestampSelector()
        self._buildMappingTable()
        self._configureExistingWidgets()
        self._connectSignals()
        self.resize(820, 720)
        self.refreshColumns()

    def _buildModeSelector(self):
        modeWidget = QWidget(self)
        modeLayout = QHBoxLayout(modeWidget)
        modeLayout.setContentsMargins(0, 0, 0, 0)
        self.BULK_CB = QCheckBox(self.tr('Bulk mode'), modeWidget)
        modeLayout.addWidget(self.BULK_CB)
        modeLayout.addStretch(1)
        self.verticalLayout.insertWidget(0, modeWidget)

    def _buildTimestampSelector(self):
        self.TC_LBL.setText(self.tr('Timestamp column'))
        self.TC_SB.hide()
        self.VC_LBL.hide()
        self.VC_SB.hide()
        self.TIMESTAMP_CB = QComboBox(self.widget_2)
        self.horizontalLayout_3.insertWidget(1, self.TIMESTAMP_CB, 1)

    def _buildMappingTable(self):
        self.MAPPING_LBL = QLabel(self.tr('Variable mappings'), self)
        self.MAPPING_TBL = QTableWidget(len(self.VARS), 3, self)
        self.MAPPING_TBL.setHorizontalHeaderLabels([
            self.tr('Import'), self.tr('Destination variable'), self.tr('Source column')
        ])
        self.MAPPING_TBL.verticalHeader().setVisible(False)
        self.MAPPING_TBL.verticalHeader().setDefaultSectionSize(28)
        self.MAPPING_TBL.horizontalHeader().setStretchLastSection(True)
        self.MAPPING_TBL.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.MAPPING_TBL.setColumnWidth(0, 65)
        self.MAPPING_TBL.setColumnWidth(1, 260)

        for row, (tableName, label) in enumerate(self.VARS.items()):
            enabled = QCheckBox(self.MAPPING_TBL)
            self.MAPPING_TBL.setCellWidget(row, 0, enabled)
            destination = QTableWidgetItem(label)
            destination.setData(Qt.UserRole, tableName)
            destination.setFlags(destination.flags() & ~Qt.ItemIsEditable)
            self.MAPPING_TBL.setItem(row, 1, destination)
            sourceColumn = QComboBox(self.MAPPING_TBL)
            sourceColumn.currentTextChanged.connect(
                lambda text, checkbox=enabled: checkbox.setChecked(bool(text))
            )
            self.MAPPING_TBL.setCellWidget(row, 2, sourceColumn)

        idealHeight = (
            self.MAPPING_TBL.horizontalHeader().sizeHint().height()
            + self.MAPPING_TBL.rowCount() * self.MAPPING_TBL.verticalHeader().defaultSectionSize()
            + 2 * self.MAPPING_TBL.frameWidth() + 4
        )
        availableHeight = QApplication.primaryScreen().availableGeometry().height()
        mappingHeight = min(idealHeight, max(160, int(availableHeight * 0.4)))
        self.MAPPING_TBL.setMinimumHeight(mappingHeight)
        self.MAPPING_TBL.setMaximumHeight(mappingHeight)

        previewLabelIndex = self.verticalLayout.indexOf(self.label)
        self.verticalLayout.insertWidget(previewLabelIndex, self.MAPPING_LBL)
        self.verticalLayout.insertWidget(previewLabelIndex + 1, self.MAPPING_TBL)

    def _configureExistingWidgets(self):
        self.widget_5.hide()
        self.SAVEEDIT_CB.hide()
        timestampRowIndex = self.verticalLayout.indexOf(self.widget_2)
        self.verticalLayout.removeWidget(self.widget_4)
        self.verticalLayout.insertWidget(timestampRowIndex, self.widget_4)
        self.SKIPLINES_LBL.setText(self.tr('Rows before header'))
        self.OVERWRITE_CB.setText(self.tr('Overwrite existing values'))
        self.SENSOR_CB.clear()
        for stationId, label in self.SENSORS.items():
            self.SENSOR_CB.addItem(label, stationId)
        if self.FORMAT_TXT.findText('%Y-%m-%d') < 0:
            self.FORMAT_TXT.insertItem(0, '%Y-%m-%d')
        self.FORMAT_TXT.setCurrentText('%Y-%m-%d')
        self.TABLE_PREVIEW.setColumnCount(1)
        self.TABLE_PREVIEW.setHorizontalHeaderLabels([self.tr('Timestamp')])
        self.TABLE_PREVIEW.setMinimumHeight(100)
        self.TABLE_PREVIEW.setMaximumHeight(170)
        self.label.setText(self.tr('Imported data preview (destination variables)'))
        importButton = self.buttonBox.button(QDialogButtonBox.Ok)
        importButton.setText(self.tr('Import'))
        importButton.setEnabled(False)
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(self.tr('Close'))

    def _connectSignals(self):
        self.SELFILE_BTN.clicked.connect(self.setInputSource)
        self.BULK_CB.toggled.connect(self.modeChanged)
        self.SELFILE_TXT.editingFinished.connect(self.refreshColumns)
        self.SKIPLINES_SB.valueChanged.connect(self.refreshColumns)
        self.SEP_TXT.editingFinished.connect(self.refreshColumns)
        self.FORMAT_TXT.currentTextChanged.connect(self.refreshPreview)
        self.TIMESTAMP_CB.currentTextChanged.connect(self.refreshPreview)
        self.buttonBox.accepted.connect(self.runImport)
        self.buttonBox.rejected.connect(self.reject)
        for row in range(self.MAPPING_TBL.rowCount()):
            self.MAPPING_TBL.cellWidget(row, 0).toggled.connect(self.refreshPreview)
            self.MAPPING_TBL.cellWidget(row, 2).currentTextChanged.connect(self.refreshPreview)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def isFolderMode(self):
        return self.BULK_CB.isChecked()

    def modeChanged(self, folderMode):
        if folderMode:
            response = QMessageBox.question(
                self,
                self.tr('Enable bulk import?'),
                self.tr(
                    'Bulk mode imports every CSV file in the selected folder.\n\n'
                    'Each filename must be a measuring-point ID (for example 100.csv), '
                    'and every file must use the same header and column structure. '
                    'Mappings and the preview are based on the first CSV file.'
                ),
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Ok,
            )
            if response != QMessageBox.Ok:
                self.BULK_CB.blockSignals(True)
                self.BULK_CB.setChecked(False)
                self.BULK_CB.blockSignals(False)
                return
        self.SENSOR_CB.setEnabled(not folderMode)
        self.SENSOR_LBL.setEnabled(not folderMode)
        self.SELFILE_LBL.setText(self.tr('Source folder') if folderMode else self.tr('Source file'))
        self.SELFILE_TXT.clear()
        self.refreshColumns()

    def setInputSource(self):
        lastPath = self.s.value('lastPath', '') if self.s else ''
        if self.isFolderMode():
            selected = QFileDialog.getExistingDirectory(self, self.tr('Import from folder'), lastPath)
        else:
            selected, _ = QFileDialog.getOpenFileName(
                self, self.tr('Import from'), lastPath,
                self.tr('CSV files (*.csv);;All files (*.*)')
            )
        if selected:
            self.SELFILE_TXT.setText(selected)
            if self.s:
                lastPath = selected if self.isFolderMode() else os.path.dirname(selected)
                self.s.setValue('lastPath', lastPath)
            self.refreshColumns()

    def previewFilename(self):
        source = self.SELFILE_TXT.text().strip()
        if self.isFolderMode():
            files = csv_files_in_folder(source) if os.path.isdir(source) else []
            return files[0] if files else ''
        return source if os.path.isfile(source) else ''

    @staticmethod
    def _normalizedName(value):
        return ''.join(character for character in value.lower() if character.isalnum())

    def _automaticColumn(self, tableName, label):
        candidates = {
            self._normalizedName(tableName),
            self._normalizedName(tableName.replace('ws_', '').replace('node_', '')),
            self._normalizedName(label),
        }
        for column in self.columns:
            if self._normalizedName(column) in candidates:
                return column
        return ''

    def refreshColumns(self, *args):
        filename = self.previewFilename()
        if self.isFolderMode() and filename:
            self.MAPPING_LBL.setText(
                self.tr('Variable mappings — columns from %s, applied to every CSV file') %
                os.path.basename(filename)
            )
        else:
            self.MAPPING_LBL.setText(self.tr('Variable mappings'))
        hadColumns = bool(self.columns)
        previousTimestamp = self.TIMESTAMP_CB.currentText()
        previousMappings = {
            self.MAPPING_TBL.item(row, 1).data(Qt.UserRole):
            self.MAPPING_TBL.cellWidget(row, 2).currentText()
            for row in range(self.MAPPING_TBL.rowCount())
        }
        previousEnabled = {
            self.MAPPING_TBL.item(row, 1).data(Qt.UserRole):
            self.MAPPING_TBL.cellWidget(row, 0).isChecked()
            for row in range(self.MAPPING_TBL.rowCount())
        }
        try:
            self.columns = read_header(
                filename, self.SEP_TXT.text(), self.SKIPLINES_SB.value()
            ) if filename else []
            errorText = ''
        except TimeSeriesImportError as error:
            self.columns = []
            errorText = str(error)

        self.TIMESTAMP_CB.blockSignals(True)
        self.TIMESTAMP_CB.clear()
        self.TIMESTAMP_CB.addItems(self.columns)
        timestampColumn = previousTimestamp if previousTimestamp in self.columns else ''
        if not timestampColumn:
            timestampCandidates = {'timestamp', 'date', '#date', 'datetime'}
            for column in self.columns:
                if column.lower() in timestampCandidates:
                    timestampColumn = column
                    break
        if timestampColumn:
            self.TIMESTAMP_CB.setCurrentText(timestampColumn)
        self.TIMESTAMP_CB.blockSignals(False)

        for row in range(self.MAPPING_TBL.rowCount()):
            tableName = self.MAPPING_TBL.item(row, 1).data(Qt.UserRole)
            label = self.MAPPING_TBL.item(row, 1).text()
            combo = self.MAPPING_TBL.cellWidget(row, 2)
            checkbox = self.MAPPING_TBL.cellWidget(row, 0)
            previous = previousMappings.get(tableName, '')
            selected = previous if previous in self.columns else self._automaticColumn(tableName, label)
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('')
            combo.addItems(self.columns)
            combo.setCurrentText(selected)
            combo.blockSignals(False)
            enabled = previousEnabled.get(tableName, False) if hadColumns else bool(selected)
            checkbox.setChecked(enabled and bool(selected))

        if errorText:
            self.MSG_LBL.setText(errorText)
        self.refreshPreview()

    def selectedMappings(self):
        mappings = {}
        for row in range(self.MAPPING_TBL.rowCount()):
            if not self.MAPPING_TBL.cellWidget(row, 0).isChecked():
                continue
            tableName = self.MAPPING_TBL.item(row, 1).data(Qt.UserRole)
            sourceColumn = self.MAPPING_TBL.cellWidget(row, 2).currentText()
            if sourceColumn:
                mappings[tableName] = sourceColumn
        return mappings

    def selectedMappingDetails(self):
        details = []
        for row in range(self.MAPPING_TBL.rowCount()):
            if not self.MAPPING_TBL.cellWidget(row, 0).isChecked():
                continue
            destination = self.MAPPING_TBL.item(row, 1)
            sourceColumn = self.MAPPING_TBL.cellWidget(row, 2).currentText()
            if sourceColumn:
                details.append((destination.data(Qt.UserRole), destination.text(), sourceColumn))
        return details

    def refreshPreview(self, *args):
        filename = self.previewFilename()
        mappingDetails = self.selectedMappingDetails()
        mappings = {tableName: sourceColumn for tableName, _, sourceColumn in mappingDetails}
        timestampColumn = self.TIMESTAMP_CB.currentText()
        sourceColumns = [timestampColumn] + [detail[2] for detail in mappingDetails] if timestampColumn else []
        previewHeaders = [self.tr('Timestamp')] + [detail[1] for detail in mappingDetails] if timestampColumn else []
        self.TABLE_PREVIEW.clearContents()
        self.TABLE_PREVIEW.setRowCount(0)
        self.TABLE_PREVIEW.setColumnCount(max(1, len(sourceColumns)))
        self.TABLE_PREVIEW.setHorizontalHeaderLabels(previewHeaders or [self.tr('Timestamp')])
        for columnIndex, sourceColumn in enumerate(sourceColumns):
            headerItem = self.TABLE_PREVIEW.horizontalHeaderItem(columnIndex)
            if headerItem:
                headerItem.setToolTip(self.tr('Source column: %s') % sourceColumn)

        stationReady = self.isFolderMode() or self.SENSOR_CB.currentData() is not None
        valid = bool(filename and timestampColumn and mappings and stationReady)
        message = ''
        if valid:
            try:
                separator = normalized_separator(self.SEP_TXT.text())
                indexes = {name: self.columns.index(name) for name in sourceColumns}
                with open(filename, 'r', encoding='utf-8-sig', newline='') as source:
                    reader = csv.reader(source, delimiter=separator)
                    for _ in range(self.SKIPLINES_SB.value() + 1):
                        next(reader)
                    for rowIndex, values in enumerate(reader):
                        if rowIndex >= 20:
                            break
                        if not values or not any(value.strip() for value in values):
                            continue
                        displayValues = []
                        for column in sourceColumns:
                            value = values[indexes[column]].strip()
                            if column == timestampColumn:
                                value = datetime.strptime(
                                    value, self.FORMAT_TXT.currentText()
                                ).strftime('%Y-%m-%d')
                            elif value:
                                float(value)
                            displayValues.append(value)
                        tableRow = self.TABLE_PREVIEW.rowCount()
                        self.TABLE_PREVIEW.insertRow(tableRow)
                        for columnIndex, value in enumerate(displayValues):
                            self.TABLE_PREVIEW.setItem(tableRow, columnIndex, QTableWidgetItem(value))
                message = self.tr('Ready to import %s variable(s).') % len(mappings)
            except Exception as error:
                valid = False
                message = self.tr('Preview error: %s') % error
        elif filename and not mappings:
            message = self.tr('Select at least one variable mapping.')
        self.MSG_LBL.setText(message)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(valid)

    def _jobs(self):
        mappings = self.selectedMappings()
        common = {
            'separator': self.SEP_TXT.text(),
            'rows_before_header': self.SKIPLINES_SB.value(),
            'timestamp_column': self.TIMESTAMP_CB.currentText(),
            'mappings': mappings,
            'time_format': self.FORMAT_TXT.currentText(),
        }
        if self.isFolderMode():
            files = csv_files_in_folder(self.SELFILE_TXT.text().strip())
            if not files:
                raise TimeSeriesImportError('The selected folder contains no CSV files.')
            return [dict(
                common, filename=filename,
                station_id=station_id_from_filename(filename, self.SENSORS.keys())
            ) for filename in files]
        stationId = self.SENSOR_CB.currentData()
        if stationId is None:
            raise TimeSeriesImportError('Select a measuring point.')
        return [dict(common, filename=self.SELFILE_TXT.text().strip(), station_id=stationId)]

    def runImport(self):
        importButton = self.buttonBox.button(QDialogButtonBox.Ok)
        importButton.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            mappings = self.selectedMappings()
            summary = import_jobs(
                self.databasePath, self._jobs(), self.OVERWRITE_CB.isChecked()
            )
            totals = {
                key: sum(item[key] for item in summary.values())
                for key in ('inserted', 'updated', 'existing_skipped', 'empty_skipped')
            }
            message = self.tr(
                'Import completed: %(inserted)s inserted, %(updated)s updated, '
                '%(existing_skipped)s existing skipped, %(empty_skipped)s empty skipped.'
            ) % totals
            self.MSG_LBL.setText(message)
            self.dataImported.emit(list(mappings))
        except Exception as error:
            self.MSG_LBL.setText(self.tr('Import failed: %s') % error)
            QMessageBox.critical(self, self.tr('Unable to import data'), str(error))
        finally:
            QApplication.restoreOverrideCursor()
            importButton.setEnabled(True)
