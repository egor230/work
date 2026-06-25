import time, subprocess, xerox, pyperclip, clipboard
class save_word:
   def __init__(self):
     self.key = None
   def save_b(self, key1):
     text= ("помоги ответить на это сообщение как-то по-доброму, обращайся в своём ответе только на Вы, "
           "очень вежливо, Пожалуйста, напишите ответ на следующее сообщение, используя только "
            "вежливую форму обращения на вы и соблюдая все правила этикета: Исключи заезженные фразы, "
            "которые делают текст роботизированным или слишком вычурным. Не используйте кавычки, "
            "в целом и я, используй вместо слова символ слово знак  в итоговом варианте. \" {0} \"").format(key1)
     self.key =text

   def return_word(self):
      return self.key
cli= save_word()

# Команды для bash
show_list_id = f'''#!/bin/bash  
copyq delete 0  # Удаляем первый элемент из истории
sleep 1
copyq select 0  # Выбираем первый элемент
'''

def check_clipboard():

  clipboard_text = pyperclip.paste()
  cli.save_b(clipboard_text)
  text= cli.return_word()
  pyperclip.copy(text)
  print("copy")


check_clipboard()

# pyperclip.paste()#
# print(clipboard_text){}{}