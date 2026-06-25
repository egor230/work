import deepspeech
import numpy as np
import pyaudio

# Параметры записи
RATE = 16000
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

# Инициализация модели DeepSpeech
model_file_path = 'deepspeech-0.9.3-models.pbmm'  # Укажи путь к модели
scorer_file_path = 'deepspeech-0.9.3-models.tflite'  # Укажи путь к скореру

# Загрузка модели
model = deepspeech.Model(model_file_path)
model.enableExternalScorer(scorer_file_path)

# Настройка записи с микрофона
audio = pyaudio.PyAudio()
stream = audio.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True,
                    frames_per_buffer=CHUNK)

# Запись и преобразование в текст
print("Начинаем говорить... (Ctrl+C для остановки)")

try:
  while True:
    data = stream.read(CHUNK)
    data16 = np.frombuffer(data, np.int16)

    # Преобразование в текст
    text = model.stt(data16)
    if text:
      print("Распознанный текст:", text)

except KeyboardInterrupt:
  print("Остановка записи.")

# Завершение работы
stream.stop_stream()
stream.close()
audio.terminate()