import subprocess

def set_mouse_color(color: str):
    try:
        subprocess.run(["rivalcfg", "--strip-top-color", "black"], check=True)
        subprocess.run(["rivalcfg", "--strip-middle-color", "black"], check=True)
        subprocess.run(["rivalcfg", "--strip-bottom-color", "black"], check=True)
        # subprocess.run(args, check=True)
        subprocess.run(["rivalcfg", "--logo-color", color], check=True)
        print(f"Цвет подсветки установлен на {color}.")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке цвета: {e}")
    except FileNotFoundError:
        print("rivalcfg не установлен или не найден в PATH.")
# subprocess.run(['rivalcfg', '--print-debug'], check=True)
# Пример вызова
# colors = ["black", "red", "green", "blue", "yellow", "cyan", "magenta", "white"]
# set_mouse_color("black")
# args = ['rivalcfg', '--sensitivity', '900']
# subprocess.run(args, check=True)
##        args = ['rivalcfg', '--buttons', '{"4": "scrollup", "5": "scrolldown"}']
config = {
    'sensitivity': 800,          # 50-8500 (dpi)
    'polling_rate': 1000,         # 125, 250, 500, 1000
    'logo_color': 'red',          # Цвет логотипа
    'light_effect': 'breath',     # Эффект подсветки
    'led_brightness': 4,          # 0-4 (0 - выключено)
    'buttons': {
        'button6': 'dpi',        # Кнопка переключения DPI
        'button5': 'scrollup',   # Доп. кнопки
        'button4': 'scrolldown'
    }
}
args = [
    'rivalcfg',
    '-s', str(config['sensitivity']),
    '-p', str(config['polling_rate']),
    # '-c', config['logo_color'],
    # '-e', config['light_effect'],
    # '--led-brightness', str(config['led_brightness']),
    # '--buttons', ' '.join([f"{k}={v}" for k, v in config['buttons'].items()])
]
# subprocess.run(['rivalcfg', '--list'], check=True)
# subprocess.run(['rivalcfg', '--reset'], check=True)
subprocess.run(['rivalcfg', '--buttons', 'buttons(button6=disabled)'], check=True)
subprocess.run(['rivalcfg', '--set-button', 'button4', 'R'], check=True)

# subprocess.run(['rivalcfg', '--sensitivity', str(value)], check=True)

# subprocess.run(args, check=True)
# show_list_id = f'''#!/bin/bash
#  sudo rivalcfg --update-udev '''  # показать список устройств в терминале
# subprocess.run(['bash', '-c', show_list_id])
# args = ['rivalcfg', '--buttons', 'buttons(button6=disabled)']
#sudo pip ins
# args = ['rivalcfg', '--buttons', '{"5": "scrollup", "4": "scrolldown"}']
# subprocess.run(args, check=True)
#         args = ['rivalcfg', '--buttons', 'buttons(button1=button1; button2=button2; button3=button3; button4=disabled; button5=disabled; button6=disabled)']

#tall rivalcfg --break-system-packages