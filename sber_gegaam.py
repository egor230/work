# Sber GigaAM - Объединенный модуль для работы с аудиоданными
# Автор: AI Assistant
# Версия: 1.0

import hashlib
import logging
import math
import os
import urllib.request
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Dict, List, Optional, Tuple, Union

import hydra
import numpy as np
import omegaconf
import onnxruntime as rt
import torch
import torch.nn.functional as F
import torchaudio
import torchaudio.functional as taF
from sentencepiece import SentencePieceProcessor
from torch import Tensor, nn
from torch.jit import TracerWarning
from tqdm import tqdm

try:
    from flash_attn import flash_attn_func
    IMPORT_FLASH = True
except Exception as err:
    IMPORT_FLASH = False
    IMPORT_FLASH_ERR = err

from pyannote.audio import Model, Pipeline
from pyannote.audio.core.task import Problem, Resolution, Specifications
from pyannote.audio.pipelines import VoiceActivityDetection
from torch.torch_version import TorchVersion

# Constants
SAMPLE_RATE = 16000
LONGFORM_THRESHOLD = 55 * SAMPLE_RATE
DTYPE = np.float32
MAX_LETTERS_PER_FRAME = 3
_CACHE_DIR = os.path.expanduser("/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/cache/gigaam/")
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

_PIPELINE = None

warnings.simplefilter("ignore", category=UserWarning)


# === PREPROCESS.PY CONTENT ===

def load_audio(
    audio_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE
) -> Tensor:
    """
    Load an audio file or process an audio array and resample it to the specified sample rate.
    """
    if isinstance(audio_input, str):
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-threads",
            "0",
            "-i",
            audio_input,
            "-f",
            "s16le",
            "-ac",
            "1",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-",
        ]
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

    # Ensure audio is 1D
    if audio_tensor.ndim > 1:
        audio_tensor = audio_tensor.flatten()

    # Resample if necessary
    if sample_rate != SAMPLE_RATE:
        if audio_tensor.numel() > 0:
            audio_tensor = taF.resample(
                audio_tensor.unsqueeze(0), orig_freq=sample_rate, new_freq=SAMPLE_RATE
            ).squeeze(0)

    return audio_tensor


class SpecScaler(nn.Module):
    """
    Module that applies logarithmic scaling to spectrogram values.
    This module clamps the input values within a certain range and then applies a natural logarithm.
    """

    def forward(self, x: Tensor) -> Tensor:
        return torch.log(x.clamp_(1e-9, 1e9))


class FeatureExtractor(nn.Module):
    """
    Module for extracting Log-mel spectrogram features from raw audio signals.
    This module uses Torchaudio's MelSpectrogram transform to extract features
    and applies logarithmic scaling.
    """

    def __init__(self, sample_rate: int, features: int, **kwargs):
        super().__init__()
        self.hop_length = kwargs.get("hop_length", sample_rate // 100)
        self.win_length = kwargs.get("win_length", sample_rate // 40)
        self.n_fft = kwargs.get("n_fft", sample_rate // 40)
        self.center = kwargs.get("center", True)
        self.featurizer = nn.Sequential(
            torchaudio.transforms.MelSpectrogram(
                sample_rate=sample_rate,
                n_mels=features,
                win_length=self.win_length,
                hop_length=self.hop_length,
                n_fft=self.n_fft,
                center=self.center,
            ),
            SpecScaler(),
        )

    def out_len(self, input_lengths: Tensor) -> Tensor:
        """
        Calculates the output length after the feature extraction process.
        """
        if self.center:
            return (
                input_lengths.div(self.hop_length, rounding_mode="floor").add(1).long()
            )
        else:
            return (
                (input_lengths - self.win_length)
                .div(self.hop_length, rounding_mode="floor")
                .add(1)
                .long()
            )

    def forward(self, input_signal: Tensor, length: Tensor) -> Tuple[Tensor, Tensor]:
        """
        Extract Log-mel spectrogram features from the input audio signal.
        """
        return self.featurizer(input_signal), self.out_len(length)


# === DECODER.PY CONTENT ===

class CTCHead(nn.Module):
    """
    CTC Head module for Connectionist Temporal Classification.
    """

    def __init__(self, feat_in: int, num_classes: int):
        super().__init__()
        self.decoder_layers = torch.nn.Sequential(
            torch.nn.Conv1d(feat_in, num_classes, kernel_size=1)
        )

    def forward(self, encoder_output: Tensor) -> Tensor:
        return torch.nn.functional.log_softmax(
            self.decoder_layers(encoder_output).transpose(1, 2), dim=-1
        )


class RNNTJoint(nn.Module):
    """
    RNN-Transducer Joint Network Module.
    This module combines the outputs of the encoder and the prediction network using
    a linear transformation followed by ReLU activation and another linear projection.
    """

    def __init__(
        self, enc_hidden: int, pred_hidden: int, joint_hidden: int, num_classes: int
    ):
        super().__init__()
        self.enc_hidden = enc_hidden
        self.pred_hidden = pred_hidden
        self.pred = nn.Linear(pred_hidden, joint_hidden)
        self.enc = nn.Linear(enc_hidden, joint_hidden)
        self.joint_net = nn.Sequential(nn.ReLU(), nn.Linear(joint_hidden, num_classes))

    def joint(self, encoder_out: Tensor, decoder_out: Tensor) -> Tensor:
        """
        Combine the encoder and prediction network outputs into a joint representation.
        """
        enc = self.enc(encoder_out).unsqueeze(2)
        pred = self.pred(decoder_out).unsqueeze(1)
        return self.joint_net(enc + pred).log_softmax(-1)

    def input_example(self) -> Tuple[Tensor, Tensor]:
        device = next(self.parameters()).device
        enc = torch.zeros(1, self.enc_hidden, 1)
        dec = torch.zeros(1, self.pred_hidden, 1)
        return enc.float().to(device), dec.float().to(device)

    def input_names(self) -> List[str]:
        return ["enc", "dec"]

    def output_names(self) -> List[str]:
        return ["joint"]

    def forward(self, enc: Tensor, dec: Tensor) -> Tensor:
        return self.joint(enc.transpose(1, 2), dec.transpose(1, 2))


class RNNTDecoder(nn.Module):
    """
    RNN-Transducer Decoder Module.
    This module handles the prediction network part of the RNN-Transducer architecture.
    """

    def __init__(self, pred_hidden: int, pred_rnn_layers: int, num_classes: int):
        super().__init__()
        self.blank_id = num_classes - 1
        self.pred_hidden = pred_hidden
        self.embed = nn.Embedding(num_classes, pred_hidden, padding_idx=self.blank_id)
        self.lstm = nn.LSTM(pred_hidden, pred_hidden, pred_rnn_layers)

    def predict(
        self,
        x: Optional[Tensor],
        state: Optional[Tensor],
        batch_size: int = 1,
    ) -> Tuple[Tensor, Tensor]:
        """
        Make predictions based on the current input and previous states.
        If no input is provided, use zeros as the initial input.
        """
        if x is not None:
            emb: Tensor = self.embed(x)
        else:
            emb = torch.zeros(
                (batch_size, 1, self.pred_hidden), device=next(self.parameters()).device
            )
        g, hid = self.lstm(emb.transpose(0, 1), state)
        return g.transpose(0, 1), hid

    def input_example(self) -> Tuple[Tensor, Tensor, Tensor]:
        device = next(self.parameters()).device
        label = torch.tensor([[0]]).to(device)
        hidden_h = torch.zeros(1, 1, self.pred_hidden).to(device)
        hidden_c = torch.zeros(1, 1, self.pred_hidden).to(device)
        return label, hidden_h, hidden_c

    def input_names(self) -> List[str]:
        return ["x", "h", "c"]

    def output_names(self) -> List[str]:
        return ["dec", "h", "c"]

    def forward(self, x: Tensor, h: Tensor, c: Tensor) -> Tuple[Tensor, Tensor, Tensor]:
        """
        ONNX-specific forward with x, state = (h, c) -> x, h, c.
        """
        emb = self.embed(x)
        g, (h, c) = self.lstm(emb.transpose(0, 1), (h, c))
        return g.transpose(0, 1), h, c


class RNNTHead(nn.Module):
    """
    RNN-Transducer Head Module.
    This module combines the decoder and joint network components of the RNN-Transducer architecture.
    """

    def __init__(self, decoder: Dict[str, int], joint: Dict[str, int]):
        super().__init__()
        self.decoder = RNNTDecoder(**decoder)
        self.joint = RNNTJoint(**joint)


# === DECODING.PY CONTENT ===

class Tokenizer:
    """
    Tokenizer for converting between text and token IDs.
    The tokenizer can operate either character-wise or using a pre-trained SentencePiece model.
    """

    def __init__(self, vocab: List[str], model_path: Optional[str] = None):
        self.charwise = model_path is None
        if self.charwise:
            self.vocab = vocab
        else:
            self.model = SentencePieceProcessor()
            self.model.load(model_path)

    def decode(self, tokens: List[int]) -> str:
        """
        Convert a list of token IDs back to a string.
        """
        if self.charwise:
            return "".join(self.vocab[tok] for tok in tokens)
        return self.model.decode(tokens)

    def __len__(self):
        """
        Get the total number of tokens in the vocabulary.
        """
        return len(self.vocab) if self.charwise else len(self.model)


class CTCGreedyDecoding:
    """
    Class for performing greedy decoding of CTC outputs.
    """

    def __init__(self, vocabulary: List[str], model_path: Optional[str] = None):
        self.tokenizer = Tokenizer(vocabulary, model_path)
        self.blank_id = len(self.tokenizer)

    @torch.inference_mode()
    def decode(self, head: CTCHead, encoded: Tensor, lengths: Tensor) -> List[str]:
        """
        Decode the output of a CTC model into a list of hypotheses.
        """
        log_probs = head(encoder_output=encoded)
        assert (
            len(log_probs.shape) == 3
        ), f"Expected log_probs shape {log_probs.shape} == [B, T, C]"
        b, _, c = log_probs.shape
        assert (
            c == len(self.tokenizer) + 1
        ), f"Num classes {c} != len(vocab) + 1 {len(self.tokenizer) + 1}"
        labels = log_probs.argmax(dim=-1, keepdim=False)

        skip_mask = labels != self.blank_id
        skip_mask[:, 1:] = torch.logical_and(
            skip_mask[:, 1:], labels[:, 1:] != labels[:, :-1]
        )
        for i, length in enumerate(lengths):
            skip_mask[i, length:] = 0

        pred_texts: List[str] = []
        for i in range(b):
            pred_texts.append(
                "".join(self.tokenizer.decode(labels[i][skip_mask[i]].cpu().tolist()))
            )
        return pred_texts


class RNNTGreedyDecoding:
    def __init__(
        self,
        vocabulary: List[str],
        model_path: Optional[str] = None,
        max_symbols_per_step: int = 10,
    ):
        """
        Class for performing greedy decoding of RNN-T outputs.
        """
        self.tokenizer = Tokenizer(vocabulary, model_path)
        self.blank_id = len(self.tokenizer)
        self.max_symbols = max_symbols_per_step

    def _greedy_decode(self, head: RNNTHead, x: Tensor, seqlen: Tensor) -> str:
        """
        Internal helper function for performing greedy decoding on a single sequence.
        """
        hyp: List[int] = []
        dec_state: Optional[Tensor] = None
        last_label: Optional[Tensor] = None
        for t in range(seqlen):
            f = x[t, :, :].unsqueeze(1)
            not_blank = True
            new_symbols = 0
            while not_blank and new_symbols < self.max_symbols:
                g, hidden = head.decoder.predict(last_label, dec_state)
                k = head.joint.joint(f, g)[0, 0, 0, :].argmax(0).item()
                if k == self.blank_id:
                    not_blank = False
                else:
                    hyp.append(int(k))
                    dec_state = hidden
                    last_label = torch.tensor([[hyp[-1]]]).to(x.device)
                    new_symbols += 1

        return self.tokenizer.decode(hyp)

    @torch.inference_mode()
    def decode(self, head: RNNTHead, encoded: Tensor, enc_len: Tensor) -> List[str]:
        """
        Decode the output of an RNN-T model into a list of hypotheses.
        """
        b = encoded.shape[0]
        pred_texts = []
        encoded = encoded.transpose(1, 2)
        for i in range(b):
            inseq = encoded[i, :, :].unsqueeze(1)
            pred_texts.append(self._greedy_decode(head, inseq, enc_len[i]))
        return pred_texts


# === ENCODER.PY CONTENT ===

class StridingSubsampling(nn.Module):
    """
    Strided Subsampling layer used to reduce the sequence length.
    """

    def __init__(
        self,
        subsampling: str,
        kernel_size: int,
        subsampling_factor: int,
        feat_in: int,
        feat_out: int,
        conv_channels: int,
    ):
        super().__init__()
        self.subsampling_type = subsampling
        assert self.subsampling_type in ["conv1d", "conv2d"]
        self._sampling_num = int(math.log(subsampling_factor, 2))
        self._stride = 2
        self._kernel_size = kernel_size
        self._padding = (self._kernel_size - 1) // 2

        layers: List[nn.Module] = []
        in_channels = 1 if self.subsampling_type == "conv2d" else feat_in
        subs_conv_class = (
            torch.nn.Conv2d if self.subsampling_type == "conv2d" else torch.nn.Conv1d
        )
        for _ in range(self._sampling_num):
            layers.append(
                subs_conv_class(
                    in_channels=in_channels,
                    out_channels=conv_channels,
                    kernel_size=self._kernel_size,
                    stride=self._stride,
                    padding=self._padding,
                )
            )
            layers.append(nn.ReLU())
            in_channels = conv_channels

        out_length = self.calc_output_length(torch.tensor(feat_in))
        if self.subsampling_type == "conv2d":
            self.out = torch.nn.Linear(conv_channels * int(out_length), feat_out)
        self.conv = torch.nn.Sequential(*layers)

    def calc_output_length(self, lengths: Tensor) -> Tensor:
        """
        Calculates the output length after applying the subsampling.
        """
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
    """
    Base class of Multi-Head Attention Mechanisms.
    """

    def __init__(
        self, n_head: int, n_feat: int, flash_attn=False, torch_sdpa_attn=False
    ):
        super().__init__()
        assert n_feat % n_head == 0
        self.d_k = n_feat // n_head
        self.h = n_head
        self.linear_q = nn.Linear(n_feat, n_feat)
        self.linear_k = nn.Linear(n_feat, n_feat)
        self.linear_v = nn.Linear(n_feat, n_feat)
        self.linear_out = nn.Linear(n_feat, n_feat)
        self.flash_attn = flash_attn
        self.torch_sdpa_attn = torch_sdpa_attn
        if self.flash_attn and not IMPORT_FLASH:
            raise RuntimeError(
                f"flash_attn_func was imported with err {IMPORT_FLASH_ERR}. "
                "Please install flash_attn or use --no_flash flag. "
                "If you have already done this, "
                "--force-reinstall flag might be useful"
            )

    def forward_qkv(
        self, query: Tensor, key: Tensor, value: Tensor
    ) -> Tuple[Tensor, Tensor, Tensor]:
        """
        Projects the inputs into queries, keys, and values for multi-head attention.
        """
        b = query.size(0)
        q = self.linear_q(query).view(b, -1, self.h, self.d_k)
        k = self.linear_k(key).view(b, -1, self.h, self.d_k)
        v = self.linear_v(value).view(b, -1, self.h, self.d_k)
        if self.flash_attn:
            return q, k, v
        return q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)

    def forward_attention(
        self, value: Tensor, scores: Tensor, mask: Optional[Tensor]
    ) -> Tensor:
        """
        Computes the scaled dot-product attention given the projected values and scores.
        """
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
    """
    Relative Position Multi-Head Attention module.
    """

    def __init__(self, n_head: int, n_feat: int):
        super().__init__(n_head, n_feat)
        self.linear_pos = nn.Linear(n_feat, n_feat, bias=False)
        self.pos_bias_u = nn.Parameter(torch.FloatTensor(self.h, self.d_k))
        self.pos_bias_v = nn.Parameter(torch.FloatTensor(self.h, self.d_k))

    def rel_shift(self, x: Tensor) -> Tensor:
        b, h, qlen, pos_len = x.size()
        x = torch.nn.functional.pad(x, pad=(1, 0))
        x = x.view(b, h, -1, qlen)
        return x[:, :, 1:].view(b, h, qlen, pos_len)

    def forward(
        self,
        query: Tensor,
        key: Tensor,
        value: Tensor,
        pos_emb: Tensor,
        mask: Optional[Tensor] = None,
    ) -> Tensor:
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
    """
    Rotary Position Multi-Head Attention module.
    """

    def forward(
        self,
        query: Tensor,
        key: Tensor,
        value: Tensor,
        pos_emb: List[Tensor],
        mask: Optional[Tensor] = None,
    ) -> Tensor:
        b, t, _ = value.size()
        query = query.transpose(0, 1).view(t, b, self.h, self.d_k)
        key = key.transpose(0, 1).view(t, b, self.h, self.d_k)
        value = value.transpose(0, 1).view(t, b, self.h, self.d_k)

        cos, sin = pos_emb
        query, key = apply_rotary_pos_emb(query, key, cos, sin, offset=0)

        q, k, v = self.forward_qkv(
            query.view(t, b, self.h * self.d_k).transpose(0, 1),
            key.view(t, b, self.h * self.d_k).transpose(0, 1),
            value.view(t, b, self.h * self.d_k).transpose(0, 1),
        )

        if self.flash_attn:
            if mask is None:
                scores = flash_attn_func(q, k, v)
            else:
                scores = apply_masked_flash_attn(q, k, v, mask, self.h, self.d_k)
            scores = scores.view(b, -1, self.h * self.d_k)
            return self.linear_out(scores)
        elif self.torch_sdpa_attn:
            attn_mask = None if mask is None else ~mask.unsqueeze(1)
            attn_output = F.scaled_dot_product_attention(
                q,
                k,
                v,
                attn_mask=attn_mask,
            )
            attn_output = attn_output.transpose(1, 2).reshape(b, t, self.h * self.d_k)
            return self.linear_out(attn_output)
        else:
            scores = torch.matmul(q, k.transpose(-2, -1) / math.sqrt(self.d_k))
            return self.forward_attention(v, scores, mask)


class PositionalEncoding(nn.Module, ABC):
    """
    Base class of Positional Encodings.
    """

    def __init__(self, dim: int, base: int):
        super().__init__()
        self.dim = dim
        self.base = base

    @abstractmethod
    def create_pe(self, length: int, device: torch.device) -> Optional[Tensor]:
        pass

    def extend_pe(self, length: int, device: torch.device):
        """
        Extends the positional encoding buffer to process longer sequences.
        """
        pe = self.create_pe(length, device)
        if pe is None:
            return
        if hasattr(self, "pe"):
            self.pe = pe
        else:
            self.register_buffer("pe", pe, persistent=False)


class RelPositionalEmbedding(PositionalEncoding):
    """
    Relative Positional Embedding module.
    """

    def create_pe(self, length: int, device: torch.device) -> Optional[Tensor]:
        """
        Creates the relative positional encoding matrix.
        """
        if hasattr(self, "pe") and self.pe.shape[1] >= 2 * length - 1:
            return None
        positions = torch.arange(length - 1, -length, -1, device=device).unsqueeze(1)
        pos_length = positions.size(0)
        pe = torch.zeros(pos_length, self.dim, device=positions.device)
        div_term = torch.exp(
            torch.arange(0, self.dim, 2, device=pe.device)
            * -(math.log(10000.0) / self.dim)
        )
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
    """
    Rotary Positional Embedding module.
    """

    def create_pe(self, length: int, device: torch.device) -> Optional[Tensor]:
        """
        Creates or extends the rotary positional encoding matrix.
        """
        if hasattr(self, "pe") and self.pe.size(0) >= 2 * length:
            return None
        positions = torch.arange(0, length, dtype=torch.float32, device=device)
        inv_freq = 1.0 / (
            self.base ** (torch.arange(0, self.dim, 2).float() / self.dim)
        )
        t = torch.arange(length, device=positions.device).type_as(inv_freq)
        freqs = torch.einsum("i,j->ij", t, inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1).to(positions.device)
        return torch.cat([emb.cos()[:, None, None, :], emb.sin()[:, None, None, :]])

    def forward(self, x: torch.Tensor) -> Tuple[Tensor, List[Tensor]]:
        cos_emb = self.pe[0 : x.shape[1]]
        half_pe = self.pe.shape[0] // 2
        sin_emb = self.pe[half_pe : half_pe + x.shape[1]]
        return x, [cos_emb, sin_emb]


class ConformerConvolution(nn.Module):
    """
    Conformer Convolution module.
    """

    def __init__(
        self,
        d_model: int,
        kernel_size: int,
        norm_type: str,
    ):
        super().__init__()
        assert (kernel_size - 1) % 2 == 0
        assert norm_type in ["batch_norm", "layer_norm"]
        self.norm_type = norm_type
        self.pointwise_conv1 = nn.Conv1d(d_model, d_model * 2, kernel_size=1)
        self.depthwise_conv = nn.Conv1d(
            in_channels=d_model,
            out_channels=d_model,
            kernel_size=kernel_size,
            padding=(kernel_size - 1) // 2,
            groups=d_model,
            bias=True,
        )
        self.batch_norm = (
            nn.BatchNorm1d(d_model)
            if norm_type == "batch_norm"
            else nn.LayerNorm(d_model)
        )
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
    """
    Conformer Feed Forward module.
    """

    def __init__(self, d_model: int, d_ff: int, use_bias=True):
        super().__init__()
        self.linear1 = nn.Linear(d_model, d_ff, bias=use_bias)
        self.activation = nn.SiLU()
        self.linear2 = nn.Linear(d_ff, d_model, bias=use_bias)

    def forward(self, x: Tensor) -> Tensor:
        return self.linear2(self.activation(self.linear1(x)))


class ConformerLayer(nn.Module):
    """
    Conformer Layer module.
    This module combines several submodules including feed forward networks,
    depthwise separable convolution, and multi-head self-attention
    to form a single Conformer block.
    """

    def __init__(
        self,
        d_model: int,
        d_ff: int,
        self_attention_model: str,
        n_heads: int = 16,
        conv_norm_type: str = "batch_norm",
        conv_kernel_size: int = 31,
        flash_attn: bool = False,
    ):
        super().__init__()
        self.fc_factor = 0.5
        self.norm_feed_forward1 = nn.LayerNorm(d_model)
        self.feed_forward1 = ConformerFeedForward(d_model=d_model, d_ff=d_ff)
        self.norm_conv = nn.LayerNorm(d_model)
        self.conv = ConformerConvolution(
            d_model=d_model,
            kernel_size=conv_kernel_size,
            norm_type=conv_norm_type,
        )
        self.norm_self_att = nn.LayerNorm(d_model)
        if self_attention_model == "rotary":
            self.self_attn: nn.Module = RotaryPositionMultiHeadAttention(
                n_head=n_heads,
                n_feat=d_model,
                flash_attn=flash_attn,
                torch_sdpa_attn=not flash_attn,
            )
        else:
            assert not flash_attn, "Not supported flash_attn for rel_pos"
            self.self_attn = RelPositionMultiHeadAttention(
                n_head=n_heads,
                n_feat=d_model,
            )
        self.norm_feed_forward2 = nn.LayerNorm(d_model)
        self.feed_forward2 = ConformerFeedForward(d_model=d_model, d_ff=d_ff)
        self.norm_out = nn.LayerNorm(d_model)

    def forward(
        self,
        x: Tensor,
        pos_emb: Union[Tensor, List[Tensor]],
        att_mask: Optional[Tensor] = None,
        pad_mask: Optional[Tensor] = None,
    ) -> Tensor:
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
    """
    Conformer Encoder module.
    This module encapsulates the entire Conformer encoder architecture,
    consisting of a StridingSubsampling layer, positional embeddings, and
    a stack of Conformer Layers.
    It serves as the main component responsible for processing speech features.
    """

    def __init__(
        self,
        feat_in: int = 64,
        n_layers: int = 16,
        d_model: int = 768,
        subsampling: str = "conv2d",
        subs_kernel_size: int = 3,
        subsampling_factor: int = 4,
        ff_expansion_factor: int = 4,
        self_attention_model: str = "rotary",
        n_heads: int = 16,
        pos_emb_max_len: int = 5000,
        conv_norm_type: str = "batch_norm",
        conv_kernel_size: int = 31,
        flash_attn: bool = False,
    ):
        super().__init__()
        self.feat_in = feat_in
        assert self_attention_model in [
            "rotary",
            "rel_pos",
        ], f"Not supported attn = {self_attention_model}"

        self.pre_encode = StridingSubsampling(
            subsampling=subsampling,
            kernel_size=subs_kernel_size,
            subsampling_factor=subsampling_factor,
            feat_in=feat_in,
            feat_out=d_model,
            conv_channels=d_model,
        )

        self.pos_emb_max_len = pos_emb_max_len
        if self_attention_model == "rotary":
            self.pos_enc: PositionalEncoding = RotaryPositionalEmbedding(
                d_model // n_heads, pos_emb_max_len
            )
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
                conv_kernel_size=conv_kernel_size,
                flash_attn=flash_attn,
            )
            self.layers.append(layer)

    def input_example(
        self,
        batch_size: int = 1,
        seqlen: int = 200,
    ) -> Tuple[Tensor, Tensor]:
        device = next(self.parameters()).device
        features = torch.zeros(batch_size, self.feat_in, seqlen)
        feature_lengths = torch.full([batch_size], features.shape[-1])
        return features.float().to(device), feature_lengths.to(device)

    def input_names(self) -> List[str]:
        return ["audio_signal", "length"]

    def output_names(self) -> List[str]:
        return ["encoded", "encoded_len"]

    def dynamic_axes(self) -> Dict[str, Dict[int, str]]:
        return {
            "audio_signal": {0: "batch_size", 2: "seq_len"},
            "length": {0: "batch_size"},
            "encoded": {0: "batch_size", 1: "seq_len"},
            "encoded_len": {0: "batch_size"},
        }

    def forward(self, audio_signal: Tensor, length: Tensor) -> Tuple[Tensor, Tensor]:
        if not hasattr(self.pos_enc, "pe"):
            self.pos_enc.extend_pe(self.pos_emb_max_len, audio_signal.device)

        audio_signal, length = self.pre_encode(
            x=audio_signal.transpose(1, 2), lengths=length
        )

        max_len = audio_signal.size(1)
        audio_signal, pos_emb = self.pos_enc(x=audio_signal)

        pad_mask = torch.arange(0, max_len, device=audio_signal.device).expand(
            length.size(0), -1
        ) < length.unsqueeze(-1)

        att_mask = None
        if audio_signal.shape[0] > 1:
            att_mask = pad_mask.unsqueeze(1).repeat([1, max_len, 1])
            att_mask = torch.logical_and(att_mask, att_mask.transpose(1, 2))
            att_mask = ~att_mask

        pad_mask = ~pad_mask

        for layer in self.layers:
            audio_signal = layer(
                x=audio_signal,
                pos_emb=pos_emb,
                att_mask=att_mask,
                pad_mask=pad_mask,
            )

        return audio_signal.transpose(1, 2), length


# === VAD_UTILS.PY CONTENT ===

def get_pipeline(device: torch.device) -> Pipeline:
    """
    Retrieves a PyAnnote voice activity detection pipeline and move it to the specified device.
    The pipeline is loaded only once and reused across subsequent calls.
    It requires the Hugging Face API token to be set in the HF_TOKEN environment variable.
    """
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE.to(device)

    try:
        hf_token = os.environ["HF_TOKEN"]
    except KeyError as exc:
        raise ValueError("HF_TOKEN environment variable is not set") from exc

    with torch.serialization.safe_globals(
        [
            TorchVersion,
            Problem,
            Specifications,
            Resolution,
        ]
    ):
        model = Model.from_pretrained("pyannote/segmentation-3.0", token=hf_token)
    _PIPELINE = VoiceActivityDetection(segmentation=model)
    _PIPELINE.instantiate({"min_duration_on": 0.0, "min_duration_off": 0.0})

    return _PIPELINE.to(device)


def segment_audio_file(
    wav_input: Union[np.ndarray, Tensor],
    sr: int,
    max_duration: float = 22.0,
    min_duration: float = 15.0,
    strict_limit_duration: float = 30.0,
    new_chunk_threshold: float = 0.2,
    device: torch.device = torch.device("cpu"),
) -> Tuple[List[torch.Tensor], List[Tuple[float, float]]]:
    """
    Segments an audio waveform into smaller chunks based on speech activity.
    The segmentation is performed using a PyAnnote voice activity detection pipeline.
    """
    if isinstance(wav_input, np.ndarray):
        audio = torch.from_numpy(wav_input.copy()).float()
    elif isinstance(wav_input, Tensor):
        audio = wav_input.float().clone()
    else:
        raise TypeError(f"Unsupported input type for VAD: {type(wav_input)}. Expected np.ndarray or Tensor.")

    # Ensure audio is 1D and on the correct device
    if audio.ndim > 1:
        audio = audio.flatten()
    audio = audio.to(device)

    pipeline = get_pipeline(device)
    # PyAnnote pipeline expects a dict with "waveform" and "sample_rate"
    sad_segments = pipeline({"waveform": audio.unsqueeze(0), "sample_rate": sr})

    segments: List[torch.Tensor] = []
    curr_duration = 0.0
    curr_start = 0.0
    curr_end = 0.0
    boundaries: List[Tuple[float, float]] = []

    def _update_segments(curr_start: float, curr_end: float, curr_duration: float):
        if curr_duration > strict_limit_duration:
            max_segments = int(curr_duration / strict_limit_duration) + 1
            segment_duration = curr_duration / max_segments
            curr_end = curr_start + segment_duration
            for _ in range(max_segments - 1):
                segments.append(audio[int(curr_start * sr) : int(curr_end * sr)])
                boundaries.append((curr_start, curr_end))
                curr_start = curr_end
                curr_end += segment_duration
        segments.append(audio[int(curr_start * sr) : int(curr_end * sr)])
        boundaries.append((curr_start, curr_end))

    # Concat segments from pipeline into chunks for asr according to max/min duration
    # Segments longer than strict_limit_duration are split manually
    for segment in sad_segments.get_timeline().support():
        start = max(0, segment.start)
        end = min(audio.shape[0] / sr, segment.end)
        if curr_duration > new_chunk_threshold and (
            curr_duration + (end - curr_end) > max_duration
            or curr_duration > min_duration
        ):
            _update_segments(curr_start, curr_end, curr_duration)
            curr_start = start
        curr_end = end
        curr_duration = curr_end - curr_start

    if curr_duration > new_chunk_threshold:
        _update_segments(curr_start, curr_end, curr_duration)

    return segments, boundaries


# === ONNX_UTILS.PY CONTENT ===

def infer_onnx(
    wav_input: Union[str, np.ndarray, Tensor],
    model_cfg: omegaconf.DictConfig,
    sessions: List[rt.InferenceSession],
    preprocessor: Optional[FeatureExtractor] = None,
    tokenizer: Optional[Tokenizer] = None,
    sample_rate: int = 16000
) -> Union[str, np.ndarray]:
    """Run ONNX sessions for the model, requires preprocessor instantiating"""
    model_name = model_cfg.model_name

    if preprocessor is None:
        preprocessor = hydra.utils.instantiate(model_cfg.preprocessor)
    if tokenizer is None and ("ctc" in model_name or "rnnt" in model_name):
        tokenizer = hydra.utils.instantiate(model_cfg.decoding).tokenizer

    input_signal = load_audio(wav_input, sample_rate=sample_rate)
    input_signal = preprocessor(
        input_signal.unsqueeze(0), torch.tensor([input_signal.shape[-1]])
    )[0].numpy()

    enc_sess = sessions[0]
    enc_inputs = {
        node.name: data
        for (node, data) in zip(
            enc_sess.get_inputs(),
            [input_signal.astype(DTYPE), [input_signal.shape[-1]]],
        )
    }
    enc_features = enc_sess.run(
        [node.name for node in enc_sess.get_outputs()], enc_inputs
    )[0]

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
            np.zeros(shape=(1, 1, model_cfg.head.decoder.pred_hidden), dtype=DTYPE),
        ]
        pred_sess, joint_sess = sessions[1:]
        for j in range(enc_features.shape[-1]):
            emitted_letters = 0
            while emitted_letters < MAX_LETTERS_PER_FRAME:
                pred_inputs = {
                    node.name: data
                    for (node, data) in zip(
                        pred_sess.get_inputs(), [np.array([[prev_token]])] + pred_states
                    )
                }
                pred_outputs = pred_sess.run(
                    [node.name for node in pred_sess.get_outputs()], pred_inputs
                )

                joint_inputs = {
                    node.name: data
                    for node, data in zip(
                        joint_sess.get_inputs(),
                        [enc_features[:, :, [j]], pred_outputs[0].swapaxes(1, 2)],
                    )
                }
                log_probs = joint_sess.run(
                    [node.name for node in joint_sess.get_outputs()], joint_inputs
                )
                token = log_probs[0].argmax(-1)[0][0]

                if token != blank_idx:
                    prev_token = int(token)
                    pred_states = pred_outputs[1:]
                    token_ids.append(int(token))
                    emitted_letters += 1
                else:
                    break

    return tokenizer.decode(token_ids)


def load_onnx(
    onnx_dir: str,
    model_version: str,
    provider: Optional[str] = None,
) -> Tuple[
    List[rt.InferenceSession], Union[omegaconf.DictConfig, omegaconf.ListConfig]
]:
    """Load ONNX sessions for the given versions and cpu / cuda provider"""
    if provider is None and "CUDAExecutionProvider" in rt.get_available_providers():
        provider = "CUDAExecutionProvider"
    elif provider is None:
        provider = "CPUExecutionProvider"

    opts = rt.SessionOptions()
    opts.intra_op_num_threads = 16
    opts.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
    opts.log_severity_level = 3

    model_cfg = omegaconf.OmegaConf.load(f"{onnx_dir}/{model_version}.yaml")

    if "rnnt" not in model_version and "ssl" not in model_version:
        model_path = f"{onnx_dir}/{model_version}.onnx"
        sessions = [
            rt.InferenceSession(model_path, providers=[provider], sess_options=opts)
        ]
    elif "ssl" in model_version:
        pth = f"{onnx_dir}/{model_version}"
        enc_sess = rt.InferenceSession(
            f"{pth}_encoder.onnx", providers=[provider], sess_options=opts
        )
        sessions = [enc_sess]
    else:
        pth = f"{onnx_dir}/{model_version}"
        enc_sess = rt.InferenceSession(
            f"{pth}_encoder.onnx", providers=[provider], sess_options=opts
        )
        pred_sess = rt.InferenceSession(
            f"{pth}_decoder.onnx", providers=[provider], sess_options=opts
        )
        joint_sess = rt.InferenceSession(
            f"{pth}_joint.onnx", providers=[provider], sess_options=opts
        )
        sessions = [enc_sess, pred_sess, joint_sess]

    return sessions, model_cfg


# === UTILS.PY CONTENT ===

def onnx_converter(
    model_name: str,
    module: torch.nn.Module,
    out_dir: str,
    inputs: Optional[Tuple[Tensor, ...]] = None,
    input_names: Optional[List[str]] = None,
    output_names: Optional[List[str]] = None,
    dynamic_axes: Optional[
        Union[Dict[str, List[int]], Dict[str, Dict[int, str]]]
    ] = None,
    opset_version: int = 17,
):
    if inputs is None:
        inputs = module.input_example()  # type: ignore[operator]
    if input_names is None:
        input_names = module.input_names()  # type: ignore[operator]
    if output_names is None:
        output_names = module.output_names()  # type: ignore[operator]

    Path(out_dir).mkdir(exist_ok=True, parents=True)
    out_path = str(Path(out_dir) / f"{model_name}.onnx")
    saved_dtype = next(module.parameters()).dtype
    with warnings.catch_warnings(), torch.no_grad():
        warnings.simplefilter("ignore", category=UserWarning)
        warnings.simplefilter("ignore", category=TracerWarning)
        torch.onnx.export(
            module.to(torch.float32),
            inputs,
            out_path,
            input_names=input_names,
            output_names=output_names,
            dynamic_axes=dynamic_axes,
            opset_version=opset_version,
        )
    print(f"Successfully ported onnx {model_name} to {out_path}.")
    module.to(saved_dtype)


def format_time(seconds: float) -> str:
    """
    Formats time in seconds to HH:MM:SS:mm format.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    full_seconds = int(seconds)
    milliseconds = int((seconds - full_seconds) * 100)

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{full_seconds:02}:{milliseconds:02}"
    return f"{minutes:02}:{full_seconds:02}:{milliseconds:02}"


def rtt_half(x: Tensor) -> Tensor:
    x1, x2 = x[..., : x.shape[-1] // 2], x[..., x.shape[-1] // 2 :]
    return torch.cat([-x2, x1], dim=x1.ndim - 1)


def apply_rotary_pos_emb(
    q: Tensor, k: Tensor, cos: Tensor, sin: Tensor, offset: int = 0
) -> Tuple[Tensor, Tensor]:
    """
    Applies Rotary Position Embeddings to query and key tensors.
    """
    cos, sin = (
        cos[offset : q.shape[0] + offset, ...],
        sin[offset : q.shape[0] + offset, ...],
    )
    return (q * cos) + (rtt_half(q) * sin), (k * cos) + (rtt_half(k) * sin)


def apply_masked_flash_attn(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    mask: Tensor,
    h: int,
    d_k: int,
) -> Tensor:
    """
    Applies Flash Attention with padding masks.
    """

    from einops import rearrange
    from flash_attn import flash_attn_varlen_func
    from flash_attn.bert_padding import pad_input, unpad_input

    pad_mask = ~mask[:, 0, :]
    b, t = pad_mask.shape
    q = q.view(b, t, h * d_k)
    k = k.view(b, t, h * d_k)
    v = v.view(b, t, h * d_k)

    q_unpad, indices_q, _, max_seqlen_q = unpad_input(q, pad_mask)[:4]
    q_unpad = rearrange(q_unpad, "nnz (h d) -> nnz h d", h=h)

    k_unpad = unpad_input(k, pad_mask)[0]
    k_unpad = rearrange(k_unpad, "nnz (h d) -> nnz h d", h=h)

    v_unpad = unpad_input(v, pad_mask)[0]
    v_unpad = rearrange(v_unpad, "nnz (h d) -> nnz h d", h=h)

    lengths_q = pad_mask.sum(1).to(torch.int32).to(q.device)
    cu_seqlens_q = F.pad(lengths_q.cumsum(0), (1, 0), value=0).to(torch.int32)
    max_seqlen_q = torch.max(lengths_q)

    output_unpad = flash_attn_varlen_func(
        q_unpad,
        k_unpad,
        v_unpad,
        cu_seqlens_q,
        cu_seqlens_q,
        max_seqlen_q,
        max_seqlen_q,
    )

    scores = pad_input(
        rearrange(output_unpad, "nnz h d -> nnz (h d)"),
        indices_q,
        b,
        t,
    )

    return scores


def download_short_audio():
    """Download test audio file if not exists"""
    audio_file = "example.wav"
    if not os.path.exists(audio_file):
        os.system(
            'wget -O example.wav "https://cdn.chatwm.opensmodel.sberdevices.ru/GigaAM/example.wav"'
        )
    assert os.path.exists(audio_file), "Short audio file not found"
    return audio_file


def download_long_audio():
    """Download test audio file if not exists"""
    audio_file = "long_example.wav"
    if not os.path.exists(audio_file):
        os.system(
            'wget -O long_example.wav "https://cdn.chatwm.opensmodel.sberdevices.ru/GigaAM/long_example.wav"'
        )
    assert os.path.exists(audio_file), "Long audio file not found"
    return audio_file


class AudioDataset(torch.utils.data.Dataset):
    """
    Helper class for creating batched inputs
    """

    def __init__(self, lst: List[Union[str, np.ndarray, torch.Tensor]]):
        if len(lst) == 0:
            raise ValueError("AudioDataset cannot be initialized with an empty list")
        assert isinstance(
            lst[0], (str, np.ndarray, torch.Tensor)
        ), f"Unexpected dtype: {type(lst[0])}"
        self.lst = lst

    def __len__(self):
        return len(self.lst)

    def __getitem__(self, idx):
        item = self.lst[idx]
        if isinstance(item, str):
            wav_tns = load_audio(item)
        elif isinstance(item, np.ndarray):
            wav_tns = torch.from_numpy(item)
        elif isinstance(item, torch.Tensor):
            wav_tns = item
        else:
            raise RuntimeError(f"Unexpected sample type: {type(item)} at idx={idx}")
        return wav_tns

    @staticmethod
    def collate(wavs):
        lengths = torch.tensor([len(wav) for wav in wavs])
        max_len = lengths.max().item()
        wav_tns = torch.zeros(len(wavs), max_len, dtype=wavs[0].dtype)
        for idx, wav in enumerate(wavs):
            wav_tns[idx, : wav.shape[-1]] = wav.squeeze()
        return wav_tns, lengths


# === MODEL.PY CONTENT ===

class GigaAM(nn.Module):
    """
    Giga Acoustic Model: Self-Supervised Model for Speech Tasks
    """

    def __init__(self, cfg: omegaconf.DictConfig):
        super().__init__()
        self.cfg = cfg
        self.preprocessor = hydra.utils.instantiate(self.cfg.preprocessor)
        self.encoder = hydra.utils.instantiate(self.cfg.encoder)

    def forward(
        self, features: Tensor, feature_lengths: Tensor
    ) -> Tuple[Tensor, Tensor]:
        """
        Perform forward pass through the preprocessor and encoder.
        """
        features, feature_lengths = self.preprocessor(features, feature_lengths)
        if self._device.type == "cpu":
            return self.encoder(features, feature_lengths)
        with torch.autocast(device_type=self._device.type, dtype=torch.float16):
            return self.encoder(features, feature_lengths)

    @property
    def _device(self) -> torch.device:
        return next(self.parameters()).device

    @property
    def _dtype(self) -> torch.dtype:
        return next(self.parameters()).dtype

    def prepare_wav(
        self, wav_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE
    ) -> Tuple[Tensor, Tensor]:
        """
        Prepare an audio file or array for processing by loading it onto
        the correct device and converting its format.

        Parameters
        ----------
        wav_input : Union[str, np.ndarray, Tensor]
            Path to audio file, numpy array, or torch tensor with audio data.
            If array/tensor, values should be in range [-1.0, 1.0] or will be normalized.
        sample_rate : int
            Sample rate of the provided array/tensor. Ignored for file inputs.
        """
        if isinstance(wav_input, str):
            # Загрузка из файла
            wav = load_audio(wav_input)
            current_sr = SAMPLE_RATE
        elif isinstance(wav_input, np.ndarray):
            # Конвертация numpy массива в torch tensor
            if wav_input.size == 0:
                raise ValueError("Audio array is empty")
            wav = torch.from_numpy(wav_input.copy()).float()
            current_sr = sample_rate
            # Убеждаемся, что это одномерный массив
            if wav.ndim > 1:
                wav = wav.flatten()
            # Нормализация, если значения не в диапазоне [-1, 1]
            max_val = wav.abs().max()
            if max_val > 0:
                if max_val > 32768.0:
                    wav = wav / 32768.0  # Нормализация для int16 формата
                elif max_val > 1.0:
                    wav = wav / max_val  # Нормализация к диапазону [-1, 1]
        elif isinstance(wav_input, Tensor):
            # Использование torch tensor напрямую
            if wav_input.numel() == 0:
                raise ValueError("Audio tensor is empty")
            wav = wav_input.float().clone()
            current_sr = sample_rate
            # Убеждаемся, что это одномерный массив
            if wav.ndim > 1:
                wav = wav.flatten()
            # Нормализация, если значения не в диапазоне [-1, 1]
            max_val = wav.abs().max()
            if max_val > 0:
                if max_val > 32768.0:
                    wav = wav / 32768.0  # Нормализация для int16 формата
                elif max_val > 1.0:
                    wav = wav / max_val  # Нормализация к диапазону [-1, 1]
        else:
            raise TypeError(f"Unsupported input type: {type(wav_input)}. Expected str, np.ndarray, or Tensor.")

        # Ресемплинг к частоте модели, если пришёл массив с другим sample_rate
        if not isinstance(wav_input, str) and current_sr != SAMPLE_RATE:
            if wav.numel() > 0:
                wav = taF.resample(
                    wav.unsqueeze(0), orig_freq=current_sr, new_freq=SAMPLE_RATE
                ).squeeze(0)

        # Проверка минимальной длины аудио ПОСЛЕ ресемплинга (минимум 0.1 секунды)
        min_length = int(SAMPLE_RATE * 0.1)
        if wav.numel() < min_length:
            raise ValueError(f"Audio is too short: {wav.numel()} samples. Minimum required: {min_length} samples (~0.1 seconds at {SAMPLE_RATE}Hz)")

        wav = wav.to(self._device).to(self._dtype).unsqueeze(0)
        length = torch.full([1], wav.shape[-1], device=self._device)
        return wav, length

    def embed_audio(
        self, wav_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE
    ) -> Tuple[Tensor, Tensor]:
        """
        Extract audio representations using the GigaAM model.

        Parameters
        ----------
        wav_input : Union[str, np.ndarray, Tensor]
            Path to audio file, numpy array, or torch tensor with audio data.
        """
        wav, length = self.prepare_wav(wav_input, sample_rate=sample_rate)
        encoded, encoded_len = self.forward(wav, length)
        return encoded, encoded_len

    def to_onnx(self, dir_path: str = ".") -> None:
        """
        Export onnx model encoder to the specified dir.
        """
        self._to_onnx(dir_path)
        omegaconf.OmegaConf.save(self.cfg, f"{dir_path}/{self.cfg.model_name}.yaml")

    def _to_onnx(self, dir_path: str = ".") -> None:
        """
        Export onnx model encoder to the specified dir.
        """
        onnx_converter(
            model_name=f"{self.cfg.model_name}_encoder",
            out_dir=dir_path,
            module=self.encoder,
            dynamic_axes=self.encoder.dynamic_axes(),
        )


class GigaAMASR(GigaAM):
    """
    Giga Acoustic Model for Speech Recognition
    """

    def __init__(self, cfg: omegaconf.DictConfig):
        super().__init__(cfg)
        self.head = hydra.utils.instantiate(self.cfg.head)
        self.decoding = hydra.utils.instantiate(self.cfg.decoding)

    @torch.inference_mode()
    def transcribe(
        self, wav_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE
    ) -> str:
        """
        Transcribes a short audio file or array into text.

        Parameters
        ----------
        wav_input : Union[str, np.ndarray, Tensor]
            Path to audio file, numpy array, or torch tensor with audio data.
            If array/tensor, values should be in range [-1.0, 1.0] or will be normalized.
        """

        wav, length = self.prepare_wav(wav_input, sample_rate=sample_rate)
        if length.item() > LONGFORM_THRESHOLD:
            raise ValueError("Too long audio, use 'transcribe_longform' method.")

        encoded, encoded_len = self.forward(wav, length)
        return self.decoding.decode(self.head, encoded, encoded_len)[0]

    def forward_for_export(self, features: Tensor, feature_lengths: Tensor) -> Tensor:
        """
        Encoder-decoder forward to save model entirely in onnx format.
        """
        return self.head(self.encoder(features, feature_lengths)[0])

    def _to_onnx(self, dir_path: str = ".") -> None:
        """
        Export onnx ASR model.
        `ctc`:  exported entirely in encoder-decoder format.
        `rnnt`: exported in encoder/decoder/joint parts separately.
        """
        if "ctc" in self.cfg.model_name:
            saved_forward = self.forward
            self.forward = self.forward_for_export  # type: ignore[assignment, method-assign]
            try:
                onnx_converter(
                    model_name=self.cfg.model_name,
                    out_dir=dir_path,
                    module=self,
                    inputs=self.encoder.input_example(),
                    input_names=["features", "feature_lengths"],
                    output_names=["log_probs"],
                    dynamic_axes={
                        "features": {0: "batch_size", 2: "seq_len"},
                        "feature_lengths": {0: "batch_size"},
                        "log_probs": {0: "batch_size", 1: "seq_len"},
                    },
                )
            finally:
                self.forward = saved_forward  # type: ignore[assignment, method-assign]
        else:
            super()._to_onnx(dir_path)  # export encoder
            onnx_converter(
                model_name=f"{self.cfg.model_name}_decoder",
                out_dir=dir_path,
                module=self.head.decoder,
            )
            onnx_converter(
                model_name=f"{self.cfg.model_name}_joint",
                out_dir=dir_path,
                module=self.head.joint,
            )

    @torch.inference_mode()
    def transcribe_longform(
        self, wav_input: Union[np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE, **kwargs
    ) -> List[Dict[str, Union[str, Tuple[float, float]]]]:
        """
        Transcribes a long audio array by splitting it into segments and
        then transcribing each segment.
        """
        transcribed_segments = []
        segments, boundaries = segment_audio_file(
            wav_input, SAMPLE_RATE, device=self._device, **kwargs
        )
        for segment, segment_boundaries in zip(segments, boundaries):
            wav = segment.to(self._device).unsqueeze(0).to(self._dtype)
            length = torch.full([1], wav.shape[-1], device=self._device)
            encoded, encoded_len = self.forward(wav, length)
            result = self.decoding.decode(self.head, encoded, encoded_len)[0]
            transcribed_segments.append(
                {"transcription": result, "boundaries": segment_boundaries}
            )
        return transcribed_segments


class GigaAMEmo(GigaAM):
    """
    Giga Acoustic Model for Emotion Recognition
    """

    def __init__(self, cfg: omegaconf.DictConfig):
        super().__init__(cfg)
        self.head = hydra.utils.instantiate(self.cfg.head)
        self.id2name = cfg.id2name

    def get_probs(
        self, wav_input: Union[str, np.ndarray, Tensor], sample_rate: int = SAMPLE_RATE
    ) -> Dict[str, float]:
        """
        Calculate probabilities for each emotion class based on the provided audio file or array.

        Parameters
        ----------
        wav_input : Union[str, np.ndarray, Tensor]
            Path to audio file, numpy array, or torch tensor with audio data.
        """
        wav, length = self.prepare_wav(wav_input, sample_rate=sample_rate)
        encoded, _ = self.forward(wav, length)
        encoded_pooled = nn.functional.avg_pool1d(
            encoded, kernel_size=encoded.shape[-1]
        ).squeeze(-1)

        logits = self.head(encoded_pooled)[0]
        probs = nn.functional.softmax(logits, dim=-1).detach().tolist()

        return {self.id2name[i]: probs[i] for i in range(len(self.id2name))}

    def forward_for_export(self, features: Tensor, feature_lengths: Tensor) -> Tensor:
        """
        Encoder-decoder forward to save model entirely in onnx format.
        """
        encoded, _ = self.encoder(features, feature_lengths)
        enc_pooled = encoded.mean(dim=-1)
        return nn.functional.softmax(self.head(enc_pooled), dim=-1)

    def _to_onnx(self, dir_path: str = ".") -> None:
        """
        Export onnx Emo model.
        """
        saved_forward = self.forward
        self.forward = self.forward_for_export  # type: ignore[assignment, method-assign]
        try:
            onnx_converter(
                model_name=self.cfg.model_name,
                out_dir=dir_path,
                module=self,
                inputs=self.encoder.input_example(),
                input_names=["features", "feature_lengths"],
                output_names=["probs"],
                dynamic_axes={
                    "features": {0: "batch_size", 2: "seq_len"},
                    "feature_lengths": {0: "batch_size"},
                    "probs": {0: "batch_size", 1: "seq_len"},
                },
            )
        finally:
            self.forward = saved_forward  # type: ignore[assignment, method-assign]


# === __INIT__.PY CONTENT ===

__all__ = [
    "GigaAM",
    "GigaAMASR",
    "GigaAMEmo",
    "load_audio",
    "format_time",
    "load_model",
]


def _download_file(file_url: str, file_path: str):
    """Helper to download a file if not already cached."""
    if os.path.exists(file_path):
        return file_path

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with urllib.request.urlopen(file_url) as source, open(file_path, "wb") as output:
        with tqdm(
            total=int(source.info().get("Content-Length", 0)),
            ncols=80,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as loop:
            while True:
                buffer = source.read(8192)
                if not buffer:
                    break

                output.write(buffer)
                loop.update(len(buffer))

    return file_path


def _download_model(model_name: str, download_root: str) -> Tuple[str, str]:
    """Download the model weights if not already cached."""
    short_names = ["ctc", "rnnt", "e2e_ctc", "e2e_rnnt", "ssl"]
    possible_names = short_names + list(_MODEL_HASHES.keys())
    if model_name not in possible_names:
        raise ValueError(
            f"Model '{model_name}' not found. Available model names: {possible_names}"
        )

    if model_name in short_names:
        model_name = f"v3_{model_name}"
    model_url = f"{_URL_DIR}/{model_name}.ckpt"
    model_path = os.path.join(download_root, model_name + ".ckpt")
    return model_name, _download_file(model_url, model_path)


def _download_tokenizer(model_name: str, download_root: str) -> Optional[str]:
    """Download the tokenizer if required and return its path."""
    if model_name != "v1_rnnt" and "e2e" not in model_name:
        return None  # No tokenizer required for this model

    tokenizer_url = f"{_URL_DIR}/{model_name}_tokenizer.model"
    tokenizer_path = os.path.join(download_root, model_name + "_tokenizer.model")
    return _download_file(tokenizer_url, tokenizer_path)


def hash_path(ckpt_path: str) -> str:
    """Calculate binary file hash for checksum"""
    return hashlib.md5(open(ckpt_path, "rb").read()).hexdigest()


def _normalize_device(device: Optional[Union[str, torch.device]]) -> torch.device:
    """Normalize device parameter to torch.device."""
    if device is None:
        device_str = "cuda" if torch.cuda.is_available() else "cpu"
        return torch.device(device_str)
    if isinstance(device, str):
        return torch.device(device)
    return device


def load_model(
    model_name: str,
    fp16_encoder: bool = True,
    use_flash: Optional[bool] = False,
    device: Optional[Union[str, torch.device]] = None,
    download_root: Optional[str] = None,
) -> Union[GigaAM, GigaAMEmo, GigaAMASR]:
    """
    Load the GigaAM model by name.

    Parameters
    ----------
    model_name : str
        The name of the model to load.
    fp16_encoder:
        Whether to convert encoder weights to FP16 precision.
    use_flash : Optional[bool]
        Whether to use flash_attn if the model allows it (requires the flash_attn library installed).
        Default to False.
    device : Optional[Union[str, torch.device]]
        The device to load the model onto. Defaults to "cuda" if available, otherwise "cpu".
    download_root : Optional[str]
        The directory to download the model to. Defaults to "~/.cache/gigaam".
    """
    device_obj = _normalize_device(device)

    if download_root is None:
        download_root = _CACHE_DIR

    model_name, model_path = _download_model(model_name, download_root)
    tokenizer_path = _download_tokenizer(model_name, download_root)

    assert (
        hash_path(model_path) == _MODEL_HASHES[model_name]
    ), f"Model checksum failed. Please run `rm {model_path}` and reload the model"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=(FutureWarning))
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)

    if use_flash is not None:
        checkpoint["cfg"].encoder.flash_attn = use_flash
    if checkpoint["cfg"].encoder.get("flash_attn", False) and device_obj.type == "cpu":
        logging.warning("flash_attn is not supported on CPU. Disabling it...")
        checkpoint["cfg"].encoder.flash_attn = False

    if tokenizer_path is not None:
        checkpoint["cfg"].decoding.model_path = tokenizer_path

    if "ssl" in model_name:
        model = GigaAM(checkpoint["cfg"])
    elif "emo" in model_name:
        model = GigaAMEmo(checkpoint["cfg"])
    else:
        model = GigaAMASR(checkpoint["cfg"])

    model.load_state_dict(checkpoint["state_dict"])
    model = model.eval()

    if fp16_encoder and device_obj.type != "cpu":
        model.encoder = model.encoder.half()

    checkpoint["cfg"].model_name = model_name
    return model.to(device_obj)
