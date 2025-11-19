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

def update_label(root, label):
 def record_and_process():
  try:
   if not get_mute_status():
    root.withdraw()
   else:
    # Показ окна с начальной надписью
    root.geometry("100x20+700+1025")
    label.config(text="Говорите...")
    root.deiconify()
    root.update()
    buffer = collections.deque()  # ИЗМЕНЕНО: используем список вместо Queue
    silence_time = 0
    last_speech_time = time.time()
    min_silence_duration = 3.9
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
      mean_amp = math.ceil(mean_amp)  #      print(mean_amp)
      if mean_amp > 6:
       last_speech_time = time.time()
       silence_time = 0
      else:
       silence_time += time.time() - last_speech_time
       last_speech_time = time.time()
      if silence_time > min_silence_duration and buffer:
       root.withdraw()
       recording_array = np.array(buffer)
       write(filename, fs, recording_array)
       if is_speech(filename):  # Проверяем, что буфер не пустой
        buffer.clear()  # Сбрасываем буфер
        segments, info = model.transcribe( filename, beam_size=10,  language="ru",  # Русский — обязательно, для лучшей точности
         task="transcribe",  # Оставляем (не translate)
         log_progress=True,  # Включи для мониторинга (полезно для отладки)
         # Поиск и терпимость (ключ для дисартрии)
         best_of=10,  # ↑ с 5: Выбирает топ-10 гипотез, снижает ошибки на 15%
         patience=3.0,  # ↑ с 1: Больше "терпения" к нечётким звукам, не останавливается рано
         length_penalty=0.8,  # ↓ с 1: Штрафует длинные фразы меньше (дисартрия часто медленная)
         repetition_penalty=1.1,  # ↑ с 1: Мягко борется с повторами (типично для ДЦП), но не агрессивно
         no_repeat_ngram_size=2,  # ↑ с 0: Избегает повторений 2-грамм (e.g., "я я"), но позволяет естественные
         # Температура (стабильность)
         temperature=(0.0, 0.2, 0.4),  # ↓ с полного списка: Низкие значения для детерминизма, но с вариациями для лучших гипотез
         prompt_reset_on_temperature=0.5,  # Дефолт: Сбрасывает промпт на temp>0.5 — ок для стабильности

         # Пороги ошибок (терпимее к "грязной" речи)
         compression_ratio_threshold=3.0,  # ↑ с 2.4: Разрешает более "сжатые" (неидеальные) фразы
         log_prob_threshold=-0.8,  # ↑ с -1.0 (менее строгий): Принимает менее уверенные слова (тихие/искажённые)
         no_speech_threshold=0.4,  # ↓ с 0.6: Ловит тихую речь (дисартрия часто "шепотная")

         # Промпт и форматирование (против капитализации)
         condition_on_previous_text=False,  # Дефолт True → False: Избегает "залипания" на прошлых ошибках (полезно для длинных аудио)
         initial_prompt = ( "Распознай речь простым текстом маленькими буквами без заглавных букв в середине предложений. "
                           "Без знаков препинания, точек, запятых. Всё в нижнем регистре: например, 'добрый день как ваши дела что у вас нового'."),
         prefix=None,  # Оставляем None (не добавляем префикс)
         # Подавление
         suppress_blank=True,  # Дефолт: Ок, подавляет пустые токены
         suppress_tokens=[-1],  # Дефолт: Блокирует EOF, но можно добавить русские punct: [-1, 184, 46, 44] (точка, запятая — тест, если initial_prompt не хватит)

         # Таймстампы и VAD (для пауз)
         without_timestamps=True,  # ↑: Без таймстампов — упрощает вывод, фокус на тексте
         max_initial_timestamp=0.0,  # ↓ с 1.0: Не ждёт "тишину" в начале (дисартрия может начинаться тихо)
         word_timestamps=False,  # Дефолт: Без словесных таймстампов — экономит
         prepend_punctuations="",  # ↓ с дефолта: Пусто — не добавляет префиксные знаки (против пунктуации)
         append_punctuations="",  # ↓ с дефолта: Пусто — не добавляет суффиксные знаки
         multilingual=False,  # Дефолт: Только русский — быстрее и точнее
         vad_filter=True,  # Включи: Фильтрует шум/паузы, но с кастомными params ниже
         vad_parameters=dict(  # Новые: Адаптировано для дисартрии (паузы длинные, речь медленная)
          min_silence_duration_ms=1000,  # ↑: 1 сек паузы — не режет фразы с дыханием
          speech_pad_ms=500,    ),# ↑: 0.5 сек запаса — ловит "хвосты" нечёткой речи
          # Другие опции, если VadOptions: threshold=0.5 (средний порог для тихой речи)

         # Дополнительно (для длинных/неравномерных аудио)
         max_new_tokens=None,  # Дефолт: Без лимита — для полных фраз
         chunk_length=15,  # ↓ с None (или 20): Короткие чанки — лучше для медленной/прерывистой речи
         clip_timestamps="0",  # Дефолт: Без клиппинга
         hallucination_silence_threshold=0.3,  # Новый: ↓ Низкий — меньше "галлюцинаций" в тишине (если модель генерит лишнее)
         hotwords=None,  # Если есть твои частые слова (e.g. имена), добавь: "имя1|имя2"
         language_detection_threshold=0.7,  # ↑ с 0.5: Увереннее в русском
         language_detection_segments=3,  )# ↑ с 1: Анализирует больше сегментов для стабильности

        segments_list = list(segments)
        text = " ".join([seg.text.strip() for seg in segments_list])
        if text:  # Проверяем, что текст не пустой
         # Приводим первый символ к нижнему регистру
         message = text[0].lower() + text[1:] if len(text) > 0 else text
         # if is_model_loaded():
         #  message = fix_text(message)
         threading.Thread(target=press_keys, args=(message,), daemon=True).start()
       break
   root.after(1000, lambda: update_label(root, label))

  except Exception as e:
   print(f"Ошибка: {e}")
   root.after(1000, lambda: update_label(root, label))
   pass

 # Проверка статуса микрофона
 if get_mute_status():
  threading.Thread(target=record_and_process).start()
 else:
  root.withdraw()
  root.after(2000, lambda: update_label(root, label))


# ===== Интерфейс =====
root = tk.Tk()
frame = tk.Frame(root)
label = tk.Label(frame, text="...", font='Times 14', anchor="center")
label.pack(padx=3, fill=tk.X, expand=True)
frame.pack(fill=tk.X)
root.overrideredirect(True)
root.resizable(True, True)
root.attributes("-topmost", True)

update_label(root, label)
root.mainloop()




