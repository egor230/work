import os, subprocess, sys, re, time, shutil, tempfile


def extract_appimage_icon(appimage_path, target_dir, base_name):
 """
 Извлекает иконку из AppImage через --appimage-extract и сохраняет её в
 target_dir под именем icon-<base_name>.<ext> (БЕЗ точки в начале имени).
 Возвращает путь к сохранённой иконке или None, если извлечь не удалось.
 """
 try:
  tmp = tempfile.mkdtemp(prefix="appimg_icon_")
 except Exception:
  return None
 try:
  subprocess.run([appimage_path, "--appimage-extract"], cwd=tmp,
   capture_output=True, timeout=120)
  root = os.path.join(tmp, "squashfs-root")
  dir_icon = os.path.join(root, ".DirIcon")
  # Runtime AppImage пишет файлы в squashfs-root АСИНХРОННО — опрашиваем
  # появление .DirIcon ~5 секунд, иначе можно попасть на пустую папку.
  for _ in range(50):
   if os.path.lexists(dir_icon):
    break
   time.sleep(0.1)
  if not os.path.lexists(dir_icon):
   return None
  # .DirIcon — обычно symlink вглубь образа; разрешаем всю цепочку.
  real = os.path.realpath(dir_icon)
  if not os.path.exists(real):
   return None
  ext = os.path.splitext(real)[1].lower()
  if ext not in {'.png', '.svg', '.jpg', '.jpeg', '.bmp', '.gif'}:
   ext = '.png'
  # Имя иконки НЕ должно начинаться с точки: icon-<name>.<ext>
  out_name = "icon-{0}{1}".format(base_name, ext)
  out_path = os.path.join(target_dir, out_name)
  shutil.copyfile(real, out_path)
  return out_path
 except Exception:
  return None
 finally:
  shutil.rmtree(tmp, ignore_errors=True)


# Разрешённые расширения иконок (всё остальное сохраняем как .png)
ICON_EXTENSIONS = {'.png', '.svg', '.jpg', '.jpeg', '.bmp', '.gif', '.ico', '.xpm'}


def save_icon(source_path, target_dir, base_name, force_ext=None):
 """
 Сохраняет файл-источник в target_dir под именем icon-<base_name>.<ext>.
 Если расширение не из разрешённых — сохраняет как .png.
 """
 ext = (force_ext or os.path.splitext(source_path)[1]).lower()
 if ext not in ICON_EXTENSIONS:
  ext = '.png'
 out_path = os.path.join(target_dir, "icon-{0}{1}".format(base_name, ext))
 shutil.copyfile(source_path, out_path)
 return out_path


def find_icon_in_tree(root_dir, base_name, limit=4000):
 """
 Ищет png/svg/xpm/ico внутри распакованного дерева (не дальше limit файлов —
 чтобы не виснуть на огромных архивах). Приоритет: точное совпадение имени,
 затем svg > png > остальные, потом кратчайший путь.
 """
 best = None
 best_score = float('inf')
 seen = 0
 bl = base_name.lower()
 for dirpath, dirs, files in os.walk(root_dir):
  for f in files:
   seen += 1
   if seen > limit:
    return best
   ext = os.path.splitext(f)[1].lower()
   if ext not in {'.svg', '.png', '.ico', '.xpm'}:
    continue
   name = os.path.splitext(f)[0].lower()
   rel = os.path.relpath(os.path.join(dirpath, f), root_dir)
   if name == bl:
    score = 0
   elif bl and (bl in name or name in bl):
    score = 10
   else:
    score = 50
   score += len(rel) * 0.01 + {'.svg': 0.0, '.png': 0.5, '.ico': 1.0, '.xpm': 1.0}[ext]
   if score < best_score:
    best = os.path.join(dirpath, f)
    best_score = score
 return best


_ICO_HELPER = """
import sys, os
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
img = Image.open(src)
best = None
for i in range(int(getattr(img, 'n_frames', 1) or 1)):
    try:
        img.seek(i)
        img.load()
    except Exception:
        break
    if best is None or img.size[0] * img.size[1] > best.size[0] * best.size[1]:
        best = img.copy()
if best is None:
    sys.exit(1)
if best.mode not in ('RGB', 'RGBA'):
    best = best.convert('RGBA')
best.save(dst, 'PNG')
sys.exit(0 if os.path.exists(dst) else 1)
"""


def _convert_ico_with_pil(ico_path, out_path):
 from PIL import Image
 img = Image.open(ico_path)
 best = None
 try:
  frames = int(getattr(img, 'n_frames', 1) or 1)
 except Exception:
  frames = 1
 for i in range(frames):
  try:
   img.seek(i)
   img.load()
  except Exception:
   break
  if best is None or (img.size[0] * img.size[1]) > (best.size[0] * best.size[1]):
   best = img.copy()
 if best is None:
  return False
 if best.mode not in ('RGB', 'RGBA'):
  best = best.convert('RGBA')
 best.save(out_path, 'PNG')
 return os.path.exists(out_path)


def ico_to_png(ico_path, target_dir, base_name):
 """
 Конвертирует .ico/.bmp в png и сохраняет в target_dir как icon-<base_name>.png.
 Берёт кадр максимального разрешения. Если PIL в текущем интерпретаторе
 недоступна/сломана (такое бывает, когда venv лежит на NTFS — там _imaging.so
 обрезается до 0 байт) — конвертация выполняется системным python3.
 """
 out_path = os.path.join(target_dir, "icon-{0}.png".format(base_name))
 try:
  if _convert_ico_with_pil(ico_path, out_path):
   return out_path
 except Exception:
  pass
 helper = None
 try:
  helper = tempfile.NamedTemporaryFile('w', suffix='.py', delete=False)
  helper.write(_ICO_HELPER)
  helper.close()
  for py in ('python3', '/usr/bin/python3'):
   r = subprocess.run([py, helper.name, ico_path, out_path],
    capture_output=True, timeout=120)
   if r.returncode == 0 and os.path.exists(out_path):
    return out_path
 except Exception:
  return None
 finally:
  if helper is not None:
   try:
    os.unlink(helper.name)
   except Exception:
    pass
 return None


# Логика извлечения иконок из PE-файлов: порт icoextract (jlu5), чистый pefile,
# без внешних утилит. В отличие от сырого вывода wrestool, здесь собирается
# валидный .ico-контейнер (ICONDIR + ICONDIRENTRY), который PIL читает нативно.
_PE_EXTRACT_HELPER = """
import struct, sys
import pefile

GRPICONDIRENTRY_FORMAT = ('GRPICONDIRENTRY',
    ('B,Width', 'B,Height', 'B,ColorCount', 'B,Reserved',
     'H,Planes', 'H,BitCount', 'I,BytesInRes', 'H,ID'))
GRPICONDIR_FORMAT = ('GRPICONDIR', ('H,Reserved', 'H,Type', 'H,Count'))

def write_ico(pe_path, ico_out):
    pe = pefile.PE(name=pe_path, fast_load=True)
    pe.parse_data_directories(pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE'])
    if not hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
        raise RuntimeError('no resource directory')
    # Разворачиваем список, чтобы первая иконка выигрывала при повторах ID
    resources = {rsrc.id: rsrc for rsrc in reversed(pe.DIRECTORY_ENTRY_RESOURCE.entries)}
    grp = resources.get(pefile.RESOURCE_TYPE['RT_GROUP_ICON'])
    rt = resources.get(pefile.RESOURCE_TYPE['RT_ICON'])
    if not grp or not rt:
        raise RuntimeError('no icon resources')
    groupicon = grp.directory.entries[0]
    if groupicon.struct.DataIsDirectory:
        groupicon = groupicon.directory.entries[0]
    rva = groupicon.data.struct.OffsetToData
    size = groupicon.data.struct.Size
    data = pe.get_data(rva, size)
    file_offset = pe.get_offset_from_rva(rva)

    grp_dir = pe.__unpack_data__(GRPICONDIR_FORMAT, data, file_offset)
    entries, icon_offset = [], grp_dir.sizeof()
    for _ in range(grp_dir.Count):
        e = pe.__unpack_data__(GRPICONDIRENTRY_FORMAT, data[icon_offset:],
                              file_offset + icon_offset)
        icon_offset += e.sizeof()
        entries.append(e)

    id_map = {l.id: l for l in rt.directory.entries}
    images = []
    for g in entries:
        ie = id_map[g.ID].directory.entries[0]
        images.append(pe.get_data(ie.data.struct.OffsetToData, ie.data.struct.Size))

    with open(ico_out, 'wb') as fd:
        fd.write(b'\\x00\\x00')
        fd.write(struct.pack('<HH', 1, len(entries)))
        data_offset = 6 + len(entries) * 16
        for g, idata in zip(entries, images):
            fd.write(g.__pack__()[:12])
            fd.write(struct.pack('<I', data_offset))
            data_offset += len(idata)
        for idata in images:
            fd.write(idata)

if __name__ == '__main__':
    write_ico(sys.argv[1], sys.argv[2])
"""


def _run_pe_helper(pe_path, ico_out, py=None):
 """
 Запускает извлечение одним интерпретатором: текущим (py=None) или внешним.
 """
 try:
  if py is None:
   ns = {'__name__': '__pe_helper__'}
   exec(compile(_PE_EXTRACT_HELPER, 'pe_helper', 'exec'), ns)
   ns['write_ico'](pe_path, ico_out)
   return os.path.getsize(ico_out) > 0
  helper = None
  try:
   helper = tempfile.NamedTemporaryFile('w', suffix='.py', delete=False)
   helper.write(_PE_EXTRACT_HELPER)
   helper.close()
   r = subprocess.run([py, helper.name, pe_path, ico_out],
    capture_output=True, timeout=120)
   return r.returncode == 0 and os.path.getsize(ico_out) > 0
  finally:
   if helper is not None:
    try:
     os.unlink(helper.name)
    except Exception:
     pass
 except Exception:
  return False


def _extract_pe_native(pe_path, ico_out):
 """
 Извлечение через pefile: сначала текущий интерпретатор (pefile есть и в venv,
 и в системном python3), при неудаче — системный python3.
 """
 if _run_pe_helper(pe_path, ico_out, py=None):
  return True
 for py in ('python3', '/usr/bin/python3'):
  if _run_pe_helper(pe_path, ico_out, py=py):
   return True
 return False


def _extract_pe_icoextract(pe_path, ico_out):
 """
 Бинарник icoextract — тот самый метод, которым пользуется PortProton.
 Пробуем системный, затем портативный из data/tmp/plugins_v20/portable (рядом с
 ним лежит собственный pefile в site-packages, поэтому PYTHONPATH переключаем).
 """
 candidates = []
 which = shutil.which('icoextract')
 if which:
  candidates.append(([which], None))
 pp_portable = "/home/egor/PortProton/data/tmp/plugins_v20/portable"
 pp_ico = os.path.join(pp_portable, "bin", "icoextract")
 if os.path.exists(pp_ico):
  pp_env = dict(os.environ,
   PYTHONPATH=os.path.join(pp_portable, "lib", "python3.9", "site-packages"))
  candidates.append(([pp_ico], pp_env))
 for cmd, env in candidates:
  try:
   r = subprocess.run(cmd + [pe_path, ico_out],
    capture_output=True, timeout=120, env=env)
   if r.returncode == 0 and os.path.getsize(ico_out) > 0:
    return True
  except Exception:
   continue
 return False


def extract_pe_icon(pe_path, target_dir, base_name):
 """
 Иконка из PE-файла (exe/dll/scr/mun/cpl/ocx). Цепочка методов:
  1. нативное извлечение через pefile (порт icoextract) — собирает валидный
     .ico, не требует внешних утилит
  2. бинарник icoextract — метод PortProton (системный или портативный)
  3. wrestool: RT_GROUP_ICON (тип 14), фолбэк на одиночные RT_ICON (тип 3);
     без -t 14 wrestool молча отказывается («don't know how to extract resource»)
 Максимальный кадр конвертируется в png через ico_to_png.
 """
 try:
  tmp = tempfile.mkdtemp(prefix="pe_icon_")
 except Exception:
  return None
 try:
  ico_out = os.path.join(tmp, "pe_icon.ico")
  icons = []
  if _extract_pe_native(pe_path, ico_out) or _extract_pe_icoextract(pe_path, ico_out):
   icons = [ico_out]
  if not icons:
   # неудачный частичный файл не должен мешать wrestool-фолбэку
   try:
    os.remove(ico_out)
   except Exception:
    pass
   for res_type in ('14', '3'):
    subprocess.run(['wrestool', '-x', '-t', res_type, '-o', tmp, pe_path],
     capture_output=True, timeout=90)
    icons = [os.path.join(r, f) for r, _, fs in os.walk(tmp) for f in fs
     if f.lower().endswith(('.ico', '.bmp')) and os.path.getsize(os.path.join(r, f)) > 0]
    if icons:
     break
  if not icons:
   return None
  # если иконок несколько — начинаем с самого крупного файла (там максимальное
  # разрешение внутри), ico_to_png ещё и выберет лучший кадр
  icons.sort(key=os.path.getsize, reverse=True)
  for icon in icons:
   result = ico_to_png(icon, target_dir, base_name)
   if result:
    return result
  return None
 except Exception:
  return None
 finally:
  shutil.rmtree(tmp, ignore_errors=True)


def extract_archive_icon(archive_path, target_dir, base_name):
 """
 Распаковывает deb/tar/zip/7z/rar/... во временную папку и ищет внутри png/svg.
 deb — через dpkg-deb -x (сам владеет ar+tar и любым сжатием), zip-подобные —
 unzip, всё остальное — tar (сам определяет сжатие), фолбэк на 7z.
 """
 try:
  tmp = tempfile.mkdtemp(prefix="arch_icon_")
 except Exception:
  return None
 try:
  low = archive_path.lower()
  if low.endswith('.deb'):
   subprocess.run(['dpkg-deb', '-x', archive_path, tmp],
    capture_output=True, timeout=300)
  elif low.endswith(('.zip', '.jar', '.apk')):
   subprocess.run(['unzip', '-o', '-q', archive_path, '-d', tmp],
    capture_output=True, timeout=300)
  else:
   r = subprocess.run(['tar', '-xf', archive_path, '-C', tmp],
    capture_output=True, timeout=300)
   if r.returncode != 0:
    subprocess.run(['7z', 'x', '-y', '-o' + tmp, archive_path],
     capture_output=True, timeout=300)
  found = find_icon_in_tree(tmp, base_name)
  if not found:
   return None
  return save_icon(found, target_dir, base_name)
 except Exception:
  return None
 finally:
  shutil.rmtree(tmp, ignore_errors=True)


def extract_icon_from_file(full_path, target_dir, base_name):
 """
 Универсальный диспетчер извлечения иконки по типу файла:
   AppImage       — выгрузка образа и .DirIcon
   PE (exe/dll)   — wrestool + PIL (максимальный кадр в png)
   deb/архивы     — распаковка во временную папку и поиск png/svg
 Обычные картинки и всё прочее здесь не трогаем — их подберёт поиск по папке
 рядом (find_best_icon), как и раньше.
 Возвращает путь к сохранённой иконке (icon-<base_name>.<ext>) или None.
 """
 low = full_path.lower()
 if low.endswith('.appimage'):
  return extract_appimage_icon(full_path, target_dir, base_name)
 ext = os.path.splitext(low)[1]
 if ext in {'.exe', '.dll', '.scr', '.mun', '.cpl', '.ocx'}:
  icon = extract_pe_icon(full_path, target_dir, base_name)
  if icon:
   return icon
 if ext in {'.deb', '.tar', '.gz', '.bz2', '.xz', '.zst', '.tgz', '.tbz',
   '.txz', '.zip', '.jar', '.apk', '.7z', '.rar', '.cab', '.msi',
   '.xpi', '.crx', '.vsix'} or '.tar.' in low:
  icon = extract_archive_icon(full_path, target_dir, base_name)
  if icon:
   return icon
 return None


def find_best_icon(image_list: list[str], search_name: str) -> str | None:
 """
 Ищет наиболее подходящую иконку по имени с учетом приоритетов.

 Приоритеты:
 1. Точное совпадение имени (без учета регистра и расширения)
 2. Имя + суффикс 'icon', 'logo', 'cover'
 3. Частичное совпадение (подстрока)

 Внутри каждой категории предпочтение отдается форматам: svg > png > jpg > bmp
 """
 if not image_list or not search_name:
  return None
 
 # Приоритеты расширений (чем меньше индекс, тем лучше)
 EXT_PRIORITY = {'.svg': 0, '.png': 1, '.jpg': 2, '.jpeg': 2, '.gif': 3, '.bmp': 4}
 
 search_lower = search_name.lower()
 candidates = []
 
 for image in image_list:
  name_part, ext = os.path.splitext(image)
  name_lower = name_part.lower()
  ext_lower = ext.lower()
  
  if ext_lower not in EXT_PRIORITY:
   continue
  
  score = float('inf')
  
  # Категория 0: Точное совпадение имени файла
  if name_lower == search_lower:
   score = 0
  # Категория 1: Имя + стандартные суффиксы для иконок
  elif re.match(rf'^{re.escape(search_lower)}[-_]?(icon|logo|cover|art)$', name_lower):
   score = 10
  # Категория 2: Имя является началом строки (префикс)
  elif name_lower.startswith(search_lower):
   score = 20 + len(name_lower) - len(search_lower)
  # Категория 3: Подстрока (наименее желательный вариант)
  elif search_lower in name_lower:
   score = 100 + len(name_lower) - len(search_lower)
  else:
   continue
  
  # Добавляем приоритет расширения к общему счету
  total_score = score + EXT_PRIORITY.get(ext_lower, 99) * 0.1
  candidates.append((total_score, image))
 
 if not candidates:
  return None
 
 # Сортируем по счету и берем лучший результат
 candidates.sort(key=lambda x: x[0])
 return candidates[0][1]


def get_files_with_extensions(folder_path):
 """Рекурсивно собирает все изображения в папке."""
 image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'}
 image_files = []
 
 for root, dirs, files in os.walk(folder_path):
  for file in files:
   _, ext = os.path.splitext(file)
   if ext.lower() in image_extensions:
    image_files.append(file)
 
 return image_files


def get_paths_file():
 """Парсит аргументы командной строки и возвращает пути."""
 # Объединяем аргументы (на случай если путь содержит пробелы и передан частями)
 url = " ".join(str(arg) for arg in sys.argv[1:]).strip()
 # url = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/opencode-desktop-linux-x86_64.AppImage"
 if not url:
  print("Ошибка: Не передан путь к файлу.")
  sys.exit(1)
 
 full_path = url
 directory = os.path.dirname(full_path)
 filename = os.path.basename(full_path)
 
 filename_without_extension = os.path.splitext(filename)[0]
 
 return directory, filename_without_extension, filename, full_path


# === Основная логика ===
directory, filename_without_extension, filename, full_path = get_paths_file()

# Сначала пробуем извлечь иконку из самого файла — универсально, по типу:
# AppImage, PE (exe/dll), deb/архивы; обычные картинки и всё остальное
# подберёт поиск по папке рядом (find_best_icon).
# Имя сохранённой иконки НЕ начинается с точки (icon-<имя>.<ext>).
icon_path = ""
if os.path.isfile(full_path):
    icon_path = extract_icon_from_file(full_path, directory, filename_without_extension) or ""

if not icon_path:
    # Получаем список картинок и ищем лучшую иконку
    image_list = get_files_with_extensions(directory)
    best_icon_name = find_best_icon(image_list, filename_without_extension)
    if best_icon_name:
        icon_path = os.path.join(directory, best_icon_name)

if not icon_path:
    print(f"Предупреждение: Иконка для '{filename_without_extension}' не найдена.")

# Генерация .desktop файла
desktop_content = f"""[Desktop Entry]
Name={filename_without_extension+str(".desktop")}
Exec="{full_path}"
Icon={icon_path}
Terminal=false
Categories=Game
Type=Application
"""

output_file = os.path.join(directory, filename_without_extension+str(".desktop"))
print(f"Создание файла: {output_file}")

with open(output_file, 'w') as f:
 f.write(desktop_content)

# Установка прав на исполнение (напрямую, без shell — bash -c здесь был лишним:
# кавычки в пути ломали бы команду; на NTFS chmod всё равно молча ничего не сделает)
subprocess.run(['chmod', '+x', output_file])




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
