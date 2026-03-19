import hashlib
import logging
import math
import os
import urllib.request
import warnings
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchaudio
import torchaudio.functional as taF
from omegaconf import DictConfig, OmegaConf
from tqdm import tqdm

# Константы
SAMPLE_RATE = 16000
DTYPE = np.float32
_URL_DIR = "https://cdn.chatwm.opensmodel.sberdevices.ru/GigaAM"
_MODEL_HASHES = {
    "v1_ctc": "f027f199e590a391d015aeede2e66174",
    "v2_ctc": "e00f59cb5d39624fb30d1786044795bf",
    "v3_ctc": "73413e7be9c6a5935827bfab5c0dd678",
    "v3_e2e_ctc": "367074d6498f426d960b25f49531cf68",
}

warnings.simplefilter("ignore", category=UserWarning)


def load_audio(audio_input: Union[str, np.ndarray, torch.Tensor], sample_rate: int = SAMPLE_RATE) -> torch.Tensor:
    """Загружает аудио из файла, массива или тензора и нормализует до 16 кГц."""
    if isinstance(audio_input, str):
        cmd = ["ffmpeg", "-nostdin", "-threads", "0", "-i", audio_input,
               "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le",
               "-ar", str(sample_rate), "-"]
        try:
            audio_bytes = run(cmd, capture_output=True, check=True).stdout
        except CalledProcessError as exc:
            raise RuntimeError("Failed to load audio") from exc
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            audio_tensor = torch.frombuffer(audio_bytes, dtype=torch.int16).float() / 32768.0
    elif isinstance(audio_input, np.ndarray):
        audio_tensor = torch.from_numpy(audio_input.copy()).float()
    elif isinstance(audio_input, torch.Tensor):
        audio_tensor = audio_input.float().clone()
    else:
        raise TypeError(f"Unsupported audio input type: {type(audio_input)}. Expected str, np.ndarray, or Tensor.")

    if audio_tensor.ndim > 1:
        audio_tensor = audio_tensor.flatten()

    if sample_rate != SAMPLE_RATE and audio_tensor.numel() > 0:
        audio_tensor = taF.resample(audio_tensor.unsqueeze(0),
                                    orig_freq=sample_rate,
                                    new_freq=SAMPLE_RATE).squeeze(0)

    return audio_tensor


class SpecScaler(nn.Module):
    """Логарифмическое масштабирование спектрограммы."""
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.log(x.clamp_(1e-9, 1e9))


class FeatureExtractor(nn.Module):
    """Извлечение Mel-спектрограммы из аудио."""
    def __init__(self, sample_rate: int, features: int, hop_length=None,
                 win_length=None, n_fft=None, center=None, **kwargs):
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
                center=self.center
            ),
            SpecScaler()
        )

    def out_len(self, input_lengths: torch.Tensor) -> torch.Tensor:
        if self.center:
            return input_lengths.div(self.hop_length, rounding_mode="floor").add(1).long()
        else:
            return (input_lengths - self.win_length).div(self.hop_length, rounding_mode="floor").add(1).long()

    def forward(self, input_signal: torch.Tensor, length: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.featurizer(input_signal), self.out_len(length)


class CTCHead(nn.Module):
    """Голова CTC для распознавания речи."""
    def __init__(self, feat_in: int, num_classes: int):
        super().__init__()
        self.decoder_layers = nn.Sequential(
            nn.Conv1d(feat_in, num_classes, kernel_size=1)
        )

    def forward(self, encoder_output: torch.Tensor) -> torch.Tensor:
        return F.log_softmax(
            self.decoder_layers(encoder_output).transpose(1, 2),
            dim=-1
        )


class Tokenizer:
    """Токенизатор для character-level словаря."""
    def __init__(self, vocab: List[str]):
        self.vocab = vocab

    def decode(self, tokens: List[int]) -> str:
        return "".join(self.vocab[tok] for tok in tokens)

    def __len__(self):
        return len(self.vocab)


class CTCGreedyDecoding:
    """Жадное декодирование для CTC."""
    def __init__(self, vocabulary: List[str]):
        self.tokenizer = Tokenizer(vocabulary)
        self.blank_id = len(self.tokenizer)

    @torch.inference_mode()
    def decode(self, head: CTCHead, encoded: torch.Tensor, lengths: torch.Tensor) -> List[str]:
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


class StridingSubsampling(nn.Module):
    """Субсэмплирование с использованием свёрток."""
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
        conv_class = nn.Conv2d if self.subsampling_type == "conv2d" else nn.Conv1d

        for _ in range(self._sampling_num):
            layers.append(conv_class(
                in_channels=in_channels,
                out_channels=conv_channels,
                kernel_size=self._kernel_size,
                stride=self._stride,
                padding=self._padding
            ))
            layers.append(nn.ReLU())
            in_channels = conv_channels

        if self.subsampling_type == "conv2d":
            out_length = self.calc_output_length(torch.tensor(feat_in))
            self.out = nn.Linear(conv_channels * int(out_length), feat_out)

        self.conv = nn.Sequential(*layers)

    def calc_output_length(self, lengths: torch.Tensor) -> torch.Tensor:
        lengths = lengths.to(torch.float)
        add_pad = 2 * self._padding - self._kernel_size

        for _ in range(self._sampling_num):
            lengths = torch.div(lengths + add_pad, self._stride) + 1.0
            lengths = torch.floor(lengths)

        return lengths.to(dtype=torch.int)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if self.subsampling_type == "conv2d":
            x = self.conv(x.unsqueeze(1))
            b, _, t, _ = x.size()
            x = self.out(x.transpose(1, 2).reshape(b, t, -1))
        else:
            x = self.conv(x.transpose(1, 2)).transpose(1, 2)

        return x, self.calc_output_length(lengths)


class MultiHeadAttention(nn.Module):
    """Базовый класс для механизма внимания."""
    def __init__(self, n_head: int, n_feat: int):
        super().__init__()
        assert n_feat % n_head == 0
        self.d_k = n_feat // n_head
        self.h = n_head

        self.linear_q = nn.Linear(n_feat, n_feat)
        self.linear_k = nn.Linear(n_feat, n_feat)
        self.linear_v = nn.Linear(n_feat, n_feat)
        self.linear_out = nn.Linear(n_feat, n_feat)

    def forward_qkv(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        b = query.size(0)
        q = self.linear_q(query).view(b, -1, self.h, self.d_k)
        k = self.linear_k(key).view(b, -1, self.h, self.d_k)
        v = self.linear_v(value).view(b, -1, self.h, self.d_k)
        return q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)

    def forward_attention(self, value: torch.Tensor, scores: torch.Tensor,
                          mask: Optional[torch.Tensor]) -> torch.Tensor:
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
    """Attention с относительными позиционными эмбеддингами."""
    def __init__(self, n_head: int, n_feat: int):
        super().__init__(n_head, n_feat)
        self.linear_pos = nn.Linear(n_feat, n_feat, bias=False)
        self.pos_bias_u = nn.Parameter(torch.FloatTensor(self.h, self.d_k))
        self.pos_bias_v = nn.Parameter(torch.FloatTensor(self.h, self.d_k))

    def rel_shift(self, x: torch.Tensor) -> torch.Tensor:
        b, h, qlen, pos_len = x.size()
        x = F.pad(x, pad=(1, 0))
        x = x.view(b, h, -1, qlen)
        return x[:, :, 1:].view(b, h, qlen, pos_len)

    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor,
                pos_emb: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
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
    """Attention с rotary позиционными эмбеддингами."""
    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor,
                pos_emb: List[torch.Tensor], mask: Optional[torch.Tensor] = None) -> torch.Tensor:
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


class PositionalEncoding(nn.Module):
    """Абстрактный класс для позиционного кодирования."""
    def __init__(self, dim: int, base: int):
        super().__init__()
        self.dim = dim
        self.base = base

    def create_pe(self, length: int, device: torch.device) -> Optional[torch.Tensor]:
        raise NotImplementedError

    def extend_pe(self, length: int, device: torch.device):
        pe = self.create_pe(length, device)
        if pe is None:
            return
        if hasattr(self, "pe"):
            self.pe = pe
        else:
            self.register_buffer("pe", pe, persistent=False)


class RelPositionalEmbedding(PositionalEncoding):
    """Относительные позиционные эмбеддинги."""
    def create_pe(self, length: int, device: torch.device) -> Optional[torch.Tensor]:
        if hasattr(self, "pe") and self.pe.shape[1] >= 2 * length - 1:
            return None

        positions = torch.arange(length - 1, -length, -1, device=device).unsqueeze(1)
        pos_length = positions.size(0)
        pe = torch.zeros(pos_length, self.dim, device=positions.device)

        div_term = torch.exp(torch.arange(0, self.dim, 2, device=pe.device) *
                             -(math.log(10000.0) / self.dim))
        pe[:, 0::2] = torch.sin(positions * div_term)
        pe[:, 1::2] = torch.cos(positions * div_term)

        return pe.unsqueeze(0)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        input_len = x.size(1)
        center_pos = self.pe.size(1) // 2 + 1
        start_pos = center_pos - input_len
        end_pos = center_pos + input_len - 1
        return x, self.pe[:, start_pos:end_pos]


class RotaryPositionalEmbedding(PositionalEncoding):
    """Rotary позиционные эмбеддинги."""
    def create_pe(self, length: int, device: torch.device) -> Optional[torch.Tensor]:
        if hasattr(self, "pe") and self.pe.size(0) >= 2 * length:
            return None

        positions = torch.arange(0, length, dtype=torch.float32, device=device)
        inv_freq = 1.0 / (self.base ** (torch.arange(0, self.dim, 2).float() / self.dim))
        t = torch.arange(length, device=positions.device).type_as(inv_freq)

        freqs = torch.einsum("i,j->ij", t, inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1).to(positions.device)

        return torch.cat([emb.cos()[:, None, None, :], emb.sin()[:, None, None, :]])

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        cos_emb = self.pe[0: x.shape[1]]
        half_pe = self.pe.shape[0] // 2
        sin_emb = self.pe[half_pe: half_pe + x.shape[1]]
        return x, [cos_emb, sin_emb]


class ConformerConvolution(nn.Module):
    """Свёрточный модуль Conformer."""
    def __init__(self, d_model: int, kernel_size: int, norm_type: str):
        super().__init__()
        assert (kernel_size - 1) % 2 == 0
        assert norm_type in ["batch_norm", "layer_norm"]

        self.norm_type = norm_type
        self.pointwise_conv1 = nn.Conv1d(d_model, d_model * 2, kernel_size=1)
        self.depthwise_conv = nn.Conv1d(in_channels=d_model, out_channels=d_model,
                                        kernel_size=kernel_size,
                                        padding=(kernel_size - 1) // 2,
                                        groups=d_model, bias=True)
        self.batch_norm = nn.BatchNorm1d(d_model) if norm_type == "batch_norm" else nn.LayerNorm(d_model)
        self.activation = nn.SiLU()
        self.pointwise_conv2 = nn.Conv1d(d_model, d_model, kernel_size=1)

    def forward(self, x: torch.Tensor, pad_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        x = x.transpose(1, 2)
        x = self.pointwise_conv1(x)
        x = F.glu(x, dim=1)

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
    """FeedForward слой Conformer."""
    def __init__(self, d_model: int, d_ff: int, use_bias=True):
        super().__init__()
        self.linear1 = nn.Linear(d_model, d_ff, bias=use_bias)
        self.activation = nn.SiLU()
        self.linear2 = nn.Linear(d_ff, d_model, bias=use_bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear2(self.activation(self.linear1(x)))


class ConformerLayer(nn.Module):
    """Один слой Conformer."""
    def __init__(self, d_model: int, d_ff: int, self_attention_model: str,
                 n_heads: int = 16, conv_norm_type: str = "batch_norm",
                 conv_kernel_size: int = 31):
        super().__init__()
        self.fc_factor = 0.5

        self.norm_feed_forward1 = nn.LayerNorm(d_model)
        self.feed_forward1 = ConformerFeedForward(d_model=d_model, d_ff=d_ff)

        self.norm_self_att = nn.LayerNorm(d_model)
        if self_attention_model == "rotary":
            self.self_attn = RotaryPositionMultiHeadAttention(n_head=n_heads, n_feat=d_model)
        else:
            self.self_attn = RelPositionMultiHeadAttention(n_head=n_heads, n_feat=d_model)

        self.norm_conv = nn.LayerNorm(d_model)
        self.conv = ConformerConvolution(d_model=d_model, kernel_size=conv_kernel_size,
                                          norm_type=conv_norm_type)

        self.norm_feed_forward2 = nn.LayerNorm(d_model)
        self.feed_forward2 = ConformerFeedForward(d_model=d_model, d_ff=d_ff)

        self.norm_out = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor, pos_emb: Union[torch.Tensor, List[torch.Tensor]],
                att_mask: Optional[torch.Tensor] = None,
                pad_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
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
    """Conformer энкодер."""
    def __init__(self, feat_in: int = 64, n_layers: int = 16, d_model: int = 768,
                 subsampling_factor: int = 4, ff_expansion_factor: int = 4,
                 self_attention_model: str = "rotary", n_heads: int = 16,
                 pos_emb_max_len: int = 5000, conv_kernel_size: int = 31,
                 subsampling=None, subs_kernel_size=None, conv_norm_type=None, **kwargs):
        super().__init__()
        self.feat_in = feat_in
        assert self_attention_model in ["rotary", "rel_pos"], f"Unsupported attention: {self_attention_model}"

        subsampling = subsampling if subsampling is not None else kwargs.get("subsampling", "conv2d")
        subs_kernel_size = subs_kernel_size if subs_kernel_size is not None else kwargs.get("subs_kernel_size", 3)
        conv_norm_type = conv_norm_type if conv_norm_type is not None else kwargs.get("conv_norm_type", "batch_norm")

        self.pre_encode = StridingSubsampling(
            subsampling=subsampling,
            kernel_size=subs_kernel_size,
            subsampling_factor=subsampling_factor,
            feat_in=feat_in,
            feat_out=d_model,
            conv_channels=d_model
        )

        self.pos_emb_max_len = pos_emb_max_len

        if self_attention_model == "rotary":
            self.pos_enc = RotaryPositionalEmbedding(d_model // n_heads, pos_emb_max_len)
        else:
            self.pos_enc = RelPositionalEmbedding(d_model, pos_emb_max_len)

        self.layers = nn.ModuleList()
        for _ in range(n_layers):
            layer = ConformerLayer(
                d_model=d_model,
                d_ff=d_model * ff_expansion_factor,
                self_attention_model=self_attention_model,
                n_heads=n_heads,
                conv_norm_type=conv_norm_type,
                conv_kernel_size=conv_kernel_size
            )
            self.layers.append(layer)

    def forward(self, audio_signal: torch.Tensor, length: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
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
            audio_signal = layer(x=audio_signal, pos_emb=pos_emb,
                                 att_mask=att_mask, pad_mask=pad_mask)

        return audio_signal.transpose(1, 2), length


def rtt_half(x: torch.Tensor) -> torch.Tensor:
    """Rotary преобразование для половины вектора."""
    x1, x2 = x[..., : x.shape[-1] // 2], x[..., x.shape[-1] // 2:]
    return torch.cat([-x2, x1], dim=x1.ndim - 1)


def apply_rotary_pos_emb(q: torch.Tensor, k: torch.Tensor,
                          cos: torch.Tensor, sin: torch.Tensor,
                          offset: int = 0) -> Tuple[torch.Tensor, torch.Tensor]:
    """Применяет rotary позиционные эмбеддинги."""
    cos, sin = cos[offset: q.shape[0] + offset, ...], sin[offset: q.shape[0] + offset, ...]
    return (q * cos) + (rtt_half(q) * sin), (k * cos) + (rtt_half(k) * sin)


class GigaAM(nn.Module):
    """Базовый класс для моделей GigaAM (только CTC)."""
    def __init__(self, cfg: DictConfig):
        super().__init__()
        self.cfg = cfg

        self.preprocessor = FeatureExtractor(
            sample_rate=cfg.preprocessor.sample_rate,
            features=cfg.preprocessor.features,
            hop_length=cfg.preprocessor.get("hop_length"),
            win_length=cfg.preprocessor.get("win_length"),
            n_fft=cfg.preprocessor.get("n_fft"),
            center=cfg.preprocessor.get("center", True)
        )

        self.encoder = ConformerEncoder(**cfg.encoder)

    def forward(self, features: torch.Tensor, feature_lengths: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        features, feature_lengths = self.preprocessor(features, feature_lengths)
        return self.encoder(features, feature_lengths)

    def prepare_wav(self, wav_input: Union[str, np.ndarray, torch.Tensor],
                    sample_rate: int = SAMPLE_RATE) -> Tuple[torch.Tensor, torch.Tensor]:
        """Подготавливает аудио для модели."""
        wav = load_audio(wav_input, sample_rate=sample_rate)

        min_length = int(SAMPLE_RATE * 0.1)
        if wav.numel() < min_length:
            raise ValueError(f"Audio too short: {wav.numel()} samples. Minimum required: {min_length}")

        wav = wav.unsqueeze(0)
        length = torch.full([1], wav.shape[-1])
        return wav, length


class GigaAMASR(GigaAM):
    """Модель ASR на основе CTC."""
    def __init__(self, cfg: DictConfig):
        super().__init__(cfg)
        self.head = CTCHead(cfg.head.feat_in, cfg.head.num_classes)
        self.decoding = CTCGreedyDecoding(cfg.decoding.vocabulary)

    @torch.inference_mode()
    def transcribe(self, wav_input: Union[str, np.ndarray, torch.Tensor],
                   sample_rate: int = SAMPLE_RATE) -> str:
        """Транскрибирует аудио в текст (короткие аудио обрабатываются целиком)."""
        wav, length = self.prepare_wav(wav_input, sample_rate=sample_rate)
        encoded, encoded_len = self.forward(wav, length)
        return self.decoding.decode(self.head, encoded, encoded_len)[0]


def _download_file(file_url: str, file_path: str, force: bool = False) -> str:
    """Скачивает файл с прогресс-баром."""
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
    """Скачивает модель если её нет (только CTC)."""
    # Если передано короткое имя, преобразуем в полное
    if model_name in ["ctc", "e2e_ctc"]:
        model_name = f"v3_{model_name}"

    if model_name not in _MODEL_HASHES:
        raise ValueError(f"Model '{model_name}' not found. Available CTC models: {list(_MODEL_HASHES.keys())}")

    model_url = f"{_URL_DIR}/{model_name}.ckpt"
    model_path = os.path.join(download_root, f"{model_name}.ckpt")

    if os.path.exists(model_path) and not force:
        logging.info(f"Model found at {model_path}, skipping download.")
        return model_name, model_path

    logging.info(f"Downloading model to {model_path}")
    return model_name, _download_file(model_url, model_path, force)


def check_model_exists(model_name: str, download_root: str) -> bool:
    """Проверяет существует ли модель и совпадает ли хэш."""
    if model_name in ["ctc", "e2e_ctc"]:
        model_name = f"v3_{model_name}"

    model_path = os.path.join(download_root, f"{model_name}.ckpt")
    if not os.path.exists(model_path):
        return False

    expected_hash = _MODEL_HASHES.get(model_name)
    if expected_hash:
        actual_hash = hashlib.md5(open(model_path, "rb").read()).hexdigest()
        if actual_hash != expected_hash:
            logging.warning(f"Model hash mismatch: expected {expected_hash}, got {actual_hash}")
            return False
    return True


def load_model(model_name: str, download_root: Optional[str] = None,
               force_download: bool = False) -> GigaAMASR:
    """
    Загружает CTC-модель GigaAM для CPU.

    Args:
        model_name: Имя модели (например, "v3_ctc", "ctc", "v3_e2e_ctc")
        download_root: Каталог для загрузки моделей
        force_download: Принудительно перезагрузить модель

    Returns:
        Загруженная модель GigaAMASR.
    """
    if download_root is None:
        raise ValueError("download_root must be specified")
    os.makedirs(download_root, exist_ok=True)

    # Проверяем и скачиваем модель
    if not check_model_exists(model_name, download_root) or force_download:
        model_name, model_path = _download_model(model_name, download_root, force_download)
    else:
        # Определяем полное имя, если было короткое
        if model_name in ["ctc", "e2e_ctc"]:
            model_name = f"v3_{model_name}"
        model_path = os.path.join(download_root, f"{model_name}.ckpt")

    # Проверка хэша
    if os.path.exists(model_path):
        actual_hash = hashlib.md5(open(model_path, "rb").read()).hexdigest()
        expected_hash = _MODEL_HASHES.get(model_name)
        if expected_hash and actual_hash != expected_hash:
            if force_download:
                logging.warning(f"Hash mismatch, re-downloading...")
                os.remove(model_path)
                model_name, model_path = _download_model(model_name, download_root, True)
            else:
                raise RuntimeError(
                    f"Model checksum failed for {model_name}. "
                    f"Expected {expected_hash}, got {actual_hash}. "
                    f"Use force_download=True to re-download."
                )

    # Загрузка чекпоинта
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)

    cfg = checkpoint["cfg"]

    # Адаптация конфига для CPU
    if "encoder" in cfg:
        cfg.encoder.flash_attn = False
        cfg.encoder.fp16 = False

    # Создаём модель ASR (только CTC)
    model = GigaAMASR(cfg)

    # Загружаем веса
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()

    # Оптимизация для CPU
    torch.set_num_threads(min(8, os.cpu_count() or 8))
    for param in model.parameters():
        param.requires_grad = False

    # Попытка компиляции (PyTorch 2.0+)
    try:
        if hasattr(torch, 'compile'):
            model = torch.compile(model, mode="reduce-overhead")
    except:
        pass

    cfg.model_name = model_name
    return model


__all__ = ["GigaAMASR", "load_audio", "load_model"]