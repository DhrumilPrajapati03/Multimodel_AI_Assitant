FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=7860 \
    ONNX_THREADS=1

# Run as a normal user (uid 1000) that owns /app, so it can write audio_out/ and
# open the Chroma index. Owning files from the start avoids a duplicate chown layer.
RUN useradd -m -u 1000 user && mkdir /app && chown user:user /app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Browser speaks the replies: Piper would use ~165 MB of a 512 MB free plan.
# Set TTS_MODE=server on hosts with more memory to use the Piper voice.
ENV TTS_MODE=browser

COPY --chown=user:user . .
USER user

# Bake the Piper voice, the ONNX embedding model and the Chroma index into the image,
# so the container starts fast and never downloads anything at runtime.
# (Speech-to-text runs on Groq, so there is no local Whisper model.)
RUN mkdir -p models/voices audio_out \
 && cd models/voices && python -m piper.download_voices en_US-lessac-medium && cd /app \
 && PYTHONPATH=/app python scripts/ingest.py

EXPOSE 7860
CMD ["python", "start.py"]
