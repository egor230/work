from write_text import *
import webrtcvad
from collections import deque
from faster_whisper import WhisperModel
import scipy.io.wavfile as wavfile
from scipy.signal import butter, lfilter
import librosa
from pydub import AudioSegment
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
subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)  # вкл микрофон.
subprocess.run(['pactl', 'set-source-volume', "54", '65000'])
try:# Загрузка модели
    model = WhisperModel(model_path, device="cpu", compute_type="int8")
except Exception as e:
    print(f"Ошибка загрузки модели: {e}")
    sys.exit(1)
# Функция для потоковой записи аудио
def record_audio_stream(fs=48000, chunk_duration=0.03):
  queue = Queue()
  def callback(indata, frames, time_info, status):
   if status:
       print(f"Статус потока: {status}")
   queue.put(indata.copy())

  stream = sd.InputStream(samplerate=fs, channels=1, callback=callback, blocksize=int(fs * chunk_duration))
  return stream, queue

# Функция для bandpass фильтра
def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def bandpass_filter(data, lowcut=1000, highcut=4000, fs=48000, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    return lfilter(b, a, data)
def transcribe_audio_segment(speech_segment, model):
 try:   # Сохраняем аудио-сегмент во временный файл
  filename = "temp.wav"
  # Шаг 1: Шумоподавление
  # S = np.abs(librosa.stft(speech_segment))
  # S_clean = librosa.decompose.nn_filter(S, aggregate=np.median, metric='cosine')
  # speech_segment_clean = librosa.istft(S_clean)
  # # Шаг 2: Эквализация
  # speech_segment_eq = bandpass_filter(speech_segment, lowcut=1000, highcut=4000, fs=48000)
  # # Шаг 4: Нормализация
  # max_amplitude = np.max(np.abs(speech_segment_compressed))
  # if max_amplitude > 0:
  #  speech_segment_compressed = speech_segment_compressed / max_amplitude * 0.95

  # Шаг 5: Сохранение
  wavfile.write(filename, 48000, np.int16(speech_segment * 32767))
  # Проверка звука
  if is_speech():
   # Транскрибируем аудио
   segments, info = model.transcribe(filename, beam_size=10, language="ru",
                                     vad_filter=True, temperature=0.7, condition_on_previous_text=True)
   segments_list = list(segments)
   if not segments_list:
     return
   else:
    message = " ".join([seg.text.strip() for seg in segments_list])
    if message:
     threading.Thread(target=process_text, args=(message,), daemon=True).start()
     # print("stop")
     # input()
 except Exception as e:
   print(f"Ошибка при транскрипции: {e}")

def process_audio_stream(queue):# Функция обработки аудиопотока
 vad = webrtcvad.Vad(3) # Инициализация параметров
 buffer = deque()
 silence_time = 0
 speech_detected = False
 last_speech_time = time.time()
 min_length = 4
 min_silence_duration = 1.6
 print("Начинаю обработку аудиопотока...")
 mid=0.18
 with sd.InputStream():
  while True:
   audio_chunk = queue.get()
   if audio_chunk is None:#   print("Завершение работы...")
    break
   audio_int16 = np.int16(audio_chunk * 65534)
   is_speech_chunk = vad.is_speech(audio_int16.tobytes(), sample_rate=48000)
   current_time = time.time()
   speech_segment = np.concatenate(audio_chunk).astype(np.float32)
   mean_amp = np.mean(np.abs(speech_segment))
   max_amp = np.max(np.abs(speech_segment))
   if mean_amp > mid and not speech_detected:#0.025 and max_amp> 0.9:
    mid=mean_amp
   # print(f"max амплитуда чанка: {max_amp:.3f}")
    print(f"Средняя амплитуда чанка: {mean_amp:.4f}")
   if is_speech_chunk and mean_amp > 0.020:  # Обнаружение речи
    # Проверяем максимальную амплитуду текущего чанка # Сохраняем только громкие чанки
     buffer.append(audio_chunk)
   if not speech_detected and buffer:   # Обнаружение начала речи
    if mean_amp > 0.25 and max_amp> 0.9:
     print(max_amp)
     print("Начало записи (обнаружена речь)")
     speech_detected = True
     last_speech_time = time.time()
   if speech_detected:
    # print(f"Средняя амплитуда чанка: {mean_amp:.4f}")
    if mean_amp > 0.0158:
     # print(max_amp)
     # print(f"Средняя амплитуда чанка: {mean_amp:.4f}")
     last_speech_time = time.time() # Речь продолжается — обнуляем паузу
     silence_time = 0
    else:# Тишина — накапливаем время
     silence_time +=  time.time() - last_speech_time
     print(silence_time)
     last_speech_time =  time.time()
   if (speech_detected and silence_time > min_silence_duration ) and buffer: # Проверяем, что буфер не пустой
    speech_segment = np.concatenate(buffer).astype(np.float32)  # Финальный сегмент
    segment_duration = len(speech_segment) / 48000
    print(f" длительность: {segment_duration:.2f} сек ")
    speech_detected = False
    silence_time = 0
    t1 = threading.Thread(target=transcribe_audio_segment, args=(speech_segment, model,))# Поток завершится при завершении основной программы
    t1.start()
    buffer.clear()  # Сбрасываем буфер
    # input()
# Запуск
stream, queue = record_audio_stream()
stream.start()

try:
    process_audio_stream(queue)
except KeyboardInterrupt:
    stream.stop()
    queue.put(None)
    print("Обработка остановлена.")