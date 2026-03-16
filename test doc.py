import subprocess

def copy_chapter_number(chapter_number):   # HTML-код с текстом "Глава <chapter_number>", красный, без переноса
  html_content = f"""
  <span style="font-family: 'Times New Roman', Times, serif; font-size: 24pt; font-weight: bold; color: red; display: inline;">
  Глава {chapter_number}
  </span>
  """  # Копируем HTML в буфер обмена с помощью xclip
  try:
   process = subprocess.Popen(   ['xclip', '-selection', 'clipboard', '-t', 'text/html'],
      stdin=subprocess.PIPE,     stderr=subprocess.PIPE,
      text=True  )
   stdout, stderr = process.communicate(input=html_content, timeout=10)
   if process.returncode == 0:
      print(f"Текст 'Глава {chapter_number}' успешно скопирован в буфер обмена.")
      # Используем copyq для записи HTML и активации в буфере
      subprocess.run(['copyq', 'write', '0', 'text/html', '-'], input=html_content, text=True)
      subprocess.run(['copyq', 'select', '0'])
   else:
      print(f"Ошибка при копировании в xclip: {stderr}")
  except subprocess.TimeoutExpired:
    print("Ошибка: превышено время ожидания для xclip")
  except FileNotFoundError:
   print("Ошибка: xclip или copyq не установлены. Убедитесь, что они доступны в системе.")


# Пример вызова функции
if __name__ == "__main__":
    copy_chapter_number(110)

