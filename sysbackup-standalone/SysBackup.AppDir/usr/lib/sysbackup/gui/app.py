import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.backup import BackupManager
from core.sudoers import disable_sudo_password
from core.utils import CommandError, logger


class SysBackupWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="SysBackup")
        self.set_default_size(520, 260)
        self.set_border_width(16)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(vbox)

        title = Gtk.Label(label="SysBackup — резервное копирование и восстановление")
        title.set_xalign(0)
        vbox.pack_start(title, False, False, 0)

        self.status_label = Gtk.Label(label="Готово")
        self.status_label.set_xalign(0)
        self.status_label.set_line_wrap(True)
        vbox.pack_start(self.status_label, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("")
        vbox.pack_start(self.progress, False, False, 0)

        btn_sudo = Gtk.Button(label="Отключить запрос пароля (sudo)")
        btn_sudo.connect("clicked", self.on_disable_sudo)
        vbox.pack_start(btn_sudo, False, False, 0)

        btn_backup = Gtk.Button(label="Создать бэкап")
        btn_backup.connect("clicked", self.on_backup)
        vbox.pack_start(btn_backup, False, False, 0)

        btn_restore = Gtk.Button(label="Восстановить из бэкапа")
        btn_restore.connect("clicked", self.on_restore)
        vbox.pack_start(btn_restore, False, False, 0)

        self.buttons = [btn_sudo, btn_backup, btn_restore]

        log_hint = Gtk.Label(label=f"Лог: {Path.home() / '.local/share/sysbackup/sysbackup.log'}")
        log_hint.set_xalign(0)
        log_hint.set_selectable(True)
        vbox.pack_end(log_hint, False, False, 0)

    def set_busy(self, busy: bool, message: str = ""):
        for b in self.buttons:
            b.set_sensitive(not busy)
        self.status_label.set_text(message or ("Выполняется..." if busy else "Готово"))
        if busy:
            self.progress.pulse()
            self.progress.set_text("Работа...")
        else:
            self.progress.set_fraction(0.0)
            self.progress.set_text("")
        # Keep pulsing while busy
        if busy:
            GLib.timeout_add(150, self._pulse_if_busy)

    def _pulse_if_busy(self):
        if any(not b.get_sensitive() for b in self.buttons):
            self.progress.pulse()
            return True
        return False

    def show_message(self, title: str, message: str, error: bool = False):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR if error else Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def choose_folder(self, title: str, create: bool = False) -> str | None:
        action = Gtk.FileChooserAction.SELECT_FOLDER
        dialog = Gtk.FileChooserDialog(
            title=title,
            parent=self,
            action=action,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        if create:
            dialog.set_create_folders(True)
        response = dialog.run()
        folder = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        return folder

    def run_task(self, task_fn, success_title: str, success_msg: str):
        self.set_busy(True, "Выполняется операция...")

        def worker():
            try:
                task_fn()
                GLib.idle_add(self._on_success, success_title, success_msg)
            except Exception as e:
                logger.exception("Ошибка в GUI задаче")
                GLib.idle_add(self._on_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, title: str, msg: str):
        self.set_busy(False, "Готово")
        self.show_message(title, msg, error=False)
        return False

    def _on_error(self, msg: str):
        self.set_busy(False, "Ошибка")
        self.show_message("Ошибка", msg, error=True)
        return False

    def on_disable_sudo(self, _btn):
        def task():
            path = disable_sudo_password()
            return path
        # custom to include path in message
        self.set_busy(True, "Настройка sudoers...")

        def worker():
            try:
                path = disable_sudo_password()
                GLib.idle_add(self._on_success, "Готово", f"Правило создано: {path}")
            except Exception as e:
                logger.exception("Ошибка disable-sudo-password")
                GLib.idle_add(self._on_error, str(e))
        threading.Thread(target=worker, daemon=True).start()

    def on_backup(self, _btn):
        folder = self.choose_folder("Выберите пустую папку для бэкапа", create=True)
        if not folder:
            return

        def task():
            BackupManager(folder).create_backup()

        self.run_task(task, "Бэкап завершён", f"Резервная копия создана в:\n{folder}")

    def on_restore(self, _btn):
        folder = self.choose_folder("Выберите папку с бэкапом", create=False)
        if not folder:
            return
        confirm = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Подтвердите восстановление",
        )
        confirm.format_secondary_text(
            "Восстановление перезапишет системные конфигурации, пакеты и данные пользователя из бэкапа. Продолжить?"
        )
        resp = confirm.run()
        confirm.destroy()
        if resp != Gtk.ResponseType.OK:
            return

        def task():
            BackupManager(folder).restore_backup()

        self.run_task(task, "Восстановление завершено", f"Система восстановлена из:\n{folder}")


def main():
    win = SysBackupWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
