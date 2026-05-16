from exceptiongroup import catch
from pytq_libs_voice import *
from write_text import *

source_id = get_webcam_source_id()
set_mute("0", source_id)

class MyThread(QThread):
 text_signal = pyqtSignal(str, bool)
 icon_signal = pyqtSignal(str)
 init_ui_signal = pyqtSignal()
 
 def __init__(self, parent=None):
   super(MyThread, self).__init__(parent)
   self.parent = parent
   self.mic = True
   self._running = True
   self.label = getattr(parent, "label", None)
   self.url = None
   self.driver = None
   self.counts = 0
   self.message = ""
   self.button = None
   self.hint_text = None
   self.DATA_TESTID_ATTR = "data-testid"
   self.OKNYX_CORE_CLASS = "StandaloneOknyxCore"
   self.MIC_BUTTON_CLASS = "StandaloneOknyx"
   self.alisa = "aria-label"
   # Обновлённые селекторы для текущей страницы
   self.chat_list = ".ChatListGroup-List .ChatListItem"
   self.stream = "AliceChat-StreamingPlaceholder"
   self.ready = "AliceChat-Thinking"
 
 def is_text_stable(self, timeout=4):
   try:
       print("is_text_stable")
       while 1:
           time.sleep(timeout)
           user_m = self._find_user_messages()
           last_user_container = user_m[-1]
           message = self._extract_message_text(last_user_container)
           if initial_text and "Message:" in initial_text:
               break
           print(initial_text)
           time.sleep(timeout)
           final_text = self._get_last_user_message_text()
           print(final_text)
           if initial_text != final_text:
               continue
           else:
               break
       return True
   except:
       time.sleep(0.5)
       return False
 
 def update_mic_state(self, mic):
   self.mic = mic
 
 def stop(self):
   self._running = False
 
 def show_message(self, text, mic):
   self.hint_text = text
   if text:
       self.text_signal.emit(text, mic)
   else:
       self.text_signal.emit(None, mic)
 
 def del_all_chats(self):
   """
   Удаляет ВСЕ чаты через контекстное меню, устойчиво к случайным пунктам.
   """
   try:
       print("🔹 Запуск удаления всех чатов")
       self.driver.execute_script("""
           const sidebar = document.querySelector('.ChatSidebar');
           if (sidebar && sidebar.classList.contains('ChatSidebar_collapsed')) {
               const expandBtn = document.querySelector('.ChatSidebar-ExpandButton');
               if (expandBtn) {
                   expandBtn.style.cssText = 'visibility:visible !important; opacity:1 !important; pointer-events:auto !important;';
                   expandBtn.click();
               }
           }
       """)
       time.sleep(3)
       deleted = 0
       max_deleted = 50
 
       while deleted < max_deleted:
           # 1. Получаем список чатов заново на каждой итерации
           chat_items = self.driver.find_elements(By.CSS_SELECTOR, '.ChatListItem')
           if not chat_items:
               print("✅ Чатов больше нет. Удалено всего:", deleted)
               break
 
           target = chat_items[0]
 
           # 2. Кликаем по кнопке «Ещё»
           more_ok = self.driver.execute_script("""
               const chat = arguments[0];
               const moreBtn = chat.querySelector('.ChatListItem-Button_more');
               if (!moreBtn) return false;
               moreBtn.style.cssText = 'opacity:1 !important; visibility:visible !important; pointer-events:auto !important;';
               ['mouseenter','mousedown','mouseup','click'].forEach(ev =>
                   moreBtn.dispatchEvent(new MouseEvent(ev, {bubbles: true}))
               );
               return true;
           """, target)
 
           if not more_ok:
               print("⚠️ Кнопка «Ещё» не найдена, пробуем следующий")
               time.sleep(1)
               continue
 
           # 3. Ждем меню и кликаем «Удалить»
           try:
               WebDriverWait(self.driver, 13).until(
                   EC.presence_of_element_located((By.CSS_SELECTOR, '[role="menu"], .Popup2'))
               )
               time.sleep(3.5)
 
               self.driver.execute_script("""
                   const items = document.querySelectorAll('.Popup2 [role="menuitem"], .Popup2 button, .Popup2 [role="button"]');
                   for (let item of items) {
                       if (item.textContent.includes('Удалить')) {
                           item.click();
                           return true;
                       }
                   }
               """)
           except:
               print("⚠️ Не удалось взаимодействовать с меню")
               self.driver.execute_script("document.body.click();")
               time.sleep(1)
               continue
 
           # 4. Обработка окна подтверждения
           time.sleep(3.8)
           print("удалить")
           # Убираем ошибочный return 0, который прерывал выполнение
           self.driver.execute_script("""
               const modalButtons = document.querySelectorAll('.Modal button, .Dialog button, button[class*="confirm"]');
               for (let btn of modalButtons) {
                   const txt = btn.textContent.toLowerCase();
                   if (txt.includes('удалить') || txt === 'да' || txt.includes('confirm')) {
                       btn.click();
                   }
               }
           """)
 
           # 5. Ждем физического исчезновения элемента из DOM
           try:
               WebDriverWait(self.driver, 25).until(EC.staleness_of(target))
               print(f"🗑️ Чат удалён (всего {deleted + 1})")
               deleted += 1
           except:
               print("⚠️ Элемент застрял в DOM, ожидание обновления...")
               time.sleep(3.5)
 
           time.sleep(3.5)
 
       print(f"🏁 Завершено. Удалено чатов: {deleted}")
       return True
   except Exception as e:
       print(f"💥 Ошибка в del_all_chats: {e}")
       return False
 
 def _collapse_sidebar(self):
   """Сворачивает боковую панель обратно."""
   try:
       result = self.driver.execute_script("""
           var collapseBtn = document.querySelector('.ChatSidebar-CollapseButton');
           if (collapseBtn) {
               collapseBtn.click();
               return 'collapsed';
           }
           var btns = document.querySelectorAll(
               '[aria-label*="Свернуть"], [aria-label*="боковую панель"]'
           );
           for (var i = 0; i < btns.length; i++) {
               btns[i].click();
               return 'collapsed_via_aria';
           }
           return 'not_found';
       """)
       time.sleep(0.5)
   except Exception as e:
       print(f"Ошибка сворачивания сайдбара: {e}")
 
 def track_all_dom_changes(self, timeout_sec=3):
   if not hasattr(self, '_class_snapshot'):
       self._class_snapshot = {}
 
   from selenium.webdriver.common.by import By
   elements = self.driver.find_elements(By.XPATH, "//*[@class]")
 
   current_classes = {}
   for el in elements:
       try:
           tag = el.tag_name
           el_id = el.get_attribute('id') or f"no-id-{hash(el)}"
           key = f"{tag}#{el_id}"
           current_classes[key] = el.get_attribute('class') or ''
       except:
           pass
 
   changes = []
   for key, new_class in current_classes.items():
       old_class = self._class_snapshot.get(key)
       if old_class is not None and old_class != new_class:
           changes.append(f"{key}: '{old_class}' -> '{new_class}'")
 
   self._class_snapshot = current_classes
 
   if changes:
       print(f"\n[ИЗМЕНЕНИЯ КЛАССОВ] Найдено {len(changes)} изменений:")
       for change in changes:
           print(f"  • {change}")
   else:
       print("Нет изменений классов")
 
   return changes
 
 def start_selenium(self):
   try:
       option = get_option()
       option.add_argument("--disable-extensions")
       option.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
       self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=option)
       self.driver.get("https://alice.yandex.ru/")
 
       time.sleep(3)
 
       self._collapse_sidebar()
       # Раскомментировать, если нужно удалить все чаты
       # self.del_all_chats()
       # self._collapse_sidebar()
 
       def get_keyboard_device():
        from evdev import InputDevice, list_devices
        try:
         # Ищем устройство по списку
         for path in list_devices():
          dev = InputDevice(path)
          if "Keyboard" in str(dev) and "phys" in str(dev):
           return dev
        except Exception:
         pass
        return None
 
       # ====================== СЛОВАРЬ ДЛЯ КЛАВИШ ======================
       simple_key_map = {
        # Основные
        'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e', 'f': 'f', 'g': 'g',
        'h': 'h', 'i': 'i', 'j': 'j', 'k': 'k', 'l': 'l', 'm': 'm', 'n': 'n',
        'o': 'o', 'p': 'p', 'q': 'q', 'r': 'r', 's': 's', 't': 't', 'u': 'u',
        'v': 'v', 'w': 'w', 'x': 'x', 'y': 'y', 'z': 'z',
        '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5',
        '6': '6', '7': '7', '8': '8', '9': '9',
 
        # Специальные
        'Key.space': 'Space',
        'Key.enter': 'Enter',
        'Key.backspace': 'Backspace',
        'Key.tab': 'Tab',
        'Key.esc': 'Esc',
        'Key.shift': 'Shift',
        'Key.ctrl': 'Ctrl',
        'Key.alt': 'Alt',
        'Key.cmd': 'Win',
 
        # Стрелки
        'Key.up': '↑',
        'Key.down': '↓',
        'Key.left': '←',
        'Key.right': '→',
 
        # Numpad — именно в твоём формате
        'Key.kp_7': '7\nHome',
        'Key.kp_8': '8\n↑',
        'Key.kp_9': '9\nPgUp',
        'Key.kp_4': '4\n←',
        'Key.kp_5': '5',
        'Key.kp_6': '6\n→',
        'Key.kp_1': '1\nEnd',
        'Key.kp_2': '2\n↓',
        'Key.kp_3': '3\nPgDn',
        'Key.kp_0': '0\nIns',
       }
 
       def on_press(key):
        try:
         # Пытаемся получить имя нажатой клавиши
         if hasattr(key, 'char') and key.char is not None:
          key_name = key.char
         else:
          # Для специальных клавиш (ctrl, alt, стрелки и т.д.)
          key_name = str(key).replace('Key.', '')
 
         # Переводим в твои имена через словарь
         simple_name = simple_key_map.get(key_name, key_name)
 
         # Список твоих спец. клавиш
         special_list = [
          "7\nHome", "8\n↑", "9\nPgUp", "4\n←", "5\n",
          "6\n→", "1\nEnd", "2\n↓", "3\nPgDn", "0\nIns"
         ]
 
         if simple_name in special_list:
          print(f"Нажата спец. клавиша: {simple_name}")
         else:
          print(f"Нажата кнопка: {simple_name}")
 
        except Exception as e:
         print(f"Ошибка при обработке: {e}")
 
       def start_listener():
        # Импорт внутри, чтобы не грузить систему при запуске файла
        listener = Listener(on_press=on_press)
        listener.daemon = True
        listener.start()
        print("Слушатель клавиатуры запущен...")
 
       # Запуск
       start_listener()
       selenium_thread = threading.Thread(target=self.selenium_worker, daemon=True)
       selenium_thread.start()
 
       # Кнопка микрофона
       self.button = None
       aria_variants = [
           'button.StandaloneOknyx[aria-label="Алиса, начни слушать"]',
           'button.StandaloneOknyx[aria-label*="слушать"]',
           'button.StandaloneOknyx[aria-label*="Алиса"]',
           'button.StandaloneOknyx',
       ]
       for selector in aria_variants:
           try:
               self.button = self.driver.find_element(By.CSS_SELECTOR, selector)
               if self.button:
                   break
           except:
               continue
 
       if not self.button:
           try:
               oknyx_core_elem = self.driver.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
               self.button = oknyx_core_elem.find_element(By.XPATH, "./..")
           except:
               pass
       self.init_ui_signal.emit()
       self.show_message("Давай поговорите", self.mic)
       if self.button:
           self.button.click()
   except Exception as e:
       print(f"Ошибка в start_selenium: {e}")
 
 def get_user_message(self, len_c):
   """
   Получает последнее сообщение пользователя и количество сообщений
   """
   try:
       # Обновлённые селекторы для контейнеров сообщений пользователя
       user_selectors = [
           ".MessageBubble-Container_from-user",
           "[data-testid='message-bubble-container-from-user']",
           ".Message_from_user",
           ".AliceTextBubble_from_user",
           ".FuturisTextBubble_from_user",
       ]
 
       user_messages = []
       for selector in user_selectors:
           try:
               elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
               if elements:
                   user_messages = elements
                   break
           except:
               continue
 
       if not user_messages:
           return "", len_c
 
       # Селекторы для текста внутри контейнера
       text_selectors = [
           ".MessageBubble",
           ".AliceTextBubble",
           ".FuturisTextBubble",
           ".MessageBubble-Text",
           ".MarkdownText",          # добавлен для новых версий
       ]
 
       last_user_container = user_messages[-1]
       message = ""
       for selector in text_selectors:
           try:
               elem = last_user_container.find_element(By.CSS_SELECTOR, selector)
               if elem and elem.text.strip():
                   message = elem.text.strip()
                   break
           except:
               continue
 
       if not message:
           try:
               message = last_user_container.text.strip()
           except:
               message = ""
 
       if user_messages and message:
           return message, len(user_messages)
 
       return "", len_c
 
   except Exception as ex:
       print(f"Ошибка: {ex}")
       return "", len_c
 
 def selenium_worker(self):
   """Отслеживает состояние и нажимает кнопку когда Алиса думает"""
   while self._running:
       try:
           if not self.mic:
               self.show_message(None, False)
           else:
               mic_button = self.driver.find_element(By.CSS_SELECTOR, f".{self.MIC_BUTTON_CLASS}")
               oknyx_core = mic_button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
               aria_label = mic_button.get_attribute(f"{self.alisa}")
               classes = oknyx_core.get_attribute("class")
               message, counts1 = self.get_user_message(self.counts)
               if "lis" in classes and "стоп" in aria_label:
                   time.sleep(1)
                   self.show_message(message, self.mic)
               else:
                   self.show_message(None, False)
       except Exception as e:
           pass
 
 def run(self):
   self.start_selenium()
   while self._running:
       try:
           time.sleep(1.5)
           aria_label = self.button.get_attribute(self.alisa)
           oknyx_core = self.button.find_element(By.CSS_SELECTOR, f".{self.OKNYX_CORE_CLASS}")
           filter_elem = oknyx_core.get_attribute("data-testid") or ""
           classes = oknyx_core.get_attribute("class") or ""
 
           # 🔥 Алиса говорит / думает
           if "collapsedOut" in classes or "thinking" in classes:
               time.sleep(1)
               self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
               self.message, counts1 = self.get_user_message(self.counts)
 
               self.button.click()
               if counts1 > self.counts:
                   print(counts1)
                   self.counts = counts1
                   self.mic = False
                   thread = threading.Thread(target=process_text, args=(self.message,))
                   thread.start()
                   thread.join()
                   time.sleep(3)
 
                   self.mic = True
                   # Останавливаем запись (имитация)
                   self.button.click()
 
           # 🎤 режим ожидания / слушает
           if self.mic and "su" in filter_elem and "сл" in aria_label and "st" in classes:
               time.sleep(2)
               self.button.click()
       except Exception as ex1:
           pass
 
 
class MyWindow(QWidget):
 def __init__(self, parent=None):
   super(MyWindow, self).__init__(parent)
   self.mic = True
   self.mythread = MyThread(parent=self)
 
   BASE_PATH = os.path.dirname(os.path.abspath(__file__))
   self.icon1_path = os.path.join(BASE_PATH, "stop.png")
   self.icon2_path = os.path.join(BASE_PATH, "voice.png")
   self.tray_icon = QSystemTrayIcon(QIcon(self.icon2_path), self)
 
   menu = QMenu()
   quit_action = QAction("Quit", self)
   quit_action.triggered.connect(self.quit_t)
   menu.addAction(quit_action)
 
   self.mythread.text_signal.connect(self._update_label_from_thread)
   self.mythread.icon_signal.connect(self.change_icon)
 
   self.tray_icon.setContextMenu(menu)
   self.tray_icon.setToolTip("OFF")
   self.tray_icon.activated.connect(self.on_tray_icon_activated)
   self.tray_icon.show()
 
   self.setWindowFlags(
       Qt.WindowType.FramelessWindowHint |
       Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
   )
   self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
   self.setStyleSheet("background-color: rgba(255, 255, 255, 255); border-radius: 3px;")
 
   self.mythread.init_ui_signal.connect(self.QL)
   self.mythread.start()
   QTimer.singleShot(0, self.hide)
 
 def QL(self):
   layout = QVBoxLayout()
   self.label = QLabel(" ")
   self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
   self.label.setFont(QFont("Times", 14))
   self.label.setStyleSheet("color: black;")
   self.label.setWordWrap(False)
   layout.addWidget(self.label)
   self.setLayout(layout)
 
 def _update_label_from_thread(self, text, mic):
   try:
       if text and mic:
           self.label.setText(text)
           width = max(250, len(text) * 11)
           height = 45
           self.setFixedSize(width, height)
           self.move(630, 1070)
           self.show()
       else:
           self.hide()
   except Exception as e:
       print(f"UI update error: {e}")
 
 def change_icon(self, icon_path):
   try:
       self.tray_icon.setIcon(QIcon(icon_path))
       self.tray_icon.show()
   except Exception as e:
       print(f"change_icon error: {e}")
 
 def on_tray_icon_activated(self, reason):
   try:
       if reason == QSystemTrayIcon.ActivationReason.Trigger:
           self.mic = not getattr(self, "mic", True)
           self.tray_icon.setToolTip("ON" if self.mic else "OFF")
           set_mute("0" if self.mic else "1", source_id)
           self.tray_icon.show()
           self.mythread.icon_signal.emit(self.icon2_path if self.mic else self.icon1_path)
           self.mythread.update_mic_state(self.mic)
           if self.mic:
               self.show()
           else:
               self.hide()
   except Exception as e:
       print(f"Error in on_tray_icon_activated: {e}")
 
 def quit_t(self):
   try:
       self.mythread.stop()
       self.mythread.quit()
       self.mythread.wait(2000)
   except Exception:
       pass
   QApplication.quit()
 
 
 if __name__ == "__main__":
  app = QApplication(sys.argv)
  window = MyWindow()
  window.show()
  sys.exit(app.exec())