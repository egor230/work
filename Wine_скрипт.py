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
export PW_WINDOWS_VER="10"
export PW_DLL_INSTALL="vcrun2019 corefonts lucida"
export WINEDLLOVERRIDES="d3dx9_36,d3dx9_42=n,b;mfc120=b,n,d3d8,d3d9,ddraw,dinput8,dsound=n,b"
export PW_VULKAN_USE="6"
export PW_USE_D3D_EXTRAS="1"
export PW_FIX_VIDEO_IN_GAME="1"
export LC_ALL=ru_RU.UTF-8 # Локализация (опционально)
export LANG=ru_RU.UTF-8
export PW_USE_SUPPLIED_DXVK_VKD3D="1"
export PW_DLL_INSTALL="vcrun2019 corefonts lucida"
export PW_VKD3D_FEATURE_LEVEL="12_2"
export PW_LOCALE_SELECT="ru_RU.utf"
export FPS_LIMIT="90"
export PW_USE_FSYNC="1"
export PW_GUI_DISABLED_CS="0"
export PW_USE_GAMEMODE="1"
export PW_USE_GSTREAMER="1"
export PW_FORCE_LARGE_ADDRESS_AWARE="1"
export PW_USE_SHADER_CACHE="1"
export PW_USE_RUNTIME="1"
export PW_WINE_CPU_TOPOLOGY="disabled"
export PW_MESA_GL_VERSION_OVERRIDE="disabled"
export PW_VKD3D_FEATURE_LEVEL="disabled"
export PW_LOCALE_SELECT="disabled"
export PW_MESA_VK_WSI_PRESENT_MODE="mailbox"
# Включаем MangoHud
export PW_MANGOHUD="1"
export PW_MANGOHUD_USER_CONF="0"
export MANGOHUD_CONFIG="fps_metrics,horizontal,horizontal_stretch,hud_compact,font_size=24"
export PW_WINE_FULLSCREEN_FSR="1"
export WINE_FULLSCREEN_FSR="1"
export WINE_FULLSCREEN_FSR_STRENGTH="3"
# Пути
WINEPREFIX_PATH="/home/egor/PortProton/data/prefixes/DEFAULT"
WINE_PATH="/home/egor/PortProton/data/dist/PROTON-SAREK10-17-ASYNC"
# Параметры gamescope
GAMESCOPE_ARGS="-f -W 1920 -H 1080 -w 1920 -h 1080 -r 90 -S auto -F fsr --sharpness 20"

GAME_PATH=\"{0}\"
# Параметры gamescope
GAMESCOPE_ARGS="-f --fullscreen -W 1920 -H 1080 -w 1280 -h 720 -r 90 -S auto -F fsr --sharpness 20"

# Назначаем переменные
export WINEPREFIX="$WINEPREFIX_PATH"

# Запуск через gamescope
gamescope $GAMESCOPE_ARGS -- "$WINE_PATH/bin/wine" "$GAME_PATH"

exit; '''.format(file1)  # показать список устройств в терминале
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
