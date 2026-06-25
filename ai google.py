import requests

API_KEY = "AIzaSyDS67-G3odwXRuv7aSj4UDNACEyk4CSXos"  # Замените на реальный ключ
API_URL = "https://api.deepseek.com/v1/chat/completions"


def ask_deepseek(question):
 headers = {
  "Authorization": f"Bearer {API_KEY}".encode("utf-8").decode("latin-1"),
  "Content-Type": "application/json"
 }
 
 data = {
  "model": "deepseek-chat",
  "messages": [{"role": "user", "content": question}]
 }
 
 try:
  response = requests.post(API_URL, headers=headers, json=data)
  response.raise_for_status()  # Проверка на ошибки HTTP
  return response.json()["choices"][0]["message"]["content"]
 except requests.exceptions.RequestException as e:
  return f"Ошибка запроса: {e}"
 except (KeyError, IndexError) as e:
  return f"Ошибка обработки ответа: {e}"


question = "Напиши Python-скрипт для сортировки списка чисел."
answer = ask_deepseek(question)
print("Ответ:", answer)
# def main():
#     print("напиши phyton скрипт :")
#     while True:
# question = input("Вы: ")
# if question.lower() in ['exit', 'quit']:
#     break


