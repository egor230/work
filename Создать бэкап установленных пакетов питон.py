import subprocess, sys, os

# Конфигурация
output_filename = "requirements.sh"
# Лучше хранить путь в переменной, чтобы было проще править
venv_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/activate"
exclude_keywords = ["huggingface", "gigachat", "nvidia"]

with open(output_filename, "w") as file:
 # Шебанг
 file.write("#!/bin/bash\n")

 # Запуск gnome-terminal.
 # Обратите внимание: мы открываем одинарную кавычку для bash -c здесь,
 # а закрываем её в самом конце. Это позволяет писать команды на разных строках.
 # Также добавлены кавычки вокруг пути source, чтобы работать с пробелами в пути.
 file.write(f'gnome-terminal -- bash -c \'source "{venv_path}";\n')

 file.write('pip install --upgrade pip;\n')

 # Получаем список пакетов, используя текущий интерпретатор Python
 # Это надежнее, чем просто вызов "pip freeze"
 result = subprocess.run(
  [sys.executable, "-m", "pip", "freeze"],
  capture_output=True,
  text=True,
  check=True
 )

 packages = result.stdout.splitlines()

 for package in packages:
  package = package.strip()

  # Пропускаем пустые строки и комментарии
  if not package or package.startswith("#"):
   continue

  # Пропускаем строки без явной версии (например, git-ссылки)
  if "==" not in package:
   continue

  # Извлекаем имя пакета для проверки фильтров
  package_name = package.split("==", 1)[0]

  # Проверяем, нужно ли пропустить пакет
  if any(bad in package_name for bad in exclude_keywords):
   continue

  # Записываем команду установки
  file.write(f"pip install {package};\n")

 # Закрываем одинарную кавычку команды bash -c и запускаем bash, чтобы терминал не закрылся
 file.write("bash'\n")

# Делаем файл исполняемым
os.chmod(output_filename, 0o755)
print(f"Файл '{output_filename}' успешно создан.")
# # Обрабатываем PyTorch-пакеты
# if package_name in ("torch", "torchvision", "torchaudio"):
#     if package_name == "torch":
#         file.write("pip install torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu;\n")
#     elif package_name == "torchvision":
#         file.write("pip install torchvision==0.20.1+cpu --index-url https://download.pytorch.org/whl/cpu;\n")
#     elif package_name == "torchaudio":
#         file.write("pip install torchaudio==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu;\n")
#     continue