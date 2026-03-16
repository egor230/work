from write_text import *
import  torch, gigaam, tempfile, torchaudio
import webrtcvad
from collections import deque
import scipy.io.wavfile as wavfile
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
 os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
 subprocess.run(["pactl", "set-source-mute", "54", "0"], check=True)  # вкл микрофон.
 # Настройка директории кэша
 cache_dir = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/gigaam")
 cache_dir.mkdir(parents=True, exist_ok=True)
 os.environ["XDG_CACHE_HOME"] = str(cache_dir)

 os.environ["OMP_NUM_THREADS"] = "8" # Настройка потоков для PyTorch
 os.environ["MKL_NUM_THREADS"] = "8"
 torch.set_num_threads(8)
 # Список доступных моделей
 models = ["v1_ssl", "v2_ssl", "ssl", "ctc", "v1_ctc", "v2_ctc", "rnnt", "v1_rnnt", "v2_rnnt", "emo"]
 model_name = models[-2]  # v2_rnnt

 model_path = cache_dir / f"{model_name}" # Путь для модели
 if not os.path.exists(f"{model_path}.ckpt"):
   print(f"Ошибка: Файл модели не найден по пути: {model_path}")
   sys.exit(1)  # Завершаем программу с кодом ошибки

 model = gigaam.load_model(model_name)

except Exception as e:
 print(e)
 pass
class MyThread(QThread):  # Определение класса потока
 mysignal = pyqtSignal(str)  # Объявление сигнала
 error_signal = pyqtSignal(str)  # Добавлено объявление сигнала ошибки
 icon_signal = pyqtSignal(str)  # Сигнал для изменения иконки

 def __init__(self, parent=None):  # Конструктор класса потока
  super(MyThread, self).__init__(parent)  # Вызов конструктора базового класса
  self._mic = True  # Приватная переменная для состояния микрофона
  self._running = False  # Флаг для управления циклом run
  self._queue = None

 @property
 def mic(self):
  return self._mic

 @mic.setter
 def mic(self, value):
  if self._mic != value:
   self._mic = value
   # Сигнал run() о необходимости начать/завершить работу
   if self._mic and not self._running:
    # Если нужно немедленно начать, но run() еще не успел это сделать,
    # мы полагаемся на цикл run().
    pass
   elif not self._mic and self._running:
    # Принудительная остановка process_audio_stream через Queue
    if self._queue:
     self._queue.put(None)

 def record_audio_stream(self, fs=48000, chunk_duration=0.03):
  """Создает и запускает поток sounddevice"""
  queue = Queue()

  def callback(indata, frames, time_info, status):
   if status:
    print(f"Статус потока: {status}")
   queue.put(indata.copy())

  # Создаем поток, но не запускаем его здесь
  stream = sd.InputStream(samplerate=fs, channels=1, callback=callback, blocksize=int(fs * chunk_duration))
  return stream, queue

 def process_audio_stream(self, queue):  # Функция обработки аудиопотока
  vad = webrtcvad.Vad(3)  # Инициализация параметров
  buffer = deque()
  silence_time = 0
  start_time = time.time()
  speech_detected = False
  last_speech_time = start_time
  min_silence_duration = 1.6
  # print("Начинаю обработку аудиопотока...")
  try:
   while self.mic:  # Работаем пока _mic == True
    audio_chunk = queue.get()
    if audio_chunk is None:
     print("Завершение работы process_audio_stream...")
     break
    audio_int16 = np.int16(audio_chunk * 32767)
    # Проверка, что аудио-чанк имеет правильную длину (обычно 0.01, 0.02 или 0.03 сек)
    # 48000 * 0.03 = 1440 сэмплов, 1440 * 2 байта = 2880 байт
    if len(audio_int16.tobytes()) not in [320, 640, 960, 1440 * 2]:  # Примеры для 8к, 16к, 32к, 48к
     print(f"ВНИМАНИЕ: Неправильная длина чанка для VAD: {len(audio_int16.tobytes())} байт")
     continue
    try:
     is_speech_chunk = vad.is_speech(audio_int16.tobytes(), sample_rate=48000)
    except Exception as vad_err:
     print(f"Ошибка VAD: {vad_err}")
     continue
    current_time = time.time()
    # print("1") # Закомментировал вывод, чтобы не спамить консоль
    if is_speech_chunk:  # Обнаружение речи
     mean_amp = np.mean(np.abs(audio_chunk))
     # print(f"Средняя амплитуда чанка: {mean_amp:.4f}")
     if mean_amp > 0.0151:  # Сохраняем только громкие чанки
      buffer.append(audio_chunk)

    # Логика VAD/записи
    if is_speech_chunk:
     if not speech_detected and buffer:  # Обнаружение начала речи
      # Только если у нас есть достаточно громкие чанки в буфере
      speech_segment_check = np.concatenate(buffer).astype(np.float32)
      if np.max(np.abs(speech_segment_check)) > 0.09:  # Проверка на реальную громкость
       # self.icon_signal.emit("голос.png") # Уже отправлено в run()
       print("Начало записи (обнаружена речь)")
       speech_detected = True
       last_speech_time = current_time

     if speech_detected:
      last_speech_time = current_time  # Речь продолжается — обнуляем паузу
      silence_time = 0

    elif speech_detected:  # Тишина, но была речь
     silence_time = current_time - last_speech_time

    # Конец сегмента
    if speech_detected and silence_time > min_silence_duration and buffer:  # Проверяем, что буфер не пустой
     self.icon_signal.emit("stop icon.jpeg")  # Индикация обработки
     speech_segment = np.concatenate(buffer).astype(np.float32)
     segment_duration = len(speech_segment) / 48000
     print(f"Длительность сегмента: {segment_duration:.2f} сек")
     speech_detected = False
     silence_time = 0
     filename = "temp.wav"
     # Делаем данные записываемыми, чтобы избежать предупреждения PyTorch
     speech_segment_int16 = np.int16(speech_segment * 32767).copy()
     wavfile.write(filename, 48000, speech_segment_int16)
     buffer.clear()
     result = model.transcribe(filename)  # Для других моделей получаем текст
     text = str(result).strip().lower()
     if text:  # Проверяем, что текст не пустой
      message = repeat(text)  # Автоподгонка ширины окна
      threading.Thread(target=process_text, args=(message,), daemon=True).start()

  except Exception as e:
   print(f"Ошибка в process_audio_stream: {e}")
   self.error_signal.emit(f"Ошибка обработки: {e}")
  finally:
   print("process_audio_stream завершен.")
   # После завершения process_audio_stream (если self.mic стал False) нужно сообщить об этом run()

 def run(self):  # Метод, исполняемый потоком
  while True:
   time.sleep(0.1)  # Короткая пауза для предотвращения 100% загрузки ЦПУ в цикле
   if self.mic and not self._running:
    try:
     self.icon_signal.emit("голос.png")
     self._running = True
     stream, queue = self.record_audio_stream()
     self._queue = queue  # Сохраняем очередь для принудительной остановки

     # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Используем контекстный менеджер для sounddevice
     # Он автоматически вызывает start() и stop()/close() при выходе
     with stream:
      self.process_audio_stream(queue)

    except Exception as ex2:
     print(f"Критическая ошибка в MyThread.run(): {ex2}")
     self.error_signal.emit(str(ex2))
    finally:
     # Логика выполнится, когда process_audio_stream завершится (по queue.get(None) или self.mic=False)
     self._running = False
     self._queue = None
     self.icon_signal.emit("stop icon.jpeg")  # Возвращаем иконку "неактивен"
     print("Аудиопоток и обработка завершены.")

   elif not self.mic and self._running:
    # Если self.mic стал False, process_audio_stream уже должен был завершиться,
    # и self._running должен быть False. Если нет, это значит, что stream не был закрыт.
    # В этом случае, мы полагаемся на логику в mic.setter, которая посылает None в очередь.
    pass


# ======================================================================================================================

class MyWindow(QtWidgets.QWidget):  # Определение класса главного окна
 def __init__(self, parent=None):  # Конструктор класса окна
  super(MyWindow, self).__init__(parent)  # Вызов конструктора базового класса

  # Сохраняем пути к иконкам как атрибуты класса для удобства
  self.icon1_path = "stop icon.jpeg"
  self.icon2_path = "голос.png"

  # Создание экземпляра потока
  self.mythread = MyThread()

  self.tray_icon = QSystemTrayIcon(QtGui.QIcon(self.icon2_path), self)  # Инициализируем иконку трея

  menu = QMenu()  # Создание контекстного меню для иконки в системном трее
  self.quit_action = QAction("Quit", self)
  self.quit_action.triggered.connect(self.quit_t)
  menu.addAction(self.quit_action)

  self.mythread.icon_signal.connect(self.change_icon)  # Подключаем сигнал изменения иконки
  self.tray_icon.setContextMenu(menu)  # Установка меню в трей
  self.tray_icon.setToolTip("ON")  # Установка начальной подсказки (по умолчанию True)
  self.tray_icon.activated.connect(self.on_tray_icon_activated)  # Привязываем обработчик к сигналу нажатия
  self.tray_icon.show()

  # Устанавливаем начальное состояние mic в потоке и запускаем его
  self.mythread.mic = True
  self.mythread.start()

 def change_icon(self, icon_path):  # Метод для изменения иконки в системном трее.
  self.tray_icon.setIcon(QtGui.QIcon(icon_path))
  self.tray_icon.show()

 def set_duration(self):  # Метод для установки длительности записи
  # Оставил оригинальную заглушку
  dialog = QDialog(self)
  dialog.setWindowTitle("Длина записи")
  layout = QVBoxLayout()
  dialog.setLayout(layout)
  dialog.exec_()

 def on_tray_icon_activated(self):  # Переключение состояния микрофона
  try:
   # Переключаем состояние в потоке через setter
   new_mic_state = not self.mythread.mic
   self.mythread.mic = new_mic_state

   # Обновляем GUI
   self.tray_icon.setToolTip("ON" if new_mic_state else "OFF")
   set_mute("0" if new_mic_state else "1")  # Обновление состояния системы

   # Если нужно немедленно обновить иконку при отключении
   if not new_mic_state:
    self.change_icon(self.icon1_path)  # "stop icon.jpeg"

   self.tray_icon.show()
  except Exception as e:
   print(f"Error in on_tray_icon_activated: {e}")

 def quit_t(self):  # Метод обработки события закрытия окна
  # Устанавливаем mic=False для корректного выхода из потока
  self.mythread.mic = False

  # Если поток еще работает, принудительно прерываем цикл run
  if self.mythread.isRunning():
   self.mythread.quit()  # Останавливаем поток
   self.mythread.wait(5000)  # Ждем завершения потока (до 5 секунд)

  QApplication.quit()


if __name__ == "__main__":
 app = QApplication(sys.argv)
 # Устанавливаем стиль приложения для лучшего отображения
 app.setQuitOnLastWindowClosed(False)  # Не закрывать при закрытии главного окна
 window = MyWindow()
 sys.exit(app.exec_())