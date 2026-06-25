import tkinter as tk

def check_state():
    global last_state
    current_state = root.state()
    if current_state != last_state:
        if current_state == 'iconic':
            print("Окно было свернуто!")
        elif current_state == 'normal':
            print("Окно было восстановлено!")
        last_state = current_state
    root.after(200, check_state)  # Проверяем состояние каждые 200 мс

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Окно Tkinter")
    root.geometry("400x250")

    label = tk.Label(root, text="Сверните и восстановите окно.\nСмотрите вывод в терминале!")
    label.pack(pady=40)

    last_state = root.state()
    root.after(200, check_state)

    root.mainloop() 