import requests
from bs4 import BeautifulSoup
from os.path import basename

import urllib.request
import re

url = "https://vk.com/im?act=browse_images&id=284318"
response = requests.get(url)

response = urllib.request.urlopen(url)

html = response.read().decode("utf-8")
print(html)