from omegaconf.base import ContainerMetadata; from omegaconf.dictconfig import DictConfig
import os, json, re, time, warnings, collections, torch, tempfile, torchaudio, math, scipy.signal, typing, numpy as np, soundfile as sf, sounddevice as sd
from sber_gegaam_without_cuda import load_model
torch.serialization.add_safe_globals([ContainerMetadata, DictConfig, typing.Any]); warnings.filterwarnings("ignore", category=DeprecationWarning); torch.set_num_threads(8); t = time.time()
class save_key:
  def __init__(self):
    self.text = ""; self.flag = False; self.word = []; self.res = {}; self.new_res = {}
  def save_text(self, text): self.text = text
  def get_text(self): return self.text
  def update_dict(self):
    data = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/list for replacements.json"
    if os.path.exists(data):
      with open(data, encoding="cp1251") as json_file:
        self.res = json.load(json_file)
        for key in self.res.keys():
          if '*' in key: self.new_res[key] = self.res[key]
        for key in self.new_res.keys(): del self.res[key]
  def get_dict(self): return self.res
  
  def save_words(self, w):
    self.word.clear()
    for i in w: self.word.append(i)
    self.word = sorted(self.word, key=lambda s: len(s.split()), reverse=True)
  def get_words(self): return self.word
k = save_key(); k.update_dict()
def check_model():
  models = ["v1_ssl", "v2_ssl", "ssl", "ctc", "v1_ctc", "v2_ctc", "rnnt", "v1_rnnt", "v2_rnnt", "emo", "v3_e2e_rnnt", "v3_e2e_ctc"]
  model_name = models[-2]
  try:
    cache_dir = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/gigaam"
    model = load_model(model_name, cache_dir)
    return model
  except Exception as e: print(e)
def repeat(text1: str):
  text = text1.replace("?", "").replace("!", "")
  k.save_text(text)
  text1 = ""
  res = k.get_dict()
  k.save_words(res)
  words = k.get_words()
  try:
    words_regex = r'\b(' + r'|'.join(map(re.escape, words)) + r')\b'
    text1 = re.sub(words_regex, lambda m: res.get(m.group(0).lower(), m.group(0)), k.get_text(), flags=re.IGNORECASE)
    k.save_text(text1)
  except Exception as ex: print(f"Ошибка: {ex}")
  return text1
def is_speech(threshold=0.074, audio_source="temp.wav"):
  try:
    if isinstance(audio_source, (str, bytes, os.PathLike)):
      if not os.path.isfile(audio_source): print(f"Файл не найден: {audio_source}"); return False
      data, sr = sf.read(audio_source, dtype='float32')
    elif isinstance(audio_source, np.ndarray): data = audio_source.astype('float32')
    else: print("Неподдерживаемый тип данных"); return False
    if len(data) == 0: print("Аудио пустое"); return False
    amp = np.mean(np.abs(data))
    return amp > threshold
  except Exception as ex: print(f"Ошибка в is_speech: {ex}"); return False
model = check_model(); print(time.time() - t); fs = 16 * 1000; silence_time = 0; last_speech_time = time.time(); min_silence_duration = 1.0; start = False
try:
  buffer = collections.deque()
  with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
    while True:
      audio_chunk, overflowed = stream.read(16096)
      mean_amp = np.mean(np.abs(audio_chunk)) * 100
      mean_amp = math.ceil(mean_amp)
      if mean_amp > 4:
        last_speech_time = time.time()
        silence_time = 0
        start = True
      if start:
        buffer.append(audio_chunk.astype(np.float32).flatten())
        if silence_time > min_silence_duration:
          array = np.fromiter((item for chunk in buffer for item in chunk), dtype=np.float32)
          duration = len(array) / fs
          if duration > 4 and is_speech(0.030, array):
            message = model.transcribe(array)
            if message != " " and len(message) > 0: print(message)
          start = False
          buffer.clear()
          silence_time = 0
        else:
          silence_time += time.time() - last_speech_time
          last_speech_time = time.time()
except Exception as e: print(e)