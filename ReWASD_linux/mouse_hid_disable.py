#!/usr/bin/env python3
"""
mouse_hid_disable.py — отключение подсветки и блокировка переключения DPI
на мыши [Maxxter] Optical Gaming Mouse [Xtrem] (VID 18F8 / PID 0F97).

Суть: у мыши есть скрытый vendor FEATURE report ID 7 (7 байт данных).
Прошивка использует только первые ТРИ байта данных: [opcode, p1, p2].
Экспериментально установлено, что команда из одних нулей

    07 00 00 00 00 00 00 00

выключает подсветку и после неё DPI-кнопка перестаёт переключать
чувствительность (наблюдалось на этой машине 28.11.2026).

Подробности и полная история экспериментов — в
ОБНОВЛЕНИЯ_2026-11-28.md, раздел 8, и в mouse_hid_tool.py.

Запуск (обязательно root — /dev/hidraw* доступен только root):

    sudo python3 mouse_hid_disable.py disable   # отключить (по умолчанию)
    sudo python3 mouse_hid_disable.py status    # прочитать текущий report 7
    sudo python3 mouse_hid_disable.py set 07 00 00 00 00 00 00 00

Чтобы вернуть исходное состояние, если оно было сохранено в EEPROM, —
переподключите мышь физически (отключить/включить USB). Программного
команды «включить обратно» надёжно не найдено.
"""
import fcntl
import glob
import os
import sys

VID = 0x18F8
PID = 0x0F97
REPORT_ID = 7
REPORT_LEN = 8  # 1 байт ID + 7 байт данных
DISABLE = bytes([0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])


def _ioc(nr, size):
    return (3 << 30) | (ord('H') << 8) | nr | (size << 16)


def find_hidraw():
    """Ищем hidraw-интерфейс мыши по VID/PID из sysfs."""
    result = []
    for uevent in glob.glob('/sys/class/hidraw/hidraw*/device/uevent'):
        try:
            text = open(uevent, encoding='utf-8', errors='replace').read().lower()
        except OSError:
            continue
        marker = 'hid_id=0003:%08x:%08x' % (VID, PID)
        if marker not in text:
            continue
        dev = '/dev/' + uevent.split('/device/')[0].rsplit('/', 1)[-1]
        iface = 'keyboard/vendor (input1)' if 'input1' in text else 'mouse (input0)'
        result.append((dev, iface))
    return result


def open_vendor_interface():
    found = find_hidraw()
    if not found:
        raise RuntimeError('мышь 18F8:0F97 не найдена среди hidraw-устройств')
    # Нужен именно интерфейс 1 — на нём висит FEATURE report 7.
    for dev, iface in found:
        if 'input1' in iface:
            return os.open(dev, os.O_RDWR), dev
    return os.open(found[0][0], os.O_RDWR), found[0][0]


def read_report(fd):
    buf = bytearray([REPORT_ID] + [0] * 31)
    n = fcntl.ioctl(fd, _ioc(0x07, len(buf)), buf, True)
    return bytes(buf[:n])


def write_report(fd, data):
    data = bytes(data)
    if not data or data[0] != REPORT_ID:
        data = bytes([REPORT_ID]) + data
    data = (data + bytes(REPORT_LEN))[:REPORT_LEN]
    fcntl.ioctl(fd, _ioc(0x06, len(data)), bytearray(data), True)
    return data


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1].lower()

    if os.geteuid() != 0:
        print('Ошибка: нужен root (sudo python3 mouse_hid_disable.py ...).')
        sys.exit(1)

    fd, dev = open_vendor_interface()
    try:
        print('HID-интерфейс:', dev)

        if cmd == 'status':
            print('report 7 =', read_report(fd).hex(' '))
            return

        if cmd == 'set':
            try:
                data = bytes(int(x, 16) for x in sys.argv[2:])
            except ValueError as exc:
                print('Ошибка разбора hex:', exc)
                sys.exit(1)
            print('SET ->', write_report(fd, data).hex(' '))
            print('GET <-', read_report(fd).hex(' '))
            return

        if cmd in ('disable', 'off', 'all'):
            print('Отправляем команду отключения:', DISABLE.hex(' '))
            write_report(fd, DISABLE)
            # Повтор на всякий случай: некоторые прошивки применяют команду
            # только со второй попытки после смены режима.
            write_report(fd, DISABLE)
            print('report 7 после записи:', read_report(fd).hex(' '))
            print('Готово. Подсветка выключена, переключение DPI заблокировано.')
            print('Для восстановления — физическое переподключение мыши.')
            return

        print(__doc__)
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
