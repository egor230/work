from omegaconf import OmegaConf
from omegaconf.base import ContainerMetadata
from omegaconf.dictconfig import DictConfig
from write_text_for_tkinter import *

import torch
import math
import typing
import warnings
import os
import numpy as np
import collections
import threading
import time
import subprocess
import tkinter as tk
import sounddevice as sd
import sys

from transformers import AutoProcessor, AutoModelForCTC

torch.serialization.add_safe_globals([ContainerMetadata, DictConfig, typing.Any])
warnings.filterwarnings("ignore", category=DeprecationWarning)
torch.set_num_threads(8)

MODEL_PATH = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/T-one"

source_id = get_webcam_source_id()
set_mute("0", source_id)

# ================= MODEL =================
import sys
import numpy as np
from tone.pipeline.streaming_ctc import StreamingCTCPipeline

MODEL_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/T-one"

# загружаем wav (16kHz, mono)
audio, sr = sf.read("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/temp1.wav", dtype="float32")
assert sr == 16000, "Нужен wav 16kHz"

pipeline = StreamingCTCPipeline.from_pretrained(
    model_path=MODEL_DIR,
    device="cpu"
)

result = pipeline.forward_offline(audio)

print("TEXT:")
print(" ".join(p.text for p in result if p.text))







# MODEL_PATH = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/T-one"
#
# pipeline = StreamingCTCPipeline.from_pretrained(
#     model_path=MODEL_PATH,
#     device="cpu"   # или "cuda"
# )
#
# def transcribe(audio_16k_float32: np.ndarray) -> str:
#     result = pipeline.forward_offline(audio_16k_float32)
#     return " ".join(p.text for p in result if p.text.strip())
#
# def check_model():
#     print("Загружаю модель...")
#
#     processor = AutoProcessor.from_pretrained(MODEL_PATH)
#     model = AutoModelForCTC.from_pretrained(MODEL_PATH)
#     model.eval()
#
#     def transcribe(audio_array: np.ndarray) -> str:
#         if audio_array is None or len(audio_array) == 0:
#             return ""
#
#         inputs = processor(
#             audio_array,
#             sampling_rate=16000,
#             return_tensors="pt"
#         )
#
#         with torch.no_grad():
#             logits = model(**inputs).logits
#
#         ids = torch.argmax(logits, dim=-1)
#         text = processor.batch_decode(ids)[0]
#         return text.strip()
#
#     model.transcribe = transcribe
#     print("Модель загружена OK")
#     return model
#
# model = check_model()
#
# # ================= AUDIO =================
#
# def boost_by_db_range(audio_array, low_db, high_db, boost=3):
#     abs_audio = np.abs(audio_array)
#     db_vals = 20 * np.log10(abs_audio + 1e-9)
#     mask = (db_vals >= low_db) & (db_vals <= high_db)
#     factor = 10 ** (boost / 20)
#     audio_array[mask] *= factor
#     return np.clip(audio_array, -1.0, 1.0)
#
# # ================= UI LOOP =================
#
# def update_label(root, label, model, source_id):
#     def record_and_process():
#         fs = 16000
#         last_speech_time = time.time()
#         min_silence = 1.0
#         buffer = collections.deque()
#         started = False
#
#         with sd.InputStream(samplerate=fs, channels=1, dtype="float32") as stream:
#             while True:
#                 if not get_mute_status(source_id):
#                     root.withdraw()
#                     return
#
#                 audio, _ = stream.read(16000)
#                 amp = np.mean(np.abs(audio)) * 100
#
#                 if amp > 4:
#                     last_speech_time = time.time()
#                     started = True
#
#                 if started:
#                     buffer.append(audio.flatten())
#
#                 if started and time.time() - last_speech_time > min_silence:
#                     break
#
#         if not buffer:
#             return
#
#         array = np.concatenate(buffer)
#         if not is_speech(0.030, array):
#             return
#
#         array = boost_by_db_range(array, -4, -20)
#         text = model.transcribe(array)
#
#         if text:
#             threading.Thread(
#                 target=process_text,
#                 args=(text,),
#                 daemon=True
#             ).start()
#
#     if get_mute_status(source_id):
#         label.config(text="Говорите...")
#         root.deiconify()
#         threading.Thread(target=record_and_process, daemon=True).start()
#     else:
#         root.withdraw()
#
#     root.after(1500, lambda: update_label(root, label, model, source_id))
#
# # ================= TK =================
#
# root = tk.Tk()
# frame = tk.Frame(root)
# label = tk.Label(frame, text="...", font="Times 14")
# label.pack(padx=3, fill=tk.X, expand=True)
# frame.pack(fill=tk.X)
#
# root.overrideredirect(True)
# root.attributes("-topmost", True)
#
# update_label(root, label, model, source_id)
# root.mainloop()

