import time, subprocess, xerox, pyperclip, clipboard
class save_word:
   def __init__(self):
     self.key = None
   def save_b(self, key1):
     # text= ("помоги мне написать промт который тебе поможет стать специалистом по копирайтингу: "
     #        "мне нужно перефразировать это текст Но он должен быть максимально похож "
     #        "на оригинал по своему стилю и по смыслу \" {0} \"").format(key1)
     text= ("Прошу Вас внимательно прочитать предоставленный текст на русском языке и исправить "
            "все имеющиеся орфографические и пунктуационные ошибки. Цель состоит в том, чтобы текст"
            " был написан грамотно и соответствовал нормам современного русского литературного языка. "
            "Пожалуйста, продемонстрируйте изменения, сделанные в тексте, чтобы было видно, что было исправлено."
            " Спасибо за помощь. \" {0} \"").format(key1)
     self.key =text

   def return_word(self):
      return self.key
cli= save_word()
def check_clipboard():

  clipboard_text = pyperclip.paste()
  cli.save_b(clipboard_text)
  text= cli.return_word()
  pyperclip.copy(text)
  # subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE).communicate(text.encode())
  print("copy")


check_clipboard()

# print(clipboard_text)
# subprocess.check_output(['xclip', '-selection', 'clipboard', '-o'])
# pyperclip.paste()#
# print(clipboard_text)