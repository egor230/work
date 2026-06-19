import sys
import os
import contextlib
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
)

from llama_cpp import Llama

MODEL_PATH = "/mnt/807EB5FA7EB5E954/Program Files/ai models/lmstudio-community/gemma-4-E2B-it-GGUF/gemma-4-E2B-it-Q4_K_M.gguf"


@contextlib.contextmanager
def suppress_output():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


class ModelLoaderThread(QThread):
    finished = pyqtSignal(object, str)

    def run(self):
        if not os.path.exists(MODEL_PATH):
            self.finished.emit(None, f"Файл модели не найден:\n{MODEL_PATH}")
            return

        try:
            with suppress_output():
                llm = Llama(
                    model_path=MODEL_PATH,
                    n_ctx=4096,
                    n_threads=8,
                    n_batch=256,
                    verbose=False,
                )
            self.finished.emit(llm, "")
        except Exception as e:
            self.finished.emit(None, str(e))


def generate_response(llm, prompt: str) -> str:
    if llm is None:
        return "Ошибка: модель не загружена."

    # правильный формат для Gemma instruct
        # усиливаем инструкцию (это критично)
    full_prompt = (
     "<start_of_turn>system\n"
     "Ты полезный ассистент. Всегда давай полный и законченный ответ.\n"
     "но нужно отвечать на русском языке. \n"
     "<end_of_turn>\n"
     "<start_of_turn>user\n"
     f"{prompt}\n"
     "<end_of_turn>\n"
     "<start_of_turn>model\n"
    )

    try:
        output = llm(
            full_prompt,
            max_tokens=256,
            temperature=0.5,
            top_p=0.9,
            stop=["<end_of_turn>"],
            echo=False,
        )

        text = output["choices"][0]["text"].strip()

        return text if text else "Модель не дала ответа."

    except Exception as e:
        return f"Ошибка генерации: {e}"


class GenerationWorker(QThread):
    result_ready = pyqtSignal(str)

    def __init__(self, llm, prompt: str):
        super().__init__()
        self.llm = llm
        self.prompt = prompt

    def run(self):
        response = generate_response(self.llm, self.prompt)
        self.result_ready.emit(response)


class ChatBotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.llm = None
        self.worker = None
        self.loader_thread = None

        self.init_ui()
        self.init_model()

    def init_model(self):
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        self.status_label.setText("Загрузка модели...")

        self.loader_thread = ModelLoaderThread()
        self.loader_thread.finished.connect(self.on_model_loaded)
        self.loader_thread.start()

    def on_model_loaded(self, llm, error):
        if llm:
            self.llm = llm
            self.status_label.setText("Модель загружена")
        else:
            self.status_label.setText(f"Ошибка: {error}")

        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.setFocus()

    def init_ui(self):
        self.setWindowTitle("Локальный чат бот Gemma")
        self.setMinimumSize(900, 650)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.status_label = QLabel("Ожидание...")
        layout.addWidget(self.status_label)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("font-family: 'Noto Sans', sans-serif;")
        layout.addWidget(self.chat_history)

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
                padding: 16px;
                font-size: 16px;
            }
            QLineEdit {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 16px;
                padding: 10px 16px;
                font-size: 16px;
            }
            QLineEdit:focus {
                border: 1px solid #00aaff;
            }
            QPushButton {
                background-color: #00aaff;
                color: #ffffff;
                border: none;
                border-radius: 16px;
                padding: 10px;
                font-size: 16px;
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

        self.chat_history.append(f"<b>Вы:</b> {user_input}")
        self.input_field.clear()

        if self.llm:
            self.input_field.setEnabled(False)
            self.send_button.setEnabled(False)

            self.worker = GenerationWorker(self.llm, user_input)
            self.worker.result_ready.connect(self.on_response_ready)
            self.worker.start()

    def on_response_ready(self, response):
        self.chat_history.append(f"<b>Бот:</b> {response}")

        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.setFocus()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatBotWindow()
    window.show()
    sys.exit(app.exec())