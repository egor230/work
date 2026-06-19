import subprocess
import re
import os
import sys
import subprocess
from pathlib import Path

WORK_DIR = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/xbox/ObsCure")
TOOLS_DIR = Path("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/xbox/extract-xiso_Linux")
CREATE_XISO = TOOLS_DIR / "create-xiso"
OUTPUT_ISO = "Obscure_CHEATS.iso"

# Минимальные файлы, без которых Obscure не запустится
REQUIRED_FILES = [
 "default.xbe",
 "STRM_EN.hvp",  # ← тут была ошибка!
 "MUSC_EN.hvp",
 "FONT.xpr",
 "LOGO.xpr",
]


def check_files():
 missing = []
 for f in REQUIRED_FILES:
  if not (WORK_DIR / f).exists():
   missing.append(f)
 return missing


def main():
 print("🎄 Obscure XISO Builder (финальная версия)")
 print("=" * 55)

 if not WORK_DIR.exists():
  print(f"❌ Папка не найдена: {WORK_DIR}")
  sys.exit(1)
 os.chdir(WORK_DIR)
 print(f"📂 Рабочая папка: {WORK_DIR}")

 # Проверка утилиты
 if not CREATE_XISO.exists():
  print("❌ create-xiso не найден. Установи его в extract-xiso_Linux/")
  sys.exit(1)
 CREATE_XISO.chmod(0o755)

 # 🔍 Проверка файлов
 missing = check_files()
 if missing:
  print("❌ Отсутствуют критичные файлы:")
  for f in missing:
   print(f"   - {f}")
  print("\n🛠  РЕКОМЕНДУЕТСЯ:")
  print("1. Распакуй оригинальный образ Obscure.iso:")
  print("   extract-xiso -q Obscure.iso /tmp/ObsCure_orig")
  print("2. Скопируй ВСЁ содержимое в ObsCure:")
  print("   cp -v /tmp/ObsCure_orig/* ./")
  print("3. Замени ТОЛЬКО default.xbe на свой (с читами)")
  sys.exit(1)
 else:
  print("✅ Все обязательные файлы на месте")

 # 🏗 Сборка
 print(f"\n📦 Создаю {OUTPUT_ISO}...")
 cmd = [str(CREATE_XISO), "-q", "-c", ".", OUTPUT_ISO]
 try:
  result = subprocess.run(cmd, capture_output=True, text=True)
  if result.returncode == 0:
   if (WORK_DIR / OUTPUT_ISO).exists():
    size_mb = (WORK_DIR / OUTPUT_ISO).stat().st_size / (1024 ** 2)
    print(f"🎉 Готово! {OUTPUT_ISO} ({size_mb:.1f} МБ)")
   else:
    print("⚠️  Файл не создан. Проверь свободное место.")
  else:
   print(f"❌ Ошибка (код {result.returncode})")
   if result.stderr.strip():
    print("stderr:", result.stderr.strip())
   if result.stdout.strip():
    print("stdout:", result.stdout.strip())
   sys.exit(1)
 except Exception as e:
  print(f"💥 Ошибка: {e}")
  sys.exit(1)

 print("\n🎮 Запускай в эмуляторе!")


if __name__ == "__main__":
 main()

# Получаем текущую группу (0 = первая раскладка, 1 = вторая и т.д.)
result = subprocess.run(['xset', '-q'], capture_output=True, text=True)
print(result)

