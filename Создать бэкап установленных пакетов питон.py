import subprocess, os
# Открываем файл для записи
with open("requirements.sh", "w") as file:
    # Шебанг и запуск терминала
    file.write("#!/bin/bash\n")
    file.write(
    'gnome-terminal -- bash -c \'source "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/activate";\n'
    )
    file.write('pip install --upgrade pip;\n')

    # Получаем список установленных пакетов через pip freeze
    result = subprocess.run(["pip", "freeze"], capture_output=True, text=True)
    packages = result.stdout.splitlines()

    # Записываем команды для установки пакетов
    for package in packages:
        # Разбиваем строку на имя и версию
        if "==" not in package:
            continue  # пропускаем строки без версии
        package_name, package_version = package.split("==", 1)

        # Проверяем, нужно ли пропустить пакет
        if any(bad in package_name for bad in ["huggingface", "gigachat", "nvidia"]):
            continue  # пропускаем

        # # Обрабатываем PyTorch-пакеты
        # if package_name in ("torch", "torchvision", "torchaudio"):
        #     if package_name == "torch":
        #         file.write("pip install torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu;\n")
        #     elif package_name == "torchvision":
        #         file.write("pip install torchvision==0.20.1+cpu --index-url https://download.pytorch.org/whl/cpu;\n")
        #     elif package_name == "torchaudio":
        #         file.write("pip install torchaudio==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu;\n")
        #     continue

        # Записываем команду pip install с указанием версии
        file.write(f"pip install {package};\n")

    # Закрываем команду для gnome-terminal
    file.write("bash'\n")

# Делаем файл исполняемым
os.chmod("requirements.sh", 0o755)
print("Файл 'requirements.sh' успешно создан.")
