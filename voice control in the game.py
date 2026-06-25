from tkinter import *
from tkinter.ttk import Combobox  # импортируем только то что надо
from tkinter import messagebox
import json, os, time, keyboard
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from threading import *
import pydirectinput as pyinput
from pynput.keyboard import Key, Controller
from pynput import *


def on_release(key):
  if key == keyboard.Key.shift_l:
      keyb = Controller()
      keyb.press(Key.shift)  # отпустить клавишу
      return False
  if key == keyboard.Key.ctrl_r:
      keyb = Controller()
      keyb.press(Key.ctrl_l)  # отпустить клавишу
      return False
  if key != keyboard.Key.shift_r and key != keyboard.Key.ctrl and key != keyboard.Key.up \
          and key != keyboard.Key.down and key != keyboard.Key.left and key != keyboard.Key.right:
      keyb = Controller()
      keyb.release(Key.shift)
      keyb.release(Key.ctrl_l)
      return False

KEYS = {"LBUTTON": 0x01, "RBUTTON": 0x02, "CANCEL": 0x03, "MBUTTON": 0x04, "XBUTTON1": 0x05,
              "XBUTTON2": 0x06, "BACK": 0x08, "TAB": 0x09, "CLEAR": 0x0C, "RETURN": 0x0D,
              "SHIFT": 0x10, "CONTROL": 0x11, "MENU": 0x12, "PAUSE": 0x13, "CAPITAL": 0x14,
              "KANA": 0x15, "JUNJA": 0x17, "FINAL": 0x18, "KANJI": 0x19, "ESCAPE": 0x1B,
              "CONVERT": 0x1C, "NONCONVERT": 0x1D, "ACCEPT": 0x1E, "MODECHANGE": 0x1F, "SPACE": 0x20,
              "PRIOR": 0x21, "NEXT": 0x22, "END": 0x23, "HOME": 0x24, "LEFT": 0x25, "UP": 0x26,
              "RIGHT": 0x27, "DOWN": 0x28, "SELECT": 0x29, "PRINT": 0x2A, "EXECUTE": 0x2B,
              "SNAPSHOT": 0x2C, "INSERT": 0x2D, "DELETE": 0x2E, "HELP": 0x2F, "KEY0": 0x30,
              "KEY1": 0x31, "KEY2": 0x32, "key3": 0x33, "key4": 0x34, "key5": 0x35, "key6": 0x36,
              "key7": 0x37, "key8": 0x38, "key9": 0x39, "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44,
              "E": 0x45, "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49,
              "J": 0x4A, "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E, "O": 0x4F, "P": 0x50, "Q": 0x51, "R": 0x52,
              "S": 0x53, "T": 0x54, "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59,
              "Z": 0x5A, "LWIN": 0x5B, "RWIN": 0x5C, "APPS": 0x5D, "SLEEP": 0x5F, "NUMPAD0": 0x60, "NUMPAD1": 0x61,
              "NUMPAD2": 0x62, "NUMPAD3": 0x63, "NUMPAD4": 0x64, "NUMPAD5": 0x65,
              "NUMPAD6": 0x66, "NUMPAD7": 0x67, "NUMPAD8": 0x68, "NUMPAD9": 0x69, "MULTIPLY": 0x6A, "ADD": 0x6B,
              "SEPARATOR": 0x6C, "SUBTRACT": 0x6D, "DECIMAL": 0x6E, "DIVIDE": 0x6F, "F1": 0x70, "F2": 0x71,
              "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
              "F11": 0x7A, "F12": 0x7B, "F13": 0x7C, "F14": 0x7D,
              "F15": 0x7E, "F16": 0x7F, "F17": 0x80, "F18": 0x81, "F19": 0x82, "F20": 0x83, "F21": 0x84,
              "F22": 0x85, "F23": 0x86, "F24": 0x87, "NUMLOCK": 0x90, "SCROLL": 0x91, "OEM_FJ_JISHO": 0x92, "OEM_FJ_MASSHOU": 0x93,
              "OEM_FJ_TOUROKU": 0x94, "OEM_FJ_LOYA": 0x95, "OEM_FJ_ROYA": 0x96, "LSHIFT": 0xA0, "RSHIFT": 0xA1, "LCONTROL": 0xA2, "RCONTROL": 0xA3, "LMENU": 0xA4, "RMENU": 0xA5, "BROWSER_BACK": 0xA6,
              "BROWSER_FORWARD": 0xA7, "BROWSER_REFRESH": 0xA8, "BROWSER_STOP": 0xA9, "BROWSER_SEARCH": 0xAA, "BROWSER_FAVORITES": 0xAB, "BROWSER_HOME": 0xAC, "VOLUME_MUTE": 0xAD, "VOLUME_DOWN": 0xAE,
              "VOLUME_UP": 0xAF, "MEDIA_NEXT_TRACK": 0xB0, "MEDIA_PREV_TRACK": 0xB1, "MEDIA_STOP": 0xB2, "MEDIA_PLAY_PAUSE": 0xB3, "LAUNCH_MAIL": 0xB4, "LAUNCH_MEDIA_SELECT": 0xB5, "LAUNCH_APP1": 0xB6,
              "LAUNCH_APP2": 0xB7, "OEM_1": 0xBA, "OEM_PLUS": 0xBB, "OEM_COMMA": 0xBC, "OEM_MINUS": 0xBD, "OEM_PERIOD": 0xBE, " OEM_2": 0xBF, "OEM_3": 0xC0, "ABNT_C1": 0xC1, "ABNT_C2": 0xC2, "OEM_4": 0xDB, "OEM_5": 0xDC, "OEM_6": 0xDD, "OEM_7": 0xDE, "OEM_8": 0xDF, "OEM_AX": 0xE1,
              "OEM_102": 0xE2, "ICO_HELP": 0xE3, "PROCESSKEY": 0xE5, "ICO_CLEAR": 0xE6, "PACKET": 0xE7, "OEM_RESET": 0xE9, "OEM_JUMP": 0xEA, "OEM_PA1": 0xEB, "OEM_PA2": 0xEC, "OEM_PA3": 0xED,
              "OEM_WSCTRL": 0xEE, "OEM_CUSEL": 0xEF, "OEM_ATTN": 0xF0, "OEM_FINISH": 0xF1, "OEM_COPY": 0xF2, "OEM_AUTO": 0xF3, "OEM_ENLW": 0xF4, "OEM_BACKTAB": 0xF5, "ATTN": 0xF6, "CRSEL": 0xF7, "EXSEL": 0xF8, " EREOF": 0xF9, "PLAY": 0xFA, "ZOOM": 0xFB, "PA1": 0xFD, " OEM_CLEAR": 0xFE
              }

def check(driver):
  url = driver.current_url
  driver.implicitly_wait(3)
  try:
    return 0
  except Exception as ex:
    check(driver)
def prease_on_key(driver, key, *words):
 words=words[0]
 while 1:
  try:
   time.sleep(0.5)
   driver.find_element_by_xpath('//*[@class="p_edit dir_LTR"]').clear()  # удалить старый текст.
   text= driver.find_element_by_xpath('//*[@id="speech-display"]').text
   if len(text) != 0 and text != None:
     text = str(text).lower()
     for word1 in words:
      word= str(word1).lower()
      if word == text:
        key1=key.upper()
        key2=KEYS[key1]
        driver.find_element_by_xpath('//*[@id="bottom-navbar"]//*[@id="mic"]').click()
        pyinput.keyDown(str(key1).replace("KEY","").lower())
        time.sleep(0.5)
        pyinput.keyUp(str(key1).replace("KEY","").lower())
        driver.find_element_by_xpath('//*[@id="bottom-navbar"]//*[@id="mic"]').click()
        break
  except Exception as ex:
    print(ex)
    pass
def prease_on_key1(driver, key, *word):
  t1 = Thread(target = prease_on_key, args =(driver, key, *word))
  t1.start()


def web():
    os.system("taskkill /f /im  chromedriver.exe")
    options = Options()
    home =r"C:\Program Files (x86)\Google\Chrome"
    options.add_argument("--use-fake-ui-for-media-stream")# звук
    options.add_experimental_option("excludeSwitches", ['enable-automation']) # убрать окно
    options.binary_location = home +r"\Application\chrome.exe"
    options.add_argument(r"--user-data-dir=C:\Users\egor\AppData\Local\Google\Chrome\User Data")
    try:
      driver = webdriver.Chrome(home+r'\chromedriver\chromedriver.exe', options=options)
      driver.set_window_position(600, 650)
      driver.set_window_size(624, 368) # optiol
      driver.get("https://www.speechtexter.com")# открыть сайт
      check(driver)
      driver.minimize_window()
      driver.find_element_by_xpath('//*[@id="bottom-navbar"]//*[@class="wave" and @id="mic"]').click()# включить запись голоса

      options.add_argument("--disable-extensions")  # отключить расширения.
      return driver

    except Exception as ex:
       pass
    finally:
       pass
# добавление нового элемента
list_profiles = ["default"]  # список профилей.


def start_voice():
  for i in range(len(arg)):
    value=list(str(arg[i].get().split(',')))
    key= str(values[i].get())
    try:
        if key=="":
            messagebox.showerror("Erorr","key emrty")
            return
        if value == "":
           messagebox.showerror("Erorr", "Value emrty")
           return
        driver = web()
        prease_on_key1(driver, key, value)
        #     with keyboard.Listener(on_release=on_release) as listener:
        #         listener.join()

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

def on_close():
    new_data={"last_pfofile" : profile_current.get(),
    "profiles" : dict_save.return_dict()} # новые значения настроек.
    old_data= dict_save.return_jnson()# старые значения настроек.
    if new_data != old_data:
     if messagebox.askokcancel("Quit", "Do you want to save the changes?"):
         json_string = json.dumps(new_data, ensure_ascii=False, indent=2)
         with open("settings.json", "w", encoding="cp1251") as w:
             w.write(json_string)# сохранить изменения в файле настроек.
     else:
        pass
    else:
        pass
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
        entry = Entry(scrollable_frame, width=25,textvariable=arg[value])  # текстовое поле и кнопка для добавления в список
        entry.grid(column=0, row=value+1, padx=10, pady=8, sticky=W)
        box = Combobox(scrollable_frame, width=12, textvariable=values[value], values=a[0])
        box.grid(column=1, row=value+1, padx=22, pady=0)  # поле со списком
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
    box = Combobox(root, width=12, textvariable=profile_current, values=list_profiles, state='readonly')
    box.grid(column=1, row=0, padx=3, pady=0)  # поле со списком.
    box.bind('<Button-1>', c)  # при нажатии на выпадающий список.
    box.bind('<<ComboboxSelected>>', update)# при изменения профиля.
    return box
def add1(root,window, new, scrollable_frame):
    value= new_profile.get()
    if value != '':
     list_profiles.append(str(value))
     box = Combobox(root, width=12, textvariable=profile_current, values=list_profiles, state='readonly')
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
  data ="settings.json"  # файл настроек.
  if os.path.exists(data):  # есть ли этот файл.
    with open(data) as json_file:
      res= json.load(json_file)

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

dict_save=save_dict()
root = Tk()
root.geometry("580x250+650+400")
profile_current, new_profile=StringVar(),StringVar()

lb = Label(root, text="Голосовое управления в играх",width=25).grid(column=0, row=0)  # текстовое поле и кнопка для добавления в список

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
start(new, scrollable_frame,box)# запуск всего.

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
root.mainloop()



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
