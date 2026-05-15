from exceptiongroup import catch
from pytq_libs_voice import *
from write_text import *

source_id = get_webcam_source_id()
set_mute("0", source_id)

import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class ClickDetector:
 def __init__(self):
  # Настройка опций Chrome (как в вашем примере)
  option = Options()
  option.add_argument("--disable-extensions")
  option.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/google-chrome')
  # При необходимости можно добавить headless=False (по умолчанию окно видимо)

  self.driver = webdriver.Chrome(
   service=Service(ChromeDriverManager().install()),
   options=option
  )
  self.driver.get("https://alice.yandex.ru/")

  # ID скрытого элемента, в который JS будет сохранять данные о клике
  self.storage_id = "click_storage"
  # Создаём в DOM скрытый div для хранения информации
  self.driver.execute_script(f"""
            if (!document.getElementById('{self.storage_id}')) {{
                let storage = document.createElement('div');
                storage.id = '{self.storage_id}';
                storage.style.display = 'none';
                document.body.appendChild(storage);
            }}
        """)

  # Внедряем глобальный обработчик кликов
  self.driver.execute_script(f"""
            (function() {{
                let storage = document.getElementById('{self.storage_id}');
                document.addEventListener('click', function(event) {{
                    let elem = event.target;
                    // Собираем информацию об элементе
                    let info = {{
                        tag: elem.tagName,
                        id: elem.id || null,
                        classes: elem.className || null,
                        text: (elem.innerText || elem.value || '').substring(0, 100),  // ограничим длину
                        xpath: getXPath(elem),
                        outer_html: elem.outerHTML.substring(0, 500)
                    }};
                    storage.innerText = JSON.stringify(info);
                    console.log("Click detected:", info);
                }});

                // Вспомогательная функция для получения XPath элемента
                function getXPath(element) {{
                    if (element.id) return '//*[@id="' + element.id + '"]';
                    if (element === document.body) return '/html/body';
                    let index = 1;
                    let siblings = element.parentNode.childNodes;
                    for (let i = 0; i < siblings.length; i++) {{
                        let sibling = siblings[i];
                        if (sibling === element) {{
                            return getXPath(element.parentNode) + '/' + element.tagName + '[' + index + ']';
                        }}
                        if (sibling.nodeType === 1 && sibling.tagName === element.tagName) index++;
                    }}
                    return '';
                }}
            }})();
        """)
  print("Обработчик кликов установлен. Теперь нажмите на любую кнопку на странице...")

 def wait_for_click(self, timeout=60):
  """Ожидает клик пользователя в течение timeout секунд, возвращает информацию об элементе."""
  start = time.time()
  while time.time() - start < timeout:
   # Считываем содержимое скрытого div
   data = self.driver.execute_script(f"""
                let storage = document.getElementById('{self.storage_id}');
                return storage ? storage.innerText : '';
            """)
   if data and data.strip():
    try:
     info = json.loads(data)
     # Очищаем хранилище после получения, чтобы не ловить повторно тот же клик
     self.driver.execute_script(f"""
                        document.getElementById('{self.storage_id}').innerText = '';
                    """)
     return info
    except json.JSONDecodeError:
     pass
   time.sleep(0.3)  # небольшая пауза, чтобы не нагружать CPU
  return None

 def run(self):
  try:
   info = self.wait_for_click()
   if info:
    print("\n=== Вы нажали на элемент ===")
    print(f"Тег: {info['tag']}")
    print(f"ID: {info['id']}")
    print(f"Классы: {info['classes']}")
    print(f"Текст: {info['text']}")
    print(f"XPath: {info['xpath']}")
    print(f"Внешний HTML (обрезано): {info['outer_html']}")
    print("================================\n")
    # Здесь вы можете добавить код, который ищет нужный класс, например:
    if info['classes']:
     class_list = info['classes'].split()
     print(f"Список классов: {class_list}")
    else:
     print("У элемента нет классов.")
   else:
    print(f"Не удалось перехватить клик за {timeout} секунд.")
  finally:
   # Закрывать браузер не обязательно, оставьте открытым для дальнейшей работы
   # self.driver.quit()  # раскомментируйте, если нужно закрыть автоматически
   pass


if __name__ == "__main__":
 detector = ClickDetector()
 detector.run()