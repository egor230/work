import time, json, os, copy, psutil, threading, re, select, glob, subprocess, psutil
from tkinter import *
from tkinter.ttk import Combobox  # импортируем только то что надо
from tkinter import messagebox
from tkinter import filedialog
from os import path

class save_dict:
    def __init__(self):
        self.labels = []  # надписи.
        self.res=[]
        self.count=0 # Индекс текущей игры.

    def save_labels(self, labels):
      self.labels = labels

    def return_labels(self):
       return self.labels
    def cl_res(self):
      self.res.clear()

    def save_res(self, res):
      self.res.clear()
      self.res = res

    def return_res(self):
      return self.res

    def return_var_list(self):
       return self.var_list


    def set_count(self, count):
        self.count=count
        return self.count

    def get_count(self):
       return self.count

k =save_dict()
folder="/mnt/807EB5FA7EB5E954/работа/база для анализа"
labels = []
k.save_labels(labels)
def check_label_changed(event, labels, count):# изменение цвета label
 res = k.return_res()
 folder1=str(folder).replace(" ", "\ ")
 file_path = str(res[count]).replace(" ", "\ ")+".doc" # номер записи.
 set_button_map = '''#!/bin/bash
    cd {0};
    wine {1}; exit;  '''.format(folder1, file_path)
 # subprocess.call(['bash', '-c', set_button_map])

 # Создание лямбда-функции, которая будет запускать команду
 run_command = lambda: subprocess.call(['bash', '-c', set_button_map])

 # Создание нового потока и запуск команды в нем
 thread = threading.Thread(target=run_command)
 thread.start()
 e.delete(0, END)
 # print(folder1)
 # print(file_path)
def del_labels():
  # print("lkmjbvf")
  labels= k.return_labels()
  # print(len(labels))
  for i in range(len(labels)):
   # print("ded")
   labels[i].destroy()
   labels[i]
  labels.clear()
  k.save_labels(labels)
  # k.cl_res()
def f(e,  labels, canvas):
  res=k.return_res()
  res = res[1:] + [res[0]]
  del_labels()
  k.save_res(res)
  name = {}
  y=17
  for count, i in enumerate(res):  # print(count)
    name[i] = StringVar()
    name[i].set(res[count])
    labels.append(Label(canvas, background="white", text=name[i].get(), width=51, anchor="w", relief=GROOVE))
    labels[count].place(x=7, y=y)  # текстовое поле и кнопка для добавления в список   # print(res[count])    # надписи
    y = y + 26
    labels[count].bind("<Button-1>", lambda event, agr=labels, agr1=count:
    check_label_changed(event, agr, agr1))
def fill_labes(canvas):
  res=k.return_res() #
  # k.cl_res()
  name = {}
  labels = k.return_labels()  # print(len(labels))

  del_labels()
  y=17
  # print(res)
  container.grid()
  canvas.grid(sticky=N + W)
  for count, i in enumerate(res):    # print(count)
    name[i] = StringVar()
    name[i].set(res[count])
    labels.append(Label(canvas, background="white", text=name[i].get(), width=51, anchor="w", relief=GROOVE))
    labels[count].place(x=7, y=y)  # текстовое поле и кнопка для добавления в список   # print(res[count])    # надписи
    y = y + 26
    labels[count].bind("<Button-1>", lambda event, agr=labels, agr1=count:check_label_changed(event, agr, agr1))
  # f(e, labels, canvas)

  # print(len(labels))
  k.save_labels(labels)
  scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)

  scrollbar.grid(column=0, row=0, sticky=N + S + E)  # полоса прокрутки.
  canvas.configure(yscrollcommand=scrollbar.set)
  scrollable_frame = Frame(root)
  scrollbar.bind("<ButtonRelease-1>",lambda event, agr=labels, agr1=canvas: f(event, agr, agr1))

<<<<<<< HEAD
=======

  # time.sleep(2)
  # print(res)
  # scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all") ))
  # time.sleep(2)
  # print(res)
>>>>>>> ca952c6e0b896bf9e25df10333b1ef1b556512e9
def update(event, canvas):# Изменение назначения кнопок.
  # k.save_labels(labels)
  # for i in range(len(labels)):
  #   labels[i].destroy()
  text = str(e.get()) #  print(text)
  res=[] #  # k.cl_res()  # text="Судьбы"
  file_list = os.listdir(folder) #
  # Выводим названия файлов
  for file_name in file_list:    # print(file_name)
    if text.lower() in file_name.lower():
     res.append(file_name[:-4])
  if len(res)>0:  #   print(res)
   k.save_res(res)
   fill_labes(canvas)
root = Tk()
root.title("Find text")  # заголовок
root.geometry("500x236+630+540")  # Первые 2 определяют ширину высоту. Пос 2 x и y координаты на экране.
root.configure(bg='DimGray')  # Цвет фона окна

container = Frame(root)
canvas = Canvas(container, width=470, height=236)

canvas.create_window((0, 0), window=container, anchor="n")
e = Entry(root, width=50, fg='blue',  borderwidth=1)

e.focus()
e.bind("<KeyRelease>", lambda event:  update(event, canvas))

e.grid(column=0, row=0, padx=10, pady=5)

# update(0)

root.mainloop()
<<<<<<< HEAD

# time.sleep(2)
# print(res)
# scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all") ))
# time.sleep(2)
# print(res)


=======
>>>>>>> ca952c6e0b896bf9e25df10333b1ef1b556512e9
