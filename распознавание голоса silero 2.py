from libs_voice import *
from pynput import keyboard
from pynput.keyboard import Controller as Contr1, Key
from silero import silero_stt
# Убедитесь, что у вас установлены torch и torchaudio
from pprint import pprint
from collections import deque
import sounddevice as sd
import numpy as np
import soundfile as sf
def record():
 # Запись аудио с микрофона
 duration = 20  # Длительность записи в секундах
 sample_rate = 16000  # Частота дискретизации
 print("Запись началась...")
 audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
 sd.wait()  # Ожидание завершения записи
 print("Запись завершена.")
 with wave.open("temp.wav", 'wb') as wf:
   wf.setnchannels(1)
   wf.setsampwidth(2)
   wf.setframerate(sample_rate)
   wf.writeframes((audio * 32767).astype(np.int16).tobytes())
 return 0
# record()
def on_press(key):  # обработчик клави.  # print(key )
 key = str(key).replace(" ", "")
 if key == "Key.shift_r":  #
  k.set_flag(True)
  return True
 if key == "Key.space" or key == "Key.right" or key == "Key.left" \
  or key == "Key.down" or key == "Key.up":
  k.set_flag(False)
  return True
 if key == "Key.alt":
  driver = k.get_driver()
  k.update_dict()
  return True
 else:
  return True

def on_release(key):
 pass
 return True

def start_listener():
 global listener
 listener = keyboard.Listener(on_press=on_press, on_release=on_release)
 listener.start()

subprocess.run( ["pactl", "set-source-mute", "54", "0"],
 check=True)# вкл микрофон.
# Настройка директории кэша
cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(cache_dir)
# Загрузка модели (tiny для скорости, small для качества)
models = ["tiny", "base", "small",
    "medium","large","large-v3"]
model = whisper.load_model(models[2])  # Убедитесь, что модель скачана через whisper.load_model()
# Параметры записи
sample_rate = 16000
block_size = 1024  # Оптимальный размер блока
buffer = queue.Queue()
audio_buffer = deque(maxlen=sample_rate * 9)  # Буфер на 5 секунд
min_speech_duration = 2.5  # Минимальная длительность речи для обработки (сек)

def audio_callback(indata, frames, time, status):# Callback функция для записи аудио"""
 if status:
  print("Ошибка записи:", status)
 audio_buffer.extend(indata[:, 0])

def is_speech_active(audio_data, threshold=0.025, min_duration=0.5):# Проверка наличия активности речи с адаптивной фильтрацией"""
 if len(audio_data) < sample_rate * min_duration:
  return False
 audio_array = np.array(audio_data) # Рассчитываем RMS с фильтрацией шума
 window_size = int(sample_rate * 0.1)  # 100 мс окно
 if window_size < 1:
  window_size = 1
 rms = np.sqrt(np.convolve(audio_array ** 2, np.ones(window_size) / window_size, mode='valid'))
 adaptive_threshold = max(threshold, np.mean(rms) * 1.5) # Адаптивный порог для учета шума
 speech_samples = np.sum(rms > adaptive_threshold)
 return speech_samples > sample_rate * min_duration * 0.5  # Требуем минимум 60% активной речи

def process_audio_chunk():#Обработка аудио чанка для распознавания"""
 if len(audio_buffer) >= sample_rate * min_speech_duration:
  audio_data = list(audio_buffer)[-sample_rate * 3:]  # Берем последние 3 секунды
  audio_array = np.array(audio_data, dtype=np.float32)
  if not is_speech_active(audio_array):  # Проверяем активность речи
   return None
  
  max_amplitude = np.max(np.abs(audio_array))  # Плавная нормализация
  if max_amplitude > 1e-6:  # Проверка на минимальную амплитуду
   audio_array = audio_array / (max_amplitude + 1e-6)
  else:
   return None
  return audio_array
 return None


def main():
 last_text = ""  # Инициализация last_text внутри функции
 print("Запуск системы распознавания речи. Говорите! Нажмите Ctrl+C для остановки.")
 
 # Создаем поток записи
 stream = sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32', callback=audio_callback, blocksize=block_size )
 
 try:
  stream.start()
  last_process_time = time.time()
  silence_counter = 0
  
  while True:
   current_time = time.time()
   
   # Обрабатываем аудио каждые 1.5 секунды
   if current_time - last_process_time >= 2.5:
    audio_chunk = process_audio_chunk()
    
    if audio_chunk is not None:
     try:     # Сохраняем во временный файл
      with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
       temp_path = f.name
      
      sf.write(temp_path, audio_chunk, sample_rate, subtype='PCM_16')      # Записываем аудио в файл
      
      # Распознавание речи
      result = model.transcribe( temp_path, language="ru", fp16=False,  verbose=False      )
      
      text = result["text"].strip()    # Выводим результат только если есть осмысленный текст
      if text and len(text) > 2 and text != last_text:  # Увеличиваем минимальную длину текста
       # Фильтруем бессмысленные результаты
       if not any(bad_word in text.lower() for bad_word in ['subtitles', 'субтитры', 'definition']):
        print(f"Распознанный текст: {text}")
        last_text = text
        silence_counter = 0
      
      # if os.path.exists(temp_path):
      #  os.unlink(temp_path)# Удаляем временный файл
     
     except Exception as e:
      print(f"Ошибка распознавания: {e}")
    
    else:
     silence_counter += 1
     # Сброс последнего текста при длительном молчании
     if silence_counter > 10:  # ~15 секунд молчания
      last_text = ""
    
    last_process_time = current_time
   
   time.sleep(0.05)  # Плавная работа цикла
 
 except KeyboardInterrupt:
  print("\nЗапись остановлена.")
 except Exception as e:
  print(f"Критическая ошибка: {e}")
 finally:
  stream.stop()
  stream.close()


if __name__ == "__main__":
 main()
    
    
# from transformers import WhisperForConditionalGeneration, WhisperProcessor, pipeline
#
# # Загружаем модель
# model = WhisperForConditionalGeneration.from_pretrained("antony66/whisper-large-v3-russian", torch_dtype=torch.float32)
# processor = WhisperProcessor.from_pretrained("antony66/whisper-large-v3-russian")
# asr_pipeline = pipeline("automatic-speech-recognition", model=model, tokenizer=processor.tokenizer, feature_extractor=processor.feature_extractor, device="cpu")
#
# # Распознаем аудио
# with open("temp.wav", "rb") as f:
#     wav = f.read()
# result = asr_pipeline(wav, generate_kwargs={"language": "russian"})
# print("Распознанный текст:", result["text"])
# # Имя модели и путь для кэша
# model_name = "silero_stt_v4_ru"
# model_path = cache_dir / "silero" / f"{model_name}.pt"
# # Проверка, установлен ли torch
#
# # Проверка наличия модели
# if model_path.exists():
#     print(f"✅ Модель '{model_name}' уже скачена: {model_path}")
# else:
#     print(f"⚠️ Модель '{model_name}' не найдена. Загружаем...")
#     try:
#         # Загрузка модели через PyTorch Hub
#         model, example_texts = torch.hub.load('snakers4/silero-models',
#                                              model='silero_stt',
#                                              language='ru',
#                                              version='v4',
#                                              cache_dir=str(cache_dir))
#         print(f"✅ Модель успешно загружена в: {model_path}")
#     except Exception as e:
#         print(f"❌ Ошибка при загрузке модели: {e}")
#         exit(1)
#
# # Установка параметров для оптимизации CPU
# os.environ["OMP_NUM_THREADS"] = "8"
# os.environ["MKL_NUM_THREADS"] = "8"
#
# # Загрузка модели
# model, example_texts = torch.hub.load('snakers4/silero-models',
#                                      model='silero_stt',
#                                      language='ru',
#                                      version='v4',
#                                      cache_dir=str(cache_dir))
#
# # Запись аудио с микрофона
# duration = 15  # Длительность записи в секундах
# sample_rate = 16000  # Частота дискретизации (Silero STT обычно работает с 16 кГц)
#
# while True:
#     print("Запись началась...")
#     audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
#     sd.wait()  # Ожидание завершения записи
#     print("Запись завершена.")
#
#     # Преобразование аудио в формат, подходящий для Silero
#     audio_np = np.squeeze(audio)  # Удаление лишних размерностей
#     audio_tensor = torch.from_numpy(audio_np).float()
#
#     # Распознавание речи
#     try:
#         output = model(audio_tensor, sample_rate)
#         message = output['transcription']
#         if message:
#          message = repeat(message)
#          process_text(message, k)
#     except Exception as e:
#        # print(e)
#        pass
'''

Да, вы можете получать распознавание речи **напрямую с микрофона** без сохранения аудио в файл. Для этого можно использовать библиотеку `sounddevice` для записи аудио с микрофона и передавать данные напрямую в модель Whisper. Вот как это сделать:

---

### 1. **Установка необходимых библиотек**
Убедитесь, что у вас установлены `whisper` и `sounddevice`:

```bash
pip install openai-whisper sounddevice numpy
```

---

### 2. **Код для распознавания речи с микрофона**
Вот пример кода, который записывает аудио с микрофона и передает его в модель Whisper для распознавания:

```python
import whisper
import sounddevice as sd
import numpy as np
import wave

# Загрузка модели Whisper
model = whisper.load_model("small")  # Можно выбрать другую модель: tiny, base, medium, large

# Параметры записи
sample_rate = 16000  # Частота дискретизации (16 кГц)
duration = 10  # Длительность записи в секундах

# Функция для записи аудио с микрофона
def record_audio(duration, sample_rate):
    print("Запись началась... Говорите!")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()  # Ожидание завершения записи
    print("Запись завершена.")
    return audio

# Запись аудио
audio = record_audio(duration, sample_rate)

# Преобразование аудио в формат, подходящий для Whisper
audio = (audio * 32767).astype(np.int16)  # Преобразование в 16-битный формат

# Распознавание речи
result = model.transcribe(audio, language="ru")
print("Распознанный текст:", result["text"])
```

---

### 3. **Как это работает?**
1. **Запись с микрофона**:
   - Библиотека `sounddevice` записывает аудио с микрофона в формате `float32`.
   - Аудио преобразуется в 16-битный формат, который поддерживает Whisper.

2. **Распознавание речи**:
   - Аудио передается в модель Whisper через метод `transcribe`.
   - Модель возвращает распознанный текст.

3. **Прямая обработка**:
   - Аудио не сохраняется на диск, а передается напрямую в модель.

---

### 4. **Режим реального времени (потоковое распознавание)**
Если вы хотите распознавать речь в реальном времени (например, как в голосовых помощниках), можно использовать следующий подход:

```python
import whisper
import sounddevice as sd
import numpy as np
import queue

# Загрузка модели Whisper
model = whisper.load_model("base")  # Используйте base или small для баланса скорости и точности

# Параметры записи
sample_rate = 16000  # Частота дискретизации (16 кГц)
block_size = 8000  # Размер блока аудио (0.5 секунды)
buffer = queue.Queue()

# Функция для обработки аудио в реальном времени
def audio_callback(indata, frames, time, status):
    if status:
        print("Ошибка записи:", status)
    buffer.put(indata.copy())

# Запуск записи с микрофона
stream = sd.InputStream(samplerate=sample_rate, channels=1, callback=audio_callback, blocksize=block_size)
stream.start()

print("Говорите! Нажмите Ctrl+C для остановки.")

try:
    while True:
        # Получение аудио из буфера
        if not buffer.empty():
            audio = buffer.get()
            audio = (audio * 32767).astype(np.int16).flatten()  # Преобразование в 16-битный формат

            # Распознавание речи
            result = model.transcribe(audio, language="ru")
            print("Распознанный текст:", result["text"])
except KeyboardInterrupt:
    print("Запись остановлена.")
finally:
    stream.stop()
    stream.close()
```

---

### 5. **Преимущества этого подхода**
- **Без сохранения файлов**: Аудио обрабатывается в оперативной памяти.
- **Режим реального времени**: Вы можете распознавать речь по мере её произнесения.
- **Гибкость**: Вы можете настроить параметры записи (длительность, частота дискретизации и т.д.).

---

### 6. **Рекомендации**
- Используйте модель `base` или `small` для баланса между скоростью и точностью.
- Если у вас слабое железо, выберите модель `tiny`.
- Для лучшей точности используйте микрофон с шумоподавлением.

---

Если у вас есть дополнительные вопросы или нужно доработать код, дайте знать! 😊
Конечно! Давайте подробнее разберем модели Whisper, их размеры, особенности и рекомендации по выбору в зависимости от задач. Это поможет вам подобрать оптимальный вариант для вашего проекта.

---
def donwloader():
# # Директория для сохранения моделей
#  model_dir = "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/whisper_models"
#  os.makedirs(model_dir, exist_ok=True)
#
#  # Список моделей и их URL-адреса
#  models = {
#     "tiny": "https://huggingface.co/openai/whisper-tiny/resolve/main/pytorch_model.bin",
#     "base": "https://huggingface.co/openai/whisper-base/resolve/main/pytorch_model.bin",
#     "small": "https://huggingface.co/openai/whisper-small/resolve/main/pytorch_model.bin",
#     "medium": "https://huggingface.co/openai/whisper-medium/resolve/main/pytorch_model.bin",
#     "large": "https://huggingface.co/openai/whisper-large/resolve/main/pytorch_model.bin",
#  }
# # Скачивание моделей
#  for model_name, url in models.items():
#     print(f"Скачивание модели: {model_name}")
#     response = requests.get(url)
#     with open(os.path.join(model_dir, f"{model_name}.pt"), "wb") as f:
#         f.write(response.content)
#     print(f"Модель {model_name} сохранена в {model_dir}")
# donwloader()
### **Модели Whisper: размеры, возможности и рекомендации**
#### 1. **Tiny (~75 МБ)**
- **Для чего подходит**:
  - Быстрое тестирование идей.
  - Простые задачи на слабых устройствах (например, мобильные приложения).
  - Распознавание коротких аудиозаписей с четкой речью.
- **Точность**: Низкая. Может путать сложные слова или акценты.
- **Пример использования**:
  ```python
  model = whisper.load_model("tiny")
  result = model.transcribe("голосовая_заметка.wav", language="ru")
  ```

#### 2. **Base (~150 МБ)**
- **Для чего подходит**:
  - Базовое распознавание речи на русском языке.
  - Приложения, где важна скорость, но не критична идеальная точность.
- **Точность**: Умеренная. Лучше справляется с шумным аудио, чем `tiny`.
- **Пример**:
  ```python
  model = whisper.load_model("base")
  result = model.transcribe("подкаст.wav", language="ru")
  ```

#### 3. **Small (~500 МБ)**
- **Для чего подходит**:
  - Универсальное решение для большинства задач.
  - Распознавание лекций, интервью, аудиокниг на русском.
  - Хороший баланс между скоростью и точностью.
- **Точность**: Высокая. Рекомендуется для проектов, где важна детализация.
- **Пример**:
  ```python
  model = whisper.load_model("small")
  result = model.transcribe("лекция_по_истории.wav", language="ru")
  ```

#### 4. **Medium (~1.5 ГБ)**
- **Для чего подходит**:
  - Профессиональные задачи: расшифровка научных докладов, аудио с шумом.
  - Точное распознавание сложных терминов и акцентов.
- **Точность**: Очень высокая. Требует больше ресурсов (рекомендуется GPU).
- **Пример**:
  ```python
  model = whisper.load_model("medium")
  result = model.transcribe("научный_доклад.wav", language="ru")
  ```

#### 5. **Large (~3 ГБ)**
- **Для чего подходит**:
  - Максимальная точность для критически важных проектов.
  - Расшифровка аудио с фоновым шумом, множеством говорящих, редкими языками.
- **Точность**: Экспертная. Используется в научных исследованиях и коммерческих продуктах.
- **Пример**:
  ```python
  model = whisper.load_model("large")
  result = model.transcribe("конференция_с_шумом.wav", language="ru")
  ```

---

### **Как выбрать модель?**
| Критерий               | Tiny | Base | Small | Medium | Large |
|------------------------|------|------|-------|--------|-------|
| Скорость               | ★★★★ | ★★★  | ★★    | ★      | ☆     |
| Точность               | ☆    | ★★   | ★★★   | ★★★★   | ★★★★★ |
| Требования к железу    | Низкие | Низкие | Средние | Высокие | Очень высокие |
| Подходит для           | Мобильные приложения | Быстрые демо | Универсальные задачи | Профессиональное использование | Научные исследования |

---

### **Советы по использованию**
1. **Для начинающих**: Начните с `small` — это золотая середина.
2. **Для мобильных приложений**: Используйте `tiny` или `base`, чтобы сэкономить память.
3. **Для точности**: Выбирайте `medium` или `large`, если у вас есть GPU.
4. **Оффлайн-использование**: Скачайте модель заранее и укажите локальный путь:
   ```python
   model = whisper.load_model("/home/user/models/whisper-small.pt")
   ```

---

### **Примеры задач**
- **Запись голосовых заметок** → `tiny` или `base`.
- **Расшифровка лекций/подкастов** → `small` или `medium`.
- **Научные исследования** → `large`.

Если вы сомневаетесь, какая модель подходит именно вам, напишите, и я помогу выбрать! 😊
'''