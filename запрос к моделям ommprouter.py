import urllib.request
import urllib.error
import json
import os

hf_token = os.environ.get("HF_TOKEN", "")

# Список популярных моделей для проверки
top_models = [
 "Qwen/Qwen2.5-Coder-32B-Instruct",
 "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
 "mistralai/Mistral-7B-Instruct-v0.3",
 "meta-llama/Llama-3.1-8B-Instruct"
]


def send_prompt(model_name, prompt):
 # Актуальный эндпоинт Hugging Face Router
 url = f"https://router.huggingface.co/hf-inference/v1/chat/completions"
 
 payload = {
  "model": model_name,
  "messages": [
   {"role": "user", "content": prompt}
  ],
  "max_tokens": 150
 }
 
 data = json.dumps(payload).encode("utf-8")
 headers = {
  "Authorization": f"Bearer {hf_token}",
  "Content-Type": "application/json"
 }
 
 req = urllib.request.Request(url, data=data, headers=headers)
 
 try:
  with urllib.request.urlopen(req, timeout=30) as response:
   if response.status == 200:
    res = json.loads(response.read().decode())
    return True, res["choices"][0]["message"]["content"]
 except urllib.error.HTTPError as e:
  err_msg = e.read().decode()
  return False, f"HTTP Error {e.code}: {err_msg}"
 except Exception as e:
  return False, f"Error: {str(e)}"


def main():
 prompt = "Привет! Ответь одним предложением: кто ты?"
 print("Проверяем доступность моделей через Router API:\n")
 
 for model in top_models:
  print(f"Тестируем: {model}")
  ok, result = send_prompt(model, prompt)
  if ok:
   print(f"\nУспешный ответ от модели [{model}]:\n{result}\n")
   break
  else:
   print(f"Причина неудачи: {result}\n")


if __name__ == "__main__":
 main()