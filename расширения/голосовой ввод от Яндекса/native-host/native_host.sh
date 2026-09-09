#!/bin/bash
# ============================================================
# native_host.sh — shim для Chrome native messaging
# КРИТИЧНО: браузер стартует native host в стерильном окружении
# БЕЗ DISPLAY. Печать идёт через X11-инструменты (xte/xset в
# write_text_fast.set_layout) + pynput требует X при импорте —
# без DISPLAY хост падает на старте и текст никогда не печатается.
# Поэтому прописываем окружение X ЯВНО.
# ============================================================
export DISPLAY=":0"
export XAUTHORITY="$HOME/.Xauthority"
exec "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python" "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/расширения/голосовой ввод от Яндекса/native-host/native_host.py"
