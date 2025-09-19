import wave, pyaudio, vosk
from libs_voice import *
from queue import Queue
from vosk import Model, KaldiRecognizer
import speech_recognition as sr
k.save_driver(0)
def get_steam(model_path):
 # Проверка наличия моделиmodel_path = "
 if not os.path.exists(model_path):
  print("Модель не найдена, скачайте модель и распакуйте ее в текущей директории")
  return
 # Отключаем предупреждения ALSA и JACK
 os.environ["PYAUDIO_ALSA_WARN"] = "0"
 os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
 os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера
 
 # Параметры
 sample_rate = 16000  # Частота 16 кГц
 block_size = 8000  # Чанк 0.5 сек (оптимально для Vosk)
 large_chunk_size = 32000  # Большой чанк для чтения
 # Перенаправляем вывод ошибок в /dev/null
 err = os.dup(2)  # Сохраняем оригинальный stderr
 os.dup2(os.open(os.devnull, os.O_WRONLY), 2)  # Перенаправляем stderr
 
 # Инициализация после перенаправления
 recognizer = sr.Recognizer()
 microphone = sr.Microphone()
 
 model = vosk.Model(model_path)
 recognizer = vosk.KaldiRecognizer(model, sample_rate)
 
 # Настраиваем чувствительность
 recognizer.energy_threshold = 50  # Снижаем порог для лучшего распознавания
 recognizer.dynamic_energy_threshold = True  # Включаем динамическую настройку
 audio = pyaudio.PyAudio() # Инициализация PyAudio
 
 # Установка параметров потока
 stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_rate,
                     input=True, frames_per_buffer=block_size)
 stream.start_stream()
 return stream, recognizer
def recognize_from_microphone(stream, recognizer):
  print("Начало распознавания речи... Говорите в микрофон.")
  while True:
   try:
    large_chunk = stream.read(16000, exception_on_overflow=False)
     # Разбиваем большие данные на чанки по 16000 байт
    for i in range(0, len(large_chunk), 8000):
     chunk = large_chunk[i:i + 8000]
     if recognizer.AcceptWaveform(chunk):
       result = recognizer.Result()
       text = json.loads(result)["text"]
       if text:
        print(text)   # if len(data) == 0:
        break

   except Exception as ex1:
    print(ex1)
    pass
# Установка пути к модели
model_path = "vosk-model-ru-0.42"
# model_path = "vosk-model-ru-0.10"
stream, recognizer = get_steam(model_path)
recognize_from_microphone(stream, recognizer)

# text = repeat(text, k)
# if k.get_flag() == True:
#    k.set_flag(False)
#    text0 = text[0].upper() + text[1:]
#    press_keys(text0)
# else:
#    press_keys(text)

#   continue
# else:
#   partial_result = recognizer.PartialResult()
# print(json.loads(partial_result)["partial"])
# except KeyboardInterrupt:
#   print("Распознавание остановлено пользователем.")
#
# stream.stop_stream()
# stream.close()
# audio.terminate()

'''
format=pyaudio.paInt16:
Формат аудио: Этот параметр указывает, что звуковые данные будут представлены в 16-битном целочисленном формате. 
Это стандартный и наиболее часто используемый формат для обработки аудио, так как он обеспечивает хорошее 
качество звука при умеренном размере данных.

channels=1:
Каналы: Указание на использование одного канала (моно). Для большинства приложений распознавания речи моно достаточно,
 и это уменьшает объем обрабатываемых данных по сравнению с стерео (2 канала).

rate=16000:
Частота дискретизации: Установка частоты дискретизации на 16000 Гц означает, что аудио данные будут захватываться 16 000 раз в секунду. 
Это стандартное значение для многих систем распознавания речи и обычно хорошо работает для человеческой речи.
input=True:
Входной поток: Указывает, что этот поток будет использоваться для захвата аудио данных с микрофона. 
Это обязательный параметр для записи звука.
frames_per_buffer=12000:
Размер буфера: Установка размера буфера на 12 000 отсчетов. Это значение определяет, сколько аудио данных 
будет возвращаться за один раз. Увеличение размера буфера может помочь избежать переполнения при высокой нагрузке, 
но это также может привести к увеличенной задержке между захватом звука и его обработкой. Важно найти оптимальный баланс:
 слишком большой буфер может вызвать заметную задержку, а слишком маленький — привести к потере данных,
  если не успевают обработать входящий поток.
  '''

'''
Чтобы ускорить распознавание речи в вашем коде, вы можете рассмотреть следующие изменения:

1. **Уменьшение размера буфера**:
   - Попробуйте уменьшить `frames_per_buffer`, например, с 8000 до 4000 или 2000. Это может помочь снизить задержку, 
   но имейте в виду, что слишком маленький размер буфера может привести к переполнению.

   ```python
   stream = audio.open(format=pyaudio.paInt16,
                       channels=1,
                       rate=16000,
                       input=True,
                       frames_per_buffer=4000)
   ```

2. **Частота дискретизации**:
   - Если ваша модель поддерживает более низкую частоту, попробуйте использовать 8000 Гц вместо 16000.
    Это уменьшит объем данных, что может ускорить обработку.

   ```python
   stream = audio.open(format=pyaudio.paInt16,
                       channels=1,
                       rate=8000,
                       input=True,
                       frames_per_buffer=4000)
   ```

3. **Оптимизация обработки данных**:
   - Убедитесь, что метод обработки аудиоданных работает эффективно. Если вы выполняете дополнительные вычисления или проверки,
    постарайтесь оптимизировать этот код.

4. **Параллельная обработка**:
   - Рассмотрите возможность использования многопоточности для обработки аудио данных и распознавания речи раздельно. Это может сократить время ожидания между захватом аудио и его обработкой.

5. **Использование меньшей модели**:
   - Если вы используете модель Vosk, убедитесь, что она не слишком велика для вашей задачи. Легкие модели могут работать быстрее, хотя это может сказаться на точности.

6. **Настройка Vosk**:
   - Если ваши требования к распознаванию не слишком строгие, вы можете настроить параметры Vosk для более быстрого распознавания.

Экспериментируйте с этими параметрами, чтобы найти оптимальный баланс между скоростью и точностью.
'''