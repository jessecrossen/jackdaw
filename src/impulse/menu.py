from gi.repository import Gtk

UI_INFO = """
<ui>
  <toolbar name='ToolBar'>
    <toolitem action='TransportBack' />
    <toolitem action='TransportForward' />
    <toolitem action='TransportStop' />
    <toolitem action='TransportPlay' />
    <toolitem action='TransportRecord' />
    <separator />
    <toolitem action='EditUndo' />
    <toolitem action='EditRedo' />
  </toolbar>
</ui>
"""

class Menu(object):
  def __init__(self, window):
    self.ui_manager = Gtk.UIManager()
    self.ui_manager.add_ui_from_string(UI_INFO)
    accel_group = self.ui_manager.get_accel_group()
    window.add_accel_group(accel_group)
    
    action_group = Gtk.ActionGroup("toolbar")
    self.add_transport_actions(action_group)
    self.add_edit_actions(action_group)
    self.ui_manager.insert_action_group(action_group)
    
    self.toolbar = self.ui_manager.get_widget("/ToolBar")
  
  def add_transport_actions(self, action_group):
    # back
    self.back_action = Gtk.Action("TransportBack", "Back",
            "Skip backward in time", Gtk.STOCK_MEDIA_REWIND)
    action_group.add_action_with_accel(self.back_action, '')
    # forward
    self.forward_action = Gtk.Action("TransportForward", "Forward",
            "Skip forward in time", Gtk.STOCK_MEDIA_FORWARD)
    action_group.add_action_with_accel(self.forward_action, '')
    # stop
    self.stop_action = Gtk.Action("TransportStop", "Stop",
            "Stop playback and recording", Gtk.STOCK_MEDIA_STOP)
    action_group.add_action_with_accel(self.stop_action, '')
    # play
    self.play_action = Gtk.Action("TransportPlay", "Play",
            "Start playback", Gtk.STOCK_MEDIA_PLAY)
    action_group.add_action_with_accel(self.play_action, '')
    # record
    self.record_action = Gtk.Action("TransportRecord", "Record",
            "Start recording", Gtk.STOCK_MEDIA_RECORD)
    action_group.add_action_with_accel(self.record_action, '')
  
  def add_edit_actions(self, action_group):
    # undo
    self.undo_action = Gtk.Action("EditUndo", "Undo",
            "Undo the last action", Gtk.STOCK_UNDO)
    action_group.add_action_with_accel(self.undo_action, '<control>z')
    # redo
    self.redo_action = Gtk.Action("EditRedo", "Redo",
            "Redo an undone action", Gtk.STOCK_REDO)
    action_group.add_action_with_accel(self.redo_action, '<shift><control>z')
  
