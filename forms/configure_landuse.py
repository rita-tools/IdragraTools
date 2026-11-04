"""Assign crop sequences to the land-use classes present in a project's map."""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from ..tools.landuse_library import crop_display_name, import_crops, read_crop_file, read_library, save_assignments


def read_only_item(text):
    item = QTableWidgetItem(str(text))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


def reload_layers(layers):
    for layer in layers:
        layer.dataProvider().reloadData()
        layer.triggerRepaint()


class ImportParameterLibrary(QDialog):
    TITLE = 'Import crop parameters'
    ITEM_LABEL = 'Crop'
    FILE_SUFFIX = '.tab'
    REPLACE_LABEL = 'Replace crop library'
    FOLDER_LABEL = 'Crop parameter folder'
    EXCLUDED_FILES = set()
    read_record = staticmethod(read_crop_file)

    def __init__(self, parent, database_path, preset_folder, layers, settings):
        super().__init__(parent)
        self.database_path = database_path
        self.preset_folder = preset_folder
        self.layers = layers
        self.settings = settings
        self.records = {}
        self.setWindowTitle(self.tr(self.TITLE))
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.source = QComboBox(self)
        self.source.addItems([self.tr('Bundled presets'), self.tr('Folder of %s files') % self.FILE_SUFFIX])
        self.browse_button = QPushButton(self.tr('Choose folder…'), self)
        self.browse_button.setEnabled(False)
        controls.addWidget(self.source)
        controls.addWidget(self.browse_button)
        layout.addLayout(controls)
        self.path_label = QLabel(self)
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels([self.tr(self.ITEM_LABEL), self.tr('File')])
        self.table.verticalHeader().hide()
        self.table.setColumnWidth(0, 270)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        self.import_button = self.buttons.addButton(self.tr(self.REPLACE_LABEL), QDialogButtonBox.ActionRole)
        layout.addWidget(self.buttons)
        self.buttons.rejected.connect(self.reject)
        self.source.currentIndexChanged.connect(self.change_source)
        self.browse_button.clicked.connect(self.choose_folder)
        self.import_button.clicked.connect(self.import_selected)
        self.table.itemChanged.connect(self.update_button)
        self.load_folder(preset_folder)
        self.resize(740, 480)

    def change_source(self):
        self.browse_button.setEnabled(self.source.currentIndex() == 1)
        if self.source.currentIndex() == 0:
            self.load_folder(self.preset_folder)
        else:
            self.records.clear()
            self.table.setRowCount(0)
            self.path_label.clear()
            self.update_button()
            self.choose_folder()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, self.tr(self.FOLDER_LABEL),
            self.settings.value('lastPath') if self.settings else '')
        if path:
            if self.settings:
                self.settings.setValue('lastPath', path)
            self.load_folder(path)

    def load_folder(self, path):
        self.records.clear()
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.path_label.setText(path)
        try:
            suffix = '.txt' if self.source.currentIndex() == 0 else self.FILE_SUFFIX
            files = sorted(name for name in os.listdir(path)
                           if name.lower().endswith(suffix) and name.lower() not in self.EXCLUDED_FILES)
            for filename in files:
                row = self.table.rowCount()
                self.table.insertRow(row)
                item = read_only_item(filename)
                try:
                    item.setText(self.read_record(os.path.join(path, filename))['name'])
                except Exception:
                    pass  # Report file errors on import, so it can still be unchecked.
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.records[row] = os.path.join(path, filename)
                self.table.setItem(row, 0, item)
                self.table.setItem(row, 1, read_only_item(filename))
        except Exception as error:
            QMessageBox.warning(self, self.tr('Unable to list parameter files'), str(error))
        finally:
            self.table.blockSignals(False)
        self.update_button()

    def update_button(self):
        self.import_button.setEnabled(any(self.table.item(row, 0).checkState() == Qt.Checked
                                         for row in self.records))

    def import_selected(self):
        if any(layer.isModified() for layer in self.layers):
            QMessageBox.warning(self, self.tr('Pending edits'), self.tr('Save or discard pending parameter edits first.'))
            return
        selected = [record for row, record in self.records.items()
                    if self.table.item(row, 0).checkState() == Qt.Checked]
        if not selected:
            return
        try:
            parameters = [self.read_record(filename) for filename in selected]
            parameters = self.prepare_records(parameters)
            if parameters is None:
                return
            answer = QMessageBox.question(self, self.tr(self.REPLACE_LABEL),
                self.confirmation_message(parameters, selected),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            self.replace_records(parameters)
        except Exception as error:
            QMessageBox.warning(self, self.tr('Import failed'), str(error))
            return
        reload_layers(self.layers)
        self.accept()

    def prepare_records(self, parameters):
        return parameters


class ImportCrops(ImportParameterLibrary):
    def confirmation_message(self, parameters, filenames):
        message = self.tr('Replace the crop library? Existing crop assignments will be cleared.')
        zero_files = [os.path.basename(filename) for filename, record in zip(filenames, parameters)
                      if record.get('id') == 0]
        if zero_files:
            message += '\n\n' + self.tr(
                'Note: crop 0 is reserved for bare soil parameters. Make sure %s describes bare soil, not an actual crop.') % ', '.join(zero_files)
        return message

    def replace_records(self, parameters):
        import_crops(self.database_path, parameters)


class ConfigureLandUse(QDialog):
    def __init__(self, parent, database_path, map_classes, layers, preset_folder, settings=None):
        super().__init__(parent)
        self.database_path = database_path
        self.layers = layers
        self.preset_folder = preset_folder
        self.settings = settings
        self.classes, self.crops = read_library(database_path)
        self.setWindowTitle(self.tr('Configure land-use classes'))
        layout = QVBoxLayout(self)
        import_button = QPushButton(self.tr('Import crops…'), self)
        import_button.setMinimumHeight(36)
        font = import_button.font()
        font.setBold(True)
        import_button.setFont(font)
        layout.addWidget(import_button)
        description = QLabel(self.tr('Assign one or two crops to each map class.'), self)
        description.setWordWrap(True)
        layout.addWidget(description)
        self.table = QTableWidget(len(map_classes), 4, self)
        self.table.setHorizontalHeaderLabels([self.tr('Map class ID'), self.tr('Land-use name'),
                                              self.tr('First crop'), self.tr('Second crop (optional)')])
        self.table.verticalHeader().hide()
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 250)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close, self)
        layout.addWidget(self.buttons)
        for row, (class_id, map_name) in enumerate(sorted(map_classes.items())):
            record = self.classes.get(class_id, {})
            sequence = record.get('crops', [])
            if len(sequence) > 2:
                raise ValueError('Class %s already has more than two crops. This editor cannot change it safely.' % class_id)
            self.table.setItem(row, 0, read_only_item(class_id))
            self.table.setItem(row, 1, QTableWidgetItem(record.get('name') or map_name or 'Land use %s' % class_id))
            for column in (2, 3):
                selector = QComboBox(self.table)
                self.table.setCellWidget(row, column, selector)
                self.fill_selector(selector, sequence[column - 2] if len(sequence) >= column - 1 else None,
                                   optional=column == 3)
                selector.currentIndexChanged.connect(self.validate)
        self.table.itemChanged.connect(self.validate)
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        import_button.clicked.connect(self.import_crops)
        self.initial = self.assignments()
        self.validate()
        height = min(650, QApplication.primaryScreen().availableGeometry().height() - 70)
        self.resize(950, min(height, 270 + 36 * len(map_classes)))

    def fill_selector(self, selector, crop_id, optional=False):
        selector.blockSignals(True)
        selector.clear()
        selector.addItem(self.tr('None') if optional else self.tr('Select crop'), None)
        for key, name in self.crops.items():
            selector.addItem('%s [%s]' % (crop_display_name(name), key), key)
        index = selector.findData(crop_id)
        if crop_id is not None and index < 0:
            selector.addItem(self.tr('Missing crop [%s]') % crop_id, crop_id)
            index = selector.count() - 1
        selector.setCurrentIndex(max(0, index))
        selector.blockSignals(False)

    def assignments(self):
        records = {}
        for row in range(self.table.rowCount()):
            first = self.table.cellWidget(row, 2).currentData()
            second = self.table.cellWidget(row, 3).currentData()
            records[int(self.table.item(row, 0).text())] = {
                'name': self.table.item(row, 1).text().strip(),
                'crops': [value for value in (first, second) if value is not None],
            }
        return records

    def validate(self):
        invalid = 0
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            first = self.table.cellWidget(row, 2).currentData()
            second = self.table.cellWidget(row, 3).currentData()
            ready = (bool(self.table.item(row, 1).text().strip()) and first in self.crops
                     and (second is None or second in self.crops))
            self.table.item(row, 0).setBackground(QColor('white') if ready else QColor('#fff0cc'))
            invalid += not ready
        self.table.blockSignals(False)
        self.status.setText(self.tr('%s classes still need a name or valid crop assignment.') % invalid
                            if invalid else self.tr('All map classes are assigned.'))
        self.buttons.button(QDialogButtonBox.Save).setEnabled(self.table.rowCount() > 0 and not invalid)

    def import_crops(self):
        dialog = ImportCrops(self, self.database_path, self.preset_folder, self.layers, self.settings)
        if dialog.exec() != QDialog.Accepted:
            return
        self.classes, self.crops = read_library(self.database_path)
        for row in range(self.table.rowCount()):
            for column in (2, 3):
                selector = self.table.cellWidget(row, column)
                self.fill_selector(selector, None, optional=column == 3)
        for record in self.initial.values():
            record['crops'] = []
        self.validate()

    def save(self):
        if not self.buttons.button(QDialogButtonBox.Save).isEnabled():
            return
        if any(layer.isModified() for layer in self.layers):
            QMessageBox.warning(self, self.tr('Pending edits'),
                self.tr('Save or discard edits to Soil uses and Crop types before saving assignments.'))
            return
        try:
            save_assignments(self.database_path, self.assignments())
        except Exception as error:
            QMessageBox.warning(self, self.tr('Save failed'), str(error))
            return
        reload_layers(self.layers)
        self.initial = self.assignments()
        self.status.setText(self.tr('Land-use assignments saved.'))

    def reject(self):
        if self.assignments() != self.initial:
            answer = QMessageBox.question(self, self.tr('Unsaved assignments'),
                self.tr('Discard changes to crop assignments? Crops already imported will remain in the project.'),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        super().reject()
