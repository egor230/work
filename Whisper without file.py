import os
import sys, time
import numpy as np
import sounddevice as sd
import webrtcvad
from queue import Queue
from collections import deque
from faster_whisper import WhisperModel
import scipy.io.wavfile as wavfile
# Paths and model loading
cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/whisper/"
model_size = "large-v3"
model_dir = os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_size}", "snapshots")
if not os.path.exists(model_dir):
    print(f"Ошибка: Папка snapshots не найдена: {model_dir}. Убедитесь, что модель скачана.")
    sys.exit(1)
snapshot = next((d for d in os.listdir(model_dir) if os.path.isdir(os.path.join(model_dir, d))), None)
if not snapshot:
    print("Ошибка: Нет snapshots в кэше. Скачайте модель заново.")
    sys.exit(1)
model_path = os.path.join(model_dir, snapshot)
if not os.path.exists(os.path.join(model_path, "model.bin")):
    print(f"Ошибка: Файл model.bin не найден в {model_path}")
    sys.exit(1)
try:# Загрузка модели
    model = WhisperModel(model_path, device="cpu", compute_type="int8")
except Exception as e:
    print(f"Ошибка загрузки модели: {e}")
    sys.exit(1)

# Функция для потоковой записи аудио
def record_audio_stream(fs=16000, chunk_duration=0.03):
    queue = Queue()
    def callback(indata, frames, time_info, status):
        if status:
            print(f"Статус потока: {status}")
        queue.put(indata.copy())

    stream = sd.InputStream(samplerate=fs, channels=1, callback=callback, blocksize=int(fs * chunk_duration))
    return stream, queue
import threading
from scipy.io import wavfile

def transcribe_audio_segment(speech_segment, model):
 try:
   # Сохраняем аудио-сегмент во временный файл
   filename = "temp_speech_segment.wav"
   wavfile.write(filename, 16000, np.int16(speech_segment * 32767))
   # Транскрибируем аудио
   segments, info = model.transcribe(filename, beam_size=10,
                                     language="ru",  vad_filter=False, temperature=0.8)
   segments_list = list(segments)
   if not segments_list:
     print("Whisper не вернул сегментов")
   else:
    message = " ".join([seg.text.strip() for seg in segments_list])
    if message:
     print(f"Распознанный текст: {message}")
     
 except Exception as e:
   print(f"Ошибка при транскрипции: {e}")

# Функция обработки аудиопотока
def process_audio_stream(queue):
 # Инициализация параметров
 vad = webrtcvad.Vad(3)
 buffer = deque()
 silence_time = 0
 start_time = time.time()
 speech_detected = False
 last_speech_time = start_time
 min_length = 4
 min_silence_duration = 1.6
 print("Начинаю обработку аудиопотока...")
 with sd.InputStream():
  while True:
   audio_chunk = queue.get()
   if audio_chunk is None:#   print("Завершение работы...")
    break
   audio_int16 = np.int16(audio_chunk * 32767)
   is_speech_chunk = vad.is_speech(audio_int16.tobytes(), sample_rate=16000)
   current_time = time.time()
   buffer.append(audio_chunk)
   # Обнаружение начала речи
   if is_speech_chunk and not speech_detected:
    speech_segment = np.concatenate(buffer).astype(np.float32)
    if np.max(np.abs(speech_segment)) > 0.7:
     print("Начало записи (обнаружена речь)")
     speech_detected = True
     last_speech_time = current_time
   if speech_detected:
    if is_speech_chunk:
     last_speech_time = current_time # Речь продолжается — обнуляем паузу
     silence_time = 0
    else: # Тишина — накапливаем время
     silence_time += current_time - last_speech_time
     last_speech_time = current_time
     # Проверка на окончание речи
     if silence_time > 0.3:
      print(f"Время тишины: {silence_time:.2f} сек")
      # Сброс
   if (speech_detected and silence_time > min_silence_duration ) and buffer: # Проверяем, что буфер не пустой
    speech_segment = np.concatenate(buffer).astype(np.float32)  # Финальный сегмент
    segment_duration = len(speech_segment) / 16000
    print(f" длительность: {segment_duration:.2f} сек ")
    speech_detected = False
    silence_time = 0
    # input()
    t1 = threading.Thread(target=transcribe_audio_segment, args=(speech_segment, model,))# Поток завершится при завершении основной программы
    t1.start()
    buffer.clear()  # Сбрасываем буфер
    input()
# Запуск
stream, queue = record_audio_stream()
stream.start()

try:
    process_audio_stream(queue)
except KeyboardInterrupt:
    stream.stop()
    queue.put(None)
    print("Обработка остановлена.")