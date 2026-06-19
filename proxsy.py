import re, requests, socket


def check_mtproto(host, port):
 try:
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.settimeout(3)
  result = sock.connect_ex((host, int(port)))
  sock.close()
  if result == 0:
   return True
 except:
  return False
 return False


def get_working_proxies():
 print("Начинаю поиск рабочих MTPROTO прокси...")
 working_proxies = []
 
 sources = [
  "https://raw.githubusercontent.com/Grim1313/mtproto-for-telegram/master/all_proxies.txt",
  "https://raw.githubusercontent.com/ALIILAPRO/MTProtoProxy/main/mtproto.txt"
 ]
 
 for url in sources:
  if len(working_proxies) >= 10:
   break
  
  try:
   print(f"Загружаю данные из источника: {url}")
   response = requests.get(url, timeout=10)
   if response.status_code != 200:
    continue
   
   lines = response.text.split("\n")
   for line in lines:
    if len(working_proxies) >= 10:
     break
    
    if "server=" in line and "port=" in line and "secret=" in line:
     server_match = re.search(r"server=([^&?\s]+)", line)
     port_match = re.search(r"port=([^&?\s]+)", line)
     secret_match = re.search(r"secret=([^&?\s]+)", line)
     
     if server_match and port_match and secret_match:
      host = server_match.group(1)
      port = port_match.group(1)
      secret = secret_match.group(1)
      
      if check_mtproto(host, port):
       print("Соединение установлено! Рабочий MTPROTO найден.")
       proxy_data = {
        "host": host,
        "port": port,
        "secret": secret
       }
       working_proxies.append(proxy_data)
  
  except Exception as error:
   print(f"Ошибка при обработке источника: {error}")
 
 return working_proxies


if __name__ == "__main__":
 found_proxies = get_working_proxies()
 
 print("\nРезультат поиска (Первые 10 рабочих MTPROTO):")
 if found_proxies:
  for current_proxy in found_proxies:
   print("---")
   print(f"Хост: {current_proxy['host']}")
   print(f"Порт: {current_proxy['port']}")
   print(f"Ключ (Secret): {current_proxy['secret']}")
   print(f"Ссылка для клика: https://t.me/proxy?server={current_proxy['host']}&port={current_proxy['port']}&secret={current_proxy['secret']}")
 else:
  print("Не удалось найти достаточное количество активных MTPROTO прокси.")
# def main():
    # all_proxies = []
    #
    # for url in SOURCES:
    #     print(f"[+] Проверяю {url}")
    #     content = fetch_url(url)
    #
    #     proxies = extract_mtproto(content)
    #     all_proxies.extend(proxies)
    #
    # # удаление дублей
    # unique = {}
    # for p in all_proxies:
    #     key = (p["server"], p["port"], p["secret"])
    #     unique[key] = p
    #
    # proxies = list(unique.values())
    #
    # print(f"\nНайдено: {len(proxies)} MTProto прокси")
    #
    # with open("mtproto.txt", "w") as f:
    #     for p in proxies:
    #         f.write(f"{p['server']}:{p['port']}:{p['secret']}\n")
    #
    # print("Сохранено в mtproto.txt")


if __name__ == "__main__":
 found_proxies = get_working_proxies()
 
 print("\nРезультат поиска:")
 if found_proxies:
  for current_proxy in found_proxies:
   print(current_proxy)
 else:
  print("Не удалось найти 10 рабочих MTPROTO прокси. Попробуйте позже.")
 
if __name__ == "__main__":
 found_proxies = get_working_proxies()
 
 print("\nРезультат поиска:")
 if found_proxies:
  for current_proxy in found_proxies:
   print(current_proxy)
 else:
  print("Не удалось найти 10 рабочих прокси за один запуск. Попробуйте позже.")
# if __name__ == "__main__":
#     main()