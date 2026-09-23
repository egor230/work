#!/usr/bin/env bash
#
# Пакует каталог Chrome/Chromium-расширения в .crx (CRX3, канонический формат).
#
# Формат побайтово воспроизводит Chromium (components/crx_file):
#
#   crx3.proto:
#     message AsymmetricKeyProof { optional bytes public_key = 1;
#                                  optional bytes signature  = 2; }
#     message CrxFileHeader { repeated AsymmetricKeyProof sha256_with_rsa = 2;
#                             optional bytes signed_header_data = 10000; }
#     message SignedData { optional bytes crx_id = 1; }   // ровно 16 байт
#
#   crx_creator.cc: ключ в proof — X.509 SPKI; подпись = RSA-SHA256(PKCS1v15)
#     над  "CRX3 SignedData\0" + LE32(len(SignedData)) + SignedData + zip;
#     crx_id = SHA-256(SPKI)[:16].
#
#   crx_verifier.cc: публичный ключ парсится ТОЛЬКО как SPKI (иначе ошибка
#     CRX_SIGNATURE_VERIFICATION_INITIALIZATION_FAILED); ID расширения
#     берётся из SignedData.crx_id.
#
# manifest.json: поле "key" заменяется на base64(SPKI) подписного ключа —
# ровно это Chrome сам делает при установке .crx (RewriteManifestFile), так
# что ID одинаков и при установке CRX, и при «Load unpacked».
#
# После сборки скрипт верифицирует готовый файл тем же алгоритмом, что
# crx_verifier.cc, и завершается с ОШИБКОЙ при любом расхождении — битый
# .crx на диск не попадёт.
#
# Использование:  ./package-crx.sh [каталог_расширения]
# Результат:      <родитель каталога>/<имя из manifest>.crx
#
set -euo pipefail

EXT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
EXT_DIR="$(cd "$EXT_DIR" && pwd)"
[[ -f "$EXT_DIR/manifest.json" ]] || { echo "ERROR: $EXT_DIR/manifest.json не найден" >&2; exit 1; }
PARENT="$(dirname "$EXT_DIR")"

EXT_NAME="$(python3 - "$EXT_DIR/manifest.json" <<'PY'
import json, sys, re
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(re.sub(r"[^A-Za-z0-9._-]", "_", d.get("name", "extension")).rstrip("_"))
PY
)"

PEM="$EXT_DIR/efyt_private.pem"
if [[ ! -f "$PEM" ]]; then
  echo "[*] Приватного ключа нет — генерирую efyt_private.pem (один раз; он определяет ID расширения)"
  python3 - "$PEM" <<'PY'
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
Path(sys.argv[1]).write_bytes(rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
PY
fi

WORKDIR="$(mktemp -d /tmp/crx_pack.XXXXXX)"
trap 'rm -rf "$WORKDIR"' EXIT

python3 - "$EXT_DIR" "$WORKDIR/out.crx" "$PEM" <<'PY'
import sys, os, io, json, struct, base64, zipfile, hashlib
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

ext_dir, crx_out, pem_path = (Path(a) for a in sys.argv[1:4])

def die(m):
    print("[!] VERIFY FAIL:", m)
    sys.exit(1)

# ---------- protobuf helpers ----------
def wv(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | 0x80 if v else b)
        if not v:
            return bytes(out)

def ld(num, payload):                      # length-delimited поле
    return wv((num << 3) | 2) + wv(len(payload)) + payload

def rv(b, i):
    v = s = 0
    while True:
        x = b[i]; i += 1
        v |= (x & 0x7F) << s; s += 7
        if not x & 0x80:
            return v, i

def parse_pb(b):
    out, i = {}, 0
    while i < len(b):
        tag, i = rv(b, i)
        num, wt = tag >> 3, tag & 7
        if wt != 2:
            die(f"wire type {wt} в поле {num} не поддерживается")
        ln, i = rv(b, i)
        out.setdefault(num, []).append(b[i:i+ln]); i += ln
    return out

def to_id(b16):
    return "".join(chr(ord('a') + (x >> 4)) + chr(ord('a') + (x & 15)) for x in b16)

# ---------- 1. ключ и его SPKI ----------
key = load_pem_private_key(pem_path.read_bytes(), password=None)
spki = key.public_key().public_bytes(serialization.Encoding.DER,
                                     serialization.PublicFormat.SubjectPublicKeyInfo)
crx_id = hashlib.sha256(spki).digest()[:16]
spki_b64 = base64.b64encode(spki).decode()
print("[*] ID расширения (SHA-256(SPKI)[:16]):", to_id(crx_id))

# ---------- 2. manifest "key" = base64(SPKI) (как делает Chrome) ----------
mf_path = ext_dir / "manifest.json"
mf = json.loads(mf_path.read_text(encoding="utf-8"))
if mf.get("key") != spki_b64:
    mf["key"] = spki_b64
    mf_path.write_text(json.dumps(mf, indent=3, ensure_ascii=False) + "\n", encoding="utf-8")
    print('[*] manifest.json: "key" -> base64(SPKI) подписного ключа')
else:
    print('[*] manifest.json: "key" уже совпадает с SPKI')

# ---------- 3. zip ----------
SKIP_DIRS = {"_metadata", ".git", "__MACOSX"}
SKIP_FILES = {"package-crx.sh", "efyt_private.pem", "README-CUSTOM.md", ".DS_Store",
              "config-backup.json", "save-config.sh", "restore-config.sh"}
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(ext_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for fn in sorted(files):
            if fn in SKIP_FILES or fn.endswith((".pem", ".crx")):
                continue
            p = Path(root) / fn
            zf.write(p, p.relative_to(ext_dir).as_posix())
archive = buf.getvalue()
print(f"[*] zip: {len(archive)} байт")

# ---------- 4. подпись и сборка (в точности crx_creator.cc) ----------
signed_data = ld(1, crx_id)                # SignedData { crx_id = 1 }
msg = (b"CRX3 SignedData\x00"
       + struct.pack("<I", len(signed_data))
       + signed_data
       + archive)
signature = key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
proof = ld(1, spki) + ld(2, signature)     # public_key = 1, signature = 2
header = ld(2, proof) + ld(10000, signed_data)
crx_out.write_bytes(b"Cr24" + struct.pack("<II", 3, len(header)) + header + archive)

# ---------- 5. самопроверка (в точности crx_verifier.cc) ----------
raw = crx_out.read_bytes()
if raw[:4] != b"Cr24": die("магия")
ver, hsize = struct.unpack("<II", raw[4:12])
if ver != 3: die("версия")
hdr, arch2 = raw[12:12+hsize], raw[12+hsize:]
if len(hdr) != hsize: die("обрезанный заголовок")
for tok in (b"PK\x05\x06", b"PK\x06\x07", b"PK\x06\x06"):
    if tok in hdr: die("EOCD-токен внутри заголовка")
top = parse_pb(hdr)
proofs = top.get(2, [])
sd_b = top.get(10000, [None])[0]
if not proofs: die("нет proof sha256_with_rsa (поле 2)")
if not sd_b: die("нет signed_header_data (поле 10000)")
sd = parse_pb(sd_b)
declared = sd.get(1, [None])[0]
if not declared or len(declared) != 16: die("SignedData.crx_id не 16 байт")
if declared != crx_id: die("SignedData.crx_id не совпадает с вычисленным")
vmsg = b"CRX3 SignedData\x00" + struct.pack("<I", len(sd_b)) + sd_b + arch2
matched = False
for pr in proofs:
    pf = parse_pb(pr)
    pub, sig = pf.get(1, [None])[0], pf.get(2, [None])[0]
    if not pub or not sig: die("в proof нет public_key(1) или signature(2)")
    try:
        k = serialization.load_der_public_key(pub)   # только SPKI парсится
    except Exception as e:
        die(f"public_key из proof не парсится как SPKI: {e}")
    if not isinstance(k, rsa.RSAPublicKey): die("ключ в proof не RSA")
    if hashlib.sha256(pub).digest()[:16] == declared:
        matched = True
        try:
            k.verify(sig, vmsg, padding.PKCS1v15(), hashes.SHA256())
        except Exception:
            die("подпись не верифицируется над каноническим сообщением")
if not matched: die("ни один proof не даёт crx_id (REQUIRED_PROOF_MISSING у Chrome)")
zf = zipfile.ZipFile(io.BytesIO(arch2))
if zf.testzip() is not None: die("битый zip")
if "manifest.json" not in zf.namelist(): die("в zip нет manifest.json")
mf2 = json.loads(zf.read("manifest.json"))
if mf2.get("key") != spki_b64: die('"key" манифеста внутри пакета != base64(SPKI)')
print(f"[+] VERIFY OK: header={hsize}B, zip={len(arch2)}B, SPKI={len(spki)}B, sig={len(signature)}B")
print("[+] ID расширения:", to_id(declared))
PY

OUT="$PARENT/${EXT_NAME}.crx"
cp -f "$WORKDIR/out.crx" "$OUT"
echo "[+] CRX собран и верифицирован: $OUT"
