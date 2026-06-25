from libs_voice import *

# Переопределение стандартных потоков вывода и ошибок, чтобы подавить сообщения ALSA и Jack
sys.stdout = open(os.devnull, 'w')  # Отключаем стандартный вывод
sys.stderr = open(os.devnull, 'w')  # Отключаем ошибки

def sound():  # Переопределение стандартного вывода ошибок
  sys.stderr = open(os.devnull, 'w')

  try:    # Настройки для работы со звуком
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 4096
    p = pyaudio.PyAudio()# Инициализация PyAudio
    # Открытие потока для записи
    stream = p.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True,    frames_per_buffer=CHUNK)

    data = stream.read(CHUNK)    # Чтение данных из потока
    audio_data = np.frombuffer(data, dtype=np.int16)

  except Exception as e:
    pass #    print(f"Error: {e}")  # Вывод информации об ошибке (если нужно)
  finally:
    # Восстановление стандартного вывода ошибок
    sys.stderr.close()
    sys.stderr = sys.__stderr__
  return p, stream, audio_data
# p, stream, audio_data= sound()
# s=[]
# for i in range(10):
#   time.sleep(0.2)
#   s.append(np.abs(audio_data).mean())
# print(s)
# Настройки
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024

# Инициализация PyAudio
p = pyaudio.PyAudio()

# Открытие потока для записи
stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                frames_per_buffer=CHUNK)

print("Проверка микрофона...")

try:
    while True:
        # Чтение данных из потока
        data = stream.read(CHUNK)
        # Преобразование данных в массив numpy
        audio_data = np.frombuffer(data, dtype=np.int16)
        # Проверка на наличие звука
        if np.abs(audio_data).mean() > 300:
            print(np.abs(audio_data).mean())
            # time.sleep(3)
            print("Микрофон активен!")
except KeyboardInterrupt:
    print("Завершение проверки.")
finally:
    # Закрытие потока и PyAudio
    stream.stop_stream()
    stream.close()
    p.terminate()