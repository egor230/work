from llama_cpp import Llama
import contextlib, os, sys

# Путь к модели
# model_path = "/mnt/807EB5FA7EB5E954/Program Files/ai models/hugging-quants/Llama-3.2-1B-Instruct-Q8_0-GGUF/llama-3.2-1b-instruct-q8_0.gguf"
model_path = "/mnt/807EB5FA7EB5E954/Program Files/ai models/lmstudio-community/WizardLM/wizardlm-7b-uncensored-q4_0.gguf"

# Функция для подавления вывода
@contextlib.contextmanager
def suppress_output():
 with open(os.devnull, 'w') as devnull:
  old_stderr = sys.stderr
  sys.stderr = devnull
  try:
      yield
  finally:
      sys.stderr = old_stderr

# Загрузка модели с оптимальными параметрами
with suppress_output():
 llm = Llama(model_path=model_path,  n_ctx=2048,       # Размер контекста
   n_threads=12,      # Количество потоков (подставьте количество Ваших физических ядер)
   n_batch=512,      # Размер пакета
   verbose=False )# Отключение подробного вывода для ускорения

# Функция для генерации ответа
def generate_response(prompt):
 output = llm(  prompt,  max_tokens=512,   # Максимальное количество токенов в ответе
   temperature=0.8,  # Температура для креативности
   top_p=0.9,        # Параметр для nucleus sampling
   echo=False    )    # Не повторять промпт в ответе
 return output['choices'][0]['text'].strip().replace("`","")

# Основной цикл для взаимодействия с пользователем
user_input = "ты можешь написать простой питон скрипт"
response = generate_response(user_input)
print("Ответ:", response)
# On Windows with a RTX3080, about 20 tokens per second.

# from ctransformers import AutoModelForCausalLM
#
# # initialize model
# llm = AutoModelForCausalLM.from_pretrained(
#  "TheBloke/WizardLM-7B-uncensored-GGUF",
#  model_file=model_path,
#  model_type="llama",
#  gpu_layers=12,
#  max_new_tokens=512,
#  context_length=100)
#
#
# def generate_and_print(llm, tokens):
#  try:
#   for token in llm.generate(tokens):
#    print(llm.detokenize(token), end='', flush=True)
#  except KeyboardInterrupt:
#   print("\nOutput interrupted by user. Enter a new prompt.")
#   return
#
#
# while True:
#  try:
#   user_input = input("\nEnter your prompt (ctrl-c to exit) : ")
#   if user_input.lower() == 'exit':
#    break
#
#   tokens = llm.tokenize(user_input)
#   generate_and_print(llm, tokens)
#  except KeyboardInterrupt:
#   print("\nProgram interrupted by user. Exiting...")
