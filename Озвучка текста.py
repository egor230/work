import torch, os
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from pathlib import Path
# Настройка кэша
cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(cache_dir)

# Параметры
sample_rate = 24000  # Частота 24 кГц (поддерживается Silero TTS)
model_id = 'snakers4/silero-models/silero_tts/ru/v3_1_ru'
speaker = 'xenia'  # Выбираем спикера (можно: aidar, baya, kseniya, xenia)

# Проверка и загрузка модели
def load_silero_model():
 model_path = cache_dir / "hub" / "checkpoints" / model_id.replace('/', '_')
 if not model_path.exists():
   print(f"Модель {model_id} не найдена в кэше, загружаем...")
   model, utils = torch.hub.load('snakers4/silero-models', 'silero_tts', language='ru',
                                speaker='v3_1_ru', cache_dir=cache_dir)
 else:
   print(f"Модель {model_id} найдена в кэше.")
   model, utils = torch.hub.load('snakers4/silero-models', 'silero_tts', language='ru',
                                speaker='v3_1_ru', cache_dir=cache_dir, force_reload=False)
 model.to(torch.device('cpu'))  # Используем CPU
 return model, utils

# Загружаем модель
model, utils = load_silero_model()

# Функция для синтеза, воспроизведения и сохранения текста
def synthesize_and_play(text):
    audio = model.apply_tts(text=text, speaker=speaker, sample_rate=sample_rate)
    audio = audio.cpu().numpy()  # Конвертируем в numpy для воспроизведения
    # Воспроизводим аудио
    sd.play(audio, samplerate=sample_rate)
    sd.wait()  # Ждем окончания воспроизведения
    # Сохраняем аудио в WAV-файл
    write("output.wav", sample_rate, audio)
    print("Аудио сохранено в output.wav")

# Пример использования
text_to_speak = str("смотреть этот код и исправить ошибки")
print(f"Озвучиваю: {text_to_speak}")
synthesize_and_play(text_to_speak)