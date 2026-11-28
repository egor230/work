#!/usr/bin/env python3
"""
mouse_hid_tool.py — утилита для investigations HID-устройства
[Maxxter] Optical Gaming Mouse [Xtrem] (VID 18F8 / PID 0F97).

Мышь имеет скрытый Vendor-Defined FEATURE report ID 7 (7 байт данных)
на интерфейсе 1 (hidraw). Через него теоретически задаются DPI и подсветка,
но формат команд неизвестен — этим инструментом его удобно подбирать.

Запуск:  sudo python3 mouse_hid_tool.py <команда>

Команды:
  info                показать найденные HID-интерфейсы мыши
  get                 прочитать текущее содержимое report 7
  set XX XX ...       записать произвольный report (первый байт — ID=07)
  sweep [n]           прогнать кандидаты команд с паузами (наблюдайте за мышью)
  dpi N               попробовать установить DPI-индекс N (0..9)
  rgb R G B           попробовать задать цвет подсветки

ВАЖНО: все команды отправляются "как есть", без проверки корректности —
прошивка мыши может отреагировать неожиданно. ПриProblems отключите/подключите
мышь заново (если есть возможность) —-volatile настройки сбросятся.
"""
import fcntl
import glob
import os
import sys
import time

VID = 0x18F8
PID = 0x0F97
REPORT_ID = 7
REPORT_LEN = 8  # 1 байт ID + 7 байт данных


def ioc_get(size):
    return (3 << 30) | (ord('H') << 8) | 0x07 | (size << 16)


def ioc_set(size):
    return (3 << 30) | (ord('H') << 8) | 0x06 | (size << 16)


def find_hidraw():
    found = []
    for path in glob.glob('/sys/class/hidraw/hidraw*/device/uevent'):
        try:
            text = open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        if ('HID_ID=0003:%08X:%08X' % (VID, PID)) not in text.upper():
            # HID_ID может быть в нижнем регистре — сравним мягко
            if ('%08x:%08x' % (VID, PID)) not in text.lower():
                continue
        iface = '?'
        if 'input0' in text:
            iface = 'mouse (input0)'
        elif 'input1' in text:
            iface = 'keyboard/vendor (input1)'
        dev = path.split('/device/')[0].rsplit('/', 1)[-1]
        found.append(('/dev/' + dev, iface, path))
    return found


def open_vendor():
    for dev, iface, _ in find_hidraw():
        if 'input1' in iface:
            return os.open(dev, os.O_RDWR)
    # fallback: первый попавшийся интерфейс мыши
    found = find_hidraw()
    if found:
        return os.open(found[0][0], os.O_RDWR)
    raise RuntimeError('мышь 18F8:0F97 не найдена среди hidraw-устройств')


def get_feature(fd):
    buf = bytearray([REPORT_ID] + [0] * 31)
    n = fcntl.ioctl(fd, ioc_get(len(buf)), buf, True)
    return bytes(buf[:n])


def set_feature(fd, data):
    if not data or data[0] != REPORT_ID:
        data = bytes([REPORT_ID]) + bytes(data)
    data = (bytes(data) + bytes(REPORT_LEN))[:REPORT_LEN]
    fcntl.ioctl(fd, ioc_set(len(data)), bytearray(data), True)
    return data


def cmd_info():
    found = find_hidraw()
    if not found:
        print('Мышь не найдена')
        return
    for dev, iface, syspath in found:
        print('%s  %-24s  %s' % (dev, iface, syspath))


def cmd_get():
    fd = open_vendor()
    try:
        data = get_feature(fd)
        print('report 7 =', data.hex(' '))
    finally:
        os.close(fd)


def cmd_set(hexbytes):
    try:
        data = bytes(int(x, 16) for x in hexbytes)
    except ValueError as e:
        print('Ошибка разбора hex:', e)
        return
    fd = open_vendor()
    try:
        print('SET ->', set_feature(fd, data).hex(' '))
        print('GET <-', get_feature(fd).hex(' '))
    finally:
        os.close(fd)


def cmd_sweep(count=1):
    fd = open_vendor()
    # Кандидаты: opcode 0..15; для каждого — несколько значений второго байта
    try:
        for op in range(16):
            for param in range(0, 6):
                pkt = bytes([REPORT_ID, op, param, 255, 0, 0, 0, 0])
                set_feature(fd, pkt)
                print('op=%2d param=%d %s %s' % (op, param,
                      time.strftime('%H:%M:%S'), pkt.hex()), flush=True)
                time.sleep(0.8)
    finally:
        os.close(fd)


def cmd_dpi(index):
    fd = open_vendor()
    try:
        for op in range(16):
            pkt = bytes([REPORT_ID, op, index, 0, 0, 0, 0, 0])
            set_feature(fd, pkt)
            print('op=%2d dpi=%d %s' % (op, index, pkt.hex()), flush=True)
            time.sleep(1.0)
    finally:
        os.close(fd)


def cmd_rgb(r, g, b):
    fd = open_vendor()
    try:
        for op in range(16):
            pkt = bytes([REPORT_ID, op, 1, r, g, b, 0, 0])
            set_feature(fd, pkt)
            print('op=%2d rgb=(%d,%d,%d) %s' % (op, r, g, b, pkt.hex()), flush=True)
            time.sleep(1.0)
    finally:
        os.close(fd)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1].lower()
    if cmd == 'info':
        cmd_info()
    elif cmd == 'get':
        cmd_get()
    elif cmd == 'set':
        cmd_set(sys.argv[2:])
    elif cmd == 'sweep':
        cmd_sweep()
    elif cmd == 'dpi':
        cmd_dpi(int(sys.argv[2]))
    elif cmd == 'rgb':
        cmd_rgb(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
