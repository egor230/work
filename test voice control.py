import time, threading, subprocess

press = '''#!/bin/bash
   xte 'keydown {0}'
   xte 'keyup {0}'
   sleep 0.1    # Небольшая пауза для надёжности
   xte 'keyup {0}'
   exit 0 '''
def prease_on_key(d): #
 timestamp = time.time()
 for key in d:
  word1 = str(d[key])
  words = word1.rsplit(",")
  x = [i.lstrip() for i in words]
 # while 1:
  try:
   text = "1"
   text = str(text).lower()
   if len(text) != 0 and text != None:   #     print(text)
     for word1 in x:
      word= str(word1).lower()
      if word == text:
       key=key.replace("KEY",'')
       thread0 = threading.Thread(target=lambda: subprocess.call(['bash', '-c', press.format(key)]))
       thread0.daemon
       thread0.start()
       time.sleep(3.5)
       # key2=str(KEYS[key1]).lower()
       # driver.find_element("id", "mic").click()

       # driver.find_element("class","p_edit dir_LTR").clear()  # удалить старый текст.
       # driver.find_element("id", "mic").click()
       break
   if time.time() - timestamp > 20:     #   print(time.time())
    # driver.find_element("id", "mic").click()
    # time.sleep(3.35)
    # driver.find_element("id", "mic").click()  #
    timestamp = time.time()
  except Exception as ex:
     # print(ex)
     pass

d={'KEY1': 'один, день, 1, день, один один', 'KEY2': '2,два', 'KEY3': 'три, тариф, да не, ты, 3, тори, скажи, да и', 'E': 'е, ее, я, е е', 'C': 'с, сидеть, сесть', 'R': 'к, ка, как', 'F': 'а', 'G': 'г', 'key4': 'сергеем, ситилинк, двойка, цветы, сергей, теперь, Seti.ee, 4', 'F5': 'сейф, сейф сейф', 'F8': 'да, давай'
   }
time.sleep(6)
print("00000")
prease_on_key(d)