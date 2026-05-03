from write_text_for_tkinter import *
import torch, time, threading, collections, math
import numpy as np
import sounddevice as sd
import tkinter as tk
import subprocess, os, warnings, logging

from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

# ================== НАСТРОЙКИ ==================
LOCAL_MODEL_PATH = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/Voxtral-Transcribe-2"

# ⚠️ ВАЖНО: укажи реальный HF repo модели
HF_MODEL_ID = "mistralai/Voxtral-Transcribe-2"

torch.set_num_threads(8)

warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)

# ================== МИКРОФОН ==================
source_id = get_webcam_source_id()
set_mute("0", source_id)

# ================== ЗАГРУЗКА МОДЕЛИ ==================
def check_model():
    try:
        print("Проверяем локальную модель...")

        use_local = os.path.exists(os.path.join(LOCAL_MODEL_PATH, "config.json"))

        if use_local:
            print("Найдена локальная модель")
            model_path = LOCAL_MODEL_PATH
            local_only = True
        else:
            print("Локальной модели нет → качаем с HuggingFace")
            model_path = HF_MODEL_ID
            local_only = False

        t_start = time.time()

        processor = AutoProcessor.from_pretrained(
            model_path,
            local_files_only=local_only,
            trust_remote_code=True
        )

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="cuda:0" if torch.cuda.is_available() else "cpu",
            local_files_only=local_only,
            trust_remote_code=True
        )

        pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
        )

        print(f"Модель готова за {time.time() - t_start:.2f} сек")
        return pipe

    except Exception as e:
        print(f"Ошибка загрузки модели: {e}")
        return None


# ================== УБИВАЕМ ДУБЛИКАТ ==================
script_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/off mic.py"
script_name = os.path.basename(script_path)

result = subprocess.run(f"pgrep -f '{script_name}'", shell=True, capture_output=True, text=True)
if result.returncode == 0 and result.stdout.strip():
    for pid in result.stdout.strip().split():
        try:
            subprocess.run(["kill", "-9", pid], check=True)
        except:
            pass


# ================== ФОНОВЫЙ СКРИПТ ==================
def run_script():
    cmd = f'"/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python" "{script_path}"'
    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


# ================== ОСНОВНАЯ ЛОГИКА ==================
def update_label(root, label, model, source_id):

    def record_and_process():
        try:
            if not get_mute_status(source_id):
                root.withdraw()
                return

            root.geometry("100x20+700+1025")
            label.config(text="Говорите...")
            root.deiconify()
            root.update()

            fs = 16000
            silence_time = 0
            last_speech_time = time.time()
            min_silence_duration = 1.0

            start = False
            buffer = collections.deque()
            pause_count = 0

            with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
                while True:

                    if not get_mute_status(source_id):
                        root.withdraw()
                        return

                    audio_chunk, _ = stream.read(16096)

                    mean_amp = math.ceil(np.mean(np.abs(audio_chunk)) * 100)

                    if mean_amp > 4:
                        last_speech_time = time.time()
                        silence_time = 0
                        start = True

                    if start:
                        buffer.append(audio_chunk.flatten())

                        if mean_amp < 9:
                            pause_count += 1

                        silence_time += time.time() - last_speech_time
                        last_speech_time = time.time()

                        if silence_time > min_silence_duration:
                            break

            root.withdraw()

            if not buffer:
                return

            audio = np.concatenate(buffer)

            if len(audio) / fs < 0.5:
                return

            if is_speech(0.030, audio):
                audio = boost_by_db_range(audio, -4, -20)

                print(f"Паузы: {pause_count}")

                with torch.no_grad():
                    result = model(
                        audio,
                        sampling_rate=fs,
                        generate_kwargs={"language": "ru"}
                    )

                text = result.get("text", "").strip()

                if text:
                    threading.Thread(
                        target=process_text,
                        args=(text,),
                        daemon=True
                    ).start()

        except Exception as e:
            print(f"Ошибка: {e}")

        root.after(500, lambda: update_label(root, label, model, source_id))

    if get_mute_status(source_id):
        threading.Thread(target=record_and_process, daemon=True).start()
    else:
        root.withdraw()
        root.after(1000, lambda: update_label(root, label, model, source_id))


# ================== GUI ==================
root = tk.Tk()
frame = tk.Frame(root)

label = tk.Label(frame, text="...", font='Times 14')
label.pack(padx=3, fill=tk.X, expand=True)

frame.pack(fill=tk.X)

root.overrideredirect(True)
root.attributes("-topmost", True)

# ================== СТАРТ ==================
model = check_model()

if model is None:
    print("Модель не загрузилась. Проверь путь или интернет.")
    exit(1)

threading.Thread(target=run_script, daemon=True).start()

update_label(root, label, model, source_id)

root.mainloop()