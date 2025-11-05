import collections, math, webrtcvad
from write_text import *
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

def process_audio_stream():# Функция обработки аудиопотока
 buffer = collections.deque()  # ИЗМЕНЕНО: используем список вместо Queue
 silence_time = 0
 last_speech_time = time.time()
 min_silence_duration = 1.7
 print("Начинаю обработку аудиопотока...")
 fs = 48000
 filename = "temp.wav"
 with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
  while True:
   # if audio_chunk is None:#   print("Завершение работы...")
    audio_chunk, overflowed = stream.read(8096)  # Читаем аудио порциями
    buffer.extend(audio_chunk.flatten())
    # max_amp = np.max(np.abs(audio_chunk))/1000
    mean_amp = np.mean(np.abs(audio_chunk)) * 100
    mean_amp = math.ceil(mean_amp * 10) / 10# print(mean_amp)
    if mean_amp > 6:
      last_speech_time = time.time()
      silence_time = 0
    else:
      silence_time += time.time() - last_speech_time
      last_speech_time = time.time()
    if silence_time > min_silence_duration and buffer:
      recording_array = np.array(buffer)
      write(filename, fs, recording_array)
      break

  if is_speech(): # Проверяем, что буфер не пустой
     segment_duration = len(recording_array) / 48000
     print(f" длительность: {segment_duration:.2f} сек ")
     segments, info = model.transcribe(filename, beam_size=10, language="ru",
                                       vad_filter=True, temperature=0.9, condition_on_previous_text=True)
     segments_list = list(segments)
     if not segments_list:
      return
     else:
      message = " ".join([seg.text.strip() for seg in segments_list])
      if message:
       threading.Thread(target=process_text, args=(message,), daemon=True).start()
     buffer.clear()  # Сбрасываем буфер
    # input()
# Запуск

try:
 while 1:
  if get_mute_status():
   process_audio_stream()
except KeyboardInterrupt:
   print("Обработка остановлена.")