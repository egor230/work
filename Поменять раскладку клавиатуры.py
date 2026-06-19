import os
import time
import subprocess

def get_current_layout():
    # Получаем текущую раскладку (аналог вашей команды)
    result = subprocess.run(["xset", "-q"], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if 'LED mask' in line:
            return line.split()[9]  # 10-й элемент (индекс 9) — это маска раскладки
    return None


# def switch_layout():
 # Определяем, какая раскладка активна
 # if "ru" in current:
 # subprocess.run(["setxkbmap", "us"])  # Переключаем на английскую
 # else:


def main():
 # switch_layout()  # Переключаем раскладку
 time.sleep(3)  # Ждём 3 секунды
 subprocess.run( "xte \"key ISO_Next_Group\"")  # Переключаем на русскую
 # subprocess.run(["setxkbmap", "ru,us"])  # Переключаем на русскую
 #switch_layout()  # Возвращаем обратно
main()