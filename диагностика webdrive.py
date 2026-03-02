from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time


class DiagnosticBot:
 def __init__(self, chrome_options):
  self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

 def inject_monitor(self):
  monitor_script = """
    window.domLog = [];
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        let target = mutation.target;
        window.domLog.push({
          time: new Date().toLocaleTimeString(),
          tag: target.tagName,
          oldClass: mutation.oldValue,
          newClass: target.className,
          attribute: mutation.attributeName,
          content: target.innerText ? target.innerText.substring(0, 30) : ""
        });
      });
    });
    observer.observe(document.body, { 
      attributes: true, 
      subtree: true, 
      attributeOldValue: true,
      attributeFilter: ['class', 'disabled', 'state', 'value'] 
    });
    """
  self.driver.execute_script(monitor_script)

 def get_diagnostics(self):
  return self.driver.execute_script("return window.domLog;")

 def run_session(self):
  print("Запуск браузера...")
  self.driver.get("https://alice.yandex.ru/chat/01938823-14ea-4000-bd7a-3cca57830d6a/")

  time.sleep(5)

  print("Диагностика активна 40 секунд. Нажимай на кнопки в чате...")
  self.inject_monitor()

  for i in range(40, 0, -1):
   if i % 10 == 0:
    print(f"Осталось времени: {i} сек")
   time.sleep(1)

  print("Время вышло. Собираю отчет...")
  report = self.get_diagnostics()

  if not report:
   print("События не найдены.")
  else:
   print("ОТЧЕТ ОБ ИЗМЕНЕНИЯХ ЭЛЕМЕНТОВ:")
   for entry in report:
    print(f"Время: {entry['time']} | Тег: {entry['tag']}")
    print(f"Атрибут: {entry['attribute']}")
    print(f"Старый класс: {entry['oldClass']}")
    print(f"Новый класс: {entry['newClass']}")
    print("---")

  self.driver.quit()


# Создаем настройки
current_options = Options()
# Для Linux часто нужны эти аргументы:
current_options.add_argument("--no-sandbox")
current_options.add_argument("--disable-dev-shm-usage")

# Запуск
bot = DiagnosticBot(current_options)
bot.run_session()