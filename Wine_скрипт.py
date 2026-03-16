import os, subprocess, sys
def get_paths_file():  #  Получаем аргументы командной строки
  # num_args = len(sys.argv)# Получаем количество аргументов
  url = ""
  for arg in sys.argv[1:]:
    url += str(arg) + " "# Объединяем аргументы через цикл for

  url = url.strip()
  # url="/mnt/807EB5FA7EB5E954/games/Far Cry/Bin32/FarCry.exe"
  directory = os.path.dirname(url)
  filename = os.path.basename(url)
  if '.' in filename:
    filename_without_extension = filename[:filename.rfind('.')]   # extension = filename[filename.rfind('.') + 1:]
  else:
    filename_without_extension = filename    # extension = None
  return url, directory, filename_without_extension, filename

full_path, directory, filename_without_extension, filename = get_paths_file()

file1=str(os.path.join(directory, filename)).replace('\'','')
show_list_id = '''#!/bin/bash
export LAUNCH_PARAMETERS="-dx11 -skipintro 1"
export WINDOWS_VER="10"
export DLL_INSTALL="vcrun2019 corefonts lucida"
export WINEDLLOVERRIDES="d3dx9_36,d3dx9_42=n,b;mfc120=b,n,d3d8,d3d9,ddraw,dinput8,dsound=n,b"
export VULKAN_USE="6"
export LC_ALL=ru_RU.UTF-8 # Локализация (опционально)
export LANG=ru_RU.UTF-8
export USE_SUPPLIED_DXVK_VKD3D="1"
export DLL_INSTALL="vcrun2019 corefonts lucida"
export VKD3D_FEATURE_LEVEL="12_2"
export LOCALE_SELECT="ru_RU.utf"
export FPS_LIMIT="90"
export USE_FSYNC="1"
export GUI_DISABLED_CS="0"
export USE_GAMEMODE="1"
export USE_D3D_EXTRAS="1"
export FIX_VIDEO_IN_GAME="1"
export USE_GSTREAMER="1"
export FORCE_LARGE_ADDRESS_AWARE="1"
export USE_SHADER_CACHE="1"
export USE_RUNTIME="1"
export AMD_VULKAN_USE="radv"
export MESA_VK_WSI_PRESENT_MODE="mailbox"
# Включаем MangoHud
# export MANGOHUD="1"
# export MANGOHUD_USER_CONF="0"
# export MANGOHUD_CONFIG="fps_metrics,horizontal,horizontal_stretch,hud_compact,font_size=24"
export WINE_FULLSCREEN_FSR="1"
export WINE_FULLSCREEN_FSR_STRENGTH="5"
export SOUND_DRIVER_USE="alsa"
# Параметры gamescope
GAMESCOPE_ARGS="-f -W 1920 -H 1080 -w 1920 -h 1080 -r 90 -S auto -F fsr --sharpness 20"
# GAMESCOPE_ARGS="-f --fullscreen -W 1920 -H 1080 -w 1280 -h 720 -r 90 -S auto -F fsr --sharpness 20"

# Пути
# Назначаем переменные
export WINEPREFIX="/home/egor/PortProton/data/prefixes/DEFAULT"

# Запуск через gamescope
#gamescope $GAMESCOPE_ARGS -- "$WINE_PATH" "$GAME_PATH"
cd \"{0}\"
DXVK_HUD=fps gamescope -f -w 1920 -h 1080 -r 90 -- \"/home/egor/PortProton/data/dist/PROTON-SAREK10-17-ASYNC/bin/wine\" {1}
exit; '''.format(file1, filename)  # показать список устройств в терминале
file=str(os.path.join(directory, filename_without_extension))+".sh"
with open(file, 'w') as file:    # Записываем текст в файл
    file.write(show_list_id)

show_list_id = '''#!/bin/bash\n
chmod +x "{0}"\n'''.format( file1)
subprocess.run(['bash', '-c', show_list_id])
# print(directory)
# print(filename_without_extension)
# print(filename)

command = f'cd "{directory}" || wrestool -x -t 14 "{filename}" > "{filename_without_extension}.ico"'
subprocess.run(['bash', '-c', command], check=True)
# show_list_id])



# url = url.strip()# os.chdir(url)# Убираем лишний пробел в конце строки
# directory = os.path.dirname(url) # Получение имени файла
# filename = os.path.basename(url)
#
# if '.' in filename:  # Удаление расширения
#  filename_without_extension = filename[:filename.rfind('.')]#  os.remove(os.path.join(url, filename))
# else:
#   filename_without_extension = filename

# file=os.path.join(directory, filename_without_extension).sh

# t = "{0}\n{1}\n{2}\n{3}".format(url, directory, filename, filename_without_extension)
#
#
# file_path = '/home/egor/Рабочий стол/1.txt'
# with open(file_path, 'w') as file:
#   # Записываем текст в файл
#  file.write(t)
#   print("У файла нет расширения")
# script = ("#!/bin/bash\n"
#           "cd \"{0}\";\n"
#           "./{1};\n"
#           "exit;".format(directory,filename))
#
#
# # print(parent_dir)
# # print(script)
# parent_dir=(str(directory+"/"+filename)+".sh")
# # parent_dir = parent_dir.replace(' ', '\ ')  # Замена пробелов на экранированные
# print(parent_dir)
# print(url)
# with open(parent_dir,'w') as f:
#    f.write(script)
