import os
import shutil
import subprocess
import zipfile
import struct
import sys
import stat
from pathlib import Path

# ================= ПУТИ =================
BASE_DIR = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/xbox")
INPUT_ISO = BASE_DIR / "ObsCure_XBOX.iso"  # ОБЯЗАТЕЛЬНО ЧИСТЫЙ ОБРАЗ
OUTPUT_ISO = BASE_DIR / "Obscure_AMMO_ONLY.iso"
TOOL_ZIP = BASE_DIR / "extract-xiso_Linux.zip"
WORK_DIR = BASE_DIR / "ammo_patch_work"


# ================= ПАТЧ ТОЛЬКО ПАТРОНОВ =================

def patch_ammo_only(xbe_path):
 print(f"\n[*] Анализ файла: {xbe_path.name}")

 with open(xbe_path, "rb") as f:
  data = bytearray(f.read())

 # Мы ищем структуру данных игрока.
 # Маркером все еще служит 100.0 (фонарик), но мы НЕ БУДЕМ его менять.
 # Мы будем менять только числа, идущие ПОСЛЕ него.

 search_pattern = b'\x00\x00\xC8\x42'  # 100.0

 patches_applied = 0
 offset = 0

 while True:
  offset = data.find(search_pattern, offset)
  if offset == -1:
   break

  # Проверяем окружение
  # Нам нужны смещения +4, +8, +12 и т.д. (где лежат патроны)
  try:
   # Смотрим на 5 чисел (интеджеров) после 100.0
   # Структура в памяти обычно: [Float HP/Flash] [Int Ammo1] [Int Ammo2] ...

   valid_ammo_sequence = False
   ammo_offsets = []

   # Проверяем следующие 6 слотов (24 байта)
   for i in range(1, 7):
    val_off = offset + (i * 4)
    if val_off + 4 > len(data): break

    val = struct.unpack('<I', data[val_off: val_off + 4])[0]

    # ЭВРИСТИКА:
    # Патроны - это маленькие числа (от 0 до 200).
    # Если число > 1000000, это указатель памяти, его трогать нельзя (будет вылет).
    if 0 <= val < 300:
     ammo_offsets.append(val_off)
     if val > 0:  # Если хотя бы одно число не ноль (например, 10 патронов)
      valid_ammo_sequence = True

   # Если мы нашли ряд маленьких чисел после 100.0 -> это инвентарь
   if valid_ammo_sequence and len(ammo_offsets) >= 2:
    print(f"    [!] Найден инвентарь по адресу {hex(offset)}")

    # ВАЖНО: Сам Float по адресу 'offset' (100.0) мы НЕ ТРОГАЕМ!
    # Иначе сломается дверь/физика.

    # Патчим только найденные слоты патронов
    for ammo_addr in ammo_offsets:
     old_val = struct.unpack('<I', data[ammo_addr: ammo_addr + 4])[0]
     # Ставим 999 патронов
     struct.pack_into('<I', data, ammo_addr, 999)
     # print(f"        -> Ammo fix: {old_val} -> 999")

    patches_applied += 1

  except Exception:
   pass

  offset += 4

 if patches_applied > 0:
  with open(xbe_path, "wb") as f:
   f.write(data)
  print(f"    [✓] Патч применен. Изменено структур: {patches_applied}")
  print("        (Фонарик не тронут во избежание вылетов, патроны = 999)")
  return True
 else:
  return False


# ================= СБОРКА =================

def setup_tool():
 if WORK_DIR.exists(): shutil.rmtree(WORK_DIR)
 WORK_DIR.mkdir(parents=True, exist_ok=True)
 with zipfile.ZipFile(TOOL_ZIP, 'r') as zf:
  zf.extractall(WORK_DIR)
 tool_bin = None
 for f in WORK_DIR.rglob("*"):
  if "extract-xiso" in f.name and not f.name.endswith(".zip") and f.is_file():
   tool_bin = f
   break
 if tool_bin:
  st = os.stat(tool_bin)
  os.chmod(tool_bin, st.st_mode | stat.S_IEXEC)
 return tool_bin


def main():
 try:
  print("--- OBSCURE STABLE PATCH (NO CRASH) ---")
  tool = setup_tool()
  if not tool: return

  extract_dir = WORK_DIR / "iso_extracted"
  extract_dir.mkdir(exist_ok=True)

  print(f"[*] Распаковка {INPUT_ISO.name}...")
  subprocess.run([str(tool), "-x", str(INPUT_ISO), "-d", str(extract_dir)], check=True)

  print("\n[*] Патчинг патронов (безопасный режим)...")
  files_to_patch = list(extract_dir.rglob("*.xbe"))
  success = False

  for game_file in files_to_patch:
   if game_file.name.lower() in ['eng.xbe', 'rus.xbe']:
    if patch_ammo_only(game_file):
     success = True

  if success:
   print(f"\n[*] Сборка образа: {OUTPUT_ISO.name}...")
   if OUTPUT_ISO.exists(): OUTPUT_ISO.unlink()
   subprocess.run([str(tool), "-c", str(extract_dir), str(OUTPUT_ISO)], check=True)
   print(f"\n[✓] ГОТОВО! Используй {OUTPUT_ISO.name}")
  else:
   print("[!] Патчи не применены. Проверь файлы.")

 except Exception as e:
  print(f"Error: {e}")
 finally:
  if WORK_DIR.exists(): shutil.rmtree(WORK_DIR)


if __name__ == "__main__":
 main()