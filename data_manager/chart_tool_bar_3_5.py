import os

from qgis.PyQt.QtGui import QCursor
from qgis.PyQt.QtWidgets import QApplication
from matplotlib.backend_tools import cursors
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT
from matplotlib.backend_bases import MouseButton
import matplotlib.dates as mdt
from qgis.PyQt import QtWidgets, QtCore, QtGui

from data_manager.dialogs.edit_legend import EditLegend


class ChartToolBar(NavigationToolbar2QT):
	def __init__(self, canvas, parent, advanced = False, digits = False):
		self.digits = digits # before parent initialization
		self.basedir = os.path.join(os.path.dirname(__file__), 'icons')
		self.ADVANCED = advanced

		NavigationToolbar2QT.__init__(self, canvas, parent)

		self.toolitems = (
			('Home', 'Reset original view', 'Home', 'home'),
			('Back', 'Back to previous view', 'Back', 'back'),
			('Forward', 'Forward to next view', 'Forward', 'forward'),
			(None, None, None, None),
			('Pan', 'Pan axes with left mouse, zoom with right', 'Move', 'pan'),
			('Zoom', 'Zoom to rectangle', 'ZoomToRect', 'zoom'),
			(None, None, None, None),
			('Subplots', 'Configure subplots', 'Subplots', 'configure_subplots'),
			(None, None, None, None),
			('Save', 'Save the figure', 'Filesave', 'save_figure'),
		)

		if self.ADVANCED:
			self.toolitems = (
				('Home', 'Reset original view', 'Home', 'home'),
				('Back', 'Back to previous view', 'Back', 'back'),
				('Forward', 'Forward to next view', 'Forward', 'forward'),
				(None, None, None, None),
				('Pan', 'Pan axes with left mouse, zoom with right', 'Move', 'pan'),
				('Zoom', 'Zoom to rectangle', 'ZoomToRect', 'zoom'),
				('Notes', 'Add notes', 'Notes', 'add_notes'),
				('NotesRemove', 'Delete notes', 'NotesRemove', 'remove_notes'),
				(None, None, None, None),
				('Subplots', 'Configure subplots', 'Subplots', 'configure_subplots'),
				('EditLegend', 'Edit legend', 'Editlegend', 'edit_legend'),
				# ('Customize', 'Edit axis, curve and image parameters', 'Customize', 'edit_parameters'),
				(None, None, None, None),
				('Save', 'Save the figure', 'Filesave', 'save_figure'),
			)

		self._init_toolbar()
		self.canvas = canvas
		self.ann_list = []

		if self.ADVANCED:
			self.cid_deltext = self.canvas.mpl_connect('button_press_event', self.delTextFromPlot)
			self.cid_addtext = self.canvas.mpl_connect('pick_event', self.addTextToPlot)

		self.coordinates = False

	def _init_toolbar(self):
		self.basedir = os.path.join(os.path.dirname(__file__), 'icons')
		self.clear() # clear all elements in the toolbar

		for text, tooltip_text, image_file, callback in self.toolitems:
			#print('load image:',os.path.join(self.basedir,image_file + '.svg'))

			if text is None:
				self.addSeparator()
			else:
				a = self.addAction(self._icon(os.path.join(self.basedir,image_file + '.svg')),
								   text, getattr(self, callback))
				self._actions[callback] = a
				if callback in ['zoom', 'pan','add_notes','remove_notes']:
					a.setCheckable(True)
				if tooltip_text is not None:
					a.setToolTip(tooltip_text)
				if text == '__Subplots':
					a = self.addAction(self._icon(os.path.join(self.basedir,image_file + '.svg')),
									   'Customize', self.edit_parameters)
					a.setToolTip('Edit axis, curve and image parameters')

		# Add the x,y location widget at the right side of the toolbar
		# The stretch factor is 1 which means any resizing of the toolbar
		# will resize this label instead of the buttons.
		if self.coordinates:
			self.locLabel = QtWidgets.QLabel("", self)
			self.locLabel.setAlignment(
				QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
			self.locLabel.setSizePolicy(
				QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
									  QtWidgets.QSizePolicy.Ignored))
			labelAction = self.addWidget(self.locLabel)
			labelAction.setVisible(True)

		if self.digits:
			self.digitLBL = QtWidgets.QLabel(self)
			self.digitLBL.setText('Digits')
			labelAction = self.addWidget(self.digitLBL)

			self.digitSB = QtWidgets.QSpinBox(self)
			self.digitSB.setMinimum(0)
			self.digitSB.setValue(2)


			labelAction = self.addWidget(self.digitSB)
			labelAction.setVisible(True)

		# Esthetic adjustments - we need to set these explicitly in PyQt5
		# otherwise the layout looks different - but we don't want to set it if
		# not using HiDPI icons otherwise they look worse than before.
		#if is_pyqt5() and self.canvas._dpi_ratio > 1:
		# if self.canvas._dpi_ratio > 1:
		# 	self.setIconSize(QtCore.QSize(24, 24))
		# 	self.layout().setSpacing(12)

	def _update_buttons_checked(self):
		# sync button checkstates to match active mode
		#print('CALL _update_buttons_checked')
		#print('_update_buttons_checked',self.canvas.figure.axes[0].get_navigate_mode())
		self._actions['pan'].setChecked(self.canvas.figure.axes[0].get_navigate_mode() == 'PAN')
		self._actions['zoom'].setChecked(self.canvas.figure.axes[0].get_navigate_mode() == 'ZOOM')
		if self.ADVANCED:
			self._actions['remove_notes'].setChecked(self.canvas.figure.axes[0].get_navigate_mode() == 'REMOVE_NOTES')
			self._actions['add_notes'].setChecked(self.canvas.figure.axes[0].get_navigate_mode() == 'ADD_NOTES')
		#toolButton.toggle()

	def edit_legend(self):
		#print('In edit legend')
		line_opt_list = {}
		for ln in self.canvas.figure.axes[0].lines:
			#print('id:',ln.get_gid(),'label:',ln.get_label(),'color:',ln.get_color(),'type',ln.get_linestyle())
			line_opt_list[ln.get_gid()]={'label':ln.get_label(),'color':ln.get_color(),'type':ln.get_linestyle()}

		# open form and send line options
		dlg = EditLegend(self.canvas,line_opt_list)
		result = dlg.exec_()
		# See if OK was pressed
		if result:
			res = dlg.getData()
			self.canvas.parent().h = []
			self.canvas.parent().l = []
			# apply edits
			for ln in self.canvas.figure.axes[0].lines:
				ln_gid = ln.get_gid()
				ln.set_linestyle(res[ln_gid]['type'])
				ln.set_color(res[ln_gid]['color'])
				ln.set_label(res[ln_gid]['label'])
				self.canvas.parent().h.append(ln)
				self.canvas.parent().l.append(res[ln_gid]['label'])

			self.canvas.figure.axes[0].legend(self.canvas.parent().h,self.canvas.parent().l)
			self.canvas.draw()

		# retrieve line options on close + OK

		# apply

	def add_notes(self):
		#print('before is',self.addNotesFlg)
		#self.addNotesFlg = not self.addNotesFlg
		if self.canvas.figure.axes[0].get_navigate_mode() == 'ADD_NOTES':
			self.canvas.figure.axes[0].set_navigate_mode(None)
		else:
			self.canvas.figure.axes[0].set_navigate_mode('ADD_NOTES')
			self._update_buttons_checked()
			self.canvas.widgetlock.release(self)
			self.canvas.set_cursor(cursors.POINTER)
			self._lastCursor = cursors.POINTER
			self.canvas.widgetlock.locked()

	def remove_notes(self):
		# TODO: fix pointer changes
		#self.removeNotesFlg = not self.removeNotesFlg
		if self.canvas.figure.axes[0].get_navigate_mode() == 'REMOVE_NOTES':
			self.canvas.figure.axes[0].set_navigate_mode(None)
		else:
			self.canvas.figure.axes[0].set_navigate_mode('REMOVE_NOTES')
			self._update_buttons_checked()
			self.canvas.widgetlock.release(self)
			self.canvas.set_cursor(cursors.POINTER)
			self._lastCursor = cursors.POINTER
			self.canvas.widgetlock.locked()

	def addTextToPlot(self,event):
		print('triggered addTextToPlot')

		numOfDig = 10
		if self.digits:
			numOfDig = self.digitSB.value()

		if self.canvas.figure.axes[0].get_navigate_mode() == 'ADD_NOTES': #self.addNotesFlg:
			artist = event.artist
			#xmouse, ymouse = event.mouseevent.xdata, event.mouseevent.ydata
			xmouse, ymouse = event.mouseevent.x, event.mouseevent.y
			x, y = artist.get_xdata(), artist.get_ydata()
			ind = event.ind
			xpos = x[ind[0]]
			ypos = y[ind[0]]
			ystr = round(ypos,numOfDig)
			if numOfDig==0: ystr=int(ystr)

			#print(type(xpos))
			#txt = '%s\n%s' % (mdt.num2date(xpos).strftime("%Y-%m-%d"), ystr)
			txt = '%s\n%s' % (xpos.strftime("%Y-%m-%d"), ystr)
			id = '%s%s'%(xpos,ypos)

			if event.mouseevent.button is MouseButton.LEFT:
				#print(xmouse,xmouse,txt)
				#for ax in self.canvas.figure.get_axes():
				ax = artist.axes
				if ax:
					#ax.text(xmouse, ymouse, txt)
					# https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.annotate.html
					ann = ax.annotate(txt, xy=(xpos, ypos),  xycoords='data',
								xytext = (30,50),textcoords='offset points',
								arrowprops=dict(arrowstyle="->", connectionstyle="arc3"),
								fontsize=12,
								horizontalalignment='left', verticalalignment='center')
					ann.set_gid(id)
					self.ann_list.append(ann)
				else:
					print('ax',ax)
			else:
				pass

		self.canvas.draw()

	def delTextFromPlot(self,event):
		xmouse, ymouse = event.x, event.y
		if self.canvas.figure.axes[0].get_navigate_mode() == 'REMOVE_NOTES': #self.removeNotesFlg:
			if len(self.ann_list)>0:
				#print('click mouse in', xmouse, ymouse)
				i=len(self.ann_list)
				for ann in reversed(self.ann_list):
					i-=1
					# ext Bbox(x0=600.8858621816512, y0=418.5381244767049, x1=768.1770064511026, y1=510.4138753387534)
					# if ann.gid == id:
					try:
						#print('bbox', ann.get_window_extent())
						if ann.get_window_extent().contains(xmouse, ymouse):
							ann.remove()
							break
					except Exception as e:
						print('error:', ann, str(e))

				self.ann_list.pop(i)

		self.canvas.draw()
