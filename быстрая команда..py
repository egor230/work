import speech_recognition as sr
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

try:
  with microphone as source:
    recognizer.adjust_for_ambient_noise(source, duration=0.3)
    os.dup2(err, 2)
    print("Слушаю... Говорите что-нибудь.")
    while True:
     try:
      audio = recognizer.listen(source, timeout=1, phrase_time_limit=6)
      command = recognizer.recognize_google(audio, language="ru-RU").lower()
      print(f"Распознанная команда: {command}")
     except:
      pass

except:
  pass
