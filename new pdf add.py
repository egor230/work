import os
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import subprocess
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk  # Импортируем ttk для доступа к Progressbar

# Функция для выбора директории с помощью zenity
def select_directory(entry):
    try:
        cmd = ['zenity', '--file-selection', '--directory']
        result = subprocess.run(cmd, capture_output=True, text=True)
        directory = result.stdout.strip()  # Получаем путь из вывода zenity
        if directory:  # Если директория выбрана
            entry.delete(0, tk.END)
            entry.insert(0, directory)
    except FileNotFoundError:
        print("Ошибка: zenity не установлен на системе.")

# Функция для вывода директорий
def print_directories():
    from_dir = entry_from.get()
    to_dir = entry_to.get()

    # Проверка, что пути не пустые
    if not from_dir or not to_dir:
        messagebox.showerror("Ошибка", "Пожалуйста, укажите обе директории.")
        return

    # Убедитесь, что выходная директория существует
    if not os.path.exists(to_dir):
        os.makedirs(to_dir)

    # Функция для конвертации DOC в PDF
    def convert_doc_to_pdf(doc_file, output_dir):
        command = [
            'libreoffice', '--headless', '--convert-to', 'pdf',
            doc_file, '--outdir', output_dir
        ]
        try:
            subprocess.run(command, check=True)  # Проверка успешности выполнения
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Ошибка конвертации", f"Не удалось конвертировать {doc_file}. Ошибка: {e}")
            return False
        return True
    # Поиск всех файлов с расширением .doc в from_dir
    from_dir="\""+str(from_dir)+"\""
    doc_files = [os.path.join(root, file) for root, dirs, files in os.walk(from_dir) for file in files if file.endswith('.doc')]

    total_files = len(doc_files)
    if total_files == 0:
        status_label.config(text="Нет файлов для конвертации.")
        return

    # Настройка прогресс-бара
    progress['maximum'] = total_files
    progress['value'] = 0
    status_label.config(text=f"Осталось файлов: {total_files}")

    # Конвертация файлов и обновление прогресс-бара
    for i, doc_file in enumerate(doc_files):
        if not convert_doc_to_pdf(doc_file, to_dir):
            continue  # Если ошибка, пропускаем файл и продолжаем с остальными
        progress['value'] = i + 1
        remaining_files = total_files - (i + 1)
        status_label.config(text=f"Осталось файлов: {remaining_files}")
        root.update_idletasks()  # Обновление интерфейса для отображения изменений

    status_label.config(text="Конвертация завершена!")

# Создаем окно
root = tk.Tk()
root.title("Convert Word to PDF")

root.geometry("620x170+600+300")

# Поле "Откуда"
label_from = tk.Label(root, text="Откуда:")
label_from.grid(row=0, column=0, sticky="e")

entry_from = tk.Entry(root, width=50)
entry_from.grid(row=0, column=1)

button_from = tk.Button(root, text="Выбрать откуда", command=lambda: select_directory(entry_from))
button_from.grid(row=0, column=2)

# Поле "Куда"
label_to = tk.Label(root, text="Куда:")
label_to.grid(row=1, column=0, sticky="e")

entry_to = tk.Entry(root, width=50)
entry_to.grid(row=1, column=1)

button_to = tk.Button(root, text="Выбрать куда", command=lambda: select_directory(entry_to))
button_to.grid(row=1, column=2)

# Кнопка "ОК"
button_ok = tk.Button(root, text="ОК", command=print_directories)
button_ok.grid(row=2, column=1)

# Добавляем прогресс-бар
progress = ttk.Progressbar(root, orient="horizontal", length=500, mode="determinate")
progress.grid(row=3, column=0, columnspan=3, pady=10)

# Добавляем статусную метку
status_label = tk.Label(root, text="Прогресс", anchor="w")
status_label.grid(row=4, column=0, columnspan=3, sticky="w", padx=10)

# Запуск приложения
root.mainloop()
