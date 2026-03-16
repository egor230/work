# Импорт необходимых библиотек
import sys
import os
import re
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton
from PyQt5.QtCore import Qt
from llama_cpp import Llama
import contextlib

# Путь к плагинам PyQt5
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "myenv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"

# Путь к модели
model_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/ollama/gemma-3-270m-it-F16.gguf"

# Функция для подавления вывода
@contextlib.contextmanager
def suppress_output():
  with open(os.devnull, 'w') as devnull:
    old_stderr = sys.stderr
    sys.stderr = devnull
    try:
      yield
    finally:
      sys.stderr = old_stderr

# Загрузка модели
try:
  with suppress_output():
    llm = Llama(
      model_path=model_path,
      n_ctx=4096,
      n_threads=8,
      n_batch=512,
      verbose=False
    )
except Exception as e:
  print(f"Ошибка при загрузке модели: {e}")
  def generate_response(prompt):
    return f"Ошибка: Не удалось загрузить LLM. Проверьте путь к модели: {model_path}"
  llm = None
else:
  def generate_response(prompt):
    system_prompt = "Отвечай кратко и по существу. Если вопрос — это вычисление, просто дай ответ без пояснений."
    full_prompt = f"{system_prompt}\n\nВопрос: {prompt}\nОтвет:"
    output = llm(
      full_prompt,
      max_tokens=128,
      temperature=0.3,
      top_p=0.9,
      echo=False
    )
    raw_text = output['choices'][0]['text'].strip()

    # Убираем возможные повторы системного промпта, вопроса и лишние части
    cleaned = re.sub(r'(Вопрос:|Ответ:).*', '', raw_text, flags=re.IGNORECASE | re.DOTALL).strip()
    if not cleaned:
      cleaned = raw_text
    return cleaned

# Главное окно чата
class ChatBotWindow(QMainWindow):
  def __init__(self):
    super().__init__()
    self.init_ui()

  def init_ui(self):
    self.setWindowTitle("Локальный Чат-бот Gemma")
    self.setGeometry(100, 100, 800, 600)

    central_widget = QWidget()
    self.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)

    # История чата
    self.chat_history = QTextEdit()
    self.chat_history.setReadOnly(True)
    self.chat_history.setAcceptRichText(True)
    self.chat_history.setStyleSheet("font-family: 'Noto Sans', sans-serif;")
    layout.addWidget(self.chat_history)

    # Поле ввода и кнопка
    input_layout = QHBoxLayout()
    self.input_field = QLineEdit()
    self.input_field.setPlaceholderText("Введите ваш вопрос...")
    input_layout.addWidget(self.input_field)

    self.send_button = QPushButton("Отправить")
    self.send_button.setFixedWidth(120)
    self.send_button.clicked.connect(self.send_message)
    input_layout.addWidget(self.send_button)

    layout.addLayout(input_layout)

    self.input_field.returnPressed.connect(self.send_message)

    # Тёмная тема
    self.setStyleSheet("""
      QMainWindow {
        background-color: #1a1a1a;
        color: #e0e0e0;
      }
      QTextEdit {
        background-color: #262626;
        color: #e0e0e0;
        border: 2px solid #3a3a3a;
        border-radius: 12px;
        padding: 15px;
        font-size: 15px;
        line-height: 1.5;
      }
      QLineEdit {
        background-color: #333333;
        color: #ffffff;
        border: 1px solid #4a4a4a;
        border-radius: 15px;
        padding: 10px 15px;
        font-size: 15px;
      }
      QLineEdit:focus {
        border: 1px solid #00aaff;
      }
      QPushButton {
        background-color: #00aaff;
        color: #ffffff;
        border: none;
        border-radius: 15px;
        padding: 10px;
        font-size: 15px;
        font-weight: bold;
      }
      QPushButton:hover {
        background-color: #0099e6;
      }
      QPushButton:pressed {
        background-color: #0077b3;
      }
    """)

  def send_message(self):
    user_input = self.input_field.text().strip()
    if not user_input:
      return

    # Сообщение пользователя (справа)
    user_message = f"""
    <div style='display: flex; justify-content: flex-end; width: 100%; margin: 8px 0;'>
      <div style='background-color: #00aaff; color: #ffffff; border-radius: 15px 15px 0 15px;
                  padding: 10px 14px; max-width: 70%; font-size: 14px; white-space: pre-wrap;'>
        <b>Вы:</b> {user_input}
      </div>
    </div>
    """
    self.chat_history.insertHtml(user_message)
    self.chat_history.insertHtml("<div style='clear: both;'></div>")
    self.chat_history.verticalScrollBar().setValue(self.chat_history.verticalScrollBar().maximum())

    self.input_field.clear()

    # Сообщение "Модель думает..."
    thinking_tag = "<div id='thinking' style='color: #888; font-style: italic; margin: 10px; text-align: center;'>Модель думает...</div>"
    self.chat_history.insertHtml(thinking_tag)
    self.chat_history.verticalScrollBar().setValue(self.chat_history.verticalScrollBar().maximum())
    QApplication.processEvents()

    # Генерация ответа
    if llm:
      response = generate_response(user_input)
    else:
      response = "Не удалось сгенерировать ответ (модель не загружена)."

    # Удаление "Модель думает..."
    html = self.chat_history.toHtml().replace(thinking_tag, "")
    self.chat_history.setHtml(html)

    # Сообщение бота (слева)
    bot_message = f"""
    <div style='display: flex; justify-content: flex-start; width: 100%; margin: 8px 0;'>
      <div style='background-color: #333333; color: #e0e0e0; border-radius: 15px 15px 15px 0;
                  padding: 10px 14px; max-width: 70%; font-size: 14px; white-space: pre-wrap;'>
        <b>Бот:</b> {response}
      </div>
    </div>
    """
    self.chat_history.insertHtml(bot_message)
    self.chat_history.insertHtml("<div style='clear: both;'></div>")
    self.chat_history.verticalScrollBar().setValue(self.chat_history.verticalScrollBar().maximum())

# Запуск приложения
if __name__ == '__main__':
  app = QApplication(sys.argv)
  window = ChatBotWindow()
  window.show()
  sys.exit(app.exec_())
