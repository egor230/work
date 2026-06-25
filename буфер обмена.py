import time, subprocess
script = f'''#!/bin/bash
first_item=$(copyq read 0);
copyq copy "$(copyq read 0)";
# copyq read | xclip -sel clip
exit;
'''
subprocess.call(['bash', '-c', script, '_'])
script1 = '''#!/bin/bash
# Получить текущее содержимое буфера обмена
clipboard_content=$(copyq clipboard)

# Проверить, пуст ли буфер обмена
if [ -z "$clipboard_content" ]; then
    echo "Буфер обмена пуст"
    exit 0
else
    echo "Буфер обмена содержит: $clipboard_content"
    exit 1
fi
'''
result = str(subprocess.run(['bash'], input=script1, stdout=subprocess.PIPE, text=True).stdout)
def check_clipboard():
 while 1:
  try:
    time.sleep(0.5)    # Получить текст из буфера обмена
    res = str(subprocess.run(['bash'], input=script1, stdout=subprocess.PIPE, text=True).stdout)
    if "Буфер обмена пуст" in res:
      # print("Буфер обмена обновлен")
      subprocess.call(['bash', '-c', script, '_'])
    else:
      print("Буфер полен")
    
  except :
    continue
    # print("Ошибка при получении содержимого буфера обмена")


check_clipboard()






class save_word:
   def __init__(self):
     self.key = None
   def save_b(self, key1):
      self.key =key1

   def return_word(self):
      return self.key
cli= save_word()
import xerox

#
# clipboard_text = xerox.paste()
# text = cli.return_word()
#
# # Отправить текст в буфер обмена
# xerox.copy(text)
# pyperclip.copy(cli.return_word())
#
#   print("Буфер обмена содержит текст:", clipboard_text)
# if clipboard_text != "" and clipboard_text != cli.return_word():
#   cli.save_b(clipboard_text)
#   xerox.copy(clipboard_text)
#   print("copy")
# print(clipboard_text)
# subprocess.check_output(['xclip', '-selection', 'clipboard', '-o'])
# pyperclip.paste()#
# print(clipboard_text)