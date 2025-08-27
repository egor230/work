from libs_voice import *
from tkinter import *
from tkinter.ttk import Combobox  # импортируем только то что надо
from tkinter import messagebox
from pynput.keyboard import Key, Controller
from pynput import *
import keyboard as keybord_from # Управление мышью
import undetected_chromedriver as uc

press = '''#!/bin/bash
   xte 'keydown {0}'
   xte 'keyup {0}'
   sleep 0.1    # Небольшая пауза для надёжности
   xte 'keyup {0}'
   exit 0 '''
def prease_on_key(driver, d): #
 timestamp = time.time()
 for key in d:
  word1 = str(d[key])
  words = word1.rsplit(",")
  x = [i.lstrip() for i in words]
 while 1:
  try:
   element = driver.find_element(By.ID, "speech-text")   # Поиск элемента по ID
   text = str(element.text).lower()
   if len(text) != 0 and text != None:  #
    print(text)
    for word1 in x:
     word = str(word1).lower()
     if word == text:
      key = key.replace("KEY", '')
      driver.find_element("id", "mic").click()
      thread0 = threading.Thread(target=lambda: subprocess.call(['bash', '-c', press.format(key)]))
      thread0.daemon
      thread0.start()   # print(key2)
      time.sleep(1.5)
       # driver.find_element("class","p_edit dir_LTR").clear()  # удалить старый текст.
      driver.find_element("id", "mic").click()
      break
   # if time.time() - timestamp > 20:     #   print(time.time())
   #  driver.find_element("id", "mic").click()
   #  time.sleep(3.35)
   #  driver.find_element("id", "mic").click()  #
   #  timestamp = time.time()
  except Exception as ex:
     # print(ex)
     pass

def check(driver):
  url = driver.current_url
  driver.implicitly_wait(3)
  try:
    return 0
  except Exception as ex:
    check(driver)
f = '''#!/bin/bash
     pkill -f "chrome"
     pkill -f "chromedriver" '''
subprocess.call(['bash', '-c', f])#
def web():
  # option = get_option()  # Включить настройки.# option.add_argument("--headless")  # Включение headless-режима
  option = webdriver.ChromeOptions()
  option.add_argument( "user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.168 Safari/537.36")
  option.add_experimental_option("excludeSwitches", ['enable-automation'])  # убрать окно
  option.add_argument("--use-fake-ui-for-media-stream")  # звук
  option.add_argument("--disable-popup-blocking")  # блок всплывающих окон.
  # option.add_argument("--disable-extensions")  # отключить расширения.
  option.add_argument('--disable-web-security')
  option.add_argument('--disable-notifications')
  # - Отключить загрузку картинок:
  option.add_argument("--blink-settings=imagesEnabled=false")
  option.binary_location = "/usr/bin/google-chrome"  # Стандартный путь
  option.add_argument("--no-sandbox")
  option.add_argument("--disable-blink-features=AutomationControlled")
  # option.add_argument("--incognito")
  # for dir_path in ["/tmp/chrome-profile", "/tmp/chrome-cache"]:
  #  if os.path.exists(dir_path):
  #   shutil.rmtree(dir_path, ignore_errors=True)
  # option.add_experimental_option("detach", True)
  # 🧹 Создаём **чистый профиль каждый раз**
  # option.add_argument("--user-data-dir=/tmp/chrome-profile")  # временная папка
  # option.add_argument("--disk-cache-dir=/tmp/chrome-cache")
  # option.add_argument("--profile-directory=Default")
  try:
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),  options=option)  # # driver.set_window_position(600, 650)
    # driver.set_window_size(624, 368) # optiol
    time.sleep(2)
    
    driver.delete_all_cookies()    # Удалить cookies
    # driver.execute_cdp_cmd('Network.clearBrowserCache', {})

    driver.get("https://alice.yandex.ru/")# открыть сайт
    driver.get("https://www.speechtexter.com")# открыть сайт
    #  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),  options=option)
    # check(driver)
    # driver.minimize_window()
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'mic')))
    driver.find_element("id", "mic").click()# включить запись голоса
    html_content = driver.page_source
    with open('page_source.html', 'w', encoding='utf-8') as file:
     file.write(html_content)

    return driver

  except Exception as ex:     #
   print(ex)
   #driver.quit()
   # if "closed connection without response" in ex:
   #     driver.quit()
   pass
   if "code 130" in ex:
       pass
  finally:
   # print(ex)
   # driver.quit()
   pass
# добавление нового элемента
list_profiles = ["default"]  # список профилей.

def start_voice():
 try:
  driver = web()# запуск браузер.
  # print("222222222222222222222222")
  d = {}
  for i in range(len(arg)):
   value = (str(arg[i].get()))
   key = str(values[i].get())
   d[key] = value
   # try:
   #   if key == "":
   #     messagebox.showerror("Erorr", "key emrty")
   #     dict_save.kill_chromedrive_id()  # Убить текущей процесс.
   #     break
   #     return
   #   if value == "":
   #     messagebox.showerror("Erorr", "Value emrty")
   #     dict_save.kill_chromedrive_id()  # Убить текущей процесс.
   #     break
   #     return
   # except Exception as ex:
   #    pass
   app_thread = threading.Thread(target=prease_on_key, args=(driver, d,))
   app_thread.start()
 except Exception as ex:
	 pass

class save_dict:
  def __init__(self):
    self.d = {}
    self.jnson = {}
  def add_dict(self, second_dict):
    self.d= self.d | second_dict
  def return_dict(self):
    return self.d
  
  def save_jnson(self, jn):
   self.jnson= jn
  
  def return_jnson(self):
    return self.jnson

def save_keys_and_values(event=0):
 d,d1={},{}
 d=dict_save.return_jnson()# старый словарь.
 d["last_pfofile"]=str(profile_current.get())
 d["start_startup"]=start_startup.get()
 d1=d["profiles"]
 d=d1[str(profile_current.get())]
 d.clear()
 for i in range(len(arg)):
		key = str(arg[i].get())
		value = str(values[i].get())
		d[key]=value# обновления словаря.
 d1[str(profile_current.get())]=d
def on_close():
    # new_data={"last_pfofile" : profile_current.get(),
    # "profiles" : dict_save.return_dict()} # новые значения настроек.
    # old_data= dict_save.return_jnson()# старые значения настроек.
    # if new_data != old_data:
    #  if messagebox.askokcancel("Quit", "Do you want to save the changes?"):
    #    json_string = json.dumps(new_data, ensure_ascii=False, indent=2)
    #    with open("settings volce game contol for linux.json", "w", encoding="cp1251") as w:
    #     w.write(json_string)# сохранить изменения в файле настроек.
    root.destroy()

# удаления записи и значения.
def remove_box_and_entry(ent_arr, box_arr):
 if len(values)>0:
    r = len(arg)
    values[r-1].set("")
    arg[r-1].set("")
    ent_arr[r-1].destroy()
    box_arr[r-1].destroy()
    ent_arr.pop()
    box_arr.pop()
    values.pop()
    arg.pop()
    return ent_arr, box_arr
 else:
    return ent_arr, box_arr

class iter_counter:
  def __init__(self):
     self._value = -1
     self.box_arr = []
     self.ent_arr = []
  def add_new_command(self, scrollable_frame, entry_value=0, box_value=0):
    self._value += 1
    value= self._value  # print(value)
    a = list(KEYS.keys()), arg.append(StringVar()), values.append(StringVar())
    entry = Entry(scrollable_frame, width=17, textvariable=arg[value])  # текстовое поле и кнопка для добавления в список
    entry.grid(column=0, row=value+1, padx=(3, 0), pady=8)
    box = Combobox(scrollable_frame, width=10, textvariable=values[value], values=a[0])
    box.grid(column=1, row=value+1, padx=38, pady=0)  # поле со списком
    key=str(profile_current.get())
    if entry_value != 0 and box_value != 0:
        arg[value].set(entry_value)
        values[value].set(box_value)
    else:
        arg[value].set("")
        values[value].set("")
    return self.ent_arr.append(entry), self.box_arr.append(box),self._value,
  def del_command(self):
       value = self._value
       ent_arr, box_arr= self.box_arr, self.ent_arr
       ent_arr, box_arr=remove_box_and_entry(ent_arr, box_arr)

       self._value -= 1
       return self._value, self.box_arr, self.ent_arr
  def remove_all_command(self, scrollable_frame):
       self._value=-1
       ent_arr, box_arr, value = self.box_arr, self.ent_arr, self._value
       for i in range(len(box_arr)):
        ent_arr, box_arr = remove_box_and_entry(ent_arr, box_arr)
       new.add_new_command(scrollable_frame)
       return self._value, self.box_arr, self.ent_arr
  def remove_all_command_without_adding(self):
       value = self._value
       ent_arr, box_arr= self.box_arr, self.ent_arr
       for i in range(len(box_arr)):
        ent_arr, box_arr = remove_box_and_entry(ent_arr, box_arr)
       self._value=-1
       return self._value, self.box_arr, self.ent_arr

def filling_fields(dict_save, last_pfofile):
  d=dict_save.return_dict()# получить словарь со всеми значениями.
  for k, v in d.items():
   if k not in list_profiles:
     list_profiles.append(k)
   if k== last_pfofile:
    for k1, v1 in v.items():
     v1=v[k1]
     new.add_new_command(scrollable_frame,k1,v1)

def update(event):
    d=dict_save.return_dict()
    d=d[str(profile_current.get())]
    new.remove_all_command_without_adding()
    filling_fields(dict_save, profile_current.get())
def c(event):
 d=dict_save.return_dict()
 d=d[str(profile_current.get())]
 for i in range(len(arg) - 1):
        key = str(arg[i].get())
        value = str(values[i].get())
        d[key]=value
 d1=dict_save.return_dict()

 d1[str(profile_current.get())]=d
 return 0
def create_box():
    box = Combobox(root, width=10, textvariable=profile_current, values=list_profiles, state='readonly')
    box.grid(column=1, row=0, padx=3, pady=0)  # поле со списком.
    box.bind('<Button-1>', c)  # при нажатии на выпадающий список.
    box.bind('<<ComboboxSelected>>', update)# при изменения профиля.
    return box
def add1(root,window, new, scrollable_frame):
    value= new_profile.get()
    if value != '':
     list_profiles.append(str(value))
     box = Combobox(root, width=10, textvariable=profile_current, values=list_profiles, state='readonly')
     box.bind('<<ComboboxSelected>>', update)
     box.grid(column=1, row=0, padx=3, pady=0)  # поле со списком
     add_button = Button(text="Добавить профиль", command= lambda:add_new_profile(root, box)).grid(column=2, row=0, padx=10, pady=6)
     box.current(len(list_profiles)-1)

     window.destroy()
     new_profile.set('')
     new.remove_all_command(scrollable_frame)

def add_new_profile(root,box,new,scrollable_frame):
    window = Toplevel(root)# основа
    window.title("add new profile")  # заголовок
    window.geometry("500x150+750+400")  # Первые 2 определяют ширину высоту. Пос 2 x и y координаты на экране.
    window.configure(bg='DimGray')  # Цвет фона окна

    e=Entry(window, width=30, textvariable=new_profile) #строка ввода профиля.
    e.grid(column=2, row=0, padx=50, pady=5)
    e.focus_set()
    Button(window, text="Добавить профиль", command= lambda:add1(root,window,new,scrollable_frame))\
        .grid(column=2, row=1, padx=50, pady=30) # кнопка добавить профиль, откроется новое окно.

def start(new, scrollable_frame,box):
  data ="settings_voice_game_control_linux.json"  # файл настроек.
  if os.path.exists(data):  # есть ли этот файл.
    with open(data, encoding='windows-1251') as json_file:
      res= json.load(json_file)
    start_startup.set(res["start_startup"])
    dict_save.save_jnson(res)# соранить начальные настройки.
    last_pfofile = res['last_pfofile'] # последний исполь профиль.
    if not last_pfofile in list_profiles:
     list_profiles.append(last_pfofile)
    box =create_box() # Создания выпадающего списка.
    box.current(len(list_profiles) - 1)
    d=res['profiles']
    dict_save.add_dict(d)
    filling_fields(dict_save, last_pfofile)# запол полей
  else:
     new.add_new_command(scrollable_frame)
def delayed_launch(start_startup):
  if start_startup.get():  # Запуск при открытий.
     start_voice()
dict_save=save_dict()
root = Tk()
root.geometry("680x250+650+400")
profile_current, new_profile=StringVar(),StringVar()

lb = Label(root, text="Голосовое управления в играх",width=28).grid(column=0, row=0)  # текстовое поле и кнопка для добавления в список

arg, values = [], []# списки для слов и значений.

container = Frame(root)
canvas = Canvas(container,width=320, height=200)
scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
scrollable_frame = Frame(canvas)
scrollable_frame.bind( "<Configure>",
    lambda e: canvas.configure( scrollregion=canvas.bbox("all")
    ))
canvas.create_window((0, 0), window=scrollable_frame, anchor="n")
canvas.configure(yscrollcommand=scrollbar.set)
container.grid()
canvas.grid(sticky=N+S)
scrollbar.grid(column=0, row=0,sticky=N+S+E)# полоса прокрутки.

box = create_box() # Создания выпадающего списка.

new=iter_counter()# объект класса.

add_button = Button(text="Добавить профиль", command= lambda:add_new_profile(root, box, new,scrollable_frame))\
    .grid(column=2, row=0, padx=10, pady=6)

add_key_button = Button(text="Добавить команду", command= lambda:new.add_new_command(scrollable_frame))\
    .grid(column=1, row=1, padx=1, pady=30,sticky=N)

del_key_button_1 = Button(text="Удалить команду", command= lambda:new.del_command())\
    .grid(column=1, row=1,padx=1,pady=90,sticky=N)

go_button_2 = Button(text="  Старт  ", command= lambda:start_voice())\
    .grid(column=2, row=1,padx=0,pady=20,sticky=SE)# Запуск управления.
root.protocol("WM_DELETE_WINDOW", on_close)

box.grid(column=1, row=0, padx=3, pady=0)  # поле со списком
start_startup = BooleanVar()
start(new, scrollable_frame,box)# запуск всего.
r1 = Checkbutton(text='Запускать при открытий',  variable=start_startup, command=lambda:save_keys_and_values())

r1.place(x=323, y=190)
t2 = threading.Thread(target=delayed_launch, args=(start_startup,))
t2.start()
root.mainloop()











# else:
    #   keybord_from.press(KEYS[key[number_key]])
# Опустить.
#     release = '''#!/bin/bash
#     xte 'keyup {0}'    '''
#     if key in self.keys_list1:
#      thread = threading.Thread(target=lambda: subprocess.call(['bash', '-c', release.format(key)]))
#      thread.daemon = True  # Установка атрибута daemon в значение True
#      thread.start()   # print(key)     # subprocess.call(['bash', '-c', release.format(key)])
#      return 0
#     key1= key.lower()
#     if key1 in self.keys_list:      # subprocess.call(['bash', '-c', release.format(key1)])
#       thread1 = threading.Thread(target=lambda: subprocess.call(['bash', '-c', release.format(key)]))
#       thread1.daemon = True  # Установка атрибута daemon в значение True
#       thread1.start()
    # else:
    #   keybord_from.release(KEYS[key[number_key]])
# def update(event):
#     # pass
#     print('event.widget.get():')
#     return
# def motion(event):
#  print("Mouse position: ")
#  return
# master = Tk()
# profile_current, new_profile=StringVar(),StringVar()
# list_profiles.append("po")
# box  = Combobox(master, width=12, textvariable=profile_current, values=list_profiles, state='readonly')
# box.bind('<Button-1>',motion)
# box.bind('<<ComboboxSelected>>', update)
# box.grid()
# mainloop()




# def update():
#     print("update")
#
# def gui(root):
#   root.config(background='snow3')
#
#   text = Text(root, height=1, width=10)  # Widget to be updated.
#   text.grid(row=0, column=0)
#
#   combobox = Combobox(root, value=('test'))
#   combobox.grid(row=0, column=1)
#
#   combobox.bind('<<ComboboxSelected>>', lambda event:update())
#
# root = Tk()
# root.geometry("300x150+850+600")
# gui(root)
# root.mainloop()



# root = Tk()
#
# b1 = Button(root, text='b1')
# b1.grid(row=0, column=0, sticky="w")
#
# e1 = Entry(root)
# e1.grid(row=0, column=1, sticky="ew")
#
# t = Treeview(root)
# t.grid(row=1, column=0, columnspan=2, sticky="nsew") # columnspan=2 goes here.
#
# scroll = Scrollbar(root)
# scroll.grid(row=1, column=2, sticky="nse") # set this to column=2 so it sits in the correct spot.
#
# scroll.configure(command=t.yview)
# t.configure(yscrollcommand=scroll.set)
#
# root.columnconfigure(0, weight=1) Removing this line fixes the sizing issue with the entry field.
# root.columnconfigure(1, weight=1)
# root.rowconfigure(1, weight=1)
#
# root.mainloop()
#

#
# root = Tk()
# container = Frame(root)
# canvas = Canvas(container)
# scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
# scrollable_frame = Frame(canvas)
#
# scrollable_frame.bind( "<Configure>",
#     lambda e: canvas.configure( scrollregion=canvas.bbox("all")
#     ))
# canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
# canvas.configure(yscrollcommand=scrollbar.set)
#
# Label(scrollable_frame, text="Голосовое управления в играх",width=35).grid(column=0, row=0)
#     # Label(scrollable_frame, text="Sample scrolling label").pack()
#
# container.pack()
# canvas.pack(side="left", fill="both", expand=True)
# scrollbar.pack(side="right", fill="y")
#
# root.mainloop()



# scrollbar1 = Scrollbar(frame,orient="vertical")
# scrollbar1.pack( side = RIGHT, fill = Y )
# scrollbar1.grid(column=1, row=2 )


# def data():
#     for i in range(50):
#        Label(frame,text=i).grid(row=i,column=0)
#        Label(frame,text="my text"+str(i)).grid(row=i,column=1)
#        Label(frame,text="..........").grid(row=i,column=2)
def myfunction(event):
    pass
    # canvas.configure(scrollregion=canvas.bbox("all"),width=200,height=200)
# root=Tk()
# sizex = 800
# sizey = 600
# posx  = 100
# posy  = 100
# container = Frame(root)
# canvas = Canvas(container)
# scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
# scrollable_frame = Frame(canvas)
# root.mainloop()

# root=Tk()
# root.wm_geometry("%dx%d+%d+%d" % (sizex, sizey, posx, posy))
# myframe=Frame(root,relief=GROOVE,width=50,height=100,bd=1)
# myframe.place(x=10,y=10)
# canvas=Canvas(myframe)
# frame=Frame(canvas)
# myscrollbar=Scrollbar(myframe,orient="vertical",command=canvas.yview)
# canvas.configure(yscrollcommand=myscrollbar.set)
# myscrollbar.pack(side="right",fill="y")
# canvas.pack(side="left")
# canvas.create_window((0,0),window=frame,anchor='nw')
# frame.bind("<Configure>",myfunction)
# data()
# root.mainloop()


# top1= Tk()
# CheckVar11 = IntVar()





# master1 = Tk()
# scrollbar1 = Scrollbar(master1, bg="green")
# scrollbar1.pack( side = RIGHT, fill = Y )
# pavanlist1 = Listbox(master1, yscrollcommand = scrollbar1.set )
# mainloop()
# top1.mainloop()
# delete_button = Button(text="Удалить", command=delete).grid(row=2, column=1, padx=5, pady=5)
# удаление выделенного элемента
# def delete():
    # selection = languages_listbox.curselection()
    # мы можем получить удаляемый элемент по индексу
    # selected_language = languages_listbox.get(selection[0])
    # languages_listbox.delete(selection[0])

# languages_listbox.insert(0, new_language)
# languages_listbox = Listbox() # создаем список
# languages_listbox.grid(row=1, column=0, columnspan=2, sticky=W + E, padx=5, pady=5)
#
# languages_listbox.insert(END, "Python")
# languages_listbox.insert(END, "C#")# добавляем в список начальные элементы







# root = Tk()
# # root.option_readfile('optionDB')
# root.title('Toplevel')
# Label(root, text='This is the main (default) Toplevel').pack(pady=10)
# t1 = Toplevel(root)
# Label(t1, text='This is a child of root').pack(padx=10, pady=10)
# t2 = Toplevel(root)
# Label(t2, text='This is a transient window of root').pack(padx=10, pady=10)
# t2.transient(root)
# t3 = Toplevel(root, borderwidth=5, bg='blue')
# Label(t3, text='No wm decorations', bg='blue', fg='white').pack(padx=10, pady=10)
# t3.overrideredirect(1)
# t3.geometry('200x70+150+150')
# root.mainloop()



# root = Tk()
# Label(root, text="You shot him!").pack(pady=10)
# Button(root, text="He's dead!", state=DISABLED).pack(side=LEFT)
# Button(root, text="He's completely dead!",
# command=root.quit).pack(side=RIGHT)
#
# root.mainloop()


# root = Tk()
# Label(root, text="Anagram:").pack(side=LEFT, padx=5, pady=10)
# e = StringVar()
# Entry(root, width=40, textvariable=e).pack(side=LEFT)
# e.set("'A shroe! A shroe! My dingkom for a shroe!'")
#
# root.mainloop()


# root = Tk()
# var = IntVar()
# for text, value in [('Passion fruit', 1), ('Loganberries', 2),
# ('Mangoes in syrup', 3), ('Oranges', 4),
# ('Apples', 5),('Grapefruit', 6)]:
#
#    Radiobutton(root, text=text, value=value, variable=var).pack(anchor=W)
#    var.set(3)
#
# root.mainloop()


# root = Tk()
# var = IntVar()
# for text, value in [('Red Leicester', 1), ('Tilsit', 2), ('Caerphilly', 3),
#  ('Stilton', 4), ('Emental', 5),
#  ('Roquefort', 6), ('Brie', 7)]:
#  Radiobutton(root, text=text, value=value, variable=var,
# indicatoron=0).pack(anchor=W, fill=X, ipadx=18)
# var.set(3)
#
# root.mainloop()


# root = Tk()
# # var=[]
# for var, castmember, row, col, status in [
# ('John Cleese', 0,0,NORMAL), ('Eric Idle', 0,1,NORMAL),
# ('Graham Chapman', 1,0,DISABLED), ('Terry Jones', 1,1,NORMAL),
# ('Michael Palin',2,0,NORMAL), ('Terry Gilliam', 2,1,NORMAL)]:
#  setattr(var, castmember, IntVar())
#  Checkbutton(root, text=castmember, state=status, anchor=W, variable = getattr(var, castmember)).grid(row=row, col=col, sticky=W)

# root.mainloop()


# root = Tk()
# list = Listbox(root, height=6, width=15)
# scroll = Scrollbar(root, command=list.yview)
# list.configure(yscrollcommand=scroll.set)
# list.pack(side=LEFT)
# scroll.pack(side=RIGHT, fill=Y)
# for item in range(5):
#  list.insert(END, item)
#
# root.mainloop()



# root = Tk()
# def setHeight(canvas, heightStr):
#     height = string.atoi(heightStr)
#     height = height + 21
#     y2 = height - 30
#     if y2 < 21:
#      y2 = 21
#     canvas.coords('poly',
#     15,20,35,20,35,y2,45,y2,25,height,5,y2,15,y2,15,20)
#
#     canvas.coords('line',
#     15,20,35,20,35,y2,45,y2,25,height,5,y2,15,y2,15,20)
# canvas = Canvas(root, width=50, height=50, bd=0, highlightthickness=0)
# canvas.create_polygon(0,0,1,1,2,2, fill='cadetblue', tags='poly')
# canvas.create_line(0,0,1,1,2,2,0,0, fill='black', tags='line')
# scale = Scale(root, orient=VERTICAL, length=284, from_=0, to=250,
# tickinterval=50, command=lambda h, c=canvas:setHeight(c,h))
# scale.grid(row=0, column=0, sticky='NE')
# canvas.grid(row=0, column=1, sticky='NWSE')
# scale.set(100)
#
# root.mainloop()


# root = Tk()
# root.option_readfile('optionDB')
# Pmw.initialise()
# Pmw.aboutversion('1.5')
# Pmw.aboutcopyright('Copyright Company Name 1999\nAll rights reserved')
# Pmw.aboutcontact(
#     'For information about this application contact:\n' +
#     '  Sales at Company Name\n' +
#     '  Phone: (401) 555-1212\n' +
#     '  email: info@company_name.com'
#     )
# about = Pmw.AboutDialog(root, applicationname='About Dialog')
#
# root.mainloop()



# root = Tk()
# balloon = Pmw.Balloon(root)
# frame = Frame(root)
# frame.pack(padx = 10, pady = 5)
# field = Pmw.EntryField(frame, labelpos=W, label_text='Name:')
# field.setentry('A.N. Other')
# field.pack(side=LEFT, padx = 10)
# balloon.bind(field, 'Your name', 'Enter your name')
# check = Button(frame, text='Check')
# check.pack(side=LEFT, padx=10)
# balloon.bind(check, 'Look up', 'Check if name is in the database')
# frame.pack()
# messageBar = Pmw.MessageBar(root, entry_width=40,
#                             entry_relief=GROOVE,
#                             labelpos=W, label_text='Status:')
# messageBar.pack(fill=X, expand=1, padx=10, pady=5)
# balloon.configure(statuscommand = messageBar.helpmessage)
#
# root.mainloop()



# root = Tk()
# def buttonPress(btn):
#   print('The "%s" button was pressed' % btn)
# def defaultKey(event):
#   buttonBox.invoke()
# buttonBox = Pmw.ButtonBox(root, labelpos='nw', label_text='ButtonBox:')
# buttonBox.pack(fill=BOTH, expand=1, padx=10, pady=10)
# buttonBox.add('OK',     command = lambda b='ok':     buttonPress(b))
# buttonBox.add('Cancel', command = lambda b='cancel': buttonPress(b))
# buttonBox.add('Apply',  command = lambda b='apply':  buttonPress(b))
# buttonBox.setdefault('Apply')
# root.bind('<Return>', defaultKey)
# root.focus_set()
# buttonBox.alignbuttons()
#
# root.mainloop()


# root = Tk()
# choice = None
# def choseEntry(entry):
#     print('You chose "%s"' % entry)
#     choice.configure(text=entry)
#
# asply = ("The Mating of the Wersh", "Two Netlemeng of Verona", "Twelfth Thing",
#  "The Chamrent of Venice", "Thamle", "Ring Kichard the Thrid")
#
# choice = None
#
# def choseEntry(entry):
#     print('You chose "%s"' % entry)
#     choice.configure(text=entry)
#
# asply = ("A", "B", "C", "D", "E", "F")
#
# root = Tk() #root.option_readfile('optionDB')
# root.title('ComboBox 2')
# Pmw.initialise()
# choice = Label(root, text='Choose play', relief=SUNKEN, padx=20, pady=20)
# choice.pack(expand=1, fill=BOTH, padx=8, pady=8)
# combobox = Pmw.ComboBox(root, label_text='Play:', labelpos='wn',
#  listbox_width=24, dropdown=1, selectioncommand=choseEntry, scrolledlist_items=asply)
# combobox.pack(fill=BOTH, expand=1, padx=8, pady=8)
#
# combobox.selectitem(asply[0])
#
# root.mainloop()


# def add_item():
#     box.insert(END, entry.get())
#     entry.delete(0, END)
#
# def del_list():
#     select = list(box.curselection())
#     select.reverse()
#     for i in select:
#         box.delete(i)
#
# def save_list():
#     f = open('list000.txt', 'w')
#     f.writelines("\n".join(box.get(0, END)))
#     f.close()
#
# root = Tk()
#
# box = Listbox(selectmode=EXTENDED)
# box.pack(side=LEFT)
# scroll = Scrollbar(command=box.yview)
# scroll.pack(side=LEFT, fill=Y)
# box.config(yscrollcommand=scroll.set)
#
# f = Frame()
# f.pack(side=LEFT, padx=10)
# entry = Entry(f)
# entry.pack(anchor=N)
# Button(f, text="Add", command=add_item).pack(fill=X)
# Button(f, text="Delete", command=del_list).pack(fill=X)
# Button(f, text="Save", command=save_list).pack(fill=X)
#
# root.mainloop()


# root = Tk()

# languages = ["Python", "JavaScript", "C#", "Java", "C/C++", "Swift",
#              "PHP", "Visual Basic.NET", "F#", "Ruby", "Rust", "R", "Go",
#              "T-SQL", "PL-SQL", "Typescript"]
#
# root = Tk()
# root.title("GUI на Python")
#
# scrollbar = Scrollbar(root)
# scrollbar.pack(side=RIGHT, fill=Y)
#
# languages_listbox = Listbox(yscrollcommand=scrollbar.set, width=40)
#
# for language in languages:
#     languages_listbox.insert(END, language)
#
# languages_listbox.pack(side=LEFT, fill=BOTH)
# scrollbar.config(command=languages_listbox.yview)
#
# root.mainloop()






# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()

# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()


# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()



# root = Tk()


# root.mainloop()
