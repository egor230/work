import sys
import os
from pathlib import Path
import sounddevice as sd
from scipy.io.wavfile import write
import pygame
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import numpy as np
import queue
import threading
import torch
import torchaudio
from speechbrain.pretrained import SpectralMaskEnhancement
import logging

# Настройка кэша
cache_dir = Path("/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(cache_dir)
os.environ["TORCH_HOME"] = str(cache_dir)
os.environ["HF_HOME"] = str(cache_dir / "huggingface")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioEnhancerModel:
    """Синглтон для управления моделью улучшения аудио"""
    _instance = None
    _model = None
    _model_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AudioEnhancerModel, cls).__new__(cls)
        return cls._instance

    def load_model(self):
        if not self._model_loaded:
            try:
                logger.info("Загрузка модели улучшения речи...")
                model_dir = cache_dir / "speechbrain_models" / "metricgan-plus-voicebank"
                self._model = SpectralMaskEnhancement.from_hparams(
                    source="speechbrain/metricgan-plus-voicebank",
                    savedir=str(model_dir),
                    run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"}
                )
                self._model_loaded = True
                logger.info("Модель успешно загружена!")
                return True
            except Exception as e:
                logger.error(f"Ошибка загрузки модели: {e}")
                self._model_loaded = False
                return False
        return True

    def enhance_audio(self, input_file, output_file):
        if not self._model_loaded:
            if not self.load_model():
                raise Exception("Не удалось загрузить модель")
        try:
            waveform, sample_rate = torchaudio.load(input_file)
            waveform = waveform.squeeze(0)  # (1, time) -> (time,)
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)
            noisy = waveform.unsqueeze(0)  # (1, time)
            lengths = torch.tensor([1.0])
            enhanced = self._model.enhance_batch(noisy, lengths=lengths)
            enhanced = enhanced.squeeze(0)  # (time,)
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(16000, sample_rate)
                enhanced = resampler(enhanced)
            enhanced = enhanced.unsqueeze(0)  # (1, time)
            torchaudio.save(output_file, enhanced.cpu(), sample_rate)
            return True
        except Exception as e:
            logger.error(f"Ошибка при улучшении аудио: {e}")
            return False

    def is_loaded(self):
        return self._model_loaded

class ContinuousRecorder:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_queue = queue.Queue()
        self.audio_data = []

    def callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_queue.put(indata.copy())

    def start_recording(self):
        self.recording = True
        self.audio_data = []
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=self.callback,
            blocksize=2048
        )
        self.stream.start()
        self.collection_thread = threading.Thread(target=self._collect_audio)
        self.collection_thread.start()

    def _collect_audio(self):
        while self.recording:
            try:
                data = self.audio_queue.get(timeout=0.1)
                self.audio_data.append(data)
            except queue.Empty:
                continue

    def stop_recording(self):
        self.recording = False
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        if hasattr(self, 'collection_thread'):
            self.collection_thread.join()
        if self.audio_data:
            return np.concatenate(self.audio_data, axis=0)
        return np.array([])

class ModelLoadingThread(QThread):
    finished = pyqtSignal(bool)
    progress = pyqtSignal(str)

    def run(self):
        self.progress.emit("Инициализация модели...")
        enhancer = AudioEnhancerModel()
        success = enhancer.load_model()
        self.finished.emit(success)

class EnhancementWorker(QObject):
    finished = pyqtSignal(bool)

    def __init__(self, enhancer, input_file, output_file):
        super().__init__()
        self.enhancer = enhancer
        self.input_file = input_file
        self.output_file = output_file

    def process(self):
        success = self.enhancer.enhance_audio(self.input_file, self.output_file)
        self.finished.emit(success)

class VoiceProcessingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.enhancer = AudioEnhancerModel()
        self.init_ui()
        self.init_audio_settings()
        pygame.mixer.init()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_counter)
        self.recording_seconds = 0
        self.is_recording = False
        self.recorder = ContinuousRecorder(self.SAMPLE_RATE)
        self.load_model_in_background()

    def init_ui(self):
        self.setWindowTitle("Voice Processing App - AI Enhancement")
        self.setGeometry(100, 100, 500, 400)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        self.model_status_label = QLabel("Проверка модели...", self)
        self.model_status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.model_status_label)
        self.status_label = QLabel("Готово к записи", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        self.counter_label = QLabel("", self)
        self.counter_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.counter_label)
        self.enhance_checkbox = QCheckBox("Использовать AI для улучшения качества")
        self.enhance_checkbox.setChecked(True)
        layout.addWidget(self.enhance_checkbox)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        self.record_button = QPushButton("Начать запись", self)
        self.record_button.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_button)
        self.play_button = QPushButton("Воспроизведение", self)
        self.play_button.clicked.connect(self.play_audio)
        self.play_button.setEnabled(False)
        layout.addWidget(self.play_button)
        self.stop_button = QPushButton("Остановить воспроизведение", self)
        self.stop_button.clicked.connect(self.stop_audio)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

    def init_audio_settings(self):
        self.SAMPLE_RATE = 44100
        self.RAW_FILE = str(cache_dir / "recording_raw.wav")
        self.ENHANCED_FILE = str(cache_dir / "recording_enhanced.wav")

    def load_model_in_background(self):
        if self.enhancer.is_loaded():
            self.model_status_label.setText("✓ AI модель загружена")
        else:
            self.model_loading_thread = ModelLoadingThread()
            self.model_loading_thread.progress.connect(self.update_model_status)
            self.model_loading_thread.finished.connect(self.on_model_loaded)
            self.model_loading_thread.start()

    def update_model_status(self, message):
        self.model_status_label.setText(message)

    def on_model_loaded(self, success):
        if success:
            self.model_status_label.setText("✓ AI модель загружена")
        else:
            self.model_status_label.setText("✗ Ошибка загрузки модели")
            self.enhance_checkbox.setChecked(False)
            self.enhance_checkbox.setEnabled(False)

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.is_recording = True
        self.recording_seconds = 0
        self.record_button.setText("Остановить запись")
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Идет запись...")
        self.counter_label.setText("0:00")
        self.timer.start(1000)
        self.recorder.start_recording()

    def stop_recording(self):
        self.is_recording = False
        self.timer.stop()
        self.record_button.setText("Начать запись")
        self.status_label.setText("Сохранение записи...")
        audio_data = self.recorder.stop_recording()
        if len(audio_data) > 0:
            write(self.RAW_FILE, self.SAMPLE_RATE, audio_data)
            if self.enhance_checkbox.isChecked() and self.enhancer.is_loaded():
                self.status_label.setText("Применение AI улучшения...")
                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, 0)
                self.enhancement_thread = QThread()
                self.enhancement_worker = EnhancementWorker(self.enhancer, self.RAW_FILE, self.ENHANCED_FILE)
                self.enhancement_worker.moveToThread(self.enhancement_thread)
                self.enhancement_thread.started.connect(self.enhancement_worker.process)
                self.enhancement_worker.finished.connect(self.on_enhancement_finished)
                self.enhancement_worker.finished.connect(self.enhancement_thread.quit)
                self.enhancement_worker.finished.connect(self.enhancement_worker.deleteLater)
                self.enhancement_thread.finished.connect(self.enhancement_thread.deleteLater)
                self.enhancement_thread.start()
            else:
                self.current_file = self.RAW_FILE
                self.finalize_recording(success=True, enhanced=False)
        else:
            self.status_label.setText("Ошибка: не удалось записать аудио")

    def on_enhancement_finished(self, success):
        self.progress_bar.setVisible(False)
        if success and os.path.exists(self.ENHANCED_FILE):
            self.current_file = self.ENHANCED_FILE
            self.finalize_recording(success=True, enhanced=True)
        else:
            self.current_file = self.RAW_FILE
            self.finalize_recording(success=True, enhanced=False)

    def finalize_recording(self, success, enhanced):
        if enhanced:
            self.status_label.setText(f"✓ AI улучшение применено! Длительность: {self.recording_seconds} сек.")
        else:
            self.status_label.setText(f"Запись сохранена. Длительность: {self.recording_seconds} сек.")
        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.play_audio()  # Автоматическое воспроизведение после записи

    def update_counter(self):
        self.recording_seconds += 1
        minutes = self.recording_seconds // 60
        seconds = self.recording_seconds % 60
        self.counter_label.setText(f"{minutes}:{seconds:02d}")

    def play_audio(self):
        if hasattr(self, 'current_file') and os.path.exists(self.current_file):
            try:
                pygame.mixer.music.load(self.current_file)
                pygame.mixer.music.play()
                self.status_label.setText("Воспроизведение...")
            except Exception as e:
                logger.error(f"Ошибка воспроизведения: {e}")
                self.status_label.setText("Ошибка воспроизведения")
        else:
            self.status_label.setText("Аудиофайл не найден")

    def stop_audio(self):
        pygame.mixer.music.stop()
        self.status_label.setText("Воспроизведение остановлено")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VoiceProcessingApp()
    window.show()
    sys.exit(app.exec_())