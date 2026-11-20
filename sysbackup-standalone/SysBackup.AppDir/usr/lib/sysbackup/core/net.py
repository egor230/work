import json
import os
import socket
import threading
from pathlib import Path

from .backup import BackupManager
from .sudoers import disable_sudo_password
from .utils import CommandError, logger


def _send(conn: socket.socket, obj: dict) -> None:
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    conn.sendall(data)


def _handle_request(req: dict) -> dict:
    action = req.get("action")
    token_expected = os.environ.get("SYSBACKUP_SERVER_TOKEN")
    if token_expected:
        if req.get("token") != token_expected:
            return {"ok": False, "error": "Неверный токен"}
    try:
        if action == "ping":
            return {"ok": True, "result": "pong"}
        if action == "backup":
            dest = req.get("dest")
            if not dest:
                return {"ok": False, "error": "Не указан dest"}
            mgr = BackupManager(dest)
            path = mgr.create_backup()
            return {"ok": True, "result": str(path)}
        if action == "restore":
            source = req.get("source")
            if not source:
                return {"ok": False, "error": "Не указан source"}
            mgr = BackupManager(source)
            mgr.restore_backup()
            return {"ok": True, "result": str(Path(source).expanduser().resolve())}
        if action == "disable-sudo-password":
            p = disable_sudo_password()
            return {"ok": True, "result": str(p)}
        return {"ok": False, "error": f"Неизвестное действие: {action}"}
    except Exception as e:
        logger.exception("Ошибка обработки сетевого запроса")
        return {"ok": False, "error": str(e)}


def serve(host: str = "0.0.0.0", port: int = 8765, once: bool = False) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(5)
    logger.info("SysBackup server listening on %s:%s", host, port)
    print(f"SysBackup server listening on {host}:{port}")
    try:
        while True:
            conn, addr = srv.accept()
            logger.info("Connection from %s", addr)
            with conn:
                conn.settimeout(60)
                try:
                    f = conn.makefile("r", encoding="utf-8")
                    line = f.readline(1024 * 1024)
                    if not line:
                        continue
                    try:
                        req = json.loads(line)
                    except Exception as e:
                        _send(conn, {"ok": False, "error": f"Некорректный JSON: {e}"})
                        if once:
                            break
                        continue
                    resp = _handle_request(req)
                    _send(conn, resp)
                except Exception as e:
                    logger.exception("Ошибка соединения: %s", e)
                    try:
                        _send(conn, {"ok": False, "error": str(e)})
                    except Exception:
                        pass
            if once:
                break
    finally:
        srv.close()


def request(host: str, port: int, action: str, token: str | None = None, timeout: int = 3600, **payload) -> dict:
    req = {"action": action}
    if token:
        req["token"] = token
    req.update(payload)
    with socket.create_connection((host, port), timeout=30) as conn:
        conn.settimeout(timeout)
        conn.sendall((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
        f = conn.makefile("r", encoding="utf-8")
        line = f.readline(1024 * 1024)
        if not line:
            raise CommandError("Пустой ответ от сервера")
        resp = json.loads(line)
        if not resp.get("ok"):
            raise CommandError(resp.get("error", "Неизвестная ошибка сервера"))
        return resp
