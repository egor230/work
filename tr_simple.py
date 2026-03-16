#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import struct


def elevate():
 if os.getuid() != 0:
  os.execvp("sudo", ["sudo", "python3"] + sys.argv)


class TombRaiderMaster:
 def __init__(self):
  self.pid = None
  self.base_address = None

 def get_pid(self):
  try:
   res = subprocess.run(["pgrep", "-f", "TombRaider"], capture_output=True, text=True)
   if res.returncode == 0:
    self.pid = int(res.stdout.split('\n')[0])
    return True
  except:
   return False
  return False

 def auto_inject(self):
  """
  Здесь должен быть поиск сигнатуры (AOB).
  Без конкретного адреса из твоей системы (Linux Mint + твоя версия игры)
  запись в случайное место убьет процесс.
  """
  # Если бы у нас был адрес 0x12345, мы бы писали сюда бесконечно:
  # with open(f"/proc/{self.pid}/mem", "r+b") as mem:
  #     mem.seek(0x12345)
  #     mem.write(struct.pack("f", 9999.0))
  pass


def main():
 elevate()
 bot = TombRaiderMaster()
 print("🤖 Фоновый мониторинг запущен...")

 while True:
  if bot.get_pid():
   # Игра запущена — тут скрипт должен "тихо" делать свою работу
   bot.auto_inject()
   time.sleep(5)
  else:
   time.sleep(10)


if __name__ == "__main__":
 main()