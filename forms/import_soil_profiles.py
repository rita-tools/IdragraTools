"""Column-mapped import of soil profiles from Excel or CSV."""

import os
import sqlite3
from contextlib import closing

import pandas as pd
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from ..tools.soil_profile_importer import (
    PROFILE_FIELDS, import_profiles, parse_profiles, read_profile_table,
)


class ImportSoilProfiles(QDialog):
    dataImported = pyqtSignal(object)

    def __init__(self, parent, database_path, layers, soil_ids=None, settings=None):
        super().__init__(parent)
        self.database_path = database_path
        self.layers = layers
        self.soil_ids = soil_ids or set()
        self.settings = settings
        self.frame = None
        self.profiles = None
        self.names = {}
        self.setWindowTitle(self.tr('Import soil profiles'))
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        form = QFormLayout()
        file_row = QHBoxLayout()
        self.filename = QLineEdit(self)
        browse = QPushButton(self.tr('Browse…'), self)
        file_row.addWidget(self.filename)
        file_row.addWidget(browse)
        form.addRow(self.tr('File'), file_row)
        self.sheet = QComboBox(self)
        form.addRow(self.tr('Worksheet'), self.sheet)
        self.separator = QLineEdit(';', self)
        form.addRow(self.tr('CSV separator'), self.separator)
        self.header_rows = QSpinBox(self)
        self.header_rows.setRange(0, 10000)
        form.addRow(self.tr('Rows before header'), self.header_rows)
        self.decimal = QComboBox(self)
        self.decimal.addItems(['.', ','])
        form.addRow(self.tr('Decimal separator'), self.decimal)
        layout.addLayout(form)

        labels = [self.tr('Soil type ID'), self.tr('Layer bottom depth (m)'),
                  self.tr('Saturated conductivity (cm/hour)'), self.tr('Field capacity (m3/m3)'),
                  self.tr('Wilting point (m3/m3)'), self.tr('Residual water content (m3/m3)'),
                  self.tr('Saturated water content (m3/m3)'), self.tr('USDA texture code (1–12)'),
                  self.tr('Soil type name (optional)')]
        self.fields = PROFILE_FIELDS + ('soil_name',)
        self.mapping = QTableWidget(len(self.fields), 2, self)
        self.mapping.setHorizontalHeaderLabels([self.tr('Destination field'), self.tr('Source column')])
        self.mapping.verticalHeader().hide()
        self.mapping.horizontalHeader().setStretchLastSection(True)
        self.mapping.setColumnWidth(0, 290)
        available_height = QApplication.primaryScreen().availableGeometry().height()
        self.mapping.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.selectors = {}
        for index, (field, label) in enumerate(zip(self.fields, labels)):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.mapping.setItem(index, 0, item)
            selector = QComboBox(self.mapping)
            selector.currentIndexChanged.connect(self.update_preview)
            self.mapping.setCellWidget(index, 1, selector)
            self.selectors[field] = selector
        self.mapping.resizeRowsToContents()
        mapping_height = (self.mapping.horizontalHeader().sizeHint().height()
                          + self.mapping.verticalHeader().length()
                          + 2 * self.mapping.frameWidth())
        self.mapping.setFixedHeight(min(mapping_height, max(180, available_height - 470)))
        layout.addWidget(self.mapping)
        self.preview = QTableWidget(self)
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview.setFixedHeight(110)
        layout.addWidget(self.preview)
        self.replace = QCheckBox(self.tr('Overwrite existing profiles'), self)
        self.replace.setToolTip(self.tr('Replaces all depth layers for soil IDs in this file. Other soils are kept.'))
        layout.addWidget(self.replace)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        self.import_button = self.buttons.addButton(self.tr('Import'), QDialogButtonBox.ActionRole)
        self.import_button.setEnabled(False)
        layout.addWidget(self.buttons)
        browse.clicked.connect(self.browse)
        self.filename.editingFinished.connect(self.load_file)
        self.sheet.currentIndexChanged.connect(self.read_table)
        self.separator.editingFinished.connect(self.read_table)
        self.header_rows.valueChanged.connect(self.read_table)
        self.decimal.currentIndexChanged.connect(self.update_preview)
        self.import_button.clicked.connect(self.import_data)
        self.buttons.rejected.connect(self.reject)
        self.resize(780, min(layout.sizeHint().height(), available_height - 60))

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr('Import soil profiles'),
            self.settings.value('lastPath') if self.settings else '',
            self.tr('Soil profiles (*.xlsx *.csv *.txt)'))
        if path:
            self.filename.setText(path)
            if self.settings:
                self.settings.setValue('lastPath', os.path.dirname(path))
            self.load_file()

    def load_file(self):
        self.sheet.blockSignals(True)
        self.sheet.clear()
        try:
            excel = self.filename.text().lower().endswith('.xlsx')
            if excel:
                with pd.ExcelFile(self.filename.text()) as book:
                    self.sheet.addItems(book.sheet_names)
            self.sheet.setEnabled(excel)
            self.separator.setEnabled(not excel)
        except Exception as error:
            self.frame = None
            self.status.setText(str(error))
            self.import_button.setEnabled(False)
            return
        finally:
            self.sheet.blockSignals(False)
        self.read_table()

    def read_table(self):
        try:
            self.frame = read_profile_table(self.filename.text(), self.sheet.currentText() or 0,
                self.separator.text(), self.header_rows.value())
            for field, selector in self.selectors.items():
                previous = selector.currentText()
                selector.blockSignals(True)
                selector.clear()
                selector.addItem(self.tr('Select column'), None)
                for index, column in enumerate(self.frame.columns):
                    selector.addItem(str(column), index)
                match = selector.findText(previous) if previous else -1
                selector.setCurrentIndex(max(0, match))
                selector.blockSignals(False)
        except Exception as error:
            self.frame = None
            self.status.setText(str(error))
            self.import_button.setEnabled(False)
            return
        self.update_preview()

    def update_preview(self):
        self.import_button.setEnabled(False)
        self.profiles = None
        if self.frame is None:
            return
        mappings = {field: selector.currentData() for field, selector in self.selectors.items()}
        self.preview.setColumnCount(len(self.fields))
        self.preview.setHorizontalHeaderLabels(list(self.fields))
        self.preview.setRowCount(min(5, len(self.frame)))
        for row in range(self.preview.rowCount()):
            for column, field in enumerate(self.fields):
                source = mappings[field]
                value = '' if source is None else self.frame.iloc[row, source]
                self.preview.setItem(row, column, QTableWidgetItem('' if pd.isna(value) else str(value)))
        try:
            self.profiles, self.names = parse_profiles(self.frame, mappings,
                self.header_rows.value(), self.decimal.currentText())
            self.status.setText(self.tr('%s soil profiles, %s horizons ready.') %
                (len(self.profiles), sum(map(len, self.profiles.values()))))
            self.import_button.setEnabled(True)
        except ValueError as error:
            self.status.setText(str(error))

    def import_data(self):
        if not self.profiles:
            return
        if any(layer.isModified() for layer in self.layers):
            QMessageBox.warning(self, self.tr('Pending edits'),
                self.tr('Save or discard edits to Soil types and Soil profiles before importing.'))
            return
        try:
            with closing(sqlite3.connect(self.database_path)) as connection:
                existing_ids = {row[0] for row in connection.execute('SELECT DISTINCT soilid FROM idr_soil_profiles')}
            missing = self.soil_ids - existing_ids - set(self.profiles)
            if missing:
                answer = QMessageBox.question(self, self.tr('Missing soil profiles'),
                    self.tr('Map soil IDs without profiles: %s. Import the available profiles anyway?') %
                    ', '.join(map(str, sorted(missing))), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes:
                    return
            result = import_profiles(self.database_path, self.profiles, self.names,
                replace_existing=self.replace.isChecked())
        except Exception as error:
            QMessageBox.warning(self, self.tr('Import failed'), str(error))
            return
        for layer in self.layers:
            layer.dataProvider().reloadData()
            layer.triggerRepaint()
        self.dataImported.emit({'idr_soil_types', 'idr_soil_profiles'})
        self.status.setText(self.tr('Saved %s profiles (%s horizons); created %s soil types; skipped %s existing profiles.') %
            (result['profiles'], result['horizons'], result['types'], result['skipped']))
