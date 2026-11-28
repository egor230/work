import hashlib, json, logging, math, os, urllib.request, warnings, numpy as np, onnxruntime as rt, torch, torch.nn.functional as F, torchaudio, torchaudio.functional as taF, omegaconf
from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Dict, List, Optional, Tuple, Union
from torch import Tensor, nn
from torch.jit import TracerWarning
from sentencepiece import SentencePieceProcessor
from tqdm import tqdm

# Константы
SAMPLE_RATE = 16000
LONGFORM_THRESHOLD = 35 * SAMPLE_RATE
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
	"multilingual_ctc": "5379d887c53ccd9cb95981e2a1832720",
	"multilingual_ssl": "af54fed7a0337eeae7c4a25b2f8779c8",
	"multilingual_large_ctc": "79a9adde50dd7f35bbf70927cb6557d0",
	"multilingual_large_ssl": "2ef65a2ca413f6e1f99a4df0e86c1cee",
	# Новое поколение (27.11.2026): Zapformer + двойные головы raw/e2e
	"v4_ctc": "7f81bb7c82588bf3f6956e9ca6ce9451",
	"v4_rnnt": "af1027b4fa8b306c7aa1974e4b740fe0",
	"v4_ssl": "22f509eba66cd723e06995e650ae99e8",
	"multilingual_v2_rnnt": "4c24acddcf2f81d512563067b40ca36d",
	"multilingual_v2_ssl": "ea8a54fb545b2e0f89a7f23dd9bcd807",
}

# Для этих моделей CDN хранит два токенизатора: raw и e2e
_DUAL_TOKENIZER_MODELS = {"v4_rnnt", "v4_ctc", "multilingual_v2_rnnt"}

_PIPELINE = None
warnings.simplefilter("ignore", category=UserWarning)


def load_audio(audio_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE) -> Tensor:
	"""Загружает аудио из файла, массива или тензора и нормализует до 16кГц"""
	if isinstance(audio_input, str):
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

	if audio_tensor.ndim > 1:
		audio_tensor = audio_tensor.flatten()

	if sample_rate != SAMPLE_RATE:
		if audio_tensor.numel() > 0:
			audio_tensor = taF.resample(audio_tensor.unsqueeze(0), orig_freq=sample_rate, new_freq=SAMPLE_RATE).squeeze(0)

	return audio_tensor


class SpecScaler(nn.Module):
	"""Логарифмическое масштабирование спектрограммы для стабильности вычислений"""

	def forward(self, x: Tensor) -> Tensor:
		return torch.log(torch.clamp(x, min=1e-9, max=1e9))


class FeatureExtractor(nn.Module):
	"""Извлечение Mel-спектрограммы из аудио"""

	def __init__(self, sample_rate: int, features: int, hop_length=None, win_length=None, n_fft=None, center=None, **kwargs):
		super().__init__()
		self.hop_length = hop_length if hop_length is not None else kwargs.get("hop_length", sample_rate // 100)
		self.win_length = win_length if win_length is not None else kwargs.get("win_length", sample_rate // 40)
		self.n_fft = n_fft if n_fft is not None else kwargs.get("n_fft", sample_rate // 40)
		self.center = center if center is not None else kwargs.get("center", True)

		self.featurizer = nn.Sequential(
			torchaudio.transforms.MelSpectrogram(
				sample_rate=sample_rate,
				n_mels=features,
				win_length=self.win_length,
				hop_length=self.hop_length,
				n_fft=self.n_fft,
				center=self.center,
				# Параметры новых моделей: раньше игнорировались, теперь важны
				mel_scale=kwargs.get("mel_scale", "htk"),
				norm=kwargs.get("mel_norm", None),
				f_min=kwargs.get("lowfreq", 0),
				f_max=kwargs.get("highfreq", None)
			),
			SpecScaler()
		)

	def out_len(self, input_lengths: Tensor) -> Tensor:
		"""Вычисляет длину выходной последовательности после извлечения признаков"""
		if self.center:
			return torch.div(input_lengths, self.hop_length, rounding_mode="floor").add(1).long()
		else:
			return torch.div(input_lengths - self.win_length, self.hop_length, rounding_mode="floor").add(1).long()

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
		return torch.log_softmax(self.joint_net(enc + pred), dim=-1)

	def forward(self, enc: Tensor, dec: Tensor) -> Tensor:
		return self.joint(enc.transpose(1, 2), dec.transpose(1, 2))


class RNNTDecoder(nn.Module):
	"""Декодер для RNN-T архитектуры"""

	def __init__(self, pred_hidden: int, pred_rnn_layers: int, num_classes: int):
		super().__init__()
		self.blank_id = num_classes - 1
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
		self.charwise = model_path is None
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
		self.blank_id = len(self.tokenizer)

	@torch.inference_mode()
	def decode(self, head: CTCHead, encoded: Tensor, lengths: Tensor) -> List[str]:
		log_probs = head(encoder_output=encoded)
		b, _, c = log_probs.shape

		labels = log_probs.argmax(dim=-1, keepdim=False)

		skip_mask = labels != self.blank_id
		skip_mask[:, 1:] = torch.logical_and(skip_mask[:, 1:], labels[:, 1:] != labels[:, :-1])

		for i, length in enumerate(lengths):
			skip_mask[i, length:] = 0

		pred_texts: List[str] = []
		for i in range(b):
			pred_texts.append("".join(self.tokenizer.decode(labels[i][skip_mask[i]].cpu().tolist())))

		return pred_texts

class RNNTGreedyDecoding:
	"""Жадное декодирование для RNN-T моделей"""

	def __init__(self, vocabulary: List[str], model_path: Optional[str] = None, max_symbols_per_step: int = 30):
		self.tokenizer = Tokenizer(vocabulary, model_path)
		self.blank_id = len(self.tokenizer)
		self.max_symbols = 50

	def _greedy_decode(self, head: RNNTHead, x: Tensor, seqlen: Tensor) -> str:
		hyp: List[int] = []
		dec_state: Optional[Tensor] = None
		last_label: Optional[Tensor] = None

		for t in range(seqlen):
			f = x[t, :, :].unsqueeze(1)
			not_blank = True
			new_symbols = 0

			while not_blank and new_symbols < self.max_symbols:
				g, hidden = head.decoder.predict(last_label, dec_state)
				joint_out = head.joint.joint(f, g)
				k = joint_out[0, 0, 0, :].argmax(0).item()
				max_prob = joint_out[0, 0, 0, :].max().exp()

				if k == self.blank_id or max_prob.item() < 0.4:
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
		encoded = encoded.transpose(1, 2)

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
			layers.append(subs_conv_class(in_channels=in_channels, out_channels=conv_channels,
			                              kernel_size=self._kernel_size,
			                              stride=self._stride, padding=self._padding
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
		self.d_k = n_feat // n_head
		self.h = n_head

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

		p = self.linear_pos(pos_emb)
		p = p.view(pos_emb.shape[0], -1, self.h, self.d_k).transpose(1, 2)

		q_with_bias_u = (q + self.pos_bias_u).transpose(1, 2)
		q_with_bias_v = (q + self.pos_bias_v).transpose(1, 2)

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

		query = query.transpose(0, 1).view(t, b, self.h, self.d_k)
		key = key.transpose(0, 1).view(t, b, self.h, self.d_k)
		value = value.transpose(0, 1).view(t, b, self.h, self.d_k)

		cos, sin = pos_emb
		query, key = apply_rotary_pos_emb(query, key, cos, sin, offset=0)

		q, k, v = self.forward_qkv(
			query.view(t, b, self.h * self.d_k).transpose(0, 1),
			key.view(t, b, self.h * self.d_k).transpose(0, 1),
			value.view(t, b, self.h * self.d_k).transpose(0, 1)
		)

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
		self.depthwise_conv = nn.Conv1d(in_channels=d_model, out_channels=d_model,
		                                kernel_size=kernel_size, padding=(kernel_size - 1) // 2, groups=d_model, bias=True)
		self.batch_norm = nn.BatchNorm1d(d_model) if norm_type == "batch_norm" else nn.LayerNorm(d_model)
		self.activation = nn.SiLU()
		self.pointwise_conv2 = nn.Conv1d(d_model, d_model, kernel_size=1)

	def forward(self, x: Tensor, pad_mask: Optional[Tensor] = None) -> Tensor:
		x = x.transpose(1, 2)
		x = self.pointwise_conv1(x)
		x = nn.functional.glu(x, dim=1)

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

		self.norm_feed_forward1 = nn.LayerNorm(d_model)
		self.feed_forward1 = ConformerFeedForward(d_model=d_model, d_ff=d_ff)

		self.norm_self_att = nn.LayerNorm(d_model)
		if self_attention_model == "rotary":
			self.self_attn: nn.Module = RotaryPositionMultiHeadAttention(n_head=n_heads, n_feat=d_model)
		else:
			self.self_attn = RelPositionMultiHeadAttention(n_head=n_heads, n_feat=d_model)

		self.norm_conv = nn.LayerNorm(d_model)
		self.conv = ConformerConvolution(d_model=d_model, kernel_size=conv_kernel_size, norm_type=conv_norm_type)

		self.norm_feed_forward2 = nn.LayerNorm(d_model)
		self.feed_forward2 = ConformerFeedForward(d_model=d_model, d_ff=d_ff)

		self.norm_out = nn.LayerNorm(d_model)

	def forward(self, x: Tensor, pos_emb: Union[Tensor, List[Tensor]],
	            att_mask: Optional[Tensor] = None, pad_mask: Optional[Tensor] = None) -> Tensor:
		residual = x

		x = self.norm_feed_forward1(x)
		x = self.feed_forward1(x)
		residual = residual + x * self.fc_factor

		x = self.norm_self_att(residual)
		x = self.self_attn(x, x, x, pos_emb, mask=att_mask)
		residual = residual + x

		x = self.norm_conv(residual)
		x = self.conv(x, pad_mask=pad_mask)
		residual = residual + x

		x = self.norm_feed_forward2(residual)
		x = self.feed_forward2(x)
		residual = residual + x * self.fc_factor

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

		subsampling = subsampling if subsampling is not None else kwargs.get("subsampling", "conv2d")
		subs_kernel_size = subs_kernel_size if subs_kernel_size is not None else kwargs.get("subs_kernel_size", 3)
		conv_norm_type = conv_norm_type if conv_norm_type is not None else kwargs.get("conv_norm_type", "batch_norm")

		self.pre_encode = StridingSubsampling(subsampling=subsampling,
		                                      kernel_size=subs_kernel_size, subsampling_factor=subsampling_factor,
		                                      feat_in=feat_in, feat_out=d_model, conv_channels=d_model)

		self.pos_emb_max_len = pos_emb_max_len

		if self_attention_model == "rotary":
			self.pos_enc: PositionalEncoding = RotaryPositionalEmbedding(d_model // n_heads, pos_emb_max_len)
		else:
			self.pos_enc = RelPositionalEmbedding(d_model, pos_emb_max_len)

		self.layers = nn.ModuleList()
		for _ in range(n_layers):
			layer = ConformerLayer(d_model=d_model, d_ff=d_model * ff_expansion_factor,
			                       self_attention_model=self_attention_model,
			                       n_heads=n_heads, conv_norm_type=conv_norm_type, conv_kernel_size=conv_kernel_size)
			self.layers.append(layer)

	def forward(self, audio_signal: Tensor, length: Tensor) -> Tuple[Tensor, Tensor]:
		if not hasattr(self.pos_enc, "pe"):
			self.pos_enc.extend_pe(self.pos_emb_max_len, audio_signal.device)

		audio_signal, length = self.pre_encode(x=audio_signal.transpose(1, 2), lengths=length)
		max_len = audio_signal.size(1)

		audio_signal, pos_emb = self.pos_enc(x=audio_signal)

		pad_mask = torch.arange(0, max_len, device=audio_signal.device).expand(length.size(0), -1) < length.unsqueeze(-1)
		att_mask = None

		if audio_signal.shape[0] > 1:
			att_mask = pad_mask.unsqueeze(1).repeat([1, max_len, 1])
			att_mask = torch.logical_and(att_mask, att_mask.transpose(1, 2))
			att_mask = ~att_mask

		pad_mask = ~pad_mask

		for layer in self.layers:
			audio_signal = layer(x=audio_signal, pos_emb=pos_emb, att_mask=att_mask, pad_mask=pad_mask)

		return audio_signal.transpose(1, 2), length


# ===== Новое поколение GigaAM-v4 / Multilingual-v2 (Zapformer, 27.11.2026) =====
# Имена модулей повторяют официальный чекпоинт, чтобы load_state_dict(strict=True)
# работал без переименования ключей. Потоковый режим и ONNX-экспорт намеренно
# опущены: скрипт использует только полный контекст и жадное декодирование.

class SwishL(nn.Module):
	def forward(self, x: Tensor) -> Tensor:
		return (
			F.silu(0.639521598815918 * x - 2.087040662765503)
			- 0.021007252857089043 * x
			+ 0.2303316444158554
		)


class SwishR(nn.Module):
	def forward(self, x: Tensor) -> Tensor:
		return (
			F.silu(0.683202862739563 * x - 0.31602001190185547)
			- 0.012898006476461887 * x
			+ 0.133248575988922
		)


def _zap_activation(name, variant="r"):
	if name.lower() == "silu":
		return nn.SiLU()
	return SwishL() if variant == "l" else SwishR()


class RMSNormTorch(nn.Module):
	def __init__(self, dim: int, eps: float = 1e-06):
		super().__init__()
		self.eps = eps
		self.weight = nn.Parameter(torch.ones(dim))

	def forward(self, x: Tensor) -> Tensor:
		variance = (x * x).mean(dim=-1, keepdim=True)
		return x * torch.rsqrt(variance + self.eps) * self.weight


class RmsNorm(nn.Module):
	def __init__(self):
		super().__init__()
		self.scale = nn.Parameter(torch.tensor(0.2))
		self.eps = nn.Parameter(torch.tensor(0.1))

	def forward(self, x: Tensor) -> Tensor:
		x_sq = torch.mean(x * x, dim=-1, keepdim=True) + self.eps * self.eps
		return x * (self.scale / x_sq.sqrt())


class OrthogonalLinear(nn.Module):
	def __init__(self, in_channels: int, out_channels: int, weight_rms: float = 0.3):
		super().__init__()
		self.weight = nn.Parameter(torch.empty(out_channels, in_channels))
		nn.init.normal_(self.weight, std=weight_rms)
		self.weight_scale = in_channels ** (-0.5) / weight_rms

	def forward(self, x: Tensor, transpose: bool = False) -> Tensor:
		weight = self.weight * self.weight_scale
		if transpose:
			weight = weight.t()
		return F.linear(x, weight, None)


class ActivationAndLinear(nn.Module):
	def __init__(self, in_channels: int, out_channels: int, activation="swish"):
		super().__init__()
		self.weight = nn.Parameter(torch.empty(out_channels, in_channels))
		self.bias = nn.Parameter(torch.empty(out_channels))
		nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))
		nn.init.zeros_(self.bias)
		self.activation = _zap_activation(activation)

	def forward(self, x: Tensor) -> Tensor:
		return F.linear(self.activation(x), self.weight, self.bias)


class RoPETable(nn.Module):
	def __init__(self, dim: int, max_seq_len: int, base: float = 10000.0):
		super().__init__()
		inv_freq = 1.0 / base ** (torch.arange(0, dim, 2, dtype=torch.float32) / dim)
		t = torch.arange(max_seq_len, dtype=torch.float32)
		freqs = torch.outer(t, inv_freq)
		self.cos = nn.Parameter(freqs.cos()[None, None, :, :], requires_grad=False)
		self.sin = nn.Parameter(freqs.sin()[None, None, :, :], requires_grad=False)
		self.max_seq_len = max_seq_len

	@staticmethod
	def key(dim: int, max_seq_len: int, base: float = 10000.0) -> str:
		return f"ed{dim}_S{max_seq_len}_b{int(base)}"

	def forward(self, positions: Tensor) -> Tuple[Tensor, Tensor]:
		return self.cos.index_select(2, positions), self.sin.index_select(2, positions)


def apply_rope(x: Tensor, cos: Tensor, sin: Tensor) -> Tensor:
	b, h, s, d = x.shape
	pair = x.reshape(b, h, s, d // 2, 2)
	x0, x1 = pair[..., 0], pair[..., 1]
	return torch.stack((x0 * cos - x1 * sin, x0 * sin + x1 * cos), dim=-1).reshape(b, h, s, d)


def _zap_tuple(value, count=None):
	values = (
		tuple(map(int, value.split(",")))
		if isinstance(value, str)
		else ((value,) if isinstance(value, int) else tuple(value))
	)
	if count is not None and len(values) == 1:
		values *= count
	return values


def _zapformer_conv2d(x, layer, padding=None):
	if padding is None:
		return layer(x)
	return F.conv2d(x, layer.weight, layer.bias, layer.stride, padding, groups=layer.groups)


class ZapformerConvNeXt(nn.Module):
	def __init__(self, channels, causal, activation="swish"):
		super().__init__()
		self.causal = causal
		kernel = 3 if causal else 7
		self.depthwise_conv = nn.Conv2d(channels, channels, kernel, groups=channels, padding=0 if causal else 3)
		self.pointwise_conv1 = nn.Conv2d(channels, channels * 3, 1)
		self.activation = _zap_activation(activation, "l")
		self.pointwise_conv2 = nn.Conv2d(channels * 3, channels, 1)

	def forward(self, x):
		residual = x
		if self.causal:
			x = F.pad(x, (1, 1, 2, 0))
		x = _zapformer_conv2d(x, self.depthwise_conv)
		x = self.activation(_zapformer_conv2d(x, self.pointwise_conv1))
		return residual + _zapformer_conv2d(x, self.pointwise_conv2)


class ZapformerFrontend(nn.Module):
	def __init__(self, feat_in, dim, channels, causal, activation="swish"):
		super().__init__()
		self.causal = causal
		c1, c2, c3 = channels
		self.conv1 = nn.Conv2d(1, c1, 3, padding=0 if causal else 1)
		self.conv2 = nn.Conv2d(c1, c2, 3, stride=2, padding=(1, 0))
		self.conv3 = nn.Conv2d(c2, c3, 3, stride=2, padding=(1, 0))
		self.subsampling_factor = self.conv2.stride[0] * self.conv3.stride[0]
		self.activation = _zap_activation(activation)
		self.convnext = ZapformerConvNeXt(c3, causal, activation)
		self.out = nn.Linear(c3 * (((feat_in - 1) // 2 - 1) // 2), dim)

	def forward(self, x, lengths, state=None):
		valid = torch.arange(x.shape[1], device=x.device)[None] < lengths[:, None]
		x = (x * valid.unsqueeze(-1)).unsqueeze(1)
		for i, conv in enumerate((self.conv1, self.conv2, self.conv3)):
			if i == 0 and self.causal:
				x = F.pad(x, (1, 1, 2, 0))
			x = self.activation(_zapformer_conv2d(x, conv))
			if i:
				lengths = (lengths + 1) // 2
			valid = torch.arange(x.shape[2], device=x.device)[None] < lengths[:, None]
			x = x * valid[:, None, :, None]
		x = self.convnext(x)
		return self.out(x.transpose(1, 2).flatten(2)) * valid.unsqueeze(-1), lengths


class ZapformerAttention(nn.Module):
	def __init__(self, dim, heads, qdim, vdim, dropout):
		super().__init__()
		self.heads, self.qdim, self.vdim = heads, qdim, vdim
		self.in_norm = RMSNormTorch(dim)
		self.qk_in_proj = nn.Linear(dim, 2 * heads * qdim)
		self.vg_in_proj = nn.Linear(dim, 3 * heads * vdim)
		self.out_proj = nn.Linear(heads * vdim, dim)
		self.dropout = dropout

	def forward(self, x_qk, x_vg, cos, sin, mask, offset=0):
		b, t, _ = x_qk.shape
		q, k = self.qk_in_proj(self.in_norm(x_qk)).chunk(2, -1)
		q, k = [
			apply_rope(
				z.reshape(b, t, self.heads, self.qdim).transpose(1, 2),
				cos.to(z.dtype),
				sin.to(z.dtype),
			)
			for z in (q, k)
		]
		v, gate_in, gate_out = self.vg_in_proj(x_vg).chunk(3, -1)
		v = (v * gate_in.sigmoid()).reshape(b, t, self.heads, self.vdim).transpose(1, 2)
		all_masked = mask.all(-1, keepdim=True)[:, None]
		out = F.scaled_dot_product_attention(
			q[:, :, offset:].masked_fill(all_masked, 0),
			k,
			v,
			attn_mask=~mask[:, None] | all_masked,
			dropout_p=self.dropout if self.training else 0.0,
		)
		out = out.transpose(1, 2).reshape(b, t - offset, self.heads * self.vdim)
		return self.out_proj(out * gate_out[:, offset:].sigmoid())


class ZapformerFeedForward(nn.Module):
	def __init__(self, dim, multiple, activation="swish"):
		super().__init__()
		self.in_proj = nn.Linear(dim, dim * multiple)
		self.activation = _zap_activation(activation)
		self.activation_dropout = nn.Dropout(0.05)
		self.out_proj = nn.Linear(dim * multiple, dim)

	def forward(self, x):
		return self.out_proj(self.activation_dropout(self.activation(self.in_proj(x))))


class ZapformerConvolution(nn.Module):
	def __init__(self, dim, kernel, chunk, activation="swish"):
		super().__init__()
		self.chunk, self.context = chunk, (kernel - 1) // 2
		self.in_proj = nn.Linear(dim, 2 * dim)
		self.depthwise_conv = nn.Conv1d(dim, dim, kernel, groups=dim, padding=self.context)
		self.weighted_mean = nn.Module()
		self.weighted_mean.weights = nn.Parameter(torch.zeros(dim))
		self.out_proj = ActivationAndLinear(dim, dim, activation)

	def forward(self, x, valid, context, chunk_size=None):
		x, gate = self.in_proj(x).chunk(2, -1)
		x = x * valid.unsqueeze(-1)
		accum = x.float()
		mean = (context.to(accum.dtype) @ accum) / context.sum(-1, keepdim=True).clamp_min(1)
		mean = mean * self.weighted_mean.weights
		y = F.conv1d(
			x.transpose(1, 2),
			self.depthwise_conv.weight,
			self.depthwise_conv.bias,
			padding=self.context,
			groups=x.shape[-1],
		)
		return self.out_proj((y.transpose(1, 2) + mean) * gate.sigmoid())


class ZapformerLayer(nn.Module):
	def __init__(self, dim, heads, qdim, vdim, multiple, kernel, chunk, dropout, activation="swish"):
		super().__init__()
		self.feed_forward1 = ZapformerFeedForward(dim, multiple, activation)
		self.feed_forward2 = ZapformerFeedForward(dim, multiple, activation) if kernel > 0 else None
		self.self_attn = ZapformerAttention(dim, heads, qdim, vdim, 0.1)
		self.conv_module = ZapformerConvolution(dim, kernel, chunk, activation) if kernel > 0 else None
		self.norm = RMSNormTorch(dim)
		self.dropout = dropout

	def forward(self, x, cos, sin, valid, allowed, chunk_size=None):
		residual = x
		qk = x
		x = x + F.dropout(self.feed_forward1(x), self.dropout, self.training)
		mask = ~allowed[None] | ~valid[:, None]
		x = x + F.dropout(self.self_attn(qk, x, cos, sin, mask), self.dropout, self.training)
		if self.conv_module is not None:
			x = x + F.dropout(
				self.conv_module(x, valid, ~mask, chunk_size=chunk_size),
				self.dropout,
				self.training,
			)
		if self.feed_forward2 is not None:
			x = x + F.dropout(self.feed_forward2(x), self.dropout, self.training)
		return self.norm(residual + 0.25 * (x - residual))


class ZapformerStack(nn.Module):
	def __init__(self, input_dim, dim, layers, heads, qdim, vdim, multiple, kernel, chunk, dropout, rope_bank, activation="swish"):
		super().__init__()
		self.proj = OrthogonalLinear(input_dim, dim)
		self.layers = nn.ModuleList(
			[ZapformerLayer(dim, heads, qdim, vdim, multiple, kernel, chunk, dropout, activation) for _ in range(layers)]
		)
		self.residual_scales = nn.Parameter(torch.tensor([-1.0] + [1.0 / layers] * layers))
		self.input_scale = nn.Parameter(torch.ones(1))
		self.rope_bank = rope_bank

	def forward(self, x, cos, sin, valid, allowed, layer_hook=None, chunk_size=None):
		residual = x
		x = self.proj(x)
		bypass = self.residual_scales[0] * x
		x = self.input_scale * x
		for i, layer in enumerate(self.layers):
			x = layer(x, cos, sin, valid, allowed, chunk_size)
			if layer_hook is not None:
				x = layer_hook(x, i)
			bypass = bypass + self.residual_scales[i + 1] * x
		return residual + self.proj(bypass, transpose=True)


class ZapformerEncoder(nn.Module):
	"""Zapformer-энкодер из GigaAM-v4 / Multilingual-v2 (полный контекст)."""

	def __init__(
		self,
		in_channels=64,
		frontend_channels="8,32,128",
		downsampling_factor="1,2,4,2",
		embed_dim=None,
		encoder_dim="320,512,768,512",
		num_encoder_layers="6,8,14,8",
		query_head_dim=None,
		value_head_dim="96,96,96,96",
		num_heads="4,4,4,4",
		feedforward_multiple="4,4,3,4",
		conv_params="31,31,15,31",
		causal=False,
		causal_frontend=False,
		chunk_size=-1,
		window_size=(-1, -1),
		chunk_window=(-1, -1),
		max_seq_len=10000,
		dropout=0.1,
		flash_attn=False,
		dual_mode=False,
		activation="swish",
	):
		super().__init__()
		if flash_attn:
			raise NotImplementedError("flash_attn не поддерживается Zipformer/Zapformer")
		self.dual_mode = dual_mode
		self.language_film = None
		if dual_mode:
			chunks = _zap_tuple(chunk_size)
			windows = (
				[tuple(w) for w in window_size]
				if not isinstance(window_size[0], int)
				else [tuple(window_size)] * len(chunks)
			)
			self._context_modes = dict(zip(chunks, windows))
			causal, chunk_size, window_size = False, -1, (-1, -1)
		self.feat_in = in_channels
		self.causal, self.causal_frontend = causal, causal_frontend
		self.downsampling_factor = ds = _zap_tuple(downsampling_factor)
		n = len(ds)
		dims, layers, heads, vdims, multiples, kernels = [
			_zap_tuple(v, n)
			for v in (
				encoder_dim,
				num_encoder_layers,
				num_heads,
				value_head_dim,
				feedforward_multiple,
				conv_params,
			)
		]
		self.layer_dims = [dim for dim, count in zip(dims, layers) for _ in range(count)]
		qdims = (
			_zap_tuple(query_head_dim, n)
			if query_head_dim is not None
			else tuple(d // h for d, h in zip(dims, heads))
		)
		self.chunk_size = chunk_size if causal else -1
		self.window_size, self.chunk_window = _zap_tuple(window_size), _zap_tuple(chunk_window)
		dim = embed_dim or dims[0]
		self.feat_out = dim
		self.encoder_embed = ZapformerFrontend(
			in_channels, dim, _zap_tuple(frontend_channels, 3), causal_frontend, activation
		)
		self.encoder = nn.Module()
		self.encoder.rope_bank = nn.Module()
		self.encoder.rope_bank.tables = nn.ModuleDict(
			{
				RoPETable.key(q, max_seq_len): RoPETable(q, max_seq_len)
				for q in set(qdims)
			}
		)
		self.encoder.encoders = nn.ModuleList(
			[
				ZapformerStack(
					d * dim, e, l, h, q, v, m, k,
					self.chunk_size // d if causal else -1,
					dropout, self.encoder.rope_bank, activation,
				)
				for d, e, l, h, q, v, m, k in zip(
					ds, dims, layers, heads, qdims, vdims, multiples, kernels
				)
			]
		)
		self.encoder.out_norm = RmsNorm()
		self.qdims, self.max_seq_len = qdims, max_seq_len

	@property
	def frontend(self):
		return self.encoder_embed

	@property
	def subsampling_factor(self):
		return self.encoder_embed.subsampling_factor

	def _allowed(self, size, device, chunk, window_size):
		q = torch.arange(size, device=device)[:, None]
		k = q.T
		if chunk <= 0:
			return torch.ones(size, size, device=device, dtype=torch.bool)
		return self._attention_mask(q, k, chunk, window_size)

	def _attention_mask(self, q, k, chunk, window_size=None):
		qc, kc = q // chunk, k // chunk
		allowed = qc == kc
		for left, right, query, key in (
			(*(self.window_size if window_size is None else window_size), q, k),
			(*self.chunk_window, qc, kc),
		):
			if (left, right) != (-1, -1):
				allowed = allowed | (
					(key >= query - left) if left >= 0 else torch.ones_like(allowed)
				) & ((key <= query + right) if right >= 0 else torch.ones_like(allowed))
		return allowed

	def forward(self, audio_signal, length, chunk_size=None, lang_embedding=None, left_context=32):
		chunk = chunk_size
		if chunk is None:
			chunk = -1
		window = self._context_modes[chunk] if self.dual_mode else self.window_size
		x, length = self.encoder_embed(audio_signal.transpose(1, 2), length)
		original = x.shape[1]
		max_ds = max(self.downsampling_factor)
		x = F.pad(x, (0, 0, 0, (-original) % max_ds))
		valid = torch.arange(x.shape[1], device=x.device)[None] < length[:, None]
		allowed = self._allowed(x.shape[1], x.device, chunk, window)
		layer_offset = 0
		for ds, qdim, stack in zip(self.downsampling_factor, self.qdims, self.encoder.encoders):
			if ds > 1:
				x = x * valid.unsqueeze(-1)
			x = x.reshape(x.shape[0], -1, x.shape[-1] * ds)
			table = self.encoder.rope_bank.tables[RoPETable.key(qdim, self.max_seq_len)]
			cos, sin = table(torch.arange(x.shape[1], device=x.device))
			hook = (
				(lambda value, index: self.language_film(value, layer_offset + index, lang_embedding))
				if self.language_film is not None
				else None
			)
			x = stack(x, cos, sin, valid[:, ::ds], allowed[::ds, ::ds], hook)
			layer_offset += len(stack.layers)
			x = x.reshape(x.shape[0], -1, x.shape[-1] // ds)
		return self.encoder.out_norm(x[:, :original]).transpose(1, 2), length


class LanguageEmbedding(nn.Module):
	def __init__(self, cfg):
		super().__init__()
		self.languages = tuple(cfg["languages"])
		self.slots = {code: i + 1 for i, code in enumerate(self.languages)}
		self.slots["auto"] = 0
		self.default = cfg.get("default_tag") or "auto"
		self.weight = nn.Parameter(torch.empty(cfg["num_slots"], cfg["embedding_dim"]))
		if cfg.get("init") == "zeros":
			nn.init.zeros_(self.weight)
		else:
			nn.init.normal_(self.weight, std=cfg.get("init_std", 0.02))

	def _vector(self, tag):
		if not isinstance(tag, dict):
			values = json.loads(tag) if isinstance(tag, str) and tag.startswith("[") else ([tag] if isinstance(tag, str) else tag)
			tag = {code: 1.0 for value in values for code in value.strip().lower().split("-")}
		vector = self.weight.new_zeros(self.weight.shape[0])
		for code, value in tag.items():
			code = code.strip().lower()
			vector[self.slots["kk" if code == "kz" else code]] += float(value)
		return vector / vector.sum()

	def forward(self, language, batch_size=1):
		language = self.default if language is None else language
		tags = [language] * batch_size if isinstance(language, (str, dict)) else language
		vectors = torch.stack([self._vector(tag) for tag in tags])
		return (vectors.unsqueeze(-1) * self.weight.unsqueeze(0)).sum(1)


class LanguageFiLM(nn.Module):
	def __init__(self, widths, embedding_dim, cfg):
		super().__init__()
		every = cfg.get("every_n", 4)
		placement = cfg.get("placement", "every_n")
		layers = range(len(widths))
		if placement == "custom":
			layers = cfg["layers"]
		elif placement != "all":
			layers = range(every - 1, len(widths), every)
		self.projections = nn.ModuleDict(
			{str(i): nn.Linear(embedding_dim, 2 * widths[i]) for i in layers}
		)
		for projection in self.projections.values():
			nn.init.zeros_(projection.weight)
			nn.init.zeros_(projection.bias)

	def forward(self, hidden, index, embedding):
		if str(index) not in self.projections:
			return hidden
		gamma, beta = self.projections[str(index)](embedding.to(hidden.dtype)).unsqueeze(1).chunk(2, -1)
		return hidden * (1 + gamma) + beta


class LanguageLateFusion(nn.Module):
	def __init__(self, width, embedding_dim, cfg):
		super().__init__()
		hidden = cfg.get("hidden", 2048)
		self.kernel = nn.Sequential(
			nn.Linear(width + embedding_dim, hidden),
			nn.ReLU(),
			nn.Dropout(cfg.get("dropout", 0.0)),
			nn.Linear(hidden, width),
		)
		nn.init.zeros_(self.kernel[-1].weight)
		nn.init.zeros_(self.kernel[-1].bias)

	def forward(self, encoded, embedding):
		with torch.autocast(device_type=encoded.device.type, enabled=False):
			encoded = encoded.float()
			frames = encoded.transpose(1, 2)
			language = embedding.float().unsqueeze(1).expand(-1, frames.shape[1], -1)
			return encoded + self.kernel(torch.cat((frames, language), -1)).transpose(1, 2)


def get_pipeline() -> "Pipeline":
	"""Создает или возвращает кэшированный VAD пайплайн"""
	from pyannote.audio import Model, Pipeline
	from pyannote.audio.core.task import Problem, Resolution, Specifications
	from pyannote.audio.pipelines import VoiceActivityDetection
	global _PIPELINE
	if _PIPELINE is not None:
		return _PIPELINE

	try:
		hf_token = os.environ["HF_TOKEN"]
	except KeyError as exc:
		raise ValueError("HF_TOKEN environment variable is not set") from exc

	try:
		with torch.serialization.safe_globals([type, Problem, Specifications, Resolution]):
			model = Model.from_pretrained("pyannote/segmentation-3.0", token=hf_token)
	except:
		model = Model.from_pretrained("pyannote/segmentation-3.0", token=hf_token)

	_PIPELINE = VoiceActivityDetection(segmentation=model)
	_PIPELINE.instantiate({"min_duration_on": 0.0, "min_duration_off": 0.0})

	return _PIPELINE


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

	for segment in sad_segments.get_timeline().support():
		start = max(0, segment.start)
		end = min(audio.shape[0] / sr, segment.end)

		if curr_duration > new_chunk_threshold and (curr_duration + (end - curr_end) > max_duration or curr_duration > min_duration):
			_update_segments(curr_start, curr_end, curr_duration)
			curr_start = start

		curr_end = end
		curr_duration = curr_end - curr_start

	if curr_duration > new_chunk_threshold:
		_update_segments(curr_start, curr_end, curr_duration)
	return segments, boundaries


def infer_onnx(wav_input: Union[str, np.ndarray, Tensor], model_cfg: omegaconf.DictConfig,
               sessions: List[rt.InferenceSession], preprocessor: Optional[FeatureExtractor] = None,
               tokenizer: Optional[Tokenizer] = None, sample_rate: int = 16000) -> Union[str, np.ndarray]:
	"""Инференс через ONNX Runtime (быстрее для CPU)"""
	model_name = model_cfg.model_name

	if preprocessor is None:
		preprocessor = FeatureExtractor(sample_rate=16000,
		                                features=model_cfg.preprocessor.features)

	if tokenizer is None and ("ctc" in model_name or "rnnt" in model_name):
		tokenizer = Tokenizer(model_cfg.decoding.vocabulary,
		                      model_cfg.decoding.get("model_path"))

	input_signal = load_audio(wav_input, sample_rate=sample_rate)
	input_signal = preprocessor(input_signal.unsqueeze(0), torch.tensor([input_signal.shape[-1]]))[0].numpy()

	enc_sess = sessions[0]
	enc_inputs = {node.name: data for (node, data) in zip(
		enc_sess.get_inputs(),
		[input_signal.astype(DTYPE), [input_signal.shape[-1]]]
	)}
	enc_features = enc_sess.run([node.name for node in enc_sess.get_outputs()], enc_inputs)[0]

	if "emo" in model_name or "ssl" in model_name:
		return enc_features

	blank_idx = len(tokenizer)
	token_ids = []
	prev_token = blank_idx

	if "ctc" in model_name:
		prev_tok = blank_idx
		for tok in enc_features.argmax(-1).squeeze().tolist():
			if (tok != prev_tok or prev_tok == blank_idx) and tok != blank_idx:
				token_ids.append(tok)
			prev_tok = tok
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
	opts.intra_op_num_threads = 16
	opts.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
	opts.log_severity_level = 3

	model_cfg = omegaconf.OmegaConf.load(f"{onnx_dir}/{model_version}.yaml")

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
		self.language_fusion = None

		# Передаём ВСЕ параметры препроцессора (у новых моделей есть mel_scale,
		# mel_norm, lowfreq/highfreq — они влияют на признаки).
		self.preprocessor = FeatureExtractor(
			**{k: v for k, v in cfg.preprocessor.items() if k != "_target_"}
		)

		enc_cfg = {k: v for k, v in cfg.encoder.items() if k != "_target_"}
		if str(cfg.encoder.get("_target_", "")).endswith("ZapformerEncoder"):
			self.encoder = ZapformerEncoder(**enc_cfg)
		else:
			self.encoder = ConformerEncoder(**enc_cfg)

		if hasattr(self.encoder, "subsampling_factor"):
			self.encoder.frame_shift_ms = (
				1000 * self.preprocessor.hop_length * self.encoder.subsampling_factor
				/ cfg.preprocessor.sample_rate
			)

	def encode_language(self, language, batch_size):
		"""Базовые модели не используют языковые подсказки"""
		return None

	def forward(self, features: Tensor, feature_lengths: Tensor, language=None, **kwargs) -> Tuple[Tensor, Tensor]:
		"""Прямой проход модели"""
		embedding = self.encode_language(language, features.shape[0])
		features, feature_lengths = self.preprocessor(features, feature_lengths)
		enc_kwargs = {"lang_embedding": embedding} if embedding is not None else {}
		encoded, lengths = self.encoder(features, feature_lengths, **enc_kwargs)
		if self.language_fusion is not None:
			encoded = self.language_fusion(encoded, embedding)
		return encoded, lengths

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

		if not isinstance(wav_input, str) and current_sr != SAMPLE_RATE:
			if wav.numel() > 0:
				wav = taF.resample(wav.unsqueeze(0), orig_freq=current_sr, new_freq=SAMPLE_RATE).squeeze(0)

		min_length = int(SAMPLE_RATE * 0.1)
		if wav.numel() < min_length:
			raise ValueError(f"Audio is too short: {wav.numel()} samples. Minimum required: {min_length} samples (~0.1 seconds at {SAMPLE_RATE}Hz)")

		wav = wav.unsqueeze(0)
		length = torch.full([1], wav.shape[-1])
		return wav, length


class GigaAMASR(GigaAM):
	"""Модель для распознавания речи"""
	def __init__(self, cfg: omegaconf.DictConfig):
		super().__init__(cfg)

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

		audio_length = audio_data.shape[-1]

		if audio_length <= LONGFORM_THRESHOLD:
			wav, length = self.prepare_wav(wav_input, sample_rate=sample_rate)
			encoded, encoded_len = self.forward(wav, length)
			return self.decoding.decode(self.head, encoded, encoded_len)[0]
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


class GigaAMDualASR(GigaAM):
	"""Модели v4 / multilingual_v2: две головы raw и e2e на одном энкодере.

	Внешний контракт сохранён: transcribe() возвращает строку (голова e2e),
	как и старые модели. Жадное декодирование — родное, с порогом 0.4.
	"""

	def __init__(self, cfg: omegaconf.DictConfig):
		super().__init__(cfg)
		self.heads = nn.ModuleDict()
		for name in ("e2e", "raw"):
			head_cfg = cfg.heads[name]
			if str(head_cfg.get("_target_", "")).endswith("RNNTHead") or "joint" in head_cfg:
				self.heads[name] = RNNTHead(head_cfg.decoder, head_cfg.joint)
			else:
				self.heads[name] = CTCHead(head_cfg.feat_in, head_cfg.num_classes)

		self.language_embedding = self.language_fusion = None
		self.default_language = None
		self._initialize_language_conditioning(cfg)

		self.decodings = {}
		for name, head in self.heads.items():
			dc = cfg.decodings[name]
			if isinstance(head, RNNTHead):
				self.decodings[name] = RNNTGreedyDecoding(
					dc.get("vocabulary"), dc.get("model_path"), dc.get("max_symbols_per_step", 10)
				)
			else:
				self.decodings[name] = CTCGreedyDecoding(
					dc.get("vocabulary"), dc.get("model_path")
				)

	def _initialize_language_conditioning(self, cfg):
		conditioning = cfg.get("language_conditioning")
		if not conditioning:
			return
		if not (
			conditioning.get("film", {}).get("enabled", False)
			or conditioning.get("late_fusion", {}).get("enabled", False)
		):
			return
		if conditioning.get("film", {}).get("enabled", False):
			self.language_embedding = LanguageEmbedding(conditioning)
			self.encoder.language_film = LanguageFiLM(
				self.encoder.layer_dims,
				conditioning["embedding_dim"],
				conditioning["film"],
			)
		if conditioning.get("late_fusion", {}).get("enabled", False):
			if self.language_embedding is None:
				self.language_embedding = LanguageEmbedding(conditioning)
			width = next(iter(cfg.heads.values())).joint.enc_hidden
			self.language_fusion = LanguageLateFusion(
				width, conditioning["embedding_dim"], conditioning["late_fusion"]
			)

	def encode_language(self, language, batch_size):
		if self.language_embedding is None:
			return None
		language = self.default_language if language is None else language
		return self.language_embedding(language, batch_size)

	def _decode_all(self, encoded, encoded_len):
		return {
			name: self.decodings[name].decode(self.heads[name], encoded, encoded_len)[0]
			for name in self.heads
		}

	@torch.inference_mode()
	def transcribe(self, wav_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE,
	               head: str = "e2e", **kwargs) -> Union[str, List[Dict[str, Union[str, Tuple[float, float]]]]]:
		"""Текст с головы e2e (по умолчанию) — совместимо со старым API."""
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
			raise TypeError(f"Unsupported audio input type: {type(wav_input)}")

		if audio_data.shape[-1] <= LONGFORM_THRESHOLD:
			wav, length = self.prepare_wav(wav_input, sample_rate=sample_rate)
			encoded, encoded_len = self.forward(wav, length)
			return self._decode_all(encoded, encoded_len)[head]

		print("long")
		transcribed_segments = []
		segments, boundaries = segment_audio_file(audio_data, SAMPLE_RATE, **kwargs)
		for segment, segment_boundaries in zip(segments, boundaries):
			wav = segment.unsqueeze(0)
			length = torch.full([1], wav.shape[-1])
			encoded, encoded_len = self.forward(wav, length)
			result = self._decode_all(encoded, encoded_len)[head]
			transcribed_segments.append({
				"transcription": result,
				"boundaries": segment_boundaries,
			})
		return transcribed_segments

	@torch.inference_mode()
	def transcribe_all(self, wav_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE) -> Dict[str, str]:
		"""Обе головы сразу: {'e2e': ..., 'raw': ...}."""
		wav, length = self.prepare_wav(wav_input, sample_rate=sample_rate)
		encoded, encoded_len = self.forward(wav, length)
		return self._decode_all(encoded, encoded_len)


def _download_file(file_url: str, file_path: str, force: bool = False) -> str:
	"""Скачивает файл с прогресс-баром"""
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


def _download_tokenizer(model_name: str, download_root: str, force: bool = False) -> Union[Optional[str], Dict[str, str]]:
	"""Скачивает токенизатор если нужно.

	Для v4/multilingual_v2 CDN хранит отдельные токенизаторы raw и e2e —
	возвращаем словарь {'raw': path, 'e2e': path} вместо одного пути.
	"""
	if model_name in _DUAL_TOKENIZER_MODELS:
		paths = {}
		for head in ("raw", "e2e"):
			filename = f"{model_name}_{head}_tokenizer.model"
			tokenizer_path = os.path.join(download_root, filename)
			if os.path.exists(tokenizer_path) and not force:
				logging.info(f"Tokenizer found at {tokenizer_path}, skipping download.")
			else:
				logging.info(f"Downloading tokenizer to {tokenizer_path}")
			paths[head] = _download_file(
				f"{_URL_DIR}/{filename}", tokenizer_path, force
			)
		return paths

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
	"""Проверяет существует ли модель"""
	short_names = ["ctc", "rnnt", "e2e_ctc", "e2e_rnnt", "ssl"]
	if model_name in short_names:
		model_name = f"v3_{model_name}"

	model_path = os.path.join(download_root, f"{model_name}.ckpt")
	if not os.path.exists(model_path):
		return False

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


def load_model(model_name: str, download_root: Optional[str] = None,
               force_download: bool = False,
               fp16_encoder: bool = True,
               use_flash: Optional[bool] = False,
               device: Optional[Union[str, torch.device]] = None) -> Union[GigaAM, GigaAMASR]:
	"""Быстрая загрузка модели для CPU
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

	device_obj = torch.device("cpu")

	if not check_model_exists(model_name, download_root) or force_download:
		_download_model(model_name, download_root, force_download)

	model_name, model_path = _download_model(model_name, download_root, force_download)
	tokenizer_path = _download_tokenizer(model_name, download_root, force_download)

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
					f"or use force_download=True to re-download automatically.")

	if not os.path.exists(model_path):
		raise FileNotFoundError(f"Model file not found: {model_path}. Please check the download directory.")

	with warnings.catch_warnings():
		warnings.simplefilter("ignore", category=(FutureWarning))
		try:
			checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
		except TypeError:
			checkpoint = torch.load(model_path, map_location="cpu")

	cfg = checkpoint["cfg"]

	if "encoder" in cfg:
		if hasattr(cfg.encoder, 'flash_attn'):
			cfg.encoder.flash_attn = False
		if hasattr(cfg.encoder, 'fp16'):
			cfg.encoder.fp16 = False

	if "preprocessor" in cfg:
		cfg.preprocessor["_target_"] = "sber_gegaam.FeatureExtractor"

	if "encoder" in cfg:
		is_zapformer = str(cfg.encoder.get("_target_", "")).endswith("ZapformerEncoder")
		cfg.encoder["_target_"] = (
			"sber_gegaam.ZapformerEncoder" if is_zapformer
			else "sber_gegaam.ConformerEncoder"
		)

	# Пути к токенизаторам: новые модели используют два (raw и e2e)
	if isinstance(tokenizer_path, dict):
		for head, path in tokenizer_path.items():
			if "decodings" in cfg and head in cfg.decodings:
				cfg.decodings[head].model_path = path
	elif tokenizer_path is not None and "decoding" in cfg:
		cfg.decoding.model_path = tokenizer_path

	if "ssl" in model_name:
		model = GigaAM(cfg)
	elif "heads" in cfg:
		model = GigaAMDualASR(cfg)
		# Русскоязычный скрипт: языковая подсказка по умолчанию
		if model_name == "multilingual_v2_rnnt":
			model.default_language = "ru"
	else:
		model = GigaAMASR(cfg)

	model.load_state_dict(checkpoint["state_dict"], strict=True)
	model.eval()

	torch.set_num_threads(min(8, os.cpu_count() or 8))

	for param in model.parameters():
		param.requires_grad = False
	try:
		if hasattr(torch, 'compile'):
			model = torch.compile(model, mode="reduce-overhead")
	except:
		pass
	cfg.model_name = model_name
	return model.to(device_obj)


__all__ = ["GigaAM", "GigaAMASR", "GigaAMDualASR", "load_audio", "load_model"]