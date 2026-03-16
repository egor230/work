#!/bin/bash
gnome-terminal -- bash -c '
# Система и ядро
uname -a
cat /etc/os-release
echo "Session: $XDG_SESSION_TYPE"

# Видеокарта и драйверы
lspci -k | grep -A 3 -E "VGA|3D"
glxinfo -B
vulkaninfo --summary
modinfo nvidia | grep version
modinfo amdgpu | grep version

# Процессор и частоты
lscpu
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
grep -E "model name|cpu MHz" /proc/cpuinfo

# Память и лимиты
free -h
swapon --show
ulimit -a

# Температуры и аппаратные сообщения (ошибки)
sensors
dmesg | grep -iE "error|fail|critical|throttling" | tail -n 50

# Переменные окружения
printenv | grep -E "DISPLAY|WAYLAND|RENDER"

exit;
exec bash'
 
