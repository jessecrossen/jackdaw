import os
import sys
import re
import yaml
import icon

from PySide.QtCore import *
from PySide.QtGui import *

import doc
from doc_view import DocumentView
from undo import UndoManager

class DocumentWindow(QMainWindow):
  def __init__(self, app=None):
    QMainWindow.__init__(self)
    self._app = app
    self.setMinimumSize(QSize(800, 600))
    self.setWindowTitle('New Document')
    # start with no document
    self._document = None
    self.document_view = None
    # make a stack to hold the document
    self.stack = QStackedWidget(self)
    self.setCentralWidget(self.stack)
    # build the menu and toolbar
    self._make_menus()
    # set up stylesheets for look and feel
    self._init_style()
    
  @property
  def document(self):
    return(self._document)
  @document.setter
  def document(self, value):
    # detach from the old document
    if (self._document is not None):
      self.detach()
      self._document = None
    # attach to the new document
    if (value is not None):
      self._document = value
      self.attach()
      
  def detach(self):
    self.document.transport.remove_observer(self.update_actions)
    self.document.view_scale.remove_observer(self.update_actions)
    # remove the document view
    if (self.document_view is not None):
      view = self.document_view
      self.document_view = None
      view.destroy()
      self.stack.removeWidget(view)
    # dump the undo stack and clear the selection
    UndoManager.reset()
  def attach(self):
    # make a view for the document
    self.document_view = DocumentView(parent=self,
      document=self.document)
    # add it to the document
    self.stack.addWidget(self.document_view)
    # update actions when relevant objects change
    self.document.transport.add_observer(self.update_actions)
    self.document.view_scale.add_observer(self.update_actions)
    self.update_actions()
  
  # build the application menu and toolbar
  def _make_menus(self):
    menubar = self.menuBar()
    
    # file menu
    file_menu = menubar.addMenu('&File')
    # new
    new_action = QAction(QIcon.fromTheme('document-new'), '&New', self)
    new_action.setShortcut('Ctrl+O')
    new_action.setStatusTip('Open a document')
    new_action.triggered.connect(self.file_new)
    file_menu.addAction(new_action)
    # open
    open_action = QAction(QIcon.fromTheme('document-open'), '&Open', self)
    open_action.setShortcut('Ctrl+O')
    open_action.setStatusTip('Open a document')
    open_action.triggered.connect(self.file_open)
    file_menu.addAction(open_action)
    # save
    save_action = QAction(QIcon.fromTheme('document-save'), '&Save', self)
    save_action.setShortcut('Ctrl+S')
    save_action.setStatusTip('Save the document')
    save_action.triggered.connect(self.file_save)
    file_menu.addAction(save_action)
    # save as
    save_as_action = QAction(QIcon.fromTheme('document-save'), 'Save &As', self)
    save_as_action.setStatusTip('Save the document to a different file')
    save_as_action.triggered.connect(self.file_save_as)
    file_menu.addAction(save_as_action)
    # ---
    file_menu.addSeparator()
    # quit
    quit_action = QAction(QIcon.fromTheme('application-exit'), '&Quit', self)
    quit_action.setShortcut('Ctrl+Q')
    quit_action.setStatusTip('Quit application')
    quit_action.triggered.connect(self.close)
    file_menu.addAction(quit_action)
    
    # edit menu
    edit_menu = menubar.addMenu('&Edit')
    # undo
    self.undo_action = QAction(icon.get('undo'), '&Undo', self)
    self.undo_action.setShortcut('Ctrl+Z')
    self.undo_action.setStatusTip('Undo the last action')
    self.undo_action.triggered.connect(self.edit_undo)
    edit_menu.addAction(self.undo_action)
    # redo
    self.redo_action = QAction(icon.get('redo'), '&Redo', self)
    self.redo_action.setShortcut('Ctrl+Shift+Z')
    self.redo_action.setStatusTip('Redo the last action that was undone')
    self.redo_action.triggered.connect(self.edit_redo)
    edit_menu.addAction(self.redo_action)
    
    # transport menu
    transport_menu = menubar.addMenu('&Transport')
    # go to start
    self.beginning_action = QAction(icon.get('beginning'), 'Jump to &Beginning', self)
    self.beginning_action.setShortcut('Home')
    self.beginning_action.setStatusTip('Jump back to the beginning of the project')
    self.beginning_action.triggered.connect(self.transport_beginning)
    transport_menu.addAction(self.beginning_action)
    # go to end
    self.end_action = QAction(icon.get('ending'), 'Jump to &End', self)
    self.end_action.setShortcut('End')
    self.end_action.setStatusTip('Jump forward to the end of the project')
    self.end_action.triggered.connect(self.transport_end)
    transport_menu.addAction(self.end_action)
    # back
    self.back_action = QAction(icon.get('backward'), 'Bac&k', self)
    self.back_action.setShortcut('PgUp')
    self.back_action.setStatusTip('Skip backward in time')
    self.back_action.triggered.connect(self.transport_back)
    transport_menu.addAction(self.back_action)
    # forward
    self.forward_action = QAction(icon.get('forward'), '&Forward', self)
    self.forward_action.setShortcut('PgDown')
    self.forward_action.setStatusTip('Skip forward in time')
    self.forward_action.triggered.connect(self.transport_forward)
    transport_menu.addAction(self.forward_action)
    # ---
    transport_menu.addSeparator()
    # previous mark
    self.previous_mark_action = QAction(icon.get('mark_previous'), 'Previous Mark', self)
    self.previous_mark_action.setShortcut('Ctrl+PgUp')
    self.previous_mark_action.setStatusTip('Skip to the previous marked time')
    self.previous_mark_action.triggered.connect(self.transport_previous_mark)
    transport_menu.addAction(self.previous_mark_action)
    # toggle mark
    self.toggle_mark_action = QAction(icon.get('mark_toggle'), 'Toggle Mark', self)
    self.toggle_mark_action.setShortcut('Ctrl+\\')
    self.toggle_mark_action.setStatusTip('Toggle a mark at the current time')
    self.toggle_mark_action.triggered.connect(self.transport_toggle_mark)
    transport_menu.addAction(self.toggle_mark_action)
    # next mark
    self.next_mark_action = QAction(icon.get('mark_next'), 'Next Mark', self)
    self.next_mark_action.setShortcut('Ctrl+PgDown')
    self.next_mark_action.setStatusTip('Skip to the next marked time')
    self.next_mark_action.triggered.connect(self.transport_next_mark)
    transport_menu.addAction(self.next_mark_action)
    # cycle
    self.toggle_cycle_action = QAction(icon.get('cycle'), 'Cycle', self)
    self.toggle_cycle_action.setShortcut('Ctrl+L')
    self.toggle_cycle_action.setStatusTip('Toggle cycling playback mode')
    self.toggle_cycle_action.setCheckable(True)
    self.toggle_cycle_action.toggled.connect(self.transport_toggle_cycle)
    transport_menu.addAction(self.toggle_cycle_action)
    # ---
    transport_menu.addSeparator()
    # stop
    self.stop_action = QAction(icon.get('stop'), '&Stop', self)
    self.stop_action.setStatusTip('Stop playback or recording')
    self.stop_action.triggered.connect(self.transport_stop)
    transport_menu.addAction(self.stop_action)
    # play
    self.play_action = QAction(icon.get('play'), '&Play', self)
    self.play_action.setStatusTip('Start playback')
    self.play_action.triggered.connect(self.transport_play)
    transport_menu.addAction(self.play_action)
    # record
    self.record_action = QAction(icon.get('record'), '&Record', self)
    self.record_action.setStatusTip('Start recording')
    self.record_action.triggered.connect(self.transport_record)
    transport_menu.addAction(self.record_action)
    # ---
    transport_menu.addSeparator()
    # zoom in
    self.zoom_in_action = QAction(icon.get('zoom_in'), 'Zoom &In', self)
    self.zoom_in_action.setShortcut('Ctrl+Shift+Plus')
    self.zoom_in_action.setStatusTip('Zoom in')
    self.zoom_in_action.triggered.connect(self.transport_zoom_in)
    transport_menu.addAction(self.zoom_in_action)
    # zoom out
    self.zoom_out_action = QAction(icon.get('zoom_out'), 'Zoom &Out', self)
    self.zoom_out_action.setShortcut('Ctrl+Shift+Minus')
    self.zoom_out_action.setStatusTip('Zoom out')
    self.zoom_out_action.triggered.connect(self.transport_zoom_out)
    transport_menu.addAction(self.zoom_out_action)
    
    # toolbar
    self.toolbar = self.addToolBar('Main')
    self.toolbar.addAction(self.undo_action)
    self.toolbar.addAction(self.redo_action)
    self.toolbar.addSeparator()
    self.toolbar.addAction(self.beginning_action)
    self.toolbar.addAction(self.back_action)
    self.toolbar.addAction(self.forward_action)
    self.toolbar.addAction(self.end_action)
    self.toolbar.addSeparator()
    self.toolbar.addAction(self.stop_action)
    self.toolbar.addAction(self.play_action)
    self.toolbar.addAction(self.record_action)
    self.toolbar.addSeparator()
    self.toolbar.addAction(self.zoom_out_action)
    self.toolbar.addAction(self.zoom_in_action)
    # give actions their initial states
    UndoManager.add_observer(self.update_actions)
    self.update_actions()
    
  # start a new document
  def file_new(self):
    self.document = doc.Document()
  # open an existing document
  def file_open(self):
    (path, group) = QFileDialog.getOpenFileName(self,
      "Open Project", "~", "Project Files (*.jdp *.yml);;All Files (*.*)")
    document = doc.Document.get_from_path(path)
    if (document is not None):
      self.document = document
  # save the document
  def file_save(self):
    if (not self.document): return
    if (not self.document.path):
      self.file_save_as()
    else:
      self.document.save()
  # save the document with a different file name
  def file_save_as(self):
    (path, group) = QFileDialog.getSaveFileName(self,
        "Save Project", "~", "Project Files (*.jdp *.yml);;All Files (*.*)")
    if (len(path) == 0): return
    self.document.path = path
    self.document.save()
  
  # undo
  def edit_undo(self):
    UndoManager.undo()
  # redo
  def edit_redo(self):
    UndoManager.redo()
  
  # transport actions
  def transport_beginning(self):
    if (self.document):
      self.document.transport.go_to_beginning()
  def transport_end(self):
    if (self.document):
      self.document.transport.go_to_end()
  def transport_back(self):
    if (self.document):
      self.document.transport.skip_back()
  def transport_forward(self):
    if (self.document):
      self.document.transport.skip_forward()
  def transport_previous_mark(self):
    if (self.document):
      self.document.transport.previous_mark()
  def transport_toggle_mark(self):
    if (self.document):
      self.document.transport.toggle_mark()
  def transport_next_mark(self):
    if (self.document):
      self.document.transport.next_mark()
  def transport_toggle_cycle(self, toggled):
    if (self.document):
      self.document.transport.cycling = toggled
  def transport_play(self):
    if (self.document):
      self.document.transport.play()
  def transport_record(self):
    if (self.document):
      self.document.transport.record()
  def transport_stop(self):
    if (self.document):
      self.document.transport.stop()
  def transport_zoom_in(self):
    if (self.document_view):
      self.document_view.zoom_in()
  def transport_zoom_out(self):
    if (self.document):
      self.document_view.zoom_out()
      
  # reflect changes to models in the action buttons
  def update_actions(self):
    # disable undo/redo at the ends of the stack
    self.undo_action.setEnabled(UndoManager.can_undo)
    self.redo_action.setEnabled(UndoManager.can_redo)
    # only allow transport actions if we have a document
    self.beginning_action.setEnabled(self.document is not None)
    self.end_action.setEnabled(self.document is not None)
    self.back_action.setEnabled(self.document is not None)
    self.forward_action.setEnabled(self.document is not None)
    self.stop_action.setEnabled(self.document is not None)
    self.play_action.setEnabled(self.document is not None)
    self.record_action.setEnabled(self.document is not None)
    # check and uncheck the cycling item when cycling changes
    self.toggle_cycle_action.setChecked((self.document is not None) and 
                                        (self.document.transport.cycling))
    # disable zoom actions at the outer limits
    self.zoom_in_action.setEnabled(
      (self.document_view is not None) and (self.document_view.can_zoom_in))
    self.zoom_out_action.setEnabled(
      (self.document_view is not None) and (self.document_view.can_zoom_out))

  # set up stylesheets for the app
  def _init_style(self):
    # style scrollbars to be simple lozenges without buttons
    self._app.setStyleSheet('''
      QScrollBar:horizontal { height: 12px; }
      QScrollBar::handle:horizontal { min-width: 24px; }
      QScrollBar:vertical { width: 12px; }
      QScrollBar::handle:vertical { min-height: 24px; }
      QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0;
      }
      QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
      }
      QScrollBar {
        background: transparent;
        padding: 2px;
      }
      QScrollBar::handle {
        background: rgba(0, 0, 0, 64);
        border-radius: 4px;
      }
      QScrollBar::handle:hover {
        background: rgba(0, 0, 0, 128);
      }
      QScrollBar::add-page, QScrollBar::sub-page {
        background: transparent;
      }
    ''')
