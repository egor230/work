from omegaconf import omegaconf
from omegaconf.base import ContainerMetadata
from omegaconf.dictconfig import DictConfig # <--- ИСПРАВЛЕНИЕ ОШИБКИ #1
from write_text_for_tkinter import *
import torch, tempfile, torchaudio, math, scipy.signal, typing
# from sber_gegaam import load_model
from sber_gegaam_without_cuda import load_model
torch.serialization.add_safe_globals([ContainerMetadata, DictConfig, typing.Any])
# Разрешаем необходимые типы для загрузки чекпоинта
warnings.filterwarnings("ignore", category=DeprecationWarning)
# Настройка директории кэша
# Отключаем предупреждения ALSA и JACK
# os.environ["PYAUDIO_ALSA_WARN"] = "0"
# os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
# os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера
# err = os.dup(2)  # Сохраняем оригинальный stderr
# os.dup2(os.open(os.devnull, os.O_WRONLY), 2)  # Перенаправляем вывод ошибок в /dev/null
torch.set_num_threads(8)
source_id = get_webcam_source_id()      # ← твоя функция
set_mute("0", source_id)# Проверка и загрузка модели GigaAMprint("0")
def check_model():
 models = ["v1_ssl", "v2_ssl", "ssl", "ctc", "v1_ctc", "v2_ctc", "rnnt", "v1_rnnt", "v2_rnnt", "emo", "v3_e2e_rnnt", "v3_e2e_ctc"]
 model_name = models[-2]  # v2_rnnt
 try:  # Проверка наличия файла (указываем полный путь, как это делает gigaam)
  cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/gigaam"
  model = load_model(model_name, cache_dir ) # 4. Указываем корневой каталог, где лежит модель (GigaAM сам добавит /gigaam)
  return model
 except Exception as e:
  print(e)
script_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/off mic.py"
script_dir = os.path.dirname(script_path)
script_name = os.path.basename(script_path)
# Команда для поиска PID по имени скрипта
check_cmd = f"pgrep -f '{script_name}'"
result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
# Если процесс найден — убиваем все экземпляры
if result.returncode == 0 and result.stdout.strip():
  pids = result.stdout.strip().split()
  for pid in pids:
   try:
    subprocess.run(["kill", "-9", pid], check=True)    # print(f"Убит запущенный процесс {script_name} с PID {pid}")
   except subprocess.CalledProcessError as e:
    pass
    # print(f"Не удалось убить PID {pid}: {e}")
# Формируем команду запуска
cmd = f'#!/bin/bash\n"/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python\" \"{script_path}\"'
def run_script():# Запускаем скрипт в отдельном демонизированном потоке
  subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
t = time.time()
model = check_model()
print(time.time() - t)
threading.Thread(target=run_script, daemon=True).start()# print("Скрипт запущен заново.")

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
      message = model.transcribe(array)
      if message !=" " and len(message) >0:
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

# buffer1.extend(audio_chunk.flatten())
# if mean_amp<7:
#  print(mean_amp)
#  arr = np.array(buffer1)
#  buffer1.clear()
#  print( model.transcribe(arr))
# array = enhance_speech_for_recognition(array)
# write(filename, fs, array)
# message = model.transcribe_longform(filename)
# os.unlink(filename)
'''
pip install \
  torch==2.5.1 \
  torchaudio==2.5.1 \
  torchvision==0.20.1 \
  numpy==1.26.4 \
  scipy==1.13.1 \
  librosa==0.10.2.post1 \
  sounddevice==0.5.3 \
  soundfile==0.13.1 \
  omegaconf==2.3.0 \
  hydra-core==1.3.2 \
  onnxruntime==1.18.0 \
  sentencepiece==0.2.0 \
  tqdm==4.66.4 \
  pyannote.audio==3.4.0 \
  transformers==4.42.3 \
  pynput==1.7.6 \
  PyQt5==5.15.11 \
  torch-audiomentations==0.12.0 \
  flash-attn==2.5.9 \
  llama-cpp-python==0.2.91
'''
