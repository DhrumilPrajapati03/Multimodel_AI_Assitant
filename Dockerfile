FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    HOST=0.0.0.0 \
    PORT=7860

WORKDIR /app

# CPU-only PyTorch first: the default Linux wheel bundles CUDA and adds several GB.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Bake every model and the vector index into the image, so the container starts fast
# and never downloads anything at runtime:
#   Piper voice (TTS), Whisper "base" (STT), MiniLM embeddings + Chroma index (RAG).
RUN mkdir -p models/voices \
 && cd models/voices && python -m piper.download_voices en_US-lessac-medium && cd /app \
 && python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')" \
 && PYTHONPATH=/app python scripts/ingest.py

# Run as a normal user (uid 1000) - Hugging Face Spaces require it - and let it write
# replies to audio_out/ and open the Chroma index.
RUN useradd -m -u 1000 user && mkdir -p audio_out && chown -R user:user /app
USER user

EXPOSE 7860
CMD ["python", "start.py"]
