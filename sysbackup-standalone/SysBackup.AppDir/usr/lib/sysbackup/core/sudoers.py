import os
import tempfile
from pathlib import Path

from .utils import CommandError, get_real_user, logger, run_command


SUDOERS_FILE = Path("/etc/sudoers.d/sysbackup-nopasswd")


def disable_sudo_password(username: str | None = None) -> Path:
    """Create /etc/sudoers.d/sysbackup-nopasswd allowing passwordless sudo for user."""
    user = username or os.environ.get("SUDO_USER") or get_real_user()
    if not user:
        raise CommandError("Не удалось определить имя пользователя")
    content = f"{user} ALL=(ALL) NOPASSWD: ALL\n"

    # If not root, we must use sudo to write. Use tee for simplicity.
    if os.geteuid() != 0:
        # This will prompt for password once if nopasswd not active
        logger.info("Запрос прав для отключения запроса пароля sudo (может потребоваться пароль один раз)")
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
            tf.write(content)
            tmp_path = tf.name
        try:
            run_command(["cp", tmp_path, str(SUDOERS_FILE)], sudo=True)
            run_command(["chmod", "0440", str(SUDOERS_FILE)], sudo=True)
            run_command(["chown", "root:root", str(SUDOERS_FILE)], sudo=True)
            # Validate syntax if visudo exists
            try:
                run_command(["visudo", "-cf", str(SUDOERS_FILE)], sudo=True)
            except Exception as e:
                logger.warning("visudo проверка не удалась/недоступна: %s", e)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    else:
        SUDOERS_FILE.write_text(content, encoding="utf-8")
        os.chmod(SUDOERS_FILE, 0o440)
        try:
            run_command(["chown", "root:root", str(SUDOERS_FILE)], sudo=False)
        except Exception:
            pass
        try:
            run_command(["visudo", "-cf", str(SUDOERS_FILE)], sudo=False)
        except Exception as e:
            logger.warning("visudo проверка не удалась/недоступна: %s", e)

    logger.info("Создан файл sudoers: %s", SUDOERS_FILE)
    return SUDOERS_FILE
