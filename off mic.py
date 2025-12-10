import subprocess, sys, os, signal
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
from PyQt5 import QtCore, QtWidgets, QtGui  # Импорт необходимых модулей из PyQt5
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QAction, QMenu, QWidget, QDialog, QLabel, QSystemTrayIcon, QMenu, QAction, QVBoxLayout, QPushButton, QApplication
from PyQt5.QtCore import QTimer
from write_text import *
source_id = get_webcam_source_id()
set_mute("0", source_id)
class MyThread(QtCore.QThread):
 text_signal = QtCore.pyqtSignal(str, bool)
 icon_signal = QtCore.pyqtSignal(str)
 init_ui_signal = QtCore.pyqtSignal()
 
 def __init__(self, parent=None):
  super(MyThread, self).__init__(parent)
  self.parent = parent
  self.mic = None
  self._running = True
 
 def update_mic_state(self, mic):
  self.mic = mic
 
 def run(self):
  while self._running:
   try:
    self.mic = get_mute_status(source_id)
    pass
   except Exception as ex1:
    pass

class MyWindow(QtWidgets.QWidget):
 def __init__(self, parent=None):
  super(MyWindow, self).__init__(parent)
  self.mic = get_mute_status(source_id)
  self.mythread = MyThread(parent=self)
  self.icon1_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/stop.png"
  self.icon2_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/voice.png"
  self.tray_icon = QSystemTrayIcon(QtGui.QIcon(self.icon2_path), self)
  menu = QMenu()
  quit_action = QAction("Quit", self)
  quit_action.triggered.connect(self.quit_t)
  menu.addAction(quit_action)
  
  self.mythread.icon_signal.connect(self.change_icon)
  
  self.tray_icon.setContextMenu(menu)
  self.tray_icon.setToolTip("OFF")
  self.tray_icon.activated.connect(self.on_tray_icon_activated)
  self.tray_icon.show()
  self.mythread.start()
  QTimer.singleShot(0, self.hide)
 
 def change_icon(self, icon_path):
  try:
   self.tray_icon.setIcon(QtGui.QIcon(icon_path))
   self.tray_icon.show()
  except Exception as e:
   print(f"change_icon error: {e}")
 
 def on_tray_icon_activated(self):
  try:
   self.mic = not getattr(self, "mic", True)
   self.tray_icon.setToolTip("ON" if self.mic else "OFF")
   set_mute("0" if self.mic else "1", source_id)
   self.tray_icon.show()
   self.mythread.icon_signal.emit(self.icon2_path if self.mic else self.icon1_path)
   self.mythread.update_mic_state(self.mic)
  except Exception as e:
   print(f"Error in on_tray_icon_activated: {e}")
 
 def quit_t(self):
  try:
   script_name ="off mic.py"   # Находим PID процесса по имени скрипта
   pid = int(subprocess.check_output( f"pgrep -f '{script_name}'",
    shell=True ).decode().strip())
   os.kill(pid, signal.SIGTERM)
   print(f"Процесс '{script_name}' (PID: {pid}) успешно завершён.")

   QApplication.quit()
  except Exception:
   QApplication.quit()
   pass
  QApplication.quit()

if __name__ == "__main__":
 app = QApplication(sys.argv)
 window = MyWindow()
 window.show()
 sys.exit(app.exec_())

