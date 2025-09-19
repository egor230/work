from PIL import Image
import glob, os, re
def check_is_folder(adress_output): # adress_output=str("‪C:/Users/egor/Desktop/держуства/output").lstrip('\u202a')
 if not os.path.exists(adress_output):
     os.mkdir(adress_output)
 else:
   pass
 # adress=r"C:\Users\egor\Desktop\держуства\Новая папка"
adress= os.getcwd()+str('/Новая папка')
adress_watermark=os.getcwd()+str(r"/watermarker.jpg")
adress_files=adress

adress_output=os.getcwd()+str(r"/output")


check_is_folder(adress_output)

# print(adress_output)
# input()
adress1=''
t=['*.PNG', '*.JPG','*.JPEG','*.BMP','*.png', '*.jpg','*.jpeg','*.bmp']
number=0#os.path.join(adress_files, file)#.lstrip('\u202a')

# os.chdir(os.getcwd()+str('/Новая папка'))#Полный путь к каталогу, который будет изменен на новый путь к каталогу.
def get_files_with_extensions(directory, extensions):
  print(directory)
  files = []
  for filename in os.listdir(directory):
    if any(filename.endswith(ext) for ext in extensions):
      files.append(filename)
  return files


# Пример использования
directory = str(adress)
extensions = ['.png', '.jpg', '.jpeg', '.bmp']
files = get_files_with_extensions(directory, extensions)
for file in files:
  file=str(file)
  lookfor = r"[/.]+[.\w+]+."
  adress1= adress +str('/')+file
  res=re.findall(lookfor, adress1)
  res=res[-1][-4:]
  number= number+1
  res=str(res)
  file_name=""
  if res.startswith('.'):
    file_name = str(number) + str(res)
  else:
   file_name=str(number)+"."+str(res)
  print(file_name)
  adress_output1=os.path.join(adress_output,file_name)
  watermark = Image.open(adress_watermark)
  print(adress_output1)
  # input()
  photo= Image.open(adress1)
  photo.paste(watermark, (0, 0))
  photo.save(adress_output1)

# print(files)
  # for file in glob.glob(i2):
    # print(file)
  # print(adress1)
  # input()
