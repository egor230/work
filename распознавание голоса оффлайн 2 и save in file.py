from libs_voice import *
import sounddevice as sd
import numpy as np
from pynput import keyboard
from pynput.keyboard import Controller as Contr1, Key

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

subprocess.run( ["pactl", "set-source-mute", "54", "0"], check=True)# вкл микрофон.
start_listener()  # Запускаем слушатель# driver.set_window_position(1, 505)
cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(cache_dir)

# Проверка наличия модели
models = ["tiny", "base", "small", "medium", "large", "large-v3"]
model_name = models[5]
model_path = cache_dir / "whisper" / f"{model_name}.pt"
# Запись аудио с микрофона
duration = 20  # Длительность записи в секундах
sample_rate = 16000  # Частота дискретизации

if model_path.exists():
    print(f"✅ Модель '{model_name}' уже скачена: {model_path}")
    # Загрузка модели (Whisper сам проверит кэш)
    os.environ["OMP_NUM_THREADS"] = "8"    # Установка параметров для оптимизации CPU
    os.environ["MKL_NUM_THREADS"] = "8"
    model = whisper.load_model(model_name, device="cpu")
else:
    print(f"⚠️ Модель '{model_name}' не найдена. Будет скачана в: {model_path}")
    exit(0)
while 1:
 print("Запись началась...")
 audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
 sd.wait()  # Ожидание завершения записи
 print("Запись завершена.")
 with wave.open("temp.wav", 'wb') as wf: # Сохранение аудио в файл
   wf.setnchannels(1)
   wf.setsampwidth(2)
   wf.setframerate(sample_rate)
   wf.writeframes((audio * 32767).astype(np.int16).tobytes())

# Распознавание речи
 message = model.transcribe("temp.wav", fp16=False, language="ru", task="transcribe")["text"]
 if message:
  message = repeat(message)
  print(message)
  # process_text(message, k) # Напечатать этот текст

'''
Да, вы можете получать распознавание речи **напрямую с микрофона** без сохранения аудио в файл.
Для этого можно использовать библиотеку `sounddevice` для записи аудио с микрофона и передавать данные напрямую в модель Whisper. Вот как это сделать:
1. **Установка необходимых библиотек**
Убедитесь, что у вас установлены `whisper` и `sounddevice`:

```bash
pip install openai-whisper sounddevice numpy
```
 2. **Код для распознавания речи с микрофона**
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