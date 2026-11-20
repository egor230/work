import json
import logging
import os
import pwd
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


LOG_DIR = Path.home() / ".local" / "share" / "sysbackup"
LOG_FILE = LOG_DIR / "sysbackup.log"


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("sysbackup")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    return logger


logger = setup_logging()


class CommandError(RuntimeError):
    pass


def run_command(
    cmd: Sequence[str],
    *,
    sudo: bool = False,
    check: bool = True,
    capture_output: bool = False,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    full_cmd: List[str] = list(cmd)
    if sudo and os.geteuid() != 0:
        full_cmd = ["sudo", "-n"] + full_cmd if sudo_nopasswd_active() else ["sudo"] + full_cmd
    logger.info("Running command: %s", " ".join(full_cmd))
    try:
        result = subprocess.run(
            full_cmd,
            check=False,
            text=True,
            capture_output=capture_output,
            cwd=cwd,
            env=env,
        )
    except FileNotFoundError as e:
        raise CommandError(f"Команда не найдена: {full_cmd[0]}") from e
    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip() if capture_output else ""
        stdout = (result.stdout or "").strip() if capture_output else ""
        msg = f"Команда завершилась с ошибкой ({result.returncode}): {' '.join(full_cmd)}"
        if stdout:
            msg += f"\nstdout: {stdout}"
        if stderr:
            msg += f"\nstderr: {stderr}"
        logger.error(msg)
        raise CommandError(msg)
    return result


def sudo_nopasswd_active() -> bool:
    try:
        result = subprocess.run(["sudo", "-n", "true"], check=False, capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def ensure_root() -> None:
    if os.geteuid() == 0:
        return
    # Trigger sudo prompt early if needed
    run_command(["true"], sudo=True)


def get_real_user() -> str:
    if os.geteuid() == 0 and os.environ.get("SUDO_USER"):
        return os.environ["SUDO_USER"]
    return pwd.getpwuid(os.getuid()).pw_name


def get_home_dir(username: Optional[str] = None) -> Path:
    user = username or get_real_user()
    return Path(pwd.getpwnam(user).pw_dir)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        logger.warning("Источник не найден, пропуск: %s", src)
        return
    ensure_dir(dst.parent)
    if src.is_dir():
        if dst.exists():
            # merge copy
            for root, dirs, files in os.walk(src):
                rel = Path(root).relative_to(src)
                target_root = dst / rel
                target_root.mkdir(parents=True, exist_ok=True)
                for d in dirs:
                    (target_root / d).mkdir(parents=True, exist_ok=True)
                for f in files:
                    shutil.copy2(Path(root) / f, target_root / f)
        else:
            shutil.copytree(src, dst, symlinks=True)
    else:
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)


def rsync_copy(src: Path, dst: Path, excludes: Optional[Iterable[str]] = None, sudo: bool = False, delete: bool = False) -> None:
    if not command_exists("rsync"):
        raise CommandError("rsync не найден. Установите пакет rsync и повторите попытку.")
    if not src.exists():
        logger.warning("Источник не найден, пропуск rsync: %s", src)
        return
    ensure_dir(dst)
    cmd = ["rsync", "-aAXH", "--numeric-ids", "--info=progress2"]
    if delete:
        cmd.append("--delete")
    for ex in (excludes or []):
        cmd.extend(["--exclude", ex])
    src_str = str(src)
    if src.is_dir() and not src_str.endswith("/"):
        src_str += "/"
    dst_str = str(dst)
    if not dst_str.endswith("/"):
        dst_str += "/"
    cmd.extend([src_str, dst_str])
    run_command(cmd, sudo=sudo)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def read_os_release() -> dict:
    data = {}
    path = Path("/etc/os-release")
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip('"')
    return data


def write_backup_info(backup_dir: Path, exclusions: Optional[list] = None, extra: Optional[dict] = None) -> None:
    info = {
        "created_at": datetime.now().isoformat(),
        "user": get_real_user(),
        "os_release": read_os_release(),
        "exclusions": exclusions or [],
    }
    if extra:
        info.update(extra)
    (backup_dir / "backup_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def load_backup_info(backup_dir: Path) -> dict:
    path = backup_dir / "backup_info.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def disk_usage_free(path: Path) -> int:
    p = Path(path)
    if not p.exists():
        p = p.parent
    st = os.statvfs(str(p))
    return st.f_bavail * st.f_frsize


def format_bytes(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024 or unit == "TB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def preflight_check(require_root: bool = True) -> list[str]:
    issues = []
    for tool in ["rsync", "sudo"]:
        if not command_exists(tool):
            issues.append(f"Не найдена обязательная утилита: {tool}")
    if require_root and os.geteuid() != 0 and not command_exists("sudo"):
        issues.append("Требуются права root, но sudo недоступен")
    return issues


def verify_backup_structure(backup_dir: Path) -> list[str]:
    issues = []
    if not backup_dir.exists() or not backup_dir.is_dir():
        return [f"Папка бэкапа не найдена: {backup_dir}"]
    expected_any = [
        backup_dir / "packages",
        backup_dir / "system_configs",
        backup_dir / "user_data",
        backup_dir / "backup_info.json",
    ]
    if not any(p.exists() for p in expected_any):
        issues.append("Папка не похожа на бэкап SysBackup (нет packages/system_configs/user_data/backup_info.json)")
    return issues
