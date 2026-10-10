"""all-MiniLM-L6-v2 sentence embeddings with ONNX Runtime (no PyTorch, no Chroma).

Same model files and maths as chromadb's ONNXMiniLM_L6_V2 - mean pooling over the
attention mask, then L2 normalisation - so vectors match sentence-transformers.
"""
import hashlib
import tarfile
import urllib.request
from pathlib import Path

import numpy as np

import tools.onnx_threads  # noqa: F401  (must run before the model loads)
import onnxruntime
from tokenizers import Tokenizer

MODEL_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
MODEL_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "embeddings"
DIM = 384

_session = None
_tokenizer = None


def ensure_model() -> Path:
    """Download and unpack the model once; returns the folder holding model.onnx."""
    folder = MODEL_DIR / "onnx"
    if (folder / "model.onnx").exists() and (folder / "tokenizer.json").exists():
        return folder
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    archive = MODEL_DIR / "onnx.tar.gz"
    print(f"Downloading embedding model to {MODEL_DIR} ...")
    urllib.request.urlretrieve(MODEL_URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != MODEL_SHA256:
        archive.unlink()
        raise RuntimeError("Embedding model download is corrupted (SHA-256 mismatch).")
    with tarfile.open(archive) as tar:
        tar.extractall(MODEL_DIR, filter="data")
    archive.unlink()
    return folder


def _load():
    global _session, _tokenizer
    if _session is None:
        folder = ensure_model()
        tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        tok.enable_truncation(max_length=256)
        tok.enable_padding(pad_id=0, pad_token="[PAD]")   # pad to the longest text in the batch
        _tokenizer = tok
        _session = onnxruntime.InferenceSession(
            str(folder / "model.onnx"),
            sess_options=onnxruntime.SessionOptions(),
            providers=["CPUExecutionProvider"],
        )
    return _session, _tokenizer


def embed(texts, batch_size: int = 16) -> np.ndarray:
    """Return an (n, 384) float32 array of unit-length vectors."""
    texts = list(texts)
    if not texts:
        return np.zeros((0, DIM), dtype=np.float32)
    session, tokenizer = _load()
    out = []
    for i in range(0, len(texts), batch_size):
        encoded = tokenizer.encode_batch(texts[i:i + batch_size])
        ids = np.array([e.ids for e in encoded], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        hidden = session.run(None, {
            "input_ids": ids,
            "attention_mask": mask,
            "token_type_ids": np.zeros_like(ids),
        })[0]
        weights = mask[..., None].astype(np.float32)
        pooled = (hidden * weights).sum(1) / np.clip(weights.sum(1), 1e-9, None)
        pooled /= np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
        out.append(pooled.astype(np.float32))
    return np.concatenate(out)
