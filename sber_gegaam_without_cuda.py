import hashlib, logging, math, os, urllib.request, warnings, numpy as np, onnxruntime as rt, torch, torch.nn.functional as F, torchaudio, torchaudio.functional as taF, omegaconf
from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Dict, List, Optional, Tuple, Union
from torch import Tensor, nn
from torch.jit import TracerWarning
from sentencepiece import SentencePieceProcessor
from tqdm import tqdm
from pyannote.audio import Model, Pipeline
from pyannote.audio.core.task import Problem, Resolution, Specifications
from pyannote.audio.pipelines import VoiceActivityDetection

# Константы
SAMPLE_RATE = 16000
LONGFORM_THRESHOLD = 35 * SAMPLE_RATE  # 25 секунд порог для длинных аудио
DTYPE = np.float32
MAX_LETTERS_PER_FRAME = 3
_URL_DIR = "https://cdn.chatwm.opensmodel.sberdevices.ru/GigaAM"
_MODEL_HASHES = {
 "emo": "7ce76f9535cb254488985057c0d33006",
 "v1_ctc": "f027f199e590a391d015aeede2e66174",
 "v1_rnnt": "02c758999bcdc6afcb2087ef256d47ef",
 "v1_ssl": "dc7f7b231f7f91c4968dc21910e7b396",
 "v2_ctc": "e00f59cb5d39624fb30d1786044795bf",
 "v2_rnnt": "547460139acfebd842323f59ed54ab54",
 "v2_ssl": "cd4cf819c8191a07b9d7edcad111668e",
 "v3_ctc": "73413e7be9c6a5935827bfab5c0dd678",
 "v3_rnnt": "0fd2c9a1ff66abd8d32a3a07f7592815",
 "v3_e2e_ctc": "367074d6498f426d960b25f49531cf68",
 "v3_e2e_rnnt": "2730de7545ac43ad256485a462b0a27a",
 "v3_ssl": "70cbf5ed7303a0ed242ddb257e9dc6a6",
}

_PIPELINE = None  # Кэш для VAD пайплайна
warnings.simplefilter("ignore", category=UserWarning)  # Игнорируем предупреждения


def load_audio(audio_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE) -> Tensor:
 """Загружает аудио из файла, массива или тензора и нормализует до 16кГц"""
 if isinstance(audio_input, str):
  # Используем ffmpeg для загрузки аудиофайлов
  cmd = ["ffmpeg", "-nostdin", "-threads", "0", "-i", audio_input, "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-"]
  try:
   audio_bytes = run(cmd, capture_output=True, check=True).stdout
  except CalledProcessError as exc:
   raise RuntimeError("Failed to load audio") from exc
  with warnings.catch_warnings():
   warnings.simplefilter("ignore", category=UserWarning)
   audio_tensor = torch.frombuffer(audio_bytes, dtype=torch.int16).float() / 32768.0
 elif isinstance(audio_input, np.ndarray):
  audio_tensor = torch.from_numpy(audio_input.copy()).float()
 elif isinstance(audio_input, Tensor):
  audio_tensor = audio_input.float().clone()
 else:
  raise TypeError(f"Unsupported audio input type: {type(audio_input)}. Expected str, np.ndarray, or Tensor.")

 # Преобразуем к одноканальному формату
 if audio_tensor.ndim > 1:
  audio_tensor = audio_tensor.flatten()

 # Ресемплируем до целевой частоты дискретизации если нужно
 if sample_rate != SAMPLE_RATE:
  if audio_tensor.numel() > 0:
   audio_tensor = taF.resample(audio_tensor.unsqueeze(0), orig_freq=sample_rate, new_freq=SAMPLE_RATE).squeeze(0)

 return audio_tensor


class SpecScaler(nn.Module):
 """Логарифмическое масштабирование спектрограммы для стабильности вычислений"""

 def forward(self, x: Tensor) -> Tensor:
  return torch.log(x.clamp_(1e-9, 1e9))  # clip для численной стабильности


class FeatureExtractor(nn.Module):
 """Извлечение Mel-спектрограммы из аудио"""

 def __init__(self, sample_rate: int, features: int, hop_length=None, win_length=None, n_fft=None, center=None, **kwargs):
  super().__init__()
  self.hop_length = hop_length if hop_length is not None else kwargs.get("hop_length", sample_rate // 100)
  self.win_length = win_length if win_length is not None else kwargs.get("win_length", sample_rate // 40)
  self.n_fft = n_fft if n_fft is not None else kwargs.get("n_fft", sample_rate // 40)
  self.center = center if center is not None else kwargs.get("center", True)

  # Мел-спектрограмма + логарифмирование
  self.featurizer = nn.Sequential(
   torchaudio.transforms.MelSpectrogram(
    sample_rate=sample_rate,
    n_mels=features,
    win_length=self.win_length,
    hop_length=self.hop_length,
    n_fft=self.n_fft,
    center=self.center
   ),
   SpecScaler()
  )

 def out_len(self, input_lengths: Tensor) -> Tensor:
  """Вычисляет длину выходной последовательности после извлечения признаков"""
  if self.center:
   return input_lengths.div(self.hop_length, rounding_mode="floor").add(1).long()
  else:
   return (input_lengths - self.win_length).div(self.hop_length, rounding_mode="floor").add(1).long()

 def forward(self, input_signal: Tensor, length: Tensor) -> Tuple[Tensor, Tensor]:
  return self.featurizer(input_signal), self.out_len(length)


class CTCHead(nn.Module):
 """Голова CTC для распознавания речи"""

 def __init__(self, feat_in: int, num_classes: int):
  super().__init__()
  self.decoder_layers = torch.nn.Sequential(
   torch.nn.Conv1d(feat_in, num_classes, kernel_size=1)
  )

 def forward(self, encoder_output: Tensor) -> Tensor:
  return torch.nn.functional.log_softmax(
   self.decoder_layers(encoder_output).transpose(1, 2),
   dim=-1
  )


class RNNTJoint(nn.Module):
 """Joint сеть для RNN-T архитектуры"""

 def __init__(self, enc_hidden: int, pred_hidden: int, joint_hidden: int, num_classes: int):
  super().__init__()
  self.enc_hidden = enc_hidden
  self.pred_hidden = pred_hidden
  self.pred = nn.Linear(pred_hidden, joint_hidden)
  self.enc = nn.Linear(enc_hidden, joint_hidden)
  self.joint_net = nn.Sequential(
   nn.ReLU(),
   nn.Linear(joint_hidden, num_classes)
  )

 def joint(self, encoder_out: Tensor, decoder_out: Tensor) -> Tensor:
  """Объединяет выходы энкодера и декодера"""
  enc = self.enc(encoder_out).unsqueeze(2)
  pred = self.pred(decoder_out).unsqueeze(1)
  return self.joint_net(enc + pred).log_softmax(-1)

 def forward(self, enc: Tensor, dec: Tensor) -> Tensor:
  return self.joint(enc.transpose(1, 2), dec.transpose(1, 2))


class RNNTDecoder(nn.Module):
 """Декодер для RNN-T архитектуры"""

 def __init__(self, pred_hidden: int, pred_rnn_layers: int, num_classes: int):
  super().__init__()
  self.blank_id = num_classes - 1  # ID для blank символа
  self.pred_hidden = pred_hidden
  self.embed = nn.Embedding(num_classes, pred_hidden, padding_idx=self.blank_id)
  self.lstm = nn.LSTM(pred_hidden, pred_hidden, pred_rnn_layers)

 def predict(self, x: Optional[Tensor], state: Optional[Tensor], batch_size: int = 1) -> Tuple[Tensor, Tensor]:
  """Предсказание следующего символа"""
  if x is not None:
   emb: Tensor = self.embed(x)
  else:
   emb = torch.zeros((batch_size, 1, self.pred_hidden), device=next(self.parameters()).device)
  g, hid = self.lstm(emb.transpose(0, 1), state)
  return g.transpose(0, 1), hid

 def forward(self, x: Tensor, h: Tensor, c: Tensor) -> Tuple[Tensor, Tensor, Tensor]:
  emb = self.embed(x)
  g, (h, c) = self.lstm(emb.transpose(0, 1), (h, c))
  return g.transpose(0, 1), h, c


class RNNTHead(nn.Module):
 """Объединяет декодер и joint сеть RNN-T"""

 def __init__(self, decoder: Dict[str, int], joint: Dict[str, int]):
  super().__init__()
  self.decoder = RNNTDecoder(**decoder)
  self.joint = RNNTJoint(**joint)


class Tokenizer:
 """Токенизатор для преобразования текста в ID и обратно"""

 def __init__(self, vocab: List[str], model_path: Optional[str] = None):
  self.charwise = model_path is None  # Используем ли character-level токенизацию
  if self.charwise:
   self.vocab = vocab
  else:
   self.model = SentencePieceProcessor()
   self.model.load(model_path)

 def decode(self, tokens: List[int]) -> str:
  if self.charwise:
   return "".join(self.vocab[tok] for tok in tokens)
  return self.model.decode(tokens)

 def __len__(self):
  return len(self.vocab) if self.charwise else len(self.model)


class CTCGreedyDecoding:
 """Жадное декодирование для CTC моделей"""

 def __init__(self, vocabulary: List[str], model_path: Optional[str] = None):
  self.tokenizer = Tokenizer(vocabulary, model_path)
  self.blank_id = len(self.tokenizer)  # ID для blank символа

 @torch.inference_mode()
 def decode(self, head: CTCHead, encoded: Tensor, lengths: Tensor) -> List[str]:
  log_probs = head(encoder_output=encoded)
  b, _, c = log_probs.shape

  # Получаем наиболее вероятные символы
  labels = log_probs.argmax(dim=-1, keepdim=False)

  # Убираем повторяющиеся символы и blank
  skip_mask = labels != self.blank_id
  skip_mask[:, 1:] = torch.logical_and(skip_mask[:, 1:], labels[:, 1:] != labels[:, :-1])

  # Обрезаем по длине
  for i, length in enumerate(lengths):
   skip_mask[i, length:] = 0

  # Собираем текст
  pred_texts: List[str] = []
  for i in range(b):
   pred_texts.append("".join(self.tokenizer.decode(labels[i][skip_mask[i]].cpu().tolist())))

  return pred_texts

class RNNTGreedyDecoding:
 """Жадное декодирование для RNN-T моделей"""

 def __init__(self, vocabulary: List[str], model_path: Optional[str] = None, max_symbols_per_step: int = 30):
  self.tokenizer = Tokenizer(vocabulary, model_path)# по умолчанию 10
  self.blank_id = len(self.tokenizer)
  self.max_symbols = 50  # Макс. символов на шаг

 def _greedy_decode(self, head: RNNTHead, x: Tensor, seqlen: Tensor) -> str:
  hyp: List[int] = []  # Список предсказанных ID
  dec_state: Optional[Tensor] = None  # Состояние декодера
  last_label: Optional[Tensor] = None  # Последний предсказанный символ

  for t in range(seqlen):
   f = x[t, :, :].unsqueeze(1)  # Текущий кадр аудио
   not_blank = True
   new_symbols = 0

   # Пока не встретим blank и не превысим лимит символов
   while not_blank and new_symbols < self.max_symbols:
    g, hidden = head.decoder.predict(last_label, dec_state)
    joint_out = head.joint.joint(f, g)
    k = joint_out[0, 0, 0, :].argmax(0).item()  # ID символа
    max_prob = joint_out[0, 0, 0, :].max().exp()  # Уверенность

    # Проверяем, не blank ли это и достаточно ли уверенности
    if k == self.blank_id or max_prob.item() < 0.4: # это порог уверенности в слове
     not_blank = False
    else:
     hyp.append(int(k))
     dec_state = hidden
     last_label = torch.tensor([[hyp[-1]]]).to(x.device)
     new_symbols += 1

  return self.tokenizer.decode(hyp)

 @torch.inference_mode()
 def decode(self, head: RNNTHead, encoded: Tensor, enc_len: Tensor) -> List[str]:
  b = encoded.shape[0]
  pred_texts = []
  encoded = encoded.transpose(1, 2)  # Приводим к нужному формату

  # Декодируем каждый элемент батча
  for i in range(b):
   inseq = encoded[i, :, :].unsqueeze(1)
   pred_texts.append(self._greedy_decode(head, inseq, enc_len[i]))

  return pred_texts


class StridingSubsampling(nn.Module):
 """Субсэмплирование с использованием сверток для уменьшения временной размерности"""

 def __init__(self, subsampling: str, kernel_size: int, subsampling_factor: int,
              feat_in: int, feat_out: int, conv_channels: int):
  super().__init__()
  self.subsampling_type = subsampling
  assert self.subsampling_type in ["conv1d", "conv2d"]

  self._sampling_num = int(math.log(subsampling_factor, 2))
  self._stride = 2
  self._kernel_size = kernel_size
  self._padding = (self._kernel_size - 1) // 2

  layers: List[nn.Module] = []
  in_channels = 1 if self.subsampling_type == "conv2d" else feat_in
  subs_conv_class = torch.nn.Conv2d if self.subsampling_type == "conv2d" else torch.nn.Conv1d

  for _ in range(self._sampling_num):
   layers.append(subs_conv_class(  in_channels=in_channels,    out_channels=conv_channels,
    kernel_size=self._kernel_size,
    stride=self._stride,   padding=self._padding
   ))
   layers.append(nn.ReLU())
   in_channels = conv_channels

  if self.subsampling_type == "conv2d":
   out_length = self.calc_output_length(torch.tensor(feat_in))
   self.out = torch.nn.Linear(conv_channels * int(out_length), feat_out)

  self.conv = torch.nn.Sequential(*layers)

 def calc_output_length(self, lengths: Tensor) -> Tensor:
  """Вычисляет длину выхода после субсэмплирования"""
  lengths = lengths.to(torch.float)
  add_pad = 2 * self._padding - self._kernel_size

  for _ in range(self._sampling_num):
   lengths = torch.div(lengths + add_pad, self._stride) + 1.0
   lengths = torch.floor(lengths)

  return lengths.to(dtype=torch.int)

 def forward(self, x: Tensor, lengths: Tensor) -> Tuple[Tensor, Tensor]:
  if self.subsampling_type == "conv2d":
   x = self.conv(x.unsqueeze(1))
   b, _, t, _ = x.size()
   x = self.out(x.transpose(1, 2).reshape(b, t, -1))
  else:
   x = self.conv(x.transpose(1, 2)).transpose(1, 2)

  return x, self.calc_output_length(lengths)

class MultiHeadAttention(nn.Module, ABC):
 """Базовый класс для механизма внимания"""

 def __init__(self, n_head: int, n_feat: int):
  super().__init__()
  assert n_feat % n_head == 0
  self.d_k = n_feat // n_head  # Размерность каждого head
  self.h = n_head

  # Линейные преобразования для Q, K, V
  self.linear_q = nn.Linear(n_feat, n_feat)
  self.linear_k = nn.Linear(n_feat, n_feat)
  self.linear_v = nn.Linear(n_feat, n_feat)
  self.linear_out = nn.Linear(n_feat, n_feat)

 def forward_qkv(self, query: Tensor, key: Tensor, value: Tensor) -> Tuple[Tensor, Tensor, Tensor]:
  b = query.size(0)
  q = self.linear_q(query).view(b, -1, self.h, self.d_k)
  k = self.linear_k(key).view(b, -1, self.h, self.d_k)
  v = self.linear_v(value).view(b, -1, self.h, self.d_k)

  return q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)

 def forward_attention(self, value: Tensor, scores: Tensor, mask: Optional[Tensor]) -> Tensor:
  b = value.size(0)

  if mask is not None:
   mask = mask.unsqueeze(1)
   scores = scores.masked_fill(mask, -10000.0)
   attn = torch.softmax(scores, dim=-1).masked_fill(mask, 0.0)
  else:
   attn = torch.softmax(scores, dim=-1)

  x = torch.matmul(attn, value)
  x = x.transpose(1, 2).reshape(b, -1, self.h * self.d_k)

  return self.linear_out(x)


class RelPositionMultiHeadAttention(MultiHeadAttention):
 """Attention с относительными позиционными эмбеддингами"""

 def __init__(self, n_head: int, n_feat: int):
  super().__init__(n_head, n_feat)
  self.linear_pos = nn.Linear(n_feat, n_feat, bias=False)
  self.pos_bias_u = nn.Parameter(torch.FloatTensor(self.h, self.d_k))
  self.pos_bias_v = nn.Parameter(torch.FloatTensor(self.h, self.d_k))

 def rel_shift(self, x: Tensor) -> Tensor:
  """Сдвиг позиционных эмбеддингов"""
  b, h, qlen, pos_len = x.size()
  x = torch.nn.functional.pad(x, pad=(1, 0))
  x = x.view(b, h, -1, qlen)
  return x[:, :, 1:].view(b, h, qlen, pos_len)

 def forward(self, query: Tensor, key: Tensor, value: Tensor, pos_emb: Tensor, mask: Optional[Tensor] = None) -> Tensor:
  q, k, v = self.forward_qkv(query, key, value)
  q = q.transpose(1, 2)

  # Позиционные эмбеддинги
  p = self.linear_pos(pos_emb)
  p = p.view(pos_emb.shape[0], -1, self.h, self.d_k).transpose(1, 2)

  # Добавляем позиционные смещения
  q_with_bias_u = (q + self.pos_bias_u).transpose(1, 2)
  q_with_bias_v = (q + self.pos_bias_v).transpose(1, 2)

  # Вычисляем attention scores
  matrix_bd = torch.matmul(q_with_bias_v, p.transpose(-2, -1))
  matrix_bd = self.rel_shift(matrix_bd)
  matrix_ac = torch.matmul(q_with_bias_u, k.transpose(-2, -1))
  matrix_bd = matrix_bd[:, :, :, : matrix_ac.size(-1)]

  scores = (matrix_ac + matrix_bd) / math.sqrt(self.d_k)

  return self.forward_attention(v, scores, mask)


class RotaryPositionMultiHeadAttention(MultiHeadAttention):
 """Attention с rotary позиционными эмбеддингами"""

 def forward(self, query: Tensor, key: Tensor, value: Tensor, pos_emb: List[Tensor], mask: Optional[Tensor] = None) -> Tensor:
  b, t, _ = value.size()

  # Подготавливаем Q, K, V
  query = query.transpose(0, 1).view(t, b, self.h, self.d_k)
  key = key.transpose(0, 1).view(t, b, self.h, self.d_k)
  value = value.transpose(0, 1).view(t, b, self.h, self.d_k)

  # Применяем rotary позиционные эмбеддинги
  cos, sin = pos_emb
  query, key = apply_rotary_pos_emb(query, key, cos, sin, offset=0)

  # Преобразуем обратно
  q, k, v = self.forward_qkv(
   query.view(t, b, self.h * self.d_k).transpose(0, 1),
   key.view(t, b, self.h * self.d_k).transpose(0, 1),
   value.view(t, b, self.h * self.d_k).transpose(0, 1)
  )

  # Вычисляем attention scores
  scores = torch.matmul(q, k.transpose(-2, -1) / math.sqrt(self.d_k))

  return self.forward_attention(v, scores, mask)


class PositionalEncoding(nn.Module, ABC):
 """Абстрактный класс для позиционного кодирования"""

 def __init__(self, dim: int, base: int):
  super().__init__()
  self.dim = dim
  self.base = base

 @abstractmethod
 def create_pe(self, length: int, device: torch.device) -> Optional[Tensor]:
  pass

 def extend_pe(self, length: int, device: torch.device):
  """Расширяет позиционные эмбеддинги если нужно"""
  pe = self.create_pe(length, device)
  if pe is None:
   return
  if hasattr(self, "pe"):
   self.pe = pe
  else:
   self.register_buffer("pe", pe, persistent=False)


class RelPositionalEmbedding(PositionalEncoding):
 """Относительные позиционные эмбеддинги"""

 def create_pe(self, length: int, device: torch.device) -> Optional[Tensor]:
  if hasattr(self, "pe") and self.pe.shape[1] >= 2 * length - 1:
   return None

  positions = torch.arange(length - 1, -length, -1, device=device).unsqueeze(1)
  pos_length = positions.size(0)
  pe = torch.zeros(pos_length, self.dim, device=positions.device)

  # Синусоидальное кодирование
  div_term = torch.exp(torch.arange(0, self.dim, 2, device=pe.device) * -(math.log(10000.0) / self.dim))
  pe[:, 0::2] = torch.sin(positions * div_term)
  pe[:, 1::2] = torch.cos(positions * div_term)

  return pe.unsqueeze(0)

 def forward(self, x: torch.Tensor) -> Tuple[Tensor, Tensor]:
  input_len = x.size(1)
  center_pos = self.pe.size(1) // 2 + 1
  start_pos = center_pos - input_len
  end_pos = center_pos + input_len - 1

  return x, self.pe[:, start_pos:end_pos]


class RotaryPositionalEmbedding(PositionalEncoding):
 """Rotary позиционные эмбеддинги"""

 def create_pe(self, length: int, device: torch.device) -> Optional[Tensor]:
  if hasattr(self, "pe") and self.pe.size(0) >= 2 * length:
   return None

  positions = torch.arange(0, length, dtype=torch.float32, device=device)
  inv_freq = 1.0 / (self.base ** (torch.arange(0, self.dim, 2).float() / self.dim))
  t = torch.arange(length, device=positions.device).type_as(inv_freq)

  freqs = torch.einsum("i,j->ij", t, inv_freq)
  emb = torch.cat((freqs, freqs), dim=-1).to(positions.device)

  return torch.cat([emb.cos()[:, None, None, :], emb.sin()[:, None, None, :]])

 def forward(self, x: torch.Tensor) -> Tuple[Tensor, List[Tensor]]:
  cos_emb = self.pe[0: x.shape[1]]
  half_pe = self.pe.shape[0] // 2
  sin_emb = self.pe[half_pe: half_pe + x.shape[1]]

  return x, [cos_emb, sin_emb]


class ConformerConvolution(nn.Module):
 """Сверточный модуль Conformer"""

 def __init__(self, d_model: int, kernel_size: int, norm_type: str):
  super().__init__()
  assert (kernel_size - 1) % 2 == 0
  assert norm_type in ["batch_norm", "layer_norm"]

  self.norm_type = norm_type
  self.pointwise_conv1 = nn.Conv1d(d_model, d_model * 2, kernel_size=1)
  self.depthwise_conv = nn.Conv1d(   in_channels=d_model,   out_channels=d_model,
   kernel_size=kernel_size,   padding=(kernel_size - 1) // 2,   groups=d_model,  bias=True  )
  self.batch_norm = nn.BatchNorm1d(d_model) if norm_type == "batch_norm" else nn.LayerNorm(d_model)
  self.activation = nn.SiLU()
  self.pointwise_conv2 = nn.Conv1d(d_model, d_model, kernel_size=1)

 def forward(self, x: Tensor, pad_mask: Optional[Tensor] = None) -> Tensor:
  x = x.transpose(1, 2)
  x = self.pointwise_conv1(x)
  x = nn.functional.glu(x, dim=1)  # Gated Linear Unit

  if pad_mask is not None:
   x = x.masked_fill(pad_mask.unsqueeze(1), 0.0)

  x = self.depthwise_conv(x)

  if self.norm_type == "batch_norm":
   x = self.batch_norm(x)
  else:
   x = self.batch_norm(x.transpose(1, 2)).transpose(1, 2)

  x = self.activation(x)
  x = self.pointwise_conv2(x)

  return x.transpose(1, 2)


class ConformerFeedForward(nn.Module):
 """FeedForward слой Conformer"""

 def __init__(self, d_model: int, d_ff: int, use_bias=True):
  super().__init__()
  self.linear1 = nn.Linear(d_model, d_ff, bias=use_bias)
  self.activation = nn.SiLU()
  self.linear2 = nn.Linear(d_ff, d_model, bias=use_bias)

 def forward(self, x: Tensor) -> Tensor:
  return self.linear2(self.activation(self.linear1(x)))


class ConformerLayer(nn.Module):
 """Один слой Conformer архитектуры"""

 def __init__(self, d_model: int, d_ff: int, self_attention_model: str,
              n_heads: int = 16, conv_norm_type: str = "batch_norm",
              conv_kernel_size: int = 31):
  super().__init__()
  self.fc_factor = 0.5

  # FeedForward 1
  self.norm_feed_forward1 = nn.LayerNorm(d_model)
  self.feed_forward1 = ConformerFeedForward(d_model=d_model, d_ff=d_ff)

  # Self-Attention
  self.norm_self_att = nn.LayerNorm(d_model)
  if self_attention_model == "rotary":
   self.self_attn: nn.Module = RotaryPositionMultiHeadAttention(n_head=n_heads, n_feat=d_model)
  else:
   self.self_attn = RelPositionMultiHeadAttention(n_head=n_heads, n_feat=d_model)

  # Convolution
  self.norm_conv = nn.LayerNorm(d_model)
  self.conv = ConformerConvolution(d_model=d_model, kernel_size=conv_kernel_size, norm_type=conv_norm_type)

  # FeedForward 2
  self.norm_feed_forward2 = nn.LayerNorm(d_model)
  self.feed_forward2 = ConformerFeedForward(d_model=d_model, d_ff=d_ff)

  # Output
  self.norm_out = nn.LayerNorm(d_model)

 def forward(self, x: Tensor, pos_emb: Union[Tensor, List[Tensor]],
             att_mask: Optional[Tensor] = None, pad_mask: Optional[Tensor] = None) -> Tensor:
  residual = x

  # FeedForward 1
  x = self.norm_feed_forward1(x)
  x = self.feed_forward1(x)
  residual = residual + x * self.fc_factor

  # Self-Attention
  x = self.norm_self_att(residual)
  x = self.self_attn(x, x, x, pos_emb, mask=att_mask)
  residual = residual + x

  # Convolution
  x = self.norm_conv(residual)
  x = self.conv(x, pad_mask=pad_mask)
  residual = residual + x

  # FeedForward 2
  x = self.norm_feed_forward2(residual)
  x = self.feed_forward2(x)
  residual = residual + x * self.fc_factor

  # Output
  x = self.norm_out(residual)

  return x


class ConformerEncoder(nn.Module):
 """Conformer энкодер"""

 def __init__(self, feat_in: int = 64, n_layers: int = 16, d_model: int = 768,
              subsampling_factor: int = 4, ff_expansion_factor: int = 4,
              self_attention_model: str = "rotary", n_heads: int = 16,
              pos_emb_max_len: int = 5000, conv_kernel_size: int = 31,
              subsampling=None, subs_kernel_size=None, conv_norm_type=None, **kwargs):
  super().__init__()
  self.feat_in = feat_in
  assert self_attention_model in ["rotary", "rel_pos"], f"Not supported attn = {self_attention_model}"

  # Параметры по умолчанию
  subsampling = subsampling if subsampling is not None else kwargs.get("subsampling", "conv2d")
  subs_kernel_size = subs_kernel_size if subs_kernel_size is not None else kwargs.get("subs_kernel_size", 3)
  conv_norm_type = conv_norm_type if conv_norm_type is not None else kwargs.get("conv_norm_type", "batch_norm")

  # Субсэмплирование
  self.pre_encode = StridingSubsampling( subsampling=subsampling,
   kernel_size=subs_kernel_size, subsampling_factor=subsampling_factor,
   feat_in=feat_in, feat_out=d_model,  conv_channels=d_model  )

  self.pos_emb_max_len = pos_emb_max_len

  # Позиционное кодирование
  if self_attention_model == "rotary":
   self.pos_enc: PositionalEncoding = RotaryPositionalEmbedding(d_model // n_heads, pos_emb_max_len)
  else:
   self.pos_enc = RelPositionalEmbedding(d_model, pos_emb_max_len)

  # Слои Conformer
  self.layers = nn.ModuleList()
  for _ in range(n_layers):
   layer = ConformerLayer(  d_model=d_model,  d_ff=d_model * ff_expansion_factor,
    self_attention_model=self_attention_model,
    n_heads=n_heads,  conv_norm_type=conv_norm_type,  conv_kernel_size=conv_kernel_size  )
   self.layers.append(layer)

 def forward(self, audio_signal: Tensor, length: Tensor) -> Tuple[Tensor, Tensor]:
  # Инициализируем позиционные эмбеддинги при первом запуске
  if not hasattr(self.pos_enc, "pe"):
   self.pos_enc.extend_pe(self.pos_emb_max_len, audio_signal.device)

  # Субсэмплирование
  audio_signal, length = self.pre_encode(x=audio_signal.transpose(1, 2), lengths=length)
  max_len = audio_signal.size(1)

  # Позиционное кодирование
  audio_signal, pos_emb = self.pos_enc(x=audio_signal)

  # Маски
  pad_mask = torch.arange(0, max_len, device=audio_signal.device).expand(length.size(0), -1) < length.unsqueeze(-1)
  att_mask = None

  if audio_signal.shape[0] > 1:
   att_mask = pad_mask.unsqueeze(1).repeat([1, max_len, 1])
   att_mask = torch.logical_and(att_mask, att_mask.transpose(1, 2))
   att_mask = ~att_mask

  pad_mask = ~pad_mask

  # Проходим через все слои
  for layer in self.layers:
   audio_signal = layer(x=audio_signal, pos_emb=pos_emb, att_mask=att_mask, pad_mask=pad_mask)

  return audio_signal.transpose(1, 2), length

def get_pipeline() -> Pipeline:
 """Создает или возвращает кэшированный VAD пайплайн"""
 global _PIPELINE
 if _PIPELINE is not None:
  return _PIPELINE

 # Требуется токен HuggingFace
 try:
  hf_token = os.environ["HF_TOKEN"]
 except KeyError as exc:
  raise ValueError("HF_TOKEN environment variable is not set") from exc

 # Безопасная загрузка модели
 with torch.serialization.safe_globals([TorchVersion, Problem, Specifications, Resolution]):
  model = Model.from_pretrained("pyannote/segmentation-3.0", token=hf_token)

 _PIPELINE = VoiceActivityDetection(segmentation=model)
 _PIPELINE.instantiate({"min_duration_on": 0.0, "min_duration_off": 0.0})

 return _PIPELINE
 '''
    def segment_audio_file(wav_input, sr, 
                           max_duration: float = 22.0,  # ← максимальная длительность сегмента
                           min_duration: float = 15.0,  # ← минимальная длительность
                           strict_limit_duration: float = 30.0,  # ← лимит для принудительного разбиения
                           new_chunk_threshold: float = 0.2):  # ← порог для нового чанка
    Что настроить:
    new_chunk_threshold - увеличить с 0.2 до 0.5-1.0 секунды
    max_duration - уменьшить с 22.0 до 15.0-18.0 секунд
    Для твоей речи:  Паузы могут быть длиннее обычных →
    слишком большой min_duration заставляет модель тащить сегмент дальше, даже когда качество уже падает.
    
    🟢 Оптимум: 6–8 секунд    3️⃣ strict_limit_duration
    strict_limit_duration: float = 60.0        
    Что это:   Жёсткий потолок.
    Если VAD “залип” и не видит пауз — сегмент принудительно режется.
    
    🔴 60 секунд — слишком опасно   🟢 Оптимум: 20–25 секунд
    
    4️⃣ new_chunk_threshold    new_chunk_threshold: float = 0.6     
    Самый важный параметр для тебя.    Что это:
    Минимальная пауза (в секундах), которая считается “настоящей”.
     меньше → игнорируется    больше → можно закрывать сегмент
    
    При ДЦП:    паузы часто неровные
    
    есть микро-остановки    дыхание может сбивать VAD
    
    🔴 0.2–0.3 → модель режет слишком часто
    🟢 0.8–1.2 → модель терпеливее, но не тянет до деградации
    
    🔧 Рекомендованные настройки именно для тебя
    ⭐ Баланс качества и стабильности (РЕКОМЕНДУЮ)
segments, boundaries = segment_audio_file(
    audio_data,
    sr=SAMPLE_RATE,
    max_duration=16.0,          # ключевое: не даём модели "уставать"
    min_duration=7.0,           # принимаем короткие фразы
    strict_limit_duration=22.0, # страховка от деградации
    new_chunk_threshold=1.0     # игнорируем микропаузы
)

🧠 Максимальное качество (если хватает CPU / RAM)
segments, boundaries = segment_audio_file(
    audio_data,
    sr=SAMPLE_RATE,
    max_duration=14.0,
    min_duration=6.0,
    strict_limit_duration=18.0,
    new_chunk_threshold=1.2
)
'''
 #Максимальное качество (если хватает CPU / RAM)

def segment_audio_file(wav_input: Union[np.ndarray, Tensor], sr: int,
                       max_duration: float = 10.0, min_duration: float = 50.0,
                       strict_limit_duration: float = 20.0, new_chunk_threshold: float = 1.0) -> Tuple[List[torch.Tensor], List[Tuple[float, float]]]:
 """Сегментирует аудио на фрагменты по голосовой активности"""
 if isinstance(wav_input, np.ndarray):
  audio = torch.from_numpy(wav_input.copy()).float()
 elif isinstance(wav_input, Tensor):
  audio = wav_input.float().clone()
 else:
  raise TypeError(f"Unsupported input type for VAD: {type(wav_input)}. Expected np.ndarray or Tensor.")
 if audio.ndim > 1:
  audio = audio.flatten()

 # Используем VAD для обнаружения речи
 pipeline = get_pipeline()
 sad_segments = pipeline({"waveform": audio.unsqueeze(0), "sample_rate": sr})

 segments: List[torch.Tensor] = []
 curr_duration = 0.0
 curr_start = 0.0
 curr_end = 0.0
 boundaries: List[Tuple[float, float]] = []

 def _update_segments(curr_start: float, curr_end: float, curr_duration: float):
  """Обрабатывает сегмент и разбивает если слишком длинный"""
  if curr_duration > strict_limit_duration:
   # Разбиваем слишком длинные сегменты
   max_segments = int(curr_duration / strict_limit_duration) + 1
   segment_duration = curr_duration / max_segments
   curr_end = curr_start + segment_duration

   for _ in range(max_segments - 1):
    segments.append(audio[int(curr_start * sr): int(curr_end * sr)])
    boundaries.append((curr_start, curr_end))
    curr_start = curr_end
    curr_end += segment_duration

  segments.append(audio[int(curr_start * sr): int(curr_end * sr)])
  boundaries.append((curr_start, curr_end))

 # Объединяем сегменты по правилам
 for segment in sad_segments.get_timeline().support():
  start = max(0, segment.start)
  end = min(audio.shape[0] / sr, segment.end)

  if curr_duration > new_chunk_threshold and (curr_duration + (end - curr_end) > max_duration or curr_duration > min_duration):
   _update_segments(curr_start, curr_end, curr_duration)
   curr_start = start

  curr_end = end
  curr_duration = curr_end - curr_start

 # Добавляем последний сегмент
 if curr_duration > new_chunk_threshold:
  _update_segments(curr_start, curr_end, curr_duration)
 return segments, boundaries

def infer_onnx(wav_input: Union[str, np.ndarray, Tensor], model_cfg: omegaconf.DictConfig,
               sessions: List[rt.InferenceSession], preprocessor: Optional[FeatureExtractor] = None,
               tokenizer: Optional[Tokenizer] = None, sample_rate: int = 16000) -> Union[str, np.ndarray]:
 """Инференс через ONNX Runtime (быстрее для CPU)"""
 model_name = model_cfg.model_name

 if preprocessor is None:
  preprocessor = FeatureExtractor(  sample_rate=16000,
   features=model_cfg.preprocessor.features  )

 if tokenizer is None and ("ctc" in model_name or "rnnt" in model_name):
  tokenizer = Tokenizer(   model_cfg.decoding.vocabulary,
   model_cfg.decoding.get("model_path")  )

 input_signal = load_audio(wav_input, sample_rate=sample_rate)
 input_signal = preprocessor(input_signal.unsqueeze(0), torch.tensor([input_signal.shape[-1]]))[0].numpy()

 # Инференс энкодера
 enc_sess = sessions[0]
 enc_inputs = {node.name: data for (node, data) in zip(
  enc_sess.get_inputs(),
  [input_signal.astype(DTYPE), [input_signal.shape[-1]]]
 )}
 enc_features = enc_sess.run([node.name for node in enc_sess.get_outputs()], enc_inputs)[0]

 # Возвращаем эмбеддинги для эмокций или SSL
 if "emo" in model_name or "ssl" in model_name:
  return enc_features

 blank_idx = len(tokenizer)
 token_ids = []
 prev_token = blank_idx

 # CTC декодирование
 if "ctc" in model_name:
  prev_tok = blank_idx
  for tok in enc_features.argmax(-1).squeeze().tolist():
   if (tok != prev_tok or prev_tok == blank_idx) and tok != blank_idx:
    token_ids.append(tok)
   prev_tok = tok
 # RNN-T декодирование
 else:
  pred_states = [
   np.zeros(shape=(1, 1, model_cfg.head.decoder.pred_hidden), dtype=DTYPE),
   np.zeros(shape=(1, 1, model_cfg.head.decoder.pred_hidden), dtype=DTYPE)
  ]
  pred_sess, joint_sess = sessions[1:]

  for j in range(enc_features.shape[-1]):
   emitted_letters = 0
   while emitted_letters < MAX_LETTERS_PER_FRAME:
    pred_inputs = {node.name: data for (node, data) in zip(
     pred_sess.get_inputs(),
     [np.array([[prev_token]])] + pred_states
    )}
    pred_outputs = pred_sess.run([node.name for node in pred_sess.get_outputs()], pred_inputs)

    joint_inputs = {node.name: data for node, data in zip(
     joint_sess.get_inputs(),
     [enc_features[:, :, [j]], pred_outputs[0].swapaxes(1, 2)]
    )}
    log_probs = joint_sess.run([node.name for node in joint_sess.get_outputs()], joint_inputs)

    token = log_probs[0].argmax(-1)[0][0]
    if token != blank_idx:
     prev_token = int(token)
     pred_states = pred_outputs[1:]
     token_ids.append(int(token))
     emitted_letters += 1
    else:
     break
 return tokenizer.decode(token_ids)

def load_onnx(onnx_dir: str, model_version: str) -> Tuple[List[rt.InferenceSession], Union[omegaconf.DictConfig, omegaconf.ListConfig]]:
 """Загружает ONNX модель для быстрого CPU инференса"""
 opts = rt.SessionOptions()
 opts.intra_op_num_threads = 16  # Используем больше потоков
 opts.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
 opts.log_severity_level = 3  # Только ошибки

 model_cfg = omegaconf.OmegaConf.load(f"{onnx_dir}/{model_version}.yaml")

 # Загружаем в зависимости от типа модели
 if "rnnt" not in model_version and "ssl" not in model_version:
  model_path = f"{onnx_dir}/{model_version}.onnx"
  sessions = [rt.InferenceSession(model_path, providers=["CPUExecutionProvider"], sess_options=opts)]
 elif "ssl" in model_version:
  pth = f"{onnx_dir}/{model_version}"
  enc_sess = rt.InferenceSession(f"{pth}_encoder.onnx", providers=["CPUExecutionProvider"], sess_options=opts)
  sessions = [enc_sess]
 else:
  pth = f"{onnx_dir}/{model_version}"
  enc_sess = rt.InferenceSession(f"{pth}_encoder.onnx", providers=["CPUExecutionProvider"], sess_options=opts)
  pred_sess = rt.InferenceSession(f"{pth}_decoder.onnx", providers=["CPUExecutionProvider"], sess_options=opts)
  joint_sess = rt.InferenceSession(f"{pth}_joint.onnx", providers=["CPUExecutionProvider"], sess_options=opts)
  sessions = [enc_sess, pred_sess, joint_sess]

 return sessions, model_cfg

def rtt_half(x: Tensor) -> Tensor:
 """Rotary преобразование для половины вектора"""
 x1, x2 = x[..., : x.shape[-1] // 2], x[..., x.shape[-1] // 2:]
 return torch.cat([-x2, x1], dim=x1.ndim - 1)

def apply_rotary_pos_emb(q: Tensor, k: Tensor, cos: Tensor, sin: Tensor, offset: int = 0) -> Tuple[Tensor, Tensor]:
 """Применяет rotary позиционные эмбеддинги"""
 cos, sin = (cos[offset: q.shape[0] + offset, ...], sin[offset: q.shape[0] + offset, ...])
 return (q * cos) + (rtt_half(q) * sin), (k * cos) + (rtt_half(k) * sin)

class GigaAM(nn.Module):
 """Базовый класс для моделей GigaAM"""

 def __init__(self, cfg: omegaconf.DictConfig):
  super().__init__()
  self.cfg = cfg

  # Быстрая инициализация без hydra
  self.preprocessor = FeatureExtractor(
   sample_rate=cfg.preprocessor.sample_rate,
   features=cfg.preprocessor.features,
   hop_length=cfg.preprocessor.get("hop_length"),
   win_length=cfg.preprocessor.get("win_length"),
   n_fft=cfg.preprocessor.get("n_fft"),
   center=cfg.preprocessor.get("center", True)
  )

  self.encoder = ConformerEncoder(**cfg.encoder)

 def forward(self, features: Tensor, feature_lengths: Tensor) -> Tuple[Tensor, Tensor]:
  """Прямой проход модели"""
  features, feature_lengths = self.preprocessor(features, feature_lengths)
  return self.encoder(features, feature_lengths)

 def prepare_wav(self, wav_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE) -> Tuple[Tensor, Tensor]:
  """Подготавливает аудио для модели"""
  if isinstance(wav_input, str):
   wav = load_audio(wav_input)
   current_sr = SAMPLE_RATE
  elif isinstance(wav_input, np.ndarray):
   if wav_input.size == 0:
    raise ValueError("Audio array is empty")
   wav = torch.from_numpy(wav_input.copy()).float()
   current_sr = sample_rate
   if wav.ndim > 1:
    wav = wav.flatten()
   max_val = wav.abs().max()
   if max_val > 0:
    if max_val > 32768.0:
     wav = wav / 32768.0
    elif max_val > 1.0:
     wav = wav / max_val
  elif isinstance(wav_input, Tensor):
   if wav_input.numel() == 0:
    raise ValueError("Audio tensor is empty")
   wav = wav_input.float().clone()
   current_sr = sample_rate
   if wav.ndim > 1:
    wav = wav.flatten()
   max_val = wav.abs().max()
   if max_val > 0:
    if max_val > 32768.0:
     wav = wav / 32768.0
    elif max_val > 1.0:
     wav = wav / max_val
  else:
   raise TypeError(f"Unsupported input type: {type(wav_input)}. Expected str, np.ndarray, or Tensor.")

  # Ресемплирование если нужно
  if not isinstance(wav_input, str) and current_sr != SAMPLE_RATE:
   if wav.numel() > 0:
    wav = taF.resample(wav.unsqueeze(0), orig_freq=current_sr, new_freq=SAMPLE_RATE).squeeze(0)

  # Проверка минимальной длины
  min_length = int(SAMPLE_RATE * 0.1)
  if wav.numel() < min_length:
   raise ValueError(f"Audio is too short: {wav.numel()} samples. Minimum required: {min_length} samples (~0.1 seconds at {SAMPLE_RATE}Hz)")

  wav = wav.unsqueeze(0)
  length = torch.full([1], wav.shape[-1])
  return wav, length

class GigaAMASR(GigaAM):# Модель для распознавания речи"""
 def __init__(self, cfg: omegaconf.DictConfig):
  super().__init__(cfg)

  # Быстрая инициализация головы
  if "ctc" in cfg.model_name:
   self.head = CTCHead(cfg.head.feat_in, cfg.head.num_classes)
   self.decoding = CTCGreedyDecoding(cfg.decoding.vocabulary, cfg.decoding.get("model_path"))
  else:
   self.head = RNNTHead(cfg.head.decoder, cfg.head.joint)
   self.decoding = RNNTGreedyDecoding(cfg.decoding.vocabulary, cfg.decoding.get("model_path"))

 @torch.inference_mode()
 def transcribe(self, wav_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE, **kwargs) -> Union[str, List[Dict[str, Union[str, Tuple[float, float]]]]]:
  """Транскрибирует аудио в текст"""
  if isinstance(wav_input, str):
   audio_data = load_audio(wav_input, sample_rate=sample_rate)
  elif isinstance(wav_input, np.ndarray):
   audio_data = torch.from_numpy(wav_input.copy()).float()
   if audio_data.ndim > 1:
    audio_data = audio_data.flatten()
  elif isinstance(wav_input, Tensor):
   audio_data = wav_input.float().clone()
   if audio_data.ndim > 1:
    audio_data = audio_data.flatten()
  else:
   raise TypeError(f"Unsupported input type: {type(wav_input)}. Expected str, np.ndarray, or Tensor.")

  # Проверяем длину аудио
  audio_length = audio_data.shape[-1]

  # Для коротких аудио обрабатываем целиком
  if audio_length <= LONGFORM_THRESHOLD:
   wav, length = self.prepare_wav(wav_input, sample_rate=sample_rate)
   encoded, encoded_len = self.forward(wav, length)
   return self.decoding.decode(self.head, encoded, encoded_len)[0]
  # Для длинных аудио сегментируем
  else:
   print("long")
   transcribed_segments = []
   segments, boundaries = segment_audio_file(audio_data, SAMPLE_RATE, **kwargs)

   for segment, segment_boundaries in zip(segments, boundaries):
    wav = segment.unsqueeze(0)
    length = torch.full([1], wav.shape[-1])
    encoded, encoded_len = self.forward(wav, length)
    result = self.decoding.decode(self.head, encoded, encoded_len)[0]
    transcribed_segments.append({
     "transcription": result,
     "boundaries": segment_boundaries
    })

   return transcribed_segments

def _download_file(file_url: str, file_path: str, force: bool = False) -> str:
 # Скачивает файл с прогресс-баром"""
 if os.path.exists(file_path) and not force:
  return file_path

 os.makedirs(os.path.dirname(file_path), exist_ok=True)

 with urllib.request.urlopen(file_url) as source, open(file_path, "wb") as output:
  with tqdm(total=int(source.info().get("Content-Length", 0)),
            ncols=80, unit="iB", unit_scale=True, unit_divisor=1024) as loop:
   while True:
    buffer = source.read(8192)
    if not buffer:
     break
    output.write(buffer)
    loop.update(len(buffer))
 return file_path

def _download_model(model_name: str, download_root: str, force: bool = False) -> Tuple[str, str]:
 """Скачивает модель если её нет"""
 short_names = ["ctc", "rnnt", "e2e_ctc", "e2e_rnnt", "ssl"]
 possible_names = short_names + list(_MODEL_HASHES.keys())

 if model_name not in possible_names:
  raise ValueError(f"Model '{model_name}' not found. Available model names: {possible_names}")

 if model_name in short_names:
  model_name = f"v3_{model_name}"

 model_url = f"{_URL_DIR}/{model_name}.ckpt"
 model_path = os.path.join(download_root, f"{model_name}.ckpt")

 if os.path.exists(model_path) and not force:
  logging.info(f"Model found at {model_path}, skipping download.")
 else:
  logging.info(f"Downloading model to {model_path}")
 return model_name, _download_file(model_url, model_path, force)

def _download_tokenizer(model_name: str, download_root: str, force: bool = False) -> Optional[str]:
 # Скачивает токенизатор если нужно
 if model_name != "v1_rnnt" and "e2e" not in model_name:
  return None
 tokenizer_url = f"{_URL_DIR}/{model_name}_tokenizer.model"
 tokenizer_path = os.path.join(download_root, f"{model_name}_tokenizer.model")

 if os.path.exists(tokenizer_path) and not force:
  logging.info(f"Tokenizer found at {tokenizer_path}, skipping download.")
 else:
  logging.info(f"Downloading tokenizer to {tokenizer_path}")

 return _download_file(tokenizer_url, tokenizer_path, force)

def check_model_exists(model_name: str, download_root: str) -> bool:
 # Проверяет существует ли модель"""
 short_names = ["ctc", "rnnt", "e2e_ctc", "e2e_rnnt", "ssl"]
 if model_name in short_names:
  model_name = f"v3_{model_name}"

 model_path = os.path.join(download_root, f"{model_name}.ckpt")
 if not os.path.exists(model_path):
  return False

 # Проверяем хэш если есть в словаре
 expected_hash = _MODEL_HASHES.get(model_name)
 if expected_hash:
  actual_hash = hashlib.md5(open(model_path, "rb").read()).hexdigest()
  if actual_hash != expected_hash:
   logging.warning(f"Model exists but hash mismatch: expected {expected_hash}, got {actual_hash}")
   return False
 return True

def _normalize_device(device: Optional[Union[str, torch.device]]) -> torch.device:
 """Нормализует устройство - всегда возвращает CPU"""
 return torch.device("cpu")

class GigaAMEmo(GigaAM):# Модель для распознавания эмоций"""
 def __init__(self, cfg: omegaconf.DictConfig):
  super().__init__(cfg)
  self.head = nn.Linear(cfg.head.in_features, cfg.head.out_features)
  self.id2name = cfg.id2name

 def get_probs(self, wav_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE) -> Dict[str, float]:
  """Определяет эмоции в аудио"""
  wav, length = self.prepare_wav(wav_input, sample_rate=sample_rate)
  encoded, _ = self.forward(wav, length)
  # Пулинг по времени
  encoded_pooled = nn.functional.avg_pool1d(encoded, kernel_size=encoded.shape[-1]).squeeze(-1)
  logits = self.head(encoded_pooled)[0]
  # Вероятности эмоций
  probs = nn.functional.softmax(logits, dim=-1).detach().tolist()
  return {self.id2name[i]: probs[i] for i in range(len(self.id2name))}

def load_model( model_name: str, download_root: Optional[str] = None,  # 4. Корневой каталог для загрузки моделей
  force_download: bool = False,  # 5. Принудительная перезагрузка модели
  fp16_encoder: bool = True,  # 1. Игнорируется, т.к. FP16 полезен только на GPU
  use_flash: Optional[bool] = False,  # 2. Игнорируется, т.к. FlashAttention не поддерживается на CPU
  device: Optional[Union[str, torch.device]] = None  ) -> Union[GigaAM, GigaAMEmo, GigaAMASR]: # 3. Игнорируется, модель всегда загружается на CPU
 """ Быстрая загрузка модели для CPU
 Args:
     model_name: Имя модели (ctc, rnnt, emo, ssl и т.д.)
     download_root: Каталог для загрузки моделей
     fp16_encoder: Игнорируется (только для GPU)
     use_flash: Игнорируется (FlashAttention не поддерживается на CPU)
     device: Игнорируется (модель всегда загружается на CPU)
     force_download: Принудительно перезагрузить модель

 Returns:
     Загруженная и готовая к использованию модель
 """
 if download_root is None:
  raise ValueError("download_root must be specified")
 os.makedirs(download_root, exist_ok=True)

 device_obj = torch.device("cpu") # Всегда используем CPU для совместимости

 # Проверяем и скачиваем модель если нужно
 if not check_model_exists(model_name, download_root) or force_download:
  _download_model(model_name, download_root, force_download)

 model_name, model_path = _download_model(model_name, download_root, force_download)
 tokenizer_path = _download_tokenizer(model_name, download_root, force_download)

 # Проверяем хэш модели
 if os.path.exists(model_path):
  actual_hash = hashlib.md5(open(model_path, "rb").read()).hexdigest()
  expected_hash = _MODEL_HASHES.get(model_name)
  if expected_hash and actual_hash != expected_hash:
   if force_download:
    logging.warning(f"Model hash mismatch: expected {expected_hash}, got {actual_hash}. Re-downloading...")
    os.remove(model_path)
    model_name, model_path = _download_model(model_name, download_root, True)
   else:
    raise RuntimeError(
     f"Model checksum failed for {model_name}. "
     f"Expected {expected_hash}, got {actual_hash}. "
     f"Please delete {model_path} and reload the model, "
     f"or use force_download=True to re-download automatically."  )

 if not os.path.exists(model_path):
  raise FileNotFoundError(f"Model file not found: {model_path}. Please check the download directory.")

 # Быстрая загрузка без лишних проверок
 with warnings.catch_warnings():
  warnings.simplefilter("ignore", category=(FutureWarning))
  checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)

 # Оптимизация для CPU
 cfg = checkpoint["cfg"]

 # Отключаем GPU-специфичные функции
 if "encoder" in cfg:
  cfg.encoder.flash_attn = False  # FlashAttention не работает на CPU
  cfg.encoder.fp16 = False  # FP16 не поддерживается на CPU

 # Заменяем hydra на прямую инициализацию для скорости
 if "preprocessor" in cfg:
  cfg.preprocessor["_target_"] = "sber_gegaam.FeatureExtractor"

 if "encoder" in cfg:
  cfg.encoder["_target_"] = "sber_gegaam.ConformerEncoder"

 # Добавляем токенизатор если нужно
 if tokenizer_path is not None and "decoding" in cfg:
  cfg.decoding.model_path = tokenizer_path

 # Создаем нужный тип модели
 if "ssl" in model_name:
  model = GigaAM(cfg)
 elif "emo" in model_name:
  model = GigaAMEmo(cfg)
 else:
  model = GigaAMASR(cfg)

 # Быстрая загрузка весов
 model.load_state_dict(checkpoint["state_dict"], strict=True)
 model.eval()

 # Оптимизация памяти для CPU
 torch.set_num_threads(min(8, os.cpu_count() or 8))  # Ограничиваем потоки для предсказуемой производительности

 # Отключаем autograd для инференса
 for param in model.parameters():
  param.requires_grad = False
 try: # Компилируем модель для ускорения (PyTorch 2.0+)
  if hasattr(torch, 'compile'):
   model = torch.compile(model, mode="reduce-overhead")
 except:
  pass  # Если компиляция не поддерживается, работаем как есть
 cfg.model_name = model_name
 return model.to(device_obj)


# Экспорт основных функций
__all__ = ["GigaAM", "GigaAMASR", "GigaAMEmo", "load_audio", "load_model"]