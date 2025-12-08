import os
import shutil
from transformers import pipeline, AutoModelForSpeechSeq2Seq, AutoProcessor
import torch

# --- КОНФИГУРАЦИЯ ---
# Отступ 2 пробела
MODEL_NAME = "vikhr-models/Vikhr-Borealis-7b"
CACHE_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache"
DUMMY_AUDIO_PATH = "temp.wav"

def check_and_download_model(model_name: str, cache_dir: str):
    """
    Проверяет наличие модели в кэше и скачивает ее, если отсутствует.
    """
    # Устанавливаем переменные окружения, чтобы Hugging Face использовал наш кэш
    os.environ['TRANSFORMERS_CACHE'] = cache_dir

    # Проверяем наличие папки для кэша и создаем, если ее нет
    if not os.path.exists(cache_dir):
        print(f"Создаю директорию кэша: {cache_dir}")
        os.makedirs(cache_dir)

    print(f"Проверяю наличие модели '{model_name}' в кэше...")

    # Попытка инициализировать модель и процессор.
    # Hugging Face автоматически скачает их в CACHE_DIR, если не найдет
    try:
        processor = AutoProcessor.from_pretrained(
            model_name,
            cache_dir=cache_dir
        )
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_name,
            cache_dir=cache_dir
        )
        print(f"✅ Модель '{model_name}' доступна в кэше или успешно скачана.")
        return model, processor

    except Exception as e:
        print(f"❌ Ошибка при загрузке модели: {e}")
        # В случае ошибки очищаем папку, если она создана не полностью
        # (опционально, для чистоты кэша)
        # shutil.rmtree(cache_dir, ignore_errors=True)
        return None, None


def create_dummy_audio(path):
    """
    Создает фиктивный аудиофайл для демонстрации распознавания.
    (Требует soundfile, numpy)
    """
    try:
        import numpy as np
        import soundfile as sf
    except ImportError:
        print("\nДля создания фиктивного аудио нужен 'numpy' и 'soundfile'.")
        print("Установите: pip install numpy soundfile")
        return False

    print(f"Создаю фиктивный аудиофайл: {path}")
    sample_rate = 16000
    duration = 3  # 3 секунды
    frequency = 440

    # Простая синусоида + "тишина"
    t = np.linspace(0., duration, int(sample_rate * duration), endpoint=False)
    data = 0.5 * np.sin(2. * np.pi * frequency * t)

    # Добавляем "речь" в виде простой синусоиды, для демонстрации не важна разборчивость
    sf.write(path, data, sample_rate)
    return True


def transcribe_audio_stream(model, processor, audio_path: str):
    """
    Демонстрирует распознавание речи (ASR) из аудиофайла,
    имитируя потоковый подход.

    Модели Whisper-типа обрабатывают аудио "блоками" (chunks),
    что можно считать псевдо-потоком, но для простоты мы используем pipeline.
    """

    # Выбираем устройство: GPU, если доступен, иначе CPU
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"\nИспользуется устройство для распознавания: {device}")

    # Инициализируем пайплайн распознавания речи
    asr_pipeline = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        device=device
    )

    # --- КАК ОНА РАСПОЗНАЕТ РЕЧЬ ---
    # Whisper-подобные модели (включая Vikhr Borealis) не являются "чисто"
    # потоковыми (streaming) ASR-системами, которые обрабатывают каждый семпл
    # по мере поступления. Вместо этого они:
    # 1. Загружают весь аудиофайл.
    # 2. Разбивают его на более мелкие "блоки" (chunks) по 30 секунд.
    # 3. Транскрибируют каждый блок.
    # 4. Соединяют результаты.

    print(f"Начинаю распознавание файла: {audio_path}")

    # Выполняем транскрипцию
    result = asr_pipeline(audio_path, chunk_length_s=15, stride_length_s=(4, 2), return_timestamps=True)

    print("\n--- Результат распознавания Vikhr Borealis ---")
    print(f"Полный текст: {result['text']}")

    # Демонстрация псевдо-потока (блоков)
    if 'chunks' in result:
        print("\nРаспознавание по блокам (имитация потока):")
        for chunk in result['chunks']:
            # На фиктивном аудио текст будет неразборчивым, но структура видна
            print(f"  [{chunk['timestamp'][0]:.2f} - {chunk['timestamp'][1]:.2f} с]: {chunk['text']}")

    print("\n-------------------------------------------")


# --- ГЛАВНАЯ ФУНКЦИЯ ---
def main():
    """
    Основная функция скрипта.
    """
    # 1. Проверка и скачивание модели
    model, processor = check_and_download_model(MODEL_NAME, CACHE_DIR)

    if model and processor:
        # 2. Создание фиктивного аудиофайла
        # if create_dummy_audio(DUMMY_AUDIO_PATH):
            # 3. Распознавание речи
            transcribe_audio_stream(model, processor, DUMMY_AUDIO_PATH)



if __name__ == "__main__":
    main()