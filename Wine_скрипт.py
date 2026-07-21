import os, subprocess, sys
def get_paths_file():  #  Получаем аргументы командной строки
  # num_args = len(sys.argv)# Получаем количество аргументов
  url = ""
  for arg in sys.argv[1:]:
    url += str(arg) + " "# Объединяем аргументы через цикл for

  url = url.strip()
  # url="/mnt/807EB5FA7EB5E954/games/GTA San Andreas ( REMASTER )/gta_sa.exe"
  directory = os.path.dirname(url)
  filename = os.path.basename(url)
  if '.' in filename:
    filename_without_extension = filename[:filename.rfind('.')]   # extension = filename[filename.rfind('.') + 1:]
  else:
    filename_without_extension = filename    # extension = None
  return url, directory, filename_without_extension, filename

full_path, directory, filename_without_extension, filename = get_paths_file()

file1=str(os.path.join(directory, filename)).replace('\'','')
# --- Создание bash-скрипта для запуска игры ---
launch_script = '''#!/bin/bash
export LAUNCH_PARAMETERS="-dx11 -skipintro 1"
export WINDOWS_VER="10"
export DLL_INSTALL="vcrun2019 corefonts lucida"
export WINEDLLOVERRIDES="d3dx9_36,d3dx9_42=n,b;mfc120=b,n,d3d8,d3d9,ddraw,dinput8,dsound=n,b"
export VULKAN_USE="6"
export LC_ALL="ru_RU.UTF-8"
export LANG="ru_RU.UTF-8"
export VKD3D_FEATURE_LEVEL="12_2"
export LOCALE_SELECT="ru_RU.utf"
export FPS_LIMIT="90"
export PW_USE_ESYNC="1"
export PW_USE_FSYNC="1"
export PW_USE_NTSYNC="1"
export USE_GAMEMODE="1"
export USE_D3D_EXTRAS="1"
export FIX_VIDEO_IN_GAME="1"
export USE_GSTREAMER="1"
export FORCE_LARGE_ADDRESS_AWARE="1"
export USE_SHADER_CACHE="1"
export USE_RUNTIME="1"
#export AMD_VULKAN_USE="radv"
export MESA_VK_WSI_PRESENT_MODE="mailbox"
export WINE_FULLSCREEN_FSR="1"
export WINE_FULLSCREEN_FSR_STRENGTH="5"
export SOUND_DRIVER_USE="pulse"
export MANGOHUD="0"

ORIGIN_W=1920
ORIGIN_H=1080
SCALE=80
NEW_W=$(( ORIGIN_W * SCALE / 100 ))
NEW_H=$(( ORIGIN_H * SCALE / 100 ))
GAMESCOPE_ARGS="-f -W ${{ORIGIN_W}} -H ${{ORIGIN_H}} -w ${{NEW_W}} -h ${{NEW_H}} -r 90 -S auto -F fsr --sharpness 20 --force-grab-cursor"

current_layout=$(xset -q | grep -A 0 'LED mask' | awk '{{print $10}}')
if [ "$current_layout" == "00000002" ]; then
    xdotool key super+space
fi

cd "{0}"
wine "{1}" -dx11 -skipintro 1
exit 0
'''.format(directory, filename)
script_path = str(os.path.join(directory, filename_without_extension)) + ".sh"
with open(script_path, 'w') as f:
    f.write(launch_script)

# --- Делаем скрипт исполняемым ---
chmod_cmd = 'chmod +x "{}"'.format(script_path)
subprocess.run(['bash', '-c', chmod_cmd])

# --- Извлекаем иконку (.ico) из exe-файла ---
ico_path = os.path.join(directory, filename_without_extension + ".ico")
extract_cmd = 'wrestool -x -t 14 "{0}" > "{1}"'.format(
    os.path.join(directory, filename),
    ico_path
)
subprocess.run(['bash', '-c', extract_cmd], check=True)

# --- Назначаем иконку эмблемой скрипта ---
ico_uri = 'file://' + os.path.abspath(ico_path)
subprocess.run(['gio', 'set', script_path, 'metadata::custom-icon', ico_uri])
show_list_id = '''#!/bin/bash
cd \"{0}\"
env "/home/egor/PortProton/data/scripts/start.sh" {1}
#portproton {1}
exit; '''.format(directory, filename)  # показать список устройств в терминале
file=str(os.path.join(directory, str("script_steam_")+filename_without_extension))+".sh"
with open(file, 'w') as file:    # Записываем текст в файл
    file.write(show_list_id)

# print(directory)
# print(filename_without_extension)
# print(filename)
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
