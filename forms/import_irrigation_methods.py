from .configure_landuse import ImportParameterLibrary
from qgis.PyQt.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QLabel,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from qgis.PyQt.QtCore import Qt
from ..tools.irrigation_library import import_irrigation_methods, map_irrigation_methods, read_irrigation_file


class IrrigationMethodMapping(QDialog):
    def __init__(self, parent, map_ids, records):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Assign irrigation methods'))
        layout = QVBoxLayout(self)
        note = QLabel(self.tr('Choose parameters for each map ID. Only mapped methods will be saved; map IDs stay unchanged.'), self)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(len(map_ids), 2, self)
        self.table.setHorizontalHeaderLabels([self.tr('Map ID'), self.tr('Irrigation parameters')])
        self.table.verticalHeader().hide()
        self.table.setColumnWidth(0, 100)
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, map_id in enumerate(sorted(map_ids)):
            item = QTableWidgetItem(str(map_id))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item)
            selector = QComboBox(self.table)
            selector.addItem(self.tr('Select method'), None)
            for index, record in enumerate(records):
                selector.addItem('%s [%s]' % (record['name'], record['id']), index)
            selector.currentIndexChanged.connect(self.validate)
            self.table.setCellWidget(row, 1, selector)
        layout.addWidget(self.table)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.button(QDialogButtonBox.Ok).setText(self.tr('Use mapping'))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.validate()
        self.resize(650, min(180 + 34 * len(map_ids),
                            QApplication.primaryScreen().availableGeometry().height() - 70))

    def assignments(self):
        return {int(self.table.item(row, 0).text()): self.table.cellWidget(row, 1).currentData()
                for row in range(self.table.rowCount())}

    def validate(self):
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(
            all(index is not None for index in self.assignments().values()))


class ImportIrrigationMethods(ImportParameterLibrary):
    TITLE = 'Import irrigation methods'
    ITEM_LABEL = 'Method'
    FILE_SUFFIX = '.txt'
    REPLACE_LABEL = 'Replace irrigation methods'
    FOLDER_LABEL = 'Irrigation parameter folder'
    EXCLUDED_FILES = {'irrmethods.txt'}  # Export manifest, not a method definition.
    read_record = staticmethod(read_irrigation_file)

    def __init__(self, parent, database_path, preset_folder, layers, settings, required_ids):
        self.required_ids = required_ids
        super().__init__(parent, database_path, preset_folder, layers, settings)

    def confirmation_message(self, parameters, filenames):
        return self.tr('Replace all irrigation method parameters? Map assignments will be kept.')

    def prepare_records(self, parameters):
        map_ids = self.required_ids()
        if not map_ids:
            return parameters
        dialog = IrrigationMethodMapping(self, map_ids, parameters)
        if dialog.exec() != QDialog.Accepted:
            return None
        return map_irrigation_methods(parameters, dialog.assignments())

    def replace_records(self, parameters):
        import_irrigation_methods(self.database_path, parameters, self.required_ids())
