FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=7860 \
    ONNX_THREADS=1

# Run as a normal user (uid 1000) that owns /app, so it can write audio_out/.
# Owning files from the start avoids a duplicate chown layer.
RUN useradd -m -u 1000 user && mkdir /app && chown user:user /app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Browser speaks the replies: Piper would use ~165 MB of a 512 MB free plan.
# On hosts with more memory set TTS_MODE=piper, or TTS_MODE=groq for Groq's voice.
ENV TTS_MODE=browser

COPY --chown=user:user . .
USER user

# Bake the Piper voice and the ONNX embedding model into the image so nothing is
# downloaded at runtime. Speech-to-text, vision and the LLM all run on Groq.
# The knowledge base lives in Postgres: the bundled PDFs in data/ are indexed into it
# on the first start, and staff upload more at /admin.
RUN mkdir -p models/voices audio_out \
 && cd models/voices && python -m piper.download_voices en_US-lessac-medium && cd /app \
 && python -c "from tools.embeddings import ensure_model; ensure_model()"

EXPOSE 7860
CMD ["python", "start.py"]
