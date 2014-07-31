from gi.repository import Gtk

UI_INFO = """
<ui>
  <toolbar name='ToolBar'>
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
    
    action_group = Gtk.ActionGroup("edit")
    self.add_edit_actions(action_group)
    self.ui_manager.insert_action_group(action_group)
    
    self.toolbar = self.ui_manager.get_widget("/ToolBar")
  
  def add_edit_actions(self, action_group):
    # undo
    self.undo_action = Gtk.Action("EditUndo", "Undo",
            "Undo the last action", Gtk.STOCK_UNDO)
    action_group.add_action_with_accel(self.undo_action, '<control>z')
    # redo
    self.redo_action = Gtk.Action("EditRedo", "Redo",
            "Redo an undone action", Gtk.STOCK_REDO)
    action_group.add_action_with_accel(self.redo_action, '<shift><control>z')
  
