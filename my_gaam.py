# =====================================================================================
# asr_gigaam.py
#
# Полный автономный модуль распознавания речи для GigaAM v2 RNN-T (v2_rnnt.ckpt)
#
# Установка зависимостей (один раз):
#   pip install torch==2.2.2 torchaudio==2.2.2 numpy>=1.24
# FFmpeg должен быть установлен в системе (apt install ffmpeg / pacman -S ffmpeg / и т.п.)
#
# Использование:
#   from asr_gigaam import GigaASR
#   asr = GigaASR("/path/to/v2_rnnt.ckpt", device="cpu")
#   print(asr.transcribe("audio.wav"))
#
# =====================================================================================

import os
import math
import numpy as np
import torch
import torchaudio
from torch import nn, Tensor
from subprocess import run, CalledProcessError
from typing import Dict, List, Tuple

# -----------------------
# Конфиги / константы
# -----------------------
SAMPLE_RATE = 16000


# -----------------------
# Утилиты: загрузка аудио
# -----------------------
def load_audio(path: str, sample_rate: int = SAMPLE_RATE) -> Tensor:
    """
    Загрузить любой аудиоформат через ffmpeg -> PCM16 -> float32 tensor в диапазоне [-1,1]
    Возвращает 1D тензор (num_samples,)
    """
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-threads", "0",
        "-i", path,
        "-f", "s16le",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-"
    ]
    try:
        proc = run(cmd, capture_output=True, check=True)
        raw = proc.stdout
    except CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg failed to read {path}: {exc}") from exc

    wav = torch.frombuffer(raw, dtype=torch.int16).float() / 32768.0
    return wav


# =====================================================================================
# FeatureExtractor (Log-Mel)
# =====================================================================================
class SpecScaler(nn.Module):
    def forward(self, x: Tensor) -> Tensor:
        return torch.log(x.clamp_(1e-9, 1e9))


class FeatureExtractor(nn.Module):
    """
    Mel spectrogram + log, возвращает (B, n_mels, T)
    """
    def __init__(self, sample_rate: int = SAMPLE_RATE, features: int = 64):
        super().__init__()
        self.sample_rate = sample_rate
        self.features = features
        self.hop_length = sample_rate // 100  # 10 ms

        self.featurizer = nn.Sequential(
            torchaudio.transforms.MelSpectrogram(
                sample_rate=sample_rate,
                n_fft=sample_rate // 40,
                win_length=sample_rate // 40,
                hop_length=self.hop_length,
                n_mels=features,
            ),
            SpecScaler()
        )

    def out_len(self, input_lengths: Tensor) -> Tensor:
        return input_lengths.div(self.hop_length, rounding_mode="floor").add(1).long()

    def forward(self, waveform: Tensor, length: Tensor) -> Tuple[Tensor, Tensor]:
        """
        waveform: (B, N) или (N,) -- в transcribe мы передаём (B,N)
        length: Tensor([N_samples])
        """
        # MelSpectrogram expects (..., time), batch dims are okay
        feats = self.featurizer(waveform)  # -> (B, n_mels, T)
        return feats, self.out_len(length)


# =====================================================================================
# Positional encoding (rotary)
# =====================================================================================
def rtt_half(x: Tensor) -> Tensor:
    x1, x2 = x[..., : x.shape[-1] // 2], x[..., x.shape[-1] // 2 :]
    return torch.cat([-x2, x1], dim=-1)


def apply_rotary_pos_emb(q: Tensor, k: Tensor, cos: Tensor, sin: Tensor, offset: int = 0):
    cos = cos[offset : q.shape[1] + offset, ...]
    sin = sin[offset : q.shape[1] + offset, ...]
    # q,k shape: (B, T, h, d)
    return (q * cos) + (rtt_half(q) * sin), (k * cos) + (rtt_half(k) * sin)


class RotaryPositionalEmbedding(nn.Module):
    def __init__(self, dim: int, base: int = 5000):
        """
        dim - half-dimension per head (d_model // n_heads)
        base - positional base
        """
        super().__init__()
        self.dim = dim
        self.base = base
        # buffer will be created on first forward via create_pe
        self.register_buffer("pe", torch.zeros(1), persistent=False)

    def create_pe(self, length: int, device: torch.device):
        if getattr(self, "pe", None) is not None and self.pe.numel() != 1 and self.pe.size(0) >= 2 * length:
            return
        pos = torch.arange(0, length, dtype=torch.float32, device=device)
        inv_freq = 1.0 / (self.base ** (torch.arange(0, self.dim, 2, device=device).float() / self.dim))
        freqs = torch.einsum("i,j->ij", pos, inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1)  # (L, dim*2)
        cos = emb.cos()
        sin = emb.sin()
        self.pe = torch.cat([cos, sin], dim=0)  # shape (2L, dim*?); we'll slice later

    def forward(self, x: Tensor):
        # x shape: (B, T, D)
        L = x.size(1)
        self.create_pe(L, x.device)
        cos = self.pe[:L].unsqueeze(1)  # (L,1,D)
        sin = self.pe[L : L + L].unsqueeze(1)
        # return pos_emb in shape convenient for apply_rotary_pos_emb
        return x, (cos, sin)


# =====================================================================================
# Attention (rotary)
# =====================================================================================
class RotaryAttention(nn.Module):
    def __init__(self, n_head: int, n_feat: int):
        super().__init__()
        assert n_feat % n_head == 0
        self.h = n_head
        self.d_k = n_feat // n_head
        self.linear_q = nn.Linear(n_feat, n_feat)
        self.linear_k = nn.Linear(n_feat, n_feat)
        self.linear_v = nn.Linear(n_feat, n_feat)
        self.linear_out = nn.Linear(n_feat, n_feat)

    def forward(self, query: Tensor, key: Tensor, value: Tensor, pos_emb, mask: Tensor = None):
        # query/key/value: (B, T, D)
        B, T, D = query.size()
        q = self.linear_q(query).view(B, T, self.h, self.d_k)
        k = self.linear_k(key).view(B, T, self.h, self.d_k)
        v = self.linear_v(value).view(B, T, self.h, self.d_k)

        cos, sin = pos_emb  # cos,sin shape (L,1,D) maybe
        # adapt shapes: cos,sin -> (B, T, h, d_k) by broadcasting
        # apply_rotary expects q,k shaped (B, T, h, d)
        q, k = apply_rotary_pos_emb(q, k, cos, sin)

        q = q.transpose(1, 2)  # (B, h, T, d)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_k)
        if mask is not None:
            scores = scores.masked_fill(mask[:, None, :, :], float("-inf"))

        attn = torch.softmax(scores, dim=-1)
        out = torch.matmul(attn, v)  # (B, h, T, d)
        out = out.transpose(1, 2).reshape(B, T, D)
        return self.linear_out(out)


# =====================================================================================
# Conformer building blocks
# =====================================================================================
class ConformerConvolution(nn.Module):
    def __init__(self, d_model: int, kernel_size: int):
        super().__init__()
        assert (kernel_size - 1) % 2 == 0
        self.pointwise_conv1 = nn.Conv1d(d_model, d_model * 2, kernel_size=1)
        self.depthwise_conv = nn.Conv1d(in_channels=d_model, out_channels=d_model, kernel_size=kernel_size,
                                        padding=(kernel_size - 1) // 2, groups=d_model, bias=True)
        self.batch_norm = nn.BatchNorm1d(d_model)
        self.activation = nn.SiLU()
        self.pointwise_conv2 = nn.Conv1d(d_model, d_model, kernel_size=1)

    def forward(self, x: Tensor, pad_mask: Tensor = None) -> Tensor:
        # x: (B, T, D) -> conv expects (B, D, T)
        x = x.transpose(1, 2)
        x = self.pointwise_conv1(x)
        x = nn.functional.glu(x, dim=1)
        if pad_mask is not None:
            x = x.masked_fill(pad_mask.unsqueeze(1), 0.0)
        x = self.depthwise_conv(x)
        x = self.batch_norm(x)
        x = self.activation(x)
        x = self.pointwise_conv2(x)
        return x.transpose(1, 2)


class ConformerFeedForward(nn.Module):
    def __init__(self, d_model: int, d_ff: int):
        super().__init__()
        self.linear1 = nn.Linear(d_model, d_ff)
        self.activation = nn.SiLU()
        self.linear2 = nn.Linear(d_ff, d_model)

    def forward(self, x: Tensor) -> Tensor:
        return self.linear2(self.activation(self.linear1(x)))


class ConformerLayer(nn.Module):
    def __init__(self, d_model: int, d_ff: int, n_heads: int, conv_kernel_size: int):
        super().__init__()
        self.fc_factor = 0.5
        self.norm_ff1 = nn.LayerNorm(d_model)
        self.ff1 = ConformerFeedForward(d_model, d_ff)
        self.norm_self_att = nn.LayerNorm(d_model)
        self.self_attn = RotaryAttention(n_head=n_heads, n_feat=d_model)
        self.norm_conv = nn.LayerNorm(d_model)
        self.conv = ConformerConvolution(d_model, conv_kernel_size)
        self.norm_ff2 = nn.LayerNorm(d_model)
        self.ff2 = ConformerFeedForward(d_model, d_ff)
        self.norm_out = nn.LayerNorm(d_model)

    def forward(self, x: Tensor, pos_emb, att_mask: Tensor = None, pad_mask: Tensor = None) -> Tensor:
        residual = x
        x = self.norm_ff1(x)
        x = self.ff1(x)
        residual = residual + x * self.fc_factor

        x = self.norm_self_att(residual)
        x = self.self_attn(x, x, x, pos_emb, att_mask)
        residual = residual + x

        x = self.norm_conv(residual)
        x = self.conv(x, pad_mask=pad_mask)
        residual = residual + x

        x = self.norm_ff2(residual)
        x = self.ff2(x)
        residual = residual + x * self.fc_factor

        x = self.norm_out(residual)
        return x


# =====================================================================================
# Subsampling (striding)
# =====================================================================================
class StridingSubsampling(nn.Module):
    def __init__(self, subsampling_factor: int, feat_in: int, feat_out: int, conv_channels: int):
        super().__init__()
        self._sampling_num = int(math.log(subsampling_factor, 2))
        self._stride = 2
        self._kernel_size = 3
        self._padding = (self._kernel_size - 1) // 2

        layers: List[nn.Module] = []
        in_channels = 1
        for _ in range(self._sampling_num):
            layers.append(
                nn.Conv2d(in_channels=in_channels, out_channels=conv_channels, kernel_size=self._kernel_size,
                          stride=self._stride, padding=self._padding)
            )
            layers.append(nn.ReLU())
            in_channels = conv_channels

        self.conv = nn.Sequential(*layers)
        # calculate output length after convs, needed for Linear
        out_length = self.calc_output_length(torch.tensor(feat_in))
        self.out = nn.Linear(conv_channels * int(out_length), feat_out)

    def calc_output_length(self, lengths: Tensor) -> Tensor:
        lengths = lengths.to(torch.float)
        add_pad = 2 * self._padding - self._kernel_size
        for _ in range(self._sampling_num):
            lengths = torch.div(lengths + add_pad, self._stride) + 1.0
            lengths = torch.floor(lengths)
        return lengths.to(dtype=torch.int)

    def forward(self, x: Tensor, lengths: Tensor) -> Tuple[Tensor, Tensor]:
        # x expected: (B, T, F)
        x = x.unsqueeze(1)  # (B,1,T,F)
        x = self.conv(x)  # (B, C, T', F')
        b, c, t, f = x.size()
        x = self.out(x.transpose(1, 2).reshape(b, t, -1))  # (B, T', feat_out)
        return x, self.calc_output_length(lengths)


# =====================================================================================
# Conformer Encoder (stack)
# =====================================================================================
class ConformerEncoder(nn.Module):
    def __init__(
        self,
        feat_in: int = 64,
        n_layers: int = 16,
        d_model: int = 768,
        subsampling_factor: int = 4,
        ff_expansion_factor: int = 4,
        self_attention_model: str = "rotary",
        pos_emb_max_len: int = 5000,
        n_heads: int = 16,
        conv_kernel_size: int = 31,
    ):
        super().__init__()
        self.feat_in = feat_in
        self.pre_encode = StridingSubsampling(subsampling_factor=subsampling_factor, feat_in=feat_in,
                                              feat_out=d_model, conv_channels=d_model)

        # rotary pos: dim per head = d_model // n_heads
        self.pos_enc = RotaryPositionalEmbedding(d_model // n_heads, pos_emb_max_len)

        self.layers = nn.ModuleList(
            [
                ConformerLayer(d_model, d_model * ff_expansion_factor, n_heads, conv_kernel_size)
                for _ in range(n_layers)
            ]
        )

    def input_example(self, batch_size: int = 1, seqlen: int = 200):
        device = next(self.parameters()).device
        features = torch.zeros(batch_size, self.feat_in, seqlen).to(device)
        feature_lengths = torch.full([batch_size], features.shape[-1]).to(device)
        return features.float().to(device), feature_lengths.to(device)

    def forward(self, features: Tensor, lengths: Tensor) -> Tuple[Tensor, Tensor]:
        """
        features: (B, feat_in, T)
        returns encoded: (B, D, T') and encoded_len: Tensor([T'])
        """
        # convert to (B, T, F) for StridingSubsampling
        x = features.transpose(1, 2)
        x, length = self.pre_encode(x, lengths)  # x: (B, T', D)
        max_len = x.size(1)
        x, pos_emb = self.pos_enc(x)  # pos_emb is (cos,sin)

        pad_mask = torch.arange(0, max_len, device=x.device).expand(length.size(0), -1) >= length.unsqueeze(1)
        att_mask = None
        for layer in self.layers:
            x = layer(x, pos_emb, att_mask=att_mask, pad_mask=pad_mask)

        # return (B, D, T') to match original code
        return x.transpose(1, 2), length


# =====================================================================================
# RNNT Decoder + Joint + Greedy decode
# =====================================================================================
class RNNTDecoder(nn.Module):
    def __init__(self, pred_hidden: int = 320, pred_rnn_layers: int = 1, num_classes: int = 34):
        super().__init__()
        self.blank_id = num_classes - 1
        self.pred_hidden = pred_hidden
        self.embed = nn.Embedding(num_classes, pred_hidden, padding_idx=self.blank_id)
        self.lstm = nn.LSTM(pred_hidden, pred_hidden, pred_rnn_layers)

    def predict(self, x: Tensor, state: Tuple[Tensor, Tensor], batch_size: int = 1) -> Tuple[Tensor, Tuple[Tensor, Tensor]]:
        """
        x: Tensor of labels (batch, 1) or None
        state: (h, c) each with shape (num_layers, batch, hidden)
        returns: (out, new_state) where out is (batch, 1, pred_hidden)
        """
        if x is not None:
            emb = self.embed(x)
        else:
            emb = torch.zeros((batch_size, 1, self.pred_hidden), device=next(self.parameters()).device)
        g, hid = self.lstm(emb.transpose(0, 1), state)
        return g.transpose(0, 1), hid

    def forward(self, x: Tensor, h: Tensor, c: Tensor):
        emb = self.embed(x)
        g, (h, c) = self.lstm(emb.transpose(0, 1), (h, c))
        return g.transpose(0, 1), h, c


class RNNTJoint(nn.Module):
    def __init__(self, enc_hidden: int = 768, pred_hidden: int = 320, joint_hidden: int = 320, num_classes: int = 34):
        super().__init__()
        self.pred = nn.Linear(pred_hidden, joint_hidden)
        self.enc = nn.Linear(enc_hidden, joint_hidden)
        self.joint_net = nn.Sequential(nn.ReLU(), nn.Linear(joint_hidden, num_classes))

    def joint(self, encoder_out: Tensor, decoder_out: Tensor) -> Tensor:
        enc = self.enc(encoder_out).unsqueeze(2)
        pred = self.pred(decoder_out).unsqueeze(1)
        return self.joint_net(enc + pred).log_softmax(-1)

    def forward(self, enc: Tensor, dec: Tensor) -> Tensor:
        return self.joint(enc.transpose(1, 2), dec.transpose(1, 2))


class RNNTGreedyDecoding:
    def __init__(self, vocabulary: List[str], max_symbols_per_step: int = 3):
        self.tokenizer = vocabulary
        self.blank_id = len(self.tokenizer)
        self.max_symbols_per_step = max_symbols_per_step

    @torch.inference_mode()
    def decode(self, head_decoder: RNNTDecoder, head_joint: RNNTJoint, encoded: Tensor, enc_len: Tensor) -> List[str]:
        """
        encoded: (B, C, T')  (as returned by ConformerEncoder)
        enc_len: (B,)
        returns list of decoded texts length B
        """
        b = encoded.shape[0]
        texts = []
        encoded = encoded.transpose(1, 2)  # (B, T', C)
        for i in range(b):
            x = encoded[i, :, :].unsqueeze(1)  # (T', 1, C)? careful in our joint usage below
            L = int(enc_len[i].item())
            # we'll follow logic from original: iterate frames
            hyp = []
            dec_state = None
            last_label = None
            for t in range(L):
                f = x[t, :, :].unsqueeze(1)  # shape (1, C) -> make consistent below
                new_symbols = 0
                not_blank = True
                while not_blank and new_symbols < self.max_symbols_per_step:
                    # pred
                    g, hid = head_decoder.predict(last_label, dec_state, batch_size=1)
                    # joint expects encoder frame and decoder output
                    # prepare shapes like original code: enc_features[:, :, [j]], pred_outputs[0].swapaxes(1,2)
                    # Here we call joint.joint which expects enc: (batch, enc_hidden) and dec: (batch, pred_hidden, 1?) We'll adapt.
                    # We'll use head_joint.joint with inputs shaped accordingly.
                    # g is shape (batch, 1, pred_hidden)
                    # f currently (1,1,C) => need (batch, C)
                    enc_frame = encoded[i, t, :].unsqueeze(0)  # (1, C)
                    # decoder out g: (1, 1, pred_hidden) -> squeeze to (1, pred_hidden)
                    dec_out = g.squeeze(1)
                    # joint.joint expects encoder_out (batch, enc_hidden) and decoder_out (batch, pred_hidden)
                    joint_logits = head_joint.joint(enc_frame, dec_out)  # returns logsoftmax over classes with shape (batch,1,1,C?) but we implemented joint->logsoftmax(-1)
                    # joint returns shape (batch, 1, 1, C) in original; our implementation returns (batch, 1, 1, C)? To be safe get argmax:
                    # flatten
                    token = int(joint_logits.view(-1).argmax().item())
                    if token != self.blank_id:
                        hyp.append(token)
                        dec_state = hid
                        last_label = torch.tensor([[hyp[-1]]], device=encoded.device)
                        new_symbols += 1
                    else:
                        not_blank = False

            texts.append("".join(self.tokenizer[t] for t in hyp))
        return texts


# =====================================================================================
# GigaASR - оболочка: создаёт модули, загружает веса, транскрибирует
# =====================================================================================
class GigaASR:
    def __init__(self, ckpt_path: str, device: str = "cpu"):
        """
        ckpt_path: путь к v2_rnnt.ckpt
        device: "cpu" или "cuda"
        """
        self.device = torch.device(device)
        if not os.path.exists(ckpt_path):
            raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

        # Загружаем чекпоинт (map_location cpu, безопаснее)
        print("[GigaASR] Loading checkpoint (torch.load)...")
        ckpt = torch.load(ckpt_path, map_location="cpu")
        if "cfg" not in ckpt or "state_dict" not in ckpt:
            raise RuntimeError("Checkpoint must contain 'cfg' and 'state_dict' keys")

        cfg = ckpt["cfg"]
        sd = ckpt["state_dict"]

        # labels / vocab
        self.vocab = cfg.get("labels") or cfg.get("decoding", {}).get("vocabulary")
        if self.vocab is None:
            raise RuntimeError("Vocabulary not found in checkpoint cfg")
        # blank id = len(vocab)
        self.blank_id = len(self.vocab)
        self.num_classes = self.blank_id + 1

        # Instantiate modules according to cfg (match parameters we extracted earlier)
        pre_cfg = cfg.get("preprocessor", {"sample_rate": SAMPLE_RATE, "features": 64})
        self.pre = FeatureExtractor(sample_rate=pre_cfg.get("sample_rate", SAMPLE_RATE),
                                    features=pre_cfg.get("features", 64)).to(self.device)

        enc_cfg = cfg.get("encoder", {})
        self.encoder = ConformerEncoder(
            feat_in=enc_cfg.get("feat_in", 64),
            n_layers=enc_cfg.get("n_layers", 16),
            d_model=enc_cfg.get("d_model", 768),
            subsampling_factor=enc_cfg.get("subsampling_factor", 4),
            ff_expansion_factor=enc_cfg.get("ff_expansion_factor", 4),
            self_attention_model=enc_cfg.get("self_attention_model", "rotary"),
            pos_emb_max_len=enc_cfg.get("pos_emb_max_len", 5000),
            n_heads=enc_cfg.get("n_heads", 16),
            conv_kernel_size=enc_cfg.get("conv_kernel_size", 31),
        ).to(self.device)

        head_cfg = cfg.get("head", {})
        decoder_cfg = head_cfg.get("decoder", {"pred_hidden": 320, "pred_rnn_layers": 1, "num_classes": self.num_classes})
        joint_cfg = head_cfg.get("joint", {"enc_hidden": 768, "pred_hidden": 320, "joint_hidden": 320, "num_classes": self.num_classes})

        self.decoder = RNNTDecoder(**decoder_cfg).to(self.device)
        self.joint = RNNTJoint(**joint_cfg).to(self.device)

        # decoding helper
        decoding_cfg = cfg.get("decoding", {})
        vocab_from_cfg = decoding_cfg.get("vocabulary", self.vocab)
        self.greedy = RNNTGreedyDecoding(vocabulary=vocab_from_cfg, max_symbols_per_step=3)

        # загрузка весов: гибкий загрузчик
        print("[GigaASR] Loading weights into modules (flexible mapping)...")
        missing, unexpected = self._flexible_load(sd, verbose=True)
        print("[GigaASR] load finished. Missing keys count:", len(missing), "Unexpected keys count:", len(unexpected))

        # set eval
        self.eval()

    def eval(self):
        self.pre.eval()
        self.encoder.eval()
        self.decoder.eval()
        self.joint.eval()

    def to(self, device: str):
        self.device = torch.device(device)
        self.pre.to(self.device)
        self.encoder.to(self.device)
        self.decoder.to(self.device)
        self.joint.to(self.device)

    # ----------------------------
    # Гибкий загрузчик весов
    # ----------------------------
    def _flexible_load(self, checkpoint_state: Dict[str, torch.Tensor], verbose: bool = False) -> Tuple[List[str], List[str]]:
        """
        Попытка максимально гибко разнести ключи из checkpoint_state по подмодулям:
        self.pre, self.encoder, self.decoder, self.joint

        Правила сопоставления (в порядке приоритета):
        1) если ключ начинается с явного префикса 'preprocessor.', 'encoder.', 'head.decoder.', 'head.joint.' и т.п. —
           используем этот префикс для определения модуля.
        2) иначе пробуем найти соответствие по концу имени параметра (suffix-match) с параметрами каждого модуля.
        3) в конце — если не удалось сопоставить, считаем ключ непредвиденным.
        """
        modules = {
            "preprocessor": self.pre,
            "encoder": self.encoder,
            "head.decoder": self.decoder,
            "head.joint": self.joint,
            # также иногда встречаются префиксы без 'head.'
            "decoder": self.decoder,
            "joint": self.joint,
        }

        # precompute module param names
        module_param_names = {k: list(m.state_dict().keys()) for k, m in modules.items()}

        assigned = {k: {} for k in modules.keys()}
        unexpected = []
        # First pass: prefix matching
        for k, v in checkpoint_state.items():
            placed = False
            for prefix in modules.keys():
                if k.startswith(prefix + "."):
                    subkey = k[len(prefix) + 1 :]
                    assigned[prefix][subkey] = v
                    placed = True
                    break
                # also accept keys like "module.encoder.xxx" -> try removing "module."
                if k.startswith("module." + prefix + "."):
                    subkey = k[len("module." + prefix) + 1 :]
                    assigned[prefix][subkey] = v
                    placed = True
                    break
            if not placed:
                # leave for second pass
                pass

        # Second pass: suffix matching for remaining keys
        for k, v in checkpoint_state.items():
            already = False
            for prefix in assigned:
                # if assigned earlier by prefix, skip
                # check if k corresponds to any already assigned item
                # if plain prefix assigned, it will have subkey entries; check presence:
                if any(k == (prefix + "." + sub) or k == ("module." + prefix + "." + sub) for sub in assigned[prefix].keys()):
                    already = True
                    break
            if already:
                continue

            # Try suffix match: find module param name that equals suffix of k
            matched = False
            for mod_name, names in module_param_names.items():
                for name in names:
                    if k.endswith(name):
                        assigned[mod_name][name] = v
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                # try to strip common prefixes like "model." or "module."
                key_strip = k
                for pfx in ("model.", "module.", "net.", "state_dict."):
                    if key_strip.startswith(pfx):
                        key_strip = key_strip[len(pfx) :]
                matched2 = False
                for mod_name, names in module_param_names.items():
                    for name in names:
                        if key_strip.endswith(name):
                            assigned[mod_name][name] = v
                            matched2 = True
                            break
                    if matched2:
                        break
                if not matched2:
                    unexpected.append(k)

        # Load into modules using load_state_dict(strict=False)
        missing_all = []
        unexpected_all = list(unexpected)  # start with unexpected
        for mod_prefix, module in modules.items():
            subdict = assigned.get(mod_prefix, {})
            if len(subdict) == 0:
                # nothing matched by prefix; try to assemble by direct mapping using suffix matches (we already added some)
                subdict = assigned.get(mod_prefix, {})

            try:
                # module.load_state_dict expects keys matching module.state_dict keys
                m_missing, m_unexpected = module.load_state_dict(subdict, strict=False)
                # PyTorch returns nothing but raises in older API; to be safe, we compute missing ourselves:
                # We'll compute missing keys by comparing module.state_dict keys vs subdict.keys()
                module_keys = set(module.state_dict().keys())
                provided_keys = set(subdict.keys())
                missing_keys = sorted(list(module_keys - provided_keys))
                # unexpected in this context are keys from subdict that didn't match module keys
                unexpected_keys = sorted(list(provided_keys - module_keys))
                missing_all.extend([f"{mod_prefix}.{k}" for k in missing_keys])
                unexpected_all.extend([f"{mod_prefix}.{k}" for k in unexpected_keys])
                if verbose:
                    print(f"[_flexible_load] module={mod_prefix}: provided={len(provided_keys)} module_keys={len(module_keys)} missing={len(missing_keys)} unexpected(provided not used)={len(unexpected_keys)}")
            except Exception as e:
                # fallback: try to match by name one-by-one (robust)
                print(f"[_flexible_load] Warning: module {mod_prefix} load_state_dict failed with {e}. Falling back to per-param copy.")
                module_sd = module.state_dict()
                m_missing_local = []
                m_unexpected_local = []
                for name, param in module_sd.items():
                    if name in subdict:
                        try:
                            module_sd[name].copy_(subdict[name])
                        except Exception:
                            m_missing_local.append(name)
                    else:
                        m_missing_local.append(name)
                missing_all.extend([f"{mod_prefix}.{x}" for x in m_missing_local])
                # Unexpected keys = provided keys not matched
                provided_keys = set(subdict.keys())
                unexpected_all.extend([f"{mod_prefix}.{x}" for x in (provided_keys - set(module_sd.keys()))])

        # dedupe lists
        missing_all = sorted(list(dict.fromkeys(missing_all)))
        unexpected_all = sorted(list(dict.fromkeys(unexpected_all)))
        return missing_all, unexpected_all

    # ----------------------------
    # Транскрибирование
    # ----------------------------
    @torch.inference_mode()
    def transcribe(self, audio_path: str) -> str:
        """
        Возвращает одну строку с расшифровкой (короткий файл).
        Для длинных файлов можно сегментировать (не реализовано здесь).
        """
        wav = load_audio(audio_path, SAMPLE_RATE).to(self.device)
        wav = wav.unsqueeze(0)  # (1, N)
        length = torch.tensor([wav.shape[-1]], device=self.device)

        feats, feat_len = self.pre(wav, length)  # feats: (1, n_mels, T)
        enc, enc_len = self.encoder(feats, feat_len)  # enc: (1, C, T')

        texts = self.greedy.decode(self.decoder, self.joint, enc.to(self.device), enc_len.to(self.device))
        return texts[0] if len(texts) > 0 else ""


# =====================================================================================
# Пример использования (если файл запущен напрямую)
# =====================================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ASR for GigaAM v2 RNN-T (single-file)")
    parser.add_argument("--ckpt", type=str, required=True, help="Path to v2_rnnt.ckpt")
    parser.add_argument("--wav", type=str, required=True, help="Path to audio file (wav/mp3/...)")
    parser.add_argument("--device", type=str, default="cpu", help="cpu or cuda")
    args = parser.parse_args()

    model = GigaASR(args.ckpt, device=args.device)
    print("Transcribing ...")
    txt = model.transcribe(args.wav)
    print("Result:", txt)
