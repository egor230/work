from omegaconf import OmegaConf
from omegaconf.base import ContainerMetadata
from omegaconf.dictconfig import DictConfig
from write_text_for_tkinter import *
import torch, tempfile, torchaudio, math, scipy.signal, typing
import os, subprocess, time, threading, collections, warnings
import numpy as np, sounddevice as sd, tkinter as tk
import tempfile
import soundfile as sf  # pip install soundfile если нет
# Новый правильный импорт для Qwen3-ASR
from qwen_asr import Qwen3ASRModel
import warnings
import logging

# Скрываем только это конкретное предупреждение
warnings.filterwarnings(
    "ignore",
    message="Setting `pad_token_id` to `eos_token_id`",
    category=UserWarning,  # или просто warnings.Warning
)

# Или полностью отключить transformers-логи (если много мусора)
logging.getLogger("transformers").setLevel(logging.ERROR)
torch.set_num_threads(8)
# warnings.filterwarnings("ignore", category=DeprecationWarning)

source_id = get_webcam_source_id()
set_mute("0", source_id)

def check_model():
 try:
   cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/Qwen3-ASR-1.7B"
   print("Загружаем Qwen3-ASR-1.7B из локальной папки...")
   t_start = time.time()

   model = Qwen3ASRModel.from_pretrained( cache_dir,
       dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
       device_map="cuda:0" if torch.cuda.is_available() else "cpu",
       trust_remote_code=True,   )

   print(f"Модель успешно загружена за {time.time() - t_start:.2f} сек")
   return model

 except Exception as e:
   print(f"Ошибка загрузки модели: {e}")
   print("Проверь: pip install -U qwen-asr; папка содержит config.json и safetensors")
   return None

script_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/off mic.py"
script_dir = os.path.dirname(script_path)
script_name = os.path.basename(script_path)
check_cmd = f"pgrep -f '{script_name}'"
result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
if result.returncode == 0 and result.stdout.strip():
    pids = result.stdout.strip().split()
    for pid in pids:
     try:
      subprocess.run(["kill", "-9", pid], check=True)
     except subprocess.CalledProcessError as e:
       pass

cmd = f'#!/bin/bash\n"/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python" "{script_path}"'
def run_script():
  subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

t = time.time()
model = check_model()
print(f"Время загрузки модели: {time.time() - t:.2f} сек")
threading.Thread(target=run_script, daemon=True).start()

def update_label(root, label, model, source_id):
 def record_and_process():
  try:
    if not get_mute_status(source_id):
      root.withdraw()
    else:
     # Показ окна с начальной надписью
     root.geometry("100x20+700+1025")
     label.config(text="Говорите...")
     root.deiconify()
     root.update()
     fs = 16*1000
     silence_time = 0
     last_speech_time = time.time()
     min_silence_duration = 1.0
     start= False
     pause_count = 0
     buffer = collections.deque()  # ИЗМЕНЕНО: используем список вместо Queue
     with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
      while True:
       if not get_mute_status(source_id):
         root.withdraw()
       else:
        audio_chunk, overflowed = stream.read(16096)  # Читаем аудио порциями
        mean_amp = np.mean(np.abs(audio_chunk)) * 100
        mean_amp = math.ceil(mean_amp)#
        if mean_amp > 4:#
         last_speech_time = time.time()
         silence_time = 0
         start = True
        if start:
         buffer.append(audio_chunk.astype(np.float32).flatten())
         if mean_amp <9:
          # array = np.fromiter((item for chunk in buffer for item in chunk), dtype=np.float32)
          # text= model.transcribe(array)
          # print(text)
          pause_count += 1  # Начало паузы
         if silence_time > min_silence_duration:
          root.withdraw()
          array = np.fromiter((item for chunk in buffer for item in chunk), dtype=np.float32)
          duration = len(array) / fs
          if duration > 4:
           start= False
           buffer.clear()  # Сбрасываем буфер
          break
         else:
          silence_time += time.time() - last_speech_time
          last_speech_time = time.time()
     root.withdraw()#
     if is_speech(0.030, array):
      array = boost_by_db_range(array, -4,-20)
      print(f"Пауз обнаружено: {pause_count}")
      pause_count=0
      with torch.no_grad(), torch.inference_mode():
       with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, array, fs)
        results = model.transcribe(audio=tmp.name,
         language="Russian"  # или None
        )
       os.unlink(tmp.name)  # удали файл после
      if results and len(results) > 0:
       message = results[0].text.strip()
       threading.Thread(target=process_text, args=(message,), daemon=True).start()
     buffer.clear()  # Сбрасываем буфер
    root.after(1000, lambda: update_label(root, label, model, source_id))
  except Exception as e:
    print(f"Ошибка: {e}")  # Добавьте остановку потока в случае ошибки
    try:
      stream.stop()
      stream.close()
    except:
      pass
    root.after(1000, lambda: update_label(root, label, model, source_id))
    pass
 # Проверка статуса микрофона
 if get_mute_status(source_id):
  threading.Thread(target=record_and_process).start()
 else:
  root.withdraw()
  root.after(2000, lambda: update_label(root, label, model, source_id))
# ===== Интерфейс =====
root = tk.Tk()
frame = tk.Frame(root)
label = tk.Label(frame, text="...", font='Times 14', anchor="center")
label.pack(padx=3, fill=tk.X, expand=True)
frame.pack(fill=tk.X)
root.overrideredirect(True)
root.resizable(True, True)
root.attributes("-topmost", True)
update_label(root, label, model, source_id)
root.mainloop()