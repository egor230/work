import subprocess
import os

# Открываем файл для записи
with open("requirements.sh", "w") as file:
    # Шебанг и запуск терминала
    file.write("#!/bin/bash\n")
    file.write(
        'gnome-terminal -- bash -c \'cd "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project";\n'
    )
    file.write('source myenv/bin/activate;\n')
    file.write('pip install --upgrade pip;\n')

    # Получаем список установленных пакетов через pip freeze
    result = subprocess.run(["pip", "freeze"], capture_output=True, text=True)
    packages = result.stdout.splitlines()

    # Записываем команды для установки пакетов
    for package in packages:
        # Строка имеет вид "package==version"
        package_name = package.split("==")[0]

        # ИСПРАВЛЕННОЕ УСЛОВИЕ:
        # Если нужно пропустить некоторые пакеты, то пишем правильно:
        if "huggingface" in package_name or "gigaam" in package_name:
            continue  # пропускаем

        # Записываем команду pip install с указанием версии
        file.write(f"pip install {package};\n")

    # Закрываем команду для gnome-terminal
    file.write("bash'\n")

# Делаем файл исполняемым
os.chmod("requirements.sh", 0o755)

print("Файл 'requirements.sh' успешно создан.")
