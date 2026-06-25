from libs_voice import *
driver=0

try:
   option= get_option()# Включить настройки.

   option.add_argument('--user-data-dir=/home/egor/.config/google-chrome')
   driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),   options=option)
   driver.get("https://vk.com/im/convo/52471674?entrypoint=list_all")# открыть сайт
   main_window = driver.current_window_handle  # Сохраняем handle главной вкладки
  # Создаём или открываем файл для записи
   with open("urls.txt", "a", encoding="utf-8") as file:
    previous_handles = set(driver.window_handles)  # Инициализируем предыдущие handles
    while True:
     try:
      current_handles = set(driver.window_handles)
      # Проверяем появление новых вкладок
      new_handles = current_handles - previous_handles
      if new_handles:
        for handle in new_handles:
          # Переключаемся на новую вкладку
          driver.switch_to.window(handle)
          # Записываем URL в файл
          url = driver.current_url
          file.write(url + "\n")
          file.flush()  # Принудительно записываем в файл
          # Закрываем новую вкладку
          driver.close()

        # Возвращаемся к главной вкладке
        driver.switch_to.window(main_window)
        previous_handles = current_handles  # Обновляем список handles
      time.sleep(3)  # Задержка для уменьшения нагрузки
     except Exception as e:
      print(f"Произошла ошибка: {str(e)}")
      # При возникновении ошибки пытаемся восстановить контекст
      driver.switch_to.window(main_window)
      previous_handles = set(driver.window_handles)

except:
  pass