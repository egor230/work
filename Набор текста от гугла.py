import os, sys, time
import speech_recognition as sr


# Контекстный менеджер для временного подавления stderr
class SuppressStderr:
 def __enter__(self):
  self.original_stderr = sys.stderr
  sys.stderr = open(os.devnull, 'w')
  return self
 
 def __exit__(self, exc_type, exc_val, exc_tb):
  sys.stderr.close()
  sys.stderr = self.original_stderr


# Отключаем предупреждения ALSA и JACK
os.environ["PYAUDIO_ALSA_WARN"] = "0"
os.environ["ALSA_LOG_LEVEL"] = "0"  # Подавляем логи ALSA
os.environ["JACK_NO_START_SERVER"] = "1"  # Отключаем запуск JACK-сервера

# Перенаправляем вывод ошибок в /dev/null
err = os.dup(2)  # Сохраняем оригинальный stderr
os.dup2(os.open(os.devnull, os.O_WRONLY), 2)  # Перенаправляем stderr

# Инициализация после перенаправления
recognizer = sr.Recognizer()
microphone = sr.Microphone()
# Настраиваем чувствительность
recognizer.energy_threshold = 50  # Снижаем порог для лучшего распознавания
recognizer.dynamic_energy_threshold = True  # Включаем динамическую настройку
# Инициализация с подавлением ошибок
with SuppressStderr():
 r = sr.Recognizer()
 # Получаем список микрофонов и выбираем первый рабочий
 try:
  mic = sr.Microphone()
 except:
  mic_index = None
  mics = sr.Microphone.list_working_microphones()
  if mics:
   mic_index = list(mics.keys())[0]
  mic = sr.Microphone(device_index=mic_index)

while True:
 try:
  with SuppressStderr():
   with mic as source:
    print("Слушаем...")
    # Увеличиваем параметры для надежности
    audio = r.listen(source, timeout=10, phrase_time_limit=25)
  
  # Распознавание вне контекста микрофона (меньше ошибок)
  text = r.recognize_google(audio, language="ru-RU")
  print(f"Распознанный текст: {text}")
  time.sleep(1)
 
 except sr.UnknownValueError:
  print("Не удалось распознать речь")
  time.sleep(1)
 except sr.RequestError as e:
  print(f"Ошибка сервиса: {e}")
  time.sleep(5)
 except sr.WaitTimeoutError:
  print("Таймаут: речь не обнаружена")
  time.sleep(1)
 except KeyboardInterrupt:
  print("Программа завершена пользователем")
  break
 except Exception as e:
  print(f"Ошибка: {type(e).__name__}: {e}")
  time.sleep(1)