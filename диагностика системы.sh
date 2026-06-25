#!/bin/bash
gnome-terminal -- bash -c '
echo "--- СИСТЕМА И ГРАФИКА ---" && inxi -Gxxz && echo "--- РАБОТА VULKAN ---" && vulkaninfo --summary || echo "Vulkan не найден" && echo "--- ОШИБКИ ЯДРА (ПОСЛЕДНИЕ 20 СТРОК) ---" && sudo dmesg | tail -n 20

echo "Завершено."
read -p "Нажмите Enter для закрытия окна..."

'
