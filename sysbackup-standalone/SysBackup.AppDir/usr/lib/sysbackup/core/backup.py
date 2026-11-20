import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .packages import PackageManager
from .utils import (
    CommandError,
    disk_usage_free,
    ensure_dir,
    ensure_root,
    format_bytes,
    get_home_dir,
    get_real_user,
    logger,
    preflight_check,
    rsync_copy,
    verify_backup_structure,
    write_backup_info,
)


class BackupManager:
    def __init__(self, dest: str | Path):
        self.dest = Path(dest).expanduser().resolve()
        self.packages_dir = self.dest / "packages"
        self.system_configs_dir = self.dest / "system_configs"
        self.user_data_dir = self.dest / "user_data"

    def validate_destination(self, for_backup: bool = True) -> None:
        if for_backup:
            ensure_dir(self.dest)
            try:
                entries = list(self.dest.iterdir())
                if entries:
                    logger.warning("Папка назначения не пуста: %s (существующие файлы могут быть перезаписаны/дополнены)", self.dest)
            except Exception:
                pass
            free = disk_usage_free(self.dest)
            logger.info("Свободное место в назначении: %s", format_bytes(free))
        else:
            if not self.dest.exists() or not self.dest.is_dir():
                raise CommandError(f"Папка бэкапа не найдена: {self.dest}")
            issues = verify_backup_structure(self.dest)
            if issues:
                raise CommandError("; ".join(issues))

    def _write_status(self, status: str, **extra):
        payload = {"status": status, "updated_at": datetime.now().isoformat(), **extra}
        try:
            (self.dest / "backup_status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def create_backup(self, exclude_home: Optional[Iterable[str]] = None) -> Path:
        issues = preflight_check(require_root=True)
        if issues:
            raise CommandError("Проверка окружения не пройдена: " + "; ".join(issues))
        self.validate_destination(for_backup=True)
        ensure_root()
        ensure_dir(self.packages_dir)
        ensure_dir(self.system_configs_dir)
        ensure_dir(self.user_data_dir)

        excludes = list(exclude_home or [".cache"])
        logger.info("Начало создания бэкапа в %s", self.dest)
        self._write_status("in_progress", phase="start")
        try:
            pm = PackageManager(self.dest)
            self._write_status("in_progress", phase="packages")
            pm.backup_all()

            self._write_status("in_progress", phase="etc")
            logger.info("Копирование /etc")
            rsync_copy(Path("/etc"), self.system_configs_dir / "etc", sudo=True)

            self._write_status("in_progress", phase="home")
            user = get_real_user()
            home = get_home_dir(user)
            logger.info("Копирование домашней директории: %s", home)
            rsync_copy(home, self.user_data_dir / "home", excludes=excludes, sudo=True)

            write_backup_info(self.dest, exclusions=excludes, extra={"source_home": str(home), "source_user": user})
            self._write_status("completed")
            logger.info("Бэкап успешно создан: %s", self.dest)
            return self.dest
        except Exception as e:
            self._write_status("failed", error=str(e))
            raise

    def restore_backup(self) -> None:
        issues = preflight_check(require_root=True)
        if issues:
            raise CommandError("Проверка окружения не пройдена: " + "; ".join(issues))
        self.validate_destination(for_backup=False)
        ensure_root()
        logger.info("Начало восстановления из %s", self.dest)
        self._write_status("restore_in_progress", phase="start")
        try:
            pm = PackageManager(self.dest)
            self._write_status("restore_in_progress", phase="packages")
            pm.restore_all()

            etc_src = self.system_configs_dir / "etc"
            if etc_src.exists():
                self._write_status("restore_in_progress", phase="etc")
                logger.info("Восстановление /etc")
                rsync_copy(etc_src, Path("/etc"), sudo=True)
            else:
                logger.warning("В бэкапе отсутствует system_configs/etc")

            home_src = self.user_data_dir / "home"
            if home_src.exists():
                self._write_status("restore_in_progress", phase="home")
                user = get_real_user()
                home = get_home_dir(user)
                logger.info("Восстановление домашней директории в %s", home)
                rsync_copy(home_src, home, sudo=True)
                try:
                    from .utils import run_command
                    run_command(["chown", "-R", f"{user}:{user}", str(home)], sudo=True, check=False)
                except Exception as e:
                    logger.warning("Не удалось восстановить владельца файлов home: %s", e)
            else:
                logger.warning("В бэкапе отсутствует user_data/home")

            self._write_status("restore_completed")
            logger.info("Восстановление завершено")
        except Exception as e:
            self._write_status("restore_failed", error=str(e))
            raise

