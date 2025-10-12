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

# Загрузка модели
try:
    model = WhisperModel(model_path, device="cpu", compute_type="int8")
    print("Модель загружена успешно.")
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

# Функция обработки аудиопотока
def process_audio_stream(queue):
    language="ru"
    fs=16000
    min_speech_duration=0.8
    min_silence_duration=2.8
    vad = webrtcvad.Vad(2)  # Увеличиваем агрессивность VAD
    buffer = deque()
    speech_detected = False
    last_speech_time = 0
    frame_duration = 0.03
    frame_size = int(fs * frame_duration)
    process_interval = 3.5
    last_process_time = time.time()

    print("Начинаю обработку аудиопотока...")

    with sd.InputStream():
        while True:
            audio_chunk = queue.get()
            if audio_chunk is None:
                print("0")
                break

            audio_int16 = np.int16(audio_chunk * 32767)
            is_speech_chunk = vad.is_speech(audio_int16.tobytes(), sample_rate=fs)

            current_time = time.time()
            buffer.append(audio_chunk)

            if is_speech_chunk:
                if not speech_detected:
                    print("2")
                    speech_detected = True
                last_speech_time = current_time

            silence_time = current_time - last_speech_time
            time_since_last_process = current_time - last_process_time
            if (speech_detected and silence_time > min_silence_duration) or time_since_last_process > process_interval:
                speech_segment = np.concatenate(buffer).astype(np.float32)
                buffer.clear()
                segment_duration = len(speech_segment) / fs
                max_amp = np.max(np.abs(speech_segment))
                if max_amp>0.7:
                    print(f"Максимальная амплитуда сегмента: {max_amp:.4f}")
                    _, test_audio = wavfile.read("clear_speech.wav")
                    test_audio = np.array(test_audio, dtype=np.float32) / 32767.0  # Нормализация
                    segments, info = model.transcribe( test_audio,
                     beam_size=10,  # Увеличиваем для точности
                     language=language,     vad_filter=False,    temperature=0.8              )
                    segments_list = list(segments)  # Преобразуем в список для отладки
                    print(f"Количество сегментов от Whisper: {len(segments_list)}")
                    if not segments_list:
                     print("Whisper не вернул сегментов")
                    else:
                     message = " ".join([seg.text.strip() for seg in segments_list])
                     if message:
                      print(f"Распознанный текст: {message}")
                     else:
                      print("Whisper вернул пустой текст")
                    speech_detected = False
                    last_process_time = current_time

                while len(buffer) * frame_duration > 10:
                    buffer.popleft()

# Запуск
stream, queue = record_audio_stream()
stream.start()

try:
    process_audio_stream(queue)
except KeyboardInterrupt:
    stream.stop()
    queue.put(None)
    print("Обработка остановлена.")