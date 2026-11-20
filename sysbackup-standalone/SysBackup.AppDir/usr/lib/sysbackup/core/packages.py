import glob
import shutil
from pathlib import Path
from typing import List

from .utils import CommandError, command_exists, ensure_dir, logger, run_command


class PackageManager:
    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.packages_dir = backup_dir / "packages"
        self.apt_cache_dir = self.packages_dir / "apt_cache"
        self.apt_repos_dir = self.packages_dir / "apt_repos"
        self.flatpak_dir = self.packages_dir / "flatpak_apps"
        self.snap_dir = self.packages_dir / "snap_apps"
        for d in [self.packages_dir, self.apt_cache_dir, self.apt_repos_dir, self.flatpak_dir, self.snap_dir]:
            ensure_dir(d)

    # ---------- APT ----------
    def backup_apt(self) -> None:
        if not command_exists("dpkg"):
            logger.info("dpkg не найден, пропуск бэкапа APT")
            return
        logger.info("Сохранение списка APT пакетов")
        res = run_command(["dpkg", "--get-selections"], sudo=False, capture_output=True)
        (self.packages_dir / "apt_packages.list").write_text(res.stdout, encoding="utf-8")

        # Repos
        logger.info("Копирование конфигураций APT репозиториев")
        sources = Path("/etc/apt/sources.list")
        if sources.exists():
            shutil.copy2(sources, self.apt_repos_dir / "sources.list")
        sources_d = Path("/etc/apt/sources.list.d")
        if sources_d.exists():
            dst = self.apt_repos_dir / "sources.list.d"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(sources_d, dst, symlinks=True)

        # Cache .deb files
        cache = Path("/var/cache/apt/archives")
        if cache.exists():
            logger.info("Копирование кэша APT (.deb)")
            for deb in cache.glob("*.deb"):
                shutil.copy2(deb, self.apt_cache_dir / deb.name)

        # Try to download missing/ensure availability of installed packages (best effort)
        self._download_apt_packages_best_effort()

    def _download_apt_packages_best_effort(self) -> None:
        if command_exists("apt-clone"):
            try:
                logger.info("Попытка apt-clone clone (best effort)")
                clone_file = self.packages_dir / "apt-clone.tar.gz"
                run_command(["apt-clone", "clone", str(clone_file)], sudo=True)
                return
            except Exception as e:
                logger.warning("apt-clone не удался: %s", e)
        # Fallback: download installed packages into cache dir
        try:
            if not command_exists("apt-cache") or not command_exists("apt-get"):
                return
            logger.info("Попытка скачать .deb для установленных пакетов (best effort)")
            # Get installed package names
            res = run_command(["dpkg-query", "-W", "-f=${Package}\n"], capture_output=True)
            pkgs = [p.strip() for p in res.stdout.splitlines() if p.strip()]
            if not pkgs:
                return
            # Download in chunks to avoid huge command lines
            chunk_size = 50
            for i in range(0, len(pkgs), chunk_size):
                chunk = pkgs[i:i + chunk_size]
                try:
                    run_command(["apt-get", "download"] + chunk, sudo=False, cwd=str(self.apt_cache_dir))
                except Exception as e:
                    logger.warning("Не удалось скачать часть пакетов: %s", e)
        except Exception as e:
            logger.warning("Ошибка при скачивании APT пакетов: %s", e)

    def restore_apt(self) -> None:
        if not command_exists("dpkg") or not command_exists("apt-get"):
            logger.info("APT/dpkg не найдены, пропуск восстановления APT")
            return
        # Restore repos
        src_sources = self.apt_repos_dir / "sources.list"
        if src_sources.exists():
            logger.info("Восстановление /etc/apt/sources.list")
            run_command(["cp", str(src_sources), "/etc/apt/sources.list"], sudo=True)
        src_sources_d = self.apt_repos_dir / "sources.list.d"
        if src_sources_d.exists():
            logger.info("Восстановление /etc/apt/sources.list.d")
            run_command(["mkdir", "-p", "/etc/apt/sources.list.d"], sudo=True)
            run_command(["cp", "-a", str(src_sources_d) + "/.", "/etc/apt/sources.list.d/"], sudo=True)

        debs = sorted(self.apt_cache_dir.glob("*.deb"))
        if debs:
            logger.info("Установка .deb пакетов из кэша (%d файлов)", len(debs))
            try:
                # Prefer dpkg -i + fix deps in offline-friendly way where possible
                run_command(["dpkg", "-i"] + [str(d) for d in debs], sudo=True, check=False)
                run_command(["apt-get", "-f", "install", "-y"], sudo=True, check=False)
            except Exception as e:
                logger.warning("Ошибка при установке локальных .deb, пробуем apt-get install: %s", e)
                try:
                    cmd = ["apt-get", "install", "-y", "--allow-downgrades"] + [str(d) for d in debs]
                    run_command(cmd, sudo=True, check=False)
                except Exception as e2:
                    logger.warning("Не удалось установить .deb через apt-get: %s", e2)

        sel = self.packages_dir / "apt_packages.list"
        if sel.exists():
            try:
                logger.info("Применение dpkg --set-selections")
                with sel.open("r", encoding="utf-8") as f:
                    data = f.read()
                import subprocess
                if shutil.which("sudo") and __import__("os").geteuid() != 0:
                    p = subprocess.run(["sudo", "dpkg", "--set-selections"], input=data, text=True, capture_output=True)
                else:
                    p = subprocess.run(["dpkg", "--set-selections"], input=data, text=True, capture_output=True)
                if p.returncode != 0:
                    logger.warning("dpkg --set-selections завершился с кодом %s: %s", p.returncode, (p.stderr or "").strip())
                else:
                    # Best effort: try to apply selection state; may require repos/network in some cases
                    run_command(["apt-get", "dselect-upgrade", "-y"], sudo=True, check=False)
            except Exception as e:
                logger.warning("Не удалось полностью применить selections: %s", e)

    # ---------- Flatpak ----------
    def backup_flatpak(self) -> None:
        if not command_exists("flatpak"):
            logger.info("flatpak не найден, пропуск")
            return
        logger.info("Сохранение списка Flatpak приложений")
        try:
            res = run_command(["flatpak", "list", "--app", "--columns=ref"], capture_output=True)
            (self.packages_dir / "flatpak_list.txt").write_text(res.stdout, encoding="utf-8")
            refs = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception as e:
            logger.warning("Не удалось получить список Flatpak: %s", e)
            return

        if not refs:
            return
        # Create offline repo/bundles via flatpak create-usb. create-usb expects a mount point; use dir as target.
        try:
            logger.info("Создание офлайн-копии Flatpak (create-usb)")
            cmd = ["flatpak", "create-usb", str(self.flatpak_dir)] + refs
            run_command(cmd, sudo=False)
        except Exception as e:
            logger.warning("flatpak create-usb не удался, пробуем bundle для каждого приложения: %s", e)
            for ref in refs:
                safe = ref.replace("/", "_").replace(":", "_")
                bundle = self.flatpak_dir / f"{safe}.flatpak"
                try:
                    run_command(["flatpak", "build-bundle", str(Path.home() / ".local/share/flatpak/repo"), str(bundle), ref], check=False)
                except Exception as e2:
                    logger.warning("Не удалось создать bundle для %s: %s", ref, e2)

    def restore_flatpak(self) -> None:
        if not command_exists("flatpak"):
            logger.info("flatpak не найден, пропуск")
            return
        # Try install from sideload repo created by create-usb
        repo_file = self.flatpak_dir / ".ostree/repo/config"
        if repo_file.exists():
            logger.info("Установка Flatpak из офлайн-репозитория")
            list_file = self.packages_dir / "flatpak_list.txt"
            if list_file.exists():
                refs = [l.strip() for l in list_file.read_text(encoding="utf-8").splitlines() if l.strip()]
                for ref in refs:
                    try:
                        run_command(["flatpak", "install", "-y", "--sideload-repo=" + str(self.flatpak_dir / ".ostree/repo"), ref], sudo=True, check=False)
                    except Exception as e:
                        logger.warning("Не удалось установить %s из sideload repo: %s", ref, e)
        # Bundles fallback
        for bundle in self.flatpak_dir.glob("*.flatpak"):
            try:
                logger.info("Установка Flatpak bundle: %s", bundle.name)
                run_command(["flatpak", "install", "-y", "--bundle", str(bundle)], sudo=True, check=False)
            except Exception as e:
                logger.warning("Не удалось установить bundle %s: %s", bundle, e)

    # ---------- Snap ----------
    def backup_snap(self) -> None:
        if not command_exists("snap"):
            logger.info("snap не найден, пропуск")
            return
        logger.info("Сохранение списка Snap пакетов")
        try:
            res = run_command(["snap", "list"], capture_output=True)
            lines = res.stdout.splitlines()
            names: List[str] = []
            for i, line in enumerate(lines):
                if i == 0:
                    continue
                parts = line.split()
                if parts:
                    names.append(parts[0])
            (self.packages_dir / "snap_list.txt").write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")
        except Exception as e:
            logger.warning("Не удалось получить список Snap: %s", e)
            return
        if not names:
            return
        for name in names:
            try:
                logger.info("Скачивание snap: %s", name)
                run_command(["snap", "download", name], cwd=str(self.snap_dir), check=False)
            except Exception as e:
                logger.warning("Не удалось скачать snap %s: %s", name, e)

    def restore_snap(self) -> None:
        if not command_exists("snap"):
            logger.info("snap не найден, пропуск")
            return
        # Install from downloaded .assert and .snap pairs
        asserts = sorted(self.snap_dir.glob("*.assert"))
        snaps = sorted(self.snap_dir.glob("*.snap"))
        # Try to pair by base name prefix
        for snap_file in snaps:
            base = snap_file.stem
            # common: name_revision.snap with matching name_revision.assert
            assert_file = self.snap_dir / f"{base}.assert"
            if not assert_file.exists():
                # try find assert starting with package name
                prefix = base.split("_")[0]
                candidates = list(self.snap_dir.glob(f"{prefix}_*.assert"))
                assert_file = candidates[0] if candidates else None
            try:
                if assert_file and assert_file.exists():
                    run_command(["snap", "ack", str(assert_file)], sudo=True, check=False)
                run_command(["snap", "install", str(snap_file), "--dangerous"], sudo=True, check=False)
                logger.info("Установлен snap: %s", snap_file.name)
            except Exception as e:
                logger.warning("Не удалось установить snap %s: %s", snap_file, e)

    def backup_all(self) -> None:
        self.backup_apt()
        self.backup_flatpak()
        self.backup_snap()

    def restore_all(self) -> None:
        self.restore_apt()
        self.restore_flatpak()
        self.restore_snap()
