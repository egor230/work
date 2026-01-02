import cv2, sys, os, warnings
from pynput.keyboard import Controller

warnings.filterwarnings('ignore')

# ---------- CONTROL KEYS ----------
LEFT_KEY = 'a'
RIGHT_KEY = 'd'
FORWARD_KEY = 'c'
BACK_KEY = 's'

# ---------- DEFAULT LINE POSITIONS ----------
DEFAULT_LEFT = 290
DEFAULT_RIGHT = 50
DEFAULT_TOP = 0
DEFAULT_BOTTOM = 190

# ---------- PATH ----------
cascade_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/haarcascade_frontalface_default.xml"

# ---------- BRIGHTNESS ----------
def enhance_brightness(frame):
    yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
    yuv[:, :, 0] = cv2.equalizeHist(yuv[:, :, 0])
    return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

# ---------- CHECK CASCADE ----------
if not os.path.exists(cascade_path):
    print("Ошибка: Haar cascade не найден")
    sys.exit(1)

face_cascade = cv2.CascadeClassifier(cascade_path)
if face_cascade.empty():
    print("Ошибка загрузки Haar cascade")
    sys.exit(1)

# ---------- CAMERA ----------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("Ошибка камеры")
        sys.exit(1)

WIDTH = 320
HEIGHT = 240
cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

# ---------- TRACKER ----------
tracker = cv2.TrackerKCF_create()
tracker_initialized = False
bbox = None

keyboard = Controller()

# ---------- OPENCV WINDOW ----------
cv2.namedWindow("Head Tracking")

def nothing(x):
    pass

# ---------- TRACKBARS ----------
cv2.createTrackbar("LEFT", "Head Tracking", DEFAULT_LEFT, WIDTH, nothing)
cv2.createTrackbar("RIGHT", "Head Tracking", DEFAULT_RIGHT, WIDTH, nothing)
cv2.createTrackbar("TOP", "Head Tracking", DEFAULT_TOP, HEIGHT, nothing)
cv2.createTrackbar("BOTTOM", "Head Tracking", DEFAULT_BOTTOM, HEIGHT, nothing)

# Минимальные и максимальные допустимые размеры для зелёного квадрата
MIN_SIZE = 20
MAX_SIZE = 200

# ---------- MAIN LOOP ----------
while True:
 if cv2.getWindowProperty("Head Tracking", cv2.WND_PROP_VISIBLE) < 1:
   break

 ret, frame = cap.read()
 if not ret:
   print("Ошибка чтения кадра")
   break

 frame = enhance_brightness(frame)

 # ---- READ TRACKBARS ----
 left_line = cv2.getTrackbarPos("LEFT", "Head Tracking")
 right_line = cv2.getTrackbarPos("RIGHT", "Head Tracking")
 top_line = cv2.getTrackbarPos("TOP", "Head Tracking")
 bottom_line = cv2.getTrackbarPos("BOTTOM", "Head Tracking")

 # ---- RED LINES ----
 cv2.line(frame, (left_line, 0), (left_line, HEIGHT), (0, 0, 255), 2)
 cv2.line(frame, (right_line, 0), (right_line, HEIGHT), (0, 0, 255), 2)
 cv2.line(frame, (0, top_line), (WIDTH, top_line), (0, 0, 255), 2)
 cv2.line(frame, (0, bottom_line), (WIDTH, bottom_line), (0, 0, 255), 2)

 # ---- FACE DETECTION AND TRACKING ----
 if not tracker_initialized:
   gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
   faces = face_cascade.detectMultiScale(
       gray,
       scaleFactor=1.3,
       minNeighbors=3,
       minSize=(MIN_SIZE, MIN_SIZE)
   )

   if len(faces) > 0:
       bbox = faces[0]
       x, y, w, h = bbox
       if w < MAX_SIZE and h < MAX_SIZE:  # Проверка на разумные размеры
           tracker.init(frame, bbox)
           tracker_initialized = True
 else:
   success, bbox = tracker.update(frame)
   if success:
       x, y, w, h = map(int, bbox)
       if w > MAX_SIZE or h > MAX_SIZE:  # Если размеры слишком большие
           tracker_initialized = False
           tracker = cv2.TrackerKCF_create()
           keyboard.release(LEFT_KEY)
           keyboard.release(RIGHT_KEY)
           keyboard.release(FORWARD_KEY)
           keyboard.release(BACK_KEY)
           continue

       # ---- DRAW GREEN RECTANGLE ----
       cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
       cv2.putText( frame, f"x:{x} y:{y}",
           (x, y - 10),   cv2.FONT_HERSHEY_SIMPLEX,
           0.5, (0, 255, 0), 1  )

       # ---- CHECK INTERSECTION WITH RED LINES ----
       left_intersect = x <= left_line and x + w >= left_line
       right_intersect = x <= right_line and x + w >= right_line
       top_intersect = y <= top_line and y + h >= top_line
       bottom_intersect = y <= bottom_line and y + h >= bottom_line

       if left_intersect:
           keyboard.press(LEFT_KEY)
       else:
           keyboard.release(LEFT_KEY)

       if right_intersect:
           keyboard.press(RIGHT_KEY)
       else:
           keyboard.release(RIGHT_KEY)

       if top_intersect:
           keyboard.press(FORWARD_KEY)
       else:
           keyboard.release(FORWARD_KEY)

       if bottom_intersect:
           keyboard.press(BACK_KEY)
       else:
           keyboard.release(BACK_KEY)
   else:
       tracker_initialized = False
       tracker = cv2.TrackerKCF_create()
       keyboard.release(LEFT_KEY)
       keyboard.release(RIGHT_KEY)
       keyboard.release(FORWARD_KEY)
       keyboard.release(BACK_KEY)

   cv2.imshow("Head Tracking", frame)

   if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ---------- CLEANUP ----------
keyboard.release(LEFT_KEY)
keyboard.release(RIGHT_KEY)
keyboard.release(FORWARD_KEY)
keyboard.release(BACK_KEY)

cap.release()
cv2.destroyAllWindows()
