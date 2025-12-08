import cv2, sys, os, time, warnings, subprocess
from pynput.keyboard import Key, Controller
warnings.filterwarnings('ignore')
# Путь к файлу Haar Cascade (ваш локальный файл)
cascade_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/haarcascade_frontalface_default.xml"

def enhance_brightness(frame):
 # Перевод в YUV, улучшение яркости канала Y
 yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
 yuv[:, :, 0] = cv2.equalizeHist(yuv[:, :, 0])
 return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

# Проверка существования файла Haar Cascade
if not os.path.exists(cascade_path):
    print(f"Ошибка: Файл каскада не найден по пути {cascade_path}")
    sys.exit(1)

# Загрузка классификатора Haar Cascade
face_cascade = cv2.CascadeClassifier(cascade_path)
if face_cascade.empty():
    print(f"Ошибка: Не удалось загрузить файл каскада {cascade_path}")
    sys.exit(1)

# Подключение к веб-камере с использованием V4L2
cap = cv2.VideoCapture('/dev/video0', cv2.CAP_V4L2)  # Попробуйте '/dev/video1', если не работает
if not cap.isOpened():
    print("Ошибка: Не удалось открыть веб-камеру. Попробуйте '/dev/video1' или другой индекс.")
    # Попытка открыть альтернативное устройство
    cap = cv2.VideoCapture('/dev/video1', cv2.CAP_V4L2)
    if not cap.isOpened():
        print("Ошибка: Не удалось открыть веб-камеру на '/dev/video1'. Проверьте устройство.")
        sys.exit(1)

# Установка разрешения камеры для ускорения обработки
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# Инициализация трекера KCF
tracker = cv2.TrackerKCF_create()
tracker_initialized = False
bbox = None  # Переменная для хранения координат лица
right = 50
left = 220
# Создаем объект для управления клавиатурой
keyboard = Controller()
# Основной цикл обработки кадров
while True: # Если трекер не инициализирован, ищем лицо с помощью Haar Cascade

 # Захват кадра с веб-камеры
 ret, frame = cap.read()

 frame = enhance_brightness(frame)
 if not tracker_initialized:
  # Преобразование кадра в серый цвет для ускорения обнаружения
  gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
  faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=3, minSize=(20, 20))

  # Если лицо найдено, инициализируем трекер
  if len(faces) > 0:
   x, y, w, h = faces[0]  # Берем первое обнаруженное лицо
   bbox = (x, y, w, h)
   tracker.init(frame, bbox)
   tracker_initialized = True
 else:  # Обновление трекера для отслеживания лица
  success, bbox = tracker.update(frame)
  x, y, w, h = [int(v) for v in bbox]  # Преобразуем координаты в целые числа
  cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Рисуем зеленый прямоугольник вокруг лица
  cv2.putText(frame, f'({x}, {y})', (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)  # Добавляем координаты над прямоугольником
  if not success: # Если трекер потерял лицо, сбрасываем инициализацию
   tracker_initialized = False
   tracker = cv2.TrackerKCF_create()  # Создаем новый трекер для повторной инициализации

 # Отрисовка прямоугольника и вывод координат
 back=101
 if bbox is not None:
  if y > back:
    keyboard.press('s')
  if y < back:
    keyboard.release('s')
  if x < right:
    keyboard.press('d')  # Нажимаем и удерживаем кнопку "d"
  if x > right:
    keyboard.release('d')  # Отпускаем кнопку "d"
  if x > left:
    keyboard.press('a')  # Нажимаем и удерживаем кнопку "d"
  if x < left:
   keyboard.release('a')  # Отпускаем кнопку "d"
 else:
    keyboard.release('d')  # Отпускаем кнопку "d"
    keyboard.release('a')  # Отпускаем кнопку "d"
 cv2.imshow("Head Tracking", frame) # Отображение кадра с наложенным прямоугольником

 # Выход из цикла по нажатию клавиши 'q'
 if cv2.waitKey(1) & 0xFF == ord('q'):
  break

# Освобождение ресурсов
cap.release()
cv2.destroyAllWindows()




# Функция для отправки клавиатурных команд
# def press(key):
#  try:
#   press_cmd = f'xte "keydown {key}"\nsleep 0.3\nxte "keyup {key}"'
#   subprocess.call(['bash', '-c', press_cmd])
#  except subprocess.CalledProcessError as e:
#   print(f"Ошибка xte: {e}")
