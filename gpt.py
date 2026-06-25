# import g4f
#
# response = g4f.ChatCompletion.create(
#     model=g4f.models.default,
#     messages=[{"role": "user", "content": "Hello"}],
#     proxy="http://host:port",
#     # or socks5://user:pass@host:port
#     timeout=120,  # in secs
# )
#
# print(f"Result:", response)
import time

import telegram
import requests
TOKEN = "1658535416:AAF3aafmAkRne-LzzVWQ5Zw_eivOTX1oJrc"

message = "как создать бота "


def send_message_to_telegram_bot(chat_id, message, token):
  url = f"https://api.telegram.org/bot{token}/sendMessage"
  params = {
    "chat_id": chat_id,
    "text": message
  }

  response = requests.get(url, params=params)

  return response.json()


def get_updates(bot_token, offset):
  url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
  params = {
    "offset": offset + 1
  }

  response = requests.get(url, params=params)

  return response.json()

# result = send_message_to_telegram_bot(YOUR_CHAT_ID, message, TOKEN)
# print(result)

import requests
import time

def send_message_to_telegram_bot(chat_id, message, token):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    response = requests.post(url, data=data)
    return response.json()


def delete_webhook(token):
  url = f"https://api.telegram.org/bot{token}/deleteWebhook"
  response = requests.post(url)
  return response.json()


import requests

def get_updates(token, offset=0):
  url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=100&allowed_updates=['message']"
  response = requests.get(url)
  updates = response.json()
  print(updates)
  if 'result' in updates and updates['result']:
    # Возвращаем последнее сообщение из последнего обновления
    return updates['result'][-1]['message']
  else:
    print("No updates or error getting updates:", updates)
    return None

def main():
    YOUR_CHAT_ID = 971199101
    TOKEN = "1658535416:AAF3aafmAkRne-LzzVWQ5Zw_eivOTX1oJrc"
    # message = "напиши пожалуйста питон код который считает 2 часа и находит их сумму"
    # send_message_to_telegram_bot(YOUR_CHAT_ID, message, TOKEN)
    # while True:
    updates = get_updates(TOKEN)
    print(updates)
    # for update in updates["result"]:
    #     offset = update["update_id"]
    #     if "message" in update:
    #         chat_id = update["message"]["chat"]["id"]
    #         message = update["message"]["text"]
    #         print(f"Received message: {message}")

    time.sleep(1)
# delete_webhook_response = delete_webhook(TOKEN)
# print(delete_webhook_response)
#
# # Если webhook был успешно удален, запускаем главную функцию
# if delete_webhook_response.get("ok"):
# main()

