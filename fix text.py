from llama_cpp import Llama
import sys, os, logging
logging.basicConfig(level=logging.ERROR)  # Показывать только ошибки

# Перенаправление stdout в файл
sys.stdout = open(os.devnull, 'w')
# Путь к модели GGUF
model_path = "/mnt/807EB5FA7EB5E954/Program Files/ai models/hugging-quants/Llama-3.2-1B-Instruct-Q8_0-GGUF/llama-3.2-1b-instruct-q8_0.gguf"

# Загрузка модели# Загрузка модели
llm = Llama(model_path=model_path, device="cpu", n_n_ctx=8192, threads=16, verbose=False) # Укажите количество потоков процессора

# Пример запроса к модели
prompt = ("Пиши как психолог по семейным отношениям, у тебя многолетний опыт работы, у тебя очень хорошая убедительная речь, ты можешь использовать любые приемы для убеждения Не используйте кавычки, "
          "в целом и я, используй вместо слова символ слово знак в итоговом варианте. Пиши свой ответ только на русском языке \""
          " всё это  говорит о том что помимо Вашей основной деятельности Вас может заинтересовать новые направления куда Вы можете вкладывать свои ресурсы а но может у Вас предоставлять Вам возможности  но пока это не заменить основную девственность")
response = llm(prompt=prompt, max_tokens=8192, temperature=0.1)

# Восстановление stdout
sys.stdout = sys.__stdout__
# Вывод ответа
print("Ответ от модели:")
print(response["choices"][0]["text"].strip())
