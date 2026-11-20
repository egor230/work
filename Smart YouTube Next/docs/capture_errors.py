#!/usr/bin/env python3
"""Небольшая ловушка логов ошибок приставки (до 5 МБ)."""
import os, re, subprocess

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_log.txt")
MAX = 5 * 1024 * 1024
KEEP = 4 * 1024 * 1024
PAT = re.compile(
    r"ErrorFixerController|ErrorLog|Chunk load failed|Unable to connect|"
    r"SocketTimeout|loadFormatInfo|Sabr|PoToken|BadWebView|MediaCodec|"
    r"Decoder|Auto-fix|Auto DNS|FATAL|AndroidRuntime|OOM|OutOfMemory|"
    r"network|timeout|failed|error",
    re.I,
)


def trim():
    if not os.path.exists(LOG) or os.path.getsize(LOG) <= MAX:
        return
    with open(LOG, "rb") as f:
        data = f.read()
    with open(LOG, "wb") as f:
        f.write(data[-KEEP:])


def main():
    proc = subprocess.Popen(["adb", "logcat", "-v", "time"], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, bufsize=1)
    for line in proc.stdout:
        if not PAT.search(line):
            continue
        # OkHttp dumps huge JSON bodies containing the word "error"/"errors";
        # keep only real transport/player failures from those lines.
        if "D/OkHttp" in line and not re.search(
            r"HTTP FAILED|SocketTimeout|Unable to connect|Chunk load failed|unknownHost|ConnectException",
            line, re.I,
        ):
            continue
        if True:
            with open(LOG, "a", encoding="utf-8", errors="replace") as f:
                f.write(line.rstrip("\n") + "\n")
            trim()


if __name__ == "__main__":
    main()
