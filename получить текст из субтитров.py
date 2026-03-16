import os, re, nltk, pyperclip, clipboard, requests
from nltk.tokenize import sent_tokenize, word_tokenize
from translate import Translator
from pytube import YouTube
from itertools import zip_longest
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter

def remove_duplicates(text):
  text =text.replace("[музыка]", "").replace("[аплодисменты]", "")
  lines = text.split("\n")
  result_lines = []
  prev_line = None

  for line in lines:    # Пропускаем пустые строки
    if line == '':
      continue    # Проверяем на дубликаты непустых строк
    if line != prev_line:
      result_lines.append(line)
      prev_line = line
  # print(result_lines)    # input()
  return " ".join(result_lines)

def get_subtitles(video_url, target_lang='ru'):
  try:
   yt = YouTube(video_url)        # Попробуем получить субтитры на русском языке
   caption = yt.captions.get(target_lang)
   if not caption:
    # Если русские субтитры недоступны, попробуем получить английские субтитры
    caption = yt.captions.get('a.en')
    if caption:
      subtitle_text = caption.generate_srt_captions()
      # Переводим субтитры на русский язык
      translator = Translator()
      translated = translator.translate(subtitle_text, src='en', dest='ru')
      subtitle_text = translated.text
      return subtitle_text
    else:
      print("No subtitles available.")
      return None
   else:
      subtitle_text = caption.generate_srt_captions()
      return subtitle_text
  except Exception as e:
   print(f"An error occurred: {e}")
   return None
  

def get_youtube_subtitles(video_id, lang='ru'):
  try:
    # Получаем субтитры на указанном языке
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    transcript = transcript_list.find_manually_created_transcript([lang])
  except Exception:
    try:
      # Если не удалось найти, получаем автоматически сгенерированные субтитры
      transcript = transcript_list.find_generated_transcript([lang])
    except Exception:
      try:
        # Если не удалось найти на указанном языке, ищем английские субтитры
        transcript = transcript_list.find_generated_transcript(['en'])
      except Exception as e:
        print("No subtitles available.")
        return None

  # Форматируем субтитры в формат SRT
  formatter = SRTFormatter()
  srt_subtitles = formatter.format_transcript(transcript.fetch())

  return srt_subtitles

def clean_subtitles(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Регулярное выражение для удаления временных меток
    clean_content = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}.*?\n', '', content)
    # Регулярное выражение для удаления дублированных предложений и тегов

    clean_content = re.sub(r'</c>', '', clean_content)

    clean_content1 = remove_duplicates(clean_content)
    pattern = r'\b\d{2}:\d{2}:\d{2}\b'
    # Удаляем все совпадения
    cleaned_text = re.sub(pattern, '', clean_content1)
    return cleaned_text


def get_video_subtitle_file_path(file_path):
  response = requests.get(file_path)
  html_content = response.text

  # Используем регулярное выражение для извлечения названия видео
  title_pattern = r'<title>(.+?)</title>'
  match = re.search(title_pattern, html_content)
  if match:
    video_title = match.group(1)
    # Удаляем &quot; и заменяем его на кавычки
    video_title = video_title.replace("&quot;", '"')
    # Удаляем - YouTube в конце строки
    video_title = re.sub(r'\s+-\s+YouTube$', '', video_title)
    subtitles = video_title.replace("\"", "") + ".txt"

    current_dir = os.getcwd()
    subtitles = current_dir + "/" + subtitles
    return subtitles
# Путь к файлу субтитров
# file_path = '/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/Хронология Splinter Cell.srt'
file_path = str(pyperclip.paste())
if ".srt" in file_path:
  print(file_path)
  # Путь должен быть корректным и файл должен существовать
  clean_text =  str(clean_subtitles(file_path))
  words = clean_text.split()

  # Объединяем слова в группы по 30
  group_size = 50
  groups = list(zip_longest(*[iter(words)] * group_size, fillvalue=''))

  # Добавляем три переноса строки после каждой группы
  clean_text = '\n\n\n'.join(' '.join(group) for group in groups)
  # Сохранение субтитров в файл
  base = os.path.splitext(file_path)[0]
  # Формируем новый путь с расширением .txt
  new_file_path = base + '.txt'
  # Переименовываем файл
  with open(new_file_path, "w", encoding="utf-8") as file:
    file.write(clean_text)

    # clean_text = "\" поставить знаки препинания также нужно разбить на абзацы в этом тексте \""+clean_text+"\""
    # pyperclip.copy(clean_text)

    # path = get_video_subtitle_file_path(file_path)
    # print(path)
  print(clean_text)
# # else:
#   file_path="https://www.youtube.com/watch?v=anyy0ZZVl3I"
#   # print(file_path)
#   text = get_subtitles(file_path)
#   print(text)
  # subtitles =  get_video_subtitle_file_path(file_path)
  # print(subtitles)

    # Сохранение субтитров в файл
    # with open("subtitles.txt", "w", encoding="utf-8") as file:
    #   file.write(response.text)
