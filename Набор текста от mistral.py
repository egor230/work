# from PyQt6 import QtCore, QtWidgets, QtGui
# from PyQt6.QtGui import QIcon, QAction
# from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
# from write_text_for_tkinter import *
# import collections, time, math, numpy as np, os, threading, sys, subprocess, json, base64
# import websockets.sync as ws_sync
# from pathlib import Path
#pip install --upgrade transformers mistral-common[audio] torch torchaudio
import time
# pip install "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/vllm-0.16.0rc2.dev184+gbcd65c1f6-cp38-abi3-manylinux_2_31_x86_64.whl"
CACHE_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache"

from transformers import VoxtralForConditionalGeneration, AutoProcessor
import torch
import os

# Создаём папку, если нет
os.makedirs(CACHE_DIR, exist_ok=True)

model_id = "mistralai/Voxtral-Mini-3B-2507"

processor = AutoProcessor.from_pretrained(
    model_id,
    cache_dir=CACHE_DIR,               # ← здесь обязательно!
    trust_remote_code=True             # часто нужно для кастомных моделей Mistral
)

model = VoxtralForConditionalGeneration.from_pretrained(
    model_id,
    torch_dtype=torch.float16,         # float32 для CPU, если памяти мало — попробуй bfloat16
    device_map="auto",                 # "cpu" если хочешь явно без GPU
    cache_dir=CACHE_DIR,               # ← и здесь тоже!
    trust_remote_code=True
)

print("Модель и процессор загружены в:", CACHE_DIR)

# Дальше твой код с messages, inputs, generate...
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Summarize this audio in Russian."},
            {"type": "audio", "path": "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/temp.wav"}
        ]
    }
]

text = processor.apply_chat_template(messages, add_generation_prompt=True)

# audios принимает список байтов (bytes) аудиофайлов
with open("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/temp.wav", "rb") as f:
    audio_bytes = f.read()

inputs = processor(
    text=text,
    audios=[audio_bytes],              # список байтов
    return_tensors="pt"
).to(model.device)

with torch.inference_mode():
    generated_ids = model.generate(**inputs, max_new_tokens=300)

decoded = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
print(decoded)
print("Готово!")
'''
"/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/myenv/bin/python" /mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/Набор текста от mistral.py 
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
Traceback (most recent call last):
  File "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/Набор текста от mistral.py", line 22, in <module>
    processor = AutoProcessor.from_pretrained(
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/myenv/lib/python3.12/site-packages/transformers/models/auto/processing_auto.py", line 398, in from_pretrained
    return processor_class.from_pretrained(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/myenv/lib/python3.12/site-packages/transformers/processing_utils.py", line 1403, in from_pretrained
    return cls.from_args_and_dict(args, processor_dict, **instantiation_kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/myenv/lib/python3.12/site-packages/transformers/processing_utils.py", line 1172, in from_args_and_dict
    logger.info(f"Processor {processor}")
                            ^^^^^^^^^^^
  File "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/myenv/lib/python3.12/site-packages/transformers/processing_utils.py", line 776, in __repr__
    attributes_repr = [f"- {name}: {repr(getattr(self, name))}" for name in self.get_attributes()]
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/myenv/lib/python3.12/site-packages/transformers/tokenization_utils_base.py", line 1406, in __repr__
    added_tokens_decoder_rep = "\n\t".join([f"{k}: {v.__repr__()}," for k, v in self.added_tokens_decoder.items()])
                                                                                ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/myenv/lib/python3.12/site-packages/transformers/tokenization_utils_base.py", line 1403, in added_tokens_decoder
    raise NotImplementedError()
NotImplementedError

Process finished with exit code 1

'''




input()
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