#! /usr/bin/env python3
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# In this prototype/example a QTreeView is created. Then it's populated with
# three containers and all containers are populated with three rows, each 
# containing three columns.
# Then the last container is expanded and the last row is selected.
# The container items are spanned through the all columns.
# Note: this requires > python-3.2
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
import sys, os, pprint, time
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
import copy 
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class PushButtonDelegateQt(QStyledItemDelegate):
	""" Delegate for a clickable button in a model view.
	Calls the model's setData() method when clicked, wherein the button clicked action should be handled.
	"""
	def __init__(self, text="", parent=None):
		QStyledItemDelegate.__init__(self, parent)
		self.title = text
		self._isMousePressed = False

	def createEditor(self, parent, option, index):
		""" Important, otherwise an editor is created if the user clicks in this cell.
		"""
		return None

	def paint(self, painter, option, index):
		""" Draw button in cell.
		"""
		opts = QStyleOptionButton()
		opts.state |= QStyle.State_Active
		opts.state |= QStyle.State_Enabled
		if QT_VERSION_STR[0] == '4':
			opts.state |= (QStyle.State_Sunken if self._isMousePressed else QStyle.State_Raised)
		elif QT_VERSION_STR[0] == '5':
			# When raised in PyQt5, white text cannot be seen on white background.
			# Should probably fix this by initializing form styled button, but for now I'll just sink it all the time.
			opts.state |= QStyle.State_Sunken
		opts.rect = option.rect
		#opts.text = self.title
		pal = QPalette() 
		pal.setColor(QPalette.Button, QColor(index.model().data(index, Qt.DisplayRole)))
		pal.setColor(QPalette.Window, QColor(index.model().data(index, Qt.DisplayRole)))
		opts.palette = pal
		QApplication.style().drawControl(QStyle.CE_PushButton, opts, painter)

	def editorEvent(self, event, model, option, index):
		""" Handle mouse events in cell.
		On left button release in this cell, call model's setData() method,
			wherein the button clicked action should be handled.
		Currently, the value supplied to setData() is the button text, but this is arbitrary.
		"""
		if event.button() == Qt.LeftButton:
			if event.type() == QEvent.MouseButtonPress:
				if option.rect.contains(event.pos()):
					self._isMousePressed = True
					return True
			elif event.type() == QEvent.MouseButtonRelease:
				self._isMousePressed = False
				if option.rect.contains(event.pos()):
					# open dialog
					dialog = QColorDialog(None) 
					dialog.exec()
					selColor = dialog.currentColor().name()
					model.setData(index, selColor, Qt.EditRole)  # Model should handle button click action in its setData() method.
					return True
		return False


class ComboBoxDelegateQt(QStyledItemDelegate):
	""" Delegate for editing a list of choices via a combobox.
	The choices attribute is a list of either values or (key, value) tuples.
	In the first case, the str rep of the values are directly displayed in the combobox.
	In the latter case, the str rep of only the keys are displayed in the combobox, and the values can be any object.
		Although only the keys are displayed in the view, the model data is set to the actual values, not the keys.
	Upon selection, view will display the str rep of either the value itself or its key if it exists.
	For example:
		To select from some integers, set choices = [1, 3, 10, 100].
			Combobox entries will be '1', '3', '10' and '100'.
			Upon selection model data will be set to the selected integer value and view will show the str rep of this value.
		To select from two of your custom objects, set choices = [('A', MyObject()), ('B', MyObject())]
			Combobox entries will be 'A' and 'B'.
			Upon selection model data will be set to the selected MyObject instance and view will show its key (either 'A' or 'B')..
	"""
	def __init__(self, choices=None, parent=None):
		QStyledItemDelegate.__init__(self, parent)
		self.choices = choices if (choices is not None and type(choices) is list) else []

	def createEditor(self, parent, option, index):
		""" Return QComboBox with list of choices (either values or their associated keys if they exist).
		"""
		try:
			editor = QComboBox(parent)
			value = index.model().data(index, Qt.DisplayRole)
			for i, choice in enumerate(self.choices):
				if (type(choice) is tuple) and (len(choice) == 2):
					# choice is a (key, value) tuple.
					key, val = choice
					editor.addItem(str(key))  # key MUST be representable as a str.
					if val == value:
						editor.setCurrentIndex(i)
				else:
					# choice is a value.
					editor.addItem(str(choice))  # choice MUST be representable as a str.
					if choice == value:
						editor.setCurrentIndex(i)
			return editor
		except:
			return None

	def setModelData(self, editor, model, index):
		""" Set model data to current choice (if choice is a key, set data to its associated value).
		"""
		try:
			choice = self.choices[editor.currentIndex()]
			if (type(choice) is tuple) and (len(choice) == 2):
				# choice is a (key, value) tuple.
				key, val = choice
				value = copy.deepcopy(val)  # Deepcopy of val in case it is a complex object.
			else:
				# choice is a value.
				value = choice
			#model.setData(index, value, Qt.EditRole)
			index.model().setData(index, value, Qt.EditRole)
			index.model().dataChanged.emit(index, index)  # Tell model to update cell display.
		except:
			pass

	def displayText(self, value, locale):
		""" Show str rep of current choice (or choice key if choice is a (key, value) tuple).
		"""
		try:
			if type(value) == QVariant:
				value = value.toPyObject()  # QVariant ==> object
			for choice in self.choices:
				if (type(choice) is tuple) and (len(choice) == 2):
					# choice is a (key, value) tuple.
					# Display the key, not the value.
					key, val = choice
					if val == value:
						return str(key)
				else:
					# choice is a value.
					# Display it's str rep.
					if choice == value:
						return str(choice)
			# If value is not in our list of choices, show str rep of value.
			return str(value)
		except:
			return ""


class CheckBoxDelegateQt(QStyledItemDelegate):
	# credits: https://github.com/marcel-goldschen-ohm/ModelViewPyQt
	""" Delegate for editing bool values via a checkbox with no label centered in its cell.
	Does not actually create a QCheckBox, but instead overrides the paint() method to draw the checkbox directly.
	Mouse events are handled by the editorEvent() method which updates the model's bool value.
	"""
	def __init__(self, parent=None):
		QStyledItemDelegate.__init__(self, parent)

	def createEditor(self, parent, option, index):
		""" Important, otherwise an editor is created if the user clicks in this cell.
		"""
		return None

	def paint(self, painter, option, index):
		""" Paint a checkbox without the label.
		"""
		d = index.model().data(index, Qt.DisplayRole)
		checked = True
		if d == 'False': checked = False
		
		opts = QStyleOptionButton()
		opts.state |= QStyle.State_Active
		if index.flags() & Qt.ItemIsEditable:
			opts.state |= QStyle.State_Enabled
		else:
			opts.state |= QStyle.State_ReadOnly
		if checked:
			opts.state |= QStyle.State_On
		else:
			opts.state |= QStyle.State_Off
		opts.rect = self.getCheckBoxRect(option)
		QApplication.style().drawControl(QStyle.CE_CheckBox, opts, painter)

	def editorEvent(self, event, model, option, index):
		""" Change the data in the model and the state of the checkbox if the
		user presses the left mouse button and this cell is editable. Otherwise do nothing.
		"""
		if not (index.flags() & Qt.ItemIsEditable):
			return False
		if event.button() == Qt.LeftButton:
			if event.type() == QEvent.MouseButtonRelease:
				if self.getCheckBoxRect(option).contains(event.pos()):
					self.setModelData(None, model, index)
					return True
			elif event.type() == QEvent.MouseButtonDblClick:
				if self.getCheckBoxRect(option).contains(event.pos()):
					return True
		return False

	def setModelData (self, editor, model, index):
		'''
		The user wanted to change the old state in the opposite.
		'''
		d = index.model().data(index, Qt.DisplayRole)
		if d=='False': d='True'
		else: d='False'
		
		index.model().setData(index, d, Qt.EditRole)
		
	def getCheckBoxRect(self, option):
		""" Get rect for checkbox centered in option.rect.
		"""
		# Get size of a standard checkbox.
		opts = QStyleOptionButton()
		checkBoxRect = QApplication.style().subElementRect(QStyle.SE_CheckBoxIndicator, opts, None)
		# Center checkbox in option.rect.
		x = option.rect.x()
		y = option.rect.y()
		w = option.rect.width()
		h = option.rect.height()
		checkBoxTopLeftCorner = QPoint(x + w / 2 - checkBoxRect.width() / 2, y + h / 2 - checkBoxRect.height() / 2)
		return QRect(checkBoxTopLeftCorner, checkBoxRect.size())
	
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def forEach(model, parent = QModelIndex()):
	for r in range(0, model.rowCount(parent)):
		for c in range(0, model.columnCount(parent)):
			index = model.index(r, c, parent)
			name = model.data(index)
			print(name)
			if( model.hasChildren(index) ):
				forEach(model, index)
				
def applyFilter(mProxyModel):
	#Regular expression
	#Contain any one of a, b, and c is sufficient
	regExp = QRegExp("[tm]", Qt.CaseInsensitive, QRegExp.RegExp)
	mProxyModel.setFilterRegExp(regExp)


#~ #applyFilter(mProxyModel)

#~ view.show()
#~ # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ forEach(model)
