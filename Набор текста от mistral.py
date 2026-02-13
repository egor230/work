from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from write_text_for_tkinter import *
import collections, time, math, numpy as np, os, threading, sys, subprocess, json, base64
import websockets.sync as ws_sync
from pathlib import Path

# ------------------------------------------------------------
#  ЖЁСТКАЯ ПРОВЕРКА И ЗАГРУЗКА МОДЕЛИ В ТВОЮ ПАПКУ (при старте)
# ------------------------------------------------------------
CACHE_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache"
MODEL_NAME = "mistralai/Voxtral-Mini-4B-Realtime-2602"
os.makedirs(CACHE_DIR, exist_ok=True)

# vLLM сам скачает модель, если её нет — просто импортируем и создаём LLM
from vllm import LLM
print("⏳ Проверка модели (при первом запуске будет загрузка ~8 ГБ)...")
_ = LLM(model=MODEL_NAME, device="cpu", dtype="float32", download_dir=CACHE_DIR)
print("✅ Модель готова")

# ------------------------------------------------------------
#  ЗАПУСК vLLM СЕРВЕРА (фоновый процесс)
# ------------------------------------------------------------
def start_server():
    return subprocess.Popen([
        "vllm", "serve", MODEL_NAME,
        "--device", "cpu",
        "--dtype", "float32",
        "--download-dir", CACHE_DIR,
        "--port", "8000",
        "--max-model-len", "30000"        # экономия RAM на CPU
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

server = start_server()
time.sleep(10)   # ждём, пока сервер поднимется
import base64
import json
from websockets.sync.client import connect  # ← это правильно (websockets 12+)

# ------------------------------------------------------------

def transcribe_voxtral(audio_array: np.ndarray) -> str:
    # Конвертация float32 [-1..1] → int16 PCM
    audio_int16 = np.clip(audio_array * 32767, -32768, 32767).astype(np.int16)
    audio_b64 = base64.b64encode(audio_int16.tobytes()).decode('utf-8')

    try:
        with connect("ws://localhost:8000/v1/realtime", open_timeout=12, close_timeout=8) as ws:
            # 1. Получаем session.created (игнорируем или логируем)
            init_msg = json.loads(ws.recv())
            print("Session:", init_msg.get("type"))  # обычно "session.created"

            # 2. Опционально: обновить параметры сессии (delay, language и т.д.)
            ws.send(json.dumps({
                "type": "session.update",
                "transcription_delay_ms": 480,  # или 200–2400, минимум 80
                # "language": "ru"  # автоопределение обычно лучше
            }))

            # 3. Отправляем весь буфер как один append → commit
            ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }))
            ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

            # 4. Запрашиваем генерацию
            ws.send(json.dumps({"type": "response.create"}))

            # 5. Ждём финальный транскрипт
            while True:
                msg = json.loads(ws.recv())
                msg_type = msg.get("type")

                if msg_type == "response.output_transcript.done":
                    text = msg.get("text", "").strip()
                    return text

                elif msg_type in ("error", "response.done"):  # или другие завершающие
                    print("Завершено с ошибкой или без текста:", msg)
                    return ""

                # Можно обрабатывать delta если хочешь частичные результаты
                # elif msg_type == "response.output_transcript.delta":
                #     print("Δ:", msg.get("delta"))

    except Exception as e:
        print(f"WebSocket / STT error: {type(e).__name__}: {e}")
        return ""
# ------------------------------------------------------------
#  ТВОЙ ПОТОК (микрофон + вызов Voxtral вместо Whisper)
# ------------------------------------------------------------
os.environ["OMP_NUM_THREADS"] = "8"
source_id = get_webcam_source_id()
set_mute("0", source_id)

class MyThread(QtCore.QThread):
    mysignal = QtCore.pyqtSignal(str)
    icon_signal = QtCore.pyqtSignal(str)
    mic_toggle_signal = QtCore.pyqtSignal(bool)

    def __init__(self, icon1_path, icon2_path, parent=None):
        super().__init__(parent)
        self.icon1_path = icon1_path
        self.icon2_path = icon2_path
        self.mic = True
        self._stop = False
        self.mic_toggle_signal.connect(self.set_mic_status)

    def set_mic_status(self, status): self.mic = status

    def run(self):
        import sounddevice as sd
        while not self._stop:
            buffer = collections.deque()
            silence_time = 0
            last_speech_time = time.time()
            min_silence_duration = 1.1
            fs = 16000
            start = False
            self.icon_signal.emit(self.icon1_path)
            try:
                if self.mic:
                    with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
                        while True:
                            audio_chunk, _ = stream.read(16096)
                            mean_amp = math.ceil(np.mean(np.abs(audio_chunk)) * 100)
                            if mean_amp > 4:
                                last_speech_time = time.time()
                                silence_time = 0
                                start = True
                            if start:
                                buffer.append(audio_chunk.astype(np.float32).flatten())
                                if silence_time > min_silence_duration:
                                    array = np.concatenate(buffer)
                                    if len(array)/fs > 3:
                                        self.icon_signal.emit(self.icon2_path)
                                        start = False
                                        break
                                else:
                                    silence_time += time.time() - last_speech_time
                                    last_speech_time = time.time()
                    if is_speech(0.0340, array):
                        # ---------- ЗАМЕНА: Voxtral вместо Whisper ----------
                        text = transcribe_voxtral(array)
                        if text and len(text) > 0:
                            threading.Thread(target=process_text, args=(text,), daemon=True).start()
            except Exception as ex:
                print(ex)

    def stop(self): self._stop = True

# ------------------------------------------------------------
#  ТВОЁ ОКНО (без изменений)
# ------------------------------------------------------------
class MyWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon1_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/voice.png"
        self.icon2_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/stop.png"
        self.mic = True
        self.tray_icon = QSystemTrayIcon(QIcon(self.icon1_path), self)
        menu = QMenu()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_t)
        menu.addAction(quit_action)
        self.mythread = MyThread(self.icon1_path, self.icon2_path)
        self.mythread.icon_signal.connect(self.change_icon)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.setToolTip("ON")
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()
        self.mythread.start()
        self.server = server   # сохраняем, чтобы убить при выходе

    def change_icon(self, icon_path):
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        try:
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self.mic = not self.mic
                self.mythread.mic_toggle_signal.emit(self.mic)
                self.tray_icon.setToolTip("ON" if self.mic else "OFF")
                set_mute("0" if self.mic else "1")
                new_icon = self.icon1_path if self.mic else self.icon2_path
                self.tray_icon.setIcon(QIcon(new_icon))
                self.tray_icon.show()
        except Exception as e:
            print(f"Error: {e}")

    def quit_t(self):
        self.mythread.stop()
        self.mythread.wait()
        self.server.terminate()
        QApplication.quit()

# ------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    sys.exit(app.exec())